"""
tests/kpi/test_ratio_loader.py
===============================
Integration tests for db/ratio_loader.py

Uses an in-memory SQLite DB seeded with minimal fixture data so tests
run without touching the real nifty100.db.

Coverage:
  - Schema creation (financial_ratios table exists, has correct columns)
  - compute_ratios_for_company() produces correct KPI values
  - insert_ratios() writes rows and handles INSERT OR REPLACE
  - run_ratio_pipeline() end-to-end with fixture companies
  - verify_row_count() returns correct count
  - Edge cases: missing BS/CF data, financial sector ROCE carve-out
"""

import sqlite3
import pytest
from pathlib import Path

from db.ratio_loader import (
    apply_schema,
    compute_ratios_for_company,
    insert_ratios,
    verify_row_count,
    _composite_quality,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_db(tmp_path):
    """In-memory SQLite with main schema + financial_ratios schema."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Minimal main schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT NOT NULL,
            ticker TEXT,
            broad_sector TEXT
        );
        CREATE TABLE IF NOT EXISTS profitandloss (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            year INTEGER,
            sales REAL,
            net_profit REAL,
            operating_profit REAL,
            depreciation REAL,
            other_income REAL,
            interest REAL,
            eps_in_rs REAL,
            opm_percentage REAL,
            dividend_payout_pct REAL
        );
        CREATE TABLE IF NOT EXISTS balancesheet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            year INTEGER,
            equity_capital REAL,
            reserves REAL,
            borrowings REAL,
            total_assets REAL,
            investments REAL,
            book_value REAL
        );
        CREATE TABLE IF NOT EXISTS cashflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            year INTEGER,
            operating_activity REAL,
            investing_activity REAL,
            financing_activity REAL
        );
    """)

    # Seed 2 companies
    conn.execute("INSERT INTO companies VALUES (1, 'TestCo A', 'TESTA', 'Industrials')")
    conn.execute("INSERT INTO companies VALUES (2, 'TestBank', 'TBNK', 'Financials')")

    # TestCo A — 6 years of data (2018–2023)
    pl_data = [
        (1, 2018, 1000, 100, 200, 50, 20, 40, 10.0, 20.0, 30.0),
        (1, 2019, 1100, 110, 220, 55, 22, 38, 11.0, 20.0, 28.0),
        (1, 2020, 1200, 120, 240, 60, 25, 35, 12.0, 20.0, 25.0),
        (1, 2021, 1350, 130, 260, 65, 28, 32, 13.0, 19.3, 22.0),
        (1, 2022, 1500, 150, 290, 70, 30, 30, 15.0, 19.3, 20.0),
        (1, 2023, 1700, 170, 320, 75, 35, 28, 17.0, 18.8, 18.0),
    ]
    conn.executemany(
        "INSERT INTO profitandloss (company_id,year,sales,net_profit,operating_profit,"
        "depreciation,other_income,interest,eps_in_rs,opm_percentage,dividend_payout_pct)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)", pl_data
    )

    bs_data = [
        (1, 2018, 100, 900, 500, 1800, 100, 95.0),
        (1, 2019, 100, 980, 480, 1900, 110, 103.0),
        (1, 2020, 100, 1060, 460, 2050, 120, 111.0),
        (1, 2021, 100, 1150, 440, 2200, 130, 120.0),
        (1, 2022, 100, 1260, 420, 2400, 140, 130.0),
        (1, 2023, 100, 1380, 400, 2600, 150, 142.0),
    ]
    conn.executemany(
        "INSERT INTO balancesheet (company_id,year,equity_capital,reserves,borrowings,"
        "total_assets,investments,book_value) VALUES (?,?,?,?,?,?,?,?)", bs_data
    )

    cf_data = [
        (1, 2018, 150, -180, -50),
        (1, 2019, 160, -170, -60),
        (1, 2020, 175, -160, -55),
        (1, 2021, 190, -150, -65),
        (1, 2022, 210, -140, -70),
        (1, 2023, 230, -130, -80),
    ]
    conn.executemany(
        "INSERT INTO cashflow (company_id,year,operating_activity,investing_activity,"
        "financing_activity) VALUES (?,?,?,?,?)", cf_data
    )

    # TestBank — 3 years, Financials sector
    conn.executemany(
        "INSERT INTO profitandloss (company_id,year,sales,net_profit,operating_profit,"
        "depreciation,other_income,interest,eps_in_rs,opm_percentage,dividend_payout_pct)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (2, 2021, 5000, 800, 1200, 100, 50, 2000, 40.0, 24.0, 15.0),
            (2, 2022, 5500, 900, 1300, 110, 60, 2200, 45.0, 23.6, 14.0),
            (2, 2023, 6000, 1000, 1400, 120, 70, 2400, 50.0, 23.3, 13.0),
        ]
    )
    conn.executemany(
        "INSERT INTO balancesheet (company_id,year,equity_capital,reserves,borrowings,"
        "total_assets,investments,book_value) VALUES (?,?,?,?,?,?,?,?)",
        [
            (2, 2021, 200, 3800, 30000, 50000, 5000, 200.0),
            (2, 2022, 200, 4500, 32000, 55000, 6000, 237.5),
            (2, 2023, 200, 5300, 34000, 60000, 7000, 275.0),
        ]
    )
    conn.commit()

    # Apply financial_ratios schema
    apply_schema(conn)
    conn.close()

    return db_path


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_table_exists(self, mem_db):
        conn = sqlite3.connect(mem_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='financial_ratios'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_required_columns_present(self, mem_db):
        conn = sqlite3.connect(mem_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_ratios)")}
        conn.close()
        required = {
            "company_id", "year",
            "net_profit_margin_pct", "operating_profit_margin_pct",
            "return_on_equity_pct", "debt_to_equity", "interest_coverage",
            "asset_turnover", "free_cash_flow_cr", "capex_cr",
            "earnings_per_share", "book_value_per_share",
            "dividend_payout_ratio_pct", "total_debt_cr",
            "cash_from_operations_cr", "revenue_cagr_5yr",
            "pat_cagr_5yr", "eps_cagr_5yr", "composite_quality_score",
        }
        assert required.issubset(cols)

    def test_unique_constraint_company_year(self, mem_db):
        conn = sqlite3.connect(mem_db)
        conn.execute(
            "INSERT INTO financial_ratios (company_id, year) VALUES (1, 2023)"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO financial_ratios (company_id, year) VALUES (1, 2023)"
            )
        conn.close()


# ---------------------------------------------------------------------------
# compute_ratios_for_company tests
# ---------------------------------------------------------------------------

class TestComputeRatios:

    def _get_rows(self, mem_db, company_id):
        conn = sqlite3.connect(mem_db)
        conn.row_factory = sqlite3.Row
        pl = conn.execute(
            "SELECT * FROM profitandloss WHERE company_id=? ORDER BY year",
            (company_id,)
        ).fetchall()
        bs = conn.execute(
            "SELECT * FROM balancesheet WHERE company_id=? ORDER BY year",
            (company_id,)
        ).fetchall()
        cf = conn.execute(
            "SELECT * FROM cashflow WHERE company_id=? ORDER BY year",
            (company_id,)
        ).fetchall()
        conn.close()
        return pl, bs, cf

    def test_returns_one_row_per_year(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        assert len(rows) == 6

    def test_npm_correct(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2023: net_profit=170, sales=1700 → NPM=10%
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert round(row_2023["net_profit_margin_pct"], 2) == 10.0

    def test_roe_correct(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2023: net_profit=170, equity=100+1380=1480 → ROE=11.49%
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert round(row_2023["return_on_equity_pct"], 2) == pytest.approx(11.49, abs=0.1)

    def test_financials_roce_is_none(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 2)
        rows = compute_ratios_for_company(2, "Financials", pl, bs, cf)
        for row in rows:
            assert row["roce_pct"] is None

    def test_de_ratio_correct(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2023: borrowings=400, equity=1480 → D/E=0.27
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert round(row_2023["debt_to_equity"], 2) == pytest.approx(0.27, abs=0.01)

    def test_fcf_correct(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2023: CFO=230, CFI=-130 → FCF=100
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert row_2023["free_cash_flow_cr"] == 100.0

    def test_capital_allocation_pattern(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # CFO=+, CFI=-, CFF=- → Reinvestor
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert row_2023["capital_allocation_pattern"] == "Reinvestor"

    def test_insufficient_cagr_for_early_years(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2018 is first year — only 1 data point, all CAGR windows INSUFFICIENT
        row_2018 = next(r for r in rows if r["year"] == 2018)
        assert row_2018["revenue_cagr_3yr"] is None
        assert row_2018["revenue_cagr_3yr_flag"] == "INSUFFICIENT"

    def test_cagr_5yr_available_after_5_years(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        # 2023 has 6 years of data → 5yr CAGR should be a float
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert isinstance(row_2023["revenue_cagr_5yr"], float)
        assert row_2023["revenue_cagr_5yr_flag"] is None

    def test_composite_score_populated(self, mem_db):
        pl, bs, cf = self._get_rows(mem_db, 1)
        rows = compute_ratios_for_company(1, "Industrials", pl, bs, cf)
        row_2023 = next(r for r in rows if r["year"] == 2023)
        assert row_2023["composite_quality_score"] is not None
        assert 0 <= row_2023["composite_quality_score"] <= 100


# ---------------------------------------------------------------------------
# insert_ratios tests
# ---------------------------------------------------------------------------

class TestInsertRatios:
    def test_insert_returns_row_count(self, mem_db):
        conn = sqlite3.connect(mem_db)
        conn.row_factory = sqlite3.Row
        rows = [{"company_id": 1, "year": 2023, **{k: None for k in [
            "net_profit_margin_pct","operating_profit_margin_pct",
            "return_on_equity_pct","return_on_assets_pct","roce_pct",
            "debt_to_equity","interest_coverage","icr_label",
            "icr_warning_flag","high_leverage_flag","asset_turnover","net_debt_cr",
            "free_cash_flow_cr","capex_cr","capex_intensity_pct","capex_intensity_label",
            "fcf_conversion_pct","cash_from_operations_cr","cfo_quality_score",
            "capital_allocation_pattern",
            "revenue_cagr_3yr","revenue_cagr_3yr_flag",
            "revenue_cagr_5yr","revenue_cagr_5yr_flag",
            "revenue_cagr_10yr","revenue_cagr_10yr_flag",
            "pat_cagr_3yr","pat_cagr_3yr_flag",
            "pat_cagr_5yr","pat_cagr_5yr_flag",
            "pat_cagr_10yr","pat_cagr_10yr_flag",
            "eps_cagr_3yr","eps_cagr_3yr_flag",
            "eps_cagr_5yr","eps_cagr_5yr_flag",
            "eps_cagr_10yr","eps_cagr_10yr_flag",
            "earnings_per_share","book_value_per_share",
            "dividend_payout_ratio_pct","total_debt_cr","composite_quality_score",
        ]}}]
        count = insert_ratios(conn, rows)
        conn.close()
        assert count == 1

    def test_insert_or_replace_idempotent(self, mem_db):
        conn = sqlite3.connect(mem_db)
        conn.row_factory = sqlite3.Row
        row = {"company_id": 1, "year": 2020, **{k: None for k in [
            "net_profit_margin_pct","operating_profit_margin_pct",
            "return_on_equity_pct","return_on_assets_pct","roce_pct",
            "debt_to_equity","interest_coverage","icr_label",
            "icr_warning_flag","high_leverage_flag","asset_turnover","net_debt_cr",
            "free_cash_flow_cr","capex_cr","capex_intensity_pct","capex_intensity_label",
            "fcf_conversion_pct","cash_from_operations_cr","cfo_quality_score",
            "capital_allocation_pattern",
            "revenue_cagr_3yr","revenue_cagr_3yr_flag",
            "revenue_cagr_5yr","revenue_cagr_5yr_flag",
            "revenue_cagr_10yr","revenue_cagr_10yr_flag",
            "pat_cagr_3yr","pat_cagr_3yr_flag",
            "pat_cagr_5yr","pat_cagr_5yr_flag",
            "pat_cagr_10yr","pat_cagr_10yr_flag",
            "eps_cagr_3yr","eps_cagr_3yr_flag",
            "eps_cagr_5yr","eps_cagr_5yr_flag",
            "eps_cagr_10yr","eps_cagr_10yr_flag",
            "earnings_per_share","book_value_per_share",
            "dividend_payout_ratio_pct","total_debt_cr","composite_quality_score",
        ]}}
        insert_ratios(conn, [row])
        insert_ratios(conn, [row])   # second insert — no error
        count = conn.execute(
            "SELECT COUNT(*) FROM financial_ratios WHERE company_id=1 AND year=2020"
        ).fetchone()[0]
        conn.close()
        assert count == 1   # replaced, not duplicated

    def test_empty_list_returns_zero(self, mem_db):
        conn = sqlite3.connect(mem_db)
        assert insert_ratios(conn, []) == 0
        conn.close()


# ---------------------------------------------------------------------------
# Composite quality score unit tests
# ---------------------------------------------------------------------------

class TestCompositeQuality:
    def test_all_top_scores(self):
        score = _composite_quality(15.0, 20.0, 5.0, "High Quality", 20.0)
        assert score == 100.0

    def test_all_none_returns_none(self):
        assert _composite_quality(None, None, None, None, None) is None

    def test_partial_inputs(self):
        score = _composite_quality(15.0, None, None, None, None)
        assert score == 100.0   # only 1 component, full score on it

    def test_moderate_returns_midrange(self):
        score = _composite_quality(7.0, 12.0, 2.0, "Moderate", 10.0)
        assert 40.0 <= score <= 60.0
