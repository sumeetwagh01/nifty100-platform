"""
tests/dq/test_rules.py

Unit tests for src/etl/validator.py (Module 12, Test Category 12.3 —
"Each of 14 DQ rules triggered on crafted violation records; severity
correct"). This suite covers all 16 rules (a superset of the 14 named in
the spec) with both a violation case and a clean/pass-through case per
rule, giving comfortable margin over the "14/14 rules trigger correctly"
bar.
"""

import pandas as pd

from src.etl.validator import (
    CRITICAL,
    INFO,
    WARNING,
    check_dq01_company_pk_uniqueness,
    check_dq02_annual_pk_uniqueness,
    check_dq03_fk_integrity,
    check_dq04_balance_sheet_balance,
    check_dq05_opm_cross_check,
    check_dq06_positive_sales,
    check_dq07_year_format,
    check_dq08_ticker_format,
    check_dq09_net_cash_check,
    check_dq10_non_negative_fixed_assets,
    check_dq11_tax_rate_range,
    check_dq12_dividend_payout_cap,
    check_dq14_eps_sign_consistency,
    check_dq15_exact_balance_count,
    check_dq16_coverage_check,
    run_all_dq_rules,
)


# ---------------------------------------------------------------------------
# DQ-01 — Company PK Uniqueness
# ---------------------------------------------------------------------------
def test_dq01_duplicate_ticker_triggers_critical():
    companies = pd.DataFrame({"id": ["TCS", "INFY", "TCS"]})
    violations = check_dq01_company_pk_uniqueness(companies)
    assert len(violations) == 2  # both occurrences flagged
    assert all(v.rule_id == "DQ-01" and v.severity == CRITICAL for v in violations)


def test_dq01_unique_tickers_pass_clean():
    companies = pd.DataFrame({"id": ["TCS", "INFY", "HDFCBANK"]})
    assert check_dq01_company_pk_uniqueness(companies) == []


# ---------------------------------------------------------------------------
# DQ-02 — Annual PK Uniqueness
# ---------------------------------------------------------------------------
def test_dq02_duplicate_company_year_triggers_critical():
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "TCS", "INFY"],
            "year": ["2023-03", "2023-03", "2023-03"],
        }
    )
    violations = check_dq02_annual_pk_uniqueness(df, "profitandloss")
    assert len(violations) == 2
    assert all(v.rule_id == "DQ-02" and v.severity == CRITICAL for v in violations)


def test_dq02_unique_company_year_pairs_pass_clean():
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "TCS", "INFY"],
            "year": ["2022-03", "2023-03", "2023-03"],
        }
    )
    assert check_dq02_annual_pk_uniqueness(df, "profitandloss") == []


# ---------------------------------------------------------------------------
# DQ-03 — FK Integrity
# ---------------------------------------------------------------------------
def test_dq03_orphan_company_id_triggers_critical():
    companies = pd.DataFrame({"id": ["TCS", "INFY"]})
    child = pd.DataFrame(
        {"company_id": ["TCS", "GHOST"], "year": ["2023-03", "2023-03"]}
    )
    violations = check_dq03_fk_integrity(child, companies, "profitandloss")
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-03"
    assert violations[0].severity == CRITICAL
    assert violations[0].company_id == "GHOST"


def test_dq03_all_company_ids_present_pass_clean():
    companies = pd.DataFrame({"id": ["TCS", "INFY"]})
    child = pd.DataFrame(
        {"company_id": ["TCS", "INFY"], "year": ["2023-03", "2023-03"]}
    )
    assert check_dq03_fk_integrity(child, companies, "profitandloss") == []


# ---------------------------------------------------------------------------
# DQ-04 — Balance Sheet Balance
# ---------------------------------------------------------------------------
def test_dq04_bs_balance_mismatch_triggers_warning():
    bs = pd.DataFrame(
        {
            "company_id": ["ABB"],
            "year": ["2024-03"],
            "total_assets": [1000],
            "total_liabilities": [1020],
        }
    )
    violations = check_dq04_balance_sheet_balance(bs)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-04"
    assert violations[0].severity == WARNING


