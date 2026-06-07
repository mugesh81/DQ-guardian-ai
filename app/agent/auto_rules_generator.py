"""DQ Guardian AI — Automatic Rules Generator.

Inspects an uploaded DataFrame and produces a YAML rules dict
using Groq AI (with heuristic fallback) — no pre-existing rules file needed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

# Load .env so GROQ_API_KEY is visible in standalone contexts
try:
    from dotenv import load_dotenv as _ld
    _ld(Path(__file__).parent.parent.parent / ".env", override=False)
except ImportError:
    pass

logger = logging.getLogger("auto_rules_generator")

# ──────────────────────────────────────────────────────────────────────────────
# Column-type heuristics (used by both AI prompt and fallback)
# ──────────────────────────────────────────────────────────────────────────────

_EMAIL_HINTS  = {"email", "mail", "e_mail", "emailaddress", "email_address"}
_PHONE_HINTS  = {"phone", "mobile", "tel", "telephone", "contact", "cell"}
_DATE_HINTS   = {"date", "dob", "birth", "created", "updated", "joined",
                  "join_date", "order_date", "timestamp", "datetime"}
_ID_HINTS     = {"id", "_id", "code", "key", "uuid", "ref", "number"}
_NAME_HINTS   = {"name", "firstname", "lastname", "fullname", "username"}
_SALARY_HINTS = {"salary", "income", "wage", "pay", "revenue", "amount",
                  "price", "cost", "fee", "total", "balance"}
_AGE_HINTS    = {"age", "years", "yrs"}
_QTY_HINTS    = {"quantity", "qty", "count", "units", "stock", "inventory"}
_DEPT_HINTS   = {"department", "dept", "division", "unit", "team", "category",
                  "section", "group", "type", "status", "region"}


def _col_lower(col: str) -> str:
    return col.lower().replace(" ", "_").replace("-", "_")


def _is_numeric(series: pd.Series) -> bool:
    return pd.to_numeric(series, errors="coerce").notna().mean() > 0.7


def _is_date_col(series: pd.Series) -> bool:
    sample = series.dropna().head(20).astype(str)
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() > 0.6


# ──────────────────────────────────────────────────────────────────────────────
# DataFrame profiling
# ──────────────────────────────────────────────────────────────────────────────

def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Return a lightweight profile dict for an uploaded DataFrame."""
    profile: Dict[str, Any] = {}
    for col in df.columns:
        series = df[col]
        null_pct = round(series.isna().mean() * 100, 1)
        unique_count = series.nunique()
        dtype_str = str(series.dtype)

        col_type = "text"
        if _is_numeric(series):
            col_type = "numeric"
        elif _is_date_col(series):
            col_type = "date"

        profile[col] = {
            "dtype": dtype_str,
            "inferred_type": col_type,
            "null_pct": null_pct,
            "unique_count": int(unique_count),
            "sample_values": series.dropna().head(3).astype(str).tolist(),
        }
    return profile


# ──────────────────────────────────────────────────────────────────────────────
# Heuristic rule builder (no LLM needed)
# ──────────────────────────────────────────────────────────────────────────────

