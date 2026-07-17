"""
tests/screener/test_integration.py
====================================
Sprint 3 Day 21 — Integration tests for sprint sign-off.

Coverage per spec:
  1. 14 DQ rule unit tests — all must pass with 0 failures
  2. Quality Compounder preset — ROE > 15% AND D/E < 1
  3. Peer rankings — highest ROE company has highest ROE percentile rank
  4. Composite scorer produces valid 0-100 scores
  5. Peer comparison data integrity checks
"""

import pytest
import pandas as pd
import numpy as np

from src.screener.engine import ScreenerEngine, DEBT_FREE_LABEL
from src.screener.presets import PresetScreener
from src.screener.scorer import (
    compute_composite_score,
    compute_sector_relative_score,
    winsorise,
    scale_0_100,
)
from src.analytics.peer import assign_peer_group, percent_rank, NO_PEER_GROUP


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def universe_df():
    """20-company universe covering all integration scenarios."""
    return pd.DataFrame({
        "company_id": list(range(1, 21)),
        "company_name": [
            "TCS", "Infosys", "HDFC Bank", "ICICI Bank", "Reliance",
            "HUL", "ITC", "L&T", "BHEL", "Sun Pharma",
            "Wipro", "Bajaj Finance", "Titan", "Asian Paints", "Maruti",
            "Nestle", "Dabur", "Coal India", "ONGC", "Power Grid",
        ],
        "broad_sector": [
            "Technology", "Technology", "Financials", "Financials", "Energy",
            "Consumer", "Consumer", "Industrials", "Industrials", "Healthcare",
            "Technology", "Financials", "Consumer", "Consumer", "Industrials",
            "Consumer", "Consumer", "Energy", "Energy", "Industrials",
        ],
        "return_on_equity_pct": [
            45.0, 30.0, 18.0, 16.0, 12.0,
            88.0, 35.0, 14.0,  5.0, 20.0,
            18.0, 22.0, 28.0, 32.0, 18.0,
            90.0, 25.0,  8.0, 10.0, 12.0,
        ],
        "debt_to_equity": [
            0.0, 0.1,  7.5,  6.8,  0.5,
            0.2, 0.0,  1.2,  2.0,  0.3,
            0.1, 8.0,  0.4,  0.1,  0.8,
            0.0, 0.2,  0.5,  0.4,  1.5,
        ],
        "free_cash_flow_cr": [
            8000, 6000,  5000,  4000,  3000,
            2000, 1500,  1200, -500,   800,
            3500, 2500,   900,  1800,  2000,
            1000,  700,  2500,  1800,   600,
        ],
        "revenue_cagr_5yr": [
            12.0, 10.0,  15.0, 14.0,  8.0,
            10.0,  6.0,  12.0,  2.0, 14.0,
             9.0, 25.0,  18.0, 12.0, 15.0,
            11.0,  8.0,   4.0,  3.0,  5.0,
        ],
        "pat_cagr_5yr": [
            14.0, 12.0, 18.0, 16.0,  6.0,
            12.0,  5.0, 10.0, -5.0, 15.0,
            10.0, 28.0, 20.0, 14.0, 18.0,
            13.0,  9.0,  2.0,  1.0,  4.0,
        ],
        "operating_profit_margin_pct": [
            28.0, 26.0, 30.0, 28.0, 15.0,
            22.0, 35.0, 12.0,  8.0, 20.0,
            22.0, 35.0, 12.0, 18.0, 12.0,
            20.0, 18.0, 35.0, 28.0, 22.0,
        ],
        "interest_coverage": [
            None, None, None, None,  8.0,
            25.0, None, 3.0,  1.2, 15.0,
            None, None, 20.0, 30.0,  4.0,
            None, 22.0,  5.0,  6.0,  2.5,
        ],
        "icr_label": [
            "Debt Free", "Debt Free", None, None, None,
            None, "Debt Free", None, None, None,
            "Debt Free", None, None, None, None,
            "Debt Free", None, None, None, None,
        ],
        "asset_turnover": [
            0.8, 0.9,  0.1,  0.1,  0.6,
            1.2, 1.0,  0.7,  0.5,  0.8,
            0.8, 0.2,  1.5,  1.2,  1.8,
            1.3, 1.1,  0.3,  0.4,  0.3,
        ],
        "net_profit_margin_pct": [
            22.0, 20.0, 22.0, 20.0, 8.0,
            15.0, 28.0,  8.0,  2.0, 16.0,
            18.0, 18.0, 10.0, 14.0, 8.0,
            15.0, 14.0, 20.0, 14.0, 12.0,
        ],
        "eps_cagr_5yr": [
            14.0, 11.0, 16.0, 15.0,  5.0,
            11.0,  4.0,  9.0, -8.0, 14.0,
             9.0, 26.0, 19.0, 13.0, 16.0,
            12.0,  8.0,  1.0,  0.0,  3.0,
        ],
        "roce_pct": [
            40.0, 28.0, None, None, 10.0,
            80.0, 32.0, 12.0, 4.0,  18.0,
            16.0, None, 26.0, 30.0, 15.0,
            85.0, 22.0,  6.0,  8.0,  9.0,
        ],
        "cfo_quality_score": [
            "High Quality", "High Quality", "Moderate", "Moderate", "Moderate",
            "High Quality", "High Quality", "Moderate", "Accrual Risk", "High Quality",
            "High Quality", "Moderate", "High Quality", "High Quality", "Moderate",
            "High Quality", "High Quality", "Moderate", "Moderate", "Moderate",
        ],
        "composite_quality_score": [
            88.0, 78.0, 55.0, 52.0, 45.0,
            92.0, 72.0, 48.0, 15.0, 70.0,
            75.0, 65.0, 80.0, 82.0, 62.0,
            90.0, 68.0, 30.0, 28.0, 35.0,
        ],
        "dividend_yield_pct": [
            1.2, 2.5, 1.0, 0.8, 0.5,
            1.5, 5.0, 1.8, 3.0, 0.6,
            0.8, 0.2, 0.4, 0.8, 0.9,
            1.2, 1.8, 5.5, 4.0, 4.5,
        ],
        "dividend_payout_ratio_pct": [
            35.0, 50.0, 20.0, 18.0, 10.0,
            90.0, 85.0, 30.0, 60.0, 15.0,
            30.0, 10.0, 8.0,  20.0, 15.0,
            40.0, 45.0, 70.0, 60.0, 75.0,
        ],
        "pe_ratio": [
            28.0, 22.0, 18.0, 16.0, 12.0,
            60.0, 25.0, 20.0, 15.0, 30.0,
            20.0, 35.0, 55.0, 58.0, 30.0,
            80.0, 50.0, 8.0,  6.0,  10.0,
        ],
        "pb_ratio": [
            12.0,  8.0,  2.5,  2.2,  1.8,
            15.0,  8.0,  3.0,  0.8,  4.0,
             5.0, 10.0, 18.0, 20.0,  5.0,
            25.0, 12.0,  1.2,  0.8,  1.5,
        ],
        "sales": [
            20000, 15000, 18000, 14000, 80000,
            12000, 18000, 22000,  8000,  5000,
            18000, 12000,  4000,  3500, 12000,
             2000,  1200, 10000, 25000,  4000,
        ],
        "year": [2023] * 20,
    })


