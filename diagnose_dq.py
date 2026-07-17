"""
Quick diagnostic — run this from your project root (with venv active) to
see exactly what's triggering DQ-02, DQ-03, and DQ-07 in your real data.

    python diagnose_dq.py
"""

import pandas as pd

df = pd.read_csv("validation_failures.csv")

print("=" * 70)
print("DQ-03 — Orphan rows, broken down by which table they came from")
print("=" * 70)
dq03 = df[df["rule_id"] == "DQ-03"].copy()
# table name is embedded in the issue text, e.g. "Orphan row in cashflow: ..."
dq03["table"] = dq03["issue"].str.extract(r"Orphan row in (\w+):")
print(dq03["table"].value_counts().to_string())
print()
print("Top 15 distinct company_id values causing DQ-03 orphans:")
print(dq03["company_id"].value_counts().head(15).to_string())
print()
print("Sample 10 DQ-03 rows:")
print(dq03[["company_id", "year", "issue"]].head(10).to_string(index=False))

print()
print("=" * 70)
print("DQ-02 — Duplicate (company_id, year) pairs, sample 10")
print("=" * 70)
dq02 = df[df["rule_id"] == "DQ-02"]
print(dq02[["company_id", "year", "issue"]].head(10).to_string(index=False))
print()
print("Which companies have the most DQ-02 duplicates:")
print(dq02["company_id"].value_counts().head(10).to_string())

print()
print("=" * 70)
print("DQ-07 — Unparseable year values, ALL distinct raw values seen")
print("=" * 70)
dq07 = df[df["rule_id"] == "DQ-07"]
# the raw unparseable value was stored in the 'year' column of the violation
print(dq07["year"].value_counts().to_string())
print()
print("Sample 10 DQ-07 rows:")
print(dq07[["company_id", "year", "issue"]].head(10).to_string(index=False))
