"""
tests/kpi/test_peer.py
=======================
Unit and integration tests for src/analytics/peer.py

Coverage:
  - assign_peer_group() — all 11 groups + NO_PEER_GROUP
  - percent_rank()      — normal, invert, NaN, single value, ties
  - PeerEngine.compute_percentiles() — correct ranks per group
  - PeerEngine.insert_percentiles()  — rows written, idempotent
  - No peer group companies — logged, not raised
  - D/E inversion — lower D/E gets higher percentile
"""

import sqlite3
import pytest
import pandas as pd

from src.analytics.peer import (
    assign_peer_group,
    percent_rank,
    PeerEngine,
    NO_PEER_GROUP,
    PEER_METRICS,
)


# ---------------------------------------------------------------------------
# assign_peer_group tests
# ---------------------------------------------------------------------------

class TestAssignPeerGroup:

    def test_financials_banking(self):
        assert assign_peer_group("Financials", "Banking") == "Financials — Banking"

    def test_financials_nbfc(self):
        assert assign_peer_group("Financials", "NBFC") == "Financials — NBFC"

    def test_financials_insurance(self):
        assert assign_peer_group("Financials", "Insurance") == "Financials — Insurance"

    def test_financials_default_nbfc(self):
        # Unknown sub-sector under Financials → NBFC
        assert assign_peer_group("Financials", "") == "Financials — NBFC"

    def test_technology(self):
        assert assign_peer_group("Technology", "IT Services") == "Technology — IT Services"

    def test_consumer_fmcg(self):
        assert assign_peer_group("Consumer", "FMCG") == "Consumer — FMCG"

    def test_consumer_retail(self):
        assert assign_peer_group("Consumer", "Retail") == "Consumer — Retail"

    def test_industrials_manufacturing(self):
        assert assign_peer_group("Industrials", "Manufacturing") == "Industrials — Manufacturing"

    def test_industrials_infrastructure(self):
        assert assign_peer_group("Industrials", "Infrastructure") == "Industrials — Infrastructure"

    def test_energy(self):
        assert assign_peer_group("Energy", "") == "Energy"

    def test_healthcare(self):
        assert assign_peer_group("Healthcare", "Pharma") == "Healthcare"

    def test_materials(self):
        assert assign_peer_group("Materials", "Metals") == "Materials"

    def test_unknown_returns_no_peer(self):
        assert assign_peer_group("Unknown", "Unknown") == NO_PEER_GROUP

    def test_none_inputs(self):
        assert assign_peer_group(None, None) == NO_PEER_GROUP

    def test_case_insensitive(self):
        assert assign_peer_group("financials", "banking") == "Financials — Banking"


# ---------------------------------------------------------------------------
# percent_rank tests
# ---------------------------------------------------------------------------

