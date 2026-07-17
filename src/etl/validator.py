"""
src/etl/validator.py

Schema / Data Quality Validator (Module 1 — Data Engineering & ETL Pipeline,
Sprint 1, Day 3). Implements all 16 DQ rules from Section 14 of the project
document and produces a flat violations table that gets written to
validation_failures.csv (columns: rule_id, severity, company_id, year,
field, issue — per AC-19).

Each DQ-xx rule is its own pure function: it takes a DataFrame (or a few
related DataFrames) and returns a list[Violation]. This keeps every rule
independently testable (see tests/dq/test_rules.py) and easy to re-run
selectively.

DQ-15 is the one exception: per the spec it's an *informational counter*
("Flag in load_audit only"), not a row-level violation, so it returns a
plain summary dict rather than a list of Violation objects and is excluded
from validation_failures.csv.

CRITICAL rules (DQ-01, 02, 03, 07, 08) are the ones the spec says should
"halt load" / "reject row" — that row-rejection wiring happens in the
SQLite loader (Day 4-5). This module's job is detection and reporting only.
"""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# Allow this file to be run directly (`python src/etl/validator.py`) as well
# as imported as a package (`from src.etl.validator import ...`). Direct
# script invocation sets sys.path[0] to this file's own directory, which
# breaks the `from src.etl...` import below unless the project root is
# added to sys.path first.
_PROJECT_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_FOR_IMPORTS))

import src.etl.normaliser as normaliser  # noqa: E402

logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DQ_LOG_PATH = Path(os.getenv("DQ_LOG_PATH", "validation_failures.csv"))
if not DQ_LOG_PATH.is_absolute():
    DQ_LOG_PATH = PROJECT_ROOT / DQ_LOG_PATH

CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

# Tables that carry a (company_id, year) composite key and therefore
# participate in DQ-02 (dedup), DQ-03 (FK), DQ-07 (year format), and
# DQ-16 (coverage).
TIME_SERIES_TABLES = ("profitandloss", "balancesheet", "cashflow")


@dataclass
class Violation:
    rule_id: str
    severity: str
    company_id: Optional[str]
    year: Optional[str]
    field: Optional[str]
    issue: str


def _violations_to_df(violations: list[Violation]) -> pd.DataFrame:
    if not violations:
        return pd.DataFrame(
            columns=["rule_id", "severity", "company_id", "year", "field", "issue"]
        )
    return pd.DataFrame([v.__dict__ for v in violations])


# ---------------------------------------------------------------------------
# DQ-01 — Company PK Uniqueness (CRITICAL)
# ---------------------------------------------------------------------------
def check_dq01_company_pk_uniqueness(companies: pd.DataFrame) -> list[Violation]:
    """len(companies) == companies.id.nunique() — halt load on failure."""
    dup_mask = companies["id"].duplicated(keep=False)
    violations = []
    for _, row in companies.loc[dup_mask].iterrows():
        violations.append(
            Violation(
                "DQ-01",
                CRITICAL,
                row["id"],
                None,
                "id",
                f"Duplicate company_id '{row['id']}' in companies table — halt load.",
            )
        )
    return violations


# ---------------------------------------------------------------------------
# DQ-02 — Annual PK Uniqueness (CRITICAL)
# ---------------------------------------------------------------------------
def check_dq02_annual_pk_uniqueness(
    df: pd.DataFrame, table_name: str
) -> list[Violation]:
    """No duplicate (company_id, year) pairs in P&L / BS / CF tables."""
    dup_mask = df.duplicated(subset=["company_id", "year"], keep=False)
    violations = []
    for _, row in df.loc[dup_mask].iterrows():
        violations.append(
            Violation(
                "DQ-02",
                CRITICAL,
                row.get("company_id"),
                row.get("year"),
                "company_id,year",
                f"Duplicate (company_id, year) pair in {table_name} — "
                "deduplicate, keep last occurrence.",
            )
        )
    return violations


# ---------------------------------------------------------------------------
# DQ-03 — FK Integrity (CRITICAL)
# ---------------------------------------------------------------------------
def check_dq03_fk_integrity(
    child: pd.DataFrame,
    companies: pd.DataFrame,
    table_name: str,
    company_col: str = "company_id",
) -> list[Violation]:
    """Every company_id in a child table must exist in companies.id."""
    valid_ids = set(companies["id"].dropna())
    orphan_mask = ~child[company_col].isin(valid_ids)
    violations = []
    for _, row in child.loc[orphan_mask].iterrows():
        violations.append(
            Violation(
                "DQ-03",
                CRITICAL,
                row.get(company_col),
                row.get("year"),
                company_col,
                f"Orphan row in {table_name}: company_id "
                f"'{row.get(company_col)}' not found in companies table.",
            )
        )
    return violations


