"""
db/ratio_loader.py
==================
Sprint 2 Day 12 — Populate the financial_ratios SQLite table.

Workflow
--------
1. Read schema_ratios.sql and CREATE the financial_ratios table
2. For each company, fetch all years from profitandloss + balancesheet + cashflow
3. Compute all KPIs using src/analytics/ratios.py, cagr.py, cashflow_kpis.py
4. INSERT OR REPLACE into financial_ratios
5. Return summary: rows written, companies processed, errors logged

Usage (CLI)
-----------
    python db/ratio_loader.py                     # uses DB_PATH from .env
    python db/ratio_loader.py --db path/to/db     # override DB path
    python db/ratio_loader.py --reset             # drop & recreate table first
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.ratios import (
    npm, opm, roe, roce, roa,
    de_ratio, icr, icr_label, icr_warning_flag, high_leverage_flag,
    net_debt, asset_turnover,
)
from src.analytics.cagr import (
    revenue_cagr_with_flag, pat_cagr_with_flag, eps_cagr_with_flag,
    all_windows_with_flags,
)
from src.analytics.cashflow_kpis import (
    fcf, cfo_quality_score, capex_intensity, fcf_conversion,
    capital_allocation_pattern,
)

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema_ratios.sql"

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection, reset: bool = False) -> None:
    """Create financial_ratios table from schema_ratios.sql."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    if reset:
        conn.execute("DROP TABLE IF EXISTS financial_ratios")
        conn.commit()
    conn.executescript(sql)
    conn.commit()
    log.info("financial_ratios table ready")


# ---------------------------------------------------------------------------
# Data fetchers — one row per company-year
# ---------------------------------------------------------------------------

def fetch_companies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.id, c.company_name,
                  COALESCE(s.broad_sector, '') AS broad_sector
           FROM companies c
           LEFT JOIN sectors s ON s.company_id = c.id
           ORDER BY c.id"""
    ).fetchall()


def fetch_pl(conn: sqlite3.Connection, company_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT year, sales, net_profit, operating_profit, depreciation,
                  other_income, interest,
                  eps          AS eps_in_rs,
                  opm_percentage,
                  dividend_payout AS dividend_payout_pct
           FROM profitandloss
           WHERE company_id = ?
           ORDER BY year""",
        (company_id,),
    ).fetchall()


def fetch_bs(conn: sqlite3.Connection, company_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT year, equity_capital, reserves, borrowings,
                  total_assets, investments,
                  NULL AS book_value
           FROM balancesheet
           WHERE company_id = ?
           ORDER BY year""",
        (company_id,),
    ).fetchall()


def fetch_cf(conn: sqlite3.Connection, company_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT year, operating_activity, investing_activity,
                  financing_activity
           FROM cashflow
           WHERE company_id = ?
           ORDER BY year""",
        (company_id,),
    ).fetchall()


def fetch_company_book_value(conn: sqlite3.Connection, company_id: int) -> float | None:
    """book_value lives in companies table, not balancesheet."""
    row = conn.execute(
        "SELECT book_value FROM companies WHERE id = ?", (company_id,)
    ).fetchone()
    return row["book_value"] if row else None


# ---------------------------------------------------------------------------
# Composite quality score
# ---------------------------------------------------------------------------

def _composite_quality(
    npm_val: float | None,
    roe_val: float | None,
    icr_val: float | None,
    cfo_quality: str | None,
    revenue_cagr: float | None,
) -> float | None:
    """
    Simple composite score (0–100) combining 5 signals.
    Each component contributes up to 20 points.

    NPM       > 10%           → 20 pts  (> 5% → 10 pts)
    ROE       > 15%           → 20 pts  (> 10% → 10 pts)
    ICR       > 3             → 20 pts  (> 1.5 → 10 pts)
    CFO Qual  High Quality    → 20 pts  (Moderate → 10 pts)
    Rev CAGR  > 15%           → 20 pts  (> 8% → 10 pts)
    """
    score = 0.0
    components = 0

    if npm_val is not None:
        components += 1
        if npm_val > 10:
            score += 20
        elif npm_val > 5:
            score += 10

    if roe_val is not None:
        components += 1
        if roe_val > 15:
            score += 20
        elif roe_val > 10:
            score += 10

    if icr_val is not None:
        components += 1
        if icr_val > 3:
            score += 20
        elif icr_val > 1.5:
            score += 10

    if cfo_quality is not None:
        components += 1
        if cfo_quality == "High Quality":
            score += 20
        elif cfo_quality == "Moderate":
            score += 10

    if revenue_cagr is not None:
        components += 1
        if revenue_cagr > 15:
            score += 20
        elif revenue_cagr > 8:
            score += 10

    if components == 0:
        return None

    # Scale to available components
    return round((score / (components * 20)) * 100, 2)


