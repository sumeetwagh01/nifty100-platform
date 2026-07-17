"""
src/analytics/cashflow_kpis.py
==============================
Sprint 2 Day 11 — Cash Flow KPIs & Capital Allocation patterns.

KPIs implemented
----------------
  FCF              Free Cash Flow           = operating_activity + investing_activity
  CFO Quality      CFO/PAT avg over 5yr     → High Quality / Moderate / Accrual Risk
  CapEx Intensity  abs(investing) / sales   → Asset Light / Moderate / Capital Intensive
  FCF Conversion   FCF / operating_profit   → None if operating_profit = 0
  Capital Alloc    sign(CFO,CFI,CFF)        → 8 pattern labels

Screener.in column mapping
--------------------------
  operating_activity  → cashflow.operating_activity   (CFO)
  investing_activity  → cashflow.investing_activity   (CFI)
  financing_activity  → cashflow.financing_activity   (CFF)
  net_profit          → profitandloss.net_profit       (PAT)
  sales               → profitandloss.sales
  operating_profit    → profitandloss.operating_profit

Capital Allocation Patterns (sign of CFO, CFI, CFF)
----------------------------------------------------
  (+,-,-)  Reinvestor               — profitable, investing, returning cash
  (+,-,-)  Shareholder Returns      — same signs but high CFO/PAT ratio
  (+,+,-)  Liquidating Assets       — selling assets, paying down debt
  (-,+,+)  Distress Signal          — losing money, selling assets, borrowing
  (-,-,+)  Growth Funded by Debt    — investing for growth via debt
  (+,+,+)  Cash Accumulator         — cash piling up across all activities
  (-,-,-)  Pre-Revenue              — burning cash across the board
  (+,-,+)  Mixed                    — profitable but complex financing
"""

from __future__ import annotations
import csv
import os

# ---------------------------------------------------------------------------
# CFO Quality thresholds
# ---------------------------------------------------------------------------

CFO_QUALITY_HIGH = 1.0
CFO_QUALITY_MODERATE_LOW = 0.5

CFO_QUALITY_HIGH_LABEL = "High Quality"
CFO_QUALITY_MODERATE_LABEL = "Moderate"
CFO_QUALITY_ACCRUAL_LABEL = "Accrual Risk"

# ---------------------------------------------------------------------------
# CapEx Intensity thresholds
# ---------------------------------------------------------------------------

CAPEX_ASSET_LIGHT_MAX = 3.0      # < 3%
CAPEX_MODERATE_MAX = 8.0         # 3–8%
                                  # > 8% = Capital Intensive

CAPEX_ASSET_LIGHT_LABEL = "Asset Light"
CAPEX_MODERATE_LABEL = "Moderate"
CAPEX_INTENSIVE_LABEL = "Capital Intensive"

# ---------------------------------------------------------------------------
# Free Cash Flow
# ---------------------------------------------------------------------------

def fcf(
    operating_activity: float | None,
    investing_activity: float | None,
) -> float | None:
    """
    Free Cash Flow = operating_activity + investing_activity.

    Negative FCF is valid and returned as-is.
    Returns None only if operating_activity is None
    (investing_activity treated as 0 if None).

    >>> fcf(500, -200)
    300.0
    >>> fcf(500, None)
    500.0
    >>> fcf(None, -200) is None
    True
    >>> fcf(-100, -50)
    -150.0
    """
    if operating_activity is None:
        return None
    inv = investing_activity or 0.0
    return float(operating_activity) + inv


# ---------------------------------------------------------------------------
# CFO Quality Score
# ---------------------------------------------------------------------------

def cfo_quality_score(
    cfo_series: list[float | None],
    pat_series: list[float | None],
) -> str | None:
    """
    CFO Quality Score — avg(CFO/PAT) over up to 5 years.

    Uses the most recent 5 year-pairs available (zip of both series,
    taking last 5). Skips any year where PAT = 0 or either value is None.

    Returns
    -------
    'High Quality'  → avg ratio > 1.0
    'Moderate'      → 0.5 <= avg ratio <= 1.0
    'Accrual Risk'  → avg ratio < 0.5
    None            → no valid year-pairs to compute

    >>> cfo_quality_score([120, 130, 140, 150, 160], [100, 110, 120, 130, 140])
    'High Quality'
    >>> cfo_quality_score([40, 50, 60], [100, 110, 120])
    'Accrual Risk'
    >>> cfo_quality_score([60, 70, 80], [100, 110, 120])
    'Moderate'
    >>> cfo_quality_score([100], [0]) is None
    True
    """
    if not cfo_series or not pat_series:
        return None

    # Take last 5 pairs
    pairs = list(zip(cfo_series, pat_series))[-5:]

    ratios = []
    for cfo, pat in pairs:
        if cfo is None or pat is None or pat == 0:
            continue
        ratios.append(cfo / pat)

    if not ratios:
        return None

    avg = sum(ratios) / len(ratios)

    if avg > CFO_QUALITY_HIGH:
        return CFO_QUALITY_HIGH_LABEL
    if avg >= CFO_QUALITY_MODERATE_LOW:
        return CFO_QUALITY_MODERATE_LABEL
    return CFO_QUALITY_ACCRUAL_LABEL


