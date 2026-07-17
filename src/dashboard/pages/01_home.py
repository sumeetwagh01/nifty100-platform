"""
pages/01_home.py — Home / Dashboard Overview
=============================================
Sprint 4 Day 23: Full implementation.

Features
--------
- Sidebar year selector (2019–2024) — all widgets react to year change
- 6 summary KPI tiles: Avg ROE, Median P/E, Median D/E, Total Companies,
  Median Revenue CAGR 5yr, Debt-Free Companies count
- Sector breakdown donut chart (Plotly) — 11 sectors with company count
- Top-5 companies by composite quality score (table)
"""

from __future__ import annotations

import sys
from pathlib import Path
# Each page runs in an isolated exec() context — must patch sys.path here.
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import get_companies, get_home_summary, get_sectors

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🏠 Nifty 100 — Dashboard Home")
st.caption("Sprint 4 · Day 23 · Financial Intelligence Platform")

# ---------------------------------------------------------------------------
# Sidebar — year selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📅 Select Year")
    selected_year = st.selectbox(
        "Analysis Year",
        options=list(range(2024, 2018, -1)),
        index=0,
        key="home_year",
    )
    st.divider()
    st.markdown(
        "<div style='font-size:0.78rem;color:#8a94a6;'>"
        "All metrics update when you change the year."
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading dashboard data…"):
    summary_df = get_home_summary(selected_year)
    companies_df = get_companies()
    sectors_df = get_sectors()

# ---------------------------------------------------------------------------
# Helper — safe median
# ---------------------------------------------------------------------------
def _median(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.median()) if not s.empty else None


def _fmt(val: float | None, suffix: str = "", decimals: int = 1) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}{suffix}"


# ---------------------------------------------------------------------------
# 6 KPI tiles
# ---------------------------------------------------------------------------
avg_roe     = _median(summary_df["return_on_equity_pct"])
median_pe   = _median(summary_df["pe_ratio"])
median_de   = _median(summary_df["debt_to_equity"])
total_cos   = len(companies_df)
med_rev_cagr = _median(summary_df["revenue_cagr_5yr"])
debt_free   = int((summary_df["debt_to_equity"].fillna(1) == 0).sum()) if not summary_df.empty else 0

st.markdown("#### 📊 Market Snapshot — " + str(selected_year))

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric(
        label="⚡ Avg ROE",
        value=_fmt(avg_roe, "%"),
        help="Median Return on Equity across all companies for this year",
    )
with col2:
    st.metric(
        label="💹 Median P/E",
        value=_fmt(median_pe, "x"),
        help="Median Price-to-Earnings ratio (from market cap table)",
    )
with col3:
    st.metric(
        label="⚖️ Median D/E",
        value=_fmt(median_de, "x"),
        help="Median Debt-to-Equity ratio",
    )
with col4:
    st.metric(
        label="🏢 Companies",
        value=str(total_cos),
        help="Total Nifty 100 companies in the platform",
    )
with col5:
    st.metric(
        label="📈 Rev CAGR 5yr",
        value=_fmt(med_rev_cagr, "%"),
        help="Median Revenue CAGR over 5 years",
    )
with col6:
    st.metric(
        label="🏦 Debt-Free",
        value=str(debt_free),
        help="Number of companies with zero debt (D/E = 0) for this year",
    )

st.divider()

# ---------------------------------------------------------------------------
# Layout: donut chart (left) + top-5 table (right)
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1.1, 1], gap="large")

