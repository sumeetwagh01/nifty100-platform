"""
pages/05_trends.py — Historical Trend Analysis
================================================
Sprint 4 Day 25: Full implementation.

Features
--------
- Company selector (search-enabled selectbox)
- Multi-metric selector — overlay up to 3 metrics on a 10-year line chart
- YoY % change annotation on every data point
- Metrics: Revenue, Net Profit, EPS, ROE, ROCE, D/E, NPM, FCF
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.dashboard.utils.db import get_ticker_list, get_trend_metrics

# ---------------------------------------------------------------------------
# Metric config
# ---------------------------------------------------------------------------
METRIC_CONFIG = {
    "Revenue (₹ Cr)":        ("sales",                  "#4f8ef7", False),
    "Net Profit (₹ Cr)":     ("net_profit",             "#22c55e", False),
    "EPS (₹)":               ("eps_in_rs",              "#f59e0b", False),
    "ROE (%)":               ("return_on_equity_pct",   "#a855f7", True),
    "ROCE (%)":              ("roce_pct",               "#ec4899", True),
    "D/E Ratio":             ("debt_to_equity",         "#ef4444", True),
    "Net Profit Margin (%)": ("net_profit_margin_pct",  "#14b8a6", True),
    "Free Cash Flow (₹ Cr)": ("free_cash_flow_cr",      "#f97316", False),
}

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("📊 Historical Trend Analysis")
st.caption("Sprint 4 · Day 25 · 10-year multi-metric overlay with YoY % change")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔍 Select Company")
    tickers = get_ticker_list()
    ticker = st.selectbox("Company (NSE Ticker)", tickers, index=0, key="trends_ticker")

    st.markdown("### 📈 Select Metrics (up to 3)")
    all_metric_names = list(METRIC_CONFIG.keys())
    selected_metrics = st.multiselect(
        "Metrics to overlay",
        options=all_metric_names,
        default=["Revenue (₹ Cr)", "Net Profit (₹ Cr)"],
        max_selections=3,
        key="trends_metrics",
    )

if not selected_metrics:
    st.warning("Please select at least one metric from the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = get_trend_metrics(ticker)

if df.empty:
    st.error(f"No data found for **{ticker}**.")
    st.stop()

# Parse year to numeric — handle both '2024' and '2024-03' formats
df["year_num"] = df["year"].astype(str).str[:4].astype(int)
df = df.sort_values("year_num").reset_index(drop=True)

# ---------------------------------------------------------------------------
# Build overlaid multi-metric chart
# ---------------------------------------------------------------------------
colors = ["#4f8ef7", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#14b8a6"]
fig = make_subplots(specs=[[{"secondary_y": True}]])

for i, metric_label in enumerate(selected_metrics):
    col, color, is_ratio = METRIC_CONFIG[metric_label]
    series = df[col].copy() if col in df.columns else pd.Series(dtype=float)
    years  = df["year_num"]

    # YoY % change
    yoy = series.pct_change() * 100
    yoy_text = [
        f"{v:+.1f}%" if pd.notna(v) and i > 0 else ""
        for i, v in enumerate(yoy)
    ]

    secondary = is_ratio and len(selected_metrics) > 1 and i > 0

    fig.add_trace(
        go.Scatter(
            x=years,
            y=series,
            name=metric_label,
            mode="lines+markers+text",
            line=dict(color=colors[i % len(colors)], width=2.5),
            marker=dict(size=8),
            text=yoy_text,
            textposition="top center",
            textfont=dict(size=10, color=colors[i % len(colors)]),
            hovertemplate=f"<b>{metric_label}</b><br>Year: %{{x}}<br>Value: %{{y:,.2f}}<extra></extra>",
        ),
        secondary_y=secondary,
    )

fig.update_layout(
    title=dict(text=f"<b>{ticker}</b> — {', '.join(selected_metrics)}", font=dict(size=18)),
    height=520,
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font=dict(color="#e0e6f0"),
    legend=dict(bgcolor="#1a1f2e", bordercolor="#2a3040", borderwidth=1),
    hovermode="x unified",
    xaxis=dict(
        title="Year",
        gridcolor="#2a3040",
        tickmode="linear",
        dtick=1,
    ),
    yaxis=dict(title=selected_metrics[0] if selected_metrics else "", gridcolor="#2a3040"),
    yaxis2=dict(title=selected_metrics[1] if len(selected_metrics) > 1 else "", gridcolor="#2a3040"),
    margin=dict(l=60, r=60, t=80, b=60),
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw data table (collapsible)
# ---------------------------------------------------------------------------
with st.expander("📋 Raw Data Table"):
    display_cols = ["year"]
    for m in selected_metrics:
        col, _, _ = METRIC_CONFIG[m]
        if col in df.columns:
            display_cols.append(col)
    st.dataframe(
        df[display_cols].rename(columns={METRIC_CONFIG[m][0]: m for m in selected_metrics}),
        use_container_width=True,
        hide_index=True,
    )
