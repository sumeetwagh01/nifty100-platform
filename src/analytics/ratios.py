"""
src/analytics/ratios.py
=======================
Sprint 2 – Ratio Engine: profitability and leverage KPIs.

All functions follow a strict contract:
  - Accept individual numeric values (float | int | None)
  - Return float | None
  - Never raise — invalid inputs return None and are logged by the caller
  - Division-by-zero always returns None (caller writes to ratio_edge_cases.log)

KPIs implemented
----------------
  NPM            Net Profit Margin          = net_profit / sales × 100
  OPM            Operating Profit Margin    = operating_profit / sales × 100
  ROE            Return on Equity           = net_profit / equity × 100
  ROCE           Return on Capital Employed = ebit / capital_employed × 100
                 → Financials sector: returns None (sector benchmark required)
  ROA            Return on Assets           = net_profit / total_assets × 100
  DE             Debt-to-Equity             = borrowings / equity  (0 if debt-free)
  ICR            Interest Coverage Ratio    = ebit / interest      (None if interest=0)
  opm_crosscheck OPM validation             = flag if |computed - screener| > 1%

Terminology mapping to Screener.in column names
------------------------------------------------
  sales             → profitandloss.sales
  net_profit        → profitandloss.net_profit
  operating_profit  → profitandloss.operating_profit   (EBITDA proxy)
  depreciation      → profitandloss.depreciation
  other_income      → profitandloss.other_income
  interest          → profitandloss.interest
  equity_capital    → balancesheet.equity_capital
  reserves          → balancesheet.reserves
  borrowings        → balancesheet.borrowings
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Return numerator / denominator, or None for any invalid input."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def _equity(equity_capital: float | None, reserves: float | None) -> float | None:
    """Shareholder equity = equity_capital + reserves. None if both are None."""
    if equity_capital is None and reserves is None:
        return None
    return (equity_capital or 0.0) + (reserves or 0.0)


# ---------------------------------------------------------------------------
# Profitability ratios
# ---------------------------------------------------------------------------

def npm(net_profit: float | None, sales: float | None) -> float | None:
    """
    Net Profit Margin (%).

    Returns None if sales is zero or either input is None.

    >>> round(npm(200, 1000), 2)
    20.0
    >>> npm(None, 1000) is None
    True
    >>> npm(200, 0) is None
    True
    """
    result = _safe_div(net_profit, sales)
    if result is None:
        return None
    return result * 100.0


def opm(operating_profit: float | None, sales: float | None) -> float | None:
    """
    Operating Profit Margin (%).

    Returns None if sales is zero or either input is None.

    >>> round(opm(300, 1000), 2)
    30.0
    >>> opm(300, 0) is None
    True
    """
    result = _safe_div(operating_profit, sales)
    if result is None:
        return None
    return result * 100.0


def roe(
    net_profit: float | None,
    equity_capital: float | None,
    reserves: float | None,
) -> float | None:
    """
    Return on Equity (%).

    equity = equity_capital + reserves
    Returns None if equity ≤ 0 (negative book value makes ROE meaningless).

    >>> round(roe(150, 100, 900), 2)
    15.0
    >>> roe(150, -200, 100) is None   # equity = -100
    True
    >>> roe(150, 0, 0) is None        # equity = 0
    True
    """
    eq = _equity(equity_capital, reserves)
    if eq is None or eq <= 0:
        return None
    result = _safe_div(net_profit, eq)
    if result is None:
        return None
    return result * 100.0


def roce(
    operating_profit: float | None,
    depreciation: float | None,
    equity_capital: float | None,
    reserves: float | None,
    borrowings: float | None,
    is_financial: bool = False,
) -> float | None:
    """
    Return on Capital Employed (%).

    EBIT = operating_profit - depreciation
    Capital Employed = equity + borrowings

    Returns None if capital_employed <= 0.
    Returns None if is_financial=True — banking/NBFC capital structure makes
    ROCE non-comparable; caller must use sector-relative benchmark instead.

    >>> round(roce(400, 50, 100, 900, 200), 2)  # EBIT=350, CE=1200
    29.17
    >>> roce(400, 50, -200, 100, 0) is None     # CE = -100
    True
    >>> roce(400, 50, 100, 900, 200, is_financial=True) is None
    True
    """
    if is_financial:
        return None

    depr = depreciation or 0.0
    if operating_profit is None:
        return None
    ebit = operating_profit - depr

    eq = _equity(equity_capital, reserves)
    borr = borrowings or 0.0
    if eq is None:
        return None
    capital_employed = eq + borr

    if capital_employed <= 0:
        return None

    return (ebit / capital_employed) * 100.0


# ---------------------------------------------------------------------------
# Leverage ratios
# ---------------------------------------------------------------------------

def de_ratio(
    borrowings: float | None,
    equity_capital: float | None,
    reserves: float | None,
) -> float | None:
    """
    Debt-to-Equity ratio.

    Returns 0.0 if borrowings is None or 0 (debt-free company).
    Returns None if equity ≤ 0 (negative book value).

    D/E > 5 for non-financial companies is flagged by the caller.

    >>> round(de_ratio(500, 100, 900), 4)
    0.5
    >>> de_ratio(0, 100, 900)
    0.0
    >>> de_ratio(None, 100, 900)
    0.0
    >>> de_ratio(500, -200, 100) is None   # equity = -100
    True
    """
    eq = _equity(equity_capital, reserves)
    if eq is None or eq <= 0:
        return None
    borr = borrowings or 0.0
    if borr == 0:
        return 0.0
    return borr / eq


def icr(
    operating_profit: float | None,
    other_income: float | None,
    interest: float | None,
    depreciation: float | None = None,
) -> float | None:
    """
    Interest Coverage Ratio.

    Numerator = operating_profit + other_income   (EBIT proxy used by Screener)
    Denominator = interest expense

    Returns None when interest is 0 or None — caller should display 'Debt Free'.
    Returns None when numerator inputs are missing.

    Note: depreciation parameter reserved for future EBIT variant; unused here.

    >>> round(icr(400, 50, 100), 2)
    4.5
    >>> icr(400, 50, 0) is None       # debt-free
    True
    >>> icr(400, 50, None) is None    # debt-free
    True
    >>> icr(None, 50, 100) is None    # missing operating profit
    True
    """
    if interest is None or interest == 0:
        return None
    if operating_profit is None:
        return None
    oi = other_income or 0.0
    numerator = operating_profit + oi
    return _safe_div(numerator, interest)


# ---------------------------------------------------------------------------
# Asset-based ratios
# ---------------------------------------------------------------------------

def roa(
    net_profit: float | None,
    total_assets: float | None,
) -> float | None:
    """
    Return on Assets (%).

    ROA = net_profit / total_assets x 100

    Returns None if total_assets is zero or None.
    Negative ROA (loss-making companies) is valid and returned as-is.

    >>> round(roa(150, 1500), 4)
    10.0
    >>> roa(150, 0) is None
    True
    >>> roa(None, 1500) is None
    True
    >>> round(roa(-100, 1500), 4)
    -6.6667
    """
    result = _safe_div(net_profit, total_assets)
    if result is None:
        return None
    return result * 100.0


# ---------------------------------------------------------------------------
# OPM cross-check (validation helper)
# ---------------------------------------------------------------------------

OPM_CROSSCHECK_THRESHOLD = 1.0   # percent — flag if diff exceeds this


def opm_crosscheck(
    operating_profit: float | None,
    sales: float | None,
    opm_percentage: float | None,
) -> dict:
    """
    Validate computed OPM against Screener.in's pre-computed opm_percentage field.

    Computes OPM from raw fields, compares to Screener value.
    Returns a result dict so the caller can decide whether to log.

    Parameters
    ----------
    operating_profit : profitandloss.operating_profit
    sales            : profitandloss.sales
    opm_percentage   : profitandloss.opm_percentage  (Screener pre-computed)

    Returns
    -------
    dict with keys:
        computed   : float | None  — our calculated OPM
        screener   : float | None  — Screener's value
        diff       : float | None  — abs(computed - screener), None if either missing
        mismatch   : bool          — True if diff > 1%
        skipped    : bool          — True if crosscheck could not run (missing data)

    >>> result = opm_crosscheck(300, 1000, 30.5)
    >>> result['computed']
    30.0
    >>> result['mismatch']
    True

    >>> result = opm_crosscheck(300, 1000, 30.0)
    >>> result['mismatch']
    False

    >>> result = opm_crosscheck(None, 1000, 30.0)
    >>> result['skipped']
    True
    """
    computed = opm(operating_profit, sales)

    if computed is None or opm_percentage is None:
        return {
            "computed": computed,
            "screener": opm_percentage,
            "diff": None,
            "mismatch": False,
            "skipped": True,
        }

    diff = abs(computed - opm_percentage)
    return {
        "computed": computed,
        "screener": opm_percentage,
        "diff": round(diff, 4),
        "mismatch": diff > OPM_CROSSCHECK_THRESHOLD,
        "skipped": False,
    }


# ---------------------------------------------------------------------------
# Leverage & efficiency — Day 09 additions
# ---------------------------------------------------------------------------

def net_debt(
    borrowings: float | None,
    investments: float | None,
) -> float | None:
    """
    Net Debt = borrowings - investments.

    investments is used as a liquid asset proxy (Screener.in balancesheet field).
    Returns None if borrowings is None.
    Negative net debt means the company holds more liquid assets than debt.

    >>> net_debt(1000, 300)
    700.0
    >>> net_debt(1000, None)
    1000.0
    >>> net_debt(None, 300) is None
    True
    >>> net_debt(300, 1000)
    -700.0
    """
    if borrowings is None:
        return None
    inv = investments or 0.0
    return float(borrowings) - inv


def asset_turnover(
    sales: float | None,
    total_assets: float | None,
) -> float | None:
    """
    Asset Turnover Ratio = sales / total_assets.

    Measures how efficiently a company uses its assets to generate revenue.
    Returns None if total_assets is zero or None.

    >>> round(asset_turnover(2000, 1000), 4)
    2.0
    >>> asset_turnover(2000, 0) is None
    True
    >>> asset_turnover(None, 1000) is None
    True
    """
    return _safe_div(sales, total_assets)


# ---------------------------------------------------------------------------
# ICR label & warning flag
# ---------------------------------------------------------------------------

ICR_DEBT_FREE_LABEL = "Debt Free"
ICR_WARNING_THRESHOLD = 1.5


def icr_label(interest: float | None) -> str | None:
    """
    Display label for ICR column.

    Returns 'Debt Free' when interest is zero or None (company has no debt).
    Returns None otherwise — caller computes and stores the numeric ICR value.

    This is stored in a separate icr_label column in financial_ratios table.

    >>> icr_label(0)
    'Debt Free'
    >>> icr_label(None)
    'Debt Free'
    >>> icr_label(100) is None
    True
    """
    if interest is None or interest == 0:
        return ICR_DEBT_FREE_LABEL
    return None


def icr_warning_flag(icr_value: float | None) -> bool:
    """
    ICR warning flag — True if company is at risk of not covering interest.

    Fires when ICR < 1.5. Returns False for None (debt-free or missing data).

    >>> icr_warning_flag(1.2)
    True
    >>> icr_warning_flag(1.5)
    False
    >>> icr_warning_flag(3.0)
    False
    >>> icr_warning_flag(None)
    False
    """
    if icr_value is None:
        return False
    return icr_value < ICR_WARNING_THRESHOLD


# ---------------------------------------------------------------------------
# High leverage flag
# ---------------------------------------------------------------------------

HIGH_LEVERAGE_THRESHOLD = 5.0


def high_leverage_flag(
    de: float | None,
    is_financial: bool = False,
) -> bool:
    """
    High leverage flag — True if D/E > 5 AND company is NOT in Financials sector.

    Financial companies (banks, NBFCs) operate with structurally high leverage
    so the threshold is not meaningful for them — flag is always False.

    Returns False for None D/E (debt-free or missing data).

    >>> high_leverage_flag(6.0)
    True
    >>> high_leverage_flag(6.0, is_financial=True)
    False
    >>> high_leverage_flag(4.9)
    False
    >>> high_leverage_flag(None)
    False
    >>> high_leverage_flag(5.0)
    False
    """
    if de is None or is_financial:
        return False
    return de > HIGH_LEVERAGE_THRESHOLD
