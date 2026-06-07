"""DQ Guardian AI Agent Loop.

Orchestrates the 6-stage agent loop: Observe -> Reason -> Act -> Validate -> Learn -> Repeat.
"""

import logging
import time
from dataclasses import dataclass, field
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load .env early so GROQ_API_KEY is available in all child modules
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)
except ImportError:
    pass

import numpy as np
import pandas as pd

# Safe builtins whitelist for exec() sandbox
# Allows common data-manipulation primitives while blocking dangerous system calls.
_SAFE_BUILTINS: Dict[str, Any] = {
    # Type constructors
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    # Common built-ins
    "len": len, "abs": abs, "round": round, "range": range,
    "min": min, "max": max, "sum": sum, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "isinstance": isinstance, "issubclass": issubclass,
    "print": print, "repr": repr, "type": type,
    "None": None, "True": True, "False": False,
    "NotImplemented": NotImplemented,
}

from app.agent.confidence_engine import ConfidenceEngine
from app.agent.fix_generator import FixGenerator
from app.agent.memory_engine import MemoryEngine
from app.agent.root_cause_analyzer import RootCauseAnalyzer
from app.agent.validator import CheckResult, ValidationEngine, ValidationReport

# Configure logger
logger = logging.getLogger("agent_loop")


@dataclass
class AgentRunResult:
    """Dataclass holding aggregate details of an agent loop execution."""

    run_id: str
    filename: str
    iterations: int
    initial_failure_count: int
    final_failure_count: int
    overall_improvement_percentage: float
    fixes_generated: List[Dict[str, Any]]
    fixes_from_memory: int
    fixes_new: int
    total_duration_seconds: float
    validation_report_before: ValidationReport
    validation_report_after: ValidationReport
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class AgentLoop:
    """The core coordination engine executing the 6-stage agent loop."""

    def __init__(
        self,
        data_path: Path,
        rules_path: Optional[Path] = None,
        rules_dict: Optional[Dict[str, Any]] = None,
        max_iterations: int = 3,
        db_path: Optional[Path] = None,
    ):
        self.data_path = Path(data_path)
        self.rules_path = Path(rules_path) if rules_path else None
        self.max_iterations = max_iterations

        # Instantiate dependencies
        self.validator = ValidationEngine()
        if rules_dict:
            self.validator.load_rules_from_dict(rules_dict)
        elif self.rules_path:
            self.validator.load_rules_from_yaml(self.rules_path)
        else:
            raise ValueError("AgentLoop requires either rules_path or rules_dict.")

        self.memory = MemoryEngine(db_path=db_path)
        self.analyzer = RootCauseAnalyzer()
        self.fix_gen = FixGenerator()

        self.confidence_eng = ConfidenceEngine()
        
        # Session state
        self.run_id = f"run_{int(time.time())}"
        self.iterations_run = 0
        self.fixes_generated_log: List[Dict[str, Any]] = []
        self.fixes_from_memory_count = 0
        self.fixes_new_count = 0

    def _load_data(self) -> pd.DataFrame:
        """Loads data auto-detecting CSV or Parquet format based on file extension."""
        suffix = self.data_path.suffix.lower()
        if suffix == ".csv":
            logger.info(f"Loading CSV data from {self.data_path}")
            return pd.read_csv(
                self.data_path,
                skip_blank_lines=True,
                on_bad_lines="warn",
                encoding_errors="replace",
            )
        elif suffix in (".parquet", ".pq"):
            logger.info(f"Loading Parquet data from {self.data_path}")
            return pd.read_parquet(self.data_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def run(self) -> Dict[str, Any]:
        """Runs the complete 6-stage agent loop.

        Returns:
            A dictionary containing the parsed run summary details.
        """
        start_time = time.time()
        logger.info(f"Starting Agent Loop for {self.data_path.name}")
        
        # Load the base dataset
        df_current = self._load_data()
        df_original = df_current.copy()
        
        # Stage 1: Observe (Initial run)
        initial_report = self.validator.run_all_checks(df_original, filename=self.data_path.name)
        initial_failures = [r for r in initial_report.results if r.status == "FAIL"]
        initial_fail_count = sum(r.failure_count for r in initial_failures)
        
        logger.info(f"OBSERVE (Initial): Found {len(initial_failures)} failed checks with {initial_fail_count} failure points.")
        
        # Loop variables
        report_before = initial_report
        report_after = initial_report
        
        severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        for iteration in range(1, self.max_iterations + 1):
            self.iterations_run = iteration
            logger.info(f"--- STARTING AGENT LOOP ITERATION {iteration}/{self.max_iterations} ---")
            
            # STAGE 1: OBSERVE
            current_report = self.validator.run_all_checks(df_current, filename=self.data_path.name)
            current_failures = [r for r in current_report.results if r.status == "FAIL"]
            
            logger.info(f"OBSERVE: Found {len(current_failures)} failures across {len(set(r.column for r in current_failures))} columns")
            if not current_failures:
                logger.info("OBSERVE: No failures detected in this iteration. Breaking loop.")
                report_after = current_report
                break
                
            # STAGE 2: REASON
            # Sort failures by severity (critical first)
            current_failures.sort(key=lambda x: severity_weights.get(x.severity, 0), reverse=True)
            
            reasoning_list = []
            for failure in current_failures:
                # Check memory for existing fix
                past_fix = self.memory.get_best_fix(failure.check_name, failure.column)
                if past_fix and past_fix.get("success_rate", 0.0) >= 80.0:
                    reasoning_list.append({
                        "failure": failure,
                        "mode": "MEMORY_REUSE",
                        "past_fix": past_fix
                    })
                else:
                    reasoning_list.append({
                        "failure": failure,
                        "mode": "NEEDS_AI_ANALYSIS",
                        "past_fix": None
                    })
                    
            ai_needs = sum(1 for item in reasoning_list if item["mode"] == "NEEDS_AI_ANALYSIS")
            mem_reuses = sum(1 for item in reasoning_list if item["mode"] == "MEMORY_REUSE")
            logger.info(f"REASON: {ai_needs} failures need AI, {mem_reuses} can use memory")
            
            # STAGE 3: ACT
            fixes_applied = 0
            
            def _generate_fix(item):
                failure = item["failure"]
                mode = item["mode"]
                
                fix_code = ""
                sql_fix = ""
                root_cause = ""
                explanation = ""
                
                if mode == "MEMORY_REUSE":
                    logger.info(f"ACT: Reusing memory fix for {failure.check_name} on {failure.column}")
                    past_fix = item["past_fix"]
                    fix_code = past_fix.get("fix_code", "")
                    sql_fix = "-- SQL fix is not stored in agent memory for reused fixes."
                    root_cause = past_fix.get("root_cause", "Retrieved from memory")
                    explanation = "Reused matching fix found in SQLite memory engine."
                else:
                    logger.info(f"ACT: Requesting AI Root Cause Analysis for {failure.check_name} on {failure.column}")
                    # AI diagnosis with fallback protection
                    analysis = self.analyzer.analyze(failure, df_current)
                    root_cause = analysis.root_cause
                    explanation = analysis.recommended_fix
                    
                    # Generate fix code
                    fix_gen_res = self.fix_gen.generate(analysis, df_current)
                    fix_code = fix_gen_res.pandas_fix
                    sql_fix = fix_gen_res.sql_fix
                    
                item["generated_data"] = {
                    "fix_code": fix_code,
                    "sql_fix": sql_fix,
                    "root_cause": root_cause,
                    "explanation": explanation
                }
                return item

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                completed_reasoning_list = list(executor.map(_generate_fix, reasoning_list))
                
            for item in completed_reasoning_list:
                failure = item["failure"]
                mode = item["mode"]
                gen_data = item.get("generated_data", {})
                
                fix_code = gen_data.get("fix_code", "")
                sql_fix = gen_data.get("sql_fix", "")
                root_cause = gen_data.get("root_cause", "")
                explanation = gen_data.get("explanation", "")
                
                if mode == "MEMORY_REUSE":
                    self.fixes_from_memory_count += 1
                else:
                    self.fixes_new_count += 1
                    
                if not fix_code:
                    logger.warning(f"ACT: Could not generate/retrieve fix code for {failure.check_name} on {failure.column}")
                    continue
                    
                # STAGE 4: VALIDATE
                logger.info(f"VALIDATE: Testing fix for {failure.check_name} on {failure.column}")
                df_temp = df_current.copy()
                
                success = False
                improvement_pct = 0.0
                conf_score = 0.0
                
                try:
                    # Apply the generated/retrieved python patch to the copied DataFrame.
                    # Execute in restricted global context with curated safe builtins.
                    # Dangerous calls (exec, eval, open, __import__, os, sys, subprocess)
                    # are NOT in _SAFE_BUILTINS and will raise NameError if attempted.
                    _exec_globals = {
                        "__builtins__": _SAFE_BUILTINS,
                        "pd": pd,
                        "np": np,
                    }
                    # Strip import lines — pd/np are already in globals; LLMs sometimes
                    # generate imports despite being told not to.
                    clean_code = "\n".join(
                        line for line in fix_code.splitlines()
                        if not line.strip().startswith("import ")
                        and not line.strip().startswith("from ")
                    )
                    exec(clean_code, _exec_globals, {"df": df_temp})  # nosec
                    
                    # Re-run ONLY the failed check
                    validation_res = self.validator.run_single_check(df_temp, failure.check_name)
                    
                    if validation_res.status == "PASS":
                        success = True
                        improvement_pct = 100.0
                    else:
                        before_fail = failure.failure_count
                        after_fail = validation_res.failure_count
                        if before_fail > 0:
                            improvement_pct = float(round(((before_fail - after_fail) / before_fail) * 100, 2))
                            if improvement_pct >= 95.0:
                                success = True
                        else:
                            improvement_pct = 0.0
                            
                    conf_score = self.confidence_eng.score(fix_code, failure, improvement_pct)
                    logger.info(f"VALIDATE: Fix improved check '{failure.check_name}' from {failure.failure_percentage}% to {validation_res.failure_percentage}% failure rate")
                except Exception as e:
                    logger.error(f"VALIDATE: Failed to execute fix code for '{failure.check_name}': {e}")
                    improvement_pct = 0.0
                    conf_score = 0.0
                    success = False
                    
                # Store proposed fix details for report and dashboard
                fix_proposal = {
                    "check_name": failure.check_name,
                    "column": failure.column,
                    "root_cause": root_cause,
                    "explanation": explanation,
                    "fix_code": fix_code,
                    "sql_fix": sql_fix,
                    "improvement_percentage": improvement_pct,
                    "confidence_score": conf_score,
                    "status": "APPROVED_PENDING_USER" if success else "FAILED_VALIDATION",
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "df_patched": df_temp if success else None  # Save local copy for applying later
                }
                self.fixes_generated_log.append(fix_proposal)
                
                # STAGE 5: LEARN
                logger.info(f"LEARN: Saving fix attempt for {failure.check_name} on {failure.column} to memory")
                self.memory.save_fix_attempt(
                    check_name=failure.check_name,
                    column=failure.column,
                    root_cause=root_cause,
                    fix_code=fix_code,
                    improvement=improvement_pct,
                    confidence=conf_score,
                    is_success=success
                )
                
                # Apply the successful validation fix to current DataFrame for subsequent checks
                if success:
                    df_current = df_temp
                    fixes_applied += 1
                    
            logger.info(f"LEARN: Saved {len(reasoning_list)} results to memory")
            
            # STAGE 6: REPEAT
            # Calculate current improvement rate
            after_report = self.validator.run_all_checks(df_current, filename=self.data_path.name)
            after_failures = [r for r in after_report.results if r.status == "FAIL"]
            after_fail_count = sum(r.failure_count for r in after_failures)
            
            if initial_fail_count > 0:
                overall_improvement = float(round(((initial_fail_count - after_fail_count) / initial_fail_count) * 100, 2))
            else:
                overall_improvement = 100.0
                
            logger.info(f"REPEAT: Iteration {iteration} complete. Overall improvement: {overall_improvement}%")
            report_after = after_report
            
            # Check exit conditions:
            # 1. All critical failures resolved
            criticals_resolved = all(r.severity != "critical" for r in after_failures)
            
            if len(after_failures) == 0 or (criticals_resolved and overall_improvement >= 95.0):
                logger.info("All exit conditions met. Exiting agent loop early.")
                break
                
        # Final calculations
        duration = float(round(time.time() - start_time, 2))
        final_report = report_after
        final_failures = [r for r in final_report.results if r.status == "FAIL"]
        final_fail_count = sum(r.failure_count for r in final_failures)
        
        if initial_fail_count > 0:
            final_improvement = float(round(((initial_fail_count - final_fail_count) / initial_fail_count) * 100, 2))
        else:
            final_improvement = 100.0
            
        # Compile result object
        run_summary = {
            "run_id": self.run_id,
            "filename": self.data_path.name,
            "iterations": self.iterations_run,
            "initial_failure_count": initial_fail_count,
            "final_failure_count": final_fail_count,
            "overall_improvement_percentage": final_improvement,
            # Filter out dataframe copies from final serializable results
            "proposed_fixes": [
                {k: v for k, v in f.items() if k != "df_patched"}
                for f in self.fixes_generated_log
            ],
            "fixes_from_memory": self.fixes_from_memory_count,
            "fixes_new": self.fixes_new_count,
            "total_duration_seconds": duration,
            "status": "Success" if final_improvement >= 95.0 else "Partial Success",
            "rules_evaluated": len(initial_report.results),
            "rules_failed": len(final_failures)
        }
        
        return run_summary
