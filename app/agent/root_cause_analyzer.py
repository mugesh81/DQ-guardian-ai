"""DQ Guardian AI Root Cause Analyzer.

Diagnoses validation failures using the Groq API (llama-3.3-70b-versatile)
and provides structured root causes and fixing templates.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd
import requests

from app.agent.validator import CheckResult

# Set up logging
logger = logging.getLogger("root_cause_analyzer")


@dataclass
class RootCauseResult:
    """Dataclass holding detailed diagnosis and proposed fix code for a failed check."""

    check_name: str
    root_cause: str
    business_impact: str
    confidence_score: float
    recommended_fix: str
    pandas_fix: str
    sql_fix: str
    is_fallback: bool  # True if rule-based fallback was utilized
    model_used: str


class RootCauseAnalyzer:
    """Uses Groq LLMs or local rule-based heuristics to diagnose data quality issues."""

    PRIMARY_MODEL = "llama-3.3-70b-versatile"
    FALLBACK_MODEL = "llama-3.1-8b-instant"
    GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def analyze(self, check_result: CheckResult, df: pd.DataFrame) -> RootCauseResult:
        """Diagnose a validation failure and propose fixes.

        Args:
            check_result: The failure description object.
            df: The dataframe being analyzed.

        Returns:
            RootCauseResult.
        """
        logger.info(f"Analyzing root cause for check '{check_result.check_name}' on column '{check_result.column}'")

        # Build context
        column = check_result.column
        stats = check_result.column_stats
        
        # Build markdown table of bad rows
        bad_rows = check_result.sample_bad_rows
        markdown_table = ""
        if bad_rows:
            headers = list(bad_rows[0].keys())
            markdown_table += "| " + " | ".join(headers) + " |\n"
            markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for row in bad_rows[:10]:
                vals = [str(row.get(h, "")) for h in headers]
                markdown_table += "| " + " | ".join(vals) + " |\n"
        else:
            markdown_table = "No sample bad rows available."

        # Prompt building
        system_prompt = "You are a senior data engineer specializing in data quality. You respond ONLY with valid JSON."
        
        user_prompt = f"""
Analyze the following validation check failure:
- Check Name: {check_result.check_name}
- Target Column: {column}
- Severity: {check_result.severity}
- Failure Count: {check_result.failure_count} out of {check_result.total_count} ({check_result.failure_percentage}%)

Column Statistics:
- Null Count: {stats.get('null_count', 0)}
- Unique Count: {stats.get('unique_count', 0)}
- Mean: {stats.get('mean')}
- Std Dev: {stats.get('std')}

Sample Failed Rows:
{markdown_table}

Identify the root cause of this failure and write a Python Pandas repair code snippet AND a SQL update statement to resolve it.
IMPORTANT: The Pandas script must expect the DataFrame to be loaded in a variable named 'df'. The script MUST modify the DataFrame 'df' in-place (e.g. df['{column}'] = ...) and MUST NOT do any imports.

