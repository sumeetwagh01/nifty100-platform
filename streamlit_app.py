"""
streamlit_app.py — Root entry point for Streamlit Community Cloud.
==================================================================
Streamlit Cloud looks for this file at the repo root by default.
It patches sys.path so that `from src.dashboard...` imports resolve,
then executes src/dashboard/app.py in-process.

Local dev: run `streamlit run src/dashboard/app.py` as before.
Cloud:     Streamlit Cloud runs this file automatically.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patch sys.path — MUST come before any project imports.
# Insert repo root so all `src.*` imports resolve on Streamlit Cloud (Linux).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Execute app.py in-place.
# We compile and exec rather than runpy.run_path so that __file__ inside
# app.py resolves correctly (needed for st.Page relative path resolution).
# ---------------------------------------------------------------------------
_APP_PY = _REPO_ROOT / "src" / "dashboard" / "app.py"
_code = compile(_APP_PY.read_text(encoding="utf-8"), str(_APP_PY), "exec")
exec(_code, {"__file__": str(_APP_PY), "__name__": "__main__"})

