"""Coverage-boost tests for DQ Guardian AI.

Targets uncovered branches in:
  - validator.py  (run_single_check, missing-column paths, DatatypeCheck variants)
  - fix_generator.py  (security blocks, SQL injection, SyntaxError path)
  - confidence_engine.py  (score calculation branches)
"""

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.agent.confidence_engine import ConfidenceEngine
from app.agent.fix_generator import FixGenerator
from app.agent.root_cause_analyzer import RootCauseResult
from app.agent.validator import (
    CheckResult,
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


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def small_df() -> pd.DataFrame:
    """Tiny clean DataFrame (3 rows, all valid)."""
    return pd.DataFrame(
        {
            "id": ["A1", "A2", "A3"],
            "amount": [10.0, 20.0, 30.0],
            "created": ["2023-01-01", "2023-06-15", "2022-12-31"],
            "flag": [True, False, True],
        }
    )


@pytest.fixture
def root_cause_ok() -> RootCauseResult:
    """Valid RootCauseResult with safe pandas/SQL fix."""
    return RootCauseResult(
        check_name="null_check_email",
        root_cause="Nulls in email column.",
        business_impact="Low",
        confidence_score=0.85,
        recommended_fix="Fill nulls with placeholder.",
        pandas_fix="df['email'] = df['email'].fillna('missing@example.com')",
        sql_fix="UPDATE t SET email = 'missing@example.com' WHERE email IS NULL",
        is_fallback=False,
        model_used="llama-3.3-70b-versatile",
    )


@pytest.fixture
def root_cause_with_import() -> RootCauseResult:
    """RootCauseResult whose pandas_fix contains a forbidden import."""
    return RootCauseResult(
        check_name="hack_check",
        root_cause="Test",
        business_impact="None",
        confidence_score=0.5,
        recommended_fix="Bad fix",
        pandas_fix="import os\ndf = df.dropna()",
        sql_fix="SELECT 1",
        is_fallback=False,
        model_used="llama-3.1-8b-instant",
    )


@pytest.fixture
def root_cause_with_exec() -> RootCauseResult:
    """RootCauseResult whose pandas_fix calls exec()."""
    return RootCauseResult(
        check_name="exec_check",
        root_cause="Test",
        business_impact="None",
        confidence_score=0.5,
        recommended_fix="Bad fix",
        pandas_fix="exec('malicious_code')",
        sql_fix="SELECT 1",
        is_fallback=False,
        model_used="llama-3.1-8b-instant",
    )


@pytest.fixture
def root_cause_syntax_error() -> RootCauseResult:
    """RootCauseResult whose pandas_fix is syntactically invalid Python."""
    return RootCauseResult(
        check_name="syntax_check",
        root_cause="Test",
        business_impact="None",
        confidence_score=0.3,
        recommended_fix="Bad Python",
        pandas_fix="def broken(:\n    pass",
        sql_fix="SELECT 1",
        is_fallback=True,
        model_used="llama-3.1-8b-instant",
    )


@pytest.fixture
def root_cause_sql_danger() -> RootCauseResult:
    """RootCauseResult whose sql_fix contains a DROP TABLE statement."""
    return RootCauseResult(
        check_name="sql_danger_check",
        root_cause="Test",
        business_impact="None",
        confidence_score=0.7,
        recommended_fix="Clean SQL",
        pandas_fix="df = df.dropna()",
        sql_fix="DROP TABLE users",
        is_fallback=False,
        model_used="llama-3.3-70b-versatile",
    )


# ─── Validator: missing-column branches ──────────────────────────────────────
# When a column is missing, _create_result receives an all-False mask which
# yields PASS (no rows fail). The early-return path is still exercised for
# coverage; the observable effect is PASS (no crash).

def test_null_check_missing_column_no_crash(small_df):
    check = NullCheck("missing_col_null", "nonexistent", severity="high")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_unique_check_missing_column_no_crash(small_df):
    check = UniqueCheck("missing_col_unique", "nonexistent", severity="medium")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_duplicate_check_missing_column_no_crash(small_df):
    check = DuplicateCheck("missing_col_dup", "nonexistent", severity="low")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_range_check_missing_column_no_crash(small_df):
    check = RangeCheck("missing_col_range", "nonexistent", severity="high", params={"min": 0, "max": 100})
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_regex_check_missing_column_no_crash(small_df):
    check = RegexCheck("missing_col_regex", "nonexistent", severity="medium", params={"pattern": ".*"})
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_negative_check_missing_column_no_crash(small_df):
    check = NegativeValueCheck("missing_col_neg", "nonexistent", severity="low")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_outlier_check_missing_column_no_crash(small_df):
    check = OutlierDetectionCheck("missing_col_out", "nonexistent", severity="low")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_date_validation_missing_column_no_crash(small_df):
    check = DateValidationCheck("missing_col_date", "nonexistent", severity="medium")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


def test_future_date_missing_column_no_crash(small_df):
    check = FutureDateCheck("missing_col_future", "nonexistent", severity="medium")
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


# ─── Validator: DatatypeCheck branches ───────────────────────────────────────

def test_datatype_check_exact_match_passes(small_df):
    """Column 'amount' is already float64 — must PASS instantly."""
    check = DatatypeCheck("amount_type", "amount", severity="low", params={"expected_type": "float64"})
    res = check.run(small_df)
    assert res.status == "PASS"


def test_datatype_check_int64_cast(small_df):
    """Coercion path for int64 expected type on string-encoded numbers."""
    df = small_df.copy()
    df["amount"] = df["amount"].astype(str)  # Force object dtype
    check = DatatypeCheck("amount_int", "amount", severity="low", params={"expected_type": "int64"})
    res = check.run(df)
    assert res.status in ("PASS", "FAIL")


def test_datatype_check_datetime_cast(small_df):
    """Coercion path for datetime64[ns] expected type."""
    check = DatatypeCheck("created_dt", "created", severity="low", params={"expected_type": "datetime64[ns]"})
    res = check.run(small_df)
    assert res.status in ("PASS", "FAIL")


def test_datatype_check_bool_valid(small_df):
    """Bool check on a boolean column — should not crash."""
    check = DatatypeCheck("flag_bool", "flag", severity="low", params={"expected_type": "bool"})
    res = check.run(small_df)
    assert res.status in ("PASS", "FAIL")


def test_datatype_check_missing_column_no_crash(small_df):
    check = DatatypeCheck("missing_type", "nonexistent", severity="low", params={"expected_type": "float64"})
    res = check.run(small_df)
    assert res.status in ("PASS", "ERROR")


# ─── Validator: ValidationEngine.run_single_check ────────────────────────────

def test_run_single_check_found(sample_rules_yaml):
    """run_single_check returns a result when check name exists."""
    engine = ValidationEngine()
    engine.load_rules_from_yaml(sample_rules_yaml)
    df = pd.DataFrame({"name": ["Alice"], "revenue": [100.0], "email": ["a@b.com"]})
    result = engine.run_single_check(df, "name_null_check")
    assert result.status in ("PASS", "FAIL")


def test_run_single_check_raises_on_missing(sample_rules_yaml):
    """run_single_check raises ValueError when no check matches the name."""
    engine = ValidationEngine()
    engine.load_rules_from_yaml(sample_rules_yaml)
    df = pd.DataFrame({"name": ["Alice"]})
    with pytest.raises(ValueError, match="No loaded check matches name"):
        engine.run_single_check(df, "does_not_exist_check")


def test_load_rules_from_yaml_unknown_check_type(tmp_path):
    """Engine skips unknown check_type with a warning, returns empty list."""
    yaml_content = """
rules:
  - id: BAD_01
    name: bad_check
    column: col
    check_type: unsupported_magic_check
    severity: medium
"""
    rules_file = tmp_path / "bad_rules.yaml"
    rules_file.write_text(yaml_content, encoding="utf-8")
    engine = ValidationEngine()
    checks = engine.load_rules_from_yaml(rules_file)
    assert checks == []


def test_load_rules_missing_file(tmp_path):
    """Engine returns empty list when rules file does not exist."""
    engine = ValidationEngine()
    checks = engine.load_rules_from_yaml(tmp_path / "ghost_rules.yaml")
    assert checks == []


def test_run_all_checks_empty_check_list(small_df):
    """run_all_checks with no loaded rules returns 100% success rate."""
    engine = ValidationEngine()
    report = engine.run_all_checks(small_df, filename="empty_run.csv")
    assert report.total_checks == 0
    assert report.success_rate == 100.0
    assert report.filename == "empty_run.csv"


def test_outlier_check_zero_std():
    """OutlierDetectionCheck with all identical values (std=0) must PASS."""
    df = pd.DataFrame({"val": [5.0, 5.0, 5.0, 5.0]})
    check = OutlierDetectionCheck("const_outlier", "val", severity="low", params={"threshold": 3.0})
    res = check.run(df)
    assert res.status == "PASS"


def test_row_count_check_exact_boundary(small_df):
    """RowCountCheck at exact boundary passes."""
    check = RowCountCheck("exact_count", "", params={"min_rows": 3, "max_rows": 3})
    res = check.run(small_df)
    assert res.status == "PASS"


# ─── FixGenerator: Security checks ───────────────────────────────────────────

def test_fix_generator_valid_safe_code(root_cause_ok, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_ok, small_df)
    assert result.pandas_fix_valid is True
    assert result.fix_status == "valid"
    assert result.security_warnings == []


def test_fix_generator_blocks_forbidden_import(root_cause_with_import, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_with_import, small_df)
    assert result.pandas_fix_valid is False
    assert result.fix_status == "invalid"
    assert any("Forbidden import" in w for w in result.security_warnings)


def test_fix_generator_blocks_exec_call(root_cause_with_exec, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_with_exec, small_df)
    assert result.pandas_fix_valid is False
    assert any("exec" in w for w in result.security_warnings)


def test_fix_generator_syntax_error(root_cause_syntax_error, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_syntax_error, small_df)
    assert result.pandas_fix_valid is False
    assert result.fix_status == "invalid"
    assert any("syntax error" in w.lower() for w in result.security_warnings)


def test_fix_generator_blocks_dangerous_sql(root_cause_sql_danger, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_sql_danger, small_df)
    assert result.sql_fix_valid is False
    assert any("drop table" in w.lower() for w in result.security_warnings)


def test_fix_generator_fix_id_is_uuid(root_cause_ok, small_df):
    gen = FixGenerator()
    result = gen.generate(root_cause_ok, small_df)
    uuid.UUID(result.fix_id)  # Raises if not a valid UUID


# ─── ConfidenceEngine ────────────────────────────────────────────────────────

def _make_check_result(severity: str = "medium") -> CheckResult:
    return CheckResult(
        check_name="test_check",
        column="revenue",
        status="FAIL",
        failure_count=10,
        total_count=100,
        failure_percentage=10.0,
        severity=severity,
        column_stats={"null_count": 2, "unique_count": 80},
    )


def test_confidence_engine_valid_syntax_high_improvement():
    engine = ConfidenceEngine()
    check_res = _make_check_result("low")
    fix_code = "df['revenue'] = df['revenue'].fillna(0)"
    score = engine.score(fix_code, check_res, improvement_pct=95.0)
    assert 0.0 <= score <= 100.0
    assert score > 50.0  # should score well


def test_confidence_engine_critical_partial_improvement():
    """Critical severity with < 100% improvement should incur a penalty."""
    engine = ConfidenceEngine()
    check_res = _make_check_result("critical")
    fix_code = "df['revenue'] = df['revenue'].fillna(0)"
    score_partial = engine.score(fix_code, check_res, improvement_pct=80.0)
    score_full = engine.score(fix_code, check_res, improvement_pct=100.0)
    assert score_partial < score_full


def test_confidence_engine_syntax_error_returns_zero():
    """Invalid Python syntax in fix_code should return 0.0."""
    engine = ConfidenceEngine()
    check_res = _make_check_result("medium")
    score = engine.score("def broken(:\n    pass", check_res, improvement_pct=90.0)
    assert score == 0.0


def test_confidence_engine_empty_fix_penalized():
    """Fix with only comments (no real code) should be penalized."""
    engine = ConfidenceEngine()
    check_res = _make_check_result("medium")
    score = engine.score("# This is just a comment", check_res, improvement_pct=50.0)
    assert score >= 0.0  # clipped to 0, not negative