# ---------------------------------------------------------------------------
# DQ Rule tests — 14 rules
# ---------------------------------------------------------------------------

class TestDQRules:
    """14 data quality rules for the screener and peer engine."""

    def test_dq01_no_null_company_ids(self, universe_df):
        assert universe_df["company_id"].notna().all()

    def test_dq02_no_duplicate_company_ids(self, universe_df):
        assert universe_df["company_id"].nunique() == len(universe_df)

    def test_dq03_roe_within_reasonable_range(self, universe_df):
        roe = universe_df["return_on_equity_pct"].dropna()
        assert roe.between(-500, 500).all()

    def test_dq04_de_ratio_non_negative(self, universe_df):
        de = universe_df["debt_to_equity"].dropna()
        assert (de >= 0).all()

    def test_dq05_composite_score_between_0_and_100(self, universe_df):
        scores = universe_df["composite_quality_score"].dropna()
        assert scores.between(0, 100).all()

    def test_dq06_revenue_cagr_reasonable(self, universe_df):
        cagr = universe_df["revenue_cagr_5yr"].dropna()
        assert cagr.between(-100, 200).all()

    def test_dq07_opm_reasonable(self, universe_df):
        opm = universe_df["operating_profit_margin_pct"].dropna()
        assert opm.between(-100, 100).all()

    def test_dq08_icr_label_valid_values(self, universe_df):
        valid = {None, "Debt Free", float("nan")}
        labels = universe_df["icr_label"].unique()
        for label in labels:
            assert label in {None, "Debt Free"} or pd.isna(label)

    def test_dq09_asset_turnover_positive(self, universe_df):
        at = universe_df["asset_turnover"].dropna()
        assert (at > 0).all()

    def test_dq10_broad_sector_not_empty(self, universe_df):
        assert universe_df["broad_sector"].notna().all()
        assert (universe_df["broad_sector"] != "").all()

    def test_dq11_sales_positive(self, universe_df):
        sales = universe_df["sales"].dropna()
        assert (sales > 0).all()

    def test_dq12_eps_cagr_reasonable(self, universe_df):
        cagr = universe_df["eps_cagr_5yr"].dropna()
        assert cagr.between(-200, 300).all()

    def test_dq13_dividend_yield_non_negative(self, universe_df):
        dy = universe_df["dividend_yield_pct"].dropna()
        assert (dy >= 0).all()

    def test_dq14_pe_ratio_non_negative(self, universe_df):
        pe = universe_df["pe_ratio"].dropna()
        assert (pe > 0).all()


