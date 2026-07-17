"""
tests/kpi/test_ratios.py
========================
Unit tests for src/analytics/ratios.py

Coverage:
  - Happy-path (known inputs → known outputs checked to ±0.01%)
  - Zero-denominator guard → None
  - Negative equity guard → None
  - None-input propagation → None
  - Debt-free edge cases (D/E = 0, ICR = None)
  - Mixed None/zero inputs
"""

import pytest
from src.analytics.ratios import (
    npm, opm, roe, roce, de_ratio, icr, roa, opm_crosscheck,
    net_debt, asset_turnover, icr_label, icr_warning_flag, high_leverage_flag,
)


# ---------------------------------------------------------------------------
# NPM
# ---------------------------------------------------------------------------

class TestNPM:
    def test_happy_path(self):
        assert round(npm(200, 1000), 4) == 20.0

    def test_negative_profit(self):
        # Losses are valid — negative margin
        assert round(npm(-100, 1000), 4) == -10.0

    def test_zero_sales(self):
        assert npm(200, 0) is None

    def test_none_profit(self):
        assert npm(None, 1000) is None

    def test_none_sales(self):
        assert npm(200, None) is None

    def test_both_none(self):
        assert npm(None, None) is None

    def test_zero_profit(self):
        assert npm(0, 1000) == 0.0

    def test_small_margin(self):
        # 1.5% margin
        assert round(npm(15, 1000), 4) == 1.5


# ---------------------------------------------------------------------------
# OPM
# ---------------------------------------------------------------------------

class TestOPM:
    def test_happy_path(self):
        assert round(opm(300, 1000), 4) == 30.0

    def test_zero_sales(self):
        assert opm(300, 0) is None

    def test_none_operating_profit(self):
        assert opm(None, 1000) is None

    def test_none_sales(self):
        assert opm(300, None) is None

    def test_negative_opm(self):
        assert round(opm(-50, 500), 4) == -10.0

    def test_zero_operating_profit(self):
        assert opm(0, 1000) == 0.0


# ---------------------------------------------------------------------------
# ROE
# ---------------------------------------------------------------------------

class TestROE:
    def test_happy_path(self):
        # net_profit=150, equity_capital=100, reserves=900 → equity=1000 → ROE=15%
        assert round(roe(150, 100, 900), 4) == 15.0

    def test_zero_equity(self):
        assert roe(150, 0, 0) is None

    def test_negative_equity(self):
        # equity_capital=100, reserves=-300 → equity=-200
        assert roe(150, 100, -300) is None

    def test_none_profit(self):
        assert roe(None, 100, 900) is None

    def test_none_equity_capital(self):
        # reserves alone still valid
        assert roe(150, None, 1000) is not None

    def test_both_equity_none(self):
        assert roe(150, None, None) is None

    def test_negative_profit_valid_equity(self):
        # Losses with positive equity → negative ROE
        assert roe(-100, 100, 900) == pytest.approx(-10.0, rel=1e-4)


# ---------------------------------------------------------------------------
# ROCE
# ---------------------------------------------------------------------------

class TestROCE:
    def test_happy_path(self):
        # EBIT = 400-50=350, CE = (100+900)+200=1200 → ROCE=29.1667%
        assert round(roce(400, 50, 100, 900, 200), 4) == 29.1667

    def test_zero_capital_employed(self):
        assert roce(400, 50, 0, 0, 0) is None

    def test_negative_capital_employed(self):
        # equity=-500, borrowings=100 → CE=-400
        assert roce(400, 50, 100, -700, 100) is None

    def test_none_operating_profit(self):
        assert roce(None, 50, 100, 900, 200) is None

    def test_none_depreciation_treated_as_zero(self):
        # depreciation=None → treated as 0
        result = roce(400, None, 100, 900, 200)
        assert result == pytest.approx(roce(400, 0, 100, 900, 200), rel=1e-4)

    def test_none_borrowings_treated_as_zero(self):
        result = roce(400, 50, 100, 900, None)
        expected = (350 / 1000) * 100
        assert result == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# D/E Ratio
# ---------------------------------------------------------------------------

