"""
src/analytics/edge_case_logger.py
==================================
Sprint 2 Day 13 — ratio_edge_cases.log writer.

Logs every anomaly encountered during KPI computation:
  - CAGR turnarounds / sentinels
  - ROCE anomalies vs Screener pre-computed value (diff > 5%)
  - ROE anomalies vs Screener pre-computed value
  - Bank ROCE carve-out suppressions
  - High D/E flag suppressions for Financials sector

Each log entry is a structured line:
  TIMESTAMP | CATEGORY | company_id | year | detail

Categories
----------
  CAGR_EDGE          TURNAROUND / DECLINE_TO_LOSS / BOTH_NEGATIVE / ZERO_BASE / INSUFFICIENT
  ROCE_MISMATCH      computed vs screener diff > 5%
  ROE_MISMATCH       computed vs screener diff significant
  BANK_CARVE_OUT     ROCE suppressed for Financials sector
  DE_FLAG_SUPPRESSED high D/E flag suppressed for Financials sector
  DATA_SOURCE_ISSUE  likely raw data problem
  VERSION_DIFF       likely Screener formula version difference
  FORMULA_DISCREPANCY our formula differs from Screener methodology
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("output/ratio_edge_cases.log")

# Anomaly category constants
CAGR_EDGE           = "CAGR_EDGE"
ROCE_MISMATCH       = "ROCE_MISMATCH"
ROE_MISMATCH        = "ROE_MISMATCH"
BANK_CARVE_OUT      = "BANK_CARVE_OUT"
DE_FLAG_SUPPRESSED  = "DE_FLAG_SUPPRESSED"
DATA_SOURCE_ISSUE   = "DATA_SOURCE_ISSUE"
VERSION_DIFF        = "VERSION_DIFF"
FORMULA_DISCREPANCY = "FORMULA_DISCREPANCY"

# Thresholds
ROCE_MISMATCH_THRESHOLD = 5.0   # percent
ROE_MISMATCH_THRESHOLD  = 5.0   # percent


def _setup_logger(log_path: Path) -> logging.Logger:
    """Configure a file logger for edge cases."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("edge_cases")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


_logger = _setup_logger(LOG_PATH)


def _entry(
    category: str,
    company_id: int,
    company_name: str,
    year: int | None,
    detail: str,
) -> str:
    return f"{category} | company_id={company_id} ({company_name}) | year={year} | {detail}"


# ---------------------------------------------------------------------------
# Public logging functions
# ---------------------------------------------------------------------------

def log_cagr_edge(
    company_id: int,
    company_name: str,
    year: int,
    metric: str,
    window: int,
    flag: str,
) -> None:
    """
    Log a CAGR sentinel (turnaround, decline-to-loss, etc.)

    Parameters
    ----------
    metric : 'revenue' | 'pat' | 'eps'
    window : 3 | 5 | 10
    flag   : one of the CAGR sentinel strings
    """
    detail = f"metric={metric} window={window}yr flag={flag}"
    _logger.info(_entry(CAGR_EDGE, company_id, company_name, year, detail))


def log_roce_mismatch(
    company_id: int,
    company_name: str,
    computed: float | None,
    screener: float | None,
    diff: float,
    classification: str,
) -> None:
    """
    Log ROCE anomaly where |computed - screener| > 5%.

    classification : 'data_source_issue' | 'version_difference' | 'formula_discrepancy'
    """
    detail = (
        f"computed_roce={computed:.2f}% screener_roce={screener:.2f}% "
        f"diff={diff:.2f}% classification={classification}"
    )
    _logger.warning(_entry(ROCE_MISMATCH, company_id, company_name, None, detail))


def log_roe_mismatch(
    company_id: int,
    company_name: str,
    computed: float | None,
    screener: float | None,
    diff: float,
    classification: str,
) -> None:
    """
    Log ROE anomaly.

    Note: Screener's roe_percentage may be anomalous for some companies
    (e.g. TCS shows 0.52 — likely a display/unit issue, not an error).
    classification should note this.
    """
    detail = (
        f"computed_roe={computed:.2f}% screener_roe={screener} "
        f"diff={diff:.2f}% classification={classification}"
    )
    _logger.warning(_entry(ROE_MISMATCH, company_id, company_name, None, detail))


def log_bank_carve_out(
    company_id: int,
    company_name: str,
) -> None:
    """Log that ROCE was suppressed (set to None) for a Financials sector company."""
    detail = "ROCE suppressed — Financials sector, sector-relative benchmark required"
    _logger.info(_entry(BANK_CARVE_OUT, company_id, company_name, None, detail))


def log_de_flag_suppressed(
    company_id: int,
    company_name: str,
    de_value: float,
) -> None:
    """Log that high D/E flag was suppressed for a Financials sector company."""
    detail = f"D/E={de_value:.2f} — high_leverage_flag suppressed for Financials sector"
    _logger.info(_entry(DE_FLAG_SUPPRESSED, company_id, company_name, None, detail))


def log_session_header(db_path: str, company_count: int) -> None:
    """Write a session header to separate pipeline runs in the log."""
    _logger.info(
        f"{'='*60} NEW RUN | db={db_path} | companies={company_count} {'='*60}"
    )


def log_session_footer(rows_written: int, anomalies: int) -> None:
    """Write a session footer with summary stats."""
    _logger.info(
        f"{'='*60} RUN COMPLETE | rows_written={rows_written} | anomalies_logged={anomalies} {'='*60}"
    )