You MUST respond with a single JSON object. Do not include markdown code block formatting (like ```json) in your final output. Ensure the keys and values match this schema:
{{
  "root_cause": "2-3 sentence explanation of the failure",
  "business_impact": "1 sentence describing the business risk of this bad data",
  "confidence_score": 0.95,
  "recommended_fix": "plain English description of how to resolve it",
  "pandas_fix": "df['{column}'] = df['{column}'].fillna(df['{column}'].mean())",
  "sql_fix": "UPDATE sales SET {column} = (SELECT AVG({column}) FROM sales) WHERE {column} IS NULL"
}}
"""

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY environment variable not set. Falling back to rule-based heuristics.")
            return self._rule_based_fallback(check_result)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Try Primary Model
        try:
            return self._call_groq_api(
                headers=headers,
                model=self.PRIMARY_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                check_name=check_result.check_name,
                column=column
            )
        except Exception as e:
            logger.warning(f"Primary model query failed: {e}. Retrying with fallback model...")
            
            # If HTTP 429 (rate limit), sleep for 60s
            if "429" in str(e):
                logger.warning("HTTP 429 Rate Limit hit. Waiting 1 seconds before calling fallback model...")
                time.sleep(1)
                
            # Try Fallback Model
            try:
                return self._call_groq_api(
                    headers=headers,
                    model=self.FALLBACK_MODEL,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    check_name=check_result.check_name,
                    column=column
                )
            except Exception as e2:
                logger.error(f"Fallback model query also failed: {e2}. Defaulting to rule-based fallback.")
                return self._rule_based_fallback(check_result)

    def _call_groq_api(
        self,
        headers: Dict[str, str],
        model: str,
        system_prompt: str,
        user_prompt: str,
        check_name: str,
        column: str
    ) -> RootCauseResult:
        """Performs HTTP POST request to Groq API and parses the JSON response.

        Args:
            headers: Authorization headers.
            model: Model name string.
            system_prompt: System context instructions.
            user_prompt: Input query instructions.
            check_name: Validation check identifier.
            column: Target dataset column.

        Returns:
            RootCauseResult object.
        """
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(self.GROQ_ENDPOINT, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 429:
            raise Exception("HTTP 429: Rate Limit Exceeded")
        elif response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        res_json = response.json()
        raw_content = res_json["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if LLM wraps JSON in ```json ... ```
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_content).strip()
        try:
            parsed_res = json.loads(cleaned)
        except json.JSONDecodeError as parse_err:
            logger.warning(f"JSON parse failed for model '{model}': {parse_err}. Falling back to rule-based.")
            raise Exception(f"JSON decode error: {parse_err}")

        return RootCauseResult(
            check_name=check_name,
            root_cause=parsed_res.get("root_cause", "Data quality threshold breach."),
            business_impact=parsed_res.get("business_impact", "Potential analytical inaccuracies."),
            confidence_score=float(parsed_res.get("confidence_score", 0.7)),
            recommended_fix=parsed_res.get("recommended_fix", "Review invalid records manually."),
            pandas_fix=parsed_res.get("pandas_fix", f"# No pandas fix code defined"),
            sql_fix=parsed_res.get("sql_fix", f"-- No SQL fix code defined"),
            is_fallback=False,
            model_used=model
        )

    def _rule_based_fallback(self, check_result: CheckResult) -> RootCauseResult:
        """Provides local, deterministic fallback logic covering all 12 check types."""
        logger.info(f"Applying local rule-based fallback logic for check: {check_result.check_name}")

        col = check_result.column
        name = check_result.check_name.lower()

        # Comprehensive template map for all 12 check types
        FALLBACK_TEMPLATES = {
            "null": (
                f"Required field '{col}' contains missing or empty values.",
                "System metrics might use invalid values leading to computation errors.",
                "Impute with default values or placeholders.",
                f"df['{col}'] = df['{col}'].fillna('MISSING')",
                f"UPDATE sales SET {col} = 'MISSING' WHERE {col} IS NULL;"
            ),
            "unique": (
                f"Duplicate primary key values detected in column '{col}'.",
                "Duplicate records cause double-counting in aggregations.",
                "Remove duplicates or assign new unique IDs.",
                f"df = df.drop_duplicates(subset=['{col}'], keep='first').reset_index(drop=True)",
                f"DELETE FROM sales WHERE rowid NOT IN (SELECT MIN(rowid) FROM sales GROUP BY {col});"
            ),
            "duplicate": (
                f"Repeated records found in column '{col}', violating uniqueness constraints.",
                "Repeated data rows skew analytical results and dashboards.",
                "Deduplicate using drop_duplicates().",
                f"df = df.drop_duplicates(subset=['{col}'], keep='first').reset_index(drop=True)",
                f"DELETE FROM sales WHERE rowid NOT IN (SELECT MIN(rowid) FROM sales GROUP BY {col});"
            ),
            "range": (
                f"Numeric values in '{col}' fall outside expected range constraints.",
                "Out-of-range values cause financial reporting inaccuracies.",
                "Clip or flag out-of-range values.",
                f"df['{col}'] = df['{col}'].clip(lower=0.0, upper=1000000.0)",
                f"UPDATE sales SET {col} = 0.0 WHERE {col} < 0.0;\nUPDATE sales SET {col} = 1000000.0 WHERE {col} > 1000000.0;"
            ),
            "regex": (
                f"Values in '{col}' are malformed or do not match the required pattern.",
                "Invalid format data corrupts downstream string processing.",
                "Strip whitespace and reformat to standard pattern.",
                f"df['{col}'] = df['{col}'].fillna('').astype(str).str.strip()",
                f"UPDATE sales SET {col} = TRIM({col});"
            ),
            "datatype": (
                f"Column '{col}' has incorrect data type or contains unparseable values.",
                "Wrong types cause runtime errors in numeric computations.",
                "Cast using pd.to_numeric() or pd.to_datetime().",
                f"df['{col}'] = pd.to_numeric(df['{col}'], errors='coerce')",
                f"-- Ensure column is stored as the correct numeric type"
            ),
            "date_validation": (
                f"Date values in '{col}' are in wrong format or unparseable.",
                "Invalid dates prevent time-series analysis.",
                "Parse with pd.to_datetime(errors='coerce').",
                f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce').dt.strftime('%Y-%m-%d')",
                f"UPDATE sales SET {col} = NULL WHERE TRY_CAST({col} AS DATE) IS NULL;"
            ),
            "future": (
                f"Order timestamps in '{col}' lie in the future.",
                "Future dates invalidate historical trend analysis.",
                "Filter or cap dates exceeding today.",
                f"dates = pd.to_datetime(df['{col}'], errors='coerce')\ndf.loc[dates > pd.Timestamp.now(), '{col}'] = pd.Timestamp.now().strftime('%Y-%m-%d')",
                f"UPDATE sales SET {col} = CURRENT_DATE WHERE {col} > CURRENT_DATE;"
            ),
            "outlier": (
                f"Statistical outliers detected in '{col}' via Z-score analysis.",
                "Extreme outliers skew means, totals, and model training.",
                "Review and cap extreme values using IQR or Z-score.",
                f"mean = df['{col}'].mean(); std = df['{col}'].std()\ndf['{col}'] = df['{col}'].clip(lower=mean - 3*std, upper=mean + 3*std)",
                f"-- Review and update outlier rows manually"
            ),
            "row_count": (
                f"Dataset has unexpected row count.",
                "Incomplete data pipelines produce wrong business summaries.",
                "Verify the data pipeline completeness and retry.",
                f"# Manual pipeline verification required",
                f"-- Check upstream data source for missing partitions"
            ),
            "column_existence": (
                f"Expected column '{col}' is missing from the dataset.",
                "Missing columns cause KeyErrors in all downstream processing.",
                "Check upstream data source schema changes.",
                f"if '{col}' not in df.columns:\n    df['{col}'] = None",
                f"ALTER TABLE sales ADD COLUMN {col} TEXT;"
            ),
            "negative": (
                f"Negative values present in non-negative column '{col}'.",
                "Negative values in revenue/quantity fields distort financial reports.",
                "Apply abs() or set negatives to NaN for review.",
                f"df['{col}'] = df['{col}'].apply(lambda x: abs(x) if x < 0 else x)",
                f"UPDATE sales SET {col} = ABS({col}) WHERE {col} < 0;"
            ),
        }

        # Match template by keyword in check name
        template_key = None
        for key in FALLBACK_TEMPLATES:
            if key in name:
                template_key = key
                break

        if template_key:
            root_cause, impact, recommended, pandas_fix, sql_fix = FALLBACK_TEMPLATES[template_key]
            confidence = 0.55
        else:
            root_cause = f"Local validator flagged records violating rules on '{col}'."
            impact = "System metrics might use invalid values leading to computation errors."
            recommended = "Apply default cleanup transformations based on type constraints."
            pandas_fix = f"# Manual inspection needed for '{col}'"
            sql_fix = f"-- Manual inspection needed for '{col}'"
            confidence = 0.40

        return RootCauseResult(
            check_name=check_result.check_name,
            root_cause=root_cause,
            business_impact=impact,
            confidence_score=confidence,
            recommended_fix=recommended,
            pandas_fix=pandas_fix,
            sql_fix=sql_fix,
            is_fallback=True,
            model_used="rule-based-fallback"
        )