def test_dq04_bs_balance_within_tolerance_pass_clean():
    bs = pd.DataFrame(
        {
            "company_id": ["ABB"],
            "year": ["2024-03"],
            "total_assets": [1000],
            "total_liabilities": [1005],
        }
    )
    assert check_dq04_balance_sheet_balance(bs) == []


def test_dq04_zero_total_assets_triggers_warning():
    bs = pd.DataFrame(
        {
            "company_id": ["X"],
            "year": ["2023-03"],
            "total_assets": [0],
            "total_liabilities": [0],
        }
    )
    violations = check_dq04_balance_sheet_balance(bs)
    assert len(violations) == 1
    assert "zero" in violations[0].issue.lower()


# ---------------------------------------------------------------------------
# DQ-05 — OPM Cross-Check
# ---------------------------------------------------------------------------
def test_dq05_opm_mismatch_triggers_warning():
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "sales": [225458],
            "operating_profit": [48534],
            "opm_percentage": [50.0],
        }
    )
    violations = check_dq05_opm_cross_check(pl)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-05" and violations[0].severity == WARNING


def test_dq05_opm_matches_computed_pass_clean():
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "sales": [225458],
            "operating_profit": [48534],
            "opm_percentage": [21.5],
        }
    )
    assert check_dq05_opm_cross_check(pl) == []


# ---------------------------------------------------------------------------
# DQ-06 — Positive Sales
# ---------------------------------------------------------------------------
def test_dq06_zero_sales_triggers_warning():
    pl = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "sales": [0]})
    violations = check_dq06_positive_sales(pl)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-06" and violations[0].severity == WARNING


def test_dq06_positive_sales_pass_clean():
    pl = pd.DataFrame({"company_id": ["TCS"], "year": ["2023-03"], "sales": [225458]})
    assert check_dq06_positive_sales(pl) == []


def test_dq06_excludes_financials_sector_when_sectors_given():
    pl = pd.DataFrame({"company_id": ["HDFCBANK"], "year": ["2023-03"], "sales": [0]})
    sectors = pd.DataFrame({"company_id": ["HDFCBANK"], "broad_sector": ["Financials"]})
    assert check_dq06_positive_sales(pl, sectors=sectors) == []


# ---------------------------------------------------------------------------
# DQ-07 — Year Format
# ---------------------------------------------------------------------------
def test_dq07_unparseable_year_triggers_critical():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["garbage"]})
    violations = check_dq07_year_format(df, "profitandloss")
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-07" and violations[0].severity == CRITICAL


def test_dq07_valid_year_formats_pass_clean():
    df = pd.DataFrame({"company_id": ["TCS", "TCS"], "year": ["Mar-23", "2022-03"]})
    assert check_dq07_year_format(df, "profitandloss") == []


# ---------------------------------------------------------------------------
# DQ-08 — Ticker Format
# ---------------------------------------------------------------------------
def test_dq08_invalid_ticker_length_triggers_critical():
    df = pd.DataFrame({"company_id": ["T"], "year": ["2023-03"]})
    violations = check_dq08_ticker_format(df, "profitandloss")
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-08" and violations[0].severity == CRITICAL


def test_dq08_valid_ticker_pass_clean():
    df = pd.DataFrame({"company_id": ["tcs"], "year": ["2023-03"]})
    assert check_dq08_ticker_format(df, "profitandloss") == []


# ---------------------------------------------------------------------------
# DQ-09 — Net Cash Check
# ---------------------------------------------------------------------------
def test_dq09_net_cash_mismatch_triggers_warning():
    cf = pd.DataFrame(
        {
            "company_id": ["X"],
            "year": ["2023-03"],
            "operating_activity": [100],
            "investing_activity": [-50],
            "financing_activity": [-20],
            "net_cash_flow": [100],
        }
    )
    violations = check_dq09_net_cash_check(cf)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-09" and violations[0].severity == WARNING


def test_dq09_net_cash_within_tolerance_pass_clean():
    cf = pd.DataFrame(
        {
            "company_id": ["X"],
            "year": ["2023-03"],
            "operating_activity": [100],
            "investing_activity": [-50],
            "financing_activity": [-20],
            "net_cash_flow": [30],
        }
    )
    assert check_dq09_net_cash_check(cf) == []


