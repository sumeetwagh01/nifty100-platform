"""
pages/06_sectors.py — Sector Analysis
=======================================
Sprint 4 Day 25: Full implementation.

Features
--------
- Sector dropdown (All + individual broad sectors)
- Bubble chart: X = Revenue, Y = ROE, bubble size = Market Cap,
  colour = sub-sector — Plotly scatter
- Sector median KPI bar chart below the bubble chart
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import get_sector_bubble_data, get_sector_kpi_summary

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🏭 Sector Analysis")
st.caption("Sprint 4 · Day 25 · Bubble chart + sector KPI benchmarks")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
bubble_df  = get_sector_bubble_data()
kpi_df     = get_sector_kpi_summary()

if bubble_df.empty:
    st.error("No sector data available.")
    st.stop()

# Fill nulls
bubble_df["market_cap_crore"]     = bubble_df["market_cap_crore"].fillna(1000)
bubble_df["return_on_equity_pct"] = bubble_df["return_on_equity_pct"].fillna(0)
bubble_df["sales"]                = bubble_df["sales"].fillna(0)
bubble_df["sub_sector"]           = bubble_df["sub_sector"].fillna("Other")

# ---------------------------------------------------------------------------
# Sidebar — sector selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏭 Filter by Sector")
    sectors = sorted(bubble_df["broad_sector"].dropna().unique().tolist())
    selected = st.selectbox("Broad Sector", ["All Sectors"] + sectors, index=0, key="sector_filter")

if selected != "All Sectors":
    view_df  = bubble_df[bubble_df["broad_sector"] == selected]
    kpi_view = kpi_df[kpi_df["broad_sector"] == selected]
else:
    view_df  = bubble_df
    kpi_view = kpi_df

# ---------------------------------------------------------------------------
# KPI summary strip
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Companies",       len(view_df))
col2.metric("Avg ROE",         f"{view_df['return_on_equity_pct'].mean():.1f}%")
col3.metric("Avg Revenue (Cr)",f"₹{view_df['sales'].mean():,.0f}")
col4.metric("Avg Mkt Cap (Cr)",f"₹{view_df['market_cap_crore'].mean():,.0f}")

st.divider()

# ---------------------------------------------------------------------------
# Bubble chart: X=Revenue, Y=ROE, size=Market Cap, colour=sub_sector
# ---------------------------------------------------------------------------
st.subheader("🔵 Revenue vs ROE — Bubble = Market Cap")

fig_bubble = px.scatter(
    view_df,
    x="sales",
    y="return_on_equity_pct",
    size="market_cap_crore",
    color="sub_sector",
    hover_name="company_name",
    hover_data={
        "broad_sector": True,
        "sub_sector": True,
        "sales": ":.0f",
        "return_on_equity_pct": ":.1f",
        "market_cap_crore": ":.0f",
        "composite_quality_score": ":.1f",
    },
    labels={
        "sales": "Revenue (₹ Cr)",
        "return_on_equity_pct": "ROE (%)",
        "market_cap_crore": "Mkt Cap (₹ Cr)",
        "sub_sector": "Sub-Sector",
    },
    size_max=60,
    opacity=0.85,
    template="plotly_dark",
)

fig_bubble.update_layout(
    height=520,
    paper_bgcolor="#0e1117",
    plot_bgcolor="#1a1f2e",
    font=dict(color="#e0e6f0"),
    xaxis=dict(title="Revenue (₹ Cr)", gridcolor="#2a3040", type="log"),
    yaxis=dict(title="ROE (%)", gridcolor="#2a3040"),
    legend=dict(bgcolor="#1a1f2e", bordercolor="#2a3040", borderwidth=1,
                orientation="v", x=1.02),
    margin=dict(l=60, r=200, t=40, b=60),
)

st.plotly_chart(fig_bubble, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Sector KPI bar chart
# ---------------------------------------------------------------------------
st.subheader("📊 Sector Median KPI Comparison")

kpi_metric = st.radio(
    "Select KPI",
    ["avg_roe", "avg_roce", "avg_npm", "avg_de"],
    format_func=lambda x: {
        "avg_roe": "Avg ROE (%)",
        "avg_roce": "Avg ROCE (%)",
        "avg_npm": "Avg Net Profit Margin (%)",
        "avg_de": "Avg D/E Ratio",
    }[x],
    horizontal=True,
    key="sector_kpi_metric",
)

kpi_label = {
    "avg_roe":  "Avg ROE (%)",
    "avg_roce": "Avg ROCE (%)",
    "avg_npm":  "Avg Net Profit Margin (%)",
    "avg_de":   "Avg D/E Ratio",
}[kpi_metric]

bar_df = kpi_df.dropna(subset=[kpi_metric]).sort_values(kpi_metric, ascending=True)

fig_bar = go.Figure(go.Bar(
    x=bar_df[kpi_metric],
    y=bar_df["broad_sector"],
    orientation="h",
    marker=dict(
        color=bar_df[kpi_metric],
        colorscale="Blues",
        showscale=True,
        colorbar=dict(title=kpi_label, tickfont=dict(color="#e0e6f0")),
    ),
    text=bar_df[kpi_metric].round(1).astype(str) + ("%" if kpi_metric != "avg_de" else "x"),
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>" + kpi_label + ": %{x:.2f}<extra></extra>",
))

fig_bar.update_layout(
    height=420,
    paper_bgcolor="#0e1117",
    plot_bgcolor="#1a1f2e",
    font=dict(color="#e0e6f0"),
    xaxis=dict(title=kpi_label, gridcolor="#2a3040"),
    yaxis=dict(title="", gridcolor="#2a3040"),
    margin=dict(l=180, r=80, t=20, b=60),
)

st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------------------------
# Company table for selected sector
# ---------------------------------------------------------------------------
st.divider()
st.subheader(f"🏢 Companies — {selected}")
show_cols = ["company_id", "company_name", "sub_sector",
             "sales", "return_on_equity_pct", "market_cap_crore", "composite_quality_score"]
display = view_df[show_cols].rename(columns={
    "company_id": "Ticker",
    "company_name": "Company",
    "sub_sector": "Sub-Sector",
    "sales": "Revenue (Cr)",
    "return_on_equity_pct": "ROE (%)",
    "market_cap_crore": "Mkt Cap (Cr)",
    "composite_quality_score": "Quality Score",
}).sort_values("Quality Score", ascending=False)

st.dataframe(display, use_container_width=True, hide_index=True)
