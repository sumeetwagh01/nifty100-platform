"""
src/dashboard/utils/db.py
==========================
Shared database loader for the Nifty 100 Streamlit dashboard.

Rules:
- Every public function is decorated with @st.cache_data(ttl=600)
  so repeated calls within a 10-minute window hit the cache.
- DB_PATH is resolved relative to the project root so the module
  works whether Streamlit is launched from the project root or from
  inside src/dashboard/.
- All functions return pandas DataFrames (never raw sqlite3 rows).
- Schema aliases follow the Sprint 1/2 known mismatches:
    eps_in_rs  → eps  (profitandloss)
    dividend_payout_pct → dividend_payout  (profitandloss)
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Resolve DB path relative to repo root (two levels above this file).
# Layout: src/dashboard/utils/db.py → src/dashboard → src → repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = str(_REPO_ROOT / "data" / "nifty100.db")


def _connect() -> sqlite3.Connection:
    """Return a read-only SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Public query functions — each cached for 10 minutes
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """
    All 92 companies with sector info.

    Columns:
        id, company_name, book_value, roce_percentage, roe_percentage,
        broad_sector, sub_sector, index_weight_pct, market_cap_category
    """
    sql = """
        SELECT
            c.id,
            c.company_name,
            c.book_value,
            c.roce_percentage,
            c.roe_percentage,
            s.broad_sector,
            s.sub_sector,
            s.index_weight_pct,
            s.market_cap_category
        FROM companies c
        LEFT JOIN sectors s ON s.company_id = c.id
        ORDER BY c.company_name
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: int | None = None) -> pd.DataFrame:
    """
    Financial ratios for a single company.

    Args:
        ticker: NSE ticker (e.g. 'TCS')
        year:   Optional integer year filter. If None, returns all years.

    Columns: all 45 columns from financial_ratios.
    """
    if year is not None:
        sql = """
            SELECT * FROM financial_ratios
            WHERE company_id = ?
              AND year = ?
            ORDER BY year
        """
        params: tuple = (ticker, year)
    else:
        sql = """
            SELECT * FROM financial_ratios
            WHERE company_id = ?
            ORDER BY year
        """
        params = (ticker,)

    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """
    Profit & Loss statement for a single company — all available years.

    Aliases applied to match Sprint 2 column expectations:
        eps              → eps_in_rs
        dividend_payout  → dividend_payout_pct

    Columns:
        company_id, year, sales, expenses, operating_profit,
        opm_percentage, other_income, interest, depreciation,
        profit_before_tax, tax_percentage, net_profit,
        eps_in_rs, dividend_payout_pct
    """
    sql = """
        SELECT
            company_id,
            year,
            sales,
            expenses,
            operating_profit,
            opm_percentage,
            other_income,
            interest,
            depreciation,
            profit_before_tax,
            tax_percentage,
            net_profit,
            eps          AS eps_in_rs,
            dividend_payout AS dividend_payout_pct
        FROM profitandloss
        WHERE company_id = ?
          AND year != 'PARSE_ERROR'
        ORDER BY year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """
    Balance Sheet for a single company — all available years.

    Columns:
        company_id, year, equity_capital, reserves, borrowings,
        other_liabilities, total_liabilities, fixed_assets, cwip,
        investments, other_asset, total_assets
    """
    sql = """
        SELECT
            company_id,
            year,
            equity_capital,
            reserves,
            borrowings,
            other_liabilities,
            total_liabilities,
            fixed_assets,
            cwip,
            investments,
            other_asset,
            total_assets
        FROM balancesheet
        WHERE company_id = ?
          AND year != 'PARSE_ERROR'
        ORDER BY year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """
    Cash Flow statement for a single company — all available years.

    Columns:
        company_id, year, operating_activity, investing_activity,
        financing_activity, net_cash_flow
    """
    sql = """
        SELECT
            company_id,
            year,
            operating_activity,
            investing_activity,
            financing_activity,
            net_cash_flow
        FROM cashflow
        WHERE company_id = ?
          AND year != 'PARSE_ERROR'
        ORDER BY year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """
    Full sector mapping for all companies.

    Columns:
        company_id, broad_sector, sub_sector, index_weight_pct,
        market_cap_category
    """
    sql = """
        SELECT
            company_id,
            broad_sector,
            sub_sector,
            index_weight_pct,
            market_cap_category
        FROM sectors
        ORDER BY broad_sector, sub_sector
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    """
    Peer percentile data for a named peer group.

    Args:
        group_name: One of the 11 peer group names defined by PeerEngine,
                    e.g. 'Financials — Banking', 'Technology — IT Services'.

    Columns:
        company_id, peer_group_name, metric, value, percentile_rank, year
    """
    sql = """
        SELECT
            company_id,
            peer_group_name,
            metric,
            value,
            percentile_rank,
            year
        FROM peer_percentiles
        WHERE peer_group_name = ?
        ORDER BY company_id, metric, year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(group_name,))


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    """
    Market cap and valuation multiples for a single company.

    Sources: market_cap table (Sprint 1, Section 6.3).
    Columns:
        company_id, year, market_cap_crore, enterprise_value_crore,
        pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct
    """
    sql = """
        SELECT
            company_id,
            year,
            market_cap_crore,
            enterprise_value_crore,
            pe_ratio,
            pb_ratio,
            ev_ebitda,
            dividend_yield_pct
        FROM market_cap
        WHERE company_id = ?
        ORDER BY year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


# ---------------------------------------------------------------------------
# Home page aggregates — used by pages/01_home.py
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_home_summary(year: int) -> pd.DataFrame:
    """
    Per-company KPI snapshot for the Home page.

    Picks the LATEST financial_ratios row whose year string starts with
    the requested calendar year (e.g. 2024 → matches '2024-03', '2024-09').
    Also joins market_cap for the P/E ratio of that same year.

    Columns returned:
        company_id, company_name, broad_sector,
        return_on_equity_pct, roce_pct, net_profit_margin_pct,
        debt_to_equity, revenue_cagr_5yr, free_cash_flow_cr,
        composite_quality_score, pe_ratio
    """
    sql = """
        WITH latest_ratios AS (
            SELECT
                company_id,
                MAX(year) AS latest_year
            FROM financial_ratios
            WHERE year LIKE :year_prefix
            GROUP BY company_id
        )
        SELECT
            fr.company_id,
            c.company_name,
            s.broad_sector,
            fr.return_on_equity_pct,
            fr.roce_pct,
            fr.net_profit_margin_pct,
            fr.debt_to_equity,
            fr.revenue_cagr_5yr,
            fr.free_cash_flow_cr,
            fr.composite_quality_score,
            mc.pe_ratio
        FROM latest_ratios lr
        JOIN financial_ratios fr
            ON fr.company_id = lr.company_id AND fr.year = lr.latest_year
        JOIN companies c ON c.id = fr.company_id
        LEFT JOIN sectors s ON s.company_id = fr.company_id
        LEFT JOIN market_cap mc
            ON mc.company_id = fr.company_id AND mc.year = :cal_year
        ORDER BY fr.composite_quality_score DESC NULLS LAST
    """
    with _connect() as conn:
        return pd.read_sql_query(
            sql, conn, params={"year_prefix": f"{year}%", "cal_year": year}
        )


@st.cache_data(ttl=600)
def get_prosandcons(ticker: str) -> pd.DataFrame:
    """
    Pros and cons qualitative data for a single company.

    Columns: id, company_id, pros, cons
    Multiple rows may exist per company (one row per bullet point pair).
    Returns empty DataFrame if no data found.
    """
    sql = """
        SELECT id, company_id, pros, cons
        FROM prosandcons
        WHERE company_id = ?
        ORDER BY id
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


