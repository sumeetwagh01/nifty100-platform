"""
src/screener/presets.py
=======================
Sprint 3 Day 16 — 6 Preset Screeners.

Each preset is a named filter configuration built on top of ScreenerEngine.
Presets can be run directly against a DataFrame or DB.

Presets
-------
  quality_compounder    ROE > 15%, D/E < 1.0, FCF > 0, Revenue CAGR 5yr > 10%
  value_pick            P/E < 20, P/B < 3.0, D/E < 2.0, Dividend Yield > 1%
  growth_accelerator    PAT CAGR 5yr > 20%, Revenue CAGR 5yr > 15%, D/E < 2.0
  dividend_champion     Dividend Yield > 2%, Dividend Payout < 80%, FCF > 0
  debt_free_blue_chip   D/E = 0, ROE > 12%, Revenue > 5000 Cr
  turnaround_watch      Revenue CAGR 3yr > 10%, FCF > 0, D/E declining YoY

Usage
-----
    from src.screener.presets import PresetScreener

    ps = PresetScreener(df=my_df)
    results = ps.run("quality_compounder")
    all_results = ps.run_all()
"""

from __future__ import annotations

import pandas as pd

from src.screener.engine import ScreenerEngine


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "quality_compounder": {
        "label":       "Quality Compounder",
        "description": "High ROE, low debt, positive FCF, strong revenue growth",
        "filters": {
            "roe_min":              15.0,
            "de_max":               1.0,
            "fcf_min":              0.0,
            "revenue_cagr_5yr_min": 10.0,
        },
    },
    "value_pick": {
        "label":       "Value Pick",
        "description": "Low P/E, low P/B, manageable debt, dividend paying",
        "filters": {
            "pe_max":             20.0,
            "pb_max":              3.0,
            "de_max":              2.0,
            "dividend_yield_min":  1.0,
        },
    },
    "growth_accelerator": {
        "label":       "Growth Accelerator",
        "description": "High PAT and Revenue CAGR with manageable leverage",
        "filters": {
            "pat_cagr_5yr_min":     20.0,
            "revenue_cagr_5yr_min": 15.0,
            "de_max":                2.0,
        },
    },
    "dividend_champion": {
        "label":       "Dividend Champion",
        "description": "Strong dividend yield, sustainable payout, positive FCF",
        "filters": {
            "dividend_yield_min": 2.0,
            "fcf_min":            0.0,
        },
        # dividend_payout < 80% handled as a custom filter (max direction)
        "custom_filters": {
            "dividend_payout_ratio_pct": {"direction": "max", "threshold": 80.0},
        },
    },
    "debt_free_blue_chip": {
        "label":       "Debt-Free Blue Chip",
        "description": "Zero debt, solid ROE, large revenue base",
        "filters": {
            "de_max":    0.0,
            "roe_min":  12.0,
            "sales_min": 5000.0,
        },
    },
    "turnaround_watch": {
        "label":       "Turnaround Watch",
        "description": "Strong 3yr revenue growth, positive FCF, declining D/E",
        "filters": {
            "revenue_cagr_5yr_min": 10.0,   # proxy for 3yr (uses available CAGR)
            "fcf_min":               0.0,
        },
        # D/E declining YoY handled via custom logic
        "requires_de_decline": True,
    },
}


# ---------------------------------------------------------------------------
# PresetScreener
# ---------------------------------------------------------------------------

