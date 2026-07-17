"""
generate_capital_allocation.py
===============================
Sprint 2 — Generate output/capital_allocation.csv

Run from project root:
    python generate_capital_allocation.py
    python generate_capital_allocation.py --db data/nifty100.db
"""

import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, ".")

from src.analytics.cashflow_kpis import capital_allocation_pattern


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT company_id, year,
                  operating_activity,
                  investing_activity,
                  financing_activity
           FROM cashflow
           ORDER BY company_id, year"""
    ).fetchall()

    os.makedirs("output", exist_ok=True)
    out_path = "output/capital_allocation.csv"

    fieldnames = ["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "pattern_label"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in rows:
            cfo = r["operating_activity"]
            cfi = r["investing_activity"]
            cff = r["financing_activity"]

            writer.writerow({
                "company_id":   r["company_id"],
                "year":         r["year"],
                "cfo_sign":     "+" if (cfo or 0) > 0 else "-",
                "cfi_sign":     "+" if (cfi or 0) > 0 else "-",
                "cff_sign":     "+" if (cff or 0) > 0 else "-",
                "pattern_label": capital_allocation_pattern(cfo, cfi, cff),
            })

    conn.close()

    print(f"Done — {len(rows)} rows written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/nifty100.db")
    args = parser.parse_args()
    run(args.db)
