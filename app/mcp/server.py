"""FastAPI MCP Server for DQ Guardian AI.

Exposes Server-Sent Events (SSE) and HTTP endpoints representing the 6 MCP tools:
- run_quality_check
- get_bad_rows
- generate_fix
- apply_fix
- generate_yaml_rules
- chat_with_dataset
"""

import json
import logging
import os
import sys
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
import requests
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.confidence_engine import ConfidenceEngine
from app.agent.fix_generator import FixGenerator, FixResult
from app.agent.memory_engine import MemoryEngine
from app.agent.root_cause_analyzer import RootCauseAnalyzer, RootCauseResult
from app.agent.validator import CheckResult, ValidationEngine, ValidationReport

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("mcp_server")


# Life-cycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup/shutdown logs for MCP server."""
    logger.info("Initializing DQ Guardian AI MCP Server...")
    yield
    logger.info("Shutting down DQ Guardian AI MCP Server...")


app = FastAPI(
    title="DQ Guardian AI MCP Server",
    description="FastAPI SSE server exposing Data Quality Agent tools",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Engines
memory = MemoryEngine()
validator = ValidationEngine()
analyzer = RootCauseAnalyzer()
fix_generator = FixGenerator()
confidence_engine = ConfidenceEngine()


# --- PYDANTIC SCHEMAS ---

class QualityCheckRequest(BaseModel):
    file_path: str = Field(..., description="Path to CSV/Parquet file")
    rules_path: str = Field(..., description="Path to rules YAML configuration file")


class QualityCheckResponse(BaseModel):
    run_id: str
    summary: Dict[str, Any]
    failed_checks: List[Dict[str, Any]]
    success_rate: float
    total_rows: int
    duration_seconds: float


class BadRowsRequest(BaseModel):
    run_id: str
    check_name: str
    limit: int = Field(10, description="Max failed records to return")


class BadRowsResponse(BaseModel):
    bad_rows: List[Dict[str, Any]]
    total_count: int
    check_name: str
    column: str


class GenerateFixRequest(BaseModel):
    run_id: str
    check_name: str


class GenerateFixResponse(BaseModel):
    fix_id: str
    pandas_fix: str
    sql_fix: str
    confidence: float
    fix_valid: bool
    root_cause: str
    business_impact: str


class ApplyFixRequest(BaseModel):
    run_id: str
    fix_id: str
    approve: bool


class ApplyFixResponse(BaseModel):
    status: str
    improvement_percentage: float
    new_failure_count: int
    cleaned_file_path: str


class GenerateRulesRequest(BaseModel):
    natural_language: str


class GenerateRulesResponse(BaseModel):
    yaml_rules: str
    parsed_rules: Dict[str, Any]
    rule_count: int
    rule_id: str


class ChatWithDatasetRequest(BaseModel):
    run_id: str
    question: str


class ChatWithDatasetResponse(BaseModel):
    answer: str
    relevant_data: Dict[str, Any]
    sources: List[str]


# --- API ENDPOINTS ---

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Service availability check."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.get("/tools")
def get_tools_list():
    """Lists all available MCP tools with descriptions and expected schemas."""
    return [
        {
            "name": "run_quality_check",
            "description": "Validates CSV/Parquet files against rule YAML file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to data file"},
                    "rules_path": {"type": "string", "description": "Path to rules yaml file"},
                },
                "required": ["file_path", "rules_path"],
            },
        },
        {
            "name": "get_bad_rows",
            "description": "Returns sample rows failing a specific check validation rule",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "UUID of validation run"},
                    "check_name": {"type": "string", "description": "Name of check configuration"},
                    "limit": {"type": "integer", "description": "Max rows to return", "default": 10},
                },
                "required": ["run_id", "check_name"],
            },
        },
        {
            "name": "generate_fix",
            "description": "Diagnoses failure root-cause and outputs Python/SQL fixes via Groq AI",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "UUID of validation run"},
                    "check_name": {"type": "string", "description": "Name of check configuration"},
                },
                "required": ["run_id", "check_name"],
            },
        },
        {
            "name": "apply_fix",
            "description": "Executes proposed pandas fix on data and saves the cleaned dataset",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "UUID of validation run"},
                    "fix_id": {"type": "string", "description": "UUID of proposed fix"},
                    "approve": {"type": "boolean", "description": "Approve applying the fix"},
                },
                "required": ["run_id", "fix_id", "approve"],
            },
        },
        {
            "name": "generate_yaml_rules",
            "description": "Converts plain text requirements into YAML validator rule configs",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "natural_language": {"type": "string", "description": "Text describing validation criteria"},
                },
                "required": ["natural_language"],
            },
        },
        {
            "name": "chat_with_dataset",
            "description": "Chat interface querying historical validations and dataset metrics",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "UUID of target validation run"},
                    "question": {"type": "string", "description": "Question about data defects"},
                },
                "required": ["run_id", "question"],
            },
        },
    ]


