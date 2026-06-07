"""DQ Guardian AI Confidence Engine.

Calculates the confidence score of proposed fixes based on multiple criteria:
- Validation improvement percentage
- Severity of the failure
- Code structure/complexity
- History of similar fixes in memory
"""

import ast
import logging
from typing import Any

from app.agent.validator import CheckResult

# Set up logging
logger = logging.getLogger("confidence_engine")


class ConfidenceEngine:
    """Calculates quantitative confidence scores for generated pandas/SQL fixes."""

    def score(self, fix_code: str, check_result: CheckResult, improvement_pct: float) -> float:
        """Calculates a confidence score between 0.0 and 100.0.

        Args:
            fix_code: The generated Python code.
            check_result: The target failure result object.
            improvement_pct: Calculated validation improvement rate.

        Returns:
            A float confidence score between 0.0 and 100.0.
        """
        logger.info(f"Scoring confidence for check: {check_result.check_name}")
        
        # Base score starts with the improvement rate
        # 100% improvement gives 50 points base
        score = (improvement_pct / 100.0) * 60.0
        
        # Check AST parse state
        try:
            tree = ast.parse(fix_code)
            # Add points for valid syntax
            score += 20.0
            
            # Code complexity sanity checks
            nodes_count = len(list(ast.walk(tree)))
            if nodes_count < 30:
                # Simple, compact fixes are preferred
                score += 10.0
            else:
                score += 5.0
        except SyntaxError:
            # Major penalty for invalid syntax
            return 0.0
            
        # Deduct points if the repair is empty or just comments
        lines = [line.strip() for line in fix_code.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not lines:
            score -= 30.0

        # Adjust score for target severity: critical/high requires more strict correctness
        if check_result.severity == "critical":
            if improvement_pct < 100.0:
                # Penalty if not completely resolving critical issues
                score -= 10.0
        elif check_result.severity == "low":
            score += 5.0

        # Clip values
        final_score = float(max(0.0, min(100.0, score)))
        logger.info(f"Confidence score calculated: {final_score:.2f}%")
        
        return final_score
