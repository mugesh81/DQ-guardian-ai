"""Tests for Groq API integration, rule-based fallback, and fix code validation.

Covers: RootCauseAnalyzer (LLM path + fallback), FixGenerator (AST/security checks),
        ConfidenceEngine scoring, and JSON fence-stripping edge cases.
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.agent.confidence_engine import ConfidenceEngine
from app.agent.fix_generator import FixGenerator
from app.agent.root_cause_analyzer import RootCauseAnalyzer
from app.agent.validator import CheckResult


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_check_result(
    check_name: str = "null_check",
    column: str = "email",
    severity: str = "high",
    failure_count: int = 5,
    total_count: int = 100,
) -> CheckResult:
    """Build a minimal CheckResult for testing."""
    return CheckResult(
        check_name=check_name,
        column=column,
        status="FAIL",
        failure_count=failure_count,
        total_count=total_count,
        failure_percentage=float(failure_count / total_count * 100),
        severity=severity,
        sample_bad_rows=[{"email": None, "customer_id": "CUST001"}],
        column_stats={"null_count": failure_count, "unique_count": 95, "mean": None, "std": None},
    )


def _make_groq_response(payload: dict) -> MagicMock:
    """Build a mock requests.post response returning a JSON-serialised payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload)}}]
    }
    return mock_resp


_VALID_LLM_PAYLOAD = {
    "root_cause": "Email column contains null values.",
    "business_impact": "Customers cannot be contacted.",
    "confidence_score": 0.92,
    "recommended_fix": "Impute missing emails with a placeholder.",
    "pandas_fix": "df['email'] = df['email'].fillna('missing@example.com')",
    "sql_fix": "UPDATE sales SET email = 'missing@example.com' WHERE email IS NULL",
}


# ── Rule-based Fallback ───────────────────────────────────────────────────────

class TestRuleBasedFallback:
    """Verify _rule_based_fallback covers all 12 check types and returns is_fallback=True."""

    ALL_CHECK_TYPES = [
        ("null_check",            "email"),
        ("unique_check",          "customer_id"),
        ("duplicate_check",       "customer_id"),
        ("range_check",           "revenue"),
        ("regex_check",           "phone"),
        ("datatype_check",        "revenue"),
        ("date_validation_check", "order_date"),
        ("future_date_check",     "order_date"),
        ("outlier_detection",     "revenue"),
        ("row_count_check",       ""),
        ("column_existence_check","missing_col"),
        ("negative_value_check",  "revenue"),
    ]

    @pytest.mark.parametrize("check_name,column", ALL_CHECK_TYPES)
    def test_fallback_returns_non_empty_root_cause(self, check_name: str, column: str):
        analyzer = RootCauseAnalyzer()
        result = analyzer._rule_based_fallback(_make_check_result(check_name, column))
        assert result.root_cause, f"No root_cause for {check_name}"
        assert result.is_fallback is True
        assert result.model_used == "rule-based-fallback"
        assert result.confidence_score > 0.0

    @pytest.mark.parametrize("check_name,column", ALL_CHECK_TYPES)
    def test_fallback_returns_non_empty_pandas_fix(self, check_name: str, column: str):
        analyzer = RootCauseAnalyzer()
        result = analyzer._rule_based_fallback(_make_check_result(check_name, column))
        assert result.pandas_fix  # must not be empty string

    def test_fallback_triggered_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None, "a@b.com"]})
        result = analyzer.analyze(_make_check_result(), df)
        assert result.is_fallback is True


# ── Groq API Path ─────────────────────────────────────────────────────────────

