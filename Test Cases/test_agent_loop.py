"""Unit tests for the agent loop coordinator.

Mocks external Groq API requests to test planning stages, fallback logic, memory reuse, and iteration counts.
"""

import os
from pathlib import Path
import pytest
import requests

from app.agent.agent_loop import AgentLoop
from app.agent.memory_engine import MemoryEngine
from app.agent.root_cause_analyzer import RootCauseResult


# Mocking Groq completions requests using pytest-mock
@pytest.fixture(autouse=True)
def mock_groq_api(mocker, mock_groq_response):
    """Automatically mocks all requests.post calls to the Groq completion server."""
    # Set env var so analyzer attempts API execution
    mocker.patch.dict(os.environ, {"GROQ_API_KEY": "fake_test_key"})
    
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_groq_response
    
    return mocker.patch("requests.post", return_value=mock_resp)


def test_agent_loop_observe_stage(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    df_loaded = loop._load_data()
    
    assert len(df_loaded) == 20
    report = loop.validator.run_all_checks(df_loaded)
    assert report.total_checks == 3


def test_agent_loop_reason_stage_uses_memory(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    db_file = tmp_path / "test.db"
    # Seed memory with highly successful past fix
    mem = MemoryEngine(db_path=db_file)
    mem.save_fix_attempt(
        check_name="name_null_check",
        column="name",
        root_cause="Missing names",
        fix_code="df['name'] = df['name'].fillna('Imputed Name')",
        improvement=100.0,
        confidence=95.0,
        is_success=True
    )
    
    # Run loop
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=db_file)
    result = loop.run()
    
    # Assert memory was checked and reused
    assert result["fixes_from_memory"] >= 1


def test_agent_loop_act_stage_generates_fixes(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    result = loop.run()
    
    assert len(result["proposed_fixes"]) >= 1
    assert result["fixes_new"] >= 1


def test_agent_loop_validate_stage_improvement(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    result = loop.run()
    
    # Improvement percentage should evaluate
    assert "overall_improvement_percentage" in result
    assert result["overall_improvement_percentage"] >= 0.0


def test_agent_loop_learn_stage_saves_to_memory(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)

    db_file = tmp_path / "test.db"
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=db_file)
    loop.run()

    # Agent loop writes fix attempts to agent_memory table (not validation_runs)
    mem = MemoryEngine(db_path=db_file)
    with mem._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM agent_memory")
        count = cursor.fetchone()[0]
    assert count >= 1


def test_agent_loop_repeats_on_low_improvement(sample_df, sample_rules_yaml, tmp_path, mocker):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    # Mock analyzer to return bad fixes (0 improvement) to force loop to repeat
    mocker.patch(
        "app.agent.fix_generator.FixGenerator.generate",
        return_value=mocker.Mock(
            fix_id="bad_fix",
            check_name="name_null_check",
            pandas_fix="df['name'] = df['name']",  # doing nothing
            sql_fix="SELECT 1",
            pandas_fix_valid=True,
            sql_fix_valid=True,
            confidence_score=50.0,
            fix_status="valid",
            security_warnings=[]
        )
    )
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db", max_iterations=2)
    result = loop.run()
    
    # Should run the maximum 2 iterations due to low/no improvement
    assert result["iterations"] == 2


def test_agent_loop_stops_at_max_iterations(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db", max_iterations=1)
    result = loop.run()
    assert result["iterations"] == 1


def test_agent_loop_handles_groq_rate_limit(sample_df, sample_rules_yaml, tmp_path, mocker, mock_groq_response):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    # Setup mock to fail with 429 on first call, succeed on second call
    mock_429 = mocker.Mock()
    mock_429.status_code = 429
    mock_429.text = "Rate Limit Exceeded"
    
    mock_200 = mocker.Mock()
    mock_200.status_code = 200
    mock_200.json.return_value = mock_groq_response
    
    mocker.patch("requests.post", side_effect=[mock_429, mock_200, mock_200, mock_200, mock_200])
    
    # Mock time.sleep to avoid waiting 60s during test execution
    mocker.patch("time.sleep", return_value=None)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    result = loop.run()
    assert result["status"] in ("Success", "Partial Success")


def test_agent_loop_uses_fallback_on_api_failure(sample_df, sample_rules_yaml, tmp_path, mocker):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    # API fails consistently
    mock_error = mocker.Mock()
    mock_error.status_code = 500
    mock_error.text = "Internal Server Error"
    mocker.patch("requests.post", return_value=mock_error)
    mocker.patch("time.sleep", return_value=None)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    result = loop.run()
    
    # Should complete without crash using fallback
    assert len(result["proposed_fixes"]) >= 1


def test_agent_loop_returns_complete_result(sample_df, sample_rules_yaml, tmp_path):
    data_path = tmp_path / "dirty_data.csv"
    sample_df.to_csv(data_path, index=False)
    
    loop = AgentLoop(data_path=data_path, rules_path=sample_rules_yaml, db_path=tmp_path / "test.db")
    result = loop.run()
    
    assert "run_id" in result
    assert "filename" in result
    assert "rules_evaluated" in result
    assert "rules_failed" in result
    assert "proposed_fixes" in result
