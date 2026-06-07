# DQ Guardian AI 🛡️

> A fully autonomous, AI-powered Data Quality Agent built with Python, Groq LLM, FastAPI, and Streamlit.

---

## Overview

**DQ Guardian AI** is an end-to-end data quality platform that uses a 6-stage agentic loop to automatically detect, diagnose, and suggest fixes for data quality issues in CSV/Parquet datasets. It requires **no external validation frameworks** — the entire validation engine is built from scratch with `pandas` and `numpy`.

```
CSV/Parquet → Observe → Reason → Act → Validate → Learn → Repeat
                 ↑                                           |
                 └───────────────────────────────────────────┘
```

---

## Architecture

```
dataqualityagent/
├── app/
│   ├── agent/
│   │   ├── validator.py          # 12 custom check classes + ValidationEngine
│   │   ├── agent_loop.py         # 6-stage autonomous agent loop
│   │   ├── root_cause_analyzer.py# Groq LLM root cause diagnosis
│   │   ├── fix_generator.py      # AST-validated pandas/SQL fix generator
│   │   ├── confidence_engine.py  # Quantitative fix confidence scorer
│   │   └── memory_engine.py      # SQLite memory (5 tables)
│   ├── mcp/
│   │   └── server.py             # FastAPI SSE MCP server (port 8000)
│   └── dashboard/
│       └── streamlit_app.py      # 8-page Streamlit UI (port 8501)
├── rules/
│   ├── sales_rules.yaml          # 12 production-ready validation rules
│   └── rule_template.yaml        # Blank rule template with all check types
├── data/                         # Sample clean + dirty CSV datasets
├── database/                     # SQLite database (auto-created)
├── tests/                        # 78 pytest tests, 83–97% core coverage
├── scripts/
│   └── generate_sample_data.py   # Generates dirty/clean CSV fixtures
├── main.py                       # CLI entrypoint
├── requirements.txt
└── .env.example
```

---

## Validation Checks (12 Built-In)

| Check | Description | Severity |
|---|---|---|
| `NullCheck` | Detects nulls, empty strings, and whitespace | Critical / High |
| `UniqueCheck` | Flags all duplicate instances in a column | Critical |
| `DuplicateCheck` | Flags all rows after the first occurrence | High |
| `RangeCheck` | Validates numeric min/max bounds | High |
| `RegexCheck` | Validates string format via regex | Medium |
| `DatatypeCheck` | Ensures column types match expected dtype | Medium |
| `DateValidationCheck` | Parses date strings to a required format | High |
| `FutureDateCheck` | Rejects dates beyond current timestamp | Medium |
| `OutlierDetectionCheck` | Z-score based statistical outlier detection | Low |
| `RowCountCheck` | Validates dataset record count bounds | High |
| `ColumnExistenceCheck` | Ensures required columns are present | Critical |
| `NegativeValueCheck` | Flags negative values in numeric columns | Medium |

---

## Agent Loop (6 Stages)

```
STAGE 1 — OBSERVE   Load file, load YAML rules, run ValidationEngine
STAGE 2 — REASON    Sort failures by severity, query memory for known fixes
STAGE 3 — ACT       Call Groq LLM for root cause + generate fix code
STAGE 4 — VALIDATE  AST-parse fix, security-scan, confidence score
STAGE 5 — LEARN     Save results, fixes, success rates to SQLite memory
STAGE 6 — REPEAT    If success rate < threshold, iterate (max 3 cycles)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [Groq API Key](https://console.groq.com/) — free tier available

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 4. Generate sample data

```bash
python scripts/generate_sample_data.py
```

### 5. Run the agent (CLI)

```bash
# Validate dirty data against sales rules
python main.py run --file data/dirty_sales.csv --rules rules/sales_rules.yaml

# Specify a custom database path
python main.py run --file data/dirty_sales.csv --rules rules/sales_rules.yaml --db database/dq_guardian.db
```

### 6. Start the MCP API server

```bash
uvicorn app.mcp.server:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at: `http://localhost:8000/docs`

### 7. Start the Streamlit dashboard

```bash
streamlit run app/dashboard/streamlit_app.py --server.port 8501
```

---

## MCP API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/tools` | GET | List all 6 MCP tool schemas |
| `/tools/run_quality_check` | POST | Run validation on a CSV/Parquet file |
| `/tools/get_bad_rows` | POST | Retrieve sample failing rows |
| `/tools/generate_fix` | POST | AI-generated pandas + SQL fix |
| `/tools/apply_fix` | POST | Apply approved fix (user-gated) |
| `/tools/generate_yaml_rules` | POST | NLP → YAML rule conversion |
| `/tools/chat_with_dataset` | POST | Chat about quality results |
| `/memory/stats` | GET | SQLite memory statistics |
| `/runs` | GET | Recent validation run history |

---

## Security

- **Fix code is NEVER auto-applied.** All generated fixes require explicit `approve: true` from the user.
- `FixGenerator` uses `ast.walk()` to block:
  - Forbidden imports (`os`, `sys`, `subprocess`, etc.)
  - Dangerous function calls (`exec`, `eval`, `open`, `__import__`)
  - Dangerous SQL patterns (`DROP TABLE`, `TRUNCATE`, `DELETE FROM`, etc.)

---

## Memory (SQLite Schema)

| Table | Purpose |
|---|---|
| `validation_runs` | Summary of each validation run |
| `validation_failures` | Per-check failure records with sample bad rows |
| `generated_fixes` | Fix proposals with confidence scores |
| `agent_memory` | Fix attempt history (for REASON stage memory reuse) |
| `generated_rules` | AI-generated YAML rules from natural language |

---

## Testing

```bash
# Run all tests
python -m pytest -v

# Run with coverage report
python -m pytest --cov=app --cov-report=term-missing

# Run a specific test module
python -m pytest tests/test_validator.py -v
```

**Coverage summary (core modules):**

| Module | Coverage |
|---|---|
| `confidence_engine.py` | 97% |
| `fix_generator.py` | 90% |
| `agent_loop.py` | 88% |
| `root_cause_analyzer.py` | 87% |
| `validator.py` | 83% |
| `memory_engine.py` | 81% |

Total: **78 tests, 0 failures**

---

## LLM Configuration

- **Primary model:** `llama-3.3-70b-versatile`
- **Fallback model:** `llama-3.1-8b-instant`
- **On HTTP 429 (rate limit):** waits 60 seconds, then retries with fallback model
- **API failures never crash the agent** — fallback rule-based analysis kicks in

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLM calls |
| `DB_PATH` | No | SQLite DB path (default: `database/dq_guardian.db`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

---

## Assumptions & Limitations

### Assumptions
- Input data is in CSV or Parquet format with a single table structure.
- The user has basic knowledge of data validation rules (or relies on the AI for auto-generation).
- A valid Groq API key is available for AI features; otherwise, the system gracefully falls back to basic heuristic rules.
- Memory database (SQLite) is stored locally and has sufficient disk space.

### Limitations
- The system currently runs in memory (Pandas), which limits the dataset size to available RAM (typically < 2GB for smooth performance).
- The AI fix generation is deterministic but not infallible; human review is required before applying code (enforced by the UI).
- External database connections (e.g., direct to PostgreSQL/Snowflake) are not yet supported for direct ingestion; files must be uploaded.
- Rate limits on the Groq API may cause slight delays, though the system implements retry logic and fallbacks.

---

## License

MIT License — use freely for personal or commercial projects.
