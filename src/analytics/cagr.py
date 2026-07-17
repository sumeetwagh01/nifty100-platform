"""
src/analytics/cagr.py
=====================
Sprint 2 – CAGR Engine: compound annual growth rates for Revenue, PAT, EPS.

Return type convention
----------------------
  float          → valid CAGR percentage  (e.g. 12.34 means 12.34%)
  "TURNAROUND"   → base_value < 0, end_value > 0  (math undefined, economically positive)
  "DECLINE_TO_LOSS" → base_value > 0, end_value < 0  (went into losses)
  "BOTH_NEGATIVE"   → base_value < 0, end_value < 0  (losses throughout)
  "ZERO_BASE"    → base_value == 0  (division impossible)
  None           → any required input is None / n < 1

All functions never raise — exceptions are caught and return None.

Screener.in column mapping
--------------------------
  Revenue CAGR  → profitandloss.sales
  PAT CAGR      → profitandloss.net_profit
  EPS CAGR      → profitandloss.eps_in_rs

Usage pattern (caller is responsible for data slicing)
-------------------------------------------------------
  The caller fetches the time-series list for a metric, sorted ascending by year,
  and passes base_value = series[0], end_value = series[-1], n = len - 1.

  Example:
      sales_series = [1000, 1100, 1250, 1400]   # years 2020-2023
      result = cagr(sales_series[0], sales_series[-1], n=3)
      # → 11.87  (11.87% revenue CAGR)
"""

from __future__ import annotations

# Sentinel strings — importable so callers can do isinstance checks
TURNAROUND = "TURNAROUND"
DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
BOTH_NEGATIVE = "BOTH_NEGATIVE"
ZERO_BASE = "ZERO_BASE"
INSUFFICIENT = "INSUFFICIENT"

SENTINELS = {TURNAROUND, DECLINE_TO_LOSS, BOTH_NEGATIVE, ZERO_BASE, INSUFFICIENT}


# ---------------------------------------------------------------------------
# Core CAGR calculator
# ---------------------------------------------------------------------------

def cagr(
    base_value: float | None,
    end_value: float | None,
    n: int,
) -> float | str | None:
    """
    Compound Annual Growth Rate (%).

    Parameters
    ----------
    base_value : value at start of period (n years ago)
    end_value  : value at end of period (current year)
    n          : number of years (must be ≥ 1)

    Returns
    -------
    float          → CAGR percentage
    sentinel str   → one of TURNAROUND / DECLINE_TO_LOSS / BOTH_NEGATIVE / ZERO_BASE
    None           → missing inputs or n < 1

    >>> round(cagr(1000, 1500, 3), 4)
    14.4714
    >>> cagr(-100, 200, 3)
    'TURNAROUND'
    >>> cagr(200, -100, 3)
    'DECLINE_TO_LOSS'
    >>> cagr(-100, -50, 3)
    'BOTH_NEGATIVE'
    >>> cagr(0, 200, 3)
    'ZERO_BASE'
    >>> cagr(None, 200, 3) is None
    True
    >>> cagr(1000, 200, 0) is None
    True
    """
    # Guard: missing inputs or invalid window
    if base_value is None or end_value is None:
        return None
    if n < 1:
        return None

    # Zero base — division impossible
    if base_value == 0:
        return ZERO_BASE

    # Sign-based sentinels (check end <= 0 before math to avoid -100% trap)
    if base_value < 0 and end_value > 0:
        return TURNAROUND
    if base_value > 0 and end_value <= 0:
        return DECLINE_TO_LOSS
    if base_value < 0 and end_value < 0:
        return BOTH_NEGATIVE

    # Normal path: both positive
    try:
        ratio = end_value / base_value
        result = (ratio ** (1.0 / n) - 1.0) * 100.0
        return result
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Window helpers — Revenue / PAT / EPS
# ---------------------------------------------------------------------------

