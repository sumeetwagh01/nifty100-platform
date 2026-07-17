"""
pages/02_profile.py — Company Profile
======================================
Sprint 4 Day 23: Full implementation.

Features
--------
- Text search box with autocomplete (company name + ticker)
- Company card — name, sector, sub-sector, NSE ticker badge, about description
- 6 KPI tiles: ROE, ROCE, Net Profit Margin, D/E, Revenue CAGR 5yr, FCF (latest year)
- 10-year Revenue & Net Profit grouped bar chart (Plotly)
- ROE & ROCE dual-axis line chart over 10 years (Plotly)
- Pros & cons section — green ✅ / red ❌ badge items
- Friendly "Ticker not found" fallback
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
from plotly.subplots import make_subplots
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_pl,
    get_prosandcons,
    get_ratios,
    get_sectors,
)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🏢 Company Profile")
st.caption("Sprint 4 · Day 23 · Search any Nifty 100 company")

# ---------------------------------------------------------------------------
# Build search list: "COMPANY NAME (TICKER)" → maps back to ticker
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600)
def _build_search_map() -> dict[str, str]:
    """Return {display_label: ticker} for the selectbox."""
    companies = get_companies()
    mapping = {}
    for _, row in companies.iterrows():
        label = f"{row['company_name'].strip()} ({row['id']})"
        mapping[label] = row["id"]
    return mapping


search_map = _build_search_map()
search_labels = sorted(search_map.keys())

# Pre-select TCS as a sensible default
_default_label = next((lbl for lbl in search_labels if "(TCS)" in lbl), search_labels[0])
_default_idx = search_labels.index(_default_label)

with st.sidebar:
    st.markdown("### 🔍 Search Company")
    chosen_label = st.selectbox(
        "Type company name or ticker",
        options=search_labels,
        index=_default_idx,
        key="profile_company",
        help="Start typing to filter the list",
    )
    st.divider()

ticker = search_map.get(chosen_label, "")

# ---------------------------------------------------------------------------
# Load all data for the selected ticker
# ---------------------------------------------------------------------------
if not ticker:
    st.warning("⚠️ Ticker not found — please try another")
    st.stop()

companies_df = get_companies()
sectors_df   = get_sectors()
pl_df        = get_pl(ticker)
ratios_df    = get_ratios(ticker)
pc_df        = get_prosandcons(ticker)

# Validate company exists
company_row = companies_df[companies_df["id"] == ticker]
if company_row.empty:
    st.warning(f"⚠️ Ticker **{ticker}** not found — please try another")
    st.stop()

company = company_row.iloc[0]
sector_row = sectors_df[sectors_df["company_id"] == ticker]
sector_info = sector_row.iloc[0] if not sector_row.empty else None

# ---------------------------------------------------------------------------
# Company card
# ---------------------------------------------------------------------------
broad_sector = sector_info["broad_sector"] if sector_info is not None else "—"
sub_sector   = sector_info["sub_sector"]   if sector_info is not None else "—"
about_text   = (company.get("about_company") or "").strip()

st.markdown(
    f"""
    <div style="
        background: linear-gradient(135deg, #1a1f2e 0%, #0e1117 100%);
        border: 1px solid #2a3040;
        border-radius: 14px;
        padding: 1.4rem 1.8rem;
        margin-bottom: 1.2rem;
    ">
        <div style="display:flex; align-items:center; gap:1rem; flex-wrap:wrap;">
            <div style="flex:1;">
                <h2 style="margin:0;color:#e0e6f0;font-size:1.6rem;font-weight:700;">
                    {company['company_name'].strip()}
                </h2>
                <div style="margin-top:0.5rem;display:flex;gap:0.6rem;flex-wrap:wrap;align-items:center;">
                    <span style="background:#4f8ef722;border:1px solid #4f8ef7;color:#4f8ef7;
                                 border-radius:20px;padding:0.15rem 0.8rem;font-size:0.8rem;font-weight:600;">
                        NSE: {ticker}
                    </span>
                    <span style="background:#a44ff722;border:1px solid #a44ff7;color:#a44ff7;
                                 border-radius:20px;padding:0.15rem 0.8rem;font-size:0.8rem;">
                        {broad_sector}
                    </span>
                    <span style="background:#f7a44f22;border:1px solid #f7a44f;color:#f7a44f;
                                 border-radius:20px;padding:0.15rem 0.8rem;font-size:0.8rem;">
                        {sub_sector or '—'}
                    </span>
                </div>
            </div>
        </div>
        {'<p style="margin:0.9rem 0 0;color:#8a94a6;font-size:0.88rem;line-height:1.55;">' + about_text + '</p>' if about_text else ''}
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 6 KPI tiles — latest year from financial_ratios
# ---------------------------------------------------------------------------
def _latest_ratio(col: str) -> float | None:
    if ratios_df.empty or col not in ratios_df.columns:
        return None
    s = ratios_df[col].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _fmt(val: float | None, suffix: str = "", decimals: int = 1) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}{suffix}"


