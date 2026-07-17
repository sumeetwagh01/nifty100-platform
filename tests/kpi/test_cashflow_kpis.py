"""
tests/kpi/test_cashflow_kpis.py
================================
Unit tests for src/analytics/cashflow_kpis.py

Coverage:
  - fcf()                        : happy path, negative FCF, None inputs
  - cfo_quality_score()          : all 3 labels, None PAT, empty series
  - capex_intensity()            : all 3 labels, zero sales, None inputs
  - fcf_conversion()             : happy path, zero op profit, None inputs
  - capital_allocation_pattern() : all 8 patterns, None input → Unknown
  - generate_capital_allocation_csv() : writes correct rows, returns count
"""

import os
import csv
import pytest
import tempfile

from src.analytics.cashflow_kpis import (
    fcf,
    cfo_quality_score,
    capex_intensity,
    fcf_conversion,
    capital_allocation_pattern,
    generate_capital_allocation_csv,
)


# ---------------------------------------------------------------------------
# FCF
# ---------------------------------------------------------------------------

class TestFCF:
    def test_happy_path(self):
        assert fcf(500, -200) == 300.0

    def test_negative_fcf(self):
        assert fcf(-100, -50) == -150.0

    def test_none_investing_treated_as_zero(self):
        assert fcf(500, None) == 500.0

    def test_none_operating_returns_none(self):
        assert fcf(None, -200) is None

    def test_both_positive(self):
        assert fcf(500, 200) == 700.0

    def test_zero_operating(self):
        assert fcf(0, -200) == -200.0

    def test_large_values(self):
        # Crore-scale
        assert fcf(50000, -30000) == 20000.0


# ---------------------------------------------------------------------------
# CFO Quality Score
# ---------------------------------------------------------------------------

class TestCFOQualityScore:
    def test_high_quality(self):
        # avg ratio = 1.2 > 1.0
        cfo = [120, 130, 140, 150, 160]
        pat = [100, 110, 120, 130, 140]
        assert cfo_quality_score(cfo, pat) == "High Quality"

    def test_moderate(self):
        # avg ratio ≈ 0.636 → Moderate
        cfo = [60, 70, 80]
        pat = [100, 110, 120]
        assert cfo_quality_score(cfo, pat) == "Moderate"

    def test_accrual_risk(self):
        # avg ratio ≈ 0.42 < 0.5
        cfo = [40, 50, 60]
        pat = [100, 110, 120]
        assert cfo_quality_score(cfo, pat) == "Accrual Risk"

    def test_exact_boundary_high(self):
        # avg ratio = 1.0 exactly → Moderate (not > 1.0)
        cfo = [100]
        pat = [100]
        assert cfo_quality_score(cfo, pat) == "Moderate"

    def test_exact_boundary_moderate_low(self):
        # avg ratio = 0.5 exactly → Moderate (>= 0.5)
        cfo = [50]
        pat = [100]
        assert cfo_quality_score(cfo, pat) == "Moderate"

    def test_zero_pat_skipped(self):
        # PAT=0 year skipped — only valid year counted
        cfo = [100, 120]
        pat = [0, 100]
        assert cfo_quality_score(cfo, pat) == "High Quality"

    def test_all_zero_pat_returns_none(self):
        assert cfo_quality_score([100], [0]) is None

    def test_none_pat_skipped(self):
        cfo = [None, 120]
        pat = [100, 100]
        assert cfo_quality_score(cfo, pat) == "High Quality"

    def test_empty_series_returns_none(self):
        assert cfo_quality_score([], []) is None

    def test_uses_last_5_years_only(self):
        # 7 values — only last 5 pairs used
        cfo = [10, 10, 120, 130, 140, 150, 160]
        pat = [100, 100, 100, 110, 120, 130, 140]
        # Last 5: cfo=[120,130,140,150,160], pat=[100,110,120,130,140] → High Quality
        assert cfo_quality_score(cfo, pat) == "High Quality"


# ---------------------------------------------------------------------------
# CapEx Intensity
# ---------------------------------------------------------------------------

class TestCapExIntensity:
    def test_asset_light(self):
        value, label = capex_intensity(-100, 5000)
        assert value == 2.0
        assert label == "Asset Light"

    def test_moderate(self):
        value, label = capex_intensity(-200, 5000)
        assert value == 4.0
        assert label == "Moderate"

    def test_capital_intensive(self):
        value, label = capex_intensity(-500, 5000)
        assert value == 10.0
        assert label == "Capital Intensive"

    def test_exact_boundary_3pct(self):
        # exactly 3% → Asset Light (< 3 is False so → Moderate)
        value, label = capex_intensity(-150, 5000)
        assert value == 3.0
        assert label == "Moderate"

    def test_exact_boundary_8pct(self):
        # exactly 8% → Moderate (<= 8)
        value, label = capex_intensity(-400, 5000)
        assert value == 8.0
        assert label == "Moderate"

    def test_positive_investing_abs_applied(self):
        # Positive CFI (asset sales) — abs() still works
        value, label = capex_intensity(100, 5000)
        assert value == 2.0
        assert label == "Asset Light"

    def test_none_investing_returns_none(self):
        assert capex_intensity(None, 5000) == (None, None)

    def test_zero_sales_returns_none(self):
        assert capex_intensity(-200, 0) == (None, None)

    def test_none_sales_returns_none(self):
        assert capex_intensity(-200, None) == (None, None)


