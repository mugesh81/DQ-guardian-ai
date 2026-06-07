"""Integration tests for the FastAPI MCP server.

Mocks backend engine validations and queries the endpoint routers using TestClient.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.mcp.server import app


@pytest.fixture
def client() -> TestClient:
    """Provides a TestClient wrapper around the server app."""
    return TestClient(app)


def test_health_endpoint_returns_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_tools_endpoint_lists_6_tools(client):
    res = client.get("/tools")
    assert res.status_code == 200
    tools = res.json()
    assert len(tools) == 6
    names = [t["name"] for t in tools]
    assert "run_quality_check" in names
    assert "get_bad_rows" in names
    assert "generate_fix" in names
    assert "apply_fix" in names
    assert "generate_yaml_rules" in names
    assert "chat_with_dataset" in names


def test_run_quality_check_returns_run_id(client, mocker):
    # Build a minimal real DataFrame so len() works
    fake_df = pd.DataFrame({"col": [1, 2, 3]})

    mocker.patch(
        "app.agent.validator.ValidationEngine.run_all_checks",
        return_value=mocker.Mock(
            run_id="run_mcp_01",
            timestamp="2023-01-01T00:00:00Z",
            total_checks=1,
            passed=1,
            failed=0,
            success_rate=100.0,
            results=[]
        )
    )
    mocker.patch("app.mcp.server.pd.read_csv", return_value=fake_df)
    mocker.patch("pathlib.Path.exists", return_value=True)
    # Mock save_run on the live memory instance inside server module to avoid UNIQUE conflicts
    mocker.patch("app.mcp.server.memory.save_run", return_value="run_mcp_01")
    mocker.patch("app.mcp.server.memory.save_failure", return_value="fail_01")

    payload = {
        "file_path": "Sample Data Folder/sales.csv",
        "rules_path": "rules/sales_rules.yaml"
    }

    res = client.post("/tools/run_quality_check", json=payload)
    assert res.status_code == 200
    assert "run_id" in res.json()


def test_get_bad_rows_returns_sample(client, mocker):
    # MagicMock supports context manager protocol (__enter__/__exit__)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        "failure_count": 5,
        "check_name": "null_check",
        "column_name": "email",
        "sample_bad_rows_json": '[{"email": null}]'
    }
    mocker.patch(
        "app.agent.memory_engine.MemoryEngine._get_connection",
        return_value=mock_conn
    )
    
    payload = {
        "run_id": "run_mcp_01",
        "check_name": "null_check",
        "limit": 1
    }
    res = client.post("/tools/get_bad_rows", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["bad_rows"]) == 1
    assert data["total_count"] == 5


def test_generate_fix_returns_fix_data(client, mocker):
    # MagicMock supports context manager protocol (__enter__/__exit__)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        {
            "id": "fail_01",
            "check_name": "null_check",
            "column_name": "email",
            "failure_count": 5,
            "total_count": 100,
            "failure_percentage": 5.0,
            "severity": "high",
            "sample_bad_rows_json": "[]"
        },
        {
            "filename": "sales.csv"
        }
    ]
    mocker.patch(
        "app.agent.memory_engine.MemoryEngine._get_connection",
        return_value=mock_conn
    )
    
    # Mock analyzer & generator
    mocker.patch(
        "app.agent.root_cause_analyzer.RootCauseAnalyzer.analyze",
        return_value=mocker.Mock(
            root_cause="Missing emails",
            business_impact="None",
            confidence_score=0.90,
            recommended_fix="Impute",
            pandas_fix="df['email'] = 'test'",
            sql_fix="UPDATE",
            is_fallback=False,
            model_used="test"
        )
    )
    
    mocker.patch(
        "app.agent.fix_generator.FixGenerator.generate",
        return_value=mocker.Mock(
            fix_id="fix_01",
            pandas_fix="df['email'] = 'test'",
            sql_fix="UPDATE",
            pandas_fix_valid=True,
            sql_fix_valid=True,
            confidence_score=90.0,
            fix_status="valid",
            security_warnings=[]
        )
    )
    
    payload = {
        "run_id": "run_mcp_01",
        "check_name": "null_check"
    }
    res = client.post("/tools/generate_fix", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["fix_id"] is not None
    assert "pandas_fix" in data


def test_apply_fix_rejected_when_approve_false(client):
    payload = {
        "run_id": "run_mcp_01",
        "fix_id": "fix_01",
        "approve": False
    }
    res = client.post("/tools/apply_fix", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "Fix rejected by user"


def test_generate_yaml_rules_returns_yaml(client, mocker):
    mocker.patch.dict("os.environ", {"GROQ_API_KEY": "fake_test_key"})
    
    mock_groq_res = mocker.Mock()
    mock_groq_res.status_code = 200
    mock_groq_res.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "rules:\n  - id: R1\n    check_type: null_check\n    column: email"
                }
            }
        ]
    }
    mocker.patch("requests.post", return_value=mock_groq_res)
    
    payload = {
        "natural_language": "Check if email is null"
    }
    res = client.post("/tools/generate_yaml_rules", json=payload)
    assert res.status_code == 200
    assert "yaml_rules" in res.json()


def test_chat_returns_answer(client, mocker):
    mocker.patch.dict("os.environ", {"GROQ_API_KEY": "fake_test_key"})

    # Patch the server-level memory instance's _get_connection directly
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        "filename": "sales.csv",
        "success_rate": 90.0,
        "total_checks": 5,
        "passed_checks": 4,
        "failed_checks": 1
    }
    mock_cursor.fetchall.return_value = []
    mocker.patch(
        "app.mcp.server.memory._get_connection",
        return_value=mock_conn
    )

    # Mock Groq call
    mock_groq_res = mocker.Mock()
    mock_groq_res.status_code = 200
    mock_groq_res.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "The dataset failed because of missing order dates."
                }
            }
        ]
    }
    mocker.patch("requests.post", return_value=mock_groq_res)

    payload = {
        "run_id": "run_mcp_01",
        "question": "Why did it fail?"
    }
    res = client.post("/tools/chat_with_dataset", json=payload)
    assert res.status_code == 200
    assert "answer" in res.json()
