"""
pages/07_capital.py — Capital Allocation
==========================================
Sprint 4 Day 22: Stub page — renders without errors.
Full implementation: Day 26.
"""

import streamlit as st
import pandas as pd
from pathlib import Path

st.title("💰 Capital Allocation")
st.caption("Sprint 4 | Day 22 scaffold — full content coming on Day 26")

_REPO_ROOT = Path(__file__).resolve().parents[3]
capital_csv = _REPO_ROOT / "output" / "capital_allocation.csv"

if capital_csv.exists():
    df = pd.read_csv(capital_csv)
    st.dataframe(df, use_container_width=True)
else:
    st.warning(
        f"capital_allocation.csv not found at {capital_csv}. "
        "Run: python generate_capital_allocation.py"
    )
