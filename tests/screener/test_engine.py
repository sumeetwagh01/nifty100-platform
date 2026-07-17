"""
tests/screener/test_engine.py
==============================
Unit tests for src/screener/engine.py

Uses in-memory DataFrames — no DB dependency.

Coverage:
  - apply() happy path — min/max filters
  - D/E filter skips Financials sector automatically
  - ICR filter — Debt Free label passes as infinity
  - CAGR flag column — non-numeric rows excluded
  - Unknown filter key raises KeyError
  - No DataFrame raises ValueError
  - validate_filters() catches bad keys and types
  - available_filters() returns all 15 keys
  - Sorting by composite_quality_score descending
  - NaN values fail filter (not skipped silently)
"""

import math
import pytest
import pandas as pd

from src.screener.engine import ScreenerEngine, DEBT_FREE_LABEL


# ---------------------------------------------------------------------------
# Fixture DataFrame
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """10-row DataFrame covering all filter edge cases."""
    return pd.DataFrame({
        "company_id":                   [1,    2,    3,    4,    5,    6,    7,    8,    9,    10],
        "company_name": [
            "QualityCo", "BankCo", "GrowthCo", "DebtyCo", "DebtFreeCo",
            "LowROECo", "HighDECo", "NaNCo", "MidCo", "ValueCo"
        ],
        "broad_sector": [
            "Industrials", "Financials", "Technology", "Industrials", "Industrials",
            "Industrials", "Industrials", "Technology", "Industrials", "Consumer"
        ],
        "return_on_equity_pct":         [22.0, 18.0, 25.0,  8.0, 20.0,  5.0, 18.0,  None, 15.0, 16.0],
        "debt_to_equity":               [0.3,  8.5,  0.2,   6.5,  0.0,  0.5,  7.0,   0.4,  0.8,  0.6],
        "free_cash_flow_cr":            [500,  800, 300,  -200,  400,  100,  200,   150,  250,  350],
        "revenue_cagr_5yr":             [14.0, 10.0, 20.0,  5.0, 12.0,  3.0,  8.0,  11.0,  9.0, 13.0],
        "pat_cagr_5yr":                 [16.0,  8.0, 22.0,  3.0, 14.0,  2.0,  6.0,   9.0, 10.0, 12.0],
        "operating_profit_margin_pct":  [20.0, 25.0, 18.0, 10.0, 22.0,  8.0, 15.0,  19.0, 16.0, 17.0],
        "interest_coverage":            [5.0,  None,  8.0,  1.2,  None,  3.0,  1.0,   4.0,  2.5,  6.0],
        "icr_label": [
            None, None, None, None, DEBT_FREE_LABEL,
            None, None, None, None, None
        ],
        "asset_turnover":               [1.2,  0.3,  1.5,  0.8,  1.1,  0.9,  0.7,   1.3,  1.0,  1.4],
        "net_profit_margin_pct":        [12.0, 18.0, 15.0,  5.0, 14.0,  3.0, 10.0,  11.0, 10.0, 13.0],
        "eps_cagr_5yr":                 [15.0,  7.0, 21.0,  4.0, 13.0,  1.0,  5.0,   8.0,  9.0, 11.0],
        "composite_quality_score":      [85.0, 60.0, 90.0, 30.0, 80.0, 20.0, 45.0,  55.0, 65.0, 75.0],
        "sales":                        [5000, 8000, 3000, 2000, 4500, 1500, 2500,  3500, 4000, 6000],
    })


@pytest.fixture
def engine(sample_df):
    return ScreenerEngine(df=sample_df)


# ---------------------------------------------------------------------------
# Basic filter tests
# ---------------------------------------------------------------------------