# ---------------------------------------------------------------------------
# Helper — used by multiple pages to build the company selector widget
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def get_ticker_list() -> list[str]:
    """Return sorted list of all NSE tickers (company IDs)."""
    sql = "SELECT id FROM companies ORDER BY id"
    with _connect() as conn:
        df = pd.read_sql_query(sql, conn)
    return df["id"].tolist()


# ---------------------------------------------------------------------------
# Screener data — used by pages/03_screener.py
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_screener_data() -> pd.DataFrame:
    """
    All 92 companies with their latest-year financial ratios and 2024
    valuation multiples, pre-joined for the Screener page.

    Uses the LATEST financial_ratios row per company (MAX(year) per company_id).
    Joins market_cap for calendar year 2024 (P/E, P/B, Dividend Yield).

    Columns:
        company_id, company_name, broad_sector,
        return_on_equity_pct, roce_pct, net_profit_margin_pct,
        debt_to_equity, revenue_cagr_5yr, pat_cagr_5yr,
        free_cash_flow_cr, interest_coverage, composite_quality_score,
        pe_ratio, pb_ratio, dividend_yield_pct
    """
    sql = """
        WITH latest AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            fr.company_id,
            TRIM(c.company_name)   AS company_name,
            s.broad_sector,
            fr.return_on_equity_pct,
            fr.roce_pct,
            fr.net_profit_margin_pct,
            fr.debt_to_equity,
            fr.revenue_cagr_5yr,
            fr.pat_cagr_5yr,
            fr.free_cash_flow_cr,
            fr.interest_coverage,
            fr.composite_quality_score,
            mc.pe_ratio,
            mc.pb_ratio,
            mc.dividend_yield_pct
        FROM latest lr
        JOIN financial_ratios fr
            ON fr.company_id = lr.company_id AND fr.year = lr.latest_year
        JOIN companies c ON c.id = fr.company_id
        LEFT JOIN sectors s ON s.company_id = fr.company_id
        LEFT JOIN market_cap mc
            ON mc.company_id = fr.company_id AND mc.year = 2024
        ORDER BY fr.composite_quality_score DESC
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


# ---------------------------------------------------------------------------
# Peer comparison data — used by pages/04_peers.py
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_broad_sectors() -> list[str]:
    """Return sorted list of distinct broad sectors from the sectors table."""
    sql = """
        SELECT DISTINCT broad_sector
        FROM sectors
        WHERE broad_sector IS NOT NULL
        ORDER BY broad_sector
    """
    with _connect() as conn:
        df = pd.read_sql_query(sql, conn)
    return df["broad_sector"].tolist()


@st.cache_data(ttl=600)
def get_peer_sector_data(sector: str) -> pd.DataFrame:
    """
    All companies in a given broad_sector with their latest-year ratios,
    for use in the Peer Comparison radar chart and KPI table.

    Columns:
        company_id, company_name, broad_sector, sub_sector,
        return_on_equity_pct, roce_pct, net_profit_margin_pct,
        debt_to_equity, revenue_cagr_5yr, pat_cagr_5yr,
        interest_coverage, composite_quality_score,
        pe_ratio, pb_ratio, dividend_yield_pct
    """
    sql = """
        WITH latest AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            fr.company_id,
            TRIM(c.company_name)  AS company_name,
            s.broad_sector,
            s.sub_sector,
            fr.return_on_equity_pct,
            fr.roce_pct,
            fr.net_profit_margin_pct,
            fr.debt_to_equity,
            fr.revenue_cagr_5yr,
            fr.pat_cagr_5yr,
            fr.interest_coverage,
            fr.composite_quality_score,
            mc.pe_ratio,
            mc.pb_ratio,
            mc.dividend_yield_pct
        FROM latest lr
        JOIN financial_ratios fr
            ON fr.company_id = lr.company_id AND fr.year = lr.latest_year
        JOIN companies c ON c.id = fr.company_id
        JOIN sectors s ON s.company_id = fr.company_id
        LEFT JOIN market_cap mc
            ON mc.company_id = fr.company_id AND mc.year = 2024
        WHERE s.broad_sector = ?
        ORDER BY fr.composite_quality_score DESC NULLS LAST
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(sector,))


