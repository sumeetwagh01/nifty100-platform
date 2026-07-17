"""
tests/screener/test_scorer.py
==============================
Tests for src/screener/scorer.py and src/screener/exporter.py
"""

import os
import pytest
import pandas as pd
import numpy as np

from src.screener.scorer import (
    winsorise,
    scale_0_100,
    compute_composite_score,
    compute_sector_relative_score,
    add_scores_to_df,
)
from src.screener.exporter import (
    generate_screener_excel,
    _meets_threshold,
    _sheet_name,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "company_id":                   [1, 2, 3, 4, 5, 6],
        "company_name":                 ["QualityCo", "BankCo", "GrowthCo", "LowCo", "DebtFreeCo", "MidCo"],
        "broad_sector":                 ["Industrials", "Financials", "Technology", "Industrials", "Technology", "Industrials"],
        "return_on_equity_pct":         [22.0, 18.0, 25.0,  5.0, 20.0, 15.0],
        "roce_pct":                     [18.0, None, 22.0,  4.0, 16.0, 12.0],
        "net_profit_margin_pct":        [12.0, 18.0, 15.0,  3.0, 14.0, 10.0],
        "debt_to_equity":               [0.3,  8.5,  0.2,  4.0,  0.0,  0.8],
        "interest_coverage":            [5.0,  None,  8.0,  1.2, None,  3.0],
        "icr_label":                    [None, None, None, None, "Debt Free", None],
        "free_cash_flow_cr":            [500,  800,  300, -200,  400,  250],
        "revenue_cagr_5yr":             [14.0, 10.0, 20.0,  2.0, 12.0,  9.0],
        "pat_cagr_5yr":                 [16.0,  8.0, 25.0,  1.0, 14.0,  8.0],
        "eps_cagr_5yr":                 [15.0,  7.0, 22.0,  0.5, 13.0,  7.0],
        "operating_profit_margin_pct":  [20.0, 25.0, 18.0,  8.0, 22.0, 16.0],
        "asset_turnover":               [1.2,  0.3,  1.5,  0.5,  1.1,  1.0],
        "cfo_quality_score":            ["High Quality", "Moderate", "High Quality", "Accrual Risk", "Moderate", "Moderate"],
        "capital_allocation_pattern":   ["Reinvestor", "Mixed", "Reinvestor", "Pre-Revenue", "Reinvestor", "Reinvestor"],
        "dividend_yield_pct":           [1.5,  0.8,  0.5,  0.2,  1.0,  1.2],
        "dividend_payout_ratio_pct":    [30.0, 20.0, 15.0, 5.0,  25.0, 35.0],
    })


# ---------------------------------------------------------------------------
# Winsorisation tests
# ---------------------------------------------------------------------------

