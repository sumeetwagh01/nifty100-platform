"""
tests/db/test_schema.py

Tests for db/schema.sql and db/loader.py (Module 1, Feature 1.6, Sprint 1
Day 4). Every test uses a fresh in-memory-style temp database (tmp_path)
so these never touch the real data/nifty100.db.
"""

import sqlite3

import pandas as pd
import pytest

from db.loader import (
    TABLE_ORDER,
    create_database,
    foreign_key_check,
    insert_balancesheet,
    insert_companies,
    insert_dataframe,
    insert_documents,
    insert_market_cap,
    insert_profitandloss,
    insert_sectors,
    insert_stock_prices,
    list_tables,
)


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test_nifty100.db"
    conn = create_database(db_path=db_path)
    yield conn
    conn.close()


@pytest.fixture
def companies_df():
    return pd.DataFrame(
        {
            "id": ["TCS", "INFY"],
            "company_name": ["Tata Consultancy Services Ltd", "Infosys Ltd"],
            "face_value": [1, 5],
            "book_value": [157.40, 220.10],
            "roce_percentage": [64.3, 35.2],
            "roe_percentage": [0.52, 28.3],
        }
    )


# ---------------------------------------------------------------------------
# Schema structure
# ---------------------------------------------------------------------------
def test_create_database_creates_exactly_10_tables(db_conn):
    tables = list_tables(db_conn)
    assert len(tables) == 10
    assert set(tables) == set(TABLE_ORDER)


def test_schema_excludes_financial_ratios_and_peer_groups(db_conn):
    """
    These two get built by later sprint modules (Ratio Engine, Peer
    Comparison Engine), not by the Day 4 raw-load schema (Section 19).
    """
    tables = list_tables(db_conn)
    assert "financial_ratios" not in tables
    assert "peer_groups" not in tables


def test_foreign_keys_pragma_is_on(db_conn):
    result = db_conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert result == 1


def test_create_database_is_idempotent(tmp_path):
    """Running create_database() twice on the same file must not error
    (every CREATE TABLE/INDEX uses IF NOT EXISTS)."""
    db_path = tmp_path / "idempotent.db"
    conn1 = create_database(db_path=db_path)
    conn1.close()
    conn2 = create_database(db_path=db_path)  # should not raise
    assert len(list_tables(conn2)) == 10
    conn2.close()


def test_fresh_database_has_zero_fk_violations(db_conn):
    assert foreign_key_check(db_conn) == []


# ---------------------------------------------------------------------------
# Insertion — happy path
# ---------------------------------------------------------------------------
def test_insert_companies_succeeds(db_conn, companies_df):
    inserted = insert_companies(db_conn, companies_df)
    assert inserted == 2
    count = db_conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert count == 2


def test_insert_profitandloss_with_valid_fk_succeeds(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "id": [61],
            "sales": [225458],
            "expenses": [176924],
            "operating_profit": [48534],
            "opm_percentage": [21.5],
            "net_profit": [34990],
            "eps": [95.3],
        }
    )
    inserted = insert_profitandloss(db_conn, pl)
    assert inserted == 1
    row = db_conn.execute(
        "SELECT company_id, year, sales, source_row_id FROM profitandloss"
    ).fetchone()
    assert row == ("TCS", "2023-03", 225458, 61)


def test_insert_dataframe_handles_nan_as_null(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "sales": [225458],
            "expenses": [176924],
            "operating_profit": [48534],
            "opm_percentage": [21.5],
            "other_income": [float("nan")],
        }
    )
    insert_profitandloss(db_conn, pl)
    other_income = db_conn.execute("SELECT other_income FROM profitandloss").fetchone()[
        0
    ]
    assert other_income is None  # not the string 'nan'


def test_insert_empty_dataframe_returns_zero(db_conn):
    empty = pd.DataFrame(columns=["id", "company_name", "face_value"])
    assert insert_companies(db_conn, empty) == 0


