"""
pages/06_sectors.py — Sector Analysis
=======================================
Sprint 4 Day 22: Stub page — renders without errors.
Full implementation: Day 26.
"""

import sys
from pathlib import Path
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import streamlit as st

from src.dashboard.utils.db import get_sectors, get_companies

st.title("🏭 Sector Analysis")
st.caption("Sprint 4 | Day 22 scaffold — full content coming on Day 26")

sectors = get_sectors()
companies = get_companies()

broad_sectors = sorted(sectors["broad_sector"].dropna().unique().tolist())
selected = st.selectbox("Select Broad Sector", ["All"] + broad_sectors, index=0)

if selected != "All":
    filtered = companies[companies["broad_sector"] == selected]
else:
    filtered = companies

st.metric("Companies in view", len(filtered))
st.dataframe(
    filtered[["id", "company_name", "broad_sector", "sub_sector", "roe_percentage", "roce_percentage"]],
    use_container_width=True,
)
