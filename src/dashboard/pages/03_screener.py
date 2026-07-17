"""
pages/03_screener.py — Stock Screener
=======================================
Sprint 4 Day 24: Full implementation.

Features
--------
- 10 metric sliders in sidebar (ROE min, D/E max, FCF min, Rev CAGR min,
  PAT CAGR min, OPM/NPM min, P/E max, P/B max, Dividend Yield min, ICR min)
- 6 preset filter buttons that auto-fill sliders via session state
- Live-updating results table with result count label
- CSV download button for all visible columns
"""

from __future__ import annotations

import sys
from pathlib import Path
# Each page runs in an isolated exec() context — must patch sys.path here.
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import io

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import get_screener_data

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🔍 Stock Screener")
st.caption("Sprint 4 · Day 24 · Filter 92 Nifty 100 companies by 10 financial metrics")

# ---------------------------------------------------------------------------
# Slider bounds (based on actual DB data ranges)
# ---------------------------------------------------------------------------
ROE_MAX       = 65.0
DE_MAX        = 15.0
FCF_MIN       = -30_000.0
FCF_MAX       = 36_000.0
REVCAGR_MAX   = 22.0
PATCAGR_MAX   = 86.0
NPM_MAX       = 33.0
PE_MAX        = 80.0
PB_MAX        = 15.0
DIV_MAX       = 4.5
ICR_MAX       = 70.0

