"""
tests/kpi/test_radar.py
========================
Tests for src/analytics/radar.py

Uses in-memory SQLite + tmp_path for PNG output.
Does NOT assert pixel content — asserts file existence,
chart count, and helper function behaviour.
"""

import os
import sqlite3
import pytest
import pandas as pd
from pathlib import Path

from src.analytics.radar import (
    RadarChartGenerator,
    _radar_plot,
    _standalone_bar_chart,
    load_peer_percentiles,
    RADAR_AXES,
)


# ---------------------------------------------------------------------------
# Fixture DB
# ---------------------------------------------------------------------------

@pytest.fixture
def radar_db(tmp_path):
    db_path = str(tmp_path / "radar_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

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

    # 3 companies in Industrials, 1 with no sector
    conn.executemany("INSERT INTO companies (id, company_name) VALUES (?,?)", [
        (1, "AlphaCo"), (2, "BetaCo"), (3, "GammaCo"), (4, "NoPeerCo"),
    ])
    conn.executemany(
        "INSERT INTO sectors (company_id, broad_sector, sub_sector) VALUES (?,?,?)", [
            (1, "Industrials", "Manufacturing"),
            (2, "Industrials", "Manufacturing"),
            (3, "Industrials", "Manufacturing"),
            (4, "Unknown",     "Unknown"),
        ]
    )
    conn.executemany(
        """INSERT INTO financial_ratios
           (company_id, year, return_on_equity_pct, roce_pct, net_profit_margin_pct,
            debt_to_equity, free_cash_flow_cr, pat_cagr_5yr, revenue_cagr_5yr,
            eps_cagr_5yr, interest_coverage, asset_turnover, composite_quality_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (1, 2023, 22.0, 18.0, 12.0, 0.3,  500.0, 16.0, 14.0, 15.0, 5.0, 1.2, 85.0),
            (2, 2023, 15.0, 12.0,  8.0, 0.8,  300.0, 10.0,  9.0, 10.0, 3.0, 0.9, 65.0),
            (3, 2023,  8.0,  6.0,  4.0, 2.0,  100.0,  5.0,  6.0,  5.0, 1.5, 0.6, 40.0),
            (4, 2023, 10.0,  8.0,  6.0, 1.0,  200.0,  8.0,  7.0,  8.0, 2.0, 0.8, 50.0),
        ]
    )

    # Seed peer_percentiles for 3 companies × 8 metrics
    metrics = ["ROE", "ROCE", "Net Profit Margin", "D/E", "FCF",
               "PAT CAGR 5yr", "Revenue CAGR 5yr", "Asset Turnover"]
    ranks = {
        1: [100.0, 100.0, 100.0,  100.0, 100.0, 100.0, 100.0, 100.0],
        2: [ 50.0,  50.0,  50.0,   50.0,  50.0,  50.0,  50.0,  50.0],
        3: [  0.0,   0.0,   0.0,    0.0,   0.0,   0.0,   0.0,   0.0],
    }
    for cid, r_list in ranks.items():
        for metric, rank in zip(metrics, r_list):
            conn.execute(
                """INSERT OR REPLACE INTO peer_percentiles
                   (company_id, peer_group_name, metric, value, percentile_rank, year)
                   VALUES (?,?,?,?,?,?)""",
                (cid, "Industrials — Manufacturing", metric, rank, rank, 2023)
            )
    conn.commit()
    conn.close()
    return db_path


def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# load_peer_percentiles tests
# ---------------------------------------------------------------------------

class TestLoadPeerPercentiles:

    def test_returns_dataframe(self, radar_db):
        conn = _conn(radar_db)
        df = load_peer_percentiles(conn, "Industrials — Manufacturing")
        conn.close()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_returns_empty_for_unknown_group(self, radar_db):
        conn = _conn(radar_db)
        df = load_peer_percentiles(conn, "Nonexistent Group")
        conn.close()
        assert df.empty

    def test_has_company_name_column(self, radar_db):
        conn = _conn(radar_db)
        df = load_peer_percentiles(conn, "Industrials — Manufacturing")
        conn.close()
        assert "company_name" in df.columns


# ---------------------------------------------------------------------------
# _radar_plot tests
# ---------------------------------------------------------------------------

class TestRadarPlot:

    def test_generates_png(self, tmp_path):
        values   = [80.0, 70.0, 60.0, 50.0, 90.0, 75.0, 65.0, 85.0]
        peer_avg = [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
        out = tmp_path / "test_radar.png"
        _radar_plot(values, peer_avg, RADAR_AXES, "TestCo", out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_handles_zero_values(self, tmp_path):
        values   = [0.0] * 8
        peer_avg = [50.0] * 8
        out = tmp_path / "zero_radar.png"
        _radar_plot(values, peer_avg, RADAR_AXES, "ZeroCo", out)
        assert out.exists()

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "subdir" / "nested" / "test.png"
        _radar_plot([50.0]*8, [50.0]*8, RADAR_AXES, "TestCo", out)
        assert out.exists()


# ---------------------------------------------------------------------------
# _standalone_bar_chart tests
# ---------------------------------------------------------------------------

class TestStandaloneBarChart:

    def test_generates_png(self, tmp_path):
        vals = {"ROE": 15.0, "ROCE": 12.0, "NPM": 10.0, "D/E": 0.5,
                "FCF": 300.0, "PAT CAGR 5yr": 12.0, "Rev CAGR 5yr": 10.0,
                "Composite Score": 65.0}
        avg  = {k: v * 0.8 for k, v in vals.items()}
        out  = tmp_path / "standalone.png"
        _standalone_bar_chart("NoPeerCo", vals, avg, out)
        assert out.exists()
        assert out.stat().st_size > 0


# ---------------------------------------------------------------------------
# RadarChartGenerator tests
# ---------------------------------------------------------------------------

class TestRadarChartGenerator:

    def test_generate_for_group_creates_pngs(self, radar_db, tmp_path):
        conn = _conn(radar_db)
        gen = RadarChartGenerator(conn, output_dir=tmp_path / "charts")
        count = gen.generate_for_group("Industrials — Manufacturing")
        conn.close()
        assert count == 3
        pngs = list((tmp_path / "charts").glob("*.png"))
        assert len(pngs) == 3

    def test_generate_for_unknown_group_returns_zero(self, radar_db, tmp_path):
        conn = _conn(radar_db)
        gen = RadarChartGenerator(conn, output_dir=tmp_path / "charts")
        count = gen.generate_for_group("Nonexistent Group")
        conn.close()
        assert count == 0

    def test_filenames_use_safe_format(self, radar_db, tmp_path):
        conn = _conn(radar_db)
        gen = RadarChartGenerator(conn, output_dir=tmp_path / "charts")
        gen.generate_for_group("Industrials — Manufacturing")
        conn.close()
        pngs = list((tmp_path / "charts").glob("*_radar.png"))
        assert len(pngs) == 3
        for p in pngs:
            assert " " not in p.name

    def test_run_all_returns_summary(self, radar_db, tmp_path):
        conn = _conn(radar_db)
        gen = RadarChartGenerator(conn, output_dir=tmp_path / "charts")
        summary = gen.run_all()
        conn.close()
        assert "charts_generated" in summary
        assert "peer_groups_processed" in summary
        assert summary["charts_generated"] >= 3

    def test_safe_filename_no_spaces(self, radar_db, tmp_path):
        conn = _conn(radar_db)
        gen = RadarChartGenerator(conn, output_dir=tmp_path)
        assert " " not in gen._safe_filename("Alpha Beta Co")
        conn.close()