class TestApplyFilters:

    def test_roe_min_filter(self, engine):
        result = engine.apply({"roe_min": 15.0})
        assert all(result["return_on_equity_pct"] >= 15.0)

    def test_de_max_filter_non_financial(self, engine):
        result = engine.apply({"de_max": 1.0})
        # Non-financial companies must have D/E <= 1
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["debt_to_equity"] <= 1.0)

    def test_de_max_skips_financials(self, engine):
        result = engine.apply({"de_max": 1.0})
        # BankCo (D/E=8.5, Financials) must still be in results
        assert "BankCo" in result["company_name"].values

    def test_fcf_min_filter(self, engine):
        result = engine.apply({"fcf_min": 200.0})
        assert all(result["free_cash_flow_cr"] >= 200.0)

    def test_revenue_cagr_min_filter(self, engine):
        result = engine.apply({"revenue_cagr_5yr_min": 10.0})
        assert all(result["revenue_cagr_5yr"] >= 10.0)

    def test_opm_min_filter(self, engine):
        result = engine.apply({"opm_min": 15.0})
        assert all(result["operating_profit_margin_pct"] >= 15.0)

    def test_asset_turnover_min_filter(self, engine):
        result = engine.apply({"asset_turnover_min": 1.0})
        assert all(result["asset_turnover"] >= 1.0)

    def test_sales_min_filter(self, engine):
        result = engine.apply({"sales_min": 3000.0})
        assert all(result["sales"] >= 3000.0)

    def test_multiple_filters_combined(self, engine):
        result = engine.apply({"roe_min": 15.0, "de_max": 1.0, "fcf_min": 100.0})
        assert len(result) > 0
        non_fin = result[result["broad_sector"] != "Financials"]
        assert all(non_fin["return_on_equity_pct"] >= 15.0)
        assert all(non_fin["debt_to_equity"] <= 1.0)

    def test_empty_filters_returns_all(self, engine, sample_df):
        result = engine.apply({})
        assert len(result) == len(sample_df)

    def test_none_threshold_skipped(self, engine, sample_df):
        result = engine.apply({"roe_min": None})
        assert len(result) == len(sample_df)


# ---------------------------------------------------------------------------
# ICR special rule — Debt Free
# ---------------------------------------------------------------------------

class TestICRDebtFree:

    def test_debt_free_passes_icr_filter(self, engine):
        # DebtFreeCo has icr_label=Debt Free, interest_coverage=None
        # Should pass any ICR min threshold
        result = engine.apply({"icr_min": 3.0})
        assert "DebtFreeCo" in result["company_name"].values

    def test_low_icr_fails_filter(self, engine):
        # DebtyCo ICR=1.2 should fail icr_min=2.0
        result = engine.apply({"icr_min": 2.0})
        assert "DebtyCo" not in result["company_name"].values

    def test_icr_nan_fails_filter(self, engine):
        # BankCo ICR=None, not Debt Free → should fail
        result = engine.apply({"icr_min": 2.0})
        assert "BankCo" not in result["company_name"].values


# ---------------------------------------------------------------------------
# NaN handling
# ---------------------------------------------------------------------------

class TestNaNHandling:

    def test_nan_roe_fails_filter(self, engine):
        # NaNCo has NaN ROE — should be excluded when ROE filter applied
        result = engine.apply({"roe_min": 10.0})
        assert "NaNCo" not in result["company_name"].values

    def test_nan_roe_passes_when_no_filter(self, engine):
        result = engine.apply({})
        assert "NaNCo" in result["company_name"].values


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSorting:

    def test_sorted_by_composite_score_descending(self, engine):
        result = engine.apply({})
        scores = result["composite_quality_score"].dropna().tolist()
        assert scores == sorted(scores, reverse=True)

    def test_top_result_is_highest_quality(self, engine):
        result = engine.apply({})
        assert result.iloc[0]["company_name"] == "GrowthCo"  # score=90


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrors:

    def test_unknown_filter_raises_key_error(self, engine):
        with pytest.raises(KeyError, match="Unknown filter key"):
            engine.apply({"unknown_metric": 10.0})

    def test_no_dataframe_raises_value_error(self):
        engine = ScreenerEngine()
        with pytest.raises(ValueError, match="No DataFrame loaded"):
            engine.apply({"roe_min": 15.0})

    def test_validate_filters_catches_unknown_key(self, engine):
        errors = engine.validate_filters({"bad_key": 10.0})
        assert any("bad_key" in e for e in errors)

    def test_validate_filters_catches_non_numeric(self, engine):
        errors = engine.validate_filters({"roe_min": "high"})
        assert len(errors) > 0

    def test_validate_filters_passes_valid(self, engine):
        errors = engine.validate_filters({"roe_min": 15.0, "de_max": 1.0})
        assert errors == []


# ---------------------------------------------------------------------------
# available_filters
# ---------------------------------------------------------------------------

class TestAvailableFilters:

    def test_returns_all_15_keys(self, engine):
        keys = engine.available_filters()
        assert len(keys) == 15

    def test_contains_expected_keys(self, engine):
        keys = engine.available_filters()
        for expected in ["roe_min", "de_max", "fcf_min", "revenue_cagr_5yr_min",
                         "icr_min", "opm_min", "asset_turnover_min", "sales_min"]:
            assert expected in keys
