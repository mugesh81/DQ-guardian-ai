"""DQ Guardian AI Validator Engine.

This module contains a 100% custom data quality validator built with Pandas and NumPy.
No external validation frameworks (like Great Expectations) are used.
"""

import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import numpy as np
import pandas as pd
import yaml

# Set up logging
logger = logging.getLogger("validator_engine")


@dataclass
class CheckResult:
    """Dataclass holding validation results for a single check."""

    check_name: str
    column: str
    status: str  # "PASS", "FAIL", or "ERROR"
    failure_count: int
    total_count: int
    failure_percentage: float
    severity: str  # "critical", "high", "medium", "low"
    sample_bad_rows: List[Dict[str, Any]] = field(default_factory=list)
    column_stats: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


@dataclass
class ValidationReport:
    """Dataclass holding the aggregated validation report for a full dataset run."""

    total_checks: int
    passed: int
    failed: int
    success_rate: float
    results: List[CheckResult]
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class BaseCheck(ABC):
    """Abstract base class for all validation checks."""

    def __init__(
        self,
        name: str,
        column: str,
        severity: str = "medium",
        params: Optional[Dict[str, Any]] = None,
        description: str = "",
    ):
        self.name = name
        self.column = column
        self.severity = severity.lower()
        self.params = params or {}
        self.description = description

    @abstractmethod
    def run(self, df: pd.DataFrame) -> CheckResult:
        """Run the check against the given pandas DataFrame.

        Args:
            df: The DataFrame to validate.

        Returns:
            A CheckResult instance detailing the output of this validation.
        """
        pass

    def _get_column_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate helper statistics for the target column.

        Args:
            df: The input DataFrame.

        Returns:
            A dictionary of summary statistics.
        """
        stats: Dict[str, Any] = {
            "null_count": 0,
            "unique_count": 0,
            "mean": None,
            "std": None,
        }

        if self.column not in df.columns:
            return stats

        col_data = df[self.column]
        stats["null_count"] = int(col_data.isna().sum())
        
        try:
            stats["unique_count"] = int(col_data.nunique())
        except Exception:
            pass

        try:
            numeric_data = pd.to_numeric(col_data, errors="coerce")
            non_null_numeric = numeric_data.dropna()
            if not non_null_numeric.empty:
                stats["mean"] = float(non_null_numeric.mean())
                stats["std"] = float(non_null_numeric.std()) if len(non_null_numeric) > 1 else 0.0
        except Exception:
            pass

        return stats

    def _create_result(
        self,
        df: pd.DataFrame,
        failed_mask: pd.Series,
        status: str = "PASS",
        error_msg: Optional[str] = None,
    ) -> CheckResult:
        """Helper to compile check results from a failed boolean mask series.

        Args:
            df: The source DataFrame.
            failed_mask: Boolean series indicating which rows failed the check.
            status: Initial evaluation status.
            error_msg: Logged message if an exception was caught.

        Returns:
            CheckResult filled with failure counts, stats, and bad rows.
        """
        total = len(df)
        
        if error_msg:
            return CheckResult(
                check_name=self.name,
                column=self.column,
                status="ERROR",
                failure_count=0,
                total_count=total,
                failure_percentage=0.0,
                severity=self.severity,
                sample_bad_rows=[],
                column_stats=self._get_column_stats(df),
            )

        fail_count = int(failed_mask.sum())
        fail_pct = float(round((fail_count / total) * 100, 2)) if total > 0 else 0.0
        final_status = "FAIL" if fail_count > 0 else "PASS"

        # Capture sample bad rows
        sample_rows = []
        if fail_count > 0:
            bad_indices = df[failed_mask].index[:10]
            # Replace NaNs with None for JSON serialization compatibility
            sample_df = df.loc[bad_indices].copy()
            # Workaround for pandas object replace to avoid warning
            sample_df = sample_df.replace({np.nan: None})
            sample_rows = sample_df.to_dict(orient="records")

        return CheckResult(
            check_name=self.name,
            column=self.column,
            status=final_status,
            failure_count=fail_count,
            total_count=total,
            failure_percentage=fail_pct,
            severity=self.severity,
            sample_bad_rows=sample_rows,
            column_stats=self._get_column_stats(df),
        )


class NullCheck(BaseCheck):
    """Checks if a column contains null/NaN values or empty whitespace strings."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running NullCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            col_data = df[self.column]
            # Flag actual nulls
            failed_mask = col_data.isna()
            
            # For string objects, flag empty strings or whitespace-only strings
            if col_data.dtype == "object":
                str_cleaned = col_data.astype(str).str.strip()
                empty_mask = (str_cleaned == "") | (str_cleaned == "None") | (str_cleaned == "nan")
                failed_mask = failed_mask | empty_mask
                
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing NullCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class UniqueCheck(BaseCheck):
    """Verifies that all values in the column are unique (no duplicates)."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running UniqueCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            col_data = df[self.column]
            # All duplicate instances are marked as failures
            failed_mask = col_data.duplicated(keep=False)
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing UniqueCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class DuplicateCheck(BaseCheck):
    """Checks for duplicate records based on the target column."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running DuplicateCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            col_data = df[self.column]
            # Marks all duplicates (excluding the first occurrence depending on config, but keep=False finds all violating rows)
            failed_mask = col_data.duplicated(keep="first")
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing DuplicateCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class RangeCheck(BaseCheck):
    """Checks if numeric values fall inside an inclusive min/max range."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running RangeCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            min_val = self.params.get("min")
            max_val = self.params.get("max")
            
            col_numeric = pd.to_numeric(df[self.column], errors="coerce")
            
            # Treat parsing failure as an error/failure
            failed_mask = col_numeric.isna()
            
            if min_val is not None:
                failed_mask = failed_mask | (col_numeric < min_val)
            if max_val is not None:
                failed_mask = failed_mask | (col_numeric > max_val)
                
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing RangeCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class RegexCheck(BaseCheck):
    """Validates string compliance against a regular expression pattern."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running RegexCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            pattern = self.params.get("pattern", ".*")
            compiled_regex = re.compile(pattern)
            
            col_str = df[self.column].astype(str)
            # Null values fail regex validations
            null_mask = df[self.column].isna()
            
            match_mask = col_str.apply(lambda x: bool(compiled_regex.match(x)) if x != "None" else False)
            failed_mask = (~match_mask) | null_mask
            
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing RegexCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class DatatypeCheck(BaseCheck):
    """Ensures data types match expectations (e.g. float64, int64)."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running DatatypeCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            expected_type = self.params.get("expected_type", "object")
            col_data = df[self.column]
            
            # If dtype matches exactly, we pass. Otherwise, find values that cannot be cast.
            if str(col_data.dtype) == expected_type:
                return self._create_result(df, pd.Series(False, index=df.index))
                
            # Check row-level casting compatibility
            failed_mask = pd.Series(False, index=df.index)
            if expected_type in ("float64", "int64"):
                converted = pd.to_numeric(col_data, errors="coerce")
                # Values that turned into NaN but were not originally NaN are failures
                failed_mask = converted.isna() & col_data.notna()
            elif expected_type == "datetime64[ns]":
                converted = pd.to_datetime(col_data, errors="coerce")
                failed_mask = converted.isna() & col_data.notna()
            elif expected_type == "bool":
                # Check for standard boolean representations
                valid_bools = {True, False, 1, 0, "1", "0", "True", "False", "true", "false"}
                failed_mask = col_data.apply(lambda x: x not in valid_bools if x is not None else True)
                
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing DatatypeCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class DateValidationCheck(BaseCheck):
    """Checks date string matching standard parsing structures."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running DateValidationCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            date_format = self.params.get("format", "%Y-%m-%d")
            col_data = df[self.column]
            
            def is_invalid_date(val: Any) -> bool:
                if pd.isna(val) or val is None:
                    return True
                try:
                    datetime.strptime(str(val), date_format)
                    return False
                except ValueError:
                    return True
                    
            failed_mask = col_data.apply(is_invalid_date)
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing DateValidationCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class FutureDateCheck(BaseCheck):
    """Prevents future timestamps (newer than today's date)."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running FutureDateCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")

            col_data = df[self.column]
            # Coerce to datetime; timezone-naive to avoid comparison issues
            parsed_dates = pd.to_datetime(col_data, errors="coerce", utc=False)
            # Normalize to remove time component and stay timezone-naive
            now_ts = pd.Timestamp.now().normalize()

            # Only flag valid parsed dates that are strictly in the future
            failed_mask = parsed_dates > now_ts

            # If dates couldn't be parsed but source value is not null, flag those too
            failed_mask = failed_mask | (parsed_dates.isna() & col_data.notna())
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing FutureDateCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class OutlierDetectionCheck(BaseCheck):
    """Detects outliers using standard Z-score analysis (threshold=3)."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running OutlierDetectionCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            threshold = self.params.get("threshold", 3.0)
            col_numeric = pd.to_numeric(df[self.column], errors="coerce")
            
            mean = col_numeric.mean()
            std = col_numeric.std()
            
            if pd.isna(mean) or pd.isna(std) or std == 0:
                failed_mask = pd.Series(False, index=df.index)
            else:
                z_scores = (col_numeric - mean).abs() / std
                failed_mask = z_scores > threshold
                
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing OutlierDetectionCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class RowCountCheck(BaseCheck):
    """Dataset-level validation matching target record size ranges."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running RowCountCheck on DataFrame")
        try:
            min_rows = self.params.get("min_rows", 1)
            max_rows = self.params.get("max_rows", 1000000)
            
            total_rows = len(df)
            passed = min_rows <= total_rows <= max_rows
            
            # Since this is a table-level check, if it fails, flag the whole table as bad.
            failed_mask = pd.Series(not passed, index=df.index)
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing RowCountCheck: {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class ColumnExistenceCheck(BaseCheck):
    """Table-level validation verifying target columns exist."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running ColumnExistenceCheck for column: '{self.column}'")
        try:
            exists = self.column in df.columns
            # If not present, all rows fail the assertion
            failed_mask = pd.Series(not exists, index=df.index)
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing ColumnExistenceCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class NegativeValueCheck(BaseCheck):
    """Flags negative values in numerical columns."""

    def run(self, df: pd.DataFrame) -> CheckResult:
        logger.info(f"Running NegativeValueCheck on column: '{self.column}'")
        try:
            if self.column not in df.columns:
                return self._create_result(df, pd.Series(False, index=df.index), status="ERROR")
            
            col_numeric = pd.to_numeric(df[self.column], errors="coerce")
            failed_mask = col_numeric < 0.0
            
            return self._create_result(df, failed_mask)
        except Exception as e:
            logger.error(f"Error executing NegativeValueCheck on '{self.column}': {e}")
            return self._create_result(df, pd.Series(False, index=df.index), error_msg=str(e))