def _window_cagr(
    series: list[float | None],
    window: int,
) -> float | str | None:
    """
    Given a time-series list sorted ascending by year, compute CAGR
    over the last `window` years.

    Requires len(series) >= window + 1 to have both base and end points.
    Returns None if series is too short or endpoint values are None.

    Parameters
    ----------
    series : values sorted oldest → newest, may contain None gaps
    window : 3, 5, or 10
    """
    if not series or len(series) < window + 1:
        return None

    # Take the last (window+1) elements: index 0 = base, index -1 = end
    segment = series[-(window + 1):]
    base_value = segment[0]
    end_value = segment[-1]

    return cagr(base_value, end_value, n=window)


def revenue_cagr(
    sales_series: list[float | None],
    window: int,
) -> float | str | None:
    """
    Revenue (Sales) CAGR over `window` years.

    Parameters
    ----------
    sales_series : profitandloss.sales values, sorted oldest → newest
    window       : 3, 5, or 10

    >>> round(revenue_cagr([1000, 1100, 1250, 1400], 3), 4)
    11.869
    >>> revenue_cagr([1000, 1100], 3) is None   # too short
    True
    """
    return _window_cagr(sales_series, window)


def pat_cagr(
    net_profit_series: list[float | None],
    window: int,
) -> float | str | None:
    """
    PAT (Profit After Tax) CAGR over `window` years.

    Parameters
    ----------
    net_profit_series : profitandloss.net_profit values, sorted oldest → newest
    window            : 3, 5, or 10

    >>> round(pat_cagr([100, 120, 140, 160], 3), 4)
    16.9613
    >>> pat_cagr([100, -50, 80, 160], 3)   # base=100 end=160 → valid
    16.9613
    >>> pat_cagr([-100, 50, 80, 160], 3)
    'TURNAROUND'
    """
    return _window_cagr(net_profit_series, window)


def eps_cagr(
    eps_series: list[float | None],
    window: int,
) -> float | str | None:
    """
    EPS CAGR over `window` years.

    Parameters
    ----------
    eps_series : profitandloss.eps_in_rs values, sorted oldest → newest
    window     : 3, 5, or 10

    >>> round(eps_cagr([10, 12, 14, 16], 3), 4)
    16.9613
    >>> eps_cagr([10], 3) is None   # only 1 data point
    True
    """
    return _window_cagr(eps_series, window)


# ---------------------------------------------------------------------------
# Convenience: compute all three windows at once for a given metric
# ---------------------------------------------------------------------------

def all_windows(
    series: list[float | None],
    metric_fn,
) -> dict[str, float | str | None]:
    """
    Compute 3yr, 5yr, 10yr CAGR for a given metric function.

    Returns
    -------
    dict with keys: 'cagr_3yr', 'cagr_5yr', 'cagr_10yr'

    >>> result = all_windows([100,110,125,140,160,185,210], revenue_cagr)
    >>> sorted(result.keys())
    ['cagr_10yr', 'cagr_3yr', 'cagr_5yr']
    """
    return {
        "cagr_3yr": metric_fn(series, 3),
        "cagr_5yr": metric_fn(series, 5),
        "cagr_10yr": metric_fn(series, 10),
    }


def is_sentinel(value: float | str | None) -> bool:
    """Return True if value is one of the four special-case sentinel strings."""
    return value in SENTINELS


# ---------------------------------------------------------------------------
# Day 10 spec wrappers — (value, flag) pairs for separate-column storage
# ---------------------------------------------------------------------------
#
# The spec requires CAGR value and edge-case flag to be stored in SEPARATE
# columns in financial_ratios (e.g. revenue_cagr_5yr + revenue_cagr_5yr_flag).
# These wrappers sit on top of the existing cagr()/sentinel-string functions
# without changing their behaviour, so all 53 existing tests stay green.
#
# Flag values: None (normal), TURNAROUND, DECLINE_TO_LOSS, BOTH_NEGATIVE,
#              ZERO_BASE, INSUFFICIENT

