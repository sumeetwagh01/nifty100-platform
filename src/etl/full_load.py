"""
src/etl/full_load.py

Full Data Load Orchestrator (Module 1, Feature 1.6-1.7, Sprint 1 Day 5).

Wires together the Day 2 loader, Day 2 normaliser, Day 3 validator, and
Day 4 DB loader into a single idempotent pipeline:

    1. Load all 12 Excel files via src/etl/loader.py
    2. Normalise company_id and year columns (Day 2 normaliser)
    3. Drop rows that would violate CRITICAL DQ rules before insert:
         DQ-07: year = PARSE_ERROR  (TTM, stub periods, garbage) -> reject
         DQ-08: company_id = None   (untickerable raw values)    -> reject
         DQ-02: duplicate (company_id, year)  -> keep last occurrence
         DQ-03: company_id not in companies   -> reject as orphan
    4. Insert into nifty100.db in FK-dependency order (companies first).
    5. Write load_audit.csv: table, rows_in, rows_out, rejected,
       timestamp, runtime_s  (Section 9, Feature 1.7).
    6. Run PRAGMA foreign_key_check -> expect 0 violations (AC-03).

Run:
    python src/etl/full_load.py           # full load (errors if DB exists)
    python src/etl/full_load.py --reset   # drop DB and reload cleanly
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# path bootstrap so this file works when run directly
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from db.loader import (  # noqa: E402
    create_database,
    foreign_key_check,
    insert_analysis,
    insert_balancesheet,
    insert_cashflow,
    insert_companies,
    insert_documents,
    insert_market_cap,
    insert_profitandloss,
    insert_prosandcons,
    insert_sectors,
    insert_stock_prices,
)
from src.etl.loader import (  # noqa: E402
    load_all_core_files,
    load_all_supplementary_files,
)
from src.etl.normaliser import (  # noqa: E402
    PARSE_ERROR,
    normalize_ticker,
    normalize_year,
)

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DB_PATH", "data/nifty100.db"))
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH

LOAD_AUDIT_PATH = Path(os.getenv("LOAD_AUDIT_PATH", "load_audit.csv"))
if not LOAD_AUDIT_PATH.is_absolute():
    LOAD_AUDIT_PATH = PROJECT_ROOT / LOAD_AUDIT_PATH


# ---------------------------------------------------------------------------
# Normalisation & cleaning helpers
# ---------------------------------------------------------------------------


def _norm_ticker(df: pd.DataFrame, col: str = "company_id") -> pd.DataFrame:
    if col not in df.columns:
        return df
    df = df.copy()
    df[col] = df[col].apply(normalize_ticker)
    return df


def _norm_year(df: pd.DataFrame, col: str = "year") -> pd.DataFrame:
    if col not in df.columns:
        return df
    df = df.copy()
    df[col] = df[col].apply(normalize_year)
    return df


def _drop_parse_errors(df: pd.DataFrame, col: str = "year") -> tuple[pd.DataFrame, int]:
    if col not in df.columns:
        return df, 0
    mask = df[col] == PARSE_ERROR
    return df[~mask].reset_index(drop=True), int(mask.sum())


def _drop_null_tickers(
    df: pd.DataFrame, col: str = "company_id"
) -> tuple[pd.DataFrame, int]:
    if col not in df.columns:
        return df, 0
    mask = df[col].isna()
    return df[~mask].reset_index(drop=True), int(mask.sum())


def _dedup(df: pd.DataFrame, subset: list[str]) -> tuple[pd.DataFrame, int]:
    """Keep last occurrence of each key combination (DQ-02 resolution)."""
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="last").reset_index(drop=True)
    return df, before - len(df)


def _drop_orphans(
    df: pd.DataFrame, valid_ids: set, col: str = "company_id"
) -> tuple[pd.DataFrame, int]:
    """Remove rows whose company_id is not in the master list (DQ-03)."""
    if col not in df.columns:
        return df, 0
    mask = ~df[col].isin(valid_ids)
    return df[~mask].reset_index(drop=True), int(mask.sum())


# ---------------------------------------------------------------------------
# Per-table clean pipelines
# ---------------------------------------------------------------------------


def _clean_companies(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    df = _norm_ticker(df, col="id")
    df, n1 = _drop_null_tickers(df, col="id")
    df, n2 = _dedup(df, ["id"])
    return df, {"rows_in": rows_in, "rejected": n1 + n2, "rows_out": len(df)}


def _clean_time_series(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df = _norm_year(df)
    df, n = _drop_parse_errors(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    df, n = _dedup(df, ["company_id", "year"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_analysis(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    df, n = _dedup(df, ["company_id"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_documents(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    if "Year" in df.columns:
        df = df.copy()
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        before = len(df)
        df = df.dropna(subset=["Year"]).reset_index(drop=True)
        rejected += before - len(df)
        df["Year"] = df["Year"].astype(int)
    df, n = _dedup(df, ["company_id", "Year"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_prosandcons(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_sectors(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    df, n = _dedup(df, ["company_id"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_stock_prices(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    df, n = _dedup(df, ["company_id", "date"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


def _clean_market_cap(df: pd.DataFrame, valid_ids: set) -> tuple[pd.DataFrame, dict]:
    rows_in = len(df)
    rejected = 0
    df = _norm_ticker(df)
    df, n = _drop_null_tickers(df)
    rejected += n
    df, n = _drop_orphans(df, valid_ids)
    rejected += n
    df, n = _dedup(df, ["company_id", "year"])
    rejected += n
    return df, {"rows_in": rows_in, "rejected": rejected, "rows_out": len(df)}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def _write_audit(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["table", "rows_in", "rows_out", "rejected", "timestamp", "runtime_s"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_full_load(
    db_path: Optional[Path] = None,
    audit_path: Optional[Path] = None,
    reset: bool = False,
) -> list[dict]:
    """
    Run the complete 12-file load pipeline. Returns the audit records list.
    Pass reset=True to delete the existing DB and reload from scratch.
    """
    db_path = Path(db_path or DB_PATH)
    audit_path = Path(audit_path or LOAD_AUDIT_PATH)

    if reset and db_path.exists():
        db_path.unlink()
        logger.info("Existing database deleted (--reset mode).")

    logger.info("Building schema at %s", db_path)
    conn = create_database(db_path=db_path)

    # 1. load raw frames
    logger.info("Loading 7 core Excel files...")
    core = load_all_core_files()
    logger.info("Loading 5 supplementary Excel files...")
    supporting = load_all_supplementary_files()

    audit: list[dict] = []

    def _rec(table: str, stats: dict, t0: float) -> None:
        audit.append(
            {
                "table": table,
                "rows_in": stats["rows_in"],
                "rows_out": stats["rows_out"],
                "rejected": stats["rejected"],
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "runtime_s": round(time.time() - t0, 3),
            }
        )
        logger.info(
            "%-20s  in=%-6d  out=%-6d  rejected=%d",
            table,
            stats["rows_in"],
            stats["rows_out"],
            stats["rejected"],
        )

    # 2. companies first (parent table)
    t0 = time.time()
    co_raw = core.get("companies", pd.DataFrame())
    if co_raw.empty:
        logger.warning("companies.xlsx not found or empty — load cannot continue.")
        _write_audit(audit, audit_path)
        conn.close()
        return audit
    co_clean, stats = _clean_companies(co_raw)
    insert_companies(conn, co_clean)
    valid_ids: set = set(co_clean["id"].dropna())
    _rec("companies", stats, t0)

    # 3. core time-series
    for name, key, fn in [
        ("profitandloss", "profitandloss", insert_profitandloss),
        ("balancesheet", "balancesheet", insert_balancesheet),
        ("cashflow", "cashflow", insert_cashflow),
    ]:
        t0 = time.time()
        clean, stats = _clean_time_series(core.get(key, pd.DataFrame()), valid_ids)
        fn(conn, clean)
        _rec(name, stats, t0)

    # 4. other core tables
    for name, key, clean_fn, ins_fn in [
        ("analysis", "analysis", _clean_analysis, insert_analysis),
        ("documents", "documents", _clean_documents, insert_documents),
        ("prosandcons", "prosandcons", _clean_prosandcons, insert_prosandcons),
    ]:
        t0 = time.time()
        clean, stats = clean_fn(core.get(key, pd.DataFrame()), valid_ids)
        ins_fn(conn, clean)
        _rec(name, stats, t0)

    # 5. supplementary tables
    for name, key, clean_fn, ins_fn in [
        ("sectors", "sectors", _clean_sectors, insert_sectors),
        ("stock_prices", "stock_prices", _clean_stock_prices, insert_stock_prices),
        ("market_cap", "market_cap", _clean_market_cap, insert_market_cap),
    ]:
        t0 = time.time()
        clean, stats = clean_fn(supporting.get(key, pd.DataFrame()), valid_ids)
        ins_fn(conn, clean)
        _rec(name, stats, t0)

    # 6. FK check
    fk_violations = foreign_key_check(conn)
    conn.close()

    # 7. write audit
    _write_audit(audit, audit_path)

    # 8. print summary
    print(f"\n{'='*63}")
    print("LOAD AUDIT SUMMARY")
    print(f"{'='*63}")
    print(f"{'Table':<22} {'In':>6} {'Out':>6} {'Rejected':>9} {'Time':>8}")
    print(f"{'-'*22} {'-'*6} {'-'*6} {'-'*9} {'-'*8}")
    total_in = total_out = total_rejected = 0
    for r in audit:
        print(
            f"{r['table']:<22} {r['rows_in']:>6} {r['rows_out']:>6} "
            f"{r['rejected']:>9} {r['runtime_s']:>7.2f}s"
        )
        total_in += r["rows_in"]
        total_out += r["rows_out"]
        total_rejected += r["rejected"]
    print(f"{'-'*22} {'-'*6} {'-'*6} {'-'*9}")
    print(f"{'TOTAL':<22} {total_in:>6} {total_out:>6} {total_rejected:>9}")
    print(f"\nAudit log: {audit_path}")
    print(
        f"FK check:  {len(fk_violations)} violation(s)  "
        f"{'✓ CLEAN' if not fk_violations else '*** INVESTIGATE ***'}"
    )

    return audit


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_full_load(reset="--reset" in sys.argv)