class TestGroqAPIPath:
    """Test the live Groq API call path using mocked requests.post."""

    @patch("app.agent.root_cause_analyzer.requests.post")
    def test_successful_api_call_returns_is_fallback_false(self, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key-abc123")
        mock_post.return_value = _make_groq_response(_VALID_LLM_PAYLOAD)

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None, "a@b.com"]})
        result = analyzer.analyze(_make_check_result(), df)

        assert result.is_fallback is False
        assert result.confidence_score == pytest.approx(0.92, abs=0.01)
        assert "email" in result.root_cause.lower()

    @patch("app.agent.root_cause_analyzer.requests.post")
    def test_api_uses_primary_model(self, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        mock_post.return_value = _make_groq_response(_VALID_LLM_PAYLOAD)

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": ["a@b.com"]})
        analyzer.analyze(_make_check_result(), df)

        call_args = mock_post.call_args
        sent_payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert sent_payload["model"] == RootCauseAnalyzer.PRIMARY_MODEL

    @patch("app.agent.root_cause_analyzer.requests.post")
    @patch("app.agent.root_cause_analyzer.time.sleep", return_value=None)
    def test_rate_limit_429_triggers_fallback(self, mock_sleep, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "Rate Limit"
        # Both primary and fallback model return 429
        mock_post.return_value = mock_429

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None]})
        result = analyzer.analyze(_make_check_result(), df)

        assert result.is_fallback is True

    @patch("app.agent.root_cause_analyzer.requests.post")
    def test_500_server_error_triggers_fallback(self, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.text = "Internal Server Error"
        mock_post.return_value = mock_500

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None]})
        result = analyzer.analyze(_make_check_result(), df)

        assert result.is_fallback is True

    @patch("app.agent.root_cause_analyzer.requests.post")
    def test_json_with_markdown_fences_is_parsed_correctly(self, mock_post, monkeypatch):
        """LLM sometimes wraps JSON in ```json ... ``` fences."""
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        fenced_content = "```json\n" + json.dumps(_VALID_LLM_PAYLOAD) + "\n```"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": fenced_content}}]
        }
        mock_post.return_value = mock_resp

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None]})
        result = analyzer.analyze(_make_check_result(), df)

        # Should parse successfully, not fall back
        assert result.is_fallback is False
        assert result.confidence_score == pytest.approx(0.92, abs=0.01)

    @patch("app.agent.root_cause_analyzer.requests.post")
    def test_invalid_json_response_triggers_fallback(self, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "This is not JSON at all!"}}]
        }
        mock_post.return_value = mock_resp

        analyzer = RootCauseAnalyzer()
        df = pd.DataFrame({"email": [None]})
        result = analyzer.analyze(_make_check_result(), df)

        # Both models fail to parse → rule-based fallback
        assert result.is_fallback is True


# ── FixGenerator / AST Validation ─────────────────────────────────────────────

