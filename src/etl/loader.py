"""
src/etl/loader.py

Excel file loader for the Nifty 100 Financial Intelligence Platform
(Module 1 — Data Engineering & ETL Pipeline, Sprint 1, Day 2).

Per Section 5 (Dataset Catalogue) load note:
    "Core files use pd.read_excel(path, header=1) — Row 0 is metadata;
     Row 1 is actual headers. Supplementary files use header=0."

This module is intentionally limited in scope to Day 2's deliverable:
reading the raw Excel files into clean DataFrames with correct column
headers. Deduplication (DQ-02), the 16-rule schema validator, and the
SQLite write-through come in Days 3-5 (schema_validator.py, db/loader.py).

Usage:
    from src.etl.loader import load_all_core_files, load_all_supplementary_files

    core = load_all_core_files()
    companies_df = core["companies"]
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
SUPPORTING_DATA_DIR = Path(os.getenv("SUPPORTING_DATA_DIR", "data/supporting"))

if not RAW_DATA_DIR.is_absolute():
    RAW_DATA_DIR = PROJECT_ROOT / RAW_DATA_DIR
if not SUPPORTING_DATA_DIR.is_absolute():
    SUPPORTING_DATA_DIR = PROJECT_ROOT / SUPPORTING_DATA_DIR

# The 7 core datasets and their sheet names (Section 5: Dataset Catalogue).
# Core files store a metadata title in row 0 and the real header in row 1,
# so every core load uses header=1.
CORE_FILES: dict[str, dict] = {
    "companies": {"filename": "companies.xlsx", "sheet": "Companies"},
    "profitandloss": {"filename": "profitandloss.xlsx", "sheet": "Profit & Loss"},
    "balancesheet": {"filename": "balancesheet.xlsx", "sheet": "Balance Sheet"},
    "cashflow": {"filename": "cashflow.xlsx", "sheet": "Cash Flow"},
    "analysis": {"filename": "analysis.xlsx", "sheet": "Analysis"},
    "documents": {"filename": "documents.xlsx", "sheet": "Documents"},
    "prosandcons": {"filename": "prosandcons.xlsx", "sheet": "Pros & Cons"},
}

# The 5 supplementary datasets (Section 6). These were created for this
# project rather than scraped, and use a plain header=0 row.
SUPPORTING_FILES: dict[str, dict] = {
    "sectors": {"filename": "sectors.xlsx", "sheet": None},
    "stock_prices": {"filename": "stock_prices.xlsx", "sheet": None},
    "market_cap": {"filename": "market_cap.xlsx", "sheet": None},
    "financial_ratios": {"filename": "financial_ratios.xlsx", "sheet": None},
    "peer_groups": {"filename": "peer_groups.xlsx", "sheet": None},
}


class LoaderError(Exception):
    """Raised when an Excel file cannot be read at all (missing/corrupt)."""


def load_core_excel(path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Load one core dataset file with header=1 (Feature 1.1).

    Row 0 in core files is a metadata/title row (sometimes a single merged
    cell spanning the sheet width); using header=1 skips it entirely so
    merged-cell artefacts in row 0 never reach the DataFrame. If a sheet
    name is not supplied, pandas reads the first sheet.
    """
    if not path.exists():
        raise LoaderError(f"Core file not found: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name or 0, header=1)
    except Exception as exc:  # noqa: BLE001 - surfaced as LoaderError for callers
        raise LoaderError(f"Failed to read core file {path.name}: {exc}") from exc

    # Defensive cleanup: drop fully-empty columns/rows that sometimes appear
    # at the edges of exported sheets, and strip whitespace from string
    # column headers (a common side-effect of merged title cells above).
    df = df.dropna(axis="columns", how="all").dropna(axis="rows", how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def load_supplementary_excel(
    path: Path, sheet_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Load one supplementary dataset file with header=0 (Section 5 load note).
    """
    if not path.exists():
        raise LoaderError(f"Supplementary file not found: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name or 0, header=0)
    except Exception as exc:  # noqa: BLE001
        raise LoaderError(
            f"Failed to read supplementary file {path.name}: {exc}"
        ) from exc

    df = df.dropna(axis="columns", how="all").dropna(axis="rows", how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def load_all_core_files(raw_dir: Optional[Path] = None) -> dict[str, pd.DataFrame]:
    """
    Load all 7 core files. Returns a dict keyed by the short dataset name
    (e.g. 'companies', 'profitandloss'). Files that are missing or fail to
    parse are logged and skipped rather than raising, so a partial data/raw/
    directory does not block loading the files that *are* present.
    """
    raw_dir = raw_dir or RAW_DATA_DIR
    frames: dict[str, pd.DataFrame] = {}

    for key, spec in CORE_FILES.items():
        path = raw_dir / spec["filename"]
        try:
            frames[key] = load_core_excel(path, sheet_name=spec["sheet"])
            logger.info(
                "Loaded %s: %d rows x %d cols",
                spec["filename"],
                len(frames[key]),
                len(frames[key].columns),
            )
        except LoaderError as exc:
            logger.warning("Skipping %s: %s", spec["filename"], exc)

    return frames


def load_all_supplementary_files(
    supporting_dir: Optional[Path] = None,
) -> dict[str, pd.DataFrame]:
    """
    Load all 5 supplementary files. Same skip-and-log behaviour as
    load_all_core_files().
    """
    supporting_dir = supporting_dir or SUPPORTING_DATA_DIR
    frames: dict[str, pd.DataFrame] = {}

    for key, spec in SUPPORTING_FILES.items():
        path = supporting_dir / spec["filename"]
        try:
            frames[key] = load_supplementary_excel(path, sheet_name=spec["sheet"])
            logger.info(
                "Loaded %s: %d rows x %d cols",
                spec["filename"],
                len(frames[key]),
                len(frames[key].columns),
            )
        except LoaderError as exc:
            logger.warning("Skipping %s: %s", spec["filename"], exc)

    return frames


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print(f"Raw data dir:         {RAW_DATA_DIR}")
    print(f"Supporting data dir:  {SUPPORTING_DATA_DIR}")
    print()

    core = load_all_core_files()
    supporting = load_all_supplementary_files()

    print(f"Core files loaded:         {len(core)} / {len(CORE_FILES)}")
    print(f"Supplementary files loaded: {len(supporting)} / {len(SUPPORTING_FILES)}")

    missing_core = set(CORE_FILES) - set(core)
    missing_supporting = set(SUPPORTING_FILES) - set(supporting)
    if missing_core:
        print(
            f"\nMissing core files (place in {RAW_DATA_DIR}/): {sorted(missing_core)}"
        )
    if missing_supporting:
        print(
            f"Missing supplementary files (place in {SUPPORTING_DATA_DIR}/): {sorted(missing_supporting)}"
        )

    for key, df in {**core, **supporting}.items():
        print(f"  {key:<20} {len(df):>6} rows  x {len(df.columns):>3} cols")
