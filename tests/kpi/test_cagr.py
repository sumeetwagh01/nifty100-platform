"""
tests/kpi/test_cagr.py
======================
Unit tests for src/analytics/cagr.py

Coverage:
  - cagr()       : core formula, all 4 sentinels, edge cases, None propagation
  - revenue_cagr(): happy path, short series, None in series
  - pat_cagr()   : turnaround and normal cases
  - eps_cagr()   : happy path, insufficient data
  - all_windows(): dict structure and values
  - is_sentinel(): all sentinels + non-sentinel values
"""

import pytest
from src.analytics.cagr import (
    cagr,
    revenue_cagr,
    pat_cagr,
    eps_cagr,
    all_windows,
    is_sentinel,
    TURNAROUND,
    DECLINE_TO_LOSS,
    BOTH_NEGATIVE,
    ZERO_BASE,
)


# ---------------------------------------------------------------------------
# Core cagr() function
# ---------------------------------------------------------------------------

class TestCAGRCore:

    # --- Happy path ---
    def test_positive_growth(self):
        # 1000 → 1500 over 3 years
        assert round(cagr(1000, 1500, 3), 4) == 14.4714

    def test_zero_growth(self):
        # No change over any period
        assert cagr(1000, 1000, 5) == pytest.approx(0.0, abs=1e-6)

    def test_negative_growth_decline(self):
        # 1000 → 500 over 3 years (~-20.6% CAGR)
        result = cagr(1000, 500, 3)
        assert result == pytest.approx(-20.6299, rel=1e-4)

    def test_single_year_window(self):
        # n=1: CAGR = (end/base - 1) * 100
        assert cagr(100, 120, 1) == pytest.approx(20.0, rel=1e-4)

    def test_ten_year_window(self):
        # 1000 → 2000 over 10 years ≈ 7.177%
        assert round(cagr(1000, 2000, 10), 3) == 7.177

    def test_large_values(self):
        # Crore-scale — should not overflow
        result = cagr(50000, 150000, 5)
        assert isinstance(result, float)
        assert result > 0

    # --- Sentinel cases ---
    def test_turnaround(self):
        assert cagr(-100, 200, 3) == TURNAROUND

    def test_decline_to_loss(self):
        assert cagr(200, -100, 3) == DECLINE_TO_LOSS

    def test_both_negative(self):
        assert cagr(-200, -100, 3) == BOTH_NEGATIVE

    def test_zero_base(self):
        assert cagr(0, 200, 3) == ZERO_BASE

    def test_zero_base_negative_end(self):
        assert cagr(0, -100, 3) == ZERO_BASE

    def test_zero_base_zero_end(self):
        assert cagr(0, 0, 3) == ZERO_BASE

    # --- None / invalid inputs ---
    def test_none_base(self):
        assert cagr(None, 1000, 3) is None

    def test_none_end(self):
        assert cagr(1000, None, 3) is None

    def test_both_none(self):
        assert cagr(None, None, 3) is None

    def test_zero_window(self):
        assert cagr(1000, 1500, 0) is None

    def test_negative_window(self):
        assert cagr(1000, 1500, -1) is None

    # --- Edge: end value = 0 (base > 0) ---
    def test_decline_to_zero(self):
        # base=1000, end=0 → DECLINE_TO_LOSS
        assert cagr(1000, 0, 3) == DECLINE_TO_LOSS

    # --- Floating point precision ---
    def test_fractional_inputs(self):
        result = cagr(10.5, 21.0, 5)
        assert isinstance(result, float)
        assert result == pytest.approx(14.869, rel=1e-3)


# ---------------------------------------------------------------------------
# revenue_cagr()
# ---------------------------------------------------------------------------

class TestRevenueCagr:

    def test_3yr_happy_path(self):
        # [1000, 1100, 1250, 1400] — base=1000, end=1400, n=3
        series = [1000, 1100, 1250, 1400]
        assert round(revenue_cagr(series, 3), 3) == 11.869

    def test_5yr_happy_path(self):
        series = [1000, 1100, 1200, 1350, 1500, 1700]
        result = revenue_cagr(series, 5)
        assert isinstance(result, float)
        assert result > 0

    def test_10yr_happy_path(self):
        series = list(range(1000, 2200, 100))   # 12 values
        result = revenue_cagr(series, 10)
        assert isinstance(result, float)

    def test_series_too_short_for_window(self):
        # Only 3 values but asking for 3yr (need 4)
        assert revenue_cagr([1000, 1100, 1200], 3) is None

    def test_single_element_series(self):
        assert revenue_cagr([1000], 3) is None

    def test_empty_series(self):
        assert revenue_cagr([], 3) is None

    def test_none_base_in_series(self):
        # base position is None
        series = [None, 1100, 1250, 1400]
        assert revenue_cagr(series, 3) is None

    def test_none_end_in_series(self):
        series = [1000, 1100, 1250, None]
        assert revenue_cagr(series, 3) is None

    def test_turnaround_in_revenue(self):
        series = [-100, 50, 100, 200]
        assert revenue_cagr(series, 3) == TURNAROUND

    def test_uses_last_n_plus_one_values(self):
        # Long series — window of 3 should use last 4 values: [800, 1000, 1100, 1400]
        series = [500, 600, 700, 800, 1000, 1100, 1400]
        result = revenue_cagr(series, 3)
        expected = cagr(800, 1400, 3)   # base=series[-4], end=series[-1]
        assert result == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# pat_cagr()
