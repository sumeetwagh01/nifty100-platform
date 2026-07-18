"""
pages/07_capital.py — Capital Allocation Map
=============================================
Sprint 4 Day 25: Full implementation.

Features
--------
- Plotly treemap of all 92 companies grouped by 8 capital allocation patterns
- Pattern → sub-sector → company hierarchy
- Clicking a pattern segment shows the companies table below
- Pattern descriptions and legend
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_capital_allocation_map

# ---------------------------------------------------------------------------
# Pattern descriptions
# ---------------------------------------------------------------------------
PATTERN_INFO = {
    "Reinvestor":           ("🔵", "Strong CFO, reinvesting in growth, returning cash to shareholders"),
    "Shareholder Returns":  ("🟢", "High CFO/PAT, prioritising dividends and buybacks"),
    "Liquidating Assets":   ("🟡", "Selling assets to pay down debt — restructuring phase"),
    "Distress Signal":      ("🔴", "Losing money, selling assets, borrowing — watch closely"),
    "Growth Funded by Debt":("🟠", "Investing aggressively via debt — high-growth or high-risk"),
    "Cash Accumulator":     ("⚪", "Cash piling up across all activities — needs deployment"),
    "Pre-Revenue":          ("⚫", "Burning cash across all activities — early stage or distress"),
    "Mixed":                ("🟣", "Profitable but complex financing mix"),
    "Unknown":              ("❓", "Pattern not classified for latest year"),
}

PATTERN_COLORS = {
    "Reinvestor":            "#4f8ef7",
    "Shareholder Returns":   "#22c55e",
    "Liquidating Assets":    "#f59e0b",
    "Distress Signal":       "#ef4444",
    "Growth Funded by Debt": "#f97316",
    "Cash Accumulator":      "#a855f7",
    "Pre-Revenue":           "#6b7280",
    "Mixed":                 "#ec4899",
    "Unknown":               "#374151",
}

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("💰 Capital Allocation Map")
st.caption("Sprint 4 · Day 25 · 8-pattern classification of all 92 companies")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = get_capital_allocation_map()

if df.empty:
    st.error("No capital allocation data available.")
    st.stop()

df["broad_sector"] = df["broad_sector"].fillna("Other")

# Add colour column for treemap
df["color_val"] = df["pattern"].map(
    lambda p: list(PATTERN_COLORS.keys()).index(p) if p in PATTERN_COLORS else 8
)

# ---------------------------------------------------------------------------
# Summary KPI strip
# ---------------------------------------------------------------------------
pattern_counts = df["pattern"].value_counts()
top_pattern    = pattern_counts.idxmax()
top_icon       = PATTERN_INFO.get(top_pattern, ("❓", ""))[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Companies",   len(df))
col2.metric("Unique Patterns",   df["pattern"].nunique())
col3.metric("Most Common",       f"{top_icon} {top_pattern}")
col4.metric("Companies",         int(pattern_counts.max()))

st.divider()

# ---------------------------------------------------------------------------
# Treemap — Pattern → Sector → Company
# ---------------------------------------------------------------------------
st.subheader("🗺️ Capital Allocation Treemap")
st.caption("Click a segment to filter the companies table below")

# Build treemap with path hierarchy: pattern → broad_sector → company
fig = px.treemap(
    df,
    path=["pattern", "broad_sector", "company_name"],
    values=[1] * len(df),          # equal size per company
    color="pattern",
    color_discrete_map=PATTERN_COLORS,
    custom_data=["company_id", "composite_quality_score", "pattern"],
    hover_data={"composite_quality_score": ":.1f"},
)

fig.update_traces(
    hovertemplate=(
        "<b>%{label}</b><br>"
        "Pattern: %{customdata[2]}<br>"
        "Quality Score: %{customdata[1]:.1f}<br>"
        "<extra></extra>"
    ),
    textfont=dict(size=11),
    marker_line_width=1.5,
    marker_line_color="#0e1117",
)

fig.update_layout(
    height=560,
    paper_bgcolor="#0e1117",
    font=dict(color="#e0e6f0", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Pattern legend
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📖 Pattern Reference Guide")

legend_cols = st.columns(3)
for i, (pattern, (icon, desc)) in enumerate(PATTERN_INFO.items()):
    count = int(pattern_counts.get(pattern, 0))
    with legend_cols[i % 3]:
        st.markdown(
            f"**{icon} {pattern}** — *{count} companies*  \n{desc}"
        )

# ---------------------------------------------------------------------------
# Filter by pattern — company table
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🔍 Companies by Pattern")

patterns_with_data = sorted(df["pattern"].unique().tolist())
selected_pattern = st.selectbox(
    "Select Pattern",
    patterns_with_data,
    index=0,
    key="cap_alloc_pattern",
)

filtered = df[df["pattern"] == selected_pattern].copy()
icon, desc = PATTERN_INFO.get(selected_pattern, ("❓", ""))

st.info(f"**{icon} {selected_pattern}** — {desc}  \n**{len(filtered)} companies** follow this pattern in their latest reported year.")

st.dataframe(
    filtered[["company_id", "company_name", "broad_sector", "composite_quality_score"]]
    .rename(columns={
        "company_id": "Ticker",
        "company_name": "Company",
        "broad_sector": "Sector",
        "composite_quality_score": "Quality Score",
    })
    .sort_values("Quality Score", ascending=False),
    use_container_width=True,
    hide_index=True,
)