@app.get("/memory/stats")
def get_memory_statistics():
    """Exposes aggregate database metrics from SQLite memory."""
    try:
        return memory.get_memory_stats()
    except Exception as e:
        logger.exception("Error loading memory stats")
        raise HTTPException(status_code=500, detail="Internal memory database fetch error")


@app.get("/runs")
def get_runs_history():
    """Retrieves 20 most recent validation runs."""
    try:
        return memory.get_run_history(limit=20)
    except Exception as e:
        logger.exception("Error loading run history")
        raise HTTPException(status_code=500, detail="Internal database fetch error")


# --- MCP TOOL API IMPLEMENTATIONS ---

@app.post("/tools/run_quality_check", response_model=QualityCheckResponse)
def run_quality_check(req: QualityCheckRequest):
    """Executes validation checks on target file paths."""
    start_time = time.time()
    file_path = Path(req.file_path)
    rules_path = Path(req.rules_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Target file not found at: {file_path}")
    if not rules_path.exists():
        raise HTTPException(status_code=404, detail=f"Rules file not found at: {rules_path}")

    try:
        # Load rules and run validation
        validator.load_rules_from_yaml(rules_path)
        
        # Load dataset
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(file_path)
        elif suffix in (".parquet", ".pq"):
            df = pd.read_parquet(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {suffix}")

        report = validator.run_all_checks(df, filename=file_path.name)
        duration = float(round(time.time() - start_time, 2))
        
        # Format metrics and save
        run_data = {
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "filename": file_path.name,
            "total_rows": len(df),
            "rules_evaluated": report.total_checks,
            "rules_failed": report.failed,
            "overall_improvement_percentage": report.success_rate,
            "total_duration_seconds": duration,
            "iterations": 1
        }
        
        run_id = memory.save_run(run_data)
        
        # Save failures to database
        failed_list = []
        for result in report.results:
            if result.status == "FAIL":
                failure_dict = {
                    "check_name": result.check_name,
                    "column": result.column,
                    "failure_count": result.failure_count,
                    "total_count": result.total_count,
                    "failure_percentage": result.failure_percentage,
                    "severity": result.severity,
                    "sample_bad_rows": result.sample_bad_rows,
                    "column_stats": result.column_stats
                }
                memory.save_failure(failure_dict, run_id)
                failed_list.append(failure_dict)

        return QualityCheckResponse(
            run_id=run_id,
            summary={
                "total_checks": report.total_checks,
                "passed": report.passed,
                "failed": report.failed,
            },
            failed_checks=failed_list,
            success_rate=report.success_rate,
            total_rows=len(df),
            duration_seconds=duration
        )

    except Exception as e:
        logger.exception("Failure running validation check tool")
        raise HTTPException(status_code=500, detail=f"Validator internal failure: {str(e)}")


@app.post("/tools/get_bad_rows", response_model=BadRowsResponse)
def get_bad_rows(req: BadRowsRequest):
    """Retrieves bad records for a failed validation check."""
    try:
        # Search failure from database using run_id and check_name
        with memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM validation_failures 
                WHERE run_id = ? AND check_name = ?
                """,
                (req.run_id, req.check_name)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Check result details not found in database memory")
            
            record = dict(row)
            bad_rows = json.loads(record.get("sample_bad_rows_json", "[]"))
            
            return BadRowsResponse(
                bad_rows=bad_rows[:req.limit],
                total_count=record.get("failure_count", 0),
                check_name=record.get("check_name", ""),
                column=record.get("column_name", "")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failure getting bad rows")
        raise HTTPException(status_code=500, detail="Failed to fetch bad rows")


@app.post("/tools/generate_fix", response_model=GenerateFixResponse)
def generate_fix(req: GenerateFixRequest):
    """Synthesizes SQL and Python cleanups for a target check."""
    try:
        # Retrieve validation failure
        with memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM validation_failures 
                WHERE run_id = ? AND check_name = ?
                """,
                (req.run_id, req.check_name)
            )
            fail_row = cursor.fetchone()
            if not fail_row:
                raise HTTPException(status_code=404, detail="Failure record not found for the given run")
            
            fail_rec = dict(fail_row)
            
            # Retrieve run record
            cursor.execute("SELECT * FROM validation_runs WHERE id = ?", (req.run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="Run record not found")
                
            run_rec = dict(run_row)
            filename = run_rec["filename"]
            
        # Re-build CheckResult
        stats = {
            "null_count": fail_rec.get("failure_count", 0) if "null" in req.check_name else 0,
            "unique_count": 0,
            "mean": None,
            "std": None
        }
        
        check_res = CheckResult(
            check_name=fail_rec["check_name"],
            column=fail_rec["column_name"],
            status="FAIL",
            failure_count=fail_rec["failure_count"],
            total_count=fail_rec["total_count"],
            failure_percentage=fail_rec["failure_percentage"],
            severity=fail_rec["severity"],
            sample_bad_rows=json.loads(fail_rec["sample_bad_rows_json"]),
            column_stats=stats
        )
        
        # Load dataset to pass to generator
        data_dir = Path("data")
        data_path = data_dir / filename
        df = pd.DataFrame()
        if data_path.exists():
            df = pd.read_csv(data_path) if data_path.suffix.lower() == ".csv" else pd.read_parquet(data_path)
            
        # Run diagnostics
        analysis: RootCauseResult = analyzer.analyze(check_res, df)
        fix_result: FixResult = fix_generator.generate(analysis, df)
        
        # Save fix proposed to DB
        fix_id = memory.save_fix(
            fix={
                "fix_id": fix_result.fix_id,
                "pandas_fix": fix_result.pandas_fix,
                "sql_fix": fix_result.sql_fix,
                "confidence_score": fix_result.confidence_score,
                "pandas_fix_valid": fix_result.pandas_fix_valid,
                "was_applied": False,
                "improvement_percentage": 0.0
            },
            failure_id=fail_rec["id"],
            run_id=req.run_id
        )
        
        return GenerateFixResponse(
            fix_id=fix_id,
            pandas_fix=fix_result.pandas_fix,
            sql_fix=fix_result.sql_fix,
            confidence=fix_result.confidence_score,
            fix_valid=fix_result.pandas_fix_valid,
            root_cause=analysis.root_cause,
            business_impact=analysis.business_impact
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failure generating fix")
        raise HTTPException(status_code=500, detail=f"Failed to generate repair fixes: {str(e)}")


@app.post("/tools/apply_fix", response_model=ApplyFixResponse)
def apply_fix(req: ApplyFixRequest):
    """Executes the approved fix and outputs cleaned file to fixes/ directory."""
    if not req.approve:
        return ApplyFixResponse(
            status="Fix rejected by user",
            improvement_percentage=0.0,
            new_failure_count=0,
            cleaned_file_path=""
        )

    try:
        # Load fix details
        with memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM generated_fixes WHERE id = ?", (req.fix_id,))
            fix_row = cursor.fetchone()
            if not fix_row:
                raise HTTPException(status_code=404, detail="Proposed fix not found")
                
            fix_rec = dict(fix_row)
            
            if fix_rec.get("fix_valid", 0) == 0:
                raise HTTPException(status_code=400, detail="Cannot apply invalid or syntactically incorrect repair script.")

            # Load failure
            cursor.execute("SELECT * FROM validation_failures WHERE id = ?", (fix_rec["failure_id"],))
            fail_row = cursor.fetchone()
            if not fail_row:
                raise HTTPException(status_code=404, detail="Associated validation failure not found")
            fail_rec = dict(fail_row)

            # Load run
            cursor.execute("SELECT * FROM validation_runs WHERE id = ?", (req.run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="Associated run record not found")
            run_rec = dict(run_row)
            
        filename = run_rec["filename"]
        data_dir = Path("data")
        data_path = data_dir / filename
        
        if not data_path.exists():
            raise HTTPException(status_code=404, detail="Original raw dataset file not found on server disk.")
            
        # Read dataset
        df = pd.read_csv(data_path) if data_path.suffix.lower() == ".csv" else pd.read_parquet(data_path)
        df_copy = df.copy()
        
        # Apply patch securely
        pandas_code = fix_rec["pandas_fix"]
        # Extract script logic under headers
        clean_lines = [line for line in pandas_code.splitlines() if not line.startswith("#")]
        executable_script = "\n".join(clean_lines)
        
        # SECURITY FIX: Secure exec environment
        local_vars = {"df": df_copy}
        exec(executable_script, {"__builtins__": {}}, local_vars)
        df_cleaned = local_vars.get("df")
        
        # Save clean file
        fixes_dir = Path("fixes")
        fixes_dir.mkdir(exist_ok=True)
        cleaned_path = fixes_dir / f"cleaned_{filename}"
        
        if data_path.suffix.lower() == ".csv":
            df_cleaned.to_csv(cleaned_path, index=False)
        else:
            df_cleaned.to_csv(cleaned_path, index=False)
            
        # Re-run target check validation to measure improvement
        validator.load_rules_from_yaml(Path("rules/sales_rules.yaml"))  # Default fallback path
        check_res = validator.run_single_check(df_cleaned, fail_rec["check_name"])
        
        # Compute improvement rate
        before_count = fail_rec["failure_count"]
        after_count = check_res.failure_count
        improvement = 100.0
        if before_count > 0:
            improvement = float(round(((before_count - after_count) / before_count) * 100, 2))
            
        # Update fix outcome in memory
        memory.update_fix_outcome(req.fix_id, improved=(improvement >= 95.0), improvement_pct=improvement)
        
        # Log to agent memory
        memory.save_fix_attempt(
            check_name=fail_rec["check_name"],
            column=fail_rec["column_name"],
            root_cause="Cleaned via MCP Tools.",
            fix_code=executable_script,
            improvement=improvement,
            confidence=fix_rec["confidence_score"],
            is_success=(improvement >= 95.0)
        )
        
        return ApplyFixResponse(
            status="Fix successfully applied",
            improvement_percentage=improvement,
            new_failure_count=after_count,
            cleaned_file_path=str(cleaned_path.resolve())
        )

    except Exception as e:
        logger.exception("Failure applying fix script")
        raise HTTPException(status_code=500, detail=f"Repair script execution failed: {str(e)}")


@app.post("/tools/generate_yaml_rules", response_model=GenerateRulesResponse)
def generate_yaml_rules(req: GenerateRulesRequest):
    """Converts a natural language description into YAML configuration rules via Groq API."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Groq API key missing on server environment configuration.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    system_prompt = "You are a data quality assistant. You respond with valid YAML configuration rules ONLY."
    user_prompt = f"""
Convert the following plain English text into a valid data quality validator configuration rules list:
"{req.natural_language}"

The YAML structure must format as:
rules:
  - id: RULE_01
    name: "rule_description_name"
    column: "target_column"
    check_type: "null_check|unique_check|range_check|regex_check|datatype_check"
    severity: "critical|high|medium|low"
    params:
      min: 0
      max: 10
      pattern: "^[A-Z]+$"
      expected_type: "float64"
    description: "English explanation"

Ensure only valid YAML is generated. Do not warp it inside markdown code blocks.
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            raise Exception(f"Groq API error: {response.text}")
            
        yaml_content = response.json()["choices"][0]["message"]["content"].strip()
        
        # Clean markdown code blocks if any
        if yaml_content.startswith("```"):
            lines = yaml_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            yaml_content = "\n".join(lines).strip()
            
        parsed = yaml.safe_load(yaml_content)
        rule_count = len(parsed.get("rules", []))
        
        # Save generated rule
        rule_id = memory.save_rule(req.natural_language, yaml_content)
        
        return GenerateRulesResponse(
            yaml_rules=yaml_content,
            parsed_rules=parsed,
            rule_count=rule_count,
            rule_id=rule_id
        )

    except Exception as e:
        logger.exception("Error translating NLP instructions to YAML rules")
        raise HTTPException(status_code=500, detail=f"Failed to generate YAML: {str(e)}")


@app.post("/tools/chat_with_dataset", response_model=ChatWithDatasetResponse)
def chat_with_dataset(req: ChatWithDatasetRequest):
    """Answering user questions based on the dataset metrics and historical runs."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Groq API key missing.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        # Load run context from SQLite
        with memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM validation_runs WHERE id = ?", (req.run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="Validation run not found")
            run_rec = dict(run_row)
            
            # Load failures
            cursor.execute("SELECT * FROM validation_failures WHERE run_id = ?", (req.run_id,))
            failures = [dict(r) for r in cursor.fetchall()]

        # Build context
        context = {
            "filename": run_rec["filename"],
            "success_rate": run_rec["success_rate"],
            "total_checks": run_rec["total_checks"],
            "passed_checks": run_rec["passed_checks"],
            "failed_checks_count": run_rec["failed_checks"],
            "failures": [
                {
                    "check_name": f["check_name"],
                    "column": f["column_name"],
                    "failure_count": f["failure_count"],
                    "failure_percentage": f["failure_percentage"]
                }
                for f in failures
            ]
        }

        system_prompt = "You are a helpful data analyst explaining data quality issues found in a dataset."
        user_prompt = f"""
Context of validation results:
{json.dumps(context, indent=2)}

User Question: "{req.question}"

Please provide a concise answer referencing specific columns or metrics in the context.
"""

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            raise Exception(f"Groq API error: {response.text}")
            
        answer = response.json()["choices"][0]["message"]["content"].strip()
        
        return ChatWithDatasetResponse(
            answer=answer,
            relevant_data=context,
            sources=["validation_runs", "validation_failures"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during dataset chat")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