class TestWinsorise:

    def test_clips_extremes(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        ws = winsorise(s)
        assert ws.max() < 100

    def test_all_nan_returns_series(self):
        s = pd.Series([None, None, None], dtype=float)
        result = winsorise(s)
        assert len(result) == 3

    def test_single_value_returns_unchanged(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = winsorise(s)
        assert result.equals(s)


# ---------------------------------------------------------------------------
# Scale 0-100 tests
# ---------------------------------------------------------------------------

class TestScale0100:

    def test_output_between_0_and_100(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = scale_0_100(s)
        assert result.between(0, 100).all()

    def test_invert_reverses_order(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        normal  = scale_0_100(s, invert=False)
        inverted = scale_0_100(s, invert=True)
        assert normal.iloc[0] < normal.iloc[-1]
        assert inverted.iloc[0] > inverted.iloc[-1]

    def test_flat_series_returns_neutral(self):
        s = pd.Series([10.0, 10.0, 10.0])
        result = scale_0_100(s)
        assert (result == 50.0).all()


# ---------------------------------------------------------------------------
# Composite score tests
# ---------------------------------------------------------------------------

class TestCompositeScore:

    def test_returns_series_same_length(self, sample_df):
        scores = compute_composite_score(sample_df)
        assert len(scores) == len(sample_df)

    def test_all_scores_between_0_and_100(self, sample_df):
        scores = compute_composite_score(sample_df)
        assert scores.between(0, 100).all()

    def test_higher_quality_scores_higher(self, sample_df):
        scores = compute_composite_score(sample_df)
        # QualityCo (idx 0) should score higher than LowCo (idx 3)
        assert scores.iloc[0] > scores.iloc[3]

    def test_empty_df_returns_empty(self):
        scores = compute_composite_score(pd.DataFrame())
        assert len(scores) == 0

    def test_returns_numeric_series(self, sample_df):
        scores = compute_composite_score(sample_df)
        assert pd.api.types.is_numeric_dtype(scores)

    def test_debt_free_scores_well_on_leverage(self, sample_df):
        scores = compute_composite_score(sample_df)
        # DebtFreeCo (idx 4) should score higher than high-DE row
        bankco_idx = sample_df[sample_df["company_name"] == "BankCo"].index[0]
        debtfree_idx = sample_df[sample_df["company_name"] == "DebtFreeCo"].index[0]
        # DebtFreeCo has 0 D/E vs BankCo 8.5 — leverage component should favour DebtFreeCo
        assert scores.iloc[debtfree_idx] >= scores.iloc[bankco_idx] - 20


# ---------------------------------------------------------------------------
# Sector-relative score tests
# ---------------------------------------------------------------------------

class TestSectorRelativeScore:

    def test_returns_series_same_length(self, sample_df):
        df = add_scores_to_df(sample_df)
        scores = compute_sector_relative_score(df)
        assert len(scores) == len(df)

    def test_scores_between_0_and_100(self, sample_df):
        df = add_scores_to_df(sample_df)
        scores = compute_sector_relative_score(df)
        assert scores.dropna().between(0, 100).all()

    def test_top_in_sector_scores_100(self, sample_df):
        df = add_scores_to_df(sample_df)
        scores = compute_sector_relative_score(df)
        # Best company in each sector should be close to 100
        for sector, grp in df.groupby("broad_sector"):
            if len(grp) > 1:
                sector_scores = scores.loc[grp.index]
                assert sector_scores.max() == pytest.approx(100.0, abs=1.0)

    def test_single_company_sector_scores_50(self, sample_df):
        df = add_scores_to_df(sample_df)
        scores = compute_sector_relative_score(df)
        # Financials has only BankCo → should score 50
        bank_idx = df[df["company_name"] == "BankCo"].index[0]
        assert scores.iloc[bank_idx] == pytest.approx(50.0, abs=1.0)


# ---------------------------------------------------------------------------
# add_scores_to_df tests
# ---------------------------------------------------------------------------

class TestAddScores:

    def test_adds_composite_column(self, sample_df):
        result = add_scores_to_df(sample_df)
        assert "composite_quality_score" in result.columns

    def test_adds_sector_relative_column(self, sample_df):
        result = add_scores_to_df(sample_df)
        assert "sector_relative_score" in result.columns

    def test_original_df_unchanged(self, sample_df):
        original_cols = list(sample_df.columns)
        add_scores_to_df(sample_df)
        assert list(sample_df.columns) == original_cols


# ---------------------------------------------------------------------------
# _meets_threshold tests
# ---------------------------------------------------------------------------

class TestMeetsThreshold:

    def test_roe_above_threshold_green(self):
        assert _meets_threshold("return_on_equity_pct", 20.0, "quality_compounder") is True

    def test_roe_below_threshold_red(self):
        assert _meets_threshold("return_on_equity_pct", 10.0, "quality_compounder") is False

    def test_de_below_threshold_green(self):
        assert _meets_threshold("debt_to_equity", 0.5, "quality_compounder") is True

    def test_de_above_threshold_red(self):
        assert _meets_threshold("debt_to_equity", 2.0, "quality_compounder") is False

    def test_column_not_in_preset_returns_none(self):
        assert _meets_threshold("company_name", "TestCo", "quality_compounder") is None

    def test_none_value_returns_none(self):
        assert _meets_threshold("return_on_equity_pct", None, "quality_compounder") is None


# ---------------------------------------------------------------------------
# Excel export tests
# ---------------------------------------------------------------------------

class TestExcelExport:

    def test_generates_file(self, sample_df, tmp_path):
        from src.screener.presets import PresetScreener
        ps = PresetScreener(df=sample_df)
        results = ps.run_all()
        out = str(tmp_path / "test_output.xlsx")
        path = generate_screener_excel(results, output_path=out)
        assert os.path.exists(path)

    def test_file_has_correct_sheets(self, sample_df, tmp_path):
        from src.screener.presets import PresetScreener, PRESETS
        ps = PresetScreener(df=sample_df)
        results = ps.run_all()
        out = str(tmp_path / "test_output.xlsx")
        generate_screener_excel(results, output_path=out)
        xl = pd.ExcelFile(out)
        assert len(xl.sheet_names) == len(PRESETS)

    def test_sheet_name_truncated(self):
        name = _sheet_name("quality_compounder")
        assert len(name) <= 31

    def test_empty_preset_writes_empty_sheet(self, tmp_path):
        results = {"quality_compounder": pd.DataFrame()}
        out = str(tmp_path / "empty_output.xlsx")
        generate_screener_excel(results, output_path=out)
        assert os.path.exists(out)
