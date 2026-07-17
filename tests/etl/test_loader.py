"""
tests/etl/test_loader.py

Unit tests for src/etl/loader.py (Module 1, Feature 1.1 — Excel file loader
with header=1 support). Uses a synthetic fixture file built with openpyxl so
these tests run without requiring the real Nifty 100 source data.
"""

import openpyxl
import pytest

from src.etl.loader import LoaderError, load_all_core_files, load_core_excel


@pytest.fixture
def core_fixture_file(tmp_path):
    """
    Mimic the real core file shape: row 0 = metadata title, row 1 = real
    headers, then data rows (Section 5 load note).
    """
    path = tmp_path / "companies.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Companies"
    ws.append(["Nifty 100 Companies — Export Metadata (row 0, should be skipped)"])
    ws.append(["id", "company_name", "roe_percentage"])
    ws.append(["TCS", "Tata Consultancy Services Ltd", 0.52])
    ws.append(["INFY", "Infosys Ltd", 28.3])
    wb.save(path)
    return path


def test_load_core_excel_skips_metadata_row(core_fixture_file):
    df = load_core_excel(core_fixture_file, sheet_name="Companies")
    assert list(df.columns) == ["id", "company_name", "roe_percentage"]
    assert len(df) == 2
    assert df.iloc[0]["id"] == "TCS"


def test_load_core_excel_strips_whitespace_from_headers(tmp_path):
    path = tmp_path / "messy.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["metadata row"])
    ws.append([" id ", " company_name "])
    ws.append(["TCS", "Tata Consultancy Services Ltd"])
    wb.save(path)

    df = load_core_excel(path)
    assert list(df.columns) == ["id", "company_name"]


def test_load_core_excel_missing_file_raises_loader_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.xlsx"
    with pytest.raises(LoaderError):
        load_core_excel(missing_path)


def test_load_all_core_files_skips_missing_files_gracefully(tmp_path):
    """
    With an empty raw/ directory, load_all_core_files() should not raise —
    it should log and skip, returning an empty dict (Section 9, Feature 1.1
    is about correct parsing; graceful degradation is handled by the
    Day 1-5 pipeline wiring, not a hard crash).
    """
    result = load_all_core_files(raw_dir=tmp_path)
    assert result == {}


def test_load_all_core_files_loads_present_files(tmp_path, core_fixture_file):
    # core_fixture_file was written to its own tmp_path; copy logic isn't
    # needed here since we just point load_all_core_files at that same dir.
    raw_dir = core_fixture_file.parent
    result = load_all_core_files(raw_dir=raw_dir)
    assert "companies" in result
    assert len(result["companies"]) == 2