# ---------------------------------------------------------------------------
# Per-company-year KPI computation
# ---------------------------------------------------------------------------

def compute_ratios_for_company(
    company_id: int,
    broad_sector: str | None,
    pl_rows: list[sqlite3.Row],
    bs_rows: list[sqlite3.Row],
    cf_rows: list[sqlite3.Row],
    company_book_value: float | None = None,
) -> list[dict]:
    """
    Compute all KPIs for one company across all available years.

    Returns a list of dicts — one per company-year — ready for DB insert.
    """
    is_financial = (broad_sector or "").strip().lower() == "financials"

    # Index by year for O(1) lookup — convert Row to dict for .get() support
    pl_by_year = {r["year"]: dict(r) for r in pl_rows}
    bs_by_year = {r["year"]: dict(r) for r in bs_rows}
    cf_by_year = {r["year"]: dict(r) for r in cf_rows}

    # Build time series for CAGR (sorted ascending)
    all_years = sorted(set(pl_by_year) | set(bs_by_year))
    sales_series = [pl_by_year.get(y, {}).get("sales") for y in all_years]
    pat_series = [pl_by_year.get(y, {}).get("net_profit") for y in all_years]
    eps_series = [pl_by_year.get(y, {}).get("eps_in_rs") for y in all_years]

    # CFO/PAT series for quality score
    cfo_series = [cf_by_year.get(y, {}).get("operating_activity") for y in all_years]

    results = []

    for idx, year in enumerate(all_years):
        pl = pl_by_year.get(year, {})
        bs = bs_by_year.get(year, {})
        cf = cf_by_year.get(year, {})

        # Safe field extraction
        def g(row, key):
            try:
                return row[key]
            except (IndexError, KeyError, TypeError):
                return None

        sales           = g(pl, "sales")
        net_profit      = g(pl, "net_profit")
        op_profit       = g(pl, "operating_profit")
        depreciation    = g(pl, "depreciation")
        other_income    = g(pl, "other_income")
        interest        = g(pl, "interest")
        eps             = g(pl, "eps_in_rs")
        div_payout      = g(pl, "dividend_payout_pct")

        equity_capital  = g(bs, "equity_capital")
        reserves        = g(bs, "reserves")
        borrowings      = g(bs, "borrowings")
        total_assets    = g(bs, "total_assets")
        investments     = g(bs, "investments")
        book_value      = company_book_value   # from companies table, same for all years

        cfo             = g(cf, "operating_activity")
        cfi             = g(cf, "investing_activity")
        cff             = g(cf, "financing_activity")

        # --- Profitability ---
        npm_val   = npm(net_profit, sales)
        opm_val   = opm(op_profit, sales)
        roe_val   = roe(net_profit, equity_capital, reserves)
        roce_val  = roce(op_profit, depreciation, equity_capital, reserves, borrowings, is_financial)
        roa_val   = roa(net_profit, total_assets)

        # --- Leverage ---
        de_val    = de_ratio(borrowings, equity_capital, reserves)
        icr_val   = icr(op_profit, other_income, interest)
        icrl      = icr_label(interest)
        icr_warn  = icr_warning_flag(icr_val)
        hi_lev    = high_leverage_flag(de_val, is_financial)
        at_val    = asset_turnover(sales, total_assets)
        nd_val    = net_debt(borrowings, investments)

        # --- Cash Flow ---
        fcf_val            = fcf(cfo, cfi)
        cap_intensity_pct, cap_intensity_label = capex_intensity(cfi, sales)
        fcf_conv_val       = fcf_conversion(fcf_val, op_profit)
        cap_pattern        = capital_allocation_pattern(cfo, cfi, cff)

        # CFO quality uses series up to current year
        cfo_q = cfo_quality_score(
            cfo_series[:idx + 1],
            pat_series[:idx + 1],
        )

        # --- CAGR — use series up to current year ---
        s_to_now   = sales_series[:idx + 1]
        pat_to_now = pat_series[:idx + 1]
        eps_to_now = eps_series[:idx + 1]

        rev_cagr_windows = all_windows_with_flags(s_to_now, revenue_cagr_with_flag)
        pat_cagr_windows = all_windows_with_flags(pat_to_now, pat_cagr_with_flag)
        eps_cagr_windows = all_windows_with_flags(eps_to_now, eps_cagr_with_flag)

        # --- Composite ---
        comp_score = _composite_quality(
            npm_val, roe_val, icr_val, cfo_q,
            rev_cagr_windows.get("cagr_5yr"),
        )

        results.append({
            "company_id":                   company_id,
            "year":                         year,
            "net_profit_margin_pct":        npm_val,
            "operating_profit_margin_pct":  opm_val,
            "return_on_equity_pct":         roe_val,
            "return_on_assets_pct":         roa_val,
            "roce_pct":                     roce_val,
            "debt_to_equity":               de_val,
            "interest_coverage":            icr_val,
            "icr_label":                    icrl,
            "icr_warning_flag":             int(icr_warn),
            "high_leverage_flag":           int(hi_lev),
            "asset_turnover":               at_val,
            "net_debt_cr":                  nd_val,
            "free_cash_flow_cr":            fcf_val,
            "capex_cr":                     cfi,
            "capex_intensity_pct":          cap_intensity_pct,
            "capex_intensity_label":        cap_intensity_label,
            "fcf_conversion_pct":           fcf_conv_val,
            "cash_from_operations_cr":      cfo,
            "cfo_quality_score":            cfo_q,
            "capital_allocation_pattern":   cap_pattern,
            "revenue_cagr_3yr":             rev_cagr_windows["cagr_3yr"],
            "revenue_cagr_3yr_flag":        rev_cagr_windows["cagr_3yr_flag"],
            "revenue_cagr_5yr":             rev_cagr_windows["cagr_5yr"],
            "revenue_cagr_5yr_flag":        rev_cagr_windows["cagr_5yr_flag"],
            "revenue_cagr_10yr":            rev_cagr_windows["cagr_10yr"],
            "revenue_cagr_10yr_flag":       rev_cagr_windows["cagr_10yr_flag"],
            "pat_cagr_3yr":                 pat_cagr_windows["cagr_3yr"],
            "pat_cagr_3yr_flag":            pat_cagr_windows["cagr_3yr_flag"],
            "pat_cagr_5yr":                 pat_cagr_windows["cagr_5yr"],
            "pat_cagr_5yr_flag":            pat_cagr_windows["cagr_5yr_flag"],
            "pat_cagr_10yr":                pat_cagr_windows["cagr_10yr"],
            "pat_cagr_10yr_flag":           pat_cagr_windows["cagr_10yr_flag"],
            "eps_cagr_3yr":                 eps_cagr_windows["cagr_3yr"],
            "eps_cagr_3yr_flag":            eps_cagr_windows["cagr_3yr_flag"],
            "eps_cagr_5yr":                 eps_cagr_windows["cagr_5yr"],
            "eps_cagr_5yr_flag":            eps_cagr_windows["cagr_5yr_flag"],
            "eps_cagr_10yr":                eps_cagr_windows["cagr_10yr"],
            "eps_cagr_10yr_flag":           eps_cagr_windows["cagr_10yr_flag"],
            "earnings_per_share":           eps,
            "book_value_per_share":         book_value,
            "dividend_payout_ratio_pct":    div_payout,
            "total_debt_cr":                borrowings,
            "composite_quality_score":      comp_score,
        })

    return results


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