# ---------------------------------------------------------------------------
# CapEx Intensity
# ---------------------------------------------------------------------------

def capex_intensity(
    investing_activity: float | None,
    sales: float | None,
) -> tuple[float | None, str | None]:
    """
    CapEx Intensity = abs(investing_activity) / sales * 100.

    Returns (value_pct, label) tuple.
    Returns (None, None) if sales = 0 or either input is None.

    Note: investing_activity is typically negative on the cash flow statement
    (cash outflow for capex). abs() is applied so intensity is always positive.

    >>> capex_intensity(-200, 5000)
    (4.0, 'Moderate')
    >>> capex_intensity(-100, 5000)
    (2.0, 'Asset Light')
    >>> capex_intensity(-500, 5000)
    (10.0, 'Capital Intensive')
    >>> capex_intensity(None, 5000)
    (None, None)
    >>> capex_intensity(-200, 0)
    (None, None)
    """
    if investing_activity is None or sales is None or sales == 0:
        return (None, None)

    pct = (abs(investing_activity) / sales) * 100.0

    if pct < CAPEX_ASSET_LIGHT_MAX:
        label = CAPEX_ASSET_LIGHT_LABEL
    elif pct <= CAPEX_MODERATE_MAX:
        label = CAPEX_MODERATE_LABEL
    else:
        label = CAPEX_INTENSIVE_LABEL

    return (round(pct, 4), label)


# ---------------------------------------------------------------------------
# FCF Conversion Rate
# ---------------------------------------------------------------------------

def fcf_conversion(
    fcf_value: float | None,
    operating_profit: float | None,
) -> float | None:
    """
    FCF Conversion Rate = FCF / operating_profit * 100.

    Measures what fraction of operating profit converts to free cash flow.
    Returns None if operating_profit = 0 or either input is None.

    >>> round(fcf_conversion(300, 500), 4)
    60.0
    >>> fcf_conversion(300, 0) is None
    True
    >>> fcf_conversion(None, 500) is None
    True
    >>> round(fcf_conversion(-100, 500), 4)
    -20.0
    """
    if fcf_value is None or operating_profit is None or operating_profit == 0:
        return None
    return (fcf_value / operating_profit) * 100.0


# ---------------------------------------------------------------------------
# Capital Allocation Pattern classifier
# ---------------------------------------------------------------------------

def _sign(value: float | None) -> str | None:
    """Return '+' for positive, '-' for zero or negative, None if missing."""
    if value is None:
        return None
    return "+" if value > 0 else "-"


def capital_allocation_pattern(
    cfo: float | None,
    cfi: float | None,
    cff: float | None,
) -> str:
    """
    Classify capital allocation strategy from cash flow signs.

    Parameters
    ----------
    cfo : cashflow.operating_activity
    cfi : cashflow.investing_activity
    cff : cashflow.financing_activity

    Returns one of 8 pattern labels, or 'Unknown' if any input is None.

    Pattern table:
      (+,-,-)  Reinvestor
      (+,-,+)  Mixed
      (+,+,-)  Liquidating Assets
      (+,+,+)  Cash Accumulator
      (-,+,+)  Distress Signal
      (-,-,+)  Growth Funded by Debt
      (-,-,-)  Pre-Revenue
      (-,+,-)  Shareholder Returns   ← CFI positive = asset sales funding returns

    Note: Spec says (+,-,-) with high CFO/PAT = Shareholder Returns.
    We classify the base pattern here; caller can override to
    Shareholder Returns if cfo_quality_score == 'High Quality'.

    >>> capital_allocation_pattern(500, -200, -100)
    'Reinvestor'
    >>> capital_allocation_pattern(-300, -200, 400)
    'Growth Funded by Debt'
    >>> capital_allocation_pattern(None, -200, -100)
    'Unknown'
    """
    s_cfo = _sign(cfo)
    s_cfi = _sign(cfi)
    s_cff = _sign(cff)

    if None in (s_cfo, s_cfi, s_cff):
        return "Unknown"

    pattern_map = {
        ("+", "-", "-"): "Reinvestor",
        ("+", "-", "+"): "Mixed",
        ("+", "+", "-"): "Liquidating Assets",
        ("+", "+", "+"): "Cash Accumulator",
        ("-", "+", "+"): "Distress Signal",
        ("-", "-", "+"): "Growth Funded by Debt",
        ("-", "-", "-"): "Pre-Revenue",
        ("-", "+", "-"): "Shareholder Returns",
    }

    key = (s_cfo, s_cfi, s_cff)
    return pattern_map.get(key, "Unknown")


# ---------------------------------------------------------------------------
# CSV generator
# ---------------------------------------------------------------------------

def generate_capital_allocation_csv(
    rows: list[dict],
    output_path: str = "output/capital_allocation.csv",
) -> int:
    """
    Write capital allocation results to output/capital_allocation.csv.

    Parameters
    ----------
    rows : list of dicts, each with keys:
        company_id, year, cfo_sign, cfi_sign, cff_sign, pattern_label
    output_path : destination path (default: output/capital_allocation.csv)

    Returns number of rows written.

    Each row is produced by the caller iterating over the cashflow table
    and calling capital_allocation_pattern() per company-year.
    """
    if not rows:
        return 0

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fieldnames = ["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)