class CrossColumnCheck(BaseCheck):
    """Compares two columns per row using a configurable operator.

    Params (all in ``params`` dict):
        left_col  (str)  : Column whose value is on the LEFT of the comparison.
                           Defaults to ``self.column`` if omitted.
        right_col (str)  : Column whose value is on the RIGHT of the comparison.
        operator  (str)  : One of ``gt`` (>), ``gte`` (>=), ``lt`` (<),
                           ``lte`` (<=), ``eq`` (==), ``ne`` (!=).
        parse_dates (bool): If True, coerce both columns to datetime before
                           comparing (useful for date strings). Default False.

    Example YAML::

        - id: RULE_CC_01
          name: "end_after_start_check"
          column: "end_date"          # used as left_col and in CheckResult.column
          check_type: cross_column_check
          severity: high
          params:
            left_col: "end_date"
            right_col: "start_date"
            operator: "gt"
            parse_dates: true
          description: "end_date must be strictly after start_date"
    """

    _OPS = {
        "gt":  lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt":  lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq":  lambda a, b: a == b,
        "ne":  lambda a, b: a != b,
    }
    _OP_SYMBOLS = {
        "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "==", "ne": "!=",
    }

    def run(self, df: pd.DataFrame) -> CheckResult:
        left_col  = self.params.get("left_col",  self.column)
        right_col = self.params.get("right_col", "")
        operator  = self.params.get("operator",  "gt")
        parse_dates = bool(self.params.get("parse_dates", False))

        log_label = f"'{left_col}' {self._OP_SYMBOLS.get(operator, operator)} '{right_col}'"
        logger.info(f"Running CrossColumnCheck: {log_label}")

        # ── Validation guards ────────────────────────────────────────────────
        if not right_col:
            return self._create_result(
                df, pd.Series(False, index=df.index),
                error_msg="CrossColumnCheck: 'right_col' param is required.",
            )

        missing = [c for c in [left_col, right_col] if c not in df.columns]
        if missing:
            return self._create_result(
                df, pd.Series(False, index=df.index),
                error_msg=f"CrossColumnCheck: columns not found in DataFrame: {missing}",
            )

        op_fn = self._OPS.get(operator)
        if op_fn is None:
            return self._create_result(
                df, pd.Series(False, index=df.index),
                error_msg=(
                    f"CrossColumnCheck: unknown operator '{operator}'. "
                    "Use: gt, gte, lt, lte, eq, ne."
                ),
            )

        try:
            left_series  = df[left_col]
            right_series = df[right_col]

            if parse_dates:
                left_series  = pd.to_datetime(left_series,  errors="coerce", utc=False)
                right_series = pd.to_datetime(right_series, errors="coerce", utc=False)

            # Rows where either side is NaN/NaT → automatically fail
            left_null  = left_series.isna()
            right_null = right_series.isna()
            any_null   = left_null | right_null

            # Evaluate operator only where both sides have values
            condition_failed = pd.Series(False, index=df.index)
            valid_mask = ~any_null
            if valid_mask.any():
                comparison_result = op_fn(left_series[valid_mask], right_series[valid_mask])
                # Rows that FAIL the condition (condition_result is False)
                condition_failed[valid_mask] = ~comparison_result

            failed_mask = any_null | condition_failed

            # Override column label to show both columns clearly
            original_column = self.column
            self.column = f"{left_col} {self._OP_SYMBOLS.get(operator, operator)} {right_col}"
            result = self._create_result(df, failed_mask)
            self.column = original_column  # restore for reuse
            return result

        except Exception as exc:
            logger.error(f"Error executing CrossColumnCheck ({log_label}): {exc}")
            return self._create_result(
                df, pd.Series(False, index=df.index), error_msg=str(exc)
            )


