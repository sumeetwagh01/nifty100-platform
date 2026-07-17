"""
day06_review.py  — Sprint 1 Day 06: Data Quality Manual Review

Runs all 10 exploratory queries from notebooks/exploratory_queries.sql
against data/nifty100.db and prints formatted results.

Usage:
    python day06_review.py
    python day06_review.py > day06_review_output.txt   (save to file)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "nifty100.db"


def run(conn: sqlite3.Connection, sql: str) -> list[tuple]:
    cur = conn.execute(sql)
    return cur.fetchall(), [d[0] for d in cur.description]


def print_table(title: str, rows: list[tuple], headers: list[str]) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    if not rows:
        print("  (no rows)")
        return
    col_widths = [
        max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    header_line = "  " + "  ".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  " + "-" * (sum(col_widths) + 2 * len(col_widths)))
    for row in rows:
        print("  " + "  ".join(str(v).ljust(w) for v, w in zip(row, col_widths)))
    print(f"\n  {len(rows)} row(s)")


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run: python src/etl/full_load.py --reset")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------
    # Q01 — Row counts
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT 'companies'     AS tbl, COUNT(*) AS rows FROM companies
        UNION ALL SELECT 'profitandloss',  COUNT(*) FROM profitandloss
        UNION ALL SELECT 'balancesheet',   COUNT(*) FROM balancesheet
        UNION ALL SELECT 'cashflow',       COUNT(*) FROM cashflow
        UNION ALL SELECT 'analysis',       COUNT(*) FROM analysis
        UNION ALL SELECT 'documents',      COUNT(*) FROM documents
        UNION ALL SELECT 'prosandcons',    COUNT(*) FROM prosandcons
        UNION ALL SELECT 'sectors',        COUNT(*) FROM sectors
        UNION ALL SELECT 'stock_prices',   COUNT(*) FROM stock_prices
        UNION ALL SELECT 'market_cap',     COUNT(*) FROM market_cap
    """)
    print_table("Q01 — Row counts across all 10 tables", rows, hdrs)
    company_count = next((r[1] for r in rows if r[0] == "companies"), 0)
    if company_count == 92:
        print("  ✓ companies = 92  (Sprint 1 exit gate PASSED)")
    else:
        print(f"  ✗ companies = {company_count}  (expected 92 — INVESTIGATE)")

    # ------------------------------------------------------------------
    # Q02 — Year coverage per company
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT p.company_id,
               COUNT(DISTINCT p.year)  AS year_count,
               MIN(p.year)             AS earliest_year,
               MAX(p.year)             AS latest_year
        FROM profitandloss p
        GROUP BY p.company_id
        ORDER BY year_count ASC, p.company_id
        LIMIT 20
    """)
    print_table("Q02 — Year coverage per company in P&L (bottom 20)", rows, hdrs)

    # ------------------------------------------------------------------
    # Q03 — Companies with < 5 years history
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT p.company_id,
               COUNT(DISTINCT p.year) AS year_count
        FROM profitandloss p
        GROUP BY p.company_id
        HAVING COUNT(DISTINCT p.year) < 5
        ORDER BY year_count ASC
    """)
    print_table("Q03 — Companies with < 5 years P&L history (DQ-16)", rows, hdrs)
    if not rows:
        print("  ✓ All companies have >= 5 years of P&L history")

    # ------------------------------------------------------------------
    # Q04 — NULL counts for key columns
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT 'sales'              AS col,
               SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END) AS nulls
        FROM profitandloss
        UNION ALL
        SELECT 'net_profit',
               SUM(CASE WHEN net_profit IS NULL THEN 1 ELSE 0 END)
        FROM profitandloss
        UNION ALL
        SELECT 'operating_profit',
               SUM(CASE WHEN operating_profit IS NULL THEN 1 ELSE 0 END)
        FROM profitandloss
        UNION ALL
        SELECT 'eps',
               SUM(CASE WHEN eps IS NULL THEN 1 ELSE 0 END)
        FROM profitandloss
        UNION ALL
        SELECT 'borrowings (BS)',
               SUM(CASE WHEN borrowings IS NULL THEN 1 ELSE 0 END)
        FROM balancesheet
        UNION ALL
        SELECT 'total_assets (BS)',
               SUM(CASE WHEN total_assets IS NULL THEN 1 ELSE 0 END)
        FROM balancesheet
        UNION ALL
        SELECT 'operating_activity (CF)',
               SUM(CASE WHEN operating_activity IS NULL THEN 1 ELSE 0 END)
        FROM cashflow
    """)
    print_table("Q04 — NULL counts for key financial columns", rows, hdrs)

    # ------------------------------------------------------------------
    # Q05 — 5 random companies spot-check
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT p.company_id, p.year,
               p.sales, p.net_profit,
               ROUND(p.opm_percentage, 1) AS opm_pct,
               p.eps
        FROM profitandloss p
        WHERE p.year = (
            SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id
        )
        ORDER BY RANDOM()
        LIMIT 5
    """)
    print_table("Q05 — 5 random companies, latest year P&L (spot-check manually)", rows, hdrs)

    # ------------------------------------------------------------------
    # Q06 — Balance sheet gaps > 1%
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT company_id, year,
               total_assets, total_liabilities,
               ROUND(ABS(total_assets - total_liabilities)
                     / total_assets * 100, 2) AS diff_pct
        FROM balancesheet
        WHERE total_assets > 0
          AND ABS(total_assets - total_liabilities) / total_assets >= 0.01
        ORDER BY diff_pct DESC
        LIMIT 10
    """)
    print_table("Q06 — Balance sheet imbalance > 1% (DQ-04)", rows, hdrs)
    if not rows:
        print("  ✓ All balance sheets balance within 1%")

    # ------------------------------------------------------------------
    # Q07 — Cash flow net check
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT company_id, year,
               ROUND(ABS(net_cash_flow -
                   (operating_activity + investing_activity + financing_activity)
               ), 1) AS gap_cr
        FROM cashflow
        WHERE operating_activity IS NOT NULL
          AND investing_activity  IS NOT NULL
          AND financing_activity  IS NOT NULL
          AND net_cash_flow       IS NOT NULL
          AND ABS(net_cash_flow -
                (operating_activity + investing_activity + financing_activity)) > 10
        ORDER BY gap_cr DESC
        LIMIT 10
    """)
    print_table("Q07 — Cash flow net mismatch > 10 Cr (DQ-09)", rows, hdrs)
    if not rows:
        print("  ✓ All cash flow statements reconcile within 10 Cr")

    # ------------------------------------------------------------------
    # Q08 — Sector distribution
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT broad_sector, COUNT(*) AS company_count
        FROM sectors
        GROUP BY broad_sector
        ORDER BY company_count DESC
    """)
    print_table("Q08 — Companies per broad sector (should total 92)", rows, hdrs)
    total = sum(r[1] for r in rows)
    print(f"  Total: {total} companies across {len(rows)} sectors")

    # ------------------------------------------------------------------
    # Q09 — Documents coverage
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT c.id AS company_id,
               COUNT(d.year)  AS reports_available,
               15 - COUNT(d.year) AS missing_years
        FROM companies c
        LEFT JOIN documents d ON c.id = d.company_id
        GROUP BY c.id
        ORDER BY missing_years DESC
        LIMIT 15
    """)
    print_table("Q09 — Annual report coverage (top 15 missing)", rows, hdrs)

    # ------------------------------------------------------------------
    # Q10 — Top 10 by sales (sanity check)
    # ------------------------------------------------------------------
    rows, hdrs = run(conn, """
        SELECT p.company_id,
               p.year          AS latest_year,
               p.sales         AS sales_cr,
               p.net_profit    AS net_profit_cr,
               ROUND(p.opm_percentage, 1) AS opm_pct
        FROM profitandloss p
        WHERE p.year = (
            SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id
        )
        ORDER BY p.sales DESC
        LIMIT 10
    """)
    print_table("Q10 — Top 10 companies by latest-year sales (sanity check)", rows, hdrs)

    # ------------------------------------------------------------------
    # FK check
    # ------------------------------------------------------------------
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"\n{'='*70}")
    print(f"  PRAGMA foreign_key_check: {len(fk_rows)} violation(s)", end="  ")
    print("✓ CLEAN" if not fk_rows else "*** INVESTIGATE ***")
    print(f"{'='*70}")

    conn.close()
    print("\nDay 06 review complete.")
    print(f"Run: python day06_review.py > day06_review_output.txt  to save results.")


if __name__ == "__main__":
    main()
