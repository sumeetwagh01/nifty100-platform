"""
src/screener/scorer.py
======================
Sprint 3 Day 17 — Composite Quality Score engine.

Score breakdown (0–100 scale)
------------------------------
  35%  Profitability
         ROE          15%
         ROCE         10%
         NPM          10%
  30%  Cash Quality
         FCF CAGR     15%   (uses revenue_cagr_5yr as proxy if fcf_cagr unavailable)
         CFO/PAT      10%   (cfo_quality_score label → numeric)
         FCF positive  5%   (binary: FCF > 0)
  20%  Growth
         Revenue CAGR 10%
         PAT CAGR     10%
  15%  Leverage
         D/E score    10%   (lower is better)
         ICR score     5%   (higher is better, Debt Free = max)

Normalisation
-------------
  Each metric is winsorised at P10/P90 before scaling to 0–100.
  This caps extreme outliers without removing them.

  winsorised = clip(value, P10, P90)
  scaled     = (winsorised - P10) / (P90 - P10) * 100

  For "lower is better" metrics (D/E), the scale is inverted:
  scaled = 100 - (winsorised - P10) / (P90 - P10) * 100

Sector-relative score
---------------------
  After computing the absolute composite score, a sector-relative score
  is computed by normalising within each broad_sector peer group.
  This reflects performance vs sector peers, not the full universe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# CFO quality label → numeric
# ---------------------------------------------------------------------------

CFO_QUALITY_MAP = {
    "High Quality": 100.0,
    "Moderate":      50.0,
    "Accrual Risk":   0.0,
}

DEBT_FREE_ICR = 999.0   # sentinel for ICR when company is debt-free


# ---------------------------------------------------------------------------
# Winsorisation helper
# ---------------------------------------------------------------------------

def winsorise(series: pd.Series, p_low: float = 10, p_high: float = 90) -> pd.Series:
    """
    Clip series at P10 and P90 percentiles.
    Returns original series if all values are NaN or P10 == P90.
    """
    lo = series.quantile(p_low / 100)
    hi = series.quantile(p_high / 100)
    if pd.isna(lo) or pd.isna(hi) or lo == hi:
        return series
    return series.clip(lower=lo, upper=hi)


def scale_0_100(
    series: pd.Series,
    invert: bool = False,
    p_low: float = 10,
    p_high: float = 90,
) -> pd.Series:
    """
    Winsorise then scale to 0–100.

    Parameters
    ----------
    invert : if True, lower values score higher (e.g. D/E ratio)
    """
    ws = winsorise(series, p_low, p_high)
    lo = ws.quantile(p_low / 100)
    hi = ws.quantile(p_high / 100)

    if pd.isna(lo) or pd.isna(hi) or lo == hi:
        return pd.Series(50.0, index=series.index)   # neutral if no range

    scaled = (ws - lo) / (hi - lo) * 100.0
    if invert:
        scaled = 100.0 - scaled
    return scaled.clip(0, 100)


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------

def _score_profitability(df: pd.DataFrame) -> pd.Series:
    """35% weight: ROE(15) + ROCE(10) + NPM(10)."""
    roe_s  = scale_0_100(df.get("return_on_equity_pct",  pd.Series(dtype=float))) * 0.15
    roce_s = scale_0_100(df.get("roce_pct",              pd.Series(dtype=float))) * 0.10
    npm_s  = scale_0_100(df.get("net_profit_margin_pct", pd.Series(dtype=float))) * 0.10

    # Align index
    return roe_s.fillna(0) + roce_s.reindex(df.index).fillna(0) + npm_s.reindex(df.index).fillna(0)


def _score_cash_quality(df: pd.DataFrame) -> pd.Series:
    """30% weight: FCF CAGR(15) + CFO quality(10) + FCF positive flag(5)."""
    # FCF CAGR — use revenue_cagr_5yr as proxy if fcf_cagr not available
    fcf_cagr_col = "fcf_cagr_5yr" if "fcf_cagr_5yr" in df.columns else "revenue_cagr_5yr"
    fcf_cagr_s = scale_0_100(pd.to_numeric(df.get(fcf_cagr_col, pd.Series(dtype=float)), errors="coerce")) * 0.15

    # CFO quality: map label to numeric
    cfo_numeric = df.get("cfo_quality_score", pd.Series(dtype=str)).map(CFO_QUALITY_MAP).fillna(50.0)
    cfo_s = (cfo_numeric / 100.0) * 10.0   # already 0-100, scale to weight

    # FCF positive flag: binary 0 or 5
    fcf_vals = pd.to_numeric(df.get("free_cash_flow_cr", pd.Series(dtype=float)), errors="coerce")
    fcf_flag_s = (fcf_vals > 0).fillna(False).astype(float) * 5.0

    return fcf_cagr_s.reindex(df.index).fillna(0) + cfo_s.reindex(df.index).fillna(0) + fcf_flag_s.reindex(df.index).fillna(0)


def _score_growth(df: pd.DataFrame) -> pd.Series:
    """20% weight: Revenue CAGR(10) + PAT CAGR(10)."""
    rev_s = scale_0_100(pd.to_numeric(df.get("revenue_cagr_5yr", pd.Series(dtype=float)), errors="coerce")) * 0.10
    pat_s = scale_0_100(pd.to_numeric(df.get("pat_cagr_5yr",     pd.Series(dtype=float)), errors="coerce")) * 0.10
    return rev_s.reindex(df.index).fillna(0) + pat_s.reindex(df.index).fillna(0)


def _score_leverage(df: pd.DataFrame) -> pd.Series:
    """15% weight: D/E(10, lower better) + ICR(5, higher better)."""
    de_vals = pd.to_numeric(df.get("debt_to_equity", pd.Series(dtype=float)), errors="coerce")
    de_s = scale_0_100(de_vals, invert=True) * 0.10   # lower D/E = higher score

    # ICR — treat Debt Free as max
    icr_vals = pd.to_numeric(df.get("interest_coverage", pd.Series(dtype=float)), errors="coerce").copy()
    if "icr_label" in df.columns:
        debt_free_mask = df["icr_label"] == "Debt Free"
        icr_vals = icr_vals.copy()
        icr_vals[debt_free_mask] = DEBT_FREE_ICR
    icr_s = scale_0_100(icr_vals) * 0.05

    return de_s.reindex(df.index).fillna(0) + icr_s.reindex(df.index).fillna(0)


# ---------------------------------------------------------------------------
# Main composite scorer
# ---------------------------------------------------------------------------

def compute_composite_score(df: pd.DataFrame) -> pd.Series:
    """
    Compute composite quality score (0–100) for each row in df.

    Uses P10/P90 winsorisation on each component before scaling.
    Weights: Profitability 35% + Cash Quality 30% + Growth 20% + Leverage 15%

    Returns pd.Series of scores indexed to df.
    """
    if df.empty:
        return pd.Series(dtype=float)

    prof = _score_profitability(df)
    cash = _score_cash_quality(df)
    grow = _score_growth(df)
    lev  = _score_leverage(df)

    total = (prof + cash + grow + lev).clip(0, 100).round(2)
    return total


def compute_sector_relative_score(df: pd.DataFrame) -> pd.Series:
    """
    Sector-relative composite score (0–100).

    Normalises composite_quality_score within each broad_sector peer group.
    Companies are ranked relative to their sector peers, not the full universe.

    Returns pd.Series of sector-relative scores indexed to df.
    """
    if df.empty or "composite_quality_score" not in df.columns:
        return pd.Series(dtype=float)

    sector_col = "broad_sector" if "broad_sector" in df.columns else None
    if sector_col is None:
        return df["composite_quality_score"]

    result = pd.Series(index=df.index, dtype=float)

    for sector, grp in df.groupby(sector_col):
        scores = grp["composite_quality_score"].dropna()
        if len(scores) == 0:
            continue
        lo, hi = scores.min(), scores.max()
        if lo == hi:
            result.loc[grp.index] = 50.0
        else:
            scaled = (grp["composite_quality_score"] - lo) / (hi - lo) * 100.0
            result.loc[grp.index] = scaled.clip(0, 100).round(2)

    return result


def add_scores_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add composite_quality_score and sector_relative_score columns to df.

    Returns df with two new columns added.
    """
    result = df.copy()
    result["composite_quality_score"]  = compute_composite_score(df)
    result["sector_relative_score"]    = compute_sector_relative_score(result)
    return result
