"""
db/loader.py

SQLite schema builder and DataFrame-insertion layer (Module 1, Feature 1.6,
Sprint 1 Day 4). This is deliberately scoped to two responsibilities:

    1. create_database()  — execute db/schema.sql against a fresh .db file,
       with PRAGMA foreign_keys = ON.
    2. insert_<table>()    — take a normalised DataFrame (already passed
       through Day 2's normalize_year()/normalize_ticker() and Day 3's
       validator) and insert it into the matching SQLite table using
       parameterised queries (Section 22: "Parameterised queries only —
       no f-string SQL").

Orchestrating the full 12-file load with row-count auditing into
load_audit.csv is Day 5's job (src/etl/full_load.py); this module only
needs to prove the schema is correct and that insertion works, table by
table, which is exactly what tests/db/test_schema.py checks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"

# The 10 tables that make up nifty100.db, in dependency order (companies
# first, since every other table has a FOREIGN KEY back to it).
TABLE_ORDER = (
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "sectors",
    "stock_prices",
    "market_cap",
)

# Maps each table to the exact column order in schema.sql, and to the
# source DataFrame column name when it differs (e.g. the source 'id'
# column becomes 'source_row_id' to avoid colliding with the surrogate/
# composite primary keys; 'Year'/'Annual_Report' get lower-cased).
_COLUMN_MAP: dict[str, dict[str, str]] = {
    "companies": {
        "id": "id",
        "company_name": "company_name",
        "company_logo": "company_logo",
        "chart_link": "chart_link",
        "about_company": "about_company",
        "website": "website",
        "nse_profile": "nse_profile",
        "bse_profile": "bse_profile",
        "face_value": "face_value",
        "book_value": "book_value",
        "roce_percentage": "roce_percentage",
        "roe_percentage": "roe_percentage",
    },
    "profitandloss": {
        "company_id": "company_id",
        "year": "year",
        "id": "source_row_id",
        "sales": "sales",
        "expenses": "expenses",
        "operating_profit": "operating_profit",
        "opm_percentage": "opm_percentage",
        "other_income": "other_income",
        "interest": "interest",
        "depreciation": "depreciation",
        "profit_before_tax": "profit_before_tax",
        "tax_percentage": "tax_percentage",
        "net_profit": "net_profit",
        "eps": "eps",
        "dividend_payout": "dividend_payout",
    },
    "balancesheet": {
        "company_id": "company_id",
        "year": "year",
        "id": "source_row_id",
        "equity_capital": "equity_capital",
        "reserves": "reserves",
        "borrowings": "borrowings",
        "other_liabilities": "other_liabilities",
        "total_liabilities": "total_liabilities",
        "fixed_assets": "fixed_assets",
        "cwip": "cwip",
        "investments": "investments",
        "other_asset": "other_asset",
        "total_assets": "total_assets",
    },
    "cashflow": {
        "company_id": "company_id",
        "year": "year",
        "id": "source_row_id",
        "operating_activity": "operating_activity",
        "investing_activity": "investing_activity",
        "financing_activity": "financing_activity",
        "net_cash_flow": "net_cash_flow",
    },
    "analysis": {
        "company_id": "company_id",
        "id": "source_row_id",
        "compounded_sales_growth": "compounded_sales_growth",
        "compounded_profit_growth": "compounded_profit_growth",
        "stock_price_cagr": "stock_price_cagr",
        "roe": "roe",
    },
    "documents": {
        "company_id": "company_id",
        "Year": "year",
        "id": "source_row_id",
        "Annual_Report": "annual_report_url",
    },
    "prosandcons": {
        "company_id": "company_id",
        "pros": "pros",
        "cons": "cons",
    },
    "sectors": {
        "company_id": "company_id",
        "broad_sector": "broad_sector",
        "sub_sector": "sub_sector",
        "index_weight_pct": "index_weight_pct",
        "market_cap_category": "market_cap_category",
    },
    "stock_prices": {
        "company_id": "company_id",
        "date": "date",
        "open_price": "open_price",
        "high_price": "high_price",
        "low_price": "low_price",
        "close_price": "close_price",
        "volume": "volume",
        "adjusted_close": "adjusted_close",
    },
    "market_cap": {
        "company_id": "company_id",
        "year": "year",
        "market_cap_crore": "market_cap_crore",
        "enterprise_value_crore": "enterprise_value_crore",
        "pe_ratio": "pe_ratio",
        "pb_ratio": "pb_ratio",
        "ev_ebitda": "ev_ebitda",
        "dividend_yield_pct": "dividend_yield_pct",
    },
}


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a connection with foreign key enforcement turned on."""
    db_path = db_path or DEFAULT_DB_PATH
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database(
    db_path: Optional[Path] = None, schema_path: Optional[Path] = None
) -> sqlite3.Connection:
    """
    Execute db/schema.sql against db_path (default data/nifty100.db),
    creating all 10 tables. Safe to call repeatedly — every CREATE TABLE
    and CREATE INDEX statement in schema.sql uses IF NOT EXISTS.
    """
    schema_path = schema_path or SCHEMA_PATH
    conn = get_connection(db_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def list_tables(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def _prepare_rows(df: pd.DataFrame, table: str) -> tuple[list[str], list[tuple]]:
    """
    Select + rename the subset of df's columns that this table needs (per
    _COLUMN_MAP), in schema column order, and convert to a list of tuples
    ready for an executemany() insert. NaN is converted to None so SQLite
    stores a real NULL rather than the literal string 'nan'.
    """
    mapping = _COLUMN_MAP[table]
    available_source_cols = [c for c in mapping if c in df.columns]
    if not available_source_cols:
        raise ValueError(
            f"None of the expected source columns {list(mapping)} were "
            f"found in the DataFrame for table '{table}'."
        )

    sql_columns = [mapping[c] for c in available_source_cols]
    subset = df[available_source_cols].where(pd.notna(df[available_source_cols]), None)
    rows = [tuple(row) for row in subset.itertuples(index=False, name=None)]
    return sql_columns, rows


def insert_dataframe(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    """
    Insert a normalised DataFrame into the given table using a
    parameterised executemany() — no f-string SQL, no string-formatted
    values (Section 22 coding standard). Returns the number of rows
    inserted. Raises sqlite3.IntegrityError if a PK/FK constraint is
    violated (e.g. a duplicate (company_id, year), or a company_id that
    doesn't exist in companies — exactly the cases DQ-01/02/03 exist to
    catch upstream).
    """
    if table not in _COLUMN_MAP:
        raise ValueError(f"Unknown table '{table}'. Expected one of {TABLE_ORDER}.")
    if df.empty:
        return 0

    columns, rows = _prepare_rows(df, table)
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"  # noqa: S608

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# Thin, explicitly-named wrappers — one per table — so calling code (and
# Day 5's full-load orchestrator) reads as a clear table-by-table sequence
# rather than a generic insert_dataframe(conn, "profitandloss", df) call
# everywhere. Each just delegates to insert_dataframe().
def insert_companies(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "companies", df)


def insert_profitandloss(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "profitandloss", df)


def insert_balancesheet(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "balancesheet", df)


def insert_cashflow(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "cashflow", df)


def insert_analysis(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "analysis", df)


def insert_documents(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "documents", df)


def insert_prosandcons(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "prosandcons", df)


def insert_sectors(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "sectors", df)


def insert_stock_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "stock_prices", df)


def insert_market_cap(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    return insert_dataframe(conn, "market_cap", df)


def foreign_key_check(conn: sqlite3.Connection) -> list[tuple]:
    """Wraps PRAGMA foreign_key_check — returns [] when the DB is clean (AC-03)."""
    return conn.execute("PRAGMA foreign_key_check").fetchall()


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    conn = create_database()
    tables = list_tables(conn)
    print(f"Schema built at {DEFAULT_DB_PATH}")
    print(f"Tables created ({len(tables)}): {tables}")

    fk_violations = foreign_key_check(conn)
    print(
        f"PRAGMA foreign_key_check: {len(fk_violations)} violation(s) "
        "(expected 0 on a freshly-created, empty database)."
    )
    print(
        "\nSchema-only build complete. Run Day 5's full-load script to "
        "populate these tables from data/raw/ and data/supporting/."
    )
    conn.close()