# ---------------------------------------------------------------------------
# DQ-10 — Non-Negative Fixed Assets
# ---------------------------------------------------------------------------
def test_dq10_negative_fixed_assets_triggers_warning():
    bs = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "fixed_assets": [-5]})
    violations = check_dq10_non_negative_fixed_assets(bs)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-10" and violations[0].severity == WARNING


def test_dq10_non_negative_fixed_assets_pass_clean():
    bs = pd.DataFrame({"company_id": ["X"], "year": ["2023-03"], "fixed_assets": [109]})
    assert check_dq10_non_negative_fixed_assets(bs) == []


# ---------------------------------------------------------------------------
# DQ-11 — Tax Rate Range
# ---------------------------------------------------------------------------
def test_dq11_tax_rate_out_of_range_triggers_warning():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "tax_percentage": [75]}
    )
    violations = check_dq11_tax_rate_range(pl)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-11" and violations[0].severity == WARNING


def test_dq11_tax_rate_in_range_pass_clean():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "tax_percentage": [25.0]}
    )
    assert check_dq11_tax_rate_range(pl) == []


# ---------------------------------------------------------------------------
# DQ-12 — Dividend Payout Cap
# ---------------------------------------------------------------------------
def test_dq12_dividend_payout_over_cap_triggers_warning():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "dividend_payout": [250]}
    )
    violations = check_dq12_dividend_payout_cap(pl)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-12" and violations[0].severity == WARNING


def test_dq12_dividend_payout_within_cap_pass_clean():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "dividend_payout": [45.0]}
    )
    assert check_dq12_dividend_payout_cap(pl) == []


# ---------------------------------------------------------------------------
# DQ-13 — URL Validity (mocked — no real network calls in tests)
# ---------------------------------------------------------------------------
def test_dq13_404_url_triggers_warning(monkeypatch):
    import src.etl.validator as validator_module

    class FakeResponse:
        status_code = 404

    def fake_head(url, timeout, allow_redirects):
        return FakeResponse()

    monkeypatch.setattr("requests.head", fake_head)

    documents = pd.DataFrame(
        {
            "company_id": ["ABB"],
            "Year": [2024],
            "Annual_Report": ["https://bseindia.com/fake.pdf"],
        }
    )
    violations = validator_module.check_dq13_url_validity(documents)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-13" and violations[0].severity == WARNING


def test_dq13_200_url_pass_clean(monkeypatch):
    import src.etl.validator as validator_module

    class FakeResponse:
        status_code = 200

    def fake_head(url, timeout, allow_redirects):
        return FakeResponse()

    monkeypatch.setattr("requests.head", fake_head)

    documents = pd.DataFrame(
        {
            "company_id": ["ABB"],
            "Year": [2024],
            "Annual_Report": ["https://bseindia.com/real.pdf"],
        }
    )
    assert validator_module.check_dq13_url_validity(documents) == []


# ---------------------------------------------------------------------------
# DQ-14 — EPS Sign Consistency
# ---------------------------------------------------------------------------
def test_dq14_eps_sign_mismatch_triggers_warning():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "net_profit": [100], "eps": [-5]}
    )
    violations = check_dq14_eps_sign_consistency(pl)
    assert len(violations) == 1
    assert violations[0].rule_id == "DQ-14" and violations[0].severity == WARNING


def test_dq14_eps_sign_consistent_pass_clean():
    pl = pd.DataFrame(
        {"company_id": ["X"], "year": ["2023-03"], "net_profit": [100], "eps": [5]}
    )
    assert check_dq14_eps_sign_consistency(pl) == []


# ---------------------------------------------------------------------------
# DQ-15 — BSE/ASE Balance, strict (informational counter, not a violation list)
# ---------------------------------------------------------------------------
def test_dq15_exact_balance_counter_counts_correctly():
    bs = pd.DataFrame(
        {
            "total_assets": [1000, 500, 750],
            "total_liabilities": [1000, 505, 750],
        }
    )
    result = check_dq15_exact_balance_count(bs)
    assert result["rule_id"] == "DQ-15"
    assert result["severity"] == INFO
    assert result["exact_balance_count"] == 2
    assert result["total_rows_checked"] == 3


