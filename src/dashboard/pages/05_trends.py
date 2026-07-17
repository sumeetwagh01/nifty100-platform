"""
pages/05_trends.py — Historical Trend Analysis
================================================
Sprint 4 Day 22: Stub page — renders without errors.
Full implementation: Day 25.
"""

import sys
from pathlib import Path
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import streamlit as st

from src.dashboard.utils.db import get_pl, get_cf, get_ticker_list

st.title("📊 Historical Trends")
st.caption("Sprint 4 | Day 22 scaffold — full content coming on Day 25")

ticker_list = get_ticker_list()
ticker = st.selectbox("Select Company", ticker_list, index=0)

if ticker:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Profit & Loss")
        pl = get_pl(ticker)
        st.dataframe(pl[["year", "sales", "net_profit", "eps_in_rs"]], use_container_width=True)
    with col2:
        st.subheader("Cash Flow")
        cf = get_cf(ticker)
        st.dataframe(cf[["year", "operating_activity", "investing_activity", "financing_activity"]], use_container_width=True)