class TestPercentRank:

    def test_five_values_ascending(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = percent_rank(s)
        assert result.tolist() == [0.0, 25.0, 50.0, 75.0, 100.0]

    def test_inverted(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = percent_rank(s, invert=True)
        assert result.tolist() == [100.0, 75.0, 50.0, 25.0, 0.0]

    def test_nan_gets_nan_rank(self):
        s = pd.Series([10.0, None, 30.0])
        result = percent_rank(s)
        assert pd.isna(result.iloc[1])

    def test_single_value_gets_50(self):
        s = pd.Series([42.0])
        result = percent_rank(s)
        assert result.iloc[0] == 50.0

    def test_all_nan_returns_nan(self):
        s = pd.Series([None, None, None], dtype=float)
        result = percent_rank(s)
        assert result.isna().all()

    def test_tied_values_same_rank(self):
        s = pd.Series([10.0, 10.0, 20.0])
        result = percent_rank(s)
        # Both 10s have 0 values less than them → rank = 0
        assert result.iloc[0] == result.iloc[1]

    def test_de_inversion_lower_is_higher(self):
        # D/E: lower value should get higher percentile
        de = pd.Series([0.2, 0.5, 1.0, 2.0, 5.0])
        ranks = percent_rank(de, invert=True)
        assert ranks.iloc[0] > ranks.iloc[-1]   # lowest D/E ranks highest

    def test_output_between_0_and_100(self):
        s = pd.Series([5.0, 15.0, 25.0, 35.0])
        result = percent_rank(s)
        assert result.between(0, 100).all()


# ---------------------------------------------------------------------------
# PeerEngine fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def peer_db(tmp_path):
    db_path = str(tmp_path / "peer_test.db")
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
    """)

    # 6 companies: 3 Industrials, 2 Technology, 1 No-peer
    companies = [
        (1, "IndustrialA"), (2, "IndustrialB"), (3, "IndustrialC"),
        (4, "TechA"),       (5, "TechB"),       (6, "NoSectorCo"),
    ]
    conn.executemany("INSERT INTO companies (id, company_name) VALUES (?,?)", companies)

    sectors = [
        (1, "Industrials", "Manufacturing"),
        (2, "Industrials", "Manufacturing"),
        (3, "Industrials", "Manufacturing"),
        (4, "Technology",  "IT Services"),
        (5, "Technology",  "IT Services"),
        (6, "Unknown",     "Unknown"),
    ]
    conn.executemany(
        "INSERT INTO sectors (company_id, broad_sector, sub_sector) VALUES (?,?,?)", sectors
    )

    ratios = [
        (1, 2023, 22.0, 18.0, 12.0, 0.3, 500.0, 16.0, 14.0, 15.0, 5.0, 1.2),
        (2, 2023, 15.0, 12.0,  8.0, 0.8, 300.0, 10.0,  9.0, 10.0, 3.0, 0.9),
        (3, 2023,  8.0,  6.0,  4.0, 2.0, 100.0,  5.0,  6.0,  5.0, 1.5, 0.6),
        (4, 2023, 25.0, 22.0, 15.0, 0.2, 600.0, 20.0, 18.0, 20.0, 8.0, 1.5),
        (5, 2023, 18.0, 15.0, 10.0, 0.5, 400.0, 14.0, 12.0, 14.0, 5.0, 1.1),
        (6, 2023, 10.0,  8.0,  6.0, 1.0, 200.0,  8.0,  7.0,  8.0, 2.0, 0.8),
    ]
    conn.executemany(
        """INSERT INTO financial_ratios
           (company_id, year, return_on_equity_pct, roce_pct, net_profit_margin_pct,
            debt_to_equity, free_cash_flow_cr, pat_cagr_5yr, revenue_cagr_5yr,
            eps_cagr_5yr, interest_coverage, asset_turnover)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ratios
    )
    conn.commit()
    return db_path


# ---------------------------------------------------------------------------
# PeerEngine tests
# ---------------------------------------------------------------------------

class TestPeerEngine:

    def _engine(self, peer_db):
        conn = sqlite3.connect(peer_db)
        conn.row_factory = sqlite3.Row
        return PeerEngine(conn)

    def test_schema_creates_table(self, peer_db):
        engine = self._engine(peer_db)
        engine.apply_schema()
        row = engine.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='peer_percentiles'"
        ).fetchone()
        assert row is not None

    def test_load_data_returns_dataframe(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6

    def test_peer_group_assigned(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        ind = df[df["company_name"] == "IndustrialA"]["peer_group_name"].iloc[0]
        assert ind == "Industrials — Manufacturing"

    def test_no_peer_assigned_for_unknown(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        no_peer = df[df["company_name"] == "NoSectorCo"]["peer_group_name"].iloc[0]
        assert no_peer == NO_PEER_GROUP

    def test_compute_percentiles_returns_dataframe(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        result = engine.compute_percentiles(df)
        assert isinstance(result, pd.DataFrame)
        assert "percentile_rank" in result.columns

    def test_compute_percentiles_excludes_no_peer(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        result = engine.compute_percentiles(df)
        assert NO_PEER_GROUP not in result["peer_group_name"].values

    def test_de_percentile_inverted(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        result = engine.compute_percentiles(df)
        de_rows = result[
            (result["metric"] == "D/E") &
            (result["peer_group_name"] == "Industrials — Manufacturing")
        ].sort_values("value")
        # Lowest D/E (IndustrialA=0.3) should have highest percentile
        assert de_rows.iloc[0]["percentile_rank"] > de_rows.iloc[-1]["percentile_rank"]

    def test_top_company_ranks_100(self, peer_db):
        engine = self._engine(peer_db)
        df = engine.load_data()
        result = engine.compute_percentiles(df)
        roe_ind = result[
            (result["metric"] == "ROE") &
            (result["peer_group_name"] == "Industrials — Manufacturing")
        ]
        assert roe_ind["percentile_rank"].max() == 100.0

    def test_insert_returns_row_count(self, peer_db):
        engine = self._engine(peer_db)
        engine.apply_schema()
        df = engine.load_data()
        percentile_df = engine.compute_percentiles(df)
        count = engine.insert_percentiles(percentile_df)
        assert count > 0

    def test_insert_idempotent(self, peer_db):
        engine = self._engine(peer_db)
        engine.apply_schema()
        df = engine.load_data()
        percentile_df = engine.compute_percentiles(df)
        engine.insert_percentiles(percentile_df)
        engine.insert_percentiles(percentile_df)  # second run — no error
        count = engine.conn.execute(
            "SELECT COUNT(*) FROM peer_percentiles"
        ).fetchone()[0]
        assert count == len(percentile_df)

    def test_run_returns_summary(self, peer_db):
        engine = self._engine(peer_db)
        summary = engine.run()
        assert "companies_loaded" in summary
        assert "peer_groups_found" in summary
        assert "rows_inserted" in summary
        assert summary["rows_inserted"] > 0

    def test_10_metrics_per_company_per_group(self, peer_db):
        engine = self._engine(peer_db)
        summary = engine.run()
        # 3 Industrials × 10 metrics + 2 Technology × 10 metrics = 50 rows
        assert summary["rows_inserted"] == 50

    def test_no_peer_count_correct(self, peer_db):
        engine = self._engine(peer_db)
        summary = engine.run()
        assert summary["no_peer_assigned"] == 1
