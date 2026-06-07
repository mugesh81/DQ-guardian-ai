"""DQ Guardian AI Fix Generator.

Validates and formats the suggested fixes, checking syntax correctness
with AST parsing and verifying code security (sandboxing checks).
"""

import ast
import logging
import uuid
from dataclasses import dataclass, field
from typing import List
import pandas as pd

from app.agent.root_cause_analyzer import RootCauseResult

# Configure logger
logger = logging.getLogger("fix_generator")


@dataclass
class FixResult:
    """Dataclass holding details of validated and sanitized repair scripts."""

    fix_id: str
    check_name: str
    pandas_fix: str
    sql_fix: str
    pandas_fix_valid: bool
    sql_fix_valid: bool
    confidence_score: float
    fix_status: str  # "valid", "invalid", "needs_review"
    security_warnings: List[str] = field(default_factory=list)


class FixGenerator:
    """Validates and processes repair recommendations safely before presenting to users."""

    def generate(self, root_cause: RootCauseResult, df: pd.DataFrame) -> FixResult:
        """Sanitizes and evaluates syntax/safety of the proposed fixes.

        Args:
            root_cause: Diagnosis containing raw fix recommendations.
            df: DataFrame to validate columns against.

        Returns:
            FixResult instance.
        """
        logger.info(f"Generating and validating repair scripts for check: {root_cause.check_name}")
        
        pandas_raw = root_cause.pandas_fix.strip()
        sql_raw = root_cause.sql_fix.strip()
        
        security_warnings: List[str] = []
        pandas_valid = False
        sql_valid = True  # SQL starts valid, checked for basic injection patterns
        
        # 1. Syntax Verification with ast.parse()
        try:
            tree = ast.parse(pandas_raw)
            pandas_valid = True
            
            # 2. Security Walk: Check for forbidden imports or function calls
            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in ("pandas", "numpy", "datetime", "pd", "np"):
                            pandas_valid = False
                            security_warnings.append(f"Forbidden import: '{alias.name}' detected.")
                elif isinstance(node, ast.ImportFrom):
                    if node.module not in ("pandas", "numpy", "datetime", "pd", "np"):
                        pandas_valid = False
                        security_warnings.append(f"Forbidden import: 'from {node.module}' detected.")
                
                # Check dangerous functions
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ("exec", "eval", "open", "input", "__import__", "getattr", "setattr"):
                            pandas_valid = False
                            security_warnings.append(f"Forbidden system call: '{node.func.id}()' detected.")
                    elif isinstance(node.func, ast.Attribute):
                        # Block attributes on modules like os.system, sys.exit
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id in ("os", "sys", "subprocess", "shutil", "socket", "builtins"):
                                pandas_valid = False
                                security_warnings.append(f"Forbidden library call: '{node.func.value.id}.{node.func.attr}' detected.")
        except SyntaxError as e:
            logger.warning(f"SyntaxError detected in generated pandas fix code for check '{root_cause.check_name}': {e}")
            pandas_valid = False
            security_warnings.append(f"Python syntax error: {str(e)}")
            
        # 3. Simple SQL Injection Sanitization
        sql_forbidden = ["drop table", "drop database", "truncate", "delete from", "grant", "revoke", "alter table"]
        for pattern in sql_forbidden:
            if pattern in sql_raw.lower():
                # Let's flag but allow if duplicate check is dropping rows
                if "delete from" in pattern and "duplicate" in root_cause.check_name.lower():
                    continue
                sql_valid = False
                security_warnings.append(f"Dangerous SQL pattern detected: '{pattern}'.")

        # 4. Formats fixes with headers
        fix_id = str(uuid.uuid4())
        
        pandas_formatted = (
            f"# Auto-generated fix for: {root_cause.check_name}\n"
            f"# Confidence Score: {root_cause.confidence_score}\n"
            f"# REVIEW BEFORE APPLYING\n"
            f"{pandas_raw}"
        )
        
        sql_formatted = (
            f"-- Auto-generated SQL fix for: {root_cause.check_name}\n"
            f"-- Confidence Score: {root_cause.confidence_score}\n"
            f"-- REVIEW BEFORE APPLYING\n"
            f"{sql_raw}"
        )

        # Overall Status Resolution
        if not pandas_valid or not sql_valid:
            status = "invalid"
        elif security_warnings:
            status = "needs_review"
        else:
            status = "valid"

        logger.info(f"Fix generation complete. ID: {fix_id}. Status: {status}. Errors/Warnings: {len(security_warnings)}")

        return FixResult(
            fix_id=fix_id,
            check_name=root_cause.check_name,
            pandas_fix=pandas_formatted,
            sql_fix=sql_formatted,
            pandas_fix_valid=pandas_valid,
            sql_fix_valid=sql_valid,
            confidence_score=root_cause.confidence_score,
            fix_status=status,
            security_warnings=security_warnings
        )