# ---------------------------------------------------------------------------
# Trends page — Day 25
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_trend_metrics(ticker: str) -> pd.DataFrame:
    """
    Multi-metric time-series for a single company — used by Trends page.

    Returns one row per year with:
        year, sales, net_profit, eps_in_rs,
        return_on_equity_pct, roce_pct, debt_to_equity,
        net_profit_margin_pct, free_cash_flow_cr
    """
    sql = """
        SELECT
            pl.year,
            pl.sales,
            pl.net_profit,
            pl.eps          AS eps_in_rs,
            fr.return_on_equity_pct,
            fr.roce_pct,
            fr.debt_to_equity,
            fr.net_profit_margin_pct,
            fr.free_cash_flow_cr
        FROM profitandloss pl
        LEFT JOIN financial_ratios fr
            ON fr.company_id = pl.company_id AND fr.year = pl.year
        WHERE pl.company_id = ?
          AND pl.year != 'PARSE_ERROR'
        ORDER BY pl.year
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


# ---------------------------------------------------------------------------
# Sectors page — Day 25
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_sector_bubble_data() -> pd.DataFrame:
    """
    Data for sector bubble chart:
        company_id, company_name, broad_sector, sub_sector,
        sales (latest year), return_on_equity_pct (latest),
        market_cap_crore (2024), composite_quality_score
    """
    sql = """
        WITH latest_pl AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM profitandloss
            WHERE year != 'PARSE_ERROR'
            GROUP BY company_id
        ),
        latest_fr AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            c.id            AS company_id,
            TRIM(c.company_name) AS company_name,
            s.broad_sector,
            s.sub_sector,
            pl.sales,
            fr.return_on_equity_pct,
            fr.composite_quality_score,
            mc.market_cap_crore
        FROM companies c
        JOIN sectors s ON s.company_id = c.id
        JOIN latest_pl lp ON lp.company_id = c.id
        JOIN profitandloss pl ON pl.company_id = c.id AND pl.year = lp.latest_year
        JOIN latest_fr lf ON lf.company_id = c.id
        JOIN financial_ratios fr ON fr.company_id = c.id AND fr.year = lf.latest_year
        LEFT JOIN market_cap mc ON mc.company_id = c.id AND mc.year = 2024
        ORDER BY s.broad_sector, company_name
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