# ── Sector Donut Chart ───────────────────────────────────────────────────────
with left_col:
    st.markdown("#### 🥧 Sector Breakdown")

    sector_counts = (
        sectors_df.groupby("broad_sector", dropna=True)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # Colour palette — distinct shades for up to 11 sectors
    PALETTE = [
        "#4f8ef7", "#f7a44f", "#4ff7a4", "#f74f79", "#a44ff7",
        "#f7e14f", "#4fc4f7", "#f74fc4", "#7af74f", "#f74f4f",
        "#4ff7e1",
    ]

    fig_donut = go.Figure(
        go.Pie(
            labels=sector_counts["broad_sector"],
            values=sector_counts["count"],
            hole=0.52,
            marker_colors=PALETTE[: len(sector_counts)],
            textinfo="label+percent",
            textposition="outside",
            hovertemplate="<b>%{label}</b><br>Companies: %{value}<br>Share: %{percent}<extra></extra>",
            pull=[0.04] + [0] * (len(sector_counts) - 1),
        )
    )
    fig_donut.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20, l=10, r=10),
        height=380,
        showlegend=False,
        annotations=[
            dict(
                text=f"<b>{len(companies_df)}</b><br>cos",
                x=0.5, y=0.5,
                font=dict(size=18, color="#e0e6f0"),
                showarrow=False,
            )
        ],
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# ── Top-5 Quality Score Table ────────────────────────────────────────────────
with right_col:
    st.markdown(f"#### 🏆 Top 5 by Quality Score — {selected_year}")

    if summary_df.empty:
        st.info(f"No financial_ratios data found for {selected_year}. Try an earlier year.")
    else:
        top5 = (
            summary_df[["company_id", "company_name", "broad_sector",
                         "composite_quality_score", "return_on_equity_pct", "roce_pct"]]
            .dropna(subset=["composite_quality_score"])
            .sort_values("composite_quality_score", ascending=False)
            .head(5)
            .reset_index(drop=True)
        )
        top5.index = top5.index + 1  # 1-based rank

        top5 = top5.rename(columns={
            "company_id":             "Ticker",
            "company_name":           "Company",
            "broad_sector":           "Sector",
            "composite_quality_score": "Quality ★",
            "return_on_equity_pct":   "ROE %",
            "roce_pct":               "ROCE %",
        })

        # Style the table
        def _style_score(val):
            if isinstance(val, float):
                if val >= 85:
                    return "color: #4ff7a4; font-weight:700"
                elif val >= 70:
                    return "color: #f7e14f;"
            return ""

        styled = (
            top5.style
            .format({
                "Quality ★": "{:.1f}",
                "ROE %":     lambda x: f"{x:.1f}" if pd.notna(x) else "—",
                "ROCE %":    lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            })
            .map(_style_score, subset=["Quality ★"])
            .set_properties(**{"text-align": "center"})
            .set_table_styles([
                {"selector": "th", "props": [("background-color", "#1a1f2e"), ("color", "#8a94a6"), ("font-size", "0.82rem")]},
                {"selector": "td", "props": [("background-color", "#0e1117"), ("color", "#e0e6f0"), ("font-size", "0.88rem"), ("padding", "0.45rem 0.6rem")]},
                {"selector": "tr:hover td", "props": [("background-color", "#1a1f2e")]},
            ])
        )

        st.dataframe(
            top5,
            use_container_width=True,
            hide_index=False,
            column_config={
                "Ticker":    st.column_config.TextColumn("Ticker", width="small"),
                "Quality ★": st.column_config.NumberColumn("Quality ★", format="%.1f"),
                "ROE %":     st.column_config.NumberColumn("ROE %",     format="%.1f"),
                "ROCE %":    st.column_config.NumberColumn("ROCE %",    format="%.1f"),
            },
        )

        # Mini context note
        st.markdown(
            "<div style='font-size:0.76rem;color:#8a94a6;margin-top:0.4rem;'>"
            f"Ranked by composite quality score · {selected_year} data"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Quick all-sector summary below the table ─────────────────────────────
    st.markdown("---")
    st.markdown("#### 📋 All Sectors at a Glance")
    sector_summary = (
        summary_df
        .groupby("broad_sector", dropna=True)
        .agg(
            Companies=("company_id", "count"),
            Avg_ROE=("return_on_equity_pct", "median"),
            Avg_ROCE=("roce_pct", "median"),
        )
        .reset_index()
        .rename(columns={
            "broad_sector": "Sector",
            "Avg_ROE":      "Med ROE %",
            "Avg_ROCE":     "Med ROCE %",
        })
        .sort_values("Med ROE %", ascending=False)
    )

    if not sector_summary.empty:
        st.dataframe(
            sector_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sector":     st.column_config.TextColumn("Sector"),
                "Companies":  st.column_config.NumberColumn("Cos", format="%d"),
                "Med ROE %":  st.column_config.NumberColumn("Med ROE %",  format="%.1f"),
                "Med ROCE %": st.column_config.NumberColumn("Med ROCE %", format="%.1f"),
            },
        )
