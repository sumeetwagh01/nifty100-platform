"""
src/etl/normaliser.py

Field-level normalisation functions used by every loader in the ETL pipeline
(Module 1 — Data Engineering & ETL Pipeline, Sprint 1, Day 2).

Two functions are exposed:

    normalize_year(raw)    -> 'YYYY-MM' string, or the sentinel PARSE_ERROR
    normalize_ticker(raw)  -> uppercase stripped ticker string, or None if the
                               value cannot satisfy DQ-08 (length 2-12 chars)

Both functions are pure (no I/O, no logging) so they can be unit tested in
isolation. The ETL pipeline (Day 3+ schema validator / loader integration) is
responsible for deciding what to do with PARSE_ERROR / None — per DQ-07 and
DQ-08 the row should be rejected and the raw value logged to
parse_failures.csv / validation_failures.csv.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Sentinel returned by normalize_year() when the input cannot be parsed.
# See Section 23, ETL Edge Cases: "year garbage -> PARSE_ERROR".
PARSE_ERROR = "PARSE_ERROR"

# DQ-08: Ticker Format — company_id length must be 2-12 chars after
# strip().upper(). Outside this range the row is rejected.
_TICKER_MIN_LEN = 2
_TICKER_MAX_LEN = 12

# Final-format validator for normalize_year() output — DQ-07.
_YEAR_FORMAT_RE = re.compile(r"^\d{4}-\d{2}$")

# Month name -> month number. Covers full names, standard 3-letter
# abbreviations, and the "Sept" 4-letter variant seen in some exports.
_MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Mon-YY / Mon YY / FullMonth-YYYY / Mon23 etc.
# Group 1 = month text, Group 2 = year digits (2 or 4).
_MONTH_YEAR_RE = re.compile(r"^([A-Za-z]+)[\s\-]*(\d{2,4})$")

# FY23 / FY 23 / FY2023 -> Indian financial year shorthand, ending March.
_FY_RE = re.compile(r"^FY\s*-?\s*(\d{2,4})$", re.IGNORECASE)

# Already-normalised 'YYYY-MM'.
_ALREADY_NORMALISED_RE = re.compile(r"^(\d{4})-(\d{2})$")

# Bare 4-digit year (e.g. '2023', or '2023.0' after Excel float coercion).
_BARE_YEAR_RE = re.compile(r"^(\d{4})(?:\.0)?$")


def _is_missing(value: Any) -> bool:
    """True for None, NaN, or an empty/whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _expand_two_digit_year(yy: str) -> int:
    """
    '23' -> 2023. Dataset coverage is FY 2010-2024 (Section 5), so every
    2-digit year in this project's source files maps to the 2000s.
    """
    return 2000 + int(yy)


def normalize_year(raw: Any) -> str:
    """
    Standardise a financial-year label to 'YYYY-MM' (Section 5: 'Standardise
    to YYYY-MM on load via normalize_year()'). Returns PARSE_ERROR if the
    value cannot be parsed (DQ-07: reject row, log raw value).

    Examples (Section 23 edge case table):
        'Mar-23'      -> '2023-03'
        'Mar 23'      -> '2023-03'
        'March-2023'  -> '2023-03'
        '2023'        -> '2023-03'   (integer year -> assume March FY close)
        'FY23'        -> '2023-03'
        'Dec-22'      -> '2022-12'   (December year-end, e.g. NESTLEIND)
        'Jun-23'      -> '2023-06'   (June year-end, some banks)
        '2023-03'     -> '2023-03'   (already normalised — pass through)
        'garbage'     -> PARSE_ERROR
    """
    if _is_missing(raw):
        return PARSE_ERROR

    text = str(raw).strip()
    if text == "":
        return PARSE_ERROR

    # Case 1: already normalised 'YYYY-MM'.
    m = _ALREADY_NORMALISED_RE.match(text)
    if m:
        year, month = m.group(1), m.group(2)
        if 1 <= int(month) <= 12:
            return f"{year}-{month}"
        return PARSE_ERROR

    # Case 2: bare 4-digit year (or '2023.0' float artefact) -> assume
    # March FY close, the most common convention in this dataset.
    m = _BARE_YEAR_RE.match(text)
    if m:
        return f"{m.group(1)}-03"

    # Case 3: FY-prefixed shorthand, e.g. 'FY23', 'FY 23', 'FY2023'.
    m = _FY_RE.match(text)
    if m:
        digits = m.group(1)
        year = _expand_two_digit_year(digits) if len(digits) == 2 else int(digits)
        return f"{year}-03"

    # Case 4: 'Mon-YY', 'Mon YY', 'FullMonth-YYYY', 'MonYY' (no separator).
    m = _MONTH_YEAR_RE.match(text)
    if m:
        month_text, year_digits = m.group(1).lower(), m.group(2)
        month_num = _MONTH_MAP.get(month_text)
        if month_num is None:
            return PARSE_ERROR
        year = (
            _expand_two_digit_year(year_digits)
            if len(year_digits) == 2
            else int(year_digits)
        )
        return f"{year}-{month_num:02d}"

    # Nothing matched -> unparseable.
    return PARSE_ERROR


def normalize_ticker(raw: Any) -> str | None:
    """
    Standardise an NSE ticker / company_id: strip whitespace, upper-case,
    enforce DQ-08 length bounds (2-12 chars). Returns None if the value is
    missing or fails the length check (row should be rejected upstream).

    Examples (Section 23 edge case table):
        'TCS'        -> 'TCS'
        'tcs'        -> 'TCS'        (upper-cased)
        'BAJAJ-AUTO' -> 'BAJAJ-AUTO' (hyphen preserved — valid NSE ticker)
        'M&M'        -> 'M&M'        (ampersand preserved — valid NSE ticker)
        'MISSING'/None -> None       (no FK match possible / reject)
    """
    if _is_missing(raw):
        return None

    # Coerce non-string inputs (e.g. an Excel cell read back as an int)
    # to text before cleaning, for robustness against mixed-type columns.
    text = str(raw).strip().upper()

    if not (_TICKER_MIN_LEN <= len(text) <= _TICKER_MAX_LEN):
        return None

    return text