class PresetScreener:
    """
    Run named preset filters against a financial_ratios DataFrame.

    Parameters
    ----------
    df          : DataFrame with financial_ratios + company_name + broad_sector
    config_path : optional path to screener_config.yaml
    """

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        config_path=None,
    ) -> None:
        kwargs = {"df": df}
        if config_path is not None:
            kwargs["config_path"] = config_path
        self._engine = ScreenerEngine(**kwargs)
        self._df = df

    def load_from_db(self, db_path: str) -> "PresetScreener":
        self._engine.load_from_db(db_path)
        self._df = self._engine._df
        return self

    # ---------------------------------------------------------------------------
    # Run a single preset
    # ---------------------------------------------------------------------------

    def run(
        self,
        preset_name: str,
        df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Run a named preset and return filtered DataFrame.

        Parameters
        ----------
        preset_name : one of the 6 preset keys
        df          : optional DataFrame override

        Raises
        ------
        KeyError if preset_name is not recognised
        """
        if preset_name not in PRESETS:
            raise KeyError(
                f"Unknown preset: '{preset_name}'. "
                f"Valid presets: {list(PRESETS)}"
            )

        preset = PRESETS[preset_name]
        filters = preset.get("filters", {})
        custom  = preset.get("custom_filters", {})

        # Apply standard engine filters
        result = self._engine.apply(filters, df=df)

        # Apply custom filters (not in screener_config.yaml)
        result = self._apply_custom_filters(result, custom)

        # Turnaround Watch — D/E declining YoY
        if preset.get("requires_de_decline"):
            result = self._filter_de_declining(result)

        return result

    # ---------------------------------------------------------------------------
    # Run all 6 presets
    # ---------------------------------------------------------------------------

    def run_all(
        self,
        df: pd.DataFrame | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Run all 6 presets and return a dict of {preset_name: DataFrame}.

        Useful for batch output or Excel multi-sheet generation.
        """
        return {name: self.run(name, df=df) for name in PRESETS}

    # ---------------------------------------------------------------------------
    # Preset metadata
    # ---------------------------------------------------------------------------

    def available_presets(self) -> list[dict]:
        """Return list of preset metadata dicts (name, label, description)."""
        return [
            {
                "name":        name,
                "label":       meta["label"],
                "description": meta["description"],
                "filter_count": len(meta.get("filters", {}))
                               + len(meta.get("custom_filters", {})),
            }
            for name, meta in PRESETS.items()
        ]

    def preset_filters(self, preset_name: str) -> dict:
        """Return the filter thresholds for a named preset."""
        if preset_name not in PRESETS:
            raise KeyError(f"Unknown preset: '{preset_name}'")
        return PRESETS[preset_name].get("filters", {})

    # ---------------------------------------------------------------------------
    # Custom filter helpers
    # ---------------------------------------------------------------------------

    def _apply_custom_filters(
        self,
        df: pd.DataFrame,
        custom_filters: dict,
    ) -> pd.DataFrame:
        """
        Apply column-level filters not covered by screener_config.yaml.

        custom_filters format:
            {"col_name": {"direction": "max"|"min", "threshold": float}}
        """
        result = df.copy()
        for col, spec in custom_filters.items():
            if col not in result.columns:
                continue
            values = pd.to_numeric(result[col], errors="coerce")
            threshold = spec["threshold"]
            if spec["direction"] == "max":
                mask = values <= threshold
            else:
                mask = values >= threshold
            result = result[mask.fillna(False)]
        return result

    def _filter_de_declining(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Turnaround Watch: keep only companies where D/E is declining YoY.

        Requires multi-year data. If only latest year available,
        passes all through (cannot verify trend).
        """
        if self._df is None or "company_id" not in self._df.columns:
            return df
        if "year" not in self._df.columns or "debt_to_equity" not in self._df.columns:
            return df   # single-year snapshot — cannot verify trend, pass all through

        # Find companies with declining D/E over last 2 available years
        de_trend = (
            self._df[["company_id", "year", "debt_to_equity"]]
            .dropna(subset=["debt_to_equity"])
            .sort_values(["company_id", "year"])
            .groupby("company_id")
            .tail(2)
        )

        declining = set()
        for cid, grp in de_trend.groupby("company_id"):
            if len(grp) >= 2:
                de_values = grp["debt_to_equity"].tolist()
                if de_values[-1] < de_values[-2]:
                    declining.add(cid)

        if not declining:
            return df   # can't determine trend — pass all through

        return df[df["company_id"].isin(declining)]
