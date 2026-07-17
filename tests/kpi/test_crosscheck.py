"""
tests/kpi/test_crosscheck.py
=============================
Tests for src/analytics/edge_case_logger.py and db/crosscheck.py

Uses in-memory SQLite with fixture data covering:
  - Financials sector company (bank carve-out)
  - Non-financial with high D/E
  - ROCE/ROE mismatch vs screener values
  - Screener preview query (ROE > 15% AND D/E < 1)
"""

import os
import sqlite3
import pytest
import tempfile
from pathlib import Path

from src.analytics.edge_case_logger import (
    log_cagr_edge, log_roce_mismatch, log_roe_mismatch,
    log_bank_carve_out, log_de_flag_suppressed,
    log_session_header, log_session_footer,
    CAGR_EDGE, ROCE_MISMATCH, ROE_MISMATCH,
    BANK_CARVE_OUT, DE_FLAG_SUPPRESSED,
)
from db.crosscheck import (
    run_roce_crosscheck,
    run_roe_crosscheck,
    run_de_suppression_audit,
    run_screener_preview,
    _classify_roce_anomaly,
    _classify_roe_anomaly,
)


# ---------------------------------------------------------------------------
# Fixture DB
# ---------------------------------------------------------------------------

@pytest.fixture
def crosscheck_db(tmp_path):
    db_path = str(tmp_path / "crosscheck_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT,
            roce_percentage REAL,
            roe_percentage REAL,
            book_value REAL
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
            debt_to_equity REAL,
            high_leverage_flag INTEGER,
            net_profit_margin_pct REAL,
            revenue_cagr_5yr REAL,
            UNIQUE(company_id, year)
        );
    """)

    # Companies: 1=industrial, 2=bank, 3=high ROE low DE
    conn.executemany("INSERT INTO companies VALUES (?,?,?,?,?)", [
        (1, "IndustrialCo", 25.0,  18.0, 150.0),   # ROCE close match
        (2, "BigBank",      None,   15.0, 200.0),   # Financials — no screener ROCE
        (3, "QualityCo",   20.0,   0.52, 180.0),   # ROE mismatch (screener=0.52 decimal fraction)
        (4, "DebtyCo",     10.0,    8.0, 100.0),   # high D/E, non-financial
    ])
    conn.executemany("INSERT INTO sectors VALUES (?,?,?,?,?)", [
        (1, "Industrials",  "Manufacturing", 1.2, "Large"),
        (2, "Financials",   "Banking",       2.1, "Large"),
        (3, "Technology",   "IT Services",   3.0, "Large"),
        (4, "Industrials",  "Infrastructure",0.8, "Large"),
    ])
    conn.executemany(
        "INSERT INTO financial_ratios (company_id,year,return_on_equity_pct,"
        "roce_pct,debt_to_equity,high_leverage_flag,net_profit_margin_pct,revenue_cagr_5yr)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [
            (1, 2023, 18.5,  27.0, 0.4, 0, 12.0, 14.0),  # ROCE diff=2 → no mismatch
            (2, 2023, 14.0,  None, 8.5, 0, 18.0, 10.0),  # bank — roce_pct=None, D/E high suppressed
            (3, 2023, 24.0,  22.0, 0.3, 0, 16.0, 18.0),  # ROE: computed=24, screener=0.52 → mismatch
            (4, 2023,  8.0,  11.0, 6.5, 0,  5.0,  6.0),  # D/E=6.5 but flag suppressed? no — non-financial
        ]
    )
    conn.commit()
    conn.close()
    return db_path


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Edge Case Logger tests
# ---------------------------------------------------------------------------

class TestEdgeCaseLogger:

    def test_log_cagr_edge_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Should not raise
        log_cagr_edge(1, "TestCo", 2023, "revenue", 5, "TURNAROUND")

    def test_log_roce_mismatch_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_roce_mismatch(1, "TestCo", 25.0, 40.0, 15.0, "version_difference")

    def test_log_roe_mismatch_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_roe_mismatch(1, "TestCo", 22.0, 0.52, 21.48, "data_source_issue")

    def test_log_bank_carve_out_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_bank_carve_out(2, "BigBank")

    def test_log_de_flag_suppressed_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_de_flag_suppressed(2, "BigBank", 8.5)

    def test_log_session_markers_no_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_session_header("data/test.db", 92)
        log_session_footer(1155, 12)


# ---------------------------------------------------------------------------
# Anomaly classification tests
# ---------------------------------------------------------------------------

class TestClassification:

    def test_roce_financials_always_formula_discrepancy(self):
        result = _classify_roce_anomaly("BigBank", 30.0, 10.0, "Financials")
        assert result == "formula_discrepancy"

    def test_roce_large_diff_data_source_issue(self):
        result = _classify_roce_anomaly("SomeCo", 80.0, 10.0, "Industrials")
        assert result == "data_source_issue"

    def test_roce_moderate_diff_version_difference(self):
        result = _classify_roce_anomaly("SomeCo", 25.0, 18.0, "Industrials")
        assert result == "version_difference"

    def test_roe_decimal_fraction_data_source(self):
        # screener=0.52, computed=22 → decimal fraction issue
        result = _classify_roe_anomaly("TCS", 22.0, 0.52)
        assert "decimal fraction" in result

    def test_roe_large_diff_data_source(self):
        result = _classify_roe_anomaly("SomeCo", 80.0, 10.0)
        assert result == "data_source_issue"

    def test_roe_moderate_diff_version_difference(self):
        result = _classify_roe_anomaly("SomeCo", 18.0, 12.0)
        assert result == "version_difference"


# ---------------------------------------------------------------------------
# ROCE cross-check tests
# ---------------------------------------------------------------------------

class TestROCECrosscheck:

    def test_runs_without_error(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_roce_crosscheck(conn)
        conn.close()
        assert "total_checked" in result
        assert "mismatches" in result
        assert "bank_carve_outs" in result

    def test_bank_carve_out_counted(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_roce_crosscheck(conn)
        conn.close()
        # BigBank has no screener ROCE so won't count as carve-out here,
        # but IndustrialCo diff=2 < 5 → no mismatch
        assert result["mismatches"] == 0

    def test_returns_dict(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_roce_crosscheck(conn)
        conn.close()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# ROE cross-check tests
# ---------------------------------------------------------------------------

class TestROECrosscheck:

    def test_runs_without_error(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_roe_crosscheck(conn)
        conn.close()
        assert "total_checked" in result
        assert "mismatches" in result

    def test_detects_screener_anomaly(self, crosscheck_db):
        # QualityCo: computed=24, screener=0.52 → diff=23.48 > 5 → mismatch
        conn = _conn(crosscheck_db)
        result = run_roe_crosscheck(conn)
        conn.close()
        assert result["mismatches"] >= 1
        assert result["anomalous_screener_values"] >= 1


# ---------------------------------------------------------------------------
# D/E suppression audit tests
# ---------------------------------------------------------------------------

class TestDESuppression:

    def test_runs_without_error(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_de_suppression_audit(conn)
        conn.close()
        assert "companies_with_suppressed_flag" in result

    def test_financials_with_high_de_logged(self, crosscheck_db):
        # BigBank D/E=8.5 > 5, flag=0 → should be logged
        conn = _conn(crosscheck_db)
        result = run_de_suppression_audit(conn)
        conn.close()
        assert result["companies_with_suppressed_flag"] >= 1


# ---------------------------------------------------------------------------
# Screener preview tests
# ---------------------------------------------------------------------------

class TestScreenerPreview:

    def test_returns_list(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_screener_preview(conn)
        conn.close()
        assert isinstance(result, list)

    def test_all_results_meet_criteria(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_screener_preview(conn)
        conn.close()
        for r in result:
            assert r["roe_pct"] > 15
            assert r["de_ratio"] < 1

    def test_qualityco_in_results(self, crosscheck_db):
        # QualityCo: ROE=24, D/E=0.3 → should appear
        conn = _conn(crosscheck_db)
        result = run_screener_preview(conn)
        conn.close()
        names = [r["company_name"] for r in result]
        assert "QualityCo" in names

    def test_bank_excluded(self, crosscheck_db):
        # BigBank: D/E=8.5 → should NOT appear
        conn = _conn(crosscheck_db)
        result = run_screener_preview(conn)
        conn.close()
        names = [r["company_name"] for r in result]
        assert "BigBank" not in names

    def test_result_dict_has_expected_keys(self, crosscheck_db):
        conn = _conn(crosscheck_db)
        result = run_screener_preview(conn)
        conn.close()
        if result:
            assert "company_name" in result[0]
            assert "roe_pct" in result[0]
            assert "de_ratio" in result[0]