class TestDERatio:
    def test_happy_path(self):
        # borrowings=500, equity=1000 → D/E=0.5
        assert round(de_ratio(500, 100, 900), 4) == 0.5

    def test_debt_free_zero_borrowings(self):
        assert de_ratio(0, 100, 900) == 0.0

    def test_debt_free_none_borrowings(self):
        assert de_ratio(None, 100, 900) == 0.0

    def test_negative_equity(self):
        assert de_ratio(500, 100, -300) is None

    def test_zero_equity(self):
        assert de_ratio(500, 0, 0) is None

    def test_high_leverage(self):
        # D/E = 6 — caller should flag for non-financials
        assert round(de_ratio(6000, 100, 900), 4) == 6.0

    def test_none_equity_capital_only_reserves(self):
        # equity_capital=None, reserves=1000 → equity=1000
        assert round(de_ratio(500, None, 1000), 4) == 0.5


# ---------------------------------------------------------------------------
# ICR
# ---------------------------------------------------------------------------

class TestICR:
    def test_happy_path(self):
        # (400 + 50) / 100 = 4.5
        assert round(icr(400, 50, 100), 4) == 4.5

    def test_zero_interest_debt_free(self):
        assert icr(400, 50, 0) is None

    def test_none_interest_debt_free(self):
        assert icr(400, 50, None) is None

    def test_none_operating_profit(self):
        assert icr(None, 50, 100) is None

    def test_none_other_income_treated_as_zero(self):
        # other_income=None → 0
        assert round(icr(400, None, 100), 4) == 4.0

    def test_negative_coverage(self):
        # Operating loss → negative ICR
        assert icr(-200, 0, 100) == pytest.approx(-2.0, rel=1e-4)

    def test_very_high_coverage(self):
        # Very low interest
        assert icr(1000, 0, 1) == pytest.approx(1000.0, rel=1e-4)


# ---------------------------------------------------------------------------
# ROCE — Financials carve-out
# ---------------------------------------------------------------------------

class TestROCEFinancials:
    def test_financials_sector_returns_none(self):
        # Banks/NBFCs: ROCE is meaningless — must return None
        assert roce(400, 50, 100, 900, 200, is_financial=True) is None

    def test_non_financial_still_works(self):
        assert round(roce(400, 50, 100, 900, 200, is_financial=False), 2) == 29.17

    def test_default_is_non_financial(self):
        # Default behaviour unchanged — existing tests still pass
        assert round(roce(400, 50, 100, 900, 200), 2) == 29.17


# ---------------------------------------------------------------------------
# ROA
# ---------------------------------------------------------------------------

class TestROA:
    def test_happy_path(self):
        assert round(roa(150, 1500), 4) == 10.0

    def test_negative_roa(self):
        assert round(roa(-100, 1500), 4) == -6.6667

    def test_zero_total_assets(self):
        assert roa(150, 0) is None

    def test_none_net_profit(self):
        assert roa(None, 1500) is None

    def test_none_total_assets(self):
        assert roa(150, None) is None

    def test_both_none(self):
        assert roa(None, None) is None

    def test_zero_profit(self):
        assert roa(0, 1500) == 0.0

    def test_large_asset_base(self):
        # Crore-scale — typical for Nifty 100 companies
        assert round(roa(5000, 200000), 4) == 2.5


# ---------------------------------------------------------------------------
# OPM Cross-check
# ---------------------------------------------------------------------------

class TestOPMCrosscheck:
    def test_no_mismatch(self):
        result = opm_crosscheck(300, 1000, 30.0)
        assert result["mismatch"] is False
        assert result["skipped"] is False
        assert result["computed"] == 30.0
        assert result["diff"] == 0.0

    def test_mismatch_above_threshold(self):
        # computed=30.0, screener=31.5 → diff=1.5 > 1%
        result = opm_crosscheck(300, 1000, 31.5)
        assert result["mismatch"] is True
        assert result["diff"] == 1.5

    def test_diff_exactly_at_threshold_not_flagged(self):
        # diff=1.0 is NOT > 1.0 so no mismatch
        result = opm_crosscheck(300, 1000, 31.0)
        assert result["mismatch"] is False
        assert result["diff"] == 1.0

    def test_none_operating_profit_skips(self):
        result = opm_crosscheck(None, 1000, 30.0)
        assert result["skipped"] is True
        assert result["mismatch"] is False

    def test_none_screener_value_skips(self):
        result = opm_crosscheck(300, 1000, None)
        assert result["skipped"] is True

    def test_zero_sales_skips(self):
        result = opm_crosscheck(300, 0, 30.0)
        assert result["skipped"] is True

    def test_dict_has_all_keys(self):
        result = opm_crosscheck(300, 1000, 30.0)
        assert set(result.keys()) == {"computed", "screener", "diff", "mismatch", "skipped"}

    def test_negative_opm_crosscheck(self):
        # Loss-making — OPM can be negative
        # computed=-10.0, screener=-9.5 → diff=0.5 → no mismatch (< 1%)
        result = opm_crosscheck(-50, 500, -9.5)
        assert result["computed"] == -10.0
        assert result["diff"] == 0.5
        assert result["mismatch"] is False


