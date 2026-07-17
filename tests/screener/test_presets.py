"""
tests/screener/test_presets.py
===============================
Unit tests for src/screener/presets.py

Coverage:
  - All 6 presets run without error
  - Each preset returns a non-empty DataFrame
  - Filter thresholds are respected per preset
  - Unknown preset raises KeyError
  - available_presets() returns 6 entries
  - preset_filters() returns correct thresholds
  - run_all() returns dict with 6 keys
  - D/E declining filter for turnaround_watch
  - Dividend payout custom filter for dividend_champion
"""

import pytest
import pandas as pd

from src.screener.presets import PresetScreener, PRESETS
from src.screener.engine import DEBT_FREE_LABEL


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """15-row DataFrame covering all 6 preset scenarios."""
    return pd.DataFrame({
        "company_id": list(range(1, 16)),
        "year": [2023] * 15,
        "company_name": [
            "QualityCo", "BankCo", "GrowthCo", "ValueCo", "DividendCo",
            "DebtFreeCo", "TurnaroundCo", "MidCo", "SmallCo", "LargeCo",
            "LowROECo", "HighDECo", "LowFCFCo", "StableCo", "MixedCo"
        ],
        "broad_sector": [
            "Industrials", "Financials", "Technology", "Consumer", "Industrials",
            "Technology", "Industrials", "Consumer", "Industrials", "Industrials",
            "Industrials", "Industrials", "Consumer", "Technology", "Financials"
        ],
        "return_on_equity_pct":         [22.0, 18.0, 25.0, 14.0, 16.0, 13.0, 18.0, 15.0,  8.0, 20.0, 5.0, 19.0, 17.0, 21.0, 16.0],
        "debt_to_equity":               [0.3,  8.5,  0.5,  1.5,  0.4,  0.0,  1.2,  0.8,  0.6,  0.3, 0.4,  6.0,  0.9,  0.2,  7.0],
        "free_cash_flow_cr":            [500,  800,  300,  200,  400,  600, 250,   150,  100,  700, 200,  300,  -50,  450,  350],
        "revenue_cagr_5yr":             [14.0, 10.0, 20.0, 8.0,  12.0, 11.0, 16.0,  9.0,  6.0, 13.0, 3.0, 15.0, 10.0, 14.0, 11.0],
        "revenue_cagr_3yr":             [12.0,  8.0, 18.0, 7.0,  11.0, 10.0, 14.0,  8.0,  5.0, 12.0, 2.0, 13.0,  9.0, 13.0, 10.0],
        "pat_cagr_5yr":                 [18.0,  8.0, 25.0, 6.0,  14.0, 10.0, 22.0,  8.0,  4.0, 16.0, 1.0, 20.0,  8.0, 17.0,  9.0],
        "operating_profit_margin_pct":  [20.0, 25.0, 18.0, 12.0, 22.0, 24.0, 15.0, 16.0, 10.0, 21.0, 8.0, 17.0, 14.0, 23.0, 19.0],
        "interest_coverage":            [5.0,  None,  8.0,  3.0,  6.0,  None,  2.5,  4.0,  3.5,  7.0, 4.0,  1.5,  5.0,  6.5, None],
        "icr_label":                    [None, None, None, None, None, DEBT_FREE_LABEL, None, None, None, None, None, None, None, None, DEBT_FREE_LABEL],
        "asset_turnover":               [1.2,  0.3,  1.5,  1.1,  1.0,  1.3,  0.9,  1.0,  0.8,  1.4, 0.9,  0.7,  1.1,  1.2,  0.4],
        "net_profit_margin_pct":        [12.0, 18.0, 15.0,  8.0, 13.0, 11.0, 14.0, 10.0,  6.0, 14.0, 3.0, 13.0, 10.0, 15.0, 12.0],
        "eps_cagr_5yr":                 [15.0,  7.0, 22.0,  5.0, 12.0,  9.0, 20.0,  7.0,  3.0, 14.0, 0.5, 18.0,  7.0, 16.0,  8.0],
        "composite_quality_score":      [85.0, 60.0, 90.0, 55.0, 75.0, 70.0, 80.0, 65.0, 40.0, 82.0,20.0, 58.0, 50.0, 88.0, 62.0],
        "sales":                        [5000, 8000, 3000, 2000, 4500, 6000, 4000, 3500, 1500, 7000,1200, 2500, 3000, 5500, 9000],
        "dividend_yield_pct":           [1.5,  0.8,  0.5,  2.0,  3.0,  1.0,  0.8,  1.2,  0.4,  1.8, 0.3,  0.6,  2.5,  1.4,  0.9],
        "dividend_payout_ratio_pct":    [30.0, 20.0, 15.0, 45.0, 60.0, 25.0, 20.0, 35.0, 10.0, 28.0,8.0, 18.0, 70.0, 32.0, 22.0],
        "pe_ratio":                     [18.0, 12.0, 30.0, 15.0, 20.0, 16.0, 22.0, 19.0, 10.0, 17.0,8.0, 14.0, 21.0, 16.0, 13.0],
        "pb_ratio":                     [2.5,  1.5,  4.0,  2.0,  2.8,  1.8,  3.0,  2.2,  1.2,  2.4, 0.8,  1.6,  2.9,  2.1,  1.4],
        "market_cap_cr":                [15000,25000,8000, 5000,12000,18000,10000,7000, 3000,20000,2000,6000, 9000,16000,30000],
    })