# ---------------------------------------------------------------------------
# FCF Conversion
# ---------------------------------------------------------------------------

class TestFCFConversion:
    def test_happy_path(self):
        assert round(fcf_conversion(300, 500), 4) == 60.0

    def test_negative_fcf(self):
        assert round(fcf_conversion(-100, 500), 4) == -20.0

    def test_zero_operating_profit(self):
        assert fcf_conversion(300, 0) is None

    def test_none_fcf(self):
        assert fcf_conversion(None, 500) is None

    def test_none_operating_profit(self):
        assert fcf_conversion(300, None) is None

    def test_over_100pct(self):
        # FCF > operating profit is valid (e.g. working capital release)
        assert round(fcf_conversion(600, 500), 4) == 120.0

    def test_zero_fcf(self):
        assert fcf_conversion(0, 500) == 0.0


# ---------------------------------------------------------------------------
# Capital Allocation Pattern
# ---------------------------------------------------------------------------

class TestCapitalAllocationPattern:
    def test_reinvestor(self):
        assert capital_allocation_pattern(500, -200, -100) == "Reinvestor"

    def test_mixed(self):
        assert capital_allocation_pattern(500, -200, 100) == "Mixed"

    def test_liquidating_assets(self):
        assert capital_allocation_pattern(500, 200, -100) == "Liquidating Assets"

    def test_cash_accumulator(self):
        assert capital_allocation_pattern(500, 200, 100) == "Cash Accumulator"

    def test_distress_signal(self):
        assert capital_allocation_pattern(-300, 200, 400) == "Distress Signal"

    def test_growth_funded_by_debt(self):
        assert capital_allocation_pattern(-300, -200, 400) == "Growth Funded by Debt"

    def test_pre_revenue(self):
        assert capital_allocation_pattern(-300, -200, -100) == "Pre-Revenue"

    def test_shareholder_returns(self):
        assert capital_allocation_pattern(-300, 200, -100) == "Shareholder Returns"

    def test_none_cfo_unknown(self):
        assert capital_allocation_pattern(None, -200, -100) == "Unknown"

    def test_none_cfi_unknown(self):
        assert capital_allocation_pattern(500, None, -100) == "Unknown"

    def test_none_cff_unknown(self):
        assert capital_allocation_pattern(500, -200, None) == "Unknown"

    def test_zero_cfo_is_negative(self):
        # Zero CFO treated as '-'
        assert capital_allocation_pattern(0, -200, -100) == "Pre-Revenue"

    def test_zero_cfi_is_negative(self):
        # Zero CFI treated as '-', so (+,-,-) = Reinvestor
        assert capital_allocation_pattern(500, 0, -100) == "Reinvestor"


# ---------------------------------------------------------------------------
# generate_capital_allocation_csv
# ---------------------------------------------------------------------------

class TestGenerateCapitalAllocationCSV:
    def _sample_rows(self):
        return [
            {"company_id": 1, "year": 2023, "cfo_sign": "+", "cfi_sign": "-", "cff_sign": "-", "pattern_label": "Reinvestor"},
            {"company_id": 2, "year": 2023, "cfo_sign": "-", "cfi_sign": "-", "cff_sign": "+", "pattern_label": "Growth Funded by Debt"},
            {"company_id": 1, "year": 2022, "cfo_sign": "+", "cfi_sign": "-", "cff_sign": "+", "pattern_label": "Mixed"},
        ]

    def test_returns_row_count(self):
        rows = self._sample_rows()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "output", "capital_allocation.csv")
            count = generate_capital_allocation_csv(rows, output_path=path)
            assert count == 3

    def test_csv_has_correct_headers(self):
        rows = self._sample_rows()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "output", "capital_allocation.csv")
            generate_capital_allocation_csv(rows, output_path=path)
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                assert set(reader.fieldnames) == {
                    "company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"
                }

    def test_csv_content_correct(self):
        rows = self._sample_rows()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "output", "capital_allocation.csv")
            generate_capital_allocation_csv(rows, output_path=path)
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                written = list(reader)
            assert written[0]["pattern_label"] == "Reinvestor"
            assert written[1]["pattern_label"] == "Growth Funded by Debt"
            assert written[2]["pattern_label"] == "Mixed"

    def test_empty_rows_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "output", "capital_allocation.csv")
            count = generate_capital_allocation_csv([], output_path=path)
            assert count == 0

    def test_creates_output_directory(self):
        rows = self._sample_rows()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nested", "dir", "capital_allocation.csv")
            generate_capital_allocation_csv(rows, output_path=path)
            assert os.path.exists(path)