@st.cache_data(ttl=600)
def get_sector_kpi_summary() -> pd.DataFrame:
    """
    Sector-level median KPIs for the Sectors bar chart.

    Columns: broad_sector, median_roe, median_roce, median_npm,
             median_de, company_count
    """
    sql = """
        WITH latest AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            s.broad_sector,
            COUNT(DISTINCT fr.company_id)          AS company_count,
            AVG(fr.return_on_equity_pct)            AS avg_roe,
            AVG(fr.roce_pct)                        AS avg_roce,
            AVG(fr.net_profit_margin_pct)           AS avg_npm,
            AVG(fr.debt_to_equity)                  AS avg_de
        FROM financial_ratios fr
        JOIN latest l ON l.company_id = fr.company_id AND l.latest_year = fr.year
        JOIN sectors s ON s.company_id = fr.company_id
        WHERE s.broad_sector IS NOT NULL
        GROUP BY s.broad_sector
        ORDER BY avg_roe DESC
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


# ---------------------------------------------------------------------------
# Capital Allocation page — Day 25
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_capital_allocation_map() -> pd.DataFrame:
    """
    Latest capital_allocation_pattern per company for the treemap.

    Columns: company_id, company_name, broad_sector,
             capital_allocation_pattern, composite_quality_score
    """
    sql = """
        WITH latest AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            fr.company_id,
            TRIM(c.company_name) AS company_name,
            s.broad_sector,
            COALESCE(fr.capital_allocation_pattern, 'Unknown') AS pattern,
            fr.composite_quality_score
        FROM financial_ratios fr
        JOIN latest l ON l.company_id = fr.company_id AND l.latest_year = fr.year
        JOIN companies c ON c.id = fr.company_id
        LEFT JOIN sectors s ON s.company_id = fr.company_id
        ORDER BY fr.capital_allocation_pattern, fr.company_id
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)


# ---------------------------------------------------------------------------
# Reports page — Day 25
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_annual_reports(ticker: str) -> pd.DataFrame:
    """
    Annual report URLs for a single company from the documents table.

    Columns: company_id, year, annual_report_url
    """
    sql = """
        SELECT company_id, year, annual_report_url
        FROM documents
        WHERE company_id = ?
          AND annual_report_url IS NOT NULL
          AND annual_report_url != ''
        ORDER BY year DESC
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=(ticker,))


# ---------------------------------------------------------------------------
# Valuation page — Day 26
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_valuation_data() -> pd.DataFrame:
    """
    Full valuation dataset for all companies — used by valuation.py and
    the Valuation dashboard page.

    Columns: company_id, company_name, broad_sector,
             pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct,
             market_cap_crore, free_cash_flow_cr, composite_quality_score
    """
    sql = """
        WITH latest_fr AS (
            SELECT company_id, MAX(year) AS latest_year
            FROM financial_ratios
            GROUP BY company_id
        )
        SELECT
            fr.company_id,
            TRIM(c.company_name)   AS company_name,
            s.broad_sector,
            mc.pe_ratio,
            mc.pb_ratio,
            mc.ev_ebitda,
            mc.dividend_yield_pct,
            mc.market_cap_crore,
            fr.free_cash_flow_cr,
            fr.composite_quality_score
        FROM latest_fr lf
        JOIN financial_ratios fr
            ON fr.company_id = lf.company_id AND fr.year = lf.latest_year
        JOIN companies c ON c.id = fr.company_id
        LEFT JOIN sectors s ON s.company_id = fr.company_id
        LEFT JOIN market_cap mc
            ON mc.company_id = fr.company_id AND mc.year = 2024
        ORDER BY fr.composite_quality_score DESC NULLS LAST
    """
    with _connect() as conn:
        return pd.read_sql_query(sql, conn)

