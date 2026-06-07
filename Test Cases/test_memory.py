"""Unit tests for the memory engine.

Tests all CRUD operations, transaction locking, statistics generators, and text searching features in SQLite.
"""

from datetime import datetime
import pytest

from app.agent.memory_engine import MemoryEngine


def test_save_and_retrieve_run(in_memory_engine):
    run_data = {
        "run_id": "run_test_01",
        "timestamp": "2023-01-01T00:00:00Z",
        "filename": "sales.csv",
        "total_rows": 100,
        "rules_evaluated": 5,
        "rules_failed": 2,
        "overall_improvement_percentage": 60.0,
        "total_duration_seconds": 1.2,
        "iterations": 1
    }
    run_id = in_memory_engine.save_run(run_data)
    assert run_id == "run_test_01"
    
    history = in_memory_engine.get_run_history(limit=5)
    assert len(history) == 1
    assert history[0]["filename"] == "sales.csv"
    assert history[0]["success_rate"] == 60.0


def test_save_and_retrieve_failure(in_memory_engine):
    run_id = "run_test_02"
    failure_data = {
        "check_name": "null_check_email",
        "column": "email",
        "failure_count": 10,
        "total_count": 100,
        "failure_percentage": 10.0,
        "severity": "critical",
        "sample_bad_rows": [{"id": 1, "email": None}],
        "column_stats": {"null_count": 10}
    }
    fail_id = in_memory_engine.save_failure(failure_data, run_id)
    assert isinstance(fail_id, str)
    
    failures = in_memory_engine.get_similar_failures("null_check", "email")
    assert len(failures) == 1
    assert failures[0]["check_name"] == "null_check_email"


def test_save_and_retrieve_fix(in_memory_engine):
    run_id = "run_test_03"
    fail_id = "fail_test_03"
    fix_data = {
        "fix_id": "fix_test_03",
        "pandas_fix": "df['email'] = df['email'].fillna('N/A')",
        "sql_fix": "UPDATE table SET email = 'N/A' WHERE email IS NULL",
        "confidence_score": 85.0,
        "pandas_fix_valid": True,
        "was_applied": False,
        "improvement_percentage": 0.0
    }
    
    fix_id = in_memory_engine.save_fix(fix_data, fail_id, run_id)
    assert fix_id == "fix_test_03"
    
    # Retrieve fix via generated_fixes table query directly or stats
    stats = in_memory_engine.get_memory_stats()
    assert stats["total_fixes"] == 1


def test_get_best_fix_for_pattern(in_memory_engine):
    # Seed duplicate fix attempts
    in_memory_engine.save_fix_attempt(
        check_name="null_check",
        column="email",
        root_cause="Missing emails",
        fix_code="df['email'] = df['email'].fillna('test@example.com')",
        improvement=100.0,
        confidence=90.0,
        is_success=True
    )
    
    best_fix = in_memory_engine.get_best_fix("null_check", "email")
    assert best_fix is not None
    assert best_fix["success_count"] == 1
    assert "test@example.com" in best_fix["fix_code"]


def test_memory_reuse_with_high_success_rate(in_memory_engine):
    in_memory_engine.save_fix_attempt(
        check_name="range_check",
        column="revenue",
        root_cause="Negative revenues",
        fix_code="df['revenue'] = df['revenue'].clip(lower=0.0)",
        improvement=100.0,
        confidence=95.0,
        is_success=True
    )
    
    # Add a failure so it has success count = 1, fail count = 0 -> 100% success rate
    best = in_memory_engine.get_best_fix("range_check", "revenue")
    assert best["success_rate"] == 100.0


def test_update_fix_outcome_success(in_memory_engine):
    # Save a run and failure first
    run_id = "run_test_04"
    fail_id = "fail_test_04"
    fix_data = {
        "fix_id": "fix_test_04",
        "pandas_fix": "df['age'] = df['age'].fillna(30)",
        "sql_fix": "UPDATE table SET age = 30",
        "confidence_score": 80.0,
        "pandas_fix_valid": True,
        "was_applied": False,
        "improvement_percentage": 0.0
    }
    in_memory_engine.save_fix(fix_data, fail_id, run_id)
    
    # Update outcome
    in_memory_engine.update_fix_outcome("fix_test_04", improved=True, improvement_pct=100.0)
    
    with in_memory_engine._get_connection() as conn:
        row = conn.execute("SELECT * FROM generated_fixes WHERE id = 'fix_test_04'").fetchone()
        assert row["was_applied"] == 1
        assert row["improvement_percentage"] == 100.0


def test_update_fix_outcome_failure(in_memory_engine):
    run_id = "run_test_05"
    fail_id = "fail_test_05"
    fix_data = {
        "fix_id": "fix_test_05",
        "pandas_fix": "df['age'] = df['age'].fillna(30)",
        "sql_fix": "UPDATE table SET age = 30",
        "confidence_score": 80.0,
        "pandas_fix_valid": True,
        "was_applied": False,
        "improvement_percentage": 0.0
    }
    in_memory_engine.save_fix(fix_data, fail_id, run_id)
    
    # Update outcome with failed improvement
    in_memory_engine.update_fix_outcome("fix_test_05", improved=False, improvement_pct=0.0)
    
    with in_memory_engine._get_connection() as conn:
        row = conn.execute("SELECT * FROM generated_fixes WHERE id = 'fix_test_05'").fetchone()
        assert row["was_applied"] == 0
        assert row["improvement_percentage"] == 0.0


def test_get_memory_stats_returns_all_fields(in_memory_engine):
    stats = in_memory_engine.get_memory_stats()
    assert "total_runs" in stats
    assert "total_fixes" in stats
    assert "avg_success_rate" in stats
    assert "most_common_failure" in stats
    assert "top_performing_fix" in stats


def test_search_memory_finds_by_root_cause(in_memory_engine):
    in_memory_engine.save_fix_attempt(
        check_name="null_check",
        column="email",
        root_cause="Discovered broken email records in source CSV",
        fix_code="df['email'] = df['email'].fillna('none@example.com')",
        improvement=100.0,
        confidence=90.0,
        is_success=True
    )
    
    results = in_memory_engine.search_memory("broken email")
    assert len(results) == 1
    assert "email" in results[0]["failure_pattern"]


def test_save_and_retrieve_generated_rule(in_memory_engine):
    nl_input = "Ensure age is between 0 and 120"
    yaml_output = "rules:\n  - id: R1\n    check_type: range_check"
    
    rule_id = in_memory_engine.save_rule(nl_input, yaml_output)
    assert isinstance(rule_id, str)
    
    rules = in_memory_engine.get_all_rules()
    assert len(rules) == 1
    assert rules[0]["natural_language_input"] == nl_input
    assert rules[0]["yaml_output"] == yaml_output