latest_roe       = _latest_ratio("return_on_equity_pct")
latest_roce      = _latest_ratio("roce_pct")
latest_npm       = _latest_ratio("net_profit_margin_pct")
latest_de        = _latest_ratio("debt_to_equity")
latest_revcagr5  = _latest_ratio("revenue_cagr_5yr")
latest_fcf       = _latest_ratio("free_cash_flow_cr")

# Latest year label
latest_year_label = "—"
if not ratios_df.empty and "year" in ratios_df.columns:
    latest_year_label = str(ratios_df["year"].dropna().iloc[-1]) if not ratios_df["year"].dropna().empty else "—"

st.markdown(f"#### 📌 Key Metrics — Latest Year ({latest_year_label})")
k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric("⚡ ROE",   _fmt(latest_roe,  "%"), help="Return on Equity")
with k2:
    st.metric("🔁 ROCE",  _fmt(latest_roce, "%"), help="Return on Capital Employed")
with k3:
    st.metric("💰 NPM",   _fmt(latest_npm,  "%"), help="Net Profit Margin")
with k4:
    st.metric("⚖️ D/E",  _fmt(latest_de,   "x"), help="Debt-to-Equity ratio")
with k5:
    st.metric("📈 Rev CAGR 5yr", _fmt(latest_revcagr5, "%"), help="Revenue CAGR over 5 years")
with k6:
    fcf_label = _fmt(latest_fcf, " Cr", decimals=0) if latest_fcf is not None else "—"
    st.metric("💸 FCF",  fcf_label, help="Free Cash Flow (latest year, ₹ Crore)")

st.divider()

# ---------------------------------------------------------------------------
# Charts — 10-year Revenue & Net Profit bar chart + ROE/ROCE dual-axis
# ---------------------------------------------------------------------------
chart_left, chart_right = st.columns(2, gap="medium")

