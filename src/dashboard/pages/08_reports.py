"""
pages/08_reports.py — Annual Reports
======================================
Sprint 4 Day 25: Full implementation.

Features
--------
- Company search box (selectbox with NSE ticker)
- Lists all available annual report years with clickable BSE PDF links
- Shows a red "Unavailable" badge if URL appears invalid or empty
- Summary count of available vs missing years
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import streamlit as st

from src.dashboard.utils.db import get_ticker_list, get_annual_reports, get_companies

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("📄 Annual Reports")
st.caption("Sprint 4 · Day 25 · BSE annual report links for all 92 Nifty 100 companies")

# ---------------------------------------------------------------------------
# Sidebar — company selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔍 Select Company")
    tickers = get_ticker_list()
    ticker = st.selectbox("Company (NSE Ticker)", tickers, index=0, key="reports_ticker")

# ---------------------------------------------------------------------------
# Company info header
# ---------------------------------------------------------------------------
companies_df = get_companies()
company_row  = companies_df[companies_df["id"] == ticker]

if not company_row.empty:
    c = company_row.iloc[0]
    st.markdown(f"## {c['company_name']}")
    cols = st.columns(3)
    if c.get("website"):
        cols[0].markdown(f"🌐 [Website]({c['website']})")
    if c.get("nse_profile"):
        cols[1].markdown(f"📈 [NSE Profile]({c['nse_profile']})")
    if c.get("bse_profile"):
        cols[2].markdown(f"🏛️ [BSE Profile]({c['bse_profile']})")

st.divider()

# ---------------------------------------------------------------------------
# Fetch annual reports
# ---------------------------------------------------------------------------
reports_df = get_annual_reports(ticker)

if reports_df.empty:
    st.warning(f"No annual report links found for **{ticker}** in the database.")
    st.stop()

# ---------------------------------------------------------------------------
# Display report cards
# ---------------------------------------------------------------------------
available   = reports_df[reports_df["annual_report_url"].str.startswith("http", na=False)]
unavailable = reports_df[~reports_df["annual_report_url"].str.startswith("http", na=False)]

c1, c2, c3 = st.columns(3)
c1.metric("Total Years", len(reports_df))
c2.metric("✅ Available",  len(available))
c3.metric("❌ Unavailable", len(unavailable))

st.markdown("### 📑 Available Annual Reports")

# Sort by year descending (most recent first)
reports_sorted = reports_df.sort_values("year", ascending=False)

for _, row in reports_sorted.iterrows():
    year = row["year"]
    url  = row["annual_report_url"]
    is_valid = isinstance(url, str) and url.startswith("http")

    col_year, col_badge, col_link = st.columns([1, 1, 6])

    with col_year:
        st.markdown(f"**{year}**")

    with col_badge:
        if is_valid:
            st.markdown(
                '<span style="background:#22c55e;color:#fff;padding:2px 8px;'
                'border-radius:4px;font-size:0.8rem;">✅ Available</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span style="background:#ef4444;color:#fff;padding:2px 8px;'
                'border-radius:4px;font-size:0.8rem;">❌ Unavailable</span>',
                unsafe_allow_html=True,
            )

    with col_link:
        if is_valid:
            st.markdown(f"[📥 Download Annual Report {year}]({url})")
        else:
            st.markdown("*Report link not available in database*")

st.divider()

# ---------------------------------------------------------------------------
# Raw data expander
# ---------------------------------------------------------------------------
with st.expander("🗃️ Raw Data from Database"):
    st.dataframe(
        reports_df.rename(columns={
            "company_id": "Ticker",
            "year": "Year",
            "annual_report_url": "Annual Report URL",
        }),
        use_container_width=True,
        hide_index=True,
    )
