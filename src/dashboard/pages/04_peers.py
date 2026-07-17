"""
pages/04_peers.py — Peer Comparison
=====================================
Sprint 4 Day 24: Full implementation.

Features
--------
- Sector dropdown (10 broad sectors from DB)
- Company selector (benchmark) within the selected sector
- Radar chart (Plotly Scatterpolar) — selected company vs sector average
  across 8 normalised financial metrics
- Side-by-side KPI table — all companies in sector, benchmark row highlighted
"""

from __future__ import annotations

import sys
from pathlib import Path
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import get_broad_sectors, get_peer_sector_data

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("👥 Peer Comparison")
st.caption("Sprint 4 · Day 24 · Compare any company against its sector peers")

# ---------------------------------------------------------------------------
# Radar chart — metric definitions
# ---------------------------------------------------------------------------
# (label, column_name, higher_is_better)
RADAR_METRICS: list[tuple[str, str, bool]] = [
    ("ROE %",        "return_on_equity_pct",  True),
    ("ROCE %",       "roce_pct",              True),
    ("NPM %",        "net_profit_margin_pct", True),
    ("Rev CAGR",     "revenue_cagr_5yr",      True),
    ("PAT CAGR",     "pat_cagr_5yr",          True),
    ("Quality ★",    "composite_quality_score",True),
    ("ICR",          "interest_coverage",     True),
    ("Low D/E",      "debt_to_equity",        False),  # inverted: lower is better
]
RADAR_LABELS = [m[0] for m in RADAR_METRICS]