class ValidationEngine:
    """Manages parsing rules YAML and running checks against DataFrames."""

    # Map rule names in YAML config to classes (all spec names + common aliases)
    RULE_MAPPING: Dict[str, Type[BaseCheck]] = {
        # Primary spec names (used in sales_rules.yaml)
        "null_check": NullCheck,
        "unique_check": UniqueCheck,
        "duplicate_check": DuplicateCheck,
        "range_check": RangeCheck,
        "regex_check": RegexCheck,
        "datatype_check": DatatypeCheck,
        "date_validation": DateValidationCheck,
        "future_date_check": FutureDateCheck,
        "outlier_detection": OutlierDetectionCheck,
        "row_count": RowCountCheck,
        "column_existence": ColumnExistenceCheck,
        "negative_value": NegativeValueCheck,
        # Cross-column comparison check
        "cross_column_check": CrossColumnCheck,
        # Legacy / alternate names for backward compatibility
        "outlier_check": OutlierDetectionCheck,
        "row_count_check": RowCountCheck,
        "column_existence_check": ColumnExistenceCheck,
        "negative_value_check": NegativeValueCheck,
    }

    def __init__(self):
        self.checks: List[BaseCheck] = []

    def load_rules_from_yaml(self, rules_path: Path) -> List[BaseCheck]:
        """Reads validation rules from a YAML configuration file.

        Args:
            rules_path: Path to the rules configuration YAML file.

        Returns:
            A list of instantiated BaseCheck sub-classes.
        """
        logger.info(f"Loading rules configuration from {rules_path}")
        self.checks = []
        
        if not rules_path.exists():
            logger.warning(f"Rules path does not exist: {rules_path}")
            return self.checks

        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                
            return self.load_rules_from_dict(config or {})
        except Exception as e:
            logger.exception(f"Failed to parse rule YAML from: {rules_path}. Error: {e}")
            
        return self.checks

    def load_rules_from_dict(self, config: Dict[str, Any]) -> List[BaseCheck]:
        """Load validation rules from an in-memory dict (same schema as YAML).

        Accepts the output of ``auto_rules_generator.generate_rules_for_dataframe``
        directly — no file I/O needed.

        Args:
            config: Dict with key ``"rules"`` containing a list of rule dicts.

        Returns:
            A list of instantiated BaseCheck sub-classes.
        """
        self.checks = []
        rules_list = config.get("rules", [])

        for r in rules_list:
            check_type = r.get("check_type")
            check_class = self.RULE_MAPPING.get(check_type)

            if not check_class:
                logger.warning(
                    f"Skipping unknown check_type: '{check_type}' in rule ID: {r.get('id')}"
                )
                continue

            check_inst = check_class(
                name=r.get("name", f"check_{r.get('id')}"),
                column=r.get("column", ""),
                severity=r.get("severity", "medium"),
                params=r.get("params", {}),
                description=r.get("description", ""),
            )
            self.checks.append(check_inst)

        logger.info(f"Loaded {len(self.checks)} checks from rules dict.")
        return self.checks

    def run_all_checks(self, df: pd.DataFrame, filename: str = "") -> ValidationReport:
        """Executes all loaded checks on the DataFrame.

        Args:
            df: The DataFrame to analyze.
            filename: Optional source file name description for reporting.

        Returns:
            Aggregated ValidationReport data object.
        """
        logger.info(f"Running all validation checks ({len(self.checks)}) on dataset...")
        results: List[CheckResult] = []
        passed = 0
        failed = 0

        for check in self.checks:
            try:
                res = check.run(df)
                results.append(res)
                if res.status == "PASS":
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.exception(f"Unexpected crash in check runner for '{check.name}': {e}")
                err_res = CheckResult(
                    check_name=check.name,
                    column=check.column,
                    status="ERROR",
                    failure_count=0,
                    total_count=len(df),
                    failure_percentage=0.0,
                    severity=check.severity,
                )
                results.append(err_res)
                failed += 1

        total = len(self.checks)
        success_rate = float(round((passed / total) * 100, 2)) if total > 0 else 100.0

        return ValidationReport(
            total_checks=total,
            passed=passed,
            failed=failed,
            success_rate=success_rate,
            results=results,
            filename=filename,
        )

    def run_single_check(self, df: pd.DataFrame, check_name: str) -> CheckResult:
        """Executes a single check in the loaded list by its specific name.

        Args:
            df: DataFrame to validate.
            check_name: String name matching rule.

        Returns:
            CheckResult.
        """
        for check in self.checks:
            if check.name == check_name:
                return check.run(df)
                
        raise ValueError(f"No loaded check matches name: '{check_name}'")
