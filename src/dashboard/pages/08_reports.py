"""
pages/08_reports.py — Reports & Exports
=========================================
Sprint 4 Day 22: Stub page — renders without errors.
Full implementation: Day 27/28.
"""

import streamlit as st
from pathlib import Path

st.title("📄 Reports & Exports")
st.caption("Sprint 4 | Day 22 scaffold — full content coming on Days 27–28")

_REPO_ROOT = Path(__file__).resolve().parents[3]
output_dir = _REPO_ROOT / "output"
reports_dir = _REPO_ROOT / "reports"

st.subheader("Available Output Files")

outputs = [
    ("Screener Output", output_dir / "screener_output.xlsx"),
    ("Peer Comparison", output_dir / "peer_comparison.xlsx"),
    ("Capital Allocation", output_dir / "capital_allocation.csv"),
    ("Load Audit", output_dir / "load_audit.csv"),
    ("Validation Failures", output_dir / "validation_failures.csv"),
]

for label, path in outputs:
    exists = path.exists()
    icon = "✅" if exists else "❌"
    st.markdown(f"{icon} **{label}** — `{path.name}`")

st.divider()
st.subheader("Radar Charts")
radar_dir = reports_dir / "radar_charts"
if radar_dir.exists():
    pngs = list(radar_dir.glob("*.png"))
    st.metric("Radar Charts Generated", len(pngs))
else:
    st.warning("No radar charts found. Run the RadarChartGenerator first.")