# ---------------------------------------------------------------------------
# Session-state defaults — only set if not already present
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, float] = {
    "scr_roe_min":      0.0,
    "scr_de_max":       DE_MAX,
    "scr_fcf_min":      FCF_MIN,
    "scr_revcagr_min":  0.0,
    "scr_patcagr_min":  0.0,
    "scr_npm_min":      0.0,
    "scr_pe_max":       PE_MAX,
    "scr_pb_max":       PB_MAX,
    "scr_div_min":      0.0,
    "scr_icr_min":      0.0,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Preset definitions — (key, value) pairs to snap
# ---------------------------------------------------------------------------
PRESETS: dict[str, dict[str, float]] = {
    "🏆 Quality": {
        "scr_roe_min":     15.0,
        "scr_de_max":       1.0,
        "scr_npm_min":     15.0,
        "scr_fcf_min":      0.0,
        "scr_revcagr_min":  0.0,
        "scr_patcagr_min":  0.0,
        "scr_pe_max":      PE_MAX,
        "scr_pb_max":      PB_MAX,
        "scr_div_min":      0.0,
        "scr_icr_min":      0.0,
    },
    "💰 Value": {
        "scr_roe_min":      0.0,
        "scr_de_max":       5.0,
        "scr_npm_min":      0.0,
        "scr_fcf_min":    FCF_MIN,
        "scr_revcagr_min":  0.0,
        "scr_patcagr_min":  0.0,
        "scr_pe_max":      20.0,
        "scr_pb_max":       3.0,
        "scr_div_min":      0.0,
        "scr_icr_min":      0.0,
    },
    "🚀 Growth": {
        "scr_roe_min":      0.0,
        "scr_de_max":       5.0,
        "scr_npm_min":      0.0,
        "scr_fcf_min":    FCF_MIN,
        "scr_revcagr_min": 15.0,
        "scr_patcagr_min": 15.0,
        "scr_pe_max":      PE_MAX,
        "scr_pb_max":      PB_MAX,
        "scr_div_min":      0.0,
        "scr_icr_min":      0.0,
    },
    "📈 Dividend": {
        "scr_roe_min":      0.0,
        "scr_de_max":       5.0,
        "scr_npm_min":      0.0,
        "scr_fcf_min":    FCF_MIN,
        "scr_revcagr_min":  0.0,
        "scr_patcagr_min":  0.0,
        "scr_pe_max":      PE_MAX,
        "scr_pb_max":      PB_MAX,
        "scr_div_min":      2.0,
        "scr_icr_min":      0.0,
    },
    "🏦 Debt-Free": {
        "scr_roe_min":      0.0,
        "scr_de_max":       0.3,
        "scr_npm_min":      0.0,
        "scr_fcf_min":    FCF_MIN,
        "scr_revcagr_min":  0.0,
        "scr_patcagr_min":  0.0,
        "scr_pe_max":      PE_MAX,
        "scr_pb_max":      PB_MAX,
        "scr_div_min":      0.0,
        "scr_icr_min":      0.0,
    },
    "🔄 Turnaround": {
        "scr_roe_min":      0.0,
        "scr_de_max":      10.0,
        "scr_npm_min":      0.0,
        "scr_fcf_min":  -5_000.0,
        "scr_revcagr_min": 10.0,
        "scr_patcagr_min":  0.0,
        "scr_pe_max":      PE_MAX,
        "scr_pb_max":      PB_MAX,
        "scr_div_min":      0.0,
        "scr_icr_min":      0.0,
    },
}

# ---------------------------------------------------------------------------
# Sidebar — preset buttons + sliders
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎯 Preset Filters")
    preset_names = list(PRESETS.keys())
    p_cols = st.columns(2)
    for i, name in enumerate(preset_names):
        with p_cols[i % 2]:
            if st.button(name, use_container_width=True, key=f"btn_{i}"):
                for k, v in PRESETS[name].items():
                    st.session_state[k] = v
                st.rerun()

    # Reset button
    if st.button("↺ Reset All", use_container_width=True):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

    st.divider()
    st.markdown("### 🎛️ Metric Filters")
    st.caption("Filters only apply when moved from their default position.")

    roe_min = st.slider(
        "ROE min (%)",
        min_value=0.0, max_value=ROE_MAX, step=1.0,
        key="scr_roe_min",
        help="Return on Equity — minimum threshold",
    )
    de_max = st.slider(
        "D/E max (×)",
        min_value=0.0, max_value=DE_MAX, step=0.1,
        key="scr_de_max",
        help="Debt-to-Equity — maximum allowed (slide left to tighten)",
    )
    fcf_min = st.slider(
        "FCF min (₹ Cr)",
        min_value=FCF_MIN, max_value=FCF_MAX, step=1_000.0,
        key="scr_fcf_min",
        format="%.0f",
        help="Free Cash Flow — minimum threshold in ₹ Crore",
    )
    revcagr_min = st.slider(
        "Revenue CAGR 5yr min (%)",
        min_value=0.0, max_value=REVCAGR_MAX, step=0.5,
        key="scr_revcagr_min",
        help="5-year Revenue CAGR — minimum growth rate",
    )
    patcagr_min = st.slider(
        "PAT CAGR 5yr min (%)",
        min_value=0.0, max_value=PATCAGR_MAX, step=1.0,
        key="scr_patcagr_min",
        help="5-year Profit After Tax CAGR — minimum growth rate",
    )
    npm_min = st.slider(
        "OPM / NPM min (%)",
        min_value=0.0, max_value=NPM_MAX, step=0.5,
        key="scr_npm_min",
        help="Net Profit Margin — minimum threshold",
    )
    pe_max = st.slider(
        "P/E max (×)",
        min_value=0.0, max_value=PE_MAX, step=1.0,
        key="scr_pe_max",
        help="Price-to-Earnings — maximum allowed",
    )
    pb_max = st.slider(
        "P/B max (×)",
        min_value=0.0, max_value=PB_MAX, step=0.25,
        key="scr_pb_max",
        help="Price-to-Book — maximum allowed",
    )
    div_min = st.slider(
        "Dividend Yield min (%)",
        min_value=0.0, max_value=DIV_MAX, step=0.1,
        key="scr_div_min",
        help="Dividend Yield — minimum threshold",
    )
    icr_min = st.slider(
        "ICR min (×)",
        min_value=0.0, max_value=ICR_MAX, step=0.5,
        key="scr_icr_min",
        help="Interest Coverage Ratio — minimum (0 = include all)",
    )

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading screener data…"):
    df = get_screener_data()

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
mask = pd.Series([True] * len(df), index=df.index)

# Min filters — only activate when moved above minimum (0.0)
if roe_min > 0:
    mask &= df["return_on_equity_pct"].notna() & (df["return_on_equity_pct"] >= roe_min)

if revcagr_min > 0:
    mask &= df["revenue_cagr_5yr"].notna() & (df["revenue_cagr_5yr"] >= revcagr_min)

if patcagr_min > 0:
    mask &= df["pat_cagr_5yr"].notna() & (df["pat_cagr_5yr"] >= patcagr_min)

if npm_min > 0:
    mask &= df["net_profit_margin_pct"].notna() & (df["net_profit_margin_pct"] >= npm_min)

if fcf_min > FCF_MIN:
    mask &= df["free_cash_flow_cr"].notna() & (df["free_cash_flow_cr"] >= fcf_min)

if icr_min > 0:
    mask &= df["interest_coverage"].notna() & (df["interest_coverage"] >= icr_min)

if div_min > 0:
    mask &= df["dividend_yield_pct"].notna() & (df["dividend_yield_pct"] >= div_min)

# Max filters — only activate when moved below maximum
if de_max < DE_MAX:
    mask &= df["debt_to_equity"].notna() & (df["debt_to_equity"] <= de_max)

if pe_max < PE_MAX:
    mask &= df["pe_ratio"].notna() & (df["pe_ratio"] <= pe_max)

if pb_max < PB_MAX:
    mask &= df["pb_ratio"].notna() & (df["pb_ratio"] <= pb_max)

filtered = df[mask].copy()

# ---------------------------------------------------------------------------
# Result count label
# ---------------------------------------------------------------------------
total = len(df)
matched = len(filtered)

count_color = "#4ff7a4" if matched >= 10 else ("#f7e14f" if matched >= 3 else "#f74f4f")
st.markdown(
    f"<h4 style='color:{count_color};margin:0 0 0.5rem;'>"
    f"{'✅' if matched > 0 else '❌'} "
    f"{matched} {'company matches' if matched == 1 else 'companies match'} your filters"
    f"<span style='color:#8a94a6;font-size:0.9rem;font-weight:400;'> &nbsp;(out of {total})</span>"
    f"</h4>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Build display table
# ---------------------------------------------------------------------------
DISPLAY_COLS = {
    "company_id":             "Ticker",
    "company_name":           "Company",
    "broad_sector":           "Sector",
    "composite_quality_score": "Quality ★",
    "return_on_equity_pct":   "ROE %",
    "debt_to_equity":         "D/E",
    "net_profit_margin_pct":  "NPM %",
    "pe_ratio":               "P/E",
    "pb_ratio":               "P/B",
    "dividend_yield_pct":     "Div Yield %",
    "revenue_cagr_5yr":       "Rev CAGR 5yr",
    "pat_cagr_5yr":           "PAT CAGR 5yr",
    "free_cash_flow_cr":      "FCF (₹ Cr)",
    "interest_coverage":      "ICR",
}

display = filtered[list(DISPLAY_COLS.keys())].rename(columns=DISPLAY_COLS).reset_index(drop=True)
display.index = display.index + 1  # 1-based

if display.empty:
    st.warning("No companies match the current filters. Try relaxing one or more sliders.")
else:
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=False,
        column_config={
            "Ticker":       st.column_config.TextColumn("Ticker", width="small"),
            "Quality ★":    st.column_config.NumberColumn("Quality ★",    format="%.1f"),
            "ROE %":        st.column_config.NumberColumn("ROE %",        format="%.1f"),
            "D/E":          st.column_config.NumberColumn("D/E",          format="%.2f"),
            "NPM %":        st.column_config.NumberColumn("NPM %",        format="%.1f"),
            "P/E":          st.column_config.NumberColumn("P/E",          format="%.1f"),
            "P/B":          st.column_config.NumberColumn("P/B",          format="%.2f"),
            "Div Yield %":  st.column_config.NumberColumn("Div Yield %",  format="%.2f"),
            "Rev CAGR 5yr": st.column_config.NumberColumn("Rev CAGR 5yr", format="%.1f"),
            "PAT CAGR 5yr": st.column_config.NumberColumn("PAT CAGR 5yr", format="%.1f"),
            "FCF (₹ Cr)":   st.column_config.NumberColumn("FCF (₹ Cr)",   format="%.0f"),
            "ICR":          st.column_config.NumberColumn("ICR",          format="%.1f"),
        },
        height=min(40 + matched * 35, 600),
    )

    # CSV download
    st.divider()
    col_dl, col_info = st.columns([1, 3])
    with col_dl:
        csv_bytes = display.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download CSV",
            data=csv_bytes,
            file_name="nifty100_screener_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_info:
        st.caption(
            f"Downloading {matched} companies · {len(DISPLAY_COLS)} columns · "
            "nifty100_screener_results.csv"
        )