# ── Revenue & Net Profit bar chart ──────────────────────────────────────────
with chart_left:
    st.markdown("#### 📊 Revenue & Net Profit (10 Years)")

    if pl_df.empty:
        st.info("No P&L data available for this company.")
    else:
        pl_plot = (
            pl_df[["year", "sales", "net_profit"]]
            .dropna(subset=["sales"])
            .copy()
        )
        # Extract year integer for display
        pl_plot["yr_label"] = pl_plot["year"].apply(
            lambda y: str(y)[:4] if isinstance(y, str) and len(str(y)) >= 4 else str(y)
        )
        pl_plot = pl_plot.tail(10)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=pl_plot["yr_label"],
            y=pl_plot["sales"],
            name="Revenue (₹ Cr)",
            marker_color="#4f8ef7",
            hovertemplate="Year: %{x}<br>Revenue: ₹%{y:,.0f} Cr<extra></extra>",
        ))
        fig_bar.add_trace(go.Bar(
            x=pl_plot["yr_label"],
            y=pl_plot["net_profit"],
            name="Net Profit (₹ Cr)",
            marker_color="#4ff7a4",
            hovertemplate="Year: %{x}<br>Net Profit: ₹%{y:,.0f} Cr<extra></extra>",
        ))
        fig_bar.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            barmode="group",
            margin=dict(t=20, b=40, l=10, r=10),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(tickangle=-30),
            yaxis=dict(title="₹ Crore", gridcolor="#2a3040"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ── ROE & ROCE dual-axis line chart ─────────────────────────────────────────
with chart_right:
    st.markdown("#### 📉 ROE & ROCE Trend (10 Years)")

    if ratios_df.empty:
        st.info("No ratio data available for this company.")
    else:
        ratio_plot = (
            ratios_df[["year", "return_on_equity_pct", "roce_pct"]]
            .dropna(subset=["return_on_equity_pct"])
            .copy()
        )
        ratio_plot["yr_label"] = ratio_plot["year"].apply(
            lambda y: str(y)[:4] if isinstance(y, str) and len(str(y)) >= 4 else str(y)
        )
        ratio_plot = ratio_plot.tail(10)

        fig_line = make_subplots(specs=[[{"secondary_y": True}]])

        fig_line.add_trace(
            go.Scatter(
                x=ratio_plot["yr_label"],
                y=ratio_plot["return_on_equity_pct"],
                name="ROE %",
                mode="lines+markers",
                line=dict(color="#f7a44f", width=2.5),
                marker=dict(size=6),
                hovertemplate="Year: %{x}<br>ROE: %{y:.1f}%<extra></extra>",
            ),
            secondary_y=False,
        )
        fig_line.add_trace(
            go.Scatter(
                x=ratio_plot["yr_label"],
                y=ratio_plot["roce_pct"],
                name="ROCE %",
                mode="lines+markers",
                line=dict(color="#a44ff7", width=2.5, dash="dot"),
                marker=dict(size=6),
                hovertemplate="Year: %{x}<br>ROCE: %{y:.1f}%<extra></extra>",
            ),
            secondary_y=True,
        )

        fig_line.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=40, l=10, r=10),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(tickangle=-30, gridcolor="#2a3040"),
        )
        fig_line.update_yaxes(
            title_text="ROE %",
            secondary_y=False,
            gridcolor="#2a3040",
        )
        fig_line.update_yaxes(
            title_text="ROCE %",
            secondary_y=True,
            showgrid=False,
        )
        st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Pros & Cons section
# ---------------------------------------------------------------------------
st.markdown("#### 🔍 Qualitative Assessment")

if pc_df.empty:
    st.info(
        "ℹ️ No qualitative pros/cons data available for this company. "
        "Data is available for select companies (e.g., HDFCBANK, SBILIFE)."
    )
else:
    pros_list = pc_df["pros"].dropna().tolist()
    cons_list = pc_df["cons"].dropna().tolist()

    pc_left, pc_right = st.columns(2, gap="large")

    with pc_left:
        st.markdown("**✅ Strengths (Pros)**")
        if pros_list:
            pros_html = "".join(
                f"""
                <div style="
                    display:flex; align-items:flex-start; gap:0.6rem;
                    background:#0b2a1a; border:1px solid #1e7a4a;
                    border-radius:8px; padding:0.6rem 0.8rem;
                    margin-bottom:0.5rem;
                ">
                    <span style="color:#4ff7a4;font-size:1rem;margin-top:0.05rem;">✅</span>
                    <span style="color:#c8f7dc;font-size:0.87rem;line-height:1.5;">{pro}</span>
                </div>
                """
                for pro in pros_list
            )
            st.markdown(pros_html, unsafe_allow_html=True)
        else:
            st.caption("No strengths listed.")

    with pc_right:
        st.markdown("**❌ Risks (Cons)**")
        if cons_list:
            cons_html = "".join(
                f"""
                <div style="
                    display:flex; align-items:flex-start; gap:0.6rem;
                    background:#2a0b0b; border:1px solid #7a1e1e;
                    border-radius:8px; padding:0.6rem 0.8rem;
                    margin-bottom:0.5rem;
                ">
                    <span style="color:#f74f4f;font-size:1rem;margin-top:0.05rem;">❌</span>
                    <span style="color:#f7c8c8;font-size:0.87rem;line-height:1.5;">{con}</span>
                </div>
                """
                for con in cons_list
            )
            st.markdown(cons_html, unsafe_allow_html=True)
        else:
            st.caption("No risks listed.")