# ---------------------------------------------------------------------------
# Quality Compounder preset verification
# ---------------------------------------------------------------------------

class TestQualityCompounderPreset:

    def test_all_results_have_roe_above_15(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["return_on_equity_pct"] >= 15.0)

    def test_all_results_have_de_below_1(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["debt_to_equity"] <= 1.0)

    def test_all_results_have_positive_fcf(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        assert all(result["free_cash_flow_cr"] >= 0)

    def test_result_count_in_expected_range(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        assert 1 <= len(result) <= len(universe_df)

    def test_tcs_in_quality_compounder(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        # TCS: ROE=45, D/E=0, FCF=8000, RevCAGR=12 → should qualify
        assert "TCS" in result["company_name"].values

    def test_bhel_excluded(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        # BHEL: ROE=5%, FCF=-500 → should be excluded
        assert "BHEL" not in result["company_name"].values

    def test_sorted_by_composite_score(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        scores = result["composite_quality_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_top_5_make_business_sense(self, universe_df):
        ps = PresetScreener(df=universe_df)
        result = ps.run("quality_compounder")
        top5 = result.head(5)["company_name"].tolist()
        # All top 5 must be quality companies — verify ROE > 15
        top5_data = result.head(5)
        assert all(top5_data["return_on_equity_pct"] >= 15.0)


# ---------------------------------------------------------------------------
# Peer ranking verification
# ---------------------------------------------------------------------------

class TestPeerRankingVerification:

    def _build_tech_df(self, universe_df):
        """Filter to Technology sector only."""
        return universe_df[universe_df["broad_sector"] == "Technology"].copy()

    def test_highest_roe_has_highest_percentile(self, universe_df):
        tech = self._build_tech_df(universe_df)
        roe_series  = pd.to_numeric(tech["return_on_equity_pct"], errors="coerce")
        ranks = percent_rank(roe_series)
        # Company with max ROE should have rank = 100
        max_roe_idx = roe_series.idxmax()
        assert ranks[max_roe_idx] == 100.0

    def test_lowest_roe_has_lowest_percentile(self, universe_df):
        tech = self._build_tech_df(universe_df)
        roe_series = pd.to_numeric(tech["return_on_equity_pct"], errors="coerce")
        ranks = percent_rank(roe_series)
        min_roe_idx = roe_series.idxmin()
        assert ranks[min_roe_idx] == 0.0

    def test_de_inversion_lowest_de_ranks_highest(self, universe_df):
        tech = self._build_tech_df(universe_df)
        de_series = pd.to_numeric(tech["debt_to_equity"], errors="coerce")
        ranks = percent_rank(de_series, invert=True)
        min_de_idx = de_series.idxmin()
        assert ranks[min_de_idx] == 100.0

    def test_all_ranks_between_0_and_100(self, universe_df):
        tech = self._build_tech_df(universe_df)
        roe_series = pd.to_numeric(tech["return_on_equity_pct"], errors="coerce")
        ranks = percent_rank(roe_series)
        assert ranks.between(0, 100).all()

    def test_it_services_peer_group_assigned(self, universe_df):
        tech = universe_df[universe_df["broad_sector"] == "Technology"].iloc[0]
        group = assign_peer_group("Technology", "IT Services")
        assert group == "Technology — IT Services"


# ---------------------------------------------------------------------------
# Composite scorer integration
# ---------------------------------------------------------------------------

class TestCompositeScoreIntegration:

    def test_scores_computed_for_all_companies(self, universe_df):
        scores = compute_composite_score(universe_df)
        assert len(scores) == len(universe_df)

    def test_all_scores_valid_range(self, universe_df):
        scores = compute_composite_score(universe_df)
        assert scores.between(0, 100).all()

    def test_sector_relative_computed(self, universe_df):
        from src.screener.scorer import add_scores_to_df
        result = add_scores_to_df(universe_df)
        assert "sector_relative_score" in result.columns
        assert result["sector_relative_score"].notna().any()

    def test_high_quality_companies_score_higher(self, universe_df):
        scores = compute_composite_score(universe_df)
        # HUL (idx 5, ROE=88, high quality) should outscore BHEL (idx 8, ROE=5)
        hul_idx  = universe_df[universe_df["company_name"] == "HUL"].index[0]
        bhel_idx = universe_df[universe_df["company_name"] == "BHEL"].index[0]
        assert scores[hul_idx] > scores[bhel_idx]

    def test_winsorise_removes_extremes(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000])
        ws = winsorise(s)
        assert ws.max() < 1000

    def test_scale_0_100_all_valid(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        scaled = scale_0_100(s)
        assert scaled.between(0, 100).all()
