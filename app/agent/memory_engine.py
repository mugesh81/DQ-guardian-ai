"""DQ Guardian AI Memory Engine.

This module provides the database persistence layer using SQLite.
It stores execution histories, failure profiles, applied fixes, and acts as agent memory.
"""

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Set up logging
logger = logging.getLogger("memory_engine")

# Global lock for thread safety
db_lock = threading.Lock()


class MemoryEngine:
    """Manages SQLite3 operations for DQ Guardian AI."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initializes database and auto-creates required tables.

        Args:
            db_path: Path to database. If None, defaults to database/dq_guardian.db.
        """
        if db_path is None:
            # Set default path
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.db_dir = base_dir / "database"
            self.db_path = self.db_dir / "dq_guardian.db"
        else:
            self.db_path = Path(db_path)
            self.db_dir = self.db_path.parent

        # Auto-create directories
        self.db_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Database path set to: {self.db_path}")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes sqlite3 connection with dict-like Row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Creates the 5 core tables if they do not exist on the filesystem."""
        logger.info("Initializing SQLite database tables...")
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # TABLE 1: validation_runs
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS validation_runs (
                            id TEXT PRIMARY KEY,
                            timestamp TEXT,
                            filename TEXT,
                            total_rows INTEGER,
                            total_checks INTEGER,
                            passed_checks INTEGER,
                            failed_checks INTEGER,
                            success_rate REAL,
                            duration_seconds REAL,
                            iterations INTEGER
                        )
                    """)
                    
                    # TABLE 2: validation_failures
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS validation_failures (
                            id TEXT PRIMARY KEY,
                            run_id TEXT,
                            check_name TEXT,
                            column_name TEXT,
                            check_type TEXT,
                            failure_count INTEGER,
                            total_count INTEGER,
                            failure_percentage REAL,
                            severity TEXT,
                            sample_bad_rows_json TEXT,
                            timestamp TEXT,
                            FOREIGN KEY(run_id) REFERENCES validation_runs(id)
                        )
                    """)
                    
                    # TABLE 3: generated_fixes
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS generated_fixes (
                            id TEXT PRIMARY KEY,
                            failure_id TEXT,
                            run_id TEXT,
                            pandas_fix TEXT,
                            sql_fix TEXT,
                            confidence_score REAL,
                            fix_valid INTEGER,
                            was_applied INTEGER,
                            improvement_percentage REAL,
                            timestamp TEXT,
                            FOREIGN KEY(failure_id) REFERENCES validation_failures(id),
                            FOREIGN KEY(run_id) REFERENCES validation_runs(id)
                        )
                    """)
                    
                    # TABLE 4: agent_memory
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS agent_memory (
                            id TEXT PRIMARY KEY,
                            failure_pattern TEXT,
                            root_cause TEXT,
                            successful_fix TEXT,
                            success_count INTEGER DEFAULT 0,
                            fail_count INTEGER DEFAULT 0,
                            avg_improvement REAL,
                            last_seen TEXT
                        )
                    """)
                    
                    # TABLE 5: generated_rules
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS generated_rules (
                            id TEXT PRIMARY KEY,
                            natural_language_input TEXT,
                            yaml_output TEXT,
                            created_at TEXT,
                            times_used INTEGER DEFAULT 0
                        )
                    """)
                    
                    conn.commit()
                logger.info("Database initialized successfully.")
            except sqlite3.Error as e:
                logger.error(f"Failed to initialize SQLite database: {e}")
                raise

    def save_run(self, run_result: Dict[str, Any]) -> str:
        """Saves validation run metadata and outcomes.

        Args:
            run_result: Run summary details.

        Returns:
            The unique run identifier string (UUID).
        """
        run_id = run_result.get("run_id") or str(uuid.uuid4())
        timestamp = run_result.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        total_checks  = run_result.get("rules_evaluated", 0)
        failed_checks = run_result.get("rules_failed", 0)
        passed_checks = max(0, total_checks - failed_checks)
        # Compute actual check-pass rate (not improvement %)
        success_rate = round((passed_checks / total_checks * 100), 2) if total_checks > 0 else 0.0

        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO validation_runs (
                            id, timestamp, filename, total_rows, total_checks, 
                            passed_checks, failed_checks, success_rate, duration_seconds, iterations
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            timestamp,
                            run_result.get("filename", ""),
                            run_result.get("total_rows", 0),
                            total_checks,
                            passed_checks,
                            failed_checks,
                            success_rate,
                            run_result.get("total_duration_seconds", 0.0),
                            run_result.get("iterations", 1)
                        )
                    )
                    conn.commit()
                logger.info(f"Saved run record: {run_id}")
            except sqlite3.Error as e:
                logger.error(f"Failed to save run {run_id}: {e}")
                raise
        return run_id

    def get_run_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves history of recent validation runs.

        Args:
            limit: Maximum count of rows to return.

        Returns:
            A list of dictionary records.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM validation_runs ORDER BY timestamp DESC LIMIT ?", (limit,)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch run history: {e}")
            raise

    def save_failure(self, failure: Dict[str, Any], run_id: str) -> str:
        """Saves details of a single check failure to validation_failures table.

        Args:
            failure: Check result containing failure details.
            run_id: Associated execution run ID.

        Returns:
            Unique failure identifier string.
        """
        failure_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bad_rows_json = json.dumps(failure.get("sample_bad_rows", []))
        
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO validation_failures (
                            id, run_id, check_name, column_name, check_type, 
                            failure_count, total_count, failure_percentage, severity, sample_bad_rows_json, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            failure_id,
                            run_id,
                            failure.get("check_name", ""),
                            failure.get("column", ""),
                            failure.get("check_name", ""),  # Using check_name as type placeholder if not specified
                            failure.get("failure_count", 0),
                            failure.get("total_count", 0),
                            failure.get("failure_percentage", 0.0),
                            failure.get("severity", "medium"),
                            bad_rows_json,
                            timestamp
                        )
                    )
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to save failure for run {run_id}: {e}")
                raise
        return failure_id

    def save_fix(self, fix: Dict[str, Any], failure_id: str, run_id: str) -> str:
        """Saves proposed SQL and Pandas fixes to generated_fixes table.

        Args:
            fix: Fix result object or dict.
            failure_id: Associated validation failure ID.
            run_id: Associated execution run ID.

        Returns:
            Unique fix identifier.
        """
        fix_id = fix.get("fix_id") or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO generated_fixes (
                            id, failure_id, run_id, pandas_fix, sql_fix, 
                            confidence_score, fix_valid, was_applied, improvement_percentage, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fix_id,
                            failure_id,
                            run_id,
                            fix.get("pandas_fix", ""),
                            fix.get("sql_fix", ""),
                            fix.get("confidence_score", 0.0),
                            1 if fix.get("pandas_fix_valid", True) else 0,
                            1 if fix.get("was_applied", False) else 0,
                            fix.get("improvement_percentage", 0.0),
                            timestamp
                        )
                    )
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to save generated fix: {e}")
                raise
        return fix_id

    def get_similar_failures(self, check_type: str, column: str) -> List[Dict[str, Any]]:
        """Finds past validation failures with matching parameters.

        Args:
            check_type: Check classification.
            column: Target column.

        Returns:
            A list of matching records.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM validation_failures 
                    WHERE (check_name LIKE ? OR check_type LIKE ?) AND column_name = ?
                    ORDER BY timestamp DESC
                    """,
                    (f"%{check_type}%", f"%{check_type}%", column)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to search similar failures: {e}")
            raise

    def get_best_fix_for_pattern(self, check_type: str, column: str) -> Optional[Dict[str, Any]]:
        """Finds the highest success rate fix for a check type and column combination.

        Args:
            check_type: Check classification.
            column: Target column.

        Returns:
            Fix metadata dictionary if found, else None.
        """
        pattern = f"{check_type}:{column}"
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM agent_memory 
                    WHERE failure_pattern = ? 
                    ORDER BY success_count DESC, avg_improvement DESC LIMIT 1
                    """,
                    (pattern,)
                )
                row = cursor.fetchone()
                if row:
                    record = dict(row)
                    # Calculate success rate for agent_loop check (>80%)
                    total = record["success_count"] + record["fail_count"]
                    record["success_rate"] = (record["success_count"] / total * 100.0) if total > 0 else 0.0
                    # Standardize fields for agent loop
                    record["fix_code"] = record.get("successful_fix", "")
                    return record
                return None
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve best fix for pattern {pattern}: {e}")
            raise

    def get_best_fix(self, check_name: str, column: str) -> Optional[Dict[str, Any]]:
        """Alias method matching agent_loop.py requirements.

        Args:
            check_name: Validation check class or name.
            column: Target column name.

        Returns:
            Dictionary matching success details.
        """
        return self.get_best_fix_for_pattern(check_name, column)

    def save_fix_attempt(
        self,
        check_name: str,
        column: str,
        root_cause: str,
        fix_code: str,
        improvement: float,
        confidence: float,
        is_success: bool
    ) -> None:
        """Stores or updates agent memory statistics for repair attempts.

        Args:
            check_name: Name of the executed check.
            column: Targets.
            root_cause: Explanatory diagnosis text.
            fix_code: Executed pandas repair code.
            improvement: Percent reduction in target failure rates.
            confidence: Code security confidence value.
            is_success: Flag indicating validation pass status.
        """
        pattern = f"{check_name}:{column}"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Try to locate existing memory record
                    cursor.execute(
                        "SELECT * FROM agent_memory WHERE failure_pattern = ?", (pattern,)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        record = dict(row)
                        new_success = record["success_count"] + (1 if is_success else 0)
                        new_fail = record["fail_count"] + (0 if is_success else 1)
                        
                        # Compute moving average improvement
                        total_runs = new_success + new_fail
                        prev_avg = record.get("avg_improvement") or 0.0
                        new_avg = ((prev_avg * (total_runs - 1)) + improvement) / total_runs
                        
                        cursor.execute(
                            """
                            UPDATE agent_memory SET 
                                root_cause = ?,
                                successful_fix = ?,
                                success_count = ?,
                                fail_count = ?,
                                avg_improvement = ?,
                                last_seen = ?
                            WHERE id = ?
                            """,
                            (
                                root_cause,
                                fix_code if is_success else record["successful_fix"],
                                new_success,
                                new_fail,
                                new_avg,
                                timestamp,
                                record["id"]
                            )
                        )
                    else:
                        memory_id = str(uuid.uuid4())
                        cursor.execute(
                            """
                            INSERT INTO agent_memory (
                                id, failure_pattern, root_cause, successful_fix, 
                                success_count, fail_count, avg_improvement, last_seen
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                memory_id,
                                pattern,
                                root_cause,
                                fix_code,
                                1 if is_success else 0,
                                0 if is_success else 1,
                                improvement,
                                timestamp
                            )
                        )
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to update fix attempt outcome for pattern {pattern}: {e}")
                raise

    def update_fix_outcome(self, fix_id: str, improved: bool, improvement_pct: float) -> None:
        """Updates applied status and improvements on generated_fixes table.

        Args:
            fix_id: Targets.
            improved: Whether accuracy grew.
            improvement_pct: Percent validation rate decline.
        """
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE generated_fixes SET 
                            was_applied = ?,
                            improvement_percentage = ?
                        WHERE id = ?
                        """,
                        (1 if improved else 0, improvement_pct, fix_id)
                    )
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to update fix outcome for ID {fix_id}: {e}")
                raise

    def save_rule(self, nl_input: str, yaml_output: str) -> str:
        """Stores user natural language instructions and generated YAML output.

        Args:
            nl_input: Instruction query.
            yaml_output: Rendered validation configurations.

        Returns:
            The saved rule UUID.
        """
        rule_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        with db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO generated_rules (
                            id, natural_language_input, yaml_output, created_at, times_used
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (rule_id, nl_input, yaml_output, created_at, 0)
                    )
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to store generated rule: {e}")
                raise
        return rule_id

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Retrieves list of all historically synthesized YAML rules."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM generated_rules ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch rules: {e}")
            raise

    def get_memory_stats(self) -> Dict[str, Any]:
        """Gathers aggregate database stats for usage in analytics dashboards."""
        stats = {
            "total_runs": 0,
            "total_fixes": 0,
            "avg_success_rate": 0.0,
            "most_common_failure": "N/A",
            "top_performing_fix": "N/A",
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # total runs
                cursor.execute("SELECT COUNT(*) FROM validation_runs")
                stats["total_runs"] = cursor.fetchone()[0]
                
                # total fixes
                cursor.execute("SELECT COUNT(*) FROM generated_fixes")
                stats["total_fixes"] = cursor.fetchone()[0]
                
                # avg_success_rate (based on runs success_rate field)
                cursor.execute("SELECT AVG(success_rate) FROM validation_runs")
                avg_rate = cursor.fetchone()[0]
                stats["avg_success_rate"] = float(round(avg_rate, 2)) if avg_rate is not None else 0.0
                
                # most_common_failure
                cursor.execute(
                    """
                    SELECT check_name, COUNT(*) as cnt FROM validation_failures 
                    GROUP BY check_name ORDER BY cnt DESC LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row:
                    stats["most_common_failure"] = f"{row['check_name']} ({row['cnt']} times)"
                    
                # top_performing_fix
                cursor.execute(
                    """
                    SELECT failure_pattern, success_count FROM agent_memory 
                    ORDER BY success_count DESC LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row:
                    stats["top_performing_fix"] = f"{row['failure_pattern']} (reused {row['success_count']} times)"
                    
        except sqlite3.Error as e:
            logger.error(f"Error fetching stats from memory database: {e}")
            
        return stats

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """Queries memory records using simple text matching across root_cause, failure_pattern, and successful_fix.

        Args:
            query: Phrase pattern search.

        Returns:
            A list of dictionary records.
        """
        try:
            pattern = f"%{query}%"
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM agent_memory 
                    WHERE root_cause LIKE ? OR failure_pattern LIKE ? OR successful_fix LIKE ?
                    ORDER BY last_seen DESC LIMIT 20
                    """,
                    (pattern, pattern, pattern)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to query SQLite search memory: {e}")
            raise
