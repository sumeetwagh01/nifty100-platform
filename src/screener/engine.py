"""
src/screener/engine.py
======================
Sprint 3 Day 15 — Filter Engine Core.

Loads screener_config.yaml and applies threshold filters to a
financial_ratios DataFrame. Returns a sorted, filtered DataFrame
with composite_quality_score column included.

Special rules
-------------
  D/E filter   : companies in Financials sector are automatically skipped
                 (high leverage is structural, not a risk signal)
  ICR filter   : icr_label = 'Debt Free' is treated as ICR = infinity
                 (always passes any ICR minimum threshold)
  CAGR columns : sentinel-flagged rows (non-numeric flag) are excluded
                 from CAGR filters — they cannot satisfy a numeric threshold

Usage
-----
    from src.screener.engine import ScreenerEngine

    engine = ScreenerEngine()
    results = engine.apply({
        "roe_min": 15.0,
        "de_max": 1.0,
        "revenue_cagr_5yr_min": 10.0,
    })
    # returns sorted DataFrame
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "screener_config.yaml"

DEBT_FREE_LABEL = "Debt Free"
INFINITY = math.inf


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: Path = CONFIG_PATH) -> dict:
    """Load screener_config.yaml. Falls back to hardcoded defaults if yaml unavailable."""
    if not _YAML_AVAILABLE:
        return _default_config()
    if not config_path.exists():
        return _default_config()
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _default_config() -> dict:
    """Minimal hardcoded config used when yaml is not installed."""
    return {
        "metrics": {
            "roe_min":              {"column": "return_on_equity_pct",       "direction": "min", "sector_skip": []},
            "de_max":               {"column": "debt_to_equity",             "direction": "max", "sector_skip": ["Financials"]},
            "fcf_min":              {"column": "free_cash_flow_cr",          "direction": "min", "sector_skip": []},
            "revenue_cagr_5yr_min": {"column": "revenue_cagr_5yr",          "direction": "min", "sector_skip": []},
            "pat_cagr_5yr_min":     {"column": "pat_cagr_5yr",              "direction": "min", "sector_skip": []},
            "opm_min":              {"column": "operating_profit_margin_pct","direction": "min", "sector_skip": []},
            "pe_max":               {"column": "pe_ratio",                   "direction": "max", "sector_skip": []},
            "pb_max":               {"column": "pb_ratio",                   "direction": "max", "sector_skip": []},
            "dividend_yield_min":   {"column": "dividend_yield_pct",         "direction": "min", "sector_skip": []},
            "icr_min":              {"column": "interest_coverage",          "direction": "min", "sector_skip": [], "debt_free_passes": True},
            "market_cap_min":       {"column": "market_cap_cr",              "direction": "min", "sector_skip": []},
            "net_profit_min":       {"column": "net_profit_margin_pct",      "direction": "min", "sector_skip": []},
            "eps_cagr_5yr_min":     {"column": "eps_cagr_5yr",              "direction": "min", "sector_skip": []},
            "asset_turnover_min":   {"column": "asset_turnover",             "direction": "min", "sector_skip": []},
            "sales_min":            {"column": "sales",                      "direction": "min", "sector_skip": []},
        }
    }


# ---------------------------------------------------------------------------
# ScreenerEngine
# ---------------------------------------------------------------------------

class ScreenerEngine:
    """
    Apply threshold filters to a financial_ratios DataFrame.

    Parameters
    ----------
    df          : DataFrame with financial_ratios columns + broad_sector + company_name
    config_path : path to screener_config.yaml (optional override)
    """

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        config_path: Path = CONFIG_PATH,
    ) -> None:
        self.config = load_config(config_path)
        self.metrics = self.config.get("metrics", {})
        self._df = df

    def load_from_db(self, db_path: str) -> "ScreenerEngine":
        """
        Load financial_ratios joined with company name and sector from SQLite.

        Returns self for chaining.
        """
        import sqlite3
        conn = sqlite3.connect(db_path)
        query = """
            SELECT
                fr.*,
                c.company_name,
                COALESCE(s.broad_sector, '') AS broad_sector
            FROM financial_ratios fr
            JOIN companies c ON c.id = fr.company_id
            LEFT JOIN sectors s ON s.company_id = fr.company_id
            WHERE fr.year = (
                SELECT MAX(year) FROM financial_ratios
                WHERE company_id = fr.company_id
            )
        """
        self._df = pd.read_sql_query(query, conn)
        conn.close()
        return self

    # ---------------------------------------------------------------------------
    # Core apply method
    # ---------------------------------------------------------------------------

    def apply(
        self,
        filters: dict[str, Any],
        df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Apply threshold filters and return sorted DataFrame.

        Parameters
        ----------
        filters : dict mapping metric_key → threshold value
                  e.g. {"roe_min": 15.0, "de_max": 1.0}
        df      : optional DataFrame override (uses self._df if not provided)

        Returns
        -------
        Filtered DataFrame sorted by composite_quality_score descending.
        Columns include all financial_ratios fields + company_name + broad_sector.

        Raises
        ------
        ValueError  if no DataFrame is available
        KeyError    if an unknown filter key is passed
        """
        source = df if df is not None else self._df
        if source is None:
            raise ValueError("No DataFrame loaded. Call load_from_db() or pass df=")

        result = source.copy()

        for key, threshold in filters.items():
            if threshold is None:
                continue
            if key not in self.metrics:
                raise KeyError(f"Unknown filter key: '{key}'. Valid keys: {list(self.metrics)}")

            result = self._apply_single_filter(result, key, threshold)

        # Sort by composite_quality_score descending
        if "composite_quality_score" in result.columns:
            result = result.sort_values("composite_quality_score", ascending=False)

        return result.reset_index(drop=True)

    # ---------------------------------------------------------------------------
    # Single filter application
    # ---------------------------------------------------------------------------

    def _apply_single_filter(
        self,
        df: pd.DataFrame,
        key: str,
        threshold: float,
    ) -> pd.DataFrame:
        """Apply one filter, respecting sector_skip and special rules."""
        metric = self.metrics[key]
        col        = metric["column"]
        direction  = metric["direction"]
        sector_skip = [s.lower() for s in metric.get("sector_skip", [])]
        debt_free_passes = metric.get("debt_free_passes", False)

        # Build sector mask — rows in skip sectors are excluded from this filter
        # (they pass through regardless)
        if sector_skip and "broad_sector" in df.columns:
            in_skip_sector = df["broad_sector"].str.lower().isin(sector_skip)
        else:
            in_skip_sector = pd.Series(False, index=df.index)

        # ICR special rule — Debt Free rows always pass ICR filters
        if debt_free_passes and "icr_label" in df.columns:
            is_debt_free = df["icr_label"] == DEBT_FREE_LABEL
        else:
            is_debt_free = pd.Series(False, index=df.index)

        # Column may not exist in df (e.g. pe_ratio from market data not yet joined)
        if col not in df.columns:
            return df   # can't filter — pass all through

        values = pd.to_numeric(df[col], errors="coerce")

        if direction == "min":
            passes_threshold = values >= threshold
        else:   # max
            passes_threshold = values <= threshold

        # Final mask: passes threshold OR is in skip sector OR is debt free
        keep = passes_threshold | in_skip_sector | is_debt_free

        # Rows with NaN in the column fail the filter (unless skip sector / debt free)
        nan_mask = values.isna()
        keep = keep & ~nan_mask | in_skip_sector | is_debt_free

        return df[keep]

    # ---------------------------------------------------------------------------
    # Convenience: validate filters dict before applying
    # ---------------------------------------------------------------------------

    def validate_filters(self, filters: dict) -> list[str]:
        """
        Return list of error strings for invalid filter keys or values.
        Empty list means all filters are valid.
        """
        errors = []
        for key, value in filters.items():
            if key not in self.metrics:
                errors.append(f"Unknown filter key: '{key}'")
                continue
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"Filter '{key}' value must be numeric, got {type(value).__name__}")
        return errors

    def available_filters(self) -> list[str]:
        """Return list of all valid filter keys."""
        return list(self.metrics.keys())