# ---------------------------------------------------------------------------
# DQ-16 — Coverage Check
# ---------------------------------------------------------------------------
def test_dq16_insufficient_history_triggers_warning():
    pl = pd.DataFrame({"company_id": ["X", "X"], "year": ["2022-03", "2023-03"]})
    bs = pd.DataFrame({"company_id": ["X", "X"], "year": ["2022-03", "2023-03"]})
    cf = pd.DataFrame({"company_id": ["X", "X"], "year": ["2022-03", "2023-03"]})
    violations = check_dq16_coverage_check(
        {"profitandloss": pl, "balancesheet": bs, "cashflow": cf}, min_years=5
    )
    assert len(violations) == 3  # flagged once per table
    assert all(v.rule_id == "DQ-16" and v.severity == WARNING for v in violations)


def test_dq16_sufficient_history_pass_clean():
    years = [f"{2018 + i}-03" for i in range(6)]
    pl = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    bs = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    cf = pd.DataFrame({"company_id": ["X"] * 6, "year": years})
    violations = check_dq16_coverage_check(
        {"profitandloss": pl, "balancesheet": bs, "cashflow": cf}, min_years=5
    )
    assert violations == []


# ---------------------------------------------------------------------------
# Orchestration — run_all_dq_rules()
# ---------------------------------------------------------------------------
def test_run_all_dq_rules_aggregates_violations_and_returns_dataframe():
    companies = pd.DataFrame({"id": ["TCS", "INFY"]})
    pl = pd.DataFrame(
        {
            "company_id": ["TCS", "GHOST"],
            "year": ["2023-03", "2023-03"],
            "sales": [225458, 0],
            "operating_profit": [48534, 0],
            "opm_percentage": [21.5, 0],
            "tax_percentage": [25.0, 25.0],
            "dividend_payout": [45.0, 45.0],
            "net_profit": [34990, 0],
            "eps": [95.3, 0],
        }
    )
    frames = {"companies": companies, "profitandloss": pl}
    violations_df, info = run_all_dq_rules(frames)

    assert isinstance(violations_df, pd.DataFrame)
    assert set(violations_df.columns) == {
        "rule_id",
        "severity",
        "company_id",
        "year",
        "field",
        "issue",
    }
    # GHOST is an orphan (DQ-03) and has sales=0 (DQ-06) — at least these
    # two rules should have fired.
    assert "DQ-03" in violations_df["rule_id"].values
    assert "DQ-06" in violations_df["rule_id"].values


def test_run_all_dq_rules_empty_input_returns_empty_dataframe():
    violations_df, info = run_all_dq_rules({})
    assert violations_df.empty
    assert list(violations_df.columns) == [
        "rule_id",
        "severity",
        "company_id",
        "year",
        "field",
        "issue",
    ]


def test_run_all_dq_rules_normalises_before_fk_and_dedup_checks():
    """
    Regression test: a lowercase/whitespace-padded company_id that refers
    to a real company must NOT be flagged as an orphan (DQ-03), and two
    rows for the same company+year written with different raw casing must
    still be caught as a true duplicate (DQ-02) — both only work if
    normalisation happens before these checks run.
    """
    companies = pd.DataFrame({"id": ["TCS"]})
    pl = pd.DataFrame(
        {
            "company_id": [" tcs ", "TCS"],  # same company, different raw casing
            "year": ["Mar-23", "2023-03"],  # same FY, different raw format
            "sales": [225458, 225458],
            "operating_profit": [48534, 48534],
            "opm_percentage": [21.5, 21.5],
            "tax_percentage": [25.0, 25.0],
            "dividend_payout": [45.0, 45.0],
            "net_profit": [34990, 34990],
            "eps": [95.3, 95.3],
        }
    )
    violations_df, _ = run_all_dq_rules({"companies": companies, "profitandloss": pl})

    # Must NOT appear: a casing/whitespace variant should never look like
    # a missing company.
    assert "DQ-03" not in violations_df["rule_id"].values

    # Must appear: after normalising, these two rows are an exact
    # (company_id, year) duplicate.
    assert "DQ-02" in violations_df["rule_id"].values