def _build_heuristic_rules(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Build a sensible set of validation rules purely from column inspection."""
    rules: List[Dict[str, Any]] = []
    rule_id = 1

    def _add(name: str, col: str, check_type: str,
             severity: str, params: Optional[Dict] = None, desc: str = "") -> None:
        nonlocal rule_id
        entry: Dict[str, Any] = {
            "id": f"AUTO_{rule_id:02d}",
            "name": name,
            "column": col,
            "check_type": check_type,
            "severity": severity,
            "description": desc or f"Auto-generated {check_type} for column '{col}'",
        }
        if params:
            entry["params"] = params
        rules.append(entry)
        rule_id += 1

    for col in df.columns:
        cl = _col_lower(col)
        series = df[col]
        is_num = _is_numeric(series)
        is_date = _is_date_col(series)

        # 1. Null check — always add for every column
        null_pct = series.isna().mean()
        if null_pct > 0 or any(h in cl for h in _EMAIL_HINTS | _ID_HINTS | _NAME_HINTS | _PHONE_HINTS):
            severity = "critical" if any(h in cl for h in _ID_HINTS) else (
                       "high"     if any(h in cl for h in _EMAIL_HINTS | _PHONE_HINTS | _NAME_HINTS) else "medium")
            _add(f"{col}_null_check", col, "null_check", severity,
                 desc=f"Column '{col}' must not contain null or empty values")

        # 2. Unique / duplicate check — for ID-like columns
        if any(h in cl for h in _ID_HINTS) or series.nunique() == len(series.dropna()):
            _add(f"{col}_unique_check", col, "unique_check", "critical",
                 desc=f"Column '{col}' must contain unique values")
            _add(f"{col}_duplicate_check", col, "duplicate_check", "high",
                 desc=f"Column '{col}' must not have duplicate rows")

        # 3. Email regex check
        if any(h in cl for h in _EMAIL_HINTS):
            _add(f"{col}_email_format", col, "regex_check", "high",
                 params={"pattern": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"},
                 desc=f"Column '{col}' must match email format")

        # 4. Phone regex check
        elif any(h in cl for h in _PHONE_HINTS):
            _add(f"{col}_phone_format", col, "regex_check", "medium",
                 params={"pattern": r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$"},
                 desc=f"Column '{col}' must match phone number format")

        # 5. Date validation
        if is_date or any(h in cl for h in _DATE_HINTS):
            _add(f"{col}_date_format", col, "date_validation", "high",
                 params={"format": "%Y-%m-%d"},
                 desc=f"Column '{col}' must be a valid YYYY-MM-DD date")
            _add(f"{col}_future_date", col, "future_date_check", "medium",
                 desc=f"Column '{col}' must not be a future date")

        # 6. Numeric range checks
        if is_num and not is_date:
            numeric = pd.to_numeric(series, errors="coerce").dropna()
            if len(numeric) > 0:
                # Salary / revenue columns — must be positive, reasonable upper bound
                if any(h in cl for h in _SALARY_HINTS):
                    _add(f"{col}_range_check", col, "range_check", "high",
                         params={"min": 0.0, "max": float(numeric.quantile(0.999) * 10)},
                         desc=f"Column '{col}' must be within a realistic salary/revenue range")
                    _add(f"{col}_negative_check", col, "negative_value", "high",
                         desc=f"Column '{col}' must not contain negative values")

                # Age columns
                elif any(h in cl for h in _AGE_HINTS):
                    _add(f"{col}_range_check", col, "range_check", "medium",
                         params={"min": 0, "max": 120},
                         desc=f"Column '{col}' (age) must be between 0 and 120")

                # Quantity columns
                elif any(h in cl for h in _QTY_HINTS):
                    _add(f"{col}_range_check", col, "range_check", "medium",
                         params={"min": 0, "max": 1_000_000},
                         desc=f"Column '{col}' must be a valid non-negative quantity")
                    _add(f"{col}_negative_check", col, "negative_value", "medium",
                         desc=f"Column '{col}' must not contain negative values")

                # Generic numeric outlier check
                else:
                    _add(f"{col}_outlier_check", col, "outlier_detection", "low",
                         params={"threshold": 3.0},
                         desc=f"Column '{col}' outlier detection (Z-score > 3)")

        # 7. Datatype check for clearly numeric columns
        if is_num and not is_date:
            _add(f"{col}_datatype_check", col, "datatype_check", "medium",
                 params={"expected_type": "float64"},
                 desc=f"Column '{col}' must be stored as a numeric type")

    return rules


# ──────────────────────────────────────────────────────────────────────────────
# AI-powered rule generation via Groq
# ──────────────────────────────────────────────────────────────────────────────

_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_PRIMARY_MODEL = "llama-3.3-70b-versatile"
_FALLBACK_MODEL = "llama-3.1-8b-instant"

_SYSTEM_PROMPT = (
    "You are a senior data quality engineer. You ONLY respond with valid JSON. "
    "Do NOT include markdown fences, comments, or explanations."
)

_SUPPORTED_CHECKS = (
    "null_check | unique_check | duplicate_check | range_check | regex_check | "
    "datatype_check | date_validation | future_date_check | outlier_detection | "
    "negative_value"
)


def _build_ai_prompt(df: pd.DataFrame, profile: Dict[str, Any]) -> str:
    col_summary = "\n".join(
        f"  - {col}: dtype={info['dtype']}, inferred={info['inferred_type']}, "
        f"null%={info['null_pct']}, unique={info['unique_count']}, "
        f"samples={info['sample_values']}"
        for col, info in profile.items()
    )
    return f"""
Dataset has {len(df)} rows and {len(df.columns)} columns:
{col_summary}

Generate comprehensive data validation rules for this dataset.
Return a JSON object with this EXACT structure:
{{
  "rules": [
    {{
      "id": "RULE_01",
      "name": "column_check_name",
      "column": "exact_column_name",
      "check_type": "{_SUPPORTED_CHECKS}",
      "severity": "critical|high|medium|low",
      "params": {{}},
      "description": "plain english description"
    }}
  ]
}}

Rules:
- Use check_type "null_check" for columns that should not be empty
- Use "unique_check" + "duplicate_check" for ID columns  
- Use "regex_check" with pattern "^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$" for email columns
- Use "regex_check" with pattern "^[+]?[0-9][0-9 .\\-]{6,14}[0-9]$" for phone columns
- Use "range_check" with params min/max for numeric columns
- Use "date_validation" with params format="%Y-%m-%d" for date columns
- Use "future_date_check" for date columns that should not be future dates
- Use "negative_value" for columns that must be non-negative (salary, age, qty)
- Use "outlier_detection" with params threshold=3.0 for general numeric columns
- Use "datatype_check" with params expected_type="float64" for numeric columns
- Cover ALL columns with at least one check
- column name MUST exactly match one of: {list(df.columns)}
""".strip()


def _call_groq(prompt: str, api_key: str, model: str) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(
        _GROQ_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=40,
    )
    if resp.status_code == 429:
        raise RuntimeError("HTTP 429 rate limit")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    return json.loads(cleaned)


# ──────────────────────────────────────────────────────────────────────────────
# Safe regex overrides (replaces any broken AI-generated patterns)
# ──────────────────────────────────────────────────────────────────────────────

# These patterns are pre-tested and known to compile cleanly.
_SAFE_REGEX_OVERRIDES: Dict[str, str] = {
    "email":   r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    "phone":   r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
    "mobile":  r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
    "tel":     r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
}


def _sanitize_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate every regex_check rule's pattern. Replace broken ones with safe overrides."""
    for rule in rules:
        if rule.get("check_type") != "regex_check":
            continue
        params = rule.get("params") or {}
        pattern = params.get("pattern", "")
        col_lower = _col_lower(rule.get("column", ""))

        # Determine if the pattern is broken
        broken = False
        if not pattern:
            broken = True
        else:
            try:
                re.compile(pattern)
            except re.error:
                broken = True

        # If broken, look for a safe override
        if broken:
            for hint_key, safe_pat in _SAFE_REGEX_OVERRIDES.items():
                if hint_key in col_lower:
                    rule.setdefault("params", {})["pattern"] = safe_pat
                    logger.warning(
                        f"Replaced broken regex for col '{rule['column']}' with safe pattern."
                    )
                    break
            else:
                # No known override → use catch-all that always passes
                rule.setdefault("params", {})["pattern"] = r"^.*$"
                logger.warning(
                    f"No safe regex override for col '{rule['column']}'; using '.*'."
                )
        else:
            # Pattern compiles OK, but may still be wrong (e.g. AI used (2,) not {2,})
            # Quick sanity check: test a known-good email against email patterns
            for hint_key, safe_pat in _SAFE_REGEX_OVERRIDES.items():
                if hint_key in col_lower:
                    import re as _re
                    try:
                        compiled = _re.compile(pattern)
                        # Use hint-specific test values
                        test_val = "test@example.com" if "email" in hint_key else "9876543210"
                        if not compiled.match(test_val):
                            rule["params"]["pattern"] = safe_pat
                            logger.warning(
                                f"Pattern for '{rule['column']}' failed sanity test; replaced."
                            )
                    except re.error:
                        rule["params"]["pattern"] = safe_pat
                    break
    return rules


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_rules_for_dataframe(
    df: pd.DataFrame,
    use_ai: bool = True,
) -> Dict[str, Any]:
    """Generate a rules dict (same schema as YAML) for any uploaded DataFrame.

    Args:
        df:      The uploaded DataFrame to inspect.
        use_ai:  If True and GROQ_API_KEY is set, call Groq for smarter rules.

    Returns:
        A dict ``{"rules": [...]}`` ready to be passed to
        ``ValidationEngine.load_rules_from_dict()``.
    """
    profile = profile_dataframe(df)

    api_key = os.getenv("GROQ_API_KEY")
    if use_ai and api_key and api_key != "your_groq_api_key_here":
        logger.info("Calling Groq AI to generate validation rules…")
        prompt = _build_ai_prompt(df, profile)
        try:
            result = _call_groq(prompt, api_key, _PRIMARY_MODEL)
            rules = result.get("rules", [])
            if rules:
                logger.info(f"Groq AI generated {len(rules)} rules.")
                return {"rules": _sanitize_rules(rules)}
        except RuntimeError as e:
            if "429" in str(e):
                logger.warning("Rate limit hit, waiting 1s then trying fallback model…")
                time.sleep(1)
                try:
                    result = _call_groq(prompt, api_key, _FALLBACK_MODEL)
                    rules = result.get("rules", [])
                    if rules:
                        return {"rules": _sanitize_rules(rules)}
                except Exception as e2:
                    logger.warning(f"Fallback model also failed: {e2}. Using heuristics.")
            else:
                logger.warning(f"Groq AI failed: {e}. Using heuristics.")
        except Exception as exc:
            logger.warning(f"Unexpected AI error: {exc}. Using heuristics.")

    # Heuristic fallback
    logger.info("Generating heuristic validation rules from column inspection…")
    rules = _build_heuristic_rules(df)
    logger.info(f"Heuristic generator produced {len(rules)} rules.")
    return {"rules": _sanitize_rules(rules)}