# ---------------------------------------------------------------------------
# Net Debt
# ---------------------------------------------------------------------------

class TestNetDebt:
    def test_happy_path(self):
        assert net_debt(1000, 300) == 700.0

    def test_none_investments_treated_as_zero(self):
        assert net_debt(1000, None) == 1000.0

    def test_none_borrowings_returns_none(self):
        assert net_debt(None, 300) is None

    def test_negative_net_debt(self):
        # More liquid assets than debt
        assert net_debt(300, 1000) == -700.0

    def test_zero_borrowings(self):
        assert net_debt(0, 300) == -300.0

    def test_both_zero(self):
        assert net_debt(0, 0) == 0.0


# ---------------------------------------------------------------------------
# Asset Turnover
# ---------------------------------------------------------------------------

class TestAssetTurnover:
    def test_happy_path(self):
        assert round(asset_turnover(2000, 1000), 4) == 2.0

    def test_zero_total_assets(self):
        assert asset_turnover(2000, 0) is None

    def test_none_sales(self):
        assert asset_turnover(None, 1000) is None

    def test_none_total_assets(self):
        assert asset_turnover(2000, None) is None

    def test_low_turnover(self):
        # Capital-heavy company
        assert round(asset_turnover(500, 5000), 4) == 0.1

    def test_zero_sales(self):
        assert asset_turnover(0, 1000) == 0.0


# ---------------------------------------------------------------------------
# ICR Label
# ---------------------------------------------------------------------------

class TestICRLabel:
    def test_zero_interest_is_debt_free(self):
        assert icr_label(0) == "Debt Free"

    def test_none_interest_is_debt_free(self):
        assert icr_label(None) == "Debt Free"

    def test_positive_interest_returns_none(self):
        assert icr_label(100) is None

    def test_small_interest_not_debt_free(self):
        assert icr_label(0.01) is None


# ---------------------------------------------------------------------------
# ICR Warning Flag
# ---------------------------------------------------------------------------

class TestICRWarningFlag:
    def test_below_threshold_flagged(self):
        assert icr_warning_flag(1.2) is True

    def test_exactly_at_threshold_not_flagged(self):
        # 1.5 is NOT < 1.5
        assert icr_warning_flag(1.5) is False

    def test_above_threshold_not_flagged(self):
        assert icr_warning_flag(3.0) is False

    def test_none_not_flagged(self):
        assert icr_warning_flag(None) is False

    def test_negative_icr_flagged(self):
        # Operating loss — definitely at risk
        assert icr_warning_flag(-1.0) is True

    def test_just_below_threshold(self):
        assert icr_warning_flag(1.49) is True


# ---------------------------------------------------------------------------
# High Leverage Flag
# ---------------------------------------------------------------------------

class TestHighLeverageFlag:
    def test_above_threshold_non_financial(self):
        assert high_leverage_flag(6.0) is True

    def test_above_threshold_financial_not_flagged(self):
        assert high_leverage_flag(6.0, is_financial=True) is False

    def test_exactly_at_threshold_not_flagged(self):
        # 5.0 is NOT > 5.0
        assert high_leverage_flag(5.0) is False

    def test_below_threshold(self):
        assert high_leverage_flag(4.9) is False

    def test_none_de_not_flagged(self):
        assert high_leverage_flag(None) is False

    def test_zero_de_not_flagged(self):
        assert high_leverage_flag(0.0) is False

    def test_default_is_non_financial(self):
        assert high_leverage_flag(6.0, is_financial=False) is True