# ---------------------------------------------------------------------------
# DQ-04 — Balance Sheet Balance (WARNING)
# ---------------------------------------------------------------------------
def check_dq04_balance_sheet_balance(
    bs: pd.DataFrame, tolerance: float = 0.01
) -> list[Violation]:
    """|total_assets - total_liabilities| / total_assets < 0.01."""
    violations = []
    for _, row in bs.iterrows():
        assets, liab = row.get("total_assets"), row.get("total_liabilities")
        if pd.isna(assets) or pd.isna(liab):
            continue
        if assets == 0:
            violations.append(
                Violation(
                    "DQ-04",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "total_assets",
                    "total_assets is zero — cannot compute balance ratio.",
                )
            )
            continue
        ratio = abs(assets - liab) / assets
        if ratio >= tolerance:
            violations.append(
                Violation(
                    "DQ-04",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "total_assets,total_liabilities",
                    f"Balance sheet does not balance: assets={assets}, "
                    f"liabilities={liab}, diff={ratio:.2%} (>= {tolerance:.0%}).",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-05 — OPM Cross-Check (WARNING)
# ---------------------------------------------------------------------------
def check_dq05_opm_cross_check(
    pl: pd.DataFrame, tolerance: float = 1.0
) -> list[Violation]:
    """|opm_percentage - (operating_profit/sales*100)| < 1.0."""
    violations = []
    for _, row in pl.iterrows():
        sales, op_profit, opm = (
            row.get("sales"),
            row.get("operating_profit"),
            row.get("opm_percentage"),
        )
        if pd.isna(sales) or pd.isna(op_profit) or pd.isna(opm) or sales == 0:
            continue
        computed_opm = op_profit / sales * 100
        diff = abs(opm - computed_opm)
        if diff >= tolerance:
            violations.append(
                Violation(
                    "DQ-05",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "opm_percentage",
                    f"Source opm_percentage={opm:.2f} vs computed "
                    f"{computed_opm:.2f} (diff={diff:.2f} >= {tolerance}).",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-06 — Positive Sales (WARNING)
# ---------------------------------------------------------------------------
def check_dq06_positive_sales(
    pl: pd.DataFrame, sectors: Optional[pd.DataFrame] = None
) -> list[Violation]:
    """sales > 0 for all non-bank/financial companies."""
    df = pl
    if sectors is not None:
        df = pl.merge(
            sectors[["company_id", "broad_sector"]], on="company_id", how="left"
        )
        df = df[df["broad_sector"] != "Financials"]

    violations = []
    for _, row in df.iterrows():
        sales = row.get("sales")
        if pd.isna(sales):
            continue
        if sales <= 0:
            violations.append(
                Violation(
                    "DQ-06",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "sales",
                    f"sales={sales} <= 0 — flagged, excluded from growth CAGR.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-07 — Year Format (CRITICAL)
# ---------------------------------------------------------------------------
def check_dq07_year_format(
    df: pd.DataFrame, table_name: str, year_col: str = "year"
) -> list[Violation]:
    """After normalize_year(), every value must match r'^\\d{4}-\\d{2}$'."""
    violations = []
    for _, row in df.iterrows():
        raw_year = row.get(year_col)
        normalised = normaliser.normalize_year(raw_year)
        if normalised == normaliser.PARSE_ERROR:
            violations.append(
                Violation(
                    "DQ-07",
                    CRITICAL,
                    row.get("company_id"),
                    str(raw_year),
                    year_col,
                    f"Unparseable {year_col} value '{raw_year}' in "
                    f"{table_name} — reject row.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-08 — Ticker Format (CRITICAL)
# ---------------------------------------------------------------------------
def check_dq08_ticker_format(
    df: pd.DataFrame, table_name: str, id_col: str = "company_id"
) -> list[Violation]:
    """company_id must normalise to a 2-12 char ticker (DQ-08)."""
    violations = []
    for _, row in df.iterrows():
        raw_ticker = row.get(id_col)
        normalised = normaliser.normalize_ticker(raw_ticker)
        if normalised is None:
            violations.append(
                Violation(
                    "DQ-08",
                    CRITICAL,
                    str(raw_ticker),
                    row.get("year"),
                    id_col,
                    f"Invalid {id_col} value '{raw_ticker}' in {table_name} "
                    "— missing or outside 2-12 char bound, reject row.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-09 — Net Cash Check (WARNING)
# ---------------------------------------------------------------------------
def check_dq09_net_cash_check(
    cf: pd.DataFrame, tolerance: float = 10
) -> list[Violation]:
    """|net_cash_flow - (CFO + CFI + CFF)| <= 10 Cr tolerance."""
    violations = []
    for _, row in cf.iterrows():
        cfo, cfi, cff, net = (
            row.get("operating_activity"),
            row.get("investing_activity"),
            row.get("financing_activity"),
            row.get("net_cash_flow"),
        )
        if any(pd.isna(v) for v in (cfo, cfi, cff, net)):
            continue
        computed = cfo + cfi + cff
        diff = abs(net - computed)
        if diff > tolerance:
            violations.append(
                Violation(
                    "DQ-09",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "net_cash_flow",
                    f"net_cash_flow={net} vs CFO+CFI+CFF={computed} "
                    f"(diff={diff:.1f} Cr > {tolerance} Cr tolerance).",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-10 — Non-Negative Fixed Assets (WARNING)
# ---------------------------------------------------------------------------
def check_dq10_non_negative_fixed_assets(bs: pd.DataFrame) -> list[Violation]:
    violations = []
    for _, row in bs.iterrows():
        fa = row.get("fixed_assets")
        if pd.isna(fa):
            continue
        if fa < 0:
            violations.append(
                Violation(
                    "DQ-10",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "fixed_assets",
                    f"fixed_assets={fa} is negative — coerce to 0 and log.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-11 — Tax Rate Range (WARNING)
# ---------------------------------------------------------------------------
def check_dq11_tax_rate_range(pl: pd.DataFrame) -> list[Violation]:
    violations = []
    for _, row in pl.iterrows():
        tax = row.get("tax_percentage")
        if pd.isna(tax):
            continue
        if not (0 <= tax <= 60):
            violations.append(
                Violation(
                    "DQ-11",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "tax_percentage",
                    f"tax_percentage={tax} outside [0, 60] range — possible "
                    "one-off deferred tax reversal.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-12 — Dividend Payout Cap (WARNING)
# ---------------------------------------------------------------------------
def check_dq12_dividend_payout_cap(pl: pd.DataFrame) -> list[Violation]:
    violations = []
    for _, row in pl.iterrows():
        payout = row.get("dividend_payout")
        if pd.isna(payout):
            continue
        if payout > 200:
            violations.append(
                Violation(
                    "DQ-12",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "dividend_payout",
                    f"dividend_payout={payout}% > 200% — likely data entry "
                    "error, analyst confirm.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-13 — URL Validity (WARNING) — network check, off by default
# ---------------------------------------------------------------------------
def _check_one_url(company_id, year, url, timeout) -> Optional[Violation]:
    import requests

    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return Violation(
                "DQ-13",
                WARNING,
                company_id,
                year,
                "Annual_Report",
                f"URL returned HTTP {resp.status_code} (expected link decay "
                "over time — do not reject row).",
            )
    except Exception as exc:  # noqa: BLE001
        return Violation(
            "DQ-13",
            WARNING,
            company_id,
            year,
            "Annual_Report",
            f"URL request failed: {exc} (expected link decay over time).",
        )
    return None


def check_dq13_url_validity(
    documents: pd.DataFrame,
    timeout: int = 5,
    max_workers: int = 10,
    sample_size: Optional[int] = None,
) -> list[Violation]:
    """
    requests.head(Annual_Report).status_code == 200 for every row.
    This is the one rule that needs network access — set sample_size to
    spot-check a subset instead of all ~1,585 rows during development.
    """
    df = documents.dropna(subset=["Annual_Report"])
    if sample_size is not None and sample_size < len(df):
        df = df.sample(n=sample_size, random_state=42)

    violations: list[Violation] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _check_one_url,
                row.get("company_id"),
                row.get("Year"),
                row.get("Annual_Report"),
                timeout,
            ): row
            for _, row in df.iterrows()
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                violations.append(result)
    return violations


# ---------------------------------------------------------------------------
# DQ-14 — EPS Sign Consistency (WARNING)
# ---------------------------------------------------------------------------
def check_dq14_eps_sign_consistency(pl: pd.DataFrame) -> list[Violation]:
    """eps > 0 if net_profit > 0."""
    violations = []
    for _, row in pl.iterrows():
        net_profit, eps = row.get("net_profit"), row.get("eps")
        if pd.isna(net_profit) or pd.isna(eps):
            continue
        if net_profit > 0 and not (eps > 0):
            violations.append(
                Violation(
                    "DQ-14",
                    WARNING,
                    row.get("company_id"),
                    row.get("year"),
                    "eps",
                    f"net_profit={net_profit} > 0 but eps={eps} — sign "
                    "mismatch, may indicate share-count adjustment.",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# DQ-15 — BSE/ASE Balance, strict (INFO — counter only, not a violation list)
# ---------------------------------------------------------------------------
def check_dq15_exact_balance_count(bs: pd.DataFrame) -> dict:
    """
    Informational counter: how many rows balance to total_liabilities ==
    total_assets *exactly* (stricter than the DQ-04 ±1% tolerance). Per the
    spec this is reported in load_audit only, not validation_failures.csv.
    """
    valid = bs.dropna(subset=["total_assets", "total_liabilities"])
    exact_matches = (valid["total_assets"] == valid["total_liabilities"]).sum()
    return {
        "rule_id": "DQ-15",
        "severity": INFO,
        "exact_balance_count": int(exact_matches),
        "total_rows_checked": int(len(valid)),
    }


# ---------------------------------------------------------------------------
# DQ-16 — Coverage Check (WARNING)
# ---------------------------------------------------------------------------
def check_dq16_coverage_check(
    tables: dict[str, pd.DataFrame], min_years: int = 5
) -> list[Violation]:
    """Each company needs >= 5 years of P&L, BS, CF records."""
    violations = []
    for table_name in TIME_SERIES_TABLES:
        df = tables.get(table_name)
        if df is None or "company_id" not in df.columns:
            continue
        year_counts = df.groupby("company_id")["year"].nunique()
        for company_id, count in year_counts.items():
            if count < min_years:
                violations.append(
                    Violation(
                        "DQ-16",
                        WARNING,
                        company_id,
                        None,
                        table_name,
                        f"Only {count} year(s) of {table_name} history "
                        f"(< {min_years}yr threshold) — exclude from CAGR "
                        "if < 3yr.",
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# Normalisation helper — used by the orchestrator below
# ---------------------------------------------------------------------------
def _normalize_table(
    df: pd.DataFrame,
    id_col: str = "company_id",
    year_col: Optional[str] = "year",
) -> pd.DataFrame:
    """
    Return a copy of df with id_col (and year_col, if given) replaced by
    their Day 2 normalised values. Rows that fail normalisation are
    dropped here — they were already reported by DQ-07/DQ-08, which run
    on the *raw* frame before this helper is called, so the row rejection
    is still visible in validation_failures.csv. Without this step, every
    other rule (PK/FK checks especially) would be comparing raw strings
    and would mistake casing/whitespace variants (e.g. 'tcs' vs 'TCS') for
    real duplicates or missing companies.
    """
    out = df.copy()
    if id_col in out.columns:
        out[id_col] = out[id_col].apply(normaliser.normalize_ticker)
        out = out[out[id_col].notna()]
    if year_col is not None and year_col in out.columns:
        out[year_col] = out[year_col].apply(normaliser.normalize_year)
        out = out[out[year_col] != normaliser.PARSE_ERROR]
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_all_dq_rules(
    frames: dict[str, pd.DataFrame],
    sectors: Optional[pd.DataFrame] = None,
    check_urls: bool = False,
    url_sample_size: Optional[int] = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Run all 16 DQ rules against the loaded frames dict (keyed the same way
    as src.etl.loader's load_all_core_files() output: 'companies',
    'profitandloss', 'balancesheet', 'cashflow', 'analysis', 'documents',
    'prosandcons').

    Returns (violations_df, info_summary). info_summary currently holds the
    DQ-15 counter; violations_df holds every CRITICAL/WARNING row and is
    what gets written to validation_failures.csv.

    Order of operations matters here: DQ-07 (year format) and DQ-08
    (ticker format) run first, against the *raw* data, since their whole
    job is to catch values that fail normalisation. Every other rule then
    runs against normalised copies (see _normalize_table) — otherwise a
    harmless 'tcs' vs 'TCS' casing difference would falsely look like a
    missing company (DQ-03) or a duplicate row (DQ-02).
    """
    violations: list[Violation] = []
    info_summary: dict = {}

    companies = frames.get("companies")
    pl = frames.get("profitandloss")
    bs = frames.get("balancesheet")
    cf = frames.get("cashflow")
    documents = frames.get("documents")
    prosandcons = frames.get("prosandcons")
    analysis = frames.get("analysis")

    # --- Step 1: format checks on RAW data (DQ-07, DQ-08) ---
    for name, df in (("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)):
        if df is None:
            continue
        violations += check_dq07_year_format(df, name)
        violations += check_dq08_ticker_format(df, name)

    if companies is not None:
        violations += check_dq08_ticker_format(companies, "companies", id_col="id")

    # --- Step 2: build normalised copies for every remaining check ---
    companies_norm = None
    if companies is not None:
        companies_norm = companies.copy()
        companies_norm["id"] = companies_norm["id"].apply(normaliser.normalize_ticker)
        companies_norm = companies_norm[companies_norm["id"].notna()].reset_index(
            drop=True
        )

    pl_norm = _normalize_table(pl) if pl is not None else None
    bs_norm = _normalize_table(bs) if bs is not None else None
    cf_norm = _normalize_table(cf) if cf is not None else None
    documents_norm = (
        _normalize_table(documents, year_col=None) if documents is not None else None
    )
    prosandcons_norm = (
        _normalize_table(prosandcons, year_col=None)
        if prosandcons is not None
        else None
    )
    analysis_norm = (
        _normalize_table(analysis, year_col=None) if analysis is not None else None
    )
    sectors_norm = None
    if sectors is not None:
        sectors_norm = sectors.copy()
        sectors_norm["company_id"] = sectors_norm["company_id"].apply(
            normaliser.normalize_ticker
        )

    # --- Step 3: PK / FK / business-rule checks on normalised data ---
    if companies_norm is not None:
        violations += check_dq01_company_pk_uniqueness(companies_norm)

    for name, df in (
        ("profitandloss", pl_norm),
        ("balancesheet", bs_norm),
        ("cashflow", cf_norm),
    ):
        if df is None:
            continue
        violations += check_dq02_annual_pk_uniqueness(df, name)
        if companies_norm is not None:
            violations += check_dq03_fk_integrity(df, companies_norm, name)

    for name, df in (
        ("documents", documents_norm),
        ("prosandcons", prosandcons_norm),
        ("analysis", analysis_norm),
    ):
        if df is None or companies_norm is None:
            continue
        violations += check_dq03_fk_integrity(df, companies_norm, name)

    if bs_norm is not None:
        violations += check_dq04_balance_sheet_balance(bs_norm)
        violations += check_dq10_non_negative_fixed_assets(bs_norm)
        info_summary["dq15"] = check_dq15_exact_balance_count(bs_norm)

    if pl_norm is not None:
        violations += check_dq05_opm_cross_check(pl_norm)
        violations += check_dq06_positive_sales(pl_norm, sectors=sectors_norm)
        violations += check_dq11_tax_rate_range(pl_norm)
        violations += check_dq12_dividend_payout_cap(pl_norm)
        violations += check_dq14_eps_sign_consistency(pl_norm)

    if cf_norm is not None:
        violations += check_dq09_net_cash_check(cf_norm)

    if documents_norm is not None and check_urls:
        violations += check_dq13_url_validity(
            documents_norm, sample_size=url_sample_size
        )

    if pl_norm is not None and bs_norm is not None and cf_norm is not None:
        violations += check_dq16_coverage_check(
            {"profitandloss": pl_norm, "balancesheet": bs_norm, "cashflow": cf_norm}
        )

    return _violations_to_df(violations), info_summary


def write_validation_failures(
    violations_df: pd.DataFrame, path: Optional[Path] = None
) -> Path:
    path = path or DQ_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    violations_df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    import sys

    from src.etl.loader import load_all_core_files, load_all_supplementary_files

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    check_urls_flag = "--check-urls" in sys.argv

    core = load_all_core_files()
    supporting = load_all_supplementary_files()
    sectors_df = supporting.get("sectors")

    violations_df, info = run_all_dq_rules(
        core, sectors=sectors_df, check_urls=check_urls_flag
    )
    out_path = write_validation_failures(violations_df)

    print(
        f"\nValidation complete. {len(violations_df)} violations logged to {out_path}\n"
    )
    if not violations_df.empty:
        summary = (
            violations_df.groupby(["rule_id", "severity"])
            .size()
            .reset_index(name="count")
            .sort_values(["severity", "rule_id"])
        )
        print(summary.to_string(index=False))

    if "dq15" in info:
        d = info["dq15"]
        print(
            f"\n[INFO] DQ-15 exact balance count: {d['exact_balance_count']} / "
            f"{d['total_rows_checked']} rows balance exactly."
        )

    critical_count = (
        (violations_df["severity"] == CRITICAL).sum() if not violations_df.empty else 0
    )
    if critical_count:
        print(
            f"\n*** {critical_count} CRITICAL violation(s) found — load should "
            "be halted and investigated before proceeding to Day 4 (SQLite "
            "schema build). ***"
        )
    else:
        print("\nNo CRITICAL violations. Safe to proceed to Day 4.")
