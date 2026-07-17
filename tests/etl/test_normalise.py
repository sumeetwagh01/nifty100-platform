"""
tests/etl/test_normalise.py

Unit tests for src/etl/normaliser.py (Module 12, Test Category 12.1 — ETL
Tests: "year_normaliser (20 cases), ticker_normaliser (15 cases)").

This file delivers 24 year-normaliser cases + 17 ticker-normaliser cases =
41 total, exceeding the 35-case minimum from the sprint plan (Day 2).
"""


import pytest

from src.etl.normaliser import PARSE_ERROR, normalize_ticker, normalize_year


# ---------------------------------------------------------------------------
# normalize_year() — 24 cases
# ---------------------------------------------------------------------------

YEAR_CASES = [
    # (raw input, expected output, case description)
    ("Mar-23", "2023-03", "standard format — most common"),
    ("Mar 23", "2023-03", "space separator instead of hyphen"),
    ("March-2023", "2023-03", "full month name + 4-digit year"),
    ("2023", "2023-03", "bare 4-digit year -> assume March FY close"),
    ("FY23", "2023-03", "FY-prefixed 2-digit shorthand"),
    ("Dec-22", "2022-12", "December year-end company (e.g. NESTLEIND)"),
    ("Jun-23", "2023-06", "June year-end (some banks)"),
    ("2023-03", "2023-03", "already normalised — pass through"),
    ("mar-23", "2023-03", "lowercase month abbreviation"),
    ("MAR-23", "2023-03", "uppercase month abbreviation"),
    (" Mar-23 ", "2023-03", "leading/trailing whitespace padding"),
    ("Sept-23", "2023-09", "4-letter Sept abbreviation"),
    ("September-2024", "2024-09", "full month name, latest dataset year"),
    ("FY 23", "2023-03", "FY prefix with space before digits"),
    ("FY2023", "2023-03", "FY prefix with 4-digit year"),
    ("2023.0", "2023-03", "float-cast year artefact from Excel"),
    ("Jan-10", "2010-01", "earliest dataset boundary year (FY2010)"),
    ("Dec-24", "2024-12", "latest dataset boundary year (FY2024)"),
    ("Mar-2023", "2023-03", "short month name + 4-digit year"),
    ("June-23", "2023-06", "full month name + 2-digit year"),
    ("garbage", PARSE_ERROR, "unparseable text"),
    ("", PARSE_ERROR, "empty string"),
    (None, PARSE_ERROR, "None input"),
    (float("nan"), PARSE_ERROR, "NaN input (pandas missing-value artefact)"),
]


@pytest.mark.parametrize("raw,expected,description", YEAR_CASES)
def test_normalize_year(raw, expected, description):
    result = normalize_year(raw)
    assert (
        result == expected
    ), f"normalize_year({raw!r}) -> {result!r}, expected {expected!r} ({description})"


def test_normalize_year_output_format_is_always_valid_or_parse_error():
    """Every successful parse must match the DQ-07 'YYYY-MM' format."""
    import re

    valid_format = re.compile(r"^\d{4}-\d{2}$")
    for raw, expected, _ in YEAR_CASES:
        result = normalize_year(raw)
        assert result == PARSE_ERROR or valid_format.match(result)


# ---------------------------------------------------------------------------
# normalize_ticker() — 17 cases
# ---------------------------------------------------------------------------

TICKER_CASES = [
    # (raw input, expected output, case description)
    ("TCS", "TCS", "already clean"),
    ("tcs", "TCS", "lowercase -> upper-cased"),
    (" TCS ", "TCS", "whitespace stripped, both sides"),
    (" tcs ", "TCS", "whitespace stripped + lowercase"),
    ("BAJAJ-AUTO", "BAJAJ-AUTO", "hyphen preserved — valid NSE ticker"),
    ("bajaj-auto", "BAJAJ-AUTO", "hyphen preserved + lowercase"),
    ("M&M", "M&M", "ampersand preserved — valid NSE ticker"),
    ("m&m", "M&M", "ampersand preserved + lowercase"),
    ("AB", "AB", "2-char boundary — minimum valid length (DQ-08)"),
    ("ABCDEFGHIJKL", "ABCDEFGHIJKL", "12-char boundary — maximum valid length (DQ-08)"),
    (123, "123", "non-string numeric input coerced to text"),
    ("HDFCBANK", "HDFCBANK", "typical 8-char ticker"),
    ("  TaTaMotors  ", "TATAMOTORS", "mixed case with heavy whitespace"),
    ("T", None, "1-char — below DQ-08 minimum, reject"),
    ("A" * 13, None, "13-char — above DQ-08 maximum, reject"),
    (None, None, "None input — no FK match possible, reject"),
    ("   ", None, "whitespace-only — empty after strip, reject"),
]


@pytest.mark.parametrize("raw,expected,description", TICKER_CASES)
def test_normalize_ticker(raw, expected, description):
    result = normalize_ticker(raw)
    assert (
        result == expected
    ), f"normalize_ticker({raw!r}) -> {result!r}, expected {expected!r} ({description})"


def test_normalize_ticker_nan_is_rejected():
    """A pandas NaN cell (common for sparse FK columns) must be rejected."""
    assert normalize_ticker(float("nan")) is None


def test_normalize_ticker_never_returns_unstripped_or_lowercase():
    """Every non-None result must already be upper-cased with no padding."""
    for raw, expected, _ in TICKER_CASES:
        result = normalize_ticker(raw)
        if result is not None:
            assert result == result.strip().upper()