INSERT_SQL = """
INSERT OR REPLACE INTO financial_ratios (
    company_id, year,
    net_profit_margin_pct, operating_profit_margin_pct,
    return_on_equity_pct, return_on_assets_pct, roce_pct,
    debt_to_equity, interest_coverage, icr_label,
    icr_warning_flag, high_leverage_flag,
    asset_turnover, net_debt_cr,
    free_cash_flow_cr, capex_cr, capex_intensity_pct,
    capex_intensity_label, fcf_conversion_pct,
    cash_from_operations_cr, cfo_quality_score,
    capital_allocation_pattern,
    revenue_cagr_3yr, revenue_cagr_3yr_flag,
    revenue_cagr_5yr, revenue_cagr_5yr_flag,
    revenue_cagr_10yr, revenue_cagr_10yr_flag,
    pat_cagr_3yr, pat_cagr_3yr_flag,
    pat_cagr_5yr, pat_cagr_5yr_flag,
    pat_cagr_10yr, pat_cagr_10yr_flag,
    eps_cagr_3yr, eps_cagr_3yr_flag,
    eps_cagr_5yr, eps_cagr_5yr_flag,
    eps_cagr_10yr, eps_cagr_10yr_flag,
    earnings_per_share, book_value_per_share,
    dividend_payout_ratio_pct, total_debt_cr,
    composite_quality_score
) VALUES (
    :company_id, :year,
    :net_profit_margin_pct, :operating_profit_margin_pct,
    :return_on_equity_pct, :return_on_assets_pct, :roce_pct,
    :debt_to_equity, :interest_coverage, :icr_label,
    :icr_warning_flag, :high_leverage_flag,
    :asset_turnover, :net_debt_cr,
    :free_cash_flow_cr, :capex_cr, :capex_intensity_pct,
    :capex_intensity_label, :fcf_conversion_pct,
    :cash_from_operations_cr, :cfo_quality_score,
    :capital_allocation_pattern,
    :revenue_cagr_3yr, :revenue_cagr_3yr_flag,
    :revenue_cagr_5yr, :revenue_cagr_5yr_flag,
    :revenue_cagr_10yr, :revenue_cagr_10yr_flag,
    :pat_cagr_3yr, :pat_cagr_3yr_flag,
    :pat_cagr_5yr, :pat_cagr_5yr_flag,
    :pat_cagr_10yr, :pat_cagr_10yr_flag,
    :eps_cagr_3yr, :eps_cagr_3yr_flag,
    :eps_cagr_5yr, :eps_cagr_5yr_flag,
    :eps_cagr_10yr, :eps_cagr_10yr_flag,
    :earnings_per_share, :book_value_per_share,
    :dividend_payout_ratio_pct, :total_debt_cr,
    :composite_quality_score
)
"""


