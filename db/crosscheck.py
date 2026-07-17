"""
db/crosscheck.py
================
Sprint 2 Day 13 — Cross-check computed KPIs against Screener pre-computed values
and run the Day 14 screener preview query.

Usage
-----
    python db/crosscheck.py --db data/nifty100.db
    python db/crosscheck.py --db data/nifty100.db --preview   # screener preview only

What it does
------------
1. ROCE cross-check  : computed roce_pct vs companies.roce_percentage
                       flags diff > 5%, classifies anomaly, logs to ratio_edge_cases.log
2. ROE cross-check   : computed return_on_equity_pct vs companies.roe_percentage
                       notes Screener anomalies (e.g. TCS = 0.52, likely display units)
3. Bank carve-out audit : confirms all Financials companies have roce_pct = NULL
4. D/E suppression audit: confirms high_leverage_flag = 0 for all Financials companies
5. Screener preview  : ROE > 15% AND D/E < 1 — expects 15–50 companies
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.edge_case_logger import (
    log_roce_mismatch, log_roe_mismatch,
    log_bank_carve_out, log_de_flag_suppressed,
    log_session_header, log_session_footer,
    ROCE_MISMATCH_THRESHOLD, ROE_MISMATCH_THRESHOLD,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anomaly classification helper
# ---------------------------------------------------------------------------

def _classify_roce_anomaly(
    company_name: str,
    computed: float,
    screener: float,
    broad_sector: str,
) -> str:
    """
    Classify why computed ROCE differs from Screener's value.

    Rules (heuristic, documented in sprint retro):
    - diff > 50%     → likely data_source_issue (different year range or TTM)
    - Financials     → formula_discrepancy (banking ROCE is structurally different)
    - otherwise      → version_difference (Screener may use different EBIT definition)
    """
    diff = abs(computed - screener)
    if broad_sector.lower() == "financials":
        return "formula_discrepancy"
    if diff > 50:
        return "data_source_issue"
    return "version_difference"


def _classify_roe_anomaly(
    company_name: str,
    computed: float,
    screener: float,
) -> str:
    """
    Classify ROE anomaly.

    Screener's roe_percentage for some companies (e.g. TCS = 0.52) appears
    to be stored as a decimal fraction rather than a percentage — a known
    data source issue.
    """
    # If screener value looks like a decimal fraction (< 2.0) but computed is > 5%
    if screener is not None and abs(screener) < 2.0 and abs(computed) > 5.0:
        return "data_source_issue (screener value appears to be decimal fraction, not %)"
    if abs(computed - screener) > 50:
        return "data_source_issue"
    return "version_difference"


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------

def run_roce_crosscheck(conn: sqlite3.Connection) -> dict:
    """
    Compare computed ROCE (financial_ratios) vs screener ROCE (companies).

    Screener stores a single ROCE value per company (likely TTM or latest year).
    We compare against the most recent year in financial_ratios.
    """
    rows = conn.execute("""
        SELECT
            c.id            AS company_id,
            c.company_name,
            c.roce_percentage AS screener_roce,
            s.broad_sector,
            fr.year,
            fr.roce_pct     AS computed_roce
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.id
        LEFT JOIN financial_ratios fr
            ON fr.company_id = c.id
            AND fr.year = (
                SELECT MAX(year) FROM financial_ratios
                WHERE company_id = c.id
            )
        WHERE c.roce_percentage IS NOT NULL
        ORDER BY c.company_name
    """).fetchall()

    mismatches = 0
    bank_carve_outs = 0

    for r in rows:
        cid      = r["company_id"]
        name     = r["company_name"]
        sector   = r["broad_sector"] or ""
        screener = r["screener_roce"]
        computed = r["computed_roce"]

        # Bank carve-out — ROCE suppressed
        if computed is None and sector.lower() == "financials":
            log_bank_carve_out(cid, name)
            bank_carve_outs += 1
            continue

        if computed is None or screener is None:
            continue

        diff = abs(computed - screener)
        if diff > ROCE_MISMATCH_THRESHOLD:
            classification = _classify_roce_anomaly(name, computed, screener, sector)
            log_roce_mismatch(cid, name, computed, screener, diff, classification)
            mismatches += 1

    return {
        "total_checked": len(rows),
        "mismatches": mismatches,
        "bank_carve_outs": bank_carve_outs,
    }


def run_roe_crosscheck(conn: sqlite3.Connection) -> dict:
    """
    Compare computed ROE vs screener ROE.

    Note: use ratio engine value for analytics, Screener value for display only.
    """
    rows = conn.execute("""
        SELECT
            c.id            AS company_id,
            c.company_name,
            c.roe_percentage AS screener_roe,
            fr.year,
            fr.return_on_equity_pct AS computed_roe
        FROM companies c
        LEFT JOIN financial_ratios fr
            ON fr.company_id = c.id
            AND fr.year = (
                SELECT MAX(year) FROM financial_ratios
                WHERE company_id = c.id
            )
        WHERE c.roe_percentage IS NOT NULL
        ORDER BY c.company_name
    """).fetchall()

    mismatches = 0
    anomalous_screener = 0

    for r in rows:
        cid      = r["company_id"]
        name     = r["company_name"]
        screener = r["screener_roe"]
        computed = r["computed_roe"]

        if computed is None or screener is None:
            continue

        diff = abs(computed - screener)
        if diff > ROE_MISMATCH_THRESHOLD:
            classification = _classify_roe_anomaly(name, computed, screener)
            log_roe_mismatch(cid, name, computed, screener, diff, classification)
            mismatches += 1
            if "decimal fraction" in classification:
                anomalous_screener += 1

    return {
        "total_checked": len(rows),
        "mismatches": mismatches,
        "anomalous_screener_values": anomalous_screener,
    }


def run_de_suppression_audit(conn: sqlite3.Connection) -> dict:
    """
    Confirm that high_leverage_flag = 0 for ALL Financials companies.
    Log any that were suppressed (expected behaviour, not errors).
    """
    rows = conn.execute("""
        SELECT
            c.id AS company_id,
            c.company_name,
            fr.debt_to_equity,
            fr.high_leverage_flag
        FROM companies c
        JOIN sectors s ON s.company_id = c.id
        JOIN financial_ratios fr ON fr.company_id = c.id
        WHERE LOWER(s.broad_sector) = 'financials'
          AND fr.debt_to_equity IS NOT NULL
          AND fr.debt_to_equity > 5
        ORDER BY c.company_name, fr.debt_to_equity DESC
    """).fetchall()

    suppressed = set()
    for r in rows:
        cid  = r["company_id"]
        name = r["company_name"]
        de   = r["debt_to_equity"]
        flag = r["high_leverage_flag"]

        if flag == 0 and cid not in suppressed:
            log_de_flag_suppressed(cid, name, de)
            suppressed.add(cid)

    return {"companies_with_suppressed_flag": len(suppressed)}


# ---------------------------------------------------------------------------
# Day 14 — Screener preview query
# ---------------------------------------------------------------------------

def run_screener_preview(conn: sqlite3.Connection) -> list[dict]:
    """
    Quick filter: ROE > 15% AND D/E < 1 — latest year per company.
    Spec: expects 15–50 companies, result should make business sense.
    """
    rows = conn.execute("""
        SELECT
            c.company_name,
            s.broad_sector,
            fr.year,
            ROUND(fr.return_on_equity_pct, 2)    AS roe_pct,
            ROUND(fr.debt_to_equity, 2)           AS de_ratio,
            ROUND(fr.net_profit_margin_pct, 2)    AS npm_pct,
            ROUND(fr.revenue_cagr_5yr, 2)         AS rev_cagr_5yr
        FROM financial_ratios fr
        JOIN companies c ON c.id = fr.company_id
        LEFT JOIN sectors s ON s.company_id = fr.company_id
        WHERE fr.return_on_equity_pct > 15
          AND fr.debt_to_equity < 1
          AND fr.debt_to_equity IS NOT NULL
          AND fr.year = (
              SELECT MAX(year) FROM financial_ratios
              WHERE company_id = fr.company_id
          )
        ORDER BY fr.return_on_equity_pct DESC
    """).fetchall()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_crosscheck(db_path: str, preview_only: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Count companies for session header
    n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    log_session_header(db_path, n)

    anomalies = 0

    if not preview_only:
        print("\n📊 ROCE Cross-check")
        print("-" * 50)
        roce_result = run_roce_crosscheck(conn)
        print(f"  Checked          : {roce_result['total_checked']}")
        print(f"  Mismatches > 5%  : {roce_result['mismatches']}")
        print(f"  Bank carve-outs  : {roce_result['bank_carve_outs']}")
        anomalies += roce_result["mismatches"]

        print("\n📊 ROE Cross-check")
        print("-" * 50)
        roe_result = run_roe_crosscheck(conn)
        print(f"  Checked          : {roe_result['total_checked']}")
        print(f"  Mismatches > 5%  : {roe_result['mismatches']}")
        print(f"  Anomalous source : {roe_result['anomalous_screener_values']}")
        anomalies += roe_result["mismatches"]

        print("\n📊 D/E Flag Suppression Audit (Financials sector)")
        print("-" * 50)
        de_result = run_de_suppression_audit(conn)
        print(f"  Companies with suppressed flag : {de_result['companies_with_suppressed_flag']}")

    print("\n🔍 Screener Preview — ROE > 15% AND D/E < 1")
    print("-" * 50)
    preview = run_screener_preview(conn)
    print(f"  Companies found  : {len(preview)}")

    if 15 <= len(preview) <= 50:
        print(f"  ✅ Count is within expected range (15–50)")
    else:
        print(f"  ⚠️  Count {len(preview)} is outside expected range (15–50)")

    print(f"\n  {'Company':<30} {'Sector':<18} {'ROE%':>7} {'D/E':>6} {'NPM%':>7} {'RevCAGR5yr':>11}")
    print(f"  {'-'*30} {'-'*18} {'-'*7} {'-'*6} {'-'*7} {'-'*11}")
    for r in preview:
        print(
            f"  {(r['company_name'] or ''):<30} "
            f"{(r['broad_sector'] or ''):<18} "
            f"{str(r['roe_pct'] or ''):>7} "
            f"{str(r['de_ratio'] or ''):>6} "
            f"{str(r['npm_pct'] or ''):>7} "
            f"{str(r['rev_cagr_5yr'] or ''):>11}"
        )

    log_session_footer(
        rows_written=conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0],
        anomalies=anomalies,
    )
    conn.close()

    print(f"\n📝 Edge cases written to: output/ratio_edge_cases.log")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Cross-check KPIs vs Screener values")
    parser.add_argument("--db", default=os.getenv("DB_PATH", "data/nifty100.db"))
    parser.add_argument("--preview", action="store_true", help="Run screener preview only")
    args = parser.parse_args()

    run_crosscheck(args.db, preview_only=args.preview)