class TestFixGenerator:
    """Verify AST parsing, security scanning, and fix formatting."""

    def _make_analyzer_result(
        self,
        check_name: str = "null_check",
        pandas_fix: str = "df['email'] = df['email'].fillna('missing@example.com')",
        sql_fix: str = "UPDATE sales SET email = 'missing@example.com' WHERE email IS NULL",
        confidence: float = 0.85,
    ):
        from app.agent.root_cause_analyzer import RootCauseResult
        return RootCauseResult(
            check_name=check_name,
            root_cause="Missing values",
            business_impact="Cannot contact customers",
            confidence_score=confidence,
            recommended_fix="Impute nulls",
            pandas_fix=pandas_fix,
            sql_fix=sql_fix,
            is_fallback=False,
            model_used="llama-3.3-70b-versatile",
        )

    def test_valid_pandas_fix_passes(self):
        gen = FixGenerator()
        result = gen.generate(self._make_analyzer_result(), pd.DataFrame())
        assert result.pandas_fix_valid is True
        assert result.fix_status in ("valid", "needs_review")

    def test_syntax_error_marks_invalid(self):
        gen = FixGenerator()
        broken = self._make_analyzer_result(pandas_fix="df['email'] = df['email'..fillna(0)")
        result = gen.generate(broken, pd.DataFrame())
        assert result.pandas_fix_valid is False
        assert any("syntax" in w.lower() for w in result.security_warnings)

    def test_os_import_rejected(self):
        gen = FixGenerator()
        dangerous = self._make_analyzer_result(pandas_fix="import os\nos.remove('data.csv')")
        result = gen.generate(dangerous, pd.DataFrame())
        assert result.pandas_fix_valid is False
        assert len(result.security_warnings) > 0

    def test_subprocess_import_rejected(self):
        gen = FixGenerator()
        dangerous = self._make_analyzer_result(
            pandas_fix="import subprocess\nsubprocess.run(['rm', '-rf', '/'])"
        )
        result = gen.generate(dangerous, pd.DataFrame())
        assert result.pandas_fix_valid is False

    def test_eval_call_rejected(self):
        gen = FixGenerator()
        dangerous = self._make_analyzer_result(pandas_fix="eval('import os')")
        result = gen.generate(dangerous, pd.DataFrame())
        assert result.pandas_fix_valid is False

    def test_exec_call_rejected(self):
        gen = FixGenerator()
        dangerous = self._make_analyzer_result(pandas_fix="exec('__import__(\"os\")')")
        result = gen.generate(dangerous, pd.DataFrame())
        assert result.pandas_fix_valid is False

    def test_fix_id_is_uuid(self):
        import uuid
        gen = FixGenerator()
        result = gen.generate(self._make_analyzer_result(), pd.DataFrame())
        # Should not raise ValueError
        uuid.UUID(result.fix_id)

    def test_pandas_fix_formatted_with_header(self):
        gen = FixGenerator()
        result = gen.generate(self._make_analyzer_result(), pd.DataFrame())
        assert "Auto-generated fix for:" in result.pandas_fix

    def test_sql_dangerous_drop_rejected(self):
        gen = FixGenerator()
        bad_sql = self._make_analyzer_result(sql_fix="DROP TABLE sales")
        result = gen.generate(bad_sql, pd.DataFrame())
        assert result.sql_fix_valid is False

    def test_sql_delete_allowed_for_duplicate_fix(self):
        """DELETE FROM is allowed when check is a duplicate check."""
        gen = FixGenerator()
        ok = self._make_analyzer_result(
            check_name="duplicate_check",
            sql_fix="DELETE FROM sales WHERE rowid NOT IN (SELECT MIN(rowid) FROM sales GROUP BY id)",
        )
        result = gen.generate(ok, pd.DataFrame())
        assert result.sql_fix_valid is True


# ── ConfidenceEngine ──────────────────────────────────────────────────────────

class TestConfidenceEngine:
    """Verify composite confidence scoring logic."""

    def test_perfect_fix_scores_high(self):
        eng = ConfidenceEngine()
        check = _make_check_result(severity="medium")
        score = eng.score("df['email'] = df['email'].fillna('x@x.com')", check, 100.0)
        assert score >= 70.0

    def test_zero_improvement_scores_low(self):
        eng = ConfidenceEngine()
        check = _make_check_result(severity="high")
        score = eng.score("df['email'] = df['email']", check, 0.0)
        assert score < 50.0

    def test_invalid_syntax_scores_zero(self):
        eng = ConfidenceEngine()
        check = _make_check_result(severity="low")
        score = eng.score("df['email'] = df['email'..fillna(0)", check, 100.0)
        assert score == 0.0

    def test_score_clamped_between_0_and_100(self):
        eng = ConfidenceEngine()
        check = _make_check_result(severity="low")
        score = eng.score("df['x'] = 1", check, 50.0)
        assert 0.0 <= score <= 100.0

    def test_critical_severity_penalty_applies(self):
        eng = ConfidenceEngine()
        critical = _make_check_result(severity="critical")
        medium = _make_check_result(severity="medium")
        code = "df['email'] = df['email'].fillna('x@x.com')"
        # Partial fix on critical should be penalised more
        score_c = eng.score(code, critical, 80.0)
        score_m = eng.score(code, medium, 80.0)
        assert score_c <= score_m