# ---------------------------------------------------------------------------

class TestPatCagr:

    def test_3yr_happy_path(self):
        series = [100, 120, 140, 160]
        assert round(pat_cagr(series, 3), 4) == 16.9607

    def test_turnaround(self):
        series = [-100, 50, 80, 160]
        assert pat_cagr(series, 3) == TURNAROUND

    def test_decline_to_loss(self):
        series = [100, 80, 50, -20]
        assert pat_cagr(series, 3) == DECLINE_TO_LOSS

    def test_both_negative(self):
        series = [-200, -150, -100, -80]
        assert pat_cagr(series, 3) == BOTH_NEGATIVE

    def test_zero_base_pat(self):
        series = [0, 50, 100, 150]
        assert pat_cagr(series, 3) == ZERO_BASE

    def test_series_too_short(self):
        assert pat_cagr([100, 120], 3) is None

    def test_interior_none_ignored(self):
        # Interior Nones don't affect base/end selection
        series = [100, None, None, 160]
        assert round(pat_cagr(series, 3), 4) == 16.9607


# ---------------------------------------------------------------------------
# eps_cagr()
# ---------------------------------------------------------------------------

class TestEpsCagr:

    def test_3yr_happy_path(self):
        series = [10, 12, 14, 16]
        assert round(eps_cagr(series, 3), 4) == 16.9607

    def test_5yr_happy_path(self):
        series = [5, 6, 7, 8, 9, 10]
        result = eps_cagr(series, 5)
        assert isinstance(result, float)
        assert result == pytest.approx(14.8698, rel=1e-3)

    def test_single_data_point(self):
        assert eps_cagr([10], 3) is None

    def test_insufficient_for_10yr(self):
        # Only 8 values — can't compute 10yr
        series = list(range(10, 90, 10))   # 8 values
        assert eps_cagr(series, 10) is None

    def test_turnaround_eps(self):
        series = [-5, 2, 8, 15]
        assert eps_cagr(series, 3) == TURNAROUND


# ---------------------------------------------------------------------------
# all_windows()
# ---------------------------------------------------------------------------

class TestAllWindows:

    def test_returns_dict_with_three_keys(self):
        series = list(range(100, 1200, 100))   # 11 values
        result = all_windows(series, revenue_cagr)
        assert set(result.keys()) == {"cagr_3yr", "cagr_5yr", "cagr_10yr"}

    def test_values_match_individual_calls(self):
        series = list(range(100, 1200, 100))
        result = all_windows(series, revenue_cagr)
        assert result["cagr_3yr"] == revenue_cagr(series, 3)
        assert result["cagr_5yr"] == revenue_cagr(series, 5)
        assert result["cagr_10yr"] == revenue_cagr(series, 10)

    def test_short_series_returns_none_for_longer_windows(self):
        # 5 values → 3yr works, 5yr and 10yr return None
        series = [100, 120, 140, 165, 190]
        result = all_windows(series, revenue_cagr)
        assert isinstance(result["cagr_3yr"], float)
        assert result["cagr_5yr"] is None
        assert result["cagr_10yr"] is None

    def test_works_with_pat_cagr(self):
        series = [100, 110, 125, 140]
        result = all_windows(series, pat_cagr)
        assert "cagr_3yr" in result

    def test_works_with_eps_cagr(self):
        series = [10, 12, 14, 16]
        result = all_windows(series, eps_cagr)
        assert "cagr_3yr" in result


# ---------------------------------------------------------------------------
# is_sentinel()
# ---------------------------------------------------------------------------

class TestIsSentinel:

    def test_turnaround_is_sentinel(self):
        assert is_sentinel(TURNAROUND) is True

    def test_decline_to_loss_is_sentinel(self):
        assert is_sentinel(DECLINE_TO_LOSS) is True

    def test_both_negative_is_sentinel(self):
        assert is_sentinel(BOTH_NEGATIVE) is True

    def test_zero_base_is_sentinel(self):
        assert is_sentinel(ZERO_BASE) is True

    def test_float_is_not_sentinel(self):
        assert is_sentinel(12.5) is False

    def test_none_is_not_sentinel(self):
        assert is_sentinel(None) is False

    def test_zero_float_is_not_sentinel(self):
        assert is_sentinel(0.0) is False


# ---------------------------------------------------------------------------
# Day 10 spec wrappers — (value, flag) pairs
# ---------------------------------------------------------------------------