# ---------------------------------------------------------------------------
# Constraint enforcement — this is the actual point of Day 4
# ---------------------------------------------------------------------------
def test_fk_violation_is_rejected(db_conn, companies_df):
    """A profitandloss row referencing a company_id NOT in companies must
    raise IntegrityError — this is what makes DQ-03 enforceable at the DB
    layer, not just at validation time."""
    insert_companies(db_conn, companies_df)
    orphan_pl = pd.DataFrame(
        {
            "company_id": ["GHOST"],
            "year": ["2023-03"],
            "sales": [100],
            "expenses": [50],
            "operating_profit": [50],
            "opm_percentage": [50.0],
        }
    )
    with pytest.raises(sqlite3.IntegrityError):
        insert_profitandloss(db_conn, orphan_pl)


def test_duplicate_company_pk_is_rejected(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    with pytest.raises(sqlite3.IntegrityError):
        insert_companies(db_conn, companies_df)  # same ids again


def test_duplicate_company_year_pk_is_rejected(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "sales": [225458],
            "expenses": [176924],
            "operating_profit": [48534],
            "opm_percentage": [21.5],
        }
    )
    insert_profitandloss(db_conn, pl)
    with pytest.raises(sqlite3.IntegrityError):
        insert_profitandloss(db_conn, pl)  # same (company_id, year) again


def test_required_not_null_column_is_enforced(db_conn):
    """companies.company_name is NOT NULL — a row missing it must be rejected."""
    bad = pd.DataFrame({"id": ["TCS"], "face_value": [1]})
    with pytest.raises(sqlite3.IntegrityError):
        insert_companies(db_conn, bad)


# ---------------------------------------------------------------------------
# Column renaming — source 'Year'/'Annual_Report' -> 'year'/'annual_report_url'
# ---------------------------------------------------------------------------
def test_insert_documents_renames_source_columns(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    documents = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "Year": [2024],
            "id": [1],
            "Annual_Report": ["https://bseindia.com/tcs_2024.pdf"],
        }
    )
    insert_documents(db_conn, documents)
    row = db_conn.execute(
        "SELECT company_id, year, annual_report_url FROM documents"
    ).fetchone()
    assert row == ("TCS", 2024, "https://bseindia.com/tcs_2024.pdf")


# ---------------------------------------------------------------------------
# Other table wrappers — quick smoke tests
# ---------------------------------------------------------------------------
def test_insert_balancesheet_succeeds(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    bs = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2024-03"],
            "equity_capital": [366],
            "total_liabilities": [78809],
            "total_assets": [78809],
        }
    )
    assert insert_balancesheet(db_conn, bs) == 1


def test_insert_sectors_succeeds(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    sectors = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "broad_sector": ["Information Technology"],
            "sub_sector": ["IT Services"],
            "index_weight_pct": [4.5],
        }
    )
    assert insert_sectors(db_conn, sectors) == 1


def test_insert_stock_prices_succeeds(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    prices = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "date": ["2024-01-01"],
            "close_price": [3500.0],
            "volume": [1_000_000],
        }
    )
    assert insert_stock_prices(db_conn, prices) == 1


def test_insert_market_cap_succeeds(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    mcap = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": [2024],
            "market_cap_crore": [1400000],
            "pe_ratio": [28.5],
        }
    )
    assert insert_market_cap(db_conn, mcap) == 1


def test_insert_dataframe_rejects_unknown_table(db_conn, companies_df):
    insert_companies(db_conn, companies_df)
    with pytest.raises(ValueError):
        insert_dataframe(db_conn, "not_a_real_table", companies_df)


def test_insert_dataframe_rejects_dataframe_with_no_matching_columns(db_conn):
    junk = pd.DataFrame({"totally_unrelated_column": [1, 2, 3]})
    with pytest.raises(ValueError):
        insert_dataframe(db_conn, "companies", junk)