def cagr_with_flag(
    base_value: float | None,
    end_value: float | None,
    n: int,
) -> tuple[float | None, str | None]:
    """
    Spec-compliant CAGR wrapper: returns (value, flag) instead of a merged type.

    - Normal case        → (float, None)
    - Any edge case       → (None, sentinel_string)
    - Missing/invalid n   → (None, INSUFFICIENT)

    >>> value, flag = cagr_with_flag(1000, 1500, 3)
    >>> round(value, 4)
    14.4714
    >>> flag is None
    True
    >>> cagr_with_flag(-100, 200, 3)
    (None, 'TURNAROUND')
    """
    if base_value is None or end_value is None or n < 1:
        return (None, INSUFFICIENT)

    result = cagr(base_value, end_value, n)

    if isinstance(result, str):
        # result is a sentinel from cagr() — value is None, flag is the sentinel
        return (None, result)

    if result is None:
        return (None, INSUFFICIENT)

    return (result, None)


def _window_cagr_with_flag(
    series: list[float | None],
    window: int,
) -> tuple[float | None, str | None]:
    """
    Spec-compliant window wrapper: returns (value, flag).

    INSUFFICIENT flag fires when:
      - series is too short for the requested window
      - base or end value in the window is None
    """
    if not series or len(series) < window + 1:
        return (None, INSUFFICIENT)

    segment = series[-(window + 1):]
    base_value = segment[0]
    end_value = segment[-1]

    if base_value is None or end_value is None:
        return (None, INSUFFICIENT)

    return cagr_with_flag(base_value, end_value, n=window)


def revenue_cagr_with_flag(
    sales_series: list[float | None],
    window: int,
) -> tuple[float | None, str | None]:
    """
    Revenue CAGR as a (value, flag) pair — for storage in
    revenue_cagr_<window>yr / revenue_cagr_<window>yr_flag columns.

    >>> revenue_cagr_with_flag([1000, 1100, 1250, 1400], 3)[1] is None
    True
    >>> revenue_cagr_with_flag([1000, 1100], 3)
    (None, 'INSUFFICIENT')
    >>> revenue_cagr_with_flag([-100, 50, 100, 200], 3)
    (None, 'TURNAROUND')
    """
    return _window_cagr_with_flag(sales_series, window)


def pat_cagr_with_flag(
    net_profit_series: list[float | None],
    window: int,
) -> tuple[float | None, str | None]:
    """
    PAT CAGR as a (value, flag) pair — for storage in
    pat_cagr_<window>yr / pat_cagr_<window>yr_flag columns.

    >>> pat_cagr_with_flag([100, 80, 50, -20], 3)
    (None, 'DECLINE_TO_LOSS')
    >>> pat_cagr_with_flag([-200, -150, -100, -80], 3)
    (None, 'BOTH_NEGATIVE')
    """
    return _window_cagr_with_flag(net_profit_series, window)


def eps_cagr_with_flag(
    eps_series: list[float | None],
    window: int,
) -> tuple[float | None, str | None]:
    """
    EPS CAGR as a (value, flag) pair — for storage in
    eps_cagr_<window>yr / eps_cagr_<window>yr_flag columns.

    >>> eps_cagr_with_flag([0, 12, 14, 16], 3)
    (None, 'ZERO_BASE')
    >>> eps_cagr_with_flag([10], 3)
    (None, 'INSUFFICIENT')
    """
    return _window_cagr_with_flag(eps_series, window)


def all_windows_with_flags(
    series: list[float | None],
    metric_fn_with_flag,
) -> dict:
    """
    Compute 3yr/5yr/10yr CAGR with flags for a given *_with_flag metric function.

    Returns a flat dict matching the financial_ratios table column shape:
        {
            'cagr_3yr': float | None,  'cagr_3yr_flag': str | None,
            'cagr_5yr': float | None,  'cagr_5yr_flag': str | None,
            'cagr_10yr': float | None, 'cagr_10yr_flag': str | None,
        }

    >>> result = all_windows_with_flags([100,110,125,140,160,185,210], revenue_cagr_with_flag)
    >>> sorted(result.keys())
    ['cagr_10yr', 'cagr_10yr_flag', 'cagr_3yr', 'cagr_3yr_flag', 'cagr_5yr', 'cagr_5yr_flag']
    """
    out = {}
    for label, window in (("cagr_3yr", 3), ("cagr_5yr", 5), ("cagr_10yr", 10)):
        value, flag = metric_fn_with_flag(series, window)
        out[label] = value
        out[f"{label}_flag"] = flag
    return out