def _minmax_normalize(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Normalise a metric column to 0-100. NaN → 0."""
    s = series.copy().fillna(0.0)
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series([50.0] * len(s), index=s.index)
    norm = (s - lo) / (hi - lo) * 100.0
    if not higher_is_better:
        norm = 100.0 - norm
    return norm


def _build_radar_data(peer_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of peer_df with one extra normalised column per radar metric.
    Normalised column names: `norm_<original_col>`.
    """
    result = peer_df.copy()
    for _, col, hib in RADAR_METRICS:
        norm_col = f"norm_{col}"
        if col in result.columns:
            result[norm_col] = _minmax_normalize(result[col], higher_is_better=hib)
        else:
            result[norm_col] = 50.0
    return result


# ---------------------------------------------------------------------------
# Load sector list
# ---------------------------------------------------------------------------
with st.spinner("Loading sectors…"):
    all_sectors = get_broad_sectors()

if not all_sectors:
    st.error("No sector data found in the database.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — sector + company selectors
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏭 Select Sector")
    # Default to Financials (richest data)
    default_sector_idx = all_sectors.index("Financials") if "Financials" in all_sectors else 0
    selected_sector = st.selectbox(
        "Broad Sector",
        options=all_sectors,
        index=default_sector_idx,
        key="peer_sector",
    )
    st.divider()

# ---------------------------------------------------------------------------
# Load peer data for selected sector
# ---------------------------------------------------------------------------
with st.spinner(f"Loading {selected_sector} peer data…"):
    peer_df = get_peer_sector_data(selected_sector)

if peer_df.empty:
    st.warning(f"No data found for sector '{selected_sector}'.")
    st.stop()

# Build company list for selector
company_options = peer_df["company_id"].tolist()
company_labels  = {
    row["company_id"]: f"{row['company_name']} ({row['company_id']})"
    for _, row in peer_df.iterrows()
}

with st.sidebar:
    st.markdown("### 🏢 Benchmark Company")
    selected_ticker = st.selectbox(
        "Select company to highlight",
        options=company_options,
        format_func=lambda t: company_labels.get(t, t),
        index=0,
        key="peer_company",
    )
    st.divider()
    st.markdown(
        f"<div style='font-size:0.78rem;color:#8a94a6;'>"
        f"<b>{len(peer_df)}</b> companies in <b>{selected_sector}</b> sector</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Normalise data for radar
# ---------------------------------------------------------------------------
normed_df = _build_radar_data(peer_df)

# Selected company row
company_row = normed_df[normed_df["company_id"] == selected_ticker]
if company_row.empty:
    st.error(f"Company {selected_ticker} not found in sector data.")
    st.stop()

company_row = company_row.iloc[0]
company_name = company_labels.get(selected_ticker, selected_ticker)

# Sector averages (normalised)
norm_cols = [f"norm_{col}" for _, col, _ in RADAR_METRICS]
sector_avg_norm = normed_df[norm_cols].mean()

# Company normalised values
company_norm = [company_row.get(f"norm_{col}", 50.0) for _, col, _ in RADAR_METRICS]
sector_norm  = [sector_avg_norm.get(f"norm_{col}", 50.0) for _, col, _ in RADAR_METRICS]

# Close the polygon for radar chart
r_company = company_norm + [company_norm[0]]
r_sector  = sector_norm  + [sector_norm[0]]
theta     = RADAR_LABELS + [RADAR_LABELS[0]]

# ---------------------------------------------------------------------------
# Build radar chart
# ---------------------------------------------------------------------------
fig_radar = go.Figure()

fig_radar.add_trace(go.Scatterpolar(
    r=r_sector,
    theta=theta,
    fill="toself",
    fillcolor="rgba(79, 142, 247, 0.12)",
    line=dict(color="#4f8ef7", width=1.5, dash="dot"),
    name="Sector Average",
    hovertemplate="%{theta}: %{r:.1f}<extra>Sector Avg</extra>",
))

fig_radar.add_trace(go.Scatterpolar(
    r=r_company,
    theta=theta,
    fill="toself",
    fillcolor="rgba(247, 164, 79, 0.22)",
    line=dict(color="#f7a44f", width=2.5),
    name=company_row.get("company_id", selected_ticker),
    hovertemplate="%{theta}: %{r:.1f}<extra>" + selected_ticker + "</extra>",
))

fig_radar.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    polar=dict(
        bgcolor="rgba(14,17,23,0.6)",
        radialaxis=dict(
            visible=True,
            range=[0, 100],
            tickfont=dict(size=9, color="#8a94a6"),
            gridcolor="#2a3040",
            linecolor="#2a3040",
        ),
        angularaxis=dict(
            tickfont=dict(size=11, color="#c8d0e0"),
            gridcolor="#2a3040",
            linecolor="#2a3040",
        ),
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.18,
        xanchor="center",
        x=0.5,
        font=dict(color="#c8d0e0"),
    ),
    margin=dict(t=30, b=60, l=60, r=60),
    height=430,
)

# ---------------------------------------------------------------------------
# Layout: radar (left) + summary card (right)
# ---------------------------------------------------------------------------
st.markdown(f"#### 📡 Radar — **{selected_ticker}** vs {selected_sector} Sector Average")

left_col, right_col = st.columns([1.3, 1], gap="large")

with left_col:
    st.plotly_chart(fig_radar, use_container_width=True)

with right_col:
    st.markdown("**📊 Benchmark Metrics**")
    # Build a small raw-values card for the selected company
    raw_labels = {
        "ROE %":        ("return_on_equity_pct", "{:.1f}%"),
        "ROCE %":       ("roce_pct",              "{:.1f}%"),
        "NPM %":        ("net_profit_margin_pct", "{:.1f}%"),
        "Rev CAGR 5yr": ("revenue_cagr_5yr",      "{:.1f}%"),
        "PAT CAGR 5yr": ("pat_cagr_5yr",          "{:.1f}%"),
        "D/E":          ("debt_to_equity",         "{:.2f}x"),
        "ICR":          ("interest_coverage",      "{:.1f}x"),
        "Quality ★":    ("composite_quality_score","{:.1f}"),
    }

    def _fmtval(row, col, fmt):
        v = row.get(col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        return fmt.format(v)

    # Sector averages (raw)
    raw_cols = [v[0] for v in raw_labels.values()]
    sector_raw_avg = peer_df[raw_cols].mean()

    metric_rows_html = ""
    for label, (col, fmt) in raw_labels.items():
        company_val = _fmtval(company_row, col, fmt)
        avg_raw = sector_raw_avg.get(col)
        avg_val = "—" if (avg_raw is None or (isinstance(avg_raw, float) and np.isnan(avg_raw))) else fmt.format(avg_raw)
        metric_rows_html += (
            f"<tr>"
            f"<td style='color:#8a94a6;padding:0.3rem 0.6rem;font-size:0.83rem;'>{label}</td>"
            f"<td style='color:#f7a44f;font-weight:600;text-align:right;padding:0.3rem 0.6rem;font-size:0.83rem;'>{company_val}</td>"
            f"<td style='color:#4f8ef7;text-align:right;padding:0.3rem 0.6rem;font-size:0.83rem;'>{avg_val}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <table style="width:100%;border-collapse:collapse;background:#1a1f2e;border-radius:10px;overflow:hidden;">
        <thead>
          <tr>
            <th style="color:#8a94a6;font-size:0.78rem;padding:0.5rem 0.6rem;text-align:left;">Metric</th>
            <th style="color:#f7a44f;font-size:0.78rem;padding:0.5rem 0.6rem;text-align:right;">{selected_ticker}</th>
            <th style="color:#4f8ef7;font-size:0.78rem;padding:0.5rem 0.6rem;text-align:right;">Sector Avg</th>
          </tr>
        </thead>
        <tbody>{metric_rows_html}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='margin-top:0.8rem;font-size:0.76rem;color:#8a94a6;'>"
        f"Sector average from <b>{len(peer_df)}</b> companies · {selected_sector}"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# KPI table — all companies in sector, benchmark row highlighted
# ---------------------------------------------------------------------------
st.markdown(f"#### 📋 {selected_sector} — All Companies KPI Table")
st.caption(f"Benchmark row ({selected_ticker}) highlighted in amber · Click column headers to sort")

KPI_COLS = {
    "company_id":             "Ticker",
    "company_name":           "Company",
    "sub_sector":             "Sub-Sector",
    "composite_quality_score":"Quality ★",
    "return_on_equity_pct":   "ROE %",
    "roce_pct":               "ROCE %",
    "net_profit_margin_pct":  "NPM %",
    "debt_to_equity":         "D/E",
    "revenue_cagr_5yr":       "Rev CAGR",
    "pat_cagr_5yr":           "PAT CAGR",
    "pe_ratio":               "P/E",
    "pb_ratio":               "P/B",
}

kpi_table = peer_df[[c for c in KPI_COLS if c in peer_df.columns]].copy()
kpi_table = kpi_table.rename(columns=KPI_COLS).reset_index(drop=True)

# Highlight benchmark row using pandas Styler
benchmark_idx = kpi_table.index[kpi_table["Ticker"] == selected_ticker].tolist()

def _highlight_benchmark(row):
    if row.name in benchmark_idx:
        return ["background-color: #3a2800; color: #f7c44f; font-weight: 700;"] * len(row)
    return [""] * len(row)

styled_kpi = (
    kpi_table.style
    .apply(_highlight_benchmark, axis=1)
    .format(
        {
            "Quality ★":  lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "ROE %":      lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "ROCE %":     lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "NPM %":      lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "D/E":        lambda x: f"{x:.2f}" if pd.notna(x) else "—",
            "Rev CAGR":   lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "PAT CAGR":   lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "P/E":        lambda x: f"{x:.1f}" if pd.notna(x) else "—",
            "P/B":        lambda x: f"{x:.2f}" if pd.notna(x) else "—",
        }
    )
    .set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#1a1f2e"),
            ("color", "#8a94a6"),
            ("font-size", "0.8rem"),
            ("padding", "0.4rem 0.5rem"),
        ]},
        {"selector": "td", "props": [
            ("font-size", "0.85rem"),
            ("padding", "0.4rem 0.5rem"),
        ]},
    ])
)

st.dataframe(
    styled_kpi,
    use_container_width=True,
    hide_index=True,
    height=min(60 + len(kpi_table) * 38, 550),
)