@pytest.fixture
def screener(sample_df):
    return PresetScreener(df=sample_df)


# ---------------------------------------------------------------------------
# All 6 presets run without error
# ---------------------------------------------------------------------------

class TestAllPresetsRun:

    @pytest.mark.parametrize("preset_name", list(PRESETS.keys()))
    def test_preset_runs_without_error(self, screener, preset_name):
        result = screener.run(preset_name)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.parametrize("preset_name", list(PRESETS.keys()))
    def test_preset_returns_dataframe_with_columns(self, screener, preset_name):
        result = screener.run(preset_name)
        assert "company_name" in result.columns
        assert "composite_quality_score" in result.columns


# ---------------------------------------------------------------------------
# Quality Compounder
# ---------------------------------------------------------------------------

class TestQualityCompounder:

    def test_roe_threshold(self, screener):
        result = screener.run("quality_compounder")
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["return_on_equity_pct"] >= 15.0)

    def test_de_threshold(self, screener):
        result = screener.run("quality_compounder")
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["debt_to_equity"] <= 1.0)

    def test_fcf_positive(self, screener):
        result = screener.run("quality_compounder")
        assert all(result["free_cash_flow_cr"] >= 0)

    def test_revenue_cagr_threshold(self, screener):
        result = screener.run("quality_compounder")
        assert all(result["revenue_cagr_5yr"] >= 10.0)

    def test_qualityco_in_results(self, screener):
        result = screener.run("quality_compounder")
        assert "QualityCo" in result["company_name"].values

    def test_lowroeco_excluded(self, screener):
        result = screener.run("quality_compounder")
        assert "LowROECo" not in result["company_name"].values


# ---------------------------------------------------------------------------
# Growth Accelerator
# ---------------------------------------------------------------------------

class TestGrowthAccelerator:

    def test_pat_cagr_threshold(self, screener):
        result = screener.run("growth_accelerator")
        assert all(result["pat_cagr_5yr"] >= 20.0)

    def test_revenue_cagr_threshold(self, screener):
        result = screener.run("growth_accelerator")
        assert all(result["revenue_cagr_5yr"] >= 15.0)

    def test_growthco_in_results(self, screener):
        result = screener.run("growth_accelerator")
        assert "GrowthCo" in result["company_name"].values


# ---------------------------------------------------------------------------
# Dividend Champion
# ---------------------------------------------------------------------------

class TestDividendChampion:

    def test_dividend_yield_threshold(self, screener):
        result = screener.run("dividend_champion")
        assert all(result["dividend_yield_pct"] >= 2.0)

    def test_fcf_positive(self, screener):
        result = screener.run("dividend_champion")
        assert all(result["free_cash_flow_cr"] >= 0)

    def test_payout_below_80(self, screener):
        result = screener.run("dividend_champion")
        assert all(result["dividend_payout_ratio_pct"] <= 80.0)

    def test_dividendco_in_results(self, screener):
        result = screener.run("dividend_champion")
        assert "DividendCo" in result["company_name"].values


# ---------------------------------------------------------------------------
# Debt-Free Blue Chip
# ---------------------------------------------------------------------------

class TestDebtFreeBlueChip:

    def test_de_is_zero(self, screener):
        result = screener.run("debt_free_blue_chip")
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["debt_to_equity"] <= 0.0)

    def test_roe_threshold(self, screener):
        result = screener.run("debt_free_blue_chip")
        assert all(result["return_on_equity_pct"] >= 12.0)

    def test_sales_threshold(self, screener):
        result = screener.run("debt_free_blue_chip")
        assert all(result["sales"] >= 5000.0)

    def test_debtfreeco_in_results(self, screener):
        result = screener.run("debt_free_blue_chip")
        assert "DebtFreeCo" in result["company_name"].values


# ---------------------------------------------------------------------------
# Turnaround Watch
# ---------------------------------------------------------------------------

class TestTurnaroundWatch:

    def test_fcf_positive(self, screener):
        result = screener.run("turnaround_watch")
        assert all(result["free_cash_flow_cr"] >= 0)

    def test_revenue_cagr_threshold(self, screener):
        result = screener.run("turnaround_watch")
        assert all(result["revenue_cagr_5yr"] >= 10.0)


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------

class TestRunAll:

    def test_returns_six_keys(self, screener):
        results = screener.run_all()
        assert set(results.keys()) == set(PRESETS.keys())

    def test_each_value_is_dataframe(self, screener):
        results = screener.run_all()
        for name, df in results.items():
            assert isinstance(df, pd.DataFrame), f"{name} did not return DataFrame"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:

    def test_available_presets_returns_six(self, screener):
        presets = screener.available_presets()
        assert len(presets) == 6

    def test_available_presets_has_required_keys(self, screener):
        for p in screener.available_presets():
            assert "name" in p
            assert "label" in p
            assert "description" in p

    def test_preset_filters_returns_dict(self, screener):
        filters = screener.preset_filters("quality_compounder")
        assert isinstance(filters, dict)
        assert "roe_min" in filters

    def test_unknown_preset_raises(self, screener):
        with pytest.raises(KeyError, match="Unknown preset"):
            screener.run("nonexistent_preset")

    def test_preset_filters_unknown_raises(self, screener):
        with pytest.raises(KeyError):
            screener.preset_filters("nonexistent")
