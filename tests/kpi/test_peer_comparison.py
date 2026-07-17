"""
tests/kpi/test_peer_comparison.py
===================================
Tests for src/analytics/peer_comparison.py
"""

import os
import sqlite3
import pytest
import pandas as pd

from src.analytics.peer_comparison import (
    load_peer_group_data,
    get_peer_groups,
    get_benchmark_company,
    generate_peer_comparison_excel,
)


# ---------------------------------------------------------------------------
# Fixture DB
# ---------------------------------------------------------------------------

@pytest.fixture
def peer_comp_db(tmp_path):
    db_path = str(tmp_path / "peer_comp_test.db")
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT,
            book_value REAL,
            roce_percentage REAL,
            roe_percentage REAL
        );
        CREATE TABLE sectors (
            company_id INTEGER,
            broad_sector TEXT,
            sub_sector TEXT,
            index_weight_pct REAL,
            market_cap_category TEXT
        );
        CREATE TABLE financial_ratios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            year INTEGER,
            return_on_equity_pct REAL,
            roce_pct REAL,
            net_profit_margin_pct REAL,
            debt_to_equity REAL,
            free_cash_flow_cr REAL,
            pat_cagr_5yr REAL,
            revenue_cagr_5yr REAL,
            eps_cagr_5yr REAL,
            interest_coverage REAL,
            asset_turnover REAL,
            composite_quality_score REAL,
            UNIQUE(company_id, year)
        );
        CREATE TABLE peer_percentiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            peer_group_name TEXT,
            metric TEXT,
            value REAL,
            percentile_rank REAL,
            year INTEGER,
            UNIQUE(company_id, peer_group_name, metric, year)
        );
    """)

    conn.executemany("INSERT INTO companies (id, company_name) VALUES (?,?)", [
        (1, "AlphaCo"), (2, "BetaCo"), (3, "GammaCo"),
        (4, "TechA"),   (5, "TechB"),
    ])

    conn.executemany(
        "INSERT INTO financial_ratios (company_id, year, return_on_equity_pct, roce_pct,"
        "net_profit_margin_pct, debt_to_equity, free_cash_flow_cr, pat_cagr_5yr,"
        "revenue_cagr_5yr, eps_cagr_5yr, interest_coverage, asset_turnover, composite_quality_score)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 2023, 22.0, 18.0, 12.0, 0.3, 500.0, 16.0, 14.0, 15.0, 5.0, 1.2, 85.0),
            (2, 2023, 15.0, 12.0,  8.0, 0.8, 300.0, 10.0,  9.0, 10.0, 3.0, 0.9, 65.0),
            (3, 2023,  8.0,  6.0,  4.0, 2.0, 100.0,  5.0,  6.0,  5.0, 1.5, 0.6, 40.0),
            (4, 2023, 25.0, 22.0, 15.0, 0.2, 600.0, 20.0, 18.0, 20.0, 8.0, 1.5, 90.0),
            (5, 2023, 18.0, 15.0, 10.0, 0.5, 400.0, 14.0, 12.0, 14.0, 5.0, 1.1, 70.0),
        ]
    )

    metrics = ["ROE", "ROCE", "Net Profit Margin", "D/E", "FCF",
               "PAT CAGR 5yr", "Revenue CAGR 5yr", "EPS CAGR 5yr",
               "Interest Coverage", "Asset Turnover"]

    ind_ranks = {1: 100.0, 2: 50.0, 3: 0.0}
    for cid, rank in ind_ranks.items():
        for metric in metrics:
            conn.execute(
                "INSERT OR REPLACE INTO peer_percentiles "
                "(company_id, peer_group_name, metric, value, percentile_rank, year) "
                "VALUES (?,?,?,?,?,?)",
                (cid, "Industrials — Manufacturing", metric, rank, rank, 2023)
            )

    tech_ranks = {4: 100.0, 5: 0.0}
    for cid, rank in tech_ranks.items():
        for metric in metrics:
            conn.execute(
                "INSERT OR REPLACE INTO peer_percentiles "
                "(company_id, peer_group_name, metric, value, percentile_rank, year) "
                "VALUES (?,?,?,?,?,?)",
                (cid, "Technology — IT Services", metric, rank, rank, 2023)
            )

    conn.commit()
    conn.close()
    return db_path


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Data loader tests
# ---------------------------------------------------------------------------

class TestLoadPeerGroupData:

    def test_returns_dataframe(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        df = load_peer_group_data(conn, "Industrials — Manufacturing")
        conn.close()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_has_value_and_rank_columns(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        df = load_peer_group_data(conn, "Industrials — Manufacturing")
        conn.close()
        assert "return_on_equity_pct" in df.columns
        assert "rank_ROE" in df.columns

    def test_empty_for_unknown_group(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        df = load_peer_group_data(conn, "Nonexistent Group")
        conn.close()
        assert df.empty


# ---------------------------------------------------------------------------
# get_peer_groups tests
# ---------------------------------------------------------------------------

class TestGetPeerGroups:

    def test_returns_two_groups(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        groups = get_peer_groups(conn)
        conn.close()
        assert len(groups) == 2

    def test_contains_expected_groups(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        groups = get_peer_groups(conn)
        conn.close()
        assert "Industrials — Manufacturing" in groups
        assert "Technology — IT Services" in groups


# ---------------------------------------------------------------------------
# get_benchmark_company tests
# ---------------------------------------------------------------------------

class TestGetBenchmarkCompany:

    def test_returns_highest_composite_score(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        # AlphaCo has highest composite (85) in Industrials
        benchmark = get_benchmark_company(conn, "Industrials — Manufacturing")
        conn.close()
        assert benchmark == 1

    def test_tech_benchmark_is_techA(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        benchmark = get_benchmark_company(conn, "Technology — IT Services")
        conn.close()
        assert benchmark == 4

    def test_unknown_group_returns_none(self, peer_comp_db):
        conn = _conn(peer_comp_db)
        benchmark = get_benchmark_company(conn, "Nonexistent")
        conn.close()
        assert benchmark is None


# ---------------------------------------------------------------------------
# Excel generation tests
# ---------------------------------------------------------------------------

class TestGeneratePeerComparisonExcel:

    def test_generates_file(self, peer_comp_db, tmp_path):
        conn = _conn(peer_comp_db)
        out = str(tmp_path / "peer_comparison.xlsx")
        path = generate_peer_comparison_excel(conn, output_path=out)
        conn.close()
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_has_correct_number_of_sheets(self, peer_comp_db, tmp_path):
        conn = _conn(peer_comp_db)
        out = str(tmp_path / "peer_comparison.xlsx")
        generate_peer_comparison_excel(conn, output_path=out)
        conn.close()
        xl = pd.ExcelFile(out)
        assert len(xl.sheet_names) == 2

    def test_sheet_names_match_peer_groups(self, peer_comp_db, tmp_path):
        conn = _conn(peer_comp_db)
        out = str(tmp_path / "peer_comparison.xlsx")
        generate_peer_comparison_excel(conn, output_path=out)
        conn.close()
        xl = pd.ExcelFile(out)
        assert any("Industrials" in s for s in xl.sheet_names)
        assert any("Technology" in s for s in xl.sheet_names)

    def test_no_peer_groups_raises(self, tmp_path):
        # Empty DB — no peer_percentiles
        db_path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE peer_percentiles (id INTEGER, peer_group_name TEXT, "
                     "company_id INTEGER, metric TEXT, value REAL, percentile_rank REAL, year INTEGER)")
        conn.commit()
        with pytest.raises(ValueError, match="No peer groups found"):
            generate_peer_comparison_excel(conn, output_path=str(tmp_path / "out.xlsx"))
        conn.close()