def insert_ratios(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Batch insert ratio rows. Returns count inserted."""
    if not rows:
        return 0
    conn.executemany(INSERT_SQL, rows)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_ratio_pipeline(
    db_path: str,
    reset: bool = False,
) -> dict:
    """
    Full pipeline: schema → compute → insert → verify.

    Returns summary dict:
        rows_written, companies_processed, companies_skipped, errors
    """
    conn = get_connection(db_path)
    apply_schema(conn, reset=reset)

    companies = fetch_companies(conn)
    log.info(f"Processing {len(companies)} companies")

    total_rows = 0
    processed = 0
    skipped = 0
    errors = []

    for company in companies:
        cid = company["id"]
        name = company["company_name"]
        sector = company["broad_sector"]

        try:
            pl_rows = fetch_pl(conn, cid)
            bs_rows = fetch_bs(conn, cid)
            cf_rows = fetch_cf(conn, cid)
            bv      = fetch_company_book_value(conn, cid)

            if not pl_rows and not bs_rows:
                log.warning(f"No data for company_id={cid} ({name}), skipping")
                skipped += 1
                continue

            ratio_rows = compute_ratios_for_company(
                cid, sector, pl_rows, bs_rows, cf_rows,
                company_book_value=bv,
            )
            written = insert_ratios(conn, ratio_rows)
            total_rows += written
            processed += 1
            log.debug(f"  {name}: {written} rows written")

        except Exception as e:
            log.error(f"Error processing company_id={cid} ({name}): {e}")
            errors.append({"company_id": cid, "name": name, "error": str(e)})

    conn.close()

    summary = {
        "rows_written": total_rows,
        "companies_processed": processed,
        "companies_skipped": skipped,
        "errors": errors,
    }
    log.info(f"Pipeline complete: {summary}")
    return summary


# ---------------------------------------------------------------------------
# Verification query
# ---------------------------------------------------------------------------

def verify_row_count(db_path: str) -> int:
    """Return SELECT COUNT(*) FROM financial_ratios."""
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Populate financial_ratios table")
    parser.add_argument("--db", default=os.getenv("DB_PATH", "data/nifty100.db"))
    parser.add_argument("--reset", action="store_true", help="Drop and recreate table")
    args = parser.parse_args()

    summary = run_ratio_pipeline(args.db, reset=args.reset)

    count = verify_row_count(args.db)
    print(f"\n✅ financial_ratios rows: {count}")
    print(f"   Companies processed : {summary['companies_processed']}")
    print(f"   Companies skipped   : {summary['companies_skipped']}")
    print(f"   Errors              : {len(summary['errors'])}")

    if count < 1100:
        print(f"\n⚠️  WARNING: row count {count} is below the 1,100 exit gate!")
        sys.exit(1)
    else:
        print(f"\n🎯 Exit gate passed: {count} >= 1,100 rows")
