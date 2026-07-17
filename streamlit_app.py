"""
streamlit_app.py — Root entry point for Streamlit Community Cloud.
==================================================================
Streamlit Cloud looks for this file at the repo root by default.
It patches sys.path so that `from src.dashboard...` imports resolve,
then delegates execution to src/dashboard/app.py.

Local dev: run `streamlit run src/dashboard/app.py` as before.
Cloud:     Streamlit Cloud runs this file automatically.
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path so all src.* imports resolve
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Run the dashboard app
import runpy
runpy.run_path(str(_REPO_ROOT / "src" / "dashboard" / "app.py"), run_name="__main__")
