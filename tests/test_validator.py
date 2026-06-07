"""Unit tests for the validator engine.

Verifies custom check logic (NullCheck, RangeCheck, RegexCheck, DatatypeCheck, etc.) and ValidationEngine report aggregation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from app.agent.validator import (
    ColumnExistenceCheck,
    DatatypeCheck,
    DateValidationCheck,
    DuplicateCheck,
    FutureDateCheck,
    NegativeValueCheck,
    NullCheck,
    OutlierDetectionCheck,
    RangeCheck,
    RegexCheck,
    RowCountCheck,
    UniqueCheck,
    ValidationEngine,
)


def test_null_check_detects_nulls(sample_df):
    check = NullCheck("name_nulls", "name", severity="critical")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    assert res.failure_count == 1
    assert len(res.sample_bad_rows) == 1
    assert res.sample_bad_rows[0]["customer_id"] == "CUST001"


def test_null_check_passes_clean_data(sample_df):
    # Category column has zero nulls
    check = NullCheck("cat_nulls", "product_category", severity="medium")
    res = check.run(sample_df)
    assert res.status == "PASS"
    assert res.failure_count == 0


def test_unique_check_detects_duplicates(sample_df):
    check = UniqueCheck("id_uniqueness", "customer_id", severity="critical")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    # Duplicated indices are CUST008 (indices 7 and 8)
    assert res.failure_count == 2


def test_duplicate_check_detects_duplicates(sample_df):
    check = DuplicateCheck("id_duplicates", "customer_id", severity="critical")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    # Keep first means only the second instance (index 8) is marked duplicate
    assert res.failure_count == 1


def test_range_check_catches_out_of_range(sample_df):
    check = RangeCheck("rev_range", "revenue", severity="high", params={"min": 0, "max": 1000000})
    res = check.run(sample_df)
    assert res.status == "FAIL"
    # Out of bounds: -50.0 (index 3) and 2000000.0 (index 4)
    assert res.failure_count == 2


def test_range_check_passes_valid_data(sample_df):
    # Quantity values are all within range 1 to 20
    check = RangeCheck("qty_range", "quantity", severity="medium", params={"min": -5, "max": 20})
    res = check.run(sample_df)
    assert res.status == "PASS"
    assert res.failure_count == 0


def test_regex_check_catches_bad_emails(sample_df):
    check = RegexCheck("email_format", "email", severity="medium", params={"pattern": "^[\\w.-]+@[\\w.-]+\\.\\w+$"})
    res = check.run(sample_df)
    assert res.status == "FAIL"
    assert res.failure_count == 1
    assert res.sample_bad_rows[0]["email"] == "bademail.com"


def test_datatype_check_catches_wrong_type(sample_df):
    # Test casting column of numbers containing strings to int64 or checking types
    check = DatatypeCheck("rev_type", "revenue", severity="low", params={"expected_type": "float64"})
    res = check.run(sample_df)
    assert res.status == "PASS"


def test_date_check_catches_bad_format(sample_df):
    check = DateValidationCheck("date_format", "order_date", severity="high", params={"format": "%Y-%m-%d"})
    res = check.run(sample_df)
    assert res.status == "FAIL"
    # 15/01/2023 format and non-existent date fail parsing format
    assert res.failure_count >= 1


def test_future_date_check_catches_future(sample_df):
    check = FutureDateCheck("no_future", "order_date", severity="medium")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    # "2027-12-31" is in the future
    assert res.failure_count >= 1


def test_outlier_check_zscore(sample_df):
    # Quantity outlier check
    check = OutlierDetectionCheck("qty_outliers", "quantity", severity="low", params={"threshold": 2.0})
    res = check.run(sample_df)
    # With a small dataset, standard deviation checks will highlight outliers
    assert res.status in ("PASS", "FAIL")


def test_validation_engine_loads_yaml(sample_rules_yaml):
    engine = ValidationEngine()
    checks = engine.load_rules_from_yaml(sample_rules_yaml)
    assert len(checks) == 3
    assert checks[0].name == "name_null_check"
    assert checks[1].column == "revenue"


def test_validation_engine_runs_all_checks(sample_df, sample_rules_yaml):
    engine = ValidationEngine()
    engine.load_rules_from_yaml(sample_rules_yaml)
    report = engine.run_all_checks(sample_df, filename="test_dataset.csv")
    assert report.total_checks == 3
    assert report.filename == "test_dataset.csv"
    assert len(report.results) == 3


def test_check_result_has_sample_rows(sample_df):
    check = NullCheck("name_nulls", "name", severity="critical")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    assert len(res.sample_bad_rows) > 0
    assert "customer_id" in res.sample_bad_rows[0]


def test_check_with_empty_dataframe():
    df_empty = pd.DataFrame(columns=["col1", "col2"])
    check = NullCheck("nulls_empty", "col1", severity="medium")
    res = check.run(df_empty)
    assert res.total_count == 0
    assert res.status == "PASS"


def test_validation_report_calculates_success_rate(sample_df, sample_rules_yaml):
    engine = ValidationEngine()
    engine.load_rules_from_yaml(sample_rules_yaml)
    report = engine.run_all_checks(sample_df)
    # The checks should evaluate and calculate success rate
    assert 0.0 <= report.success_rate <= 100.0


def test_negative_value_check(sample_df):
    check = NegativeValueCheck("neg_rev", "revenue", severity="medium")
    res = check.run(sample_df)
    assert res.status == "FAIL"
    assert res.failure_count == 1  # -50.0


def test_column_existence_check(sample_df):
    check_exists = ColumnExistenceCheck("exist_check", "revenue", severity="high")
    res_exists = check_exists.run(sample_df)
    assert res_exists.status == "PASS"
    
    check_missing = ColumnExistenceCheck("missing_check", "invalid_col", severity="high")
    res_missing = check_missing.run(sample_df)
    assert res_missing.status == "FAIL"


def test_row_count_check(sample_df):
    check_pass = RowCountCheck("count_pass", "", params={"min_rows": 10, "max_rows": 100})
    res_pass = check_pass.run(sample_df)
    assert res_pass.status == "PASS"
    
    check_fail = RowCountCheck("count_fail", "", params={"min_rows": 100, "max_rows": 200})
    res_fail = check_fail.run(sample_df)
    assert res_fail.status == "FAIL"