from src.analytics.cagr import (
    cagr_with_flag,
    revenue_cagr_with_flag,
    pat_cagr_with_flag,
    eps_cagr_with_flag,
    all_windows_with_flags,
    INSUFFICIENT,
)


class TestCagrWithFlag:

    def test_normal_cagr_value_with_no_flag(self):
        value, flag = cagr_with_flag(1000, 1500, 3)
        assert round(value, 4) == 14.4714
        assert flag is None

    def test_turnaround_flag(self):
        value, flag = cagr_with_flag(-100, 200, 3)
        assert value is None
        assert flag == TURNAROUND

    def test_decline_to_loss_flag(self):
        value, flag = cagr_with_flag(200, -100, 3)
        assert value is None
        assert flag == DECLINE_TO_LOSS

    def test_both_negative_flag(self):
        value, flag = cagr_with_flag(-200, -100, 3)
        assert value is None
        assert flag == BOTH_NEGATIVE

    def test_zero_base_flag(self):
        value, flag = cagr_with_flag(0, 200, 3)
        assert value is None
        assert flag == ZERO_BASE

    def test_insufficient_data_none_base(self):
        value, flag = cagr_with_flag(None, 200, 3)
        assert value is None
        assert flag == INSUFFICIENT

    def test_insufficient_data_invalid_window(self):
        value, flag = cagr_with_flag(1000, 1500, 0)
        assert value is None
        assert flag == INSUFFICIENT


class TestWindowCagrWithFlag:

    def test_revenue_cagr_normal(self):
        value, flag = revenue_cagr_with_flag([1000, 1100, 1250, 1400], 3)
        assert round(value, 4) == 11.8689
        assert flag is None

    def test_revenue_cagr_insufficient_short_series(self):
        value, flag = revenue_cagr_with_flag([1000, 1100], 3)
        assert value is None
        assert flag == INSUFFICIENT

    def test_revenue_cagr_turnaround(self):
        value, flag = revenue_cagr_with_flag([-100, 50, 100, 200], 3)
        assert value is None
        assert flag == TURNAROUND

    def test_pat_cagr_decline_to_loss(self):
        value, flag = pat_cagr_with_flag([100, 80, 50, -20], 3)
        assert value is None
        assert flag == DECLINE_TO_LOSS

    def test_pat_cagr_both_negative(self):
        value, flag = pat_cagr_with_flag([-200, -150, -100, -80], 3)
        assert value is None
        assert flag == BOTH_NEGATIVE

    def test_eps_cagr_zero_base(self):
        value, flag = eps_cagr_with_flag([0, 12, 14, 16], 3)
        assert value is None
        assert flag == ZERO_BASE

    def test_eps_cagr_insufficient_single_point(self):
        value, flag = eps_cagr_with_flag([10], 3)
        assert value is None
        assert flag == INSUFFICIENT

    def test_interior_none_insufficient(self):
        # base/end present but interior None should not break a valid calc
        value, flag = pat_cagr_with_flag([100, None, None, 160], 3)
        assert round(value, 4) == 16.9607
        assert flag is None

    def test_none_base_in_window_insufficient(self):
        value, flag = revenue_cagr_with_flag([None, 1100, 1250, 1400], 3)
        assert value is None
        assert flag == INSUFFICIENT

    def test_none_end_in_window_insufficient(self):
        value, flag = revenue_cagr_with_flag([1000, 1100, 1250, None], 3)
        assert value is None
        assert flag == INSUFFICIENT


class TestAllWindowsWithFlags:

    def test_returns_six_keys(self):
        series = list(range(100, 1200, 100))   # 11 values
        result = all_windows_with_flags(series, revenue_cagr_with_flag)
        expected_keys = {
            "cagr_3yr", "cagr_3yr_flag",
            "cagr_5yr", "cagr_5yr_flag",
            "cagr_10yr", "cagr_10yr_flag",
        }
        assert set(result.keys()) == expected_keys

    def test_normal_value_has_none_flag(self):
        series = list(range(100, 1200, 100))
        result = all_windows_with_flags(series, revenue_cagr_with_flag)
        assert result["cagr_3yr"] is not None
        assert result["cagr_3yr_flag"] is None

    def test_short_series_flags_insufficient(self):
        series = [100, 120, 140, 165, 190]   # 5 values -> 3yr ok, 5yr/10yr short
        result = all_windows_with_flags(series, revenue_cagr_with_flag)
        assert result["cagr_5yr"] is None
        assert result["cagr_5yr_flag"] == INSUFFICIENT
        assert result["cagr_10yr"] is None
        assert result["cagr_10yr_flag"] == INSUFFICIENT

    def test_works_with_pat_and_eps(self):
        series = [100, 110, 125, 140]
        pat_result = all_windows_with_flags(series, pat_cagr_with_flag)
        eps_result = all_windows_with_flags(series, eps_cagr_with_flag)
        assert "cagr_3yr_flag" in pat_result
        assert "cagr_3yr_flag" in eps_result
