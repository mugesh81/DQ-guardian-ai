# DQ Guardian AI — Complete Project Knowledge Transfer Document

> **Your complete guide to confidently explain, present, and defend this project to anyone.**

---

# PART 1 — PROJECT INTRODUCTION

## Project Name
**DQ Guardian AI** — Data Quality Guardian with Artificial Intelligence

## Project Purpose
DQ Guardian AI is an intelligent, automated data quality validation and remediation platform. It finds problems in your data, explains why those problems exist, and generates code to fix them — automatically.

## Problem Statement
Every organization — banks, hospitals, e-commerce companies, and retailers — stores millions of records in files and databases. These records are constantly uploaded, transferred, and processed by different systems. During this journey, data gets corrupted:
- Emails become blank or malformed
- Revenue values turn negative
- Dates are entered in wrong formats
- Customer IDs get duplicated
- Phone numbers contain letters instead of digits

**The problem:** Finding these issues manually takes hours. Fixing them requires writing code. Most businesses don't have the time, tools, or expertise to do this reliably.

## Why This Project Was Built
Data engineers and analysts waste 60-80% of their time just cleaning data instead of analyzing it (a well-known industry fact). There was no tool that could:
1. Automatically detect what rules a dataset needs
2. Find every violation of those rules
3. Explain *why* the violation happened (root cause)
4. Generate working Python and SQL code to fix it
5. Learn from past fixes and reuse them next time

DQ Guardian AI was built to solve all five problems in one unified system.

## Real-World Problem It Solves
Imagine a retail company uploads daily sales data. Their system accidentally enters:
- Revenue as `-500` (negative, which is impossible)
- Email as `john@@example` (invalid format)
- Order date as `2027-01-01` (future date, physically impossible)
- Customer ID `CUST001` appearing 50 times (duplicate)

Without DQ Guardian, a data analyst would open Excel or Python and manually hunt these issues. With DQ Guardian, they upload the file, click one button, and receive:
- A full report of every issue
- The exact rows that failed
- AI-generated explanation of what went wrong
- Ready-to-run Python code to fix it

## Target Users
- **Data Engineers**: Who build and maintain data pipelines
- **Data Analysts**: Who need clean data for reporting
- **Business Intelligence Teams**: Who build dashboards from raw data
- **Database Administrators**: Who manage production databases
- **Students and Researchers**: Learning data quality concepts
- **Any business**: That deals with CSV or tabular data files

## Business Value
- **Saves time**: Automated detection replaces hours of manual review
- **Reduces errors**: AI-generated fixes are tested before being applied
- **Builds institutional knowledge**: The memory system learns from every run
- **Audit trail**: Every validation run is recorded in a database
- **No-code access**: Business users can describe rules in plain English

## Industry Use Cases
- **Banking**: Validate transaction records for missing amounts, duplicate IDs
- **Healthcare**: Validate patient records for missing dates, invalid ages
- **Retail**: Validate sales data for negative quantities, future dates
- **HR Systems**: Validate employee records for invalid emails, phone numbers
- **E-Commerce**: Validate order data for revenue range violations
- **Insurance**: Validate policy data for missing coverage amounts

---

# PART 2 — PROJECT OVERALL WORKFLOW

## Complete Flow from Start to Finish

```
USER ACTION: Uploads a CSV or Parquet file
              ↓
SYSTEM: Reads file bytes, caches in session state
              ↓
AI PROCESS (Auto Rules Generator): 
  Calls Groq LLM (llama-3.3-70b-versatile)
  → Inspects column names, data types, sample values
  → Generates YAML validation rules automatically
  → Falls back to heuristic rules if AI unavailable
              ↓
AGENT LOOP STARTS (6 Stages):
  
  STAGE 1 — OBSERVE:
    ValidationEngine reads YAML rules
    Runs all 12 check types on the DataFrame
    Produces ValidationReport (pass/fail for each check)
              ↓
  STAGE 2 — REASON:
    Agent sorts failures by severity (critical first)
    For each failure: checks MemoryEngine for similar past fix
    Decides: reuse memory fix OR call AI for new analysis
              ↓
  STAGE 3 — ACT:
    For memory reuse: retrieves fix code from SQLite
    For AI path: calls RootCauseAnalyzer
      → Sends failure details + bad rows to Groq API
      → Gets JSON response with root cause + fix code
    FixGenerator validates syntax + security of fix code
              ↓
  STAGE 4 — VALIDATE:
    Applies fix code to a COPY of the DataFrame
    Re-runs the specific failed check
    Measures improvement percentage
    ConfidenceEngine calculates score (0-100)
    If improvement ≥ 95%: fix is marked APPROVED
              ↓
  STAGE 5 — LEARN:
    Saves fix attempt to SQLite agent_memory table
    Records: check name, column, root cause, fix code,
             improvement %, confidence, success/fail
              ↓
  STAGE 6 — REPEAT:
    Checks if all critical failures resolved
    If yes: exits loop early
    If no: runs up to max_iterations (default: 2)
              ↓
BACKEND PROCESS: 
  MemoryEngine saves run to validation_runs table
  Saves failures to validation_failures table
  Saves fixes to generated_fixes table
              ↓
DATABASE (SQLite):
  5 tables updated with full run details
              ↓
OUTPUT (Streamlit Dashboard):
  ✅ Pipeline complete! Quality improved by X%
  Shows: rules evaluated, rules failed,
         fixes generated, improvement %
  Navigation to all 8 pages
```

## Workflow Diagram

```
┌─────────────────────────────────────────────────────┐
│                    USER BROWSER                       │
│              http://localhost:8501                    │
└─────────────────────────┬───────────────────────────┘
                          │  Upload File + Click Run
                          ▼
┌─────────────────────────────────────────────────────┐
│              STREAMLIT FRONTEND                       │
│          (app/dashboard/streamlit_app.py)             │
│  - Reads file bytes                                   │
│  - Calls generate_rules_for_dataframe()              │
│  - Instantiates AgentLoop                            │
│  - Shows progress animation                          │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  AGENT LOOP                           │
│              (app/agent/agent_loop.py)               │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │Validator │  │RootCause │  │  FixGenerator    │   │
│  │ Engine   │  │ Analyzer │  │  + Confidence    │   │
│  └────┬─────┘  └─────┬────┘  └────────┬─────────┘   │
│       │              │                 │              │
│       └──────────────┴─────────────────┘             │
└─────────────────────────┬───────────────────────────┘
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
┌─────────────────┐         ┌─────────────────────────┐
│   GROQ AI API   │         │    SQLITE DATABASE        │
│  (External LLM) │         │   (database/dq_guardian) │
│                 │         │                           │
│ llama-3.3-70b   │         │  5 tables:                │
│ llama-3.1-8b    │         │  validation_runs          │
│ (fallback)      │         │  validation_failures      │
└─────────────────┘         │  generated_fixes          │
                            │  agent_memory             │
                            │  generated_rules          │
                            └─────────────────────────┘
```

---

# PART 3 — HIGH LEVEL ARCHITECTURE

## Frontend Layer
**Technology**: Streamlit (Python web framework)
**File**: `app/dashboard/streamlit_app.py` (1,363 lines)
**Pages**: 8 pages navigated via sidebar radio buttons
**Styling**: Custom CSS (Enterprise Light Theme) with Inter/JetBrains Mono fonts
**Charts**: Plotly (interactive line charts, pie charts, bar charts)

The frontend directly imports and calls backend Python modules. It is NOT a separate service — Streamlit runs the same Python process that runs the agent loop.

## Backend Layer
**Technology**: Python 3.13
**Modules in `app/agent/`**:
- `agent_loop.py` — Orchestrates all 6 stages
- `validator.py` — Runs all 12 data checks
- `root_cause_analyzer.py` — Calls Groq AI for diagnosis
- `fix_generator.py` — Validates and formats fix code
- `confidence_engine.py` — Scores fix quality
- `memory_engine.py` — Reads/writes SQLite database
- `auto_rules_generator.py` — Creates YAML rules automatically

## AI Layer
**External API**: Groq Cloud (https://api.groq.com)
**Primary Model**: `llama-3.3-70b-versatile` (large, accurate)
**Fallback Model**: `llama-3.1-8b-instant` (fast, used on rate limits)
**Use cases**:
- Generating validation rules from column inspection
- Diagnosing why a validation check failed
- Producing Python (Pandas) fix code
- Producing SQL fix statements
- Answering user questions in AI Chat
- Converting plain English to YAML rules

## Database Layer
**Technology**: SQLite3 (embedded, file-based)
**File**: `database/dq_guardian.db`
**Tables**: 5 (see Part 12 for full details)
**Thread Safety**: Uses Python threading.Lock() for concurrent access

## Validation Engine
**Technology**: 100% custom Python with Pandas + NumPy
**No external frameworks**: No Great Expectations, no Deequ
**12 Check Types**: Each is a separate Python class inheriting from BaseCheck
**YAML-driven**: Rules loaded from YAML files or auto-generated dicts

## Memory Engine
**What it stores**: Every validation run, every failure, every fix attempt
**Intelligence**: When a new failure matches a past pattern, it reuses the fix
**Learning**: Updates success/failure counts and average improvement per pattern
**Search**: Text search across root causes and fix scripts

## API Layer
**Technology**: FastAPI + Uvicorn
**File**: `app/mcp/server.py` (741 lines)
**Protocol**: HTTP REST + Server-Sent Events (SSE) for MCP
**Port**: 8000 (configurable via FASTAPI_PORT env var)
**Endpoints**: 6 tool endpoints + health + tools list + memory stats

## Data Flow Summary

```
CSV File → Pandas DataFrame → ValidationEngine 
                                    ↓
                              CheckResult[]
                                    ↓
                            RootCauseAnalyzer
                                    ↓
                           Groq AI (JSON response)
                                    ↓
                            FixGenerator (AST validation)
                                    ↓
                          exec() in sandbox → DataFrame updated
                                    ↓
                          ConfidenceEngine (score 0-100)
                                    ↓
                          MemoryEngine → SQLite
                                    ↓
                          Streamlit UI (charts, tables, code)
```

---

# PART 4 — COMPLETE USER JOURNEY

## Step 1: Opens the Application
User navigates to `http://localhost:8501`
- Streamlit renders the **Dashboard page** by default
- Sidebar shows 8 navigation options
- System status panel shows: Groq API status (green/red dot), SQLite Memory Active (always blue), Pipeline status (grey = no data yet)
- If no runs exist: shows a welcome screen with 🛡️ icon
- If runs exist: shows quality score trend chart, failed checks bar chart, recent runs table

## Step 2: Uploads a File
User clicks sidebar → **📤 Upload & Validate**
- Two file uploaders appear:
  - Dataset uploader (CSV or Parquet) — **required**
  - Rules YAML uploader — **optional** (AI generates rules if omitted)
- When user drops a CSV file:
  - File bytes are immediately cached in `st.session_state`
  - A **Dataset Profile** panel appears instantly showing:
    - File name, row count, column count, null cell count
    - Column schema table (column name, dtype, inferred type, null %, unique count, sample values)
    - Data preview (first 8 rows)

## Step 3: Runs Validation (Clicks "▶ Run AI Pipeline")
- Button is enabled only when a file is uploaded
- 6-stage progress bar appears with animation
- **Stage 1**: "Observing — inspecting uploaded dataset"
- **Auto Rule Generation**: If no YAML uploaded, calls Groq AI to generate rules
  - Shows: "✨ 24 validation rules auto-generated for 8 columns"
- **Stage 2**: Agent running — calls AgentLoop
- AgentLoop runs up to 2 iterations:
  - Validates data against all rules
  - Gets AI analysis for each failure
  - Tests fixes on data copies
  - Saves everything to SQLite
- Progress completes → Shows success banner:
  - "✅ Pipeline complete! Quality improved by 73.5%"
  - Metrics: Rules Evaluated | Rules Failed | Fixes Generated | Improvement %
- Button appears: "📊 View Validation Results →"

## Step 4: Reviews Results
User clicks **📊 Validation Results** in sidebar
- **KPI Row**: Total Checks | Passed | Failed | Success Rate
- **Pie Chart**: Pass/Fail split (green = pass, red = fail)
- **Results Table**: Every check with:
  - Check name, column, ✅/❌ status, failure count, fail %, severity (🔴🟠🟡🔵)
- **Severity Bar Chart**: How many failures at each severity level

## Step 5: Explores Failures
User clicks **🔍 Failure Explorer**
- Dropdown to select any failed check
- On selection:
  - Failure Count, Failure Rate %, Severity displayed as metrics
  - Column statistics (null count, unique count, mean, std dev)
  - Table of sample bad rows (up to 10 rows)
  - **Download button**: "📥 Download Bad Rows CSV"

## Step 6: Uses AI Suggestions
User clicks **🤖 AI Suggestions**
- Lists all proposed fixes from the agent run
- Each fix shown in an expandable card with:
  - Check name, column, confidence percentage (e.g., "85%")
  - Root cause explanation (from Groq AI)
  - Recommended fix in plain English
  - Confidence progress bar with tier (🟢 High / 🟡 Medium / 🔴 Low)
  - **🐍 Pandas Fix tab**: Python code with syntax highlighting
  - **🗄️ SQL Fix tab**: SQL UPDATE statement
  - Checkbox: "✔️ I have reviewed this fix and accept responsibility"
  - Button: "✅ Apply Fix to In-Memory DataFrame" (only enabled after checkbox)
  - On apply: runs code in sandbox → updates DataFrame → shows 🎈 balloons
  - **Export Dataset Panel**: After applying fixes, a panel at the bottom allows the user to click "⬇ Download Cleaned File" to export the fully fixed, clean dataset as a CSV.

## Step 7: Uses AI Chat
User clicks **💬 AI Chat**
- 5 quick-question buttons at top (clickable prompts)
- Chat interface with message history
- User types or clicks a question
- AI responds using validation context (file name, check results, failure details)
- "🗑️ Clear Chat" button available

## Step 8: Uses Rule Generator
User clicks **⚙️ Rule Generator**
- 4 example prompt buttons
- Text area for plain English input
- "⚡ Generate YAML Rules" button
- On click: calls Groq AI → returns YAML
- Shows: YAML code block + parsed rule summary table
- Buttons: "📥 Download YAML" | "💾 Save to Library" | "🚀 Use for Next Validation"

## Step 9: Uses Memory Center
User clicks **🧠 Memory Center**
- 3 KPI cards: Total Runs | Total Fixes | Avg Quality
- 3 tabs:
  - **📜 Run History**: Table of all past runs with export button
  - **🧠 Fix Memory**: Searchable knowledge base of fix patterns
    - Each record shows: failure pattern, success rate, root cause, success/fail counts, avg improvement, best fix script
  - **📋 Rule Library**: All saved YAML rule sets
    - Each shows YAML code + download button
  - **Danger Zone**: Wipe database (with confirmation checkbox)

---

# PART 5 — FRONTEND EXPLANATION

## Page 1: 🏠 Dashboard (Home)

**Purpose**: Bird's-eye view of all historical data quality runs

**Components**:
- **Page Hero**: Title "Platform Overview" with description
- **4 KPI Cards**:
  - Avg Quality Score (%)
  - Pipelines Run (count)
  - Fixes Generated (count)
  - Most Common Failure (check name + count)
- **Quality Score Trend Chart** (Plotly line chart, filled area): Shows how quality score evolved over time across all runs
- **Failed Checks by Run Chart** (Plotly bar chart, color-coded): Shows failure count per run
- **Recent Runs Table**: Last 10 runs with timestamp, filename, rows, passed, failed, success rate
- **Empty State**: If no runs exist, shows centered welcome card

**Data Source**: `memory.get_memory_stats()` and `memory.get_run_history()`

---

## Page 2: 📤 Upload & Validate

**Purpose**: The entry point for processing new datasets

**Components**:
- **Page Hero**: Title + description
- **2 File Uploaders** (side by side):
  - Left: Dataset (CSV/Parquet) — required
  - Right: Rules YAML — optional
- **Dataset Profile Panel** (appears after upload):
  - Row of 4 metric cards (file name, rows, columns, null cells)
  - Column schema table
  - Data preview (8 rows)
- **▶ Run AI Pipeline** button (primary, full width)
- **6-Stage Progress Indicator**: Icon + stage name + detail caption
- **Auto-rule generation info**: Shows how many rules were generated
- **Success Banner**: Green box with improvement percentage
- **Post-run metrics**: 4 st.metric() widgets
- **Navigation button**: "📊 View Validation Results →"

**Buttons**:
- `▶ Run AI Pipeline`: Triggers entire agent loop execution

**User Interactions**:
- Drag-and-drop or click to upload file
- Optional YAML upload
- Click Run → progress animation → results

---

## Page 3: 📊 Validation Results

**Purpose**: Detailed check-by-check quality report

**Components**:
- **4 KPI Cards**: Total Checks, Passed, Failed, Success Rate
- **Pie Chart** (left column): Pass vs Fail ratio with donut hole
- **Results Table** (right column): All checks in one table:
  - Check name, Column, Status (✅/❌), Issues count, Fail %, Severity (🔴🟠🟡🔵)
- **Severity Bar Chart**: Count of failures per severity level

**Data Source**: `st.session_state.validation_report` (ValidationReport object)

---

## Page 4: 🔍 Failure Explorer

**Purpose**: Deep inspection of individual check failures

**Components**:
- **Selectbox**: Dropdown listing all failed check names
- **3 Metric Widgets**: Failure Count, Failure Rate %, Severity
- **Column Stats Row**: Null count, Unique count, Mean, Std Dev
- **Bad Rows Table**: Actual data rows that failed the check (up to 10)
- **Download Button**: Export bad rows as CSV

**How to use**: Select a check → see exactly which rows are broken

---

## Page 5: 🤖 AI Suggestions

**Purpose**: Review and apply AI-generated fixes

**Components**:
For each fix (as expandable accordion/expander):
- **Header**: Icon + Check name + Column + Confidence %
- **Root Cause Info Box**: Blue info panel with AI explanation
- **Recommended Fix Warning Box**: Orange panel with plain English fix
- **Confidence Meter**: Progress bar + 🟢/🟡/🔴 tier label
- **2 Tabs**:
  - Pandas Fix: Python code block with syntax highlighting
  - SQL Fix: SQL code block with syntax highlighting
- **Review Checkbox**: User must agree before applying
- **Apply Button**: Executes fix in sandbox, updates in-memory DataFrame, shows 🎈 balloons
- **Export Dataset Panel**: At the bottom of the page, provides buttons to download the "Cleaned File" (if fixes were applied), the "Current CSV", or the "Original (pre-fix) CSV".

---

## Page 6: ⚙️ Rule Generator

**Purpose**: Convert plain English into YAML validation rules

**Components**:
- **4 Example Prompt Buttons**: Clickable shortcuts
- **Text Area**: Multi-line input for rule description
- **⚡ Generate YAML Rules button**: Calls Groq AI
- **2-column output panel**:
  - Left: Generated YAML code block
  - Right: Parsed rule summary table (name, column, type, severity)
- **3 Action Buttons**: Download YAML | Save to Library | Use for Next Validation

**Example Input**: "Revenue must be positive and email must match standard email format"
**Example Output**: YAML with `null_check`, `range_check`, `regex_check` rules

---

## Page 7: 💬 AI Chat

**Purpose**: Conversational interface about data quality results

**Components**:
- **5 Quick Question Buttons**: Clickable conversation starters
- **Message History**: Scrollable list of past messages with avatars (🧑 user, 🛡️ AI)
- **Chat Input Box**: Standard Streamlit chat input at bottom
- **Clear Chat Button**: Removes all messages

**Context Injection**: Every AI response includes:
- Validation report summary (check counts, success rate, filename)
- All failed checks with column names and failure counts
- Number of fixes generated and overall improvement %

---

## Page 8: 🧠 Memory Center

**Purpose**: View and manage the AI learning database

**Components**:
- **3 KPI Cards**: Total Runs, Total Fixes, Avg Quality %
- **3 Tabs**:

**Tab 1 — 📜 Run History**:
  - Full table of all validation runs
  - Columns: timestamp, filename, total_rows, passed/failed checks, success rate, duration, iterations
  - "📥 Export Run History" download button

**Tab 2 — 🧠 Fix Memory**:
  - Search box for filtering memory records
  - Each memory record expandable:
    - Root cause text
    - Success/failure count metrics
    - Average improvement %
    - Last seen timestamp
    - Best fix Python code

**Tab 3 — 📋 Rule Library**:
  - All YAML rule sets saved from Rule Generator
  - Each record expandable with YAML code + download
  - Shows creation date, times used
  - **Danger Zone**: Wipe all data (with confirmation)

---

# PART 6 — BACKEND EXPLANATION

## File: `main.py` (Root entry point)

**Why it exists**: CLI entry point for starting different modes

**What it does**:
- Parses command-line arguments (`--mode dashboard/mcp/agent`)
- For dashboard mode: calls `python -m streamlit run app/dashboard/streamlit_app.py`
- For MCP mode: starts FastAPI server with Uvicorn
- For agent mode: runs offline agent loop (headless, no UI)

**Inputs**: CLI arguments (`--mode`, `--data`, `--rules`)
**Outputs**: Starts appropriate server/process

**Command**: `python main.py --mode dashboard`

---

## File: `app/agent/validator.py` (Validation Engine)

**Why it exists**: The core data quality checking engine

**Architecture**: Abstract base class pattern
- `BaseCheck` (abstract): All checks inherit from this
- 12 concrete check classes: `NullCheck`, `UniqueCheck`, `DuplicateCheck`, `RangeCheck`, `RegexCheck`, `DatatypeCheck`, `DateValidationCheck`, `FutureDateCheck`, `OutlierDetectionCheck`, `RowCountCheck`, `ColumnExistenceCheck`, `NegativeValueCheck`
- `ValidationEngine`: Loads rules from YAML, runs all checks, produces report

**Key Data Classes**:
- `CheckResult`: Holds result of a single check (status, failure count, sample rows, column stats)
- `ValidationReport`: Aggregates all check results + overall pass rate

**Logic Flow**:
1. `ValidationEngine.load_rules_from_yaml(path)` → reads YAML → creates check objects
2. `ValidationEngine.run_all_checks(df)` → loops through all checks → calls `check.run(df)`
3. Each check returns a `CheckResult` with a boolean mask of failing rows
4. `run_all_checks` returns `ValidationReport` with all results

**Dependencies**: `pandas`, `numpy`, `re`, `yaml`, `abc`

---

## File: `app/agent/agent_loop.py` (The Orchestrator)

**Why it exists**: Coordinates all 6 stages of intelligent data quality resolution

**What it does**:
- Loads the data file (CSV or Parquet auto-detected)
- Runs all 6 stages in a loop (up to max_iterations)
- Uses ThreadPoolExecutor for parallel AI analysis (up to 5 workers)
- Manages a sandboxed exec() environment for fix code
- Compiles a final AgentRunResult

**Key Security Feature**: The `_SAFE_BUILTINS` dictionary restricts what the AI-generated code can do when executed. It explicitly excludes: `os`, `sys`, `subprocess`, `open`, `__import__`, `exec`, `eval`

**Inputs**: 
- `data_path`: Path to CSV/Parquet
- `rules_path` or `rules_dict`: Validation rules source
- `max_iterations`: How many times to loop (default: 3, dashboard uses 2)

**Outputs**: A dictionary with run_id, improvement %, proposed_fixes list, iteration count, duration

**Early Exit Conditions**:
- All failures resolved
- All critical failures resolved AND overall improvement ≥ 95%

---

## File: `app/agent/root_cause_analyzer.py` (AI Diagnosis)

**Why it exists**: Diagnoses WHY a validation check failed using AI

**What it does**:
- Builds a structured prompt with: check name, column, severity, failure count, column statistics, sample bad rows (as markdown table)
- Sends to Groq API (`llama-3.3-70b-versatile`)
- Parses JSON response to extract: root_cause, business_impact, confidence_score, recommended_fix, pandas_fix, sql_fix
- Falls back to `_rule_based_fallback()` if Groq unavailable

**Fallback Templates**: 12 templates covering all check types with deterministic fix code

**API Details**:
- Endpoint: `https://api.groq.com/openai/v1/chat/completions`
- Temperature: 0.1 (very deterministic, minimal creativity)
- Response format: JSON object mode
- Timeout: 30 seconds

**Retry Logic**:
1. Try primary model (`llama-3.3-70b-versatile`)
2. On HTTP 429 (rate limit): wait 1 second, try fallback model (`llama-3.1-8b-instant`)
3. On any failure: use rule-based local fallback

---

## File: `app/agent/fix_generator.py` (Fix Validator)

**Why it exists**: Ensures AI-generated code is safe to execute before presenting to users

**What it does**:
1. Parses fix code with Python's `ast.parse()` (Abstract Syntax Tree)
2. Walks the AST tree checking for forbidden patterns:
   - Forbidden imports: anything except pandas, numpy, datetime
   - Forbidden function calls: `exec`, `eval`, `open`, `input`, `__import__`, `getattr`, `setattr`
   - Forbidden library calls: `os.*`, `sys.*`, `subprocess.*`, `shutil.*`, `socket.*`, `builtins.*`
3. Checks SQL for dangerous patterns: DROP TABLE, TRUNCATE, DELETE FROM (with exception for duplicate fixes), GRANT, REVOKE, ALTER TABLE
4. Returns a `FixResult` with: fix code (with header comments), validity flags, security warnings, fix status

**Status Values**: `"valid"` | `"invalid"` | `"needs_review"`

---

## File: `app/agent/confidence_engine.py` (Fix Scorer)

**Why it exists**: Quantifies how trustworthy a generated fix is

**Scoring Algorithm** (returns 0.0–100.0):
1. **Base score**: `(improvement_pct / 100) × 60.0` — up to 60 points from measured improvement
2. **Syntax bonus**: `+20.0` if `ast.parse()` succeeds (valid Python)
3. **Complexity bonus**: `+10.0` if AST node count < 30 (simple fixes preferred), else `+5.0`
4. **Content check**: `-30.0` if fix is all comments/empty
5. **Severity adjustment**:
   - critical + improvement < 100%: `-10.0` penalty
   - low severity: `+5.0` bonus
6. Clipped to [0.0, 100.0]

---

## File: `app/agent/memory_engine.py` (The Brain's Long-Term Memory)

**Why it exists**: Persistent storage and retrieval of all intelligence the system has accumulated

**What it does**:
- Creates and manages SQLite database with 5 tables
- Saves every run, failure, fix, memory pattern, and rule
- Provides the `get_best_fix()` method that enables learning:
  - Looks up `agent_memory` by pattern `"check_name:column"`
  - Returns the fix if success rate ≥ 80%
- Thread-safe: uses `threading.Lock()` for all write operations
- Row factory: returns dict-like rows for easy JSON serialization

**Key Methods**:
- `save_run()`: Save validation run summary
- `save_failure()`: Save individual check failure
- `save_fix()`: Save generated fix to generated_fixes table
- `save_fix_attempt()`: Update or create agent_memory record
- `get_best_fix()`: Retrieve highest-performing past fix
- `get_memory_stats()`: Aggregate metrics for dashboard
- `search_memory()`: Text search across all memory records
- `save_rule()`: Save NL-generated YAML rules

---

## File: `app/agent/auto_rules_generator.py` (Automatic Rule Creator)

**Why it exists**: Eliminates the need for users to write YAML validation rules manually

**Two modes**:

**AI Mode** (when GROQ_API_KEY is set):
- Profiles the DataFrame (column types, null %, unique counts, sample values)
- Builds a prompt describing all columns
- Calls Groq API to generate a full rules JSON
- Sanitizes regex patterns (replaces broken patterns with tested safe ones)

**Heuristic Mode** (fallback, no AI needed):
- Uses column name hints to infer rules:
  - `email`, `mail` → regex_check + null_check
  - `id`, `key`, `uuid` → unique_check + duplicate_check + null_check (critical)
  - `phone`, `mobile`, `tel` → regex_check + null_check
  - `date`, `order_date` → date_validation + future_date_check
  - `revenue`, `salary`, `amount` → range_check + negative_value
  - `age`, `years` → range_check (0–120)
  - `quantity`, `qty` → range_check + negative_value
  - All numeric columns → outlier_detection + datatype_check

**Regex Safety**: Has a `_sanitize_rules()` function that tests every regex_check pattern against a known-good sample value and replaces broken ones with pre-tested safe patterns.

---

## File: `app/mcp/server.py` (FastAPI REST API)

**Why it exists**: Provides an API interface for programmatic/external access to all DQ Guardian capabilities

**What it does**: Exposes 6 MCP tool endpoints plus utility endpoints
Uses Pydantic for request/response validation
Uses FastAPI for routing and documentation
Uses SSE (Server-Sent Events) for streaming

**Dependencies**: `fastapi`, `uvicorn`, `sse_starlette`, `pydantic`, `requests`, `yaml`

---

# PART 7 — FILE UPLOAD SYSTEM

## How File Upload Works (Step by Step)

### 1. User Selects File
Streamlit's `st.file_uploader()` opens OS file picker.
Accepted types: `.csv`, `.parquet`, `.yaml`, `.yml`

### 2. File Bytes Cached
When file is selected:
```python
st.session_state["_cached_file_bytes"] = bytes(uploaded_data.getbuffer())
st.session_state["_cached_file_name"]  = uploaded_data.name
```
Why cached? Streamlit UploadedFile objects can only be read **once per render cycle**. Caching as bytes makes it re-readable on any button click.

### 3. Immediate Preview
The cached bytes are immediately parsed for the profile panel:
- `_read_bytes_to_df(raw_bytes, filename)` → handles CSV and Parquet

### 4. CSV Processing
```python
pd.read_csv(
    io.BytesIO(raw_bytes),
    skip_blank_lines=True,
    on_bad_lines="warn",     # Bad rows get a warning, not an error
    encoding_errors="replace" # Encoding issues replaced, not crashed
)
```

### 5. Parquet Processing
```python
pd.read_parquet(io.BytesIO(raw_bytes))
```
Requires `pyarrow` library.

### 6. Data Saved to Disk
Before running the agent, file bytes are saved to `data/` directory:
```python
data_dir = Path("data")
data_path = data_dir / cached_name
data_path.write_bytes(cached_bytes)
```
This is needed because `AgentLoop` takes a file path and needs to read the file during fix application.

### 7. Error Handling
- Empty file (0 bytes) → `ValueError` with friendly message
- Empty data (headers only) → `ValueError`
- No columns detected → `ValueError` (suggests checking delimiter)
- Unsupported format → `ValueError`
- Parquet read error → `ValueError` with original exception

---

# PART 8 — VALIDATION ENGINE

## Architecture
- **Pattern**: Strategy Pattern — each check is an independent class
- **Base class**: `BaseCheck` (abstract with abstract `run()` method)
- **Registry**: `RULE_MAPPING` dictionary maps YAML `check_type` strings to classes
- **Result class**: `CheckResult` dataclass — standard output for every check
- **Report class**: `ValidationReport` — aggregates all results

## Validation Flow
```
1. Load YAML → parse rules list
2. For each rule dict:
   a. Look up check class in RULE_MAPPING
   b. Instantiate class with (name, column, severity, params)
   c. Add to checks list
3. For each check in list:
   a. Call check.run(df)
   b. Returns CheckResult with bool mask of failing rows
   c. Count failures, calculate percentage
   d. Sample up to 10 bad rows
4. Aggregate into ValidationReport
```

## Rule Execution Process
Each check's `run()` method follows this pattern:
```python
1. Check if target column exists in DataFrame
2. Apply vectorized Pandas operations to find failing rows
3. Create boolean mask (True = row failed)
4. Call _create_result(df, failed_mask)
5. _create_result:
   a. Count how many True values in mask
   b. Calculate failure percentage
   c. Sample up to 10 bad rows (with NaN→None replacement)
   d. Get column statistics (null count, unique count, mean, std)
   e. Return CheckResult
```

---

## Check 1: NullCheck

**Purpose**: Find rows with missing, empty, or null values

**Logic**:
```python
failed_mask = col_data.isna()  # True for NaN/None
# For string columns, also check empty strings
if col_data.dtype == "object":
    str_cleaned = col_data.astype(str).str.strip()
    empty_mask = (str_cleaned == "") | (str_cleaned == "None") | (str_cleaned == "nan")
    failed_mask = failed_mask | empty_mask
```

**Example**: Email column has 5 rows with `NaN` → CheckResult(failure_count=5, status="FAIL")

**Output Fields**: check_name, column, status (FAIL/PASS/ERROR), failure_count, failure_percentage, severity, sample_bad_rows

---

## Check 2: UniqueCheck

**Purpose**: Ensure every value in a column is unique (no value appears more than once)

**Logic**:
```python
failed_mask = col_data.duplicated(keep=False)
# keep=False: marks ALL instances of duplicates as True
```

**Difference from DuplicateCheck**: UniqueCheck marks EVERY copy of a duplicate (e.g., if "CUST001" appears 3 times, all 3 are flagged). DuplicateCheck marks only the 2nd+ occurrence (keeps first).

**Example**: Column has values [A, B, A, C] → rows 0 and 2 both fail (A appears twice)

---

## Check 3: DuplicateCheck

**Purpose**: Find rows that are exact duplicates of earlier rows

**Logic**:
```python
failed_mask = col_data.duplicated(keep="first")
# keep="first": keeps first occurrence, marks all subsequent as True
```

**Example**: [A, B, A, C] → only row 2 fails (it's the duplicate of row 0)

---

## Check 4: RangeCheck

**Purpose**: Ensure numeric values fall within an inclusive [min, max] range

**Logic**:
```python
col_numeric = pd.to_numeric(df[column], errors="coerce")
failed_mask = col_numeric.isna()  # non-parseable values fail
if min_val is not None:
    failed_mask = failed_mask | (col_numeric < min_val)
if max_val is not None:
    failed_mask = failed_mask | (col_numeric > max_val)
```

**Parameters**: `params: {min: 0.0, max: 1000000.0}`

**Example**: Revenue column with value `-500` → fails (below min=0)

**Formula**: `FAIL if value < min OR value > max OR value is not numeric`

---

## Check 5: RegexCheck

**Purpose**: Validate string values against a regular expression pattern

**Logic**:
```python
compiled_regex = re.compile(pattern)
null_mask = df[column].isna()
match_mask = col_str.apply(lambda x: bool(compiled_regex.match(x)) if x != "None" else False)
failed_mask = (~match_mask) | null_mask
```

**Parameters**: `params: {pattern: "^[\\w.-]+@[\\w.-]+\\.\\w+$"}`

**Example**: Email "john@@example" → regex match fails → row flagged

**Common patterns**:
- Email: `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`
- Phone: `^[+]?[0-9][0-9 .\-]{6,14}[0-9]$`

---

## Check 6: DatatypeCheck

**Purpose**: Ensure values are of the expected data type

**Logic**:
```python
# If dtype already matches exactly → all pass
if str(col_data.dtype) == expected_type:
    return all_pass_result

# Otherwise check row-by-row
if expected_type in ("float64", "int64"):
    converted = pd.to_numeric(col_data, errors="coerce")
    failed_mask = converted.isna() & col_data.notna()  # was not null but couldn't parse
elif expected_type == "datetime64[ns]":
    converted = pd.to_datetime(col_data, errors="coerce")
    failed_mask = converted.isna() & col_data.notna()
elif expected_type == "bool":
    valid_bools = {True, False, 1, 0, "1", "0", "True", "False", "true", "false"}
    failed_mask = col_data.apply(lambda x: x not in valid_bools if x is not None else True)
```

**Parameters**: `params: {expected_type: "float64"}`

**Example**: Revenue column with value "abc" → can't convert to float64 → row fails

---

## Check 7: DateValidationCheck

**Purpose**: Ensure date strings match a specific format pattern

**Logic**:
```python
def is_invalid_date(val):
    if pd.isna(val): return True  # nulls fail
    try:
        datetime.strptime(str(val), date_format)
        return False  # parsing succeeded → valid
    except ValueError:
        return True   # parsing failed → invalid
        
failed_mask = col_data.apply(is_invalid_date)
```

**Parameters**: `params: {format: "%Y-%m-%d"}`

**Example**: Date "25-12-2023" → strptime with `%Y-%m-%d` fails → row flagged

---

## Check 8: FutureDateCheck

**Purpose**: Ensure dates are not in the future (past or today only)

**Logic**:
```python
parsed_dates = pd.to_datetime(col_data, errors="coerce", utc=False)
now_ts = pd.Timestamp.now().normalize()  # today at midnight

# Strict future dates fail
failed_mask = parsed_dates > now_ts
# Also fail unparseable non-null values
failed_mask = failed_mask | (parsed_dates.isna() & col_data.notna())
```

**Example**: Order date "2027-01-01" → greater than today → fails

**Why Important**: In sales data, orders in the future indicate data entry errors or system clock issues

---

## Check 9: OutlierDetectionCheck

**Purpose**: Find statistically extreme values using Z-score analysis

**Logic**:
```python
mean = col_numeric.mean()
std = col_numeric.std()
z_scores = (col_numeric - mean).abs() / std
failed_mask = z_scores > threshold  # default threshold = 3.0
```

**Formula**: `Z-score = |value - mean| / std_dev`
If Z-score > 3.0, the value is an outlier (lies 3 standard deviations from mean).

**Parameters**: `params: {threshold: 3.0}`

**Example**: Revenue values [100, 200, 150, 50000] → 50000 has z-score >> 3 → flagged

**Statistical Interpretation**: In a normal distribution, only 0.3% of values fall beyond 3 standard deviations. Values beyond this threshold are extreme outliers.

---

## Check 10: RowCountCheck

**Purpose**: Dataset-level check — ensure the file has the right number of rows

**Logic**:
```python
total_rows = len(df)
passed = min_rows <= total_rows <= max_rows
failed_mask = pd.Series(not passed, index=df.index)
# If fails: all rows are marked as failing (dataset-level violation)
```

**Parameters**: `params: {min_rows: 1, max_rows: 1000000}`

**Example**: Expected at least 100 rows, got 5 → all rows flagged → check FAILS

---

## Check 11: ColumnExistenceCheck

**Purpose**: Verify that an expected column actually exists in the dataset

**Logic**:
```python
exists = self.column in df.columns
failed_mask = pd.Series(not exists, index=df.index)
# If column missing: all rows fail (schema violation)
```

**Example**: Rule requires "order_id" column, but file doesn't have it → check FAILS

**Why Important**: Schema changes upstream break downstream processing silently

---

## Check 12: NegativeValueCheck

**Purpose**: Ensure numeric values are non-negative (≥ 0)

**Logic**:
```python
col_numeric = pd.to_numeric(df[column], errors="coerce")
failed_mask = col_numeric < 0.0
```

**Example**: Revenue column with `-500` → less than 0 → row fails

**Business Reason**: Revenue, quantity, age, and price can never be negative in most business domains

---

# PART 9 — AI ENGINE

## Which Model is Used
- **Primary**: `llama-3.3-70b-versatile` (Meta's LLaMA 3.3 70-billion parameter model)
- **Fallback**: `llama-3.1-8b-instant` (smaller, faster, used when rate-limited)
- **Provider**: Groq Cloud (not OpenAI — Groq uses custom hardware called LPUs for ultra-fast inference)

## Why Groq Was Chosen
1. **Speed**: Groq's LPU hardware generates responses in ~1-2 seconds vs 5-15 seconds for other providers
2. **Cost**: Has a generous free tier
3. **OpenAI-compatible API**: Same request format as OpenAI, easy to integrate
4. **JSON mode**: Supports `response_format: {type: "json_object"}` — forces the model to return valid JSON
5. **Reliability**: Has a fallback model (`llama-3.1-8b-instant`) on the same platform

## How Prompts are Created

### Root Cause Analysis Prompt
The prompt contains:
1. **System message**: "You are a senior data engineer specializing in data quality. You respond ONLY with valid JSON."
2. **User message** includes:
   - Check name and column name
   - Severity level
   - Failure count and percentage
   - Column statistics (null count, unique count, mean, std dev)
   - Sample bad rows as a markdown table
   - Exact JSON schema the response must follow
   - Explicit instruction: "Pandas script MUST modify df in-place, MUST NOT import anything"

### How Responses are Processed
1. Get raw string from `response.json()["choices"][0]["message"]["content"]`
2. Strip any markdown code fences (LLMs sometimes wrap JSON in ```json...```)
3. Parse with `json.loads()`
4. Extract fields: root_cause, business_impact, confidence_score, recommended_fix, pandas_fix, sql_fix
5. Return as `RootCauseResult` dataclass

---

## AI Rule Generation

**Input**: DataFrame profiling data (column names, types, null %, unique counts, samples)
**Process**:
1. `profile_dataframe()` generates metadata for all columns
2. `_build_ai_prompt()` creates a detailed prompt with column summary
3. Groq returns a JSON object with `{"rules": [...]}`
4. `_sanitize_rules()` validates all regex patterns
5. Returns `{"rules": [...]}` dictionary

**Example AI-generated rule**:
```json
{
  "id": "RULE_01",
  "name": "email_null_check",
  "column": "email",
  "check_type": "null_check",
  "severity": "critical",
  "params": {},
  "description": "Email must not contain null values"
}
```

---

## AI Fix Generation

**Input**: `CheckResult` (failure details) + DataFrame
**Process**:
1. Build prompt with failure metadata + sample bad rows
2. Call Groq API with JSON mode
3. Parse: root_cause, pandas_fix, sql_fix
4. Pass to `FixGenerator.generate()` for security validation
5. Pass to `ConfidenceEngine.score()` for confidence rating

**Example Groq Response**:
```json
{
  "root_cause": "Revenue column contains null values due to incomplete data entry...",
  "business_impact": "Missing revenue data prevents accurate financial reporting",
  "confidence_score": 0.92,
  "recommended_fix": "Fill null revenue values with column mean",
  "pandas_fix": "df['revenue'] = df['revenue'].fillna(df['revenue'].mean())",
  "sql_fix": "UPDATE sales SET revenue = (SELECT AVG(revenue) FROM sales) WHERE revenue IS NULL"
}
```

---

## AI Chat

**Input**: User question + validation context (report summary, failed checks)
**Process**:
1. Build context string from `st.session_state.validation_report` and `run_result`
2. Send: system prompt ("You are DQ Guardian AI...") + user question + context
3. Display streaming response in chat interface
4. Append to chat history

---

## Confidence Scoring

| Factor | Points | Notes |
|--------|--------|-------|
| Improvement rate | 0-60 | 100% improvement = 60 pts |
| Valid Python syntax | +20 | AST parse must succeed |
| Code simplicity | +10 or +5 | <30 AST nodes = simple |
| Empty code penalty | -30 | All-comment code |
| Critical + incomplete | -10 | Critical failures must be fully resolved |
| Low severity bonus | +5 | Less strict requirement |

---

# PART 10 — AGENT LOOP

## Overview
The 6-stage agent loop is the heart of DQ Guardian AI. It mimics how a human data engineer would think and act, but does it automatically and repeatedly.

## Stage 1: OBSERVE

**Input**: DataFrame + validation rules

**Processing**:
- Calls `ValidationEngine.run_all_checks(df)`
- Runs every check in parallel (Pandas vectorized operations)
- Produces a list of `CheckResult` objects

**Output**: `current_failures` — list of checks with status "FAIL"

**Analogy**: A doctor examining a patient and taking all vital measurements

---

## Stage 2: REASON

**Input**: `current_failures` list

**Processing**:
- Sorts failures by severity (critical=4, high=3, medium=2, low=1) — most severe first
- For each failure:
  - Calls `memory.get_best_fix(check_name, column)`
  - If memory returns a fix with success_rate ≥ 80% → "MEMORY_REUSE"
  - Otherwise → "NEEDS_AI_ANALYSIS"

**Output**: `reasoning_list` — each failure tagged with its resolution mode

**Analogy**: A doctor reviewing patient history to see if they've had this condition before

---

## Stage 3: ACT

**Input**: `reasoning_list`

**Processing** (parallel with ThreadPoolExecutor, 5 workers):
- For MEMORY_REUSE: retrieves cached fix code from SQLite
- For NEEDS_AI_ANALYSIS:
  - Calls `RootCauseAnalyzer.analyze(failure, df)` → Groq API call
  - Calls `FixGenerator.generate(analysis, df)` → security validation

**Output**: `completed_reasoning_list` — each failure now has fix_code, sql_fix, root_cause, explanation

**Analogy**: A doctor prescribing either a known treatment or consulting a specialist for new diagnosis

---

## Stage 4: VALIDATE

**Input**: fix_code, failure check

**Processing**:
```python
df_temp = df_current.copy()  # NEVER modify original data
exec(clean_code, _exec_globals, {"df": df_temp})  # Apply fix to copy
validation_res = validator.run_single_check(df_temp, failure.check_name)

# Calculate improvement
if validation_res.status == "PASS":
    improvement_pct = 100.0
else:
    improvement_pct = ((before_fail - after_fail) / before_fail) * 100

confidence = confidence_engine.score(fix_code, failure, improvement_pct)
success = (improvement_pct >= 95.0)
```

**Security**: `exec()` runs with `_SAFE_BUILTINS` — no `os`, `sys`, `open`, `subprocess`

**Output**: success flag, improvement percentage, confidence score

**Analogy**: A doctor testing whether the prescribed medicine actually works before giving it to the patient

---

## Stage 5: LEARN

**Input**: check_name, column, fix_code, improvement, confidence, is_success

**Processing**:
```python
memory.save_fix_attempt(
    check_name=failure.check_name,
    column=failure.column,
    root_cause=root_cause,
    fix_code=fix_code,
    improvement=improvement_pct,
    confidence=conf_score,
    is_success=success
)
```

**Database update**:
- If pattern exists: UPDATE agent_memory (increment success/fail count, update running average improvement)
- If new pattern: INSERT new row

**Output**: SQLite `agent_memory` table updated

**Analogy**: A doctor recording the treatment outcome in the patient's file for future reference

---

## Stage 6: REPEAT

**Input**: Current DataFrame (possibly improved by applied fixes)

**Processing**:
- Re-runs all validation checks on current DataFrame
- Calculates overall improvement percentage
- Checks exit conditions:
  1. `len(after_failures) == 0` → all clean, exit
  2. `criticals_resolved AND overall_improvement >= 95%` → good enough, exit
  3. `iteration >= max_iterations` → stop looping

**Output**: Either loops back to Stage 1 with improved data, or compiles final result

**Analogy**: A doctor re-checking vital signs after treatment to decide if more treatment is needed

---

## Agent Loop Diagram

```
┌────────────────────────────────────────────────────────┐
│                    AGENT LOOP                           │
│                                                         │
│  df_current ──► OBSERVE ──► failures[]                  │
│                    │                                     │
│               REASON                                     │
│          ┌─────────┴──────────┐                         │
│      MEMORY                  AI                         │
│      REUSE                ANALYSIS                      │
│          └─────────┬──────────┘                         │
│                   ACT                                    │
│              (parallel, 5 threads)                       │
│                    │                                     │
│               VALIDATE                                   │
│            (sandbox exec)                               │
│                    │                                     │
│                LEARN                                     │
│             (SQLite write)                              │
│                    │                                     │
│    ┌──── REPEAT ───┘                                    │
│    │    • All clean? EXIT                               │
│    │    • Criticals resolved? EXIT                      │
│    │    • Max iterations? EXIT                          │
│    └─────────────────────────                           │
└────────────────────────────────────────────────────────┘
```

---

# PART 11 — MEMORY ENGINE

## Why Memory Exists
Without memory, the system would call the expensive Groq AI API for every single failure, every single time, even for problems it has already seen and solved. This would be:
- Slow (API latency for every fix)
- Expensive (API usage costs)
- Repetitive (same errors in similar datasets)

Memory makes the system **intelligent** — it learns from experience.

## How Memory Learns

**Pattern Key**: `"{check_name}:{column}"` — e.g., `"null_check:email"` or `"range_check:revenue"`

When a fix is attempted:
1. Look up pattern in `agent_memory` table
2. **If found**: Update existing record
   - Increment success_count or fail_count
   - Recalculate running average improvement:
     ```python
     new_avg = ((prev_avg * (total_runs - 1)) + new_improvement) / total_runs
     ```
   - If fix succeeded: update `successful_fix` to the new code
3. **If not found**: Insert new record with initial stats

## How Fixes are Stored
```sql
agent_memory table:
  id                TEXT (UUID)
  failure_pattern   TEXT  -- e.g., "null_check:email"
  root_cause        TEXT  -- AI's explanation
  successful_fix    TEXT  -- Python code that worked best
  success_count     INT   -- how many times it worked
  fail_count        INT   -- how many times it failed
  avg_improvement   REAL  -- running average % improvement
  last_seen         TEXT  -- ISO timestamp
```

## How Fixes are Reused
In Stage 2 (REASON):
```python
past_fix = memory.get_best_fix(failure.check_name, failure.column)
if past_fix and past_fix.get("success_rate", 0.0) >= 80.0:
    # Reuse this fix — skip AI call
    mode = "MEMORY_REUSE"
```

**Success rate calculation**: `success_count / (success_count + fail_count) × 100`

## Complete Learning Workflow
```
Run 1: email has nulls
  → No memory found
  → Call Groq AI
  → Get fix: df['email'] = df['email'].fillna('MISSING')
  → Test fix → improvement: 100%
  → SAVE to memory: pattern="null_check:email", success_count=1, avg_improvement=100%

Run 2: different file, email has nulls again
  → memory.get_best_fix("null_check", "email")
  → Found! success_rate = 100% (≥ 80%)
  → REUSE: df['email'] = df['email'].fillna('MISSING')
  → No Groq API call needed!
  → UPDATE memory: success_count=2

Run 3: Same pattern, fix doesn't improve data
  → UPDATE memory: fail_count=1, success_count stays at 2
  → success_rate = 2/3 = 66.7% < 80% threshold
  → Next time: will call AI again for fresh analysis
```

---

# PART 12 — DATABASE

## Database Technology
**SQLite3**: An embedded relational database stored as a single file (`database/dq_guardian.db`). No separate database server needed.

## Table 1: `validation_runs`

**Purpose**: Records every validation pipeline execution

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID — unique run identifier |
| timestamp | TEXT | ISO 8601 datetime of execution |
| filename | TEXT | Name of the validated file |
| total_rows | INTEGER | Number of data rows |
| total_checks | INTEGER | How many rules were evaluated |
| passed_checks | INTEGER | How many rules passed |
| failed_checks | INTEGER | How many rules failed |
| success_rate | REAL | passed/total × 100 |
| duration_seconds | REAL | How long the run took |
| iterations | INTEGER | How many agent loop cycles ran |

---

## Table 2: `validation_failures`

**Purpose**: Detailed record of each individual check failure

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| run_id | TEXT (FK) | Links to validation_runs.id |
| check_name | TEXT | e.g., "email_null_check" |
| column_name | TEXT | e.g., "email" |
| check_type | TEXT | e.g., "null_check" |
| failure_count | INTEGER | How many rows failed |
| total_count | INTEGER | Total rows in dataset |
| failure_percentage | REAL | failure_count/total × 100 |
| severity | TEXT | "critical"/"high"/"medium"/"low" |
| sample_bad_rows_json | TEXT | JSON array of up to 10 bad rows |
| timestamp | TEXT | ISO 8601 |

---

## Table 3: `generated_fixes`

**Purpose**: Stores all proposed fix scripts (both applied and unapplied)

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| failure_id | TEXT (FK) | Links to validation_failures.id |
| run_id | TEXT (FK) | Links to validation_runs.id |
| pandas_fix | TEXT | Python code with header comments |
| sql_fix | TEXT | SQL UPDATE statement |
| confidence_score | REAL | 0.0 to 100.0 |
| fix_valid | INTEGER | 1=valid, 0=invalid (AST check) |
| was_applied | INTEGER | 1=applied, 0=not applied |
| improvement_percentage | REAL | Measured improvement % |
| timestamp | TEXT | ISO 8601 |

---

## Table 4: `agent_memory`

**Purpose**: The AI learning knowledge base — patterns and their best fixes

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| failure_pattern | TEXT | "check_name:column" e.g., "null_check:email" |
| root_cause | TEXT | Most recent AI root cause explanation |
| successful_fix | TEXT | Python code that worked best |
| success_count | INTEGER | Times this fix succeeded |
| fail_count | INTEGER | Times this fix failed |
| avg_improvement | REAL | Running average improvement % |
| last_seen | TEXT | Last time this pattern was encountered |

---

## Table 5: `generated_rules`

**Purpose**: Stores YAML rule sets created via the Rule Generator

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| natural_language_input | TEXT | The user's original plain English prompt |
| yaml_output | TEXT | The generated YAML rule configuration |
| created_at | TEXT | ISO 8601 |
| times_used | INTEGER | How many times this rule set was used |

---

## Schema Relationships

```
validation_runs (1)
       |
       |─── validation_failures (many) ─── generated_fixes (many)
       
agent_memory (independent — pattern-based key)

generated_rules (independent — user-created YAML storage)
```

---

# PART 13 — API EXPLANATION

## Base URL
`http://localhost:8000` (configurable via FASTAPI_PORT env var)

## Auto-Documentation
FastAPI auto-generates interactive docs at:
- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/redoc` (ReDoc)

---

## Endpoint 1: GET /health

**Purpose**: Check if server is running

**Request**: `GET /health`

**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-06-06T15:00:00Z"
}
```

---

## Endpoint 2: GET /tools

**Purpose**: List all available MCP tool endpoints with their input schemas

**Response**: Array of 6 tool objects with name, description, inputSchema

---

## Endpoint 3: POST /tools/run_quality_check

**Purpose**: Run full validation on a file path

**Request**:
```json
{
  "file_path": "data/sales.csv",
  "rules_path": "rules/sales_rules.yaml"
}
```

**Processing**:
1. Validates both file paths exist
2. Loads rules YAML
3. Reads CSV/Parquet file
4. Runs all validation checks
5. Saves run and failures to SQLite
6. Returns summary

**Response**:
```json
{
  "run_id": "uuid-string",
  "summary": {"total_checks": 12, "passed": 8, "failed": 4},
  "failed_checks": [...],
  "success_rate": 66.67,
  "total_rows": 1000,
  "duration_seconds": 1.23
}
```

---

## Endpoint 4: POST /tools/get_bad_rows

**Purpose**: Retrieve the sample failed rows for a specific check

**Request**:
```json
{
  "run_id": "uuid-string",
  "check_name": "email_null_check",
  "limit": 10
}
```

**Processing**: Queries `validation_failures` table by run_id + check_name, parses JSON bad rows

**Response**:
```json
{
  "bad_rows": [{"customer_id": "CUST001", "email": null, "revenue": 500.0}],
  "total_count": 47,
  "check_name": "email_null_check",
  "column": "email"
}
```

---

## Endpoint 5: POST /tools/generate_fix

**Purpose**: Generate AI-powered fix for a specific check failure

**Request**:
```json
{
  "run_id": "uuid-string",
  "check_name": "email_null_check"
}
```

**Processing**:
1. Retrieves failure record from SQLite
2. Reconstructs `CheckResult` object
3. Loads original data file
4. Calls `RootCauseAnalyzer.analyze()`
5. Calls `FixGenerator.generate()`
6. Saves fix to `generated_fixes` table

**Response**:
```json
{
  "fix_id": "uuid-string",
  "pandas_fix": "# Auto-generated fix...\ndf['email'] = df['email'].fillna('MISSING')",
  "sql_fix": "UPDATE sales SET email = 'MISSING' WHERE email IS NULL",
  "confidence": 85.0,
  "fix_valid": true,
  "root_cause": "Email column contains null values due to incomplete registration...",
  "business_impact": "Missing emails prevent customer communication"
}
```

---

## Endpoint 6: POST /tools/apply_fix

**Purpose**: Execute an approved fix and save the cleaned dataset

**Request**:
```json
{
  "run_id": "uuid-string",
  "fix_id": "uuid-string",
  "approve": true
}
```

**Processing**:
1. If `approve=false`: return rejection immediately
2. Loads fix script from SQLite
3. Validates fix_valid=1
4. Reads original data file
5. Executes pandas script in restricted env
6. Saves cleaned file to `fixes/cleaned_<filename>`
7. Re-runs original check to measure improvement
8. Updates fix outcome in SQLite
9. Saves fix attempt to agent_memory

**Response**:
```json
{
  "status": "Fix successfully applied",
  "improvement_percentage": 100.0,
  "new_failure_count": 0,
  "cleaned_file_path": "C:\\path\\to\\fixes\\cleaned_sales.csv"
}
```

---

## Endpoint 7: POST /tools/generate_yaml_rules

**Purpose**: Convert natural language to YAML validation rules

**Request**:
```json
{
  "natural_language": "Email must not be null and must match email format"
}
```

**Processing**: Calls Groq API with YAML generation prompt, parses result, saves to SQLite

**Response**:
```json
{
  "yaml_rules": "rules:\n  - id: RULE_01...",
  "parsed_rules": {"rules": [...]},
  "rule_count": 2,
  "rule_id": "uuid-string"
}
```

---

## Endpoint 8: POST /tools/chat_with_dataset

**Purpose**: Answer questions about validation results using AI

**Request**:
```json
{
  "run_id": "uuid-string",
  "question": "Which columns have the most issues?"
}
```

**Processing**:
1. Loads run and all failures from SQLite
2. Builds context JSON
3. Calls Groq with context + question
4. Returns AI answer

**Response**:
```json
{
  "answer": "Based on the validation report, the 'email' column has the most issues...",
  "relevant_data": {"filename": "sales.csv", "success_rate": 66.7, "failures": [...]},
  "sources": ["validation_runs", "validation_failures"]
}
```

---

# PART 14 — SECURITY

## 1. Sandboxed Code Execution

The most critical security feature is the restricted `exec()` environment.

**Problem**: AI generates Python code that gets executed in the system. A malicious or buggy AI response could generate `os.system("rm -rf /")` or `open("/etc/passwd")`.

**Solution**: The `_SAFE_BUILTINS` whitelist:
```python
_SAFE_BUILTINS = {
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "len": len, "abs": abs, "round": round, "range": range,
    # ... basic Python builtins only
}
# exec() is called with:
exec(code, {"__builtins__": _SAFE_BUILTINS, "pd": pd, "np": np}, {"df": df_temp})
```

Only `pd` (pandas) and `np` (numpy) are in globals. No `os`, `sys`, `subprocess`, `open`, `socket`.

## 2. AST Security Scanning

Before any fix is shown to the user, `FixGenerator` walks the Abstract Syntax Tree:
- Scans every `Import` node for forbidden modules
- Scans every `Call` node for forbidden functions
- Blocks: `exec`, `eval`, `open`, `input`, `__import__`, `getattr`, `setattr`
- Blocks library attributes: `os.*`, `sys.*`, `subprocess.*`, `shutil.*`, `socket.*`

## 3. Import Stripping

Before executing AI-generated code, all import lines are stripped:
```python
clean_code = "\n".join(
    line for line in fix_code.splitlines()
    if not line.strip().startswith("import ")
    and not line.strip().startswith("from ")
)
```
This prevents any `import os` that might slip through, since `pd` and `np` are already in the execution globals.

## 4. SQL Injection Protection

The `FixGenerator` checks SQL for dangerous patterns:
- `drop table`, `drop database`, `truncate`, `delete from`, `grant`, `revoke`, `alter table`
- Exception: `delete from` is allowed if the check is a duplicate check (deduplication requires deletion)

## 5. API Key Protection

The Groq API key is loaded from `.env` file (not hardcoded):
```python
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
```

The `.env` file is listed in `.gitignore` and never committed to version control. The `.env.example` file shows what keys are needed without actual values.

## 6. Database Thread Safety

SQLite is not thread-safe by default. The `MemoryEngine` uses `threading.Lock()`:
```python
db_lock = threading.Lock()
# All write operations:
with db_lock:
    with self._get_connection() as conn:
        # ... write operation
```

## 7. CORS Configuration (FastAPI)

The MCP server allows all origins (`allow_origins=["*"]`) for development. In production, this should be restricted to specific trusted domains.

---

# PART 15 — ERROR HANDLING

## What Can Go Wrong

| Scenario | How System Handles It |
|----------|----------------------|
| File is empty (0 bytes) | `ValueError` with friendly message before processing starts |
| File has no data rows | Caught in `_read_bytes_to_df()`, shown as Streamlit error |
| GROQ_API_KEY missing | Falls back to rule-based heuristics (no crash) |
| Groq API returns HTTP 429 | Waits 1 second, tries fallback model (llama-3.1-8b-instant) |
| Fallback model also fails | Uses `_rule_based_fallback()` — 12 deterministic templates |
| AI returns invalid JSON | Caught with `json.JSONDecodeError`, falls back to heuristics |
| Fix code has syntax error | Caught by `ast.parse()` in `FixGenerator`, marked "invalid" |
| Fix code fails exec() | Caught with try/except, improvement=0%, confidence=0% |
| Column doesn't exist | All checks return `status="ERROR"`, report shows check as ERROR |
| SQLite connection fails | Raises exception with error logged — no silent failures |
| Parquet file corrupt | `ValueError` from `pd.read_parquet()`, shown as Streamlit error |
| Network timeout to Groq | 30-second timeout → caught → falls back to heuristics |
| Regex pattern invalid | `_sanitize_rules()` replaces with safe pre-tested pattern |

## Recovery Mechanisms

### Groq API Fallback Chain:
```
Primary Model (llama-3.3-70b-versatile)
    ↓ (if fails)
Fallback Model (llama-3.1-8b-instant)
    ↓ (if fails)
Rule-Based Heuristics (local, no network)
```

### Fix Validation Fallback:
```
AI generates fix code
    ↓
FixGenerator validates syntax + security
    ↓ (if invalid)
Fix marked as "invalid" — not shown as applicable
    ↓
Agent loop records failure in agent_memory
    ↓
Next run: will try AI again with fresh context
```

### UI Error Display:
- All errors shown as `st.error()` (red box) in Streamlit
- Full Python traceback available in expandable section
- No crashes — all exceptions caught and displayed gracefully

---

# PART 16 — PROJECT DEMONSTRATION GUIDE

## 5-Minute Demo Flow

**Goal**: Show the core value proposition quickly

1. **(30 sec)** Open the app at http://localhost:8501. Point out the Dashboard showing system status (Groq connected, SQLite active).

2. **(30 sec)** Click "📤 Upload & Validate". Show the upload area. Mention: "No rules needed — AI auto-generates them."

3. **(1 min)** Upload a dirty CSV (test1.csv). Show the instant Dataset Profile panel: column types, null percentage, sample values.

4. **(1 min)** Click "▶ Run AI Pipeline". Watch the progress animation through all 6 stages. Say "This is our 6-stage agentic loop — Observe, Reason, Act, Validate, Learn, Repeat."

5. **(1 min)** Show success banner: "Quality improved by X%". Point out the 4 metrics: rules evaluated, failed, fixes generated, improvement.

6. **(1 min)** Navigate to "🤖 AI Suggestions". Open one fix card. Show root cause + Python code + SQL code. Say "The AI diagnosed the problem AND generated the fix code."

---

## 10-Minute Demo Flow

Everything in 5-min demo, plus:

7. **(1 min)** Navigate to "📊 Validation Results". Walk through the pie chart and results table. Point out severity badges.

8. **(1 min)** Navigate to "🔍 Failure Explorer". Select a failed check. Show the sample bad rows table. Download as CSV.

9. **(1 min)** Apply a fix (check the review checkbox, click Apply). Show the 🎈 balloons. Mention "The fix runs in a secure sandbox — no dangerous code can execute."

10. **(1 min)** Navigate to "⚙️ Rule Generator". Type "Email must be valid and revenue must be positive." Click Generate. Show YAML output.

---

## 15-Minute Demo Flow

Everything in 10-min demo, plus:

11. **(1 min)** Navigate to "💬 AI Chat". Click a quick question button. Show the AI responding with specific column names and metrics.

12. **(1 min)** Navigate to "🧠 Memory Center". Show the Run History tab. Then Fix Memory tab — explain "This is where the system stores what it learned. Next time it sees the same problem, it won't need to call the AI."

13. **(1 min)** Run the pipeline again on the same file. Point out that some fixes now come from "MEMORY_REUSE" — the system is faster and smarter than the first run.

14. **(1 min)** Open the FastAPI server (if running). Show http://localhost:8000/docs — the interactive Swagger UI. Say "This is our MCP API — external tools can use DQ Guardian programmatically."

15. **(1 min)** Summary: explain the 5 innovations: (1) auto rule generation, (2) AI root cause analysis, (3) automated fix generation, (4) sandboxed execution, (5) persistent memory learning.

---

## What Judges Care About

1. **AI Integration**: They want to see real AI doing real work — not just calling an API for display
2. **Innovation**: The memory learning system is the key differentiator
3. **Security**: The sandboxed exec() shows awareness of AI risks
4. **Architecture**: The 6-stage loop shows system thinking
5. **Completeness**: Working demo, not just a prototype
6. **Business Value**: Can they understand what problem this solves?

**Always lead with**: "This system finds data quality problems, explains why they happened, writes code to fix them, and learns from every run to get better over time."

---

# PART 17 — INTERVIEW AND JUDGE QUESTIONS (50 Q&A)

---

**Q1: What is DQ Guardian AI?**

**Simple**: It's a smart tool that checks your data files for problems, figures out why problems exist, and generates code to fix them automatically.

**Technical**: An agentic data quality pipeline built on Streamlit, FastAPI, Groq LLMs, and SQLite. It implements a 6-stage agent loop (Observe→Reason→Act→Validate→Learn→Repeat) to automatically detect, diagnose, and remediate data quality violations.

---

**Q2: What is a "data quality problem"?**

**Simple**: Think of it as a typo or mistake in a spreadsheet — like a phone number that's all letters, or a sales amount that's negative, or a customer email that's blank.

**Technical**: Constraint violations in tabular data — nullability, uniqueness, range bounds, regex pattern compliance, data type conformity, temporal validity, and statistical anomalies (outliers).

---

**Q3: What makes this project different from other data quality tools?**

Three innovations:
1. **Auto rule generation**: Most tools require users to write rules manually. We use AI to inspect columns and generate rules automatically.
2. **AI-powered root cause analysis**: Not just detecting issues, but diagnosing WHY they happened with domain-specific explanations.
3. **Persistent learning memory**: The system gets smarter over time by remembering what fixes worked and reusing them without calling the AI again.

---

**Q4: Why did you use Groq instead of OpenAI?**

**Simple**: Groq is much faster — responses in 1-2 seconds vs 5-15 seconds. It also has a free tier and uses Meta's open-source LLaMA models.

**Technical**: Groq uses custom Language Processing Units (LPUs) optimized for transformer inference, achieving significantly higher tokens-per-second throughput. It's OpenAI API-compatible, supports JSON response mode, and has a generous free tier. The llama-3.3-70b-versatile model performs comparably to GPT-4 class models for structured JSON tasks.

---

**Q5: What is the 6-stage agent loop?**

**Simple**: It's like a smart robot that: (1) looks at the data, (2) thinks about the problems, (3) generates fixes, (4) tests if fixes work, (5) learns from results, (6) repeats if needed.

**Technical**: An iterative agentic control loop: Observe (run all checks), Reason (prioritize by severity, check memory), Act (generate fixes in parallel threads), Validate (sandbox exec + re-check), Learn (update SQLite memory), Repeat (check exit conditions — all resolved OR 95%+ improvement).

---

**Q6: What is the Memory Engine?**

**Simple**: It's like the system's experience. Every time it fixes a problem, it remembers what worked. Next time it sees the same problem, it reuses that fix instead of asking the AI again.

**Technical**: A SQLite-backed pattern-matching knowledge base. Uses pattern key `"{check_name}:{column}"`. Stores success_count, fail_count, avg_improvement, and the best performing fix code. Returns cached fixes when success_rate ≥ 80%.

---

**Q7: How do you ensure AI-generated code is safe to run?**

**Simple**: Before running any AI code, we check it like a security guard. We only allow safe math operations and data manipulation — no file access, no internet access, no system commands.

**Technical**: Two-layer protection:
1. `ast.parse()` + AST walk: scans for forbidden imports (os, sys, subprocess) and forbidden calls (exec, eval, open, __import__)
2. Restricted `exec()` environment: `_SAFE_BUILTINS` whitelist + only `pd` and `np` in globals. All `import` statements stripped from code before execution.

---

**Q8: What are the 12 validation checks?**

NullCheck, UniqueCheck, DuplicateCheck, RangeCheck, RegexCheck, DatatypeCheck, DateValidationCheck, FutureDateCheck, OutlierDetectionCheck, RowCountCheck, ColumnExistenceCheck, NegativeValueCheck.

---

**Q9: How does the Auto Rules Generator work?**

**Simple**: It looks at your column names and data to guess what rules make sense. A column named "email" should be in email format. A column named "revenue" should be positive numbers.

**Technical**: 
- Calls Groq AI with a column profile (dtype, null%, unique count, sample values)
- Groq returns a JSON rules object
- Falls back to heuristic `_build_heuristic_rules()` using column name hints (_EMAIL_HINTS, _ID_HINTS, _SALARY_HINTS, _DATE_HINTS, etc.)
- `_sanitize_rules()` validates all regex patterns against known-good test values

---

**Q10: What is the Confidence Engine?**

**Simple**: It gives each fix a score from 0 to 100 to tell you how trustworthy it is. High score = very likely to work. Low score = should be reviewed carefully.

**Technical**: Weighted scoring: improvement_pct × 0.6 (up to 60 pts) + AST validity bonus (20 pts) + code simplicity (5-10 pts) − penalties for incomplete critical fixes and empty code. Final score clipped to [0, 100].

---

**Q11: What is an outlier in data quality?**

**Simple**: An outlier is a value so extreme it's probably wrong. Like if everyone's revenue is between $100-$1000, but one entry says $10,000,000 — that's suspicious.

**Technical**: Using Z-score method: `Z = |value - mean| / std_dev`. Values where Z > threshold (default 3.0) are flagged. In a normal distribution, only 0.3% of genuine values exceed 3 standard deviations — so high Z-scores indicate likely errors.

---

**Q12: How does the Validation Engine load rules?**

From YAML files via `load_rules_from_yaml(path)` or from Python dicts via `load_rules_from_dict(config)`. Each rule dict is mapped to a check class via `RULE_MAPPING` dictionary, instantiated with its parameters, and added to the checks list.

---

**Q13: What happens if the Groq API is down?**

System falls back to rule-based heuristics in `_rule_based_fallback()` — 12 deterministic templates covering all check types with pre-written fix code. The system never crashes or stops working due to external API unavailability.

---

**Q14: What is the YAML rules format?**

```yaml
rules:
  - id: RULE_01
    name: "email_null_check"
    column: "email"
    check_type: "null_check"
    severity: "critical"
    description: "Email must not be null"
  - id: RULE_06
    name: "revenue_range_check"
    column: "revenue"
    check_type: "range_check"
    severity: "high"
    params:
      min: 0.0
      max: 1000000.0
```

---

**Q15: Why use Streamlit instead of React/Vue?**

**Simple**: Streamlit lets us build a full web app using only Python. Since all our AI and data processing is in Python, we don't need a separate frontend language.

**Technical**: Streamlit eliminates the frontend/backend divide — the same Python code that runs the agent loop also renders the UI. This reduces complexity, speeds development, and ensures no API translation layer between data processing and display. For a data-focused application, Streamlit's native support for Pandas DataFrames, Plotly charts, and file uploaders is superior.

---

**Q16: What is FastAPI and why was it used?**

**Simple**: FastAPI lets us expose our system as an API — so other programs (like automation scripts or Claude AI) can use DQ Guardian without needing the browser interface.

**Technical**: FastAPI is a high-performance Python web framework based on Python type hints and Pydantic models. It auto-generates OpenAPI documentation, supports async, and is compatible with the MCP (Model Context Protocol) standard. SSE (Server-Sent Events) support via `sse_starlette` enables streaming responses.

---

**Q17: What is MCP?**

**Simple**: MCP stands for Model Context Protocol. It's a standard way for AI systems (like Claude AI) to call external tools. Our FastAPI server exposes DQ Guardian as an MCP tool.

**Technical**: MCP is a protocol developed by Anthropic that standardizes how LLMs call external functions (tools). By implementing MCP endpoints, DQ Guardian can be used by any MCP-compatible AI system as a data quality tool.

---

**Q18: What is the difference between UniqueCheck and DuplicateCheck?**

- **UniqueCheck** (`keep=False`): Marks **every** occurrence of a value that appears more than once. If "CUST001" appears 3 times, all 3 rows are flagged. Failure rate tells you the total scope of uniqueness violation.
- **DuplicateCheck** (`keep="first"`): Marks only the 2nd+ occurrence. The first instance is considered "original". Only the redundant copies are flagged.

---

**Q19: What files does the system support?**

CSV (comma-separated values) and Parquet (columnar binary format). Parquet requires `pyarrow` library. Detection is by file extension: `.csv`, `.parquet`, `.pq`.

---

**Q20: How is the app started?**

```bash
python main.py --mode dashboard   # Streamlit UI on port 8501
python main.py --mode mcp         # FastAPI API on port 8000
python main.py --mode agent --data data/sales.csv --rules rules/sales.yaml  # CLI
```

---

**Q21: What is session state in Streamlit?**

`st.session_state` is a dictionary that persists between Streamlit reruns (each user interaction causes a rerun). It stores: uploaded DataFrame, validation report, run results, chat history, YAML output, and applied fixes. Without session_state, all data would be lost on every button click.

---

**Q22: Why cache uploaded file bytes in session_state?**

Streamlit's `UploadedFile` object can only be read once per render cycle. After the first `.read()` or `.getbuffer()`, the file pointer is at the end. By caching as raw `bytes`, we can re-parse the file on any subsequent button click without needing the original upload object.

---

**Q23: How does ThreadPoolExecutor help performance?**

When multiple validation failures need AI analysis, the system spawns up to 5 parallel threads via `concurrent.futures.ThreadPoolExecutor(max_workers=5)`. Each thread makes an independent Groq API call. This reduces total wait time from `n × API_latency` to approximately `API_latency` for up to 5 simultaneous failures.

---

**Q24: What is Z-score and why is 3.0 the threshold?**

Z-score = `(value - mean) / standard_deviation`. It tells you how many standard deviations a value is from the average. In a normal distribution:
- Z > 1: top/bottom 32%
- Z > 2: top/bottom 5%  
- Z > 3: top/bottom 0.3% (extremely rare)

A Z-score above 3.0 means the value is so extreme it's almost certainly an error, not genuine data variation. This is the universally accepted threshold in statistics.

---

**Q25: What is the difference between confidence_score in RootCauseAnalyzer vs ConfidenceEngine?**

- **`RootCauseAnalyzer.confidence_score`**: The AI's self-reported confidence in its own diagnosis (0.0–1.0). Comes from the Groq JSON response field `"confidence_score"`. It's subjective — the AI estimates how certain it is.
- **`ConfidenceEngine.score()`**: An objective, calculated score (0.0–100.0) based on measurable factors: actual improvement percentage, code syntax validity, code complexity, and severity alignment. More reliable than the AI's self-assessment.

---

**Q26: What is the `@st.cache_resource` decorator?**

It tells Streamlit to create the decorated object **only once** per app instance and reuse it for all users and reruns. Used for `MemoryEngine` and `ValidationEngine` — expensive objects that involve database connections. Without caching, a new engine would be created on every user interaction.

---

**Q27: How does the AI Chat maintain context?**

`st.session_state.chat_history` stores all messages as `[{"role": "user"/"assistant", "content": "..."}]`. Each new question includes the current validation report context injected into the prompt, so the AI always has access to the latest data quality findings.

---

**Q28: What is the Rule Generator page and how does it work?**

Users type plain English (e.g., "Revenue must be positive"). The system sends this to Groq with a YAML template, receives a YAML string back, strips any markdown fences, sanitizes double-quoted regex patterns → single-quoted (YAML-safe), and displays the result. Users can download, save to library, or activate for the next validation run.

---

**Q29: What security issue does double-quoted regex in YAML cause?**

YAML double-quoted strings process escape sequences. A regex pattern like `"^[a-zA-Z0-9._%+\-]+@..."` will have `\-` interpreted as a literal hyphen by YAML — breaking the regex. Single-quoted strings in YAML are treated as raw strings. The code has a `_fix_dq_patterns()` function that converts `pattern: "..."` → `pattern: '...'` in all generated YAML.

---

**Q30: What does "APPROVED_PENDING_USER" status mean for fixes?**

A fix tested successfully in the sandbox (improvement ≥ 95%) but has NOT been applied to the actual data yet. It's waiting for the user to review and explicitly click the "Apply Fix" button with the review checkbox checked. This ensures human oversight before any data modification.

---

**Q31: What happens when you "Apply Fix" on the AI Suggestions page?**

The fix Python code runs in a restricted sandbox against a copy of the in-memory DataFrame. If successful, `st.session_state.df` is updated to the cleaned version. Balloons appear. The fix is NOT saved to disk from this page — it only updates the in-memory working copy during the current session.

---

**Q32: How does the system measure fix improvement?**

```python
before_fail = failure.failure_count  # from original validation
after_fail = validation_res.failure_count  # after applying fix to copy
improvement = ((before_fail - after_fail) / before_fail) * 100
```
If before=50 failures and after=0 failures: 100% improvement.
If before=50 failures and after=5 failures: 90% improvement.

---

**Q33: What is the `_col_lower()` function in auto_rules_generator?**

```python
def _col_lower(col: str) -> str:
    return col.lower().replace(" ", "_").replace("-", "_")
```
It normalizes column names for hint matching. "Order Date", "order-date", and "order_date" all become "order_date" for consistent hint lookup.

---

**Q34: How does the system determine if a column is numeric?**

```python
def _is_numeric(series: pd.Series) -> bool:
    return pd.to_numeric(series, errors="coerce").notna().mean() > 0.7
```
More than 70% of non-null values in the column must be parseable as numbers. This handles mixed-type columns gracefully.

---

**Q35: What are the 8 pages of the dashboard?**

1. 🏠 Dashboard (overview/home)
2. 📤 Upload & Validate (data upload + pipeline run)
3. 📊 Validation Results (check-by-check report)
4. 🔍 Failure Explorer (drill into bad rows)
5. 🤖 AI Suggestions (review + apply fixes)
6. ⚙️ Rule Generator (NL → YAML rules)
7. 💬 AI Chat (conversational interface)
8. 🧠 Memory Center (knowledge base viewer)

---

**Q36: What Python version is required?**

Python 3.13 (as indicated by the executable path in the system). Minimum Python 3.9+ is required for all features including `asynccontextmanager` and modern type hints.

---

**Q37: How does the "Wipe Database" feature work in Memory Center?**

User must first check the confirmation checkbox: "⚠️ I understand this will permanently delete all history." Then click "🗑️ Wipe Database". The code runs:
```python
for tbl in ["validation_runs", "validation_failures", "generated_fixes", "agent_memory", "generated_rules"]:
    cur.execute(f"DELETE FROM {tbl}")
```
This truncates all 5 tables but keeps the table structure (schema) intact.

---

**Q38: Why does FutureDateCheck use `.normalize()`?**

`pd.Timestamp.now().normalize()` strips the time component, setting the timestamp to midnight (00:00:00) of today. This prevents a date of "today" from being flagged as "future" when the comparison is done later in the same day.

---

**Q39: What is the `lifespan` function in FastAPI?**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing DQ Guardian AI MCP Server...")
    yield
    logger.info("Shutting down DQ Guardian AI MCP Server...")
```
An async context manager for startup/shutdown logging. Modern FastAPI uses this instead of the deprecated `@app.on_event("startup")` approach.

---

**Q40: How does the system handle a file with no columns?**

In `_read_bytes_to_df()`:
```python
if len(df.columns) == 0:
    raise ValueError(f"'{filename}' has no columns — check the delimiter.")
```
Shown as a Streamlit error with friendly guidance.

---

**Q41: What is `sqlite3.Row.row_factory`?**

Setting `conn.row_factory = sqlite3.Row` makes SQLite return rows that behave like both tuples AND dictionaries. You can access columns by name: `row["check_name"]` instead of `row[2]`. The code calls `dict(row)` to convert to plain Python dicts for JSON serialization.

---

**Q42: Why is `temperature: 0.1` used for AI calls?**

Temperature controls how creative/random the AI response is. `0.1` is very low → highly deterministic, consistent outputs. For code generation and root cause analysis, we want the AI to give precise, reliable answers rather than creative variations. Higher temperature would give different answers each run, making the system unpredictable.

---

**Q43: What is the `_SAFE_REGEX_OVERRIDES` dictionary?**

A dictionary of pre-tested, guaranteed-working regex patterns for common column types:
```python
_SAFE_REGEX_OVERRIDES = {
    "email":  r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    "phone":  r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
    "mobile": r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
    "tel":    r"^[+]?[0-9][0-9 .\-]{6,14}[0-9]$",
}
```
Used when AI generates broken regex patterns.

---

**Q44: How does the system know which fixes come from memory vs new AI analysis?**

In the agent loop result:
```python
"fixes_from_memory": self.fixes_from_memory_count,
"fixes_new": self.fixes_new_count,
```
Each fix in `fixes_generated_log` is tagged with its mode during the REASON stage (`"mode": "MEMORY_REUSE"` or `"NEEDS_AI_ANALYSIS"`).

---

**Q45: What would happen if a user uploaded a 10GB CSV file?**

The current system would attempt to load it entirely into memory using `pd.read_csv()`. This would likely cause an out-of-memory error. The system is designed for medium-sized datasets (up to a few hundred MB). For production scale, chunked reading with `pd.read_csv(chunksize=...)` would be needed.

---

**Q46: What is the purpose of the `run_id` across all tables?**

It's a UUID generated for each pipeline execution that links data across all 5 tables:
- `validation_runs.id` → primary key
- `validation_failures.run_id` → foreign key to runs
- `generated_fixes.run_id` → foreign key to runs

This allows: "show me all failures from this specific run" and "show me all fixes generated for this run's failures."

---

**Q47: What is the `skip_blank_lines=True` parameter in pd.read_csv?**

It makes Pandas skip completely empty lines in the CSV file. Without it, blank lines create rows of NaN values that would trigger false positive NullCheck failures. `on_bad_lines="warn"` prints a warning but continues instead of raising an exception for malformed rows.

---

**Q48: What is the business impact field in the root cause response?**

A 1-sentence description of the real-world consequence of the data quality issue. For example: "Missing emails prevent customer communication and CRM campaigns." This helps business stakeholders understand WHY fixing the issue matters, not just what the issue is technically.

---

**Q49: Can the system validate data in real-time (as it streams in)?**

Currently no — the system processes uploaded static files. For real-time/streaming validation, you would need to integrate with Apache Kafka or AWS Kinesis and process data in micro-batches. This is listed as a future improvement.

---

**Q50: How does the system avoid double-processing uploaded files?**

Using a cache key:
```python
file_key = f"_cached_file_{uploaded_data.name}_{uploaded_data.size}"
if st.session_state.get("_cached_file_key") != file_key:
    st.session_state["_cached_file_bytes"] = bytes(uploaded_data.getbuffer())
    st.session_state["_cached_file_key"] = file_key
```
Only re-reads bytes when the file name OR size has changed. Same file upload doesn't re-cache.

---

# PART 18 — VIVA PREPARATION

## Why Streamlit was Used

**Reason**: Streamlit is the ideal framework for AI/data applications built by Python developers.

**Arguments**:
1. **Single language**: No HTML/CSS/JavaScript needed — the entire app is Python
2. **Native data support**: Built-in rendering for Pandas DataFrames, Plotly charts, file uploaders
3. **Session state**: Easy state management for multi-step pipelines
4. **Rapid development**: A working dashboard in hours, not weeks
5. **Direct module import**: Can import and call `AgentLoop`, `MemoryEngine` directly

**Alternative considered**: Flask/React — would require a REST API between Python backend and JavaScript frontend, doubling the complexity. Not justified for a data-focused internal tool.

---

## Why FastAPI was Used (MCP Server)

**Reason**: FastAPI is the modern standard for Python APIs.

**Arguments**:
1. **Auto-documentation**: Generates Swagger UI automatically from type hints
2. **Pydantic validation**: Request/response schemas validated at runtime
3. **Performance**: Async support, built on Starlette
4. **MCP compatibility**: SSE support via `sse_starlette`
5. **OpenAPI standard**: Compatible with all modern API tools

**Alternative considered**: Flask — lacks async support and auto-documentation. Django — too heavy for a focused API.

---

## Why Groq was Used

**Reason**: Best balance of speed, cost, and capability.

**Arguments**:
1. **Speed**: LPU hardware → sub-2-second responses vs 10+ seconds for other providers
2. **Cost**: Generous free tier (no cost for development/demo)
3. **Model quality**: llama-3.3-70b performs at GPT-4 level for structured tasks
4. **JSON mode**: Forces structured JSON output — critical for code generation
5. **Fallback model**: Two models on same platform for reliability

**Alternative considered**: OpenAI GPT-4 — slower, expensive, no free tier. Google Gemini — different API format, no JSON mode at time of development. Local LLM (Ollama) — requires powerful GPU, impractical for deployment.

---

## Why SQLite was Used

**Reason**: Simplest persistent storage that meets all requirements.

**Arguments**:
1. **Zero configuration**: No server to install or manage
2. **Single file**: Entire database is `database/dq_guardian.db`
3. **Fully featured**: Supports foreign keys, transactions, complex queries
4. **Portable**: Database travels with the project
5. **Python native**: `sqlite3` is in Python standard library — no extra install

**Alternative considered**: PostgreSQL — overkill for single-user app, requires separate server process. MongoDB — NoSQL is worse for relational data like runs→failures→fixes. Redis — in-memory only, no persistence after restart.

---

## Why Pandas was Used for Validation

**Reason**: Industry standard for tabular data processing in Python.

**Arguments**:
1. **Vectorized operations**: Boolean mask operations are orders of magnitude faster than Python loops
2. **Type coercion**: `pd.to_numeric(errors="coerce")`, `pd.to_datetime(errors="coerce")` handle mixed types gracefully
3. **No external framework**: Custom validation engine — no dependency on Great Expectations or Deequ
4. **Flexibility**: Can validate any tabular data regardless of schema

**No external validation framework** was intentional:
- Great Expectations is complex, heavy, and has steep learning curve
- AWS Deequ requires Spark (JVM dependency)
- Custom engine gives full control over check logic and output format

---

## Trade-offs Made

| Decision | Trade-off |
|----------|-----------|
| Streamlit over React | Faster development, but less UI flexibility |
| SQLite over PostgreSQL | Zero-config, but no multi-user concurrent writes at scale |
| Groq over local LLM | No GPU required, but needs internet connection |
| In-memory DataFrame for fixes | Fast, but doesn't persist between app restarts |
| exec() sandbox | Allows AI code execution, but complex security to maintain |
| 2 agent iterations (dashboard) | Fast response, but may not fully resolve complex data |

---

# PART 19 — PROJECT STRENGTHS

## Innovation

1. **Auto Rule Generation**: First-class feature — no manual YAML writing required. AI inspects your data and creates appropriate rules automatically.

2. **Intelligent Memory System**: The persistent learning engine is a genuine differentiator. Unlike stateless tools, DQ Guardian improves with every run, reusing proven fixes without re-calling the AI.

3. **6-Stage Agentic Loop**: Implements a genuine agent pattern (not just API calls) — Observe, Reason, Act, Validate, Learn, Repeat — with proper exit conditions and iteration control.

4. **Dual-Mode Fix Output**: Every fix comes with BOTH Python (Pandas) and SQL code — covering both DataFrame-based and database-based workflows.

5. **Rule Generator from Natural Language**: Business users with no technical knowledge can describe rules in plain English and get production-ready YAML.

---

## Technical Strengths

1. **100% Custom Validation Engine**: No dependency on external validation frameworks. Full control over check logic, output format, and error messages.

2. **Security-First Design**: Multi-layer protection for AI code execution (AST scanning + restricted builtins + import stripping + SQL injection blocking).

3. **Graceful Degradation**: Every AI dependency has a fallback — Groq primary → Groq fallback → Rule-based heuristics. System never fails completely.

4. **Thread-Safe Database**: `threading.Lock()` ensures safe concurrent access to SQLite.

5. **Abstract Base Class Pattern**: Clean extensibility — adding a new validation check requires only creating a new class inheriting from `BaseCheck`.

---

## AI Strengths

1. **Structured Output**: Uses JSON mode to guarantee parseable AI responses.
2. **Context-Rich Prompts**: Includes column stats, sample bad rows, and check details for accurate AI analysis.
3. **Confidence Scoring**: Objective, measured confidence (not self-reported) using actual improvement data.
4. **Temperature Control**: 0.1 temperature for deterministic, reliable outputs.

---

## Business Strengths

1. **Zero Setup**: Upload a file, click run — no configuration, no rule writing, no code.
2. **Audit Trail**: Every run, failure, and fix permanently recorded in SQLite.
3. **Sandboxed execution**: Python's `ast` blocks malicious code paths
4. **Traceability**: All actions logged in SQLite
5. **Exportable Artifacts**: Cleaned CSV datasets, bad rows, run history, and YAML rules all downloadable.

---

# PART 20 — PROJECT LIMITATIONS

## Current Limitations

1. **Scale**: Loads entire dataset into memory. Large files (>1GB) may cause memory errors.

2. **Single-User**: SQLite's write lock means only one user can write at a time in multi-user scenarios.

3. **No Real-Time Processing**: Only processes static files. Cannot handle streaming data.

4. **Internet Required for AI**: Full AI features require Groq API access. Offline mode uses limited rule-based heuristics.

5. **No Data Versioning**: Cannot track changes to the same dataset across multiple uploads.

6. **Fix Not Auto-Applied**: Agent loop generates approved fixes but doesn't automatically write them back to the source file (by design — human oversight).

7. **No Column Relationship Checks**: Cannot validate cross-column rules (e.g., "end_date must be after start_date").

8. **No Custom Check Types**: Users cannot add new validation check types without modifying Python code.

---

## Future Improvements

1. **Chunked Processing**: Use Pandas chunk reading for large files
2. **PostgreSQL Support**: Replace SQLite for production multi-user deployment
3. **Streaming Integration**: Kafka/Kinesis connector for real-time validation
4. **Cross-Column Rules**: Implement composite check type in validation engine
5. **Version Control**: Track data changes across runs with diff reporting
6. **User Authentication**: Add login system for multi-tenant deployment
7. **Plugin Architecture**: Allow users to register custom check classes
8. **Auto-Apply Mode**: Option to automatically apply high-confidence fixes
9. **Email Reports**: Scheduled validation with email delivery of reports
10. **Cloud Storage**: S3/GCS file upload instead of local filesystem

---

## Scalability Considerations

| Component | Current Limit | Scalable Solution |
|-----------|--------------|-------------------|
| File processing | ~500MB RAM | Chunked Pandas + Dask |
| Database writes | 1 concurrent writer | PostgreSQL + connection pooling |
| AI calls | 5 parallel threads | Async/await + proper rate limiting |
| UI users | Single user | Deploy on Streamlit Cloud or Kubernetes |
| Rule storage | Single file | Distributed rule repository with versioning |

---

# PART 21 — FINAL PROJECT MASTERY GUIDE

## How to Explain This Project to Anyone

### To a Judge or Professor:
*"DQ Guardian AI is an agentic data quality platform that implements a 6-stage intelligent loop — Observe, Reason, Act, Validate, Learn, Repeat — to automatically detect, diagnose, and remediate data quality violations in CSV and Parquet files. It uses Groq LLMs for AI-powered root cause analysis and fix generation, implements a memory system that learns from every run, and provides both a web dashboard and a FastAPI MCP server. The key innovation is the combination of auto-rule generation, AI diagnosis, sandboxed fix execution, and persistent learning — making data quality autonomous rather than manual."*

### To a Business Client:
*"You upload your messy data file. Our system automatically figures out what rules your data should follow, finds all the violations, explains why each problem happened in plain English, and gives you Python and SQL code to fix it — all in one click. The more you use it, the smarter it gets."*

### To a Developer:
*"It's a Streamlit + FastAPI application where the core is a 6-stage agentic loop written in Python. The validation engine has 12 check types as separate classes inheriting from BaseCheck. Groq handles the AI — primary model is llama-3.3-70b-versatile with llama-3.1-8b-instant as fallback. Fix code is executed in a restricted exec() sandbox with AST scanning. Everything persists to SQLite via the MemoryEngine."*

### To an Interviewer:
*"The project demonstrates: (1) agent loop architecture, (2) custom validation engine with 12 check types, (3) Groq LLM integration with fallback chain, (4) security-aware code execution, (5) persistent learning via SQLite, (6) full-stack Python development with Streamlit and FastAPI."*

---

## The 5 Things You Must Always Know

1. **The 6 Stages**: Observe → Reason → Act → Validate → Learn → Repeat

2. **The 12 Checks**: Null, Unique, Duplicate, Range, Regex, Datatype, DateValidation, FutureDate, Outlier, RowCount, ColumnExistence, NegativeValue

3. **The 5 Tables**: validation_runs, validation_failures, generated_fixes, agent_memory, generated_rules

4. **The 3 AI Uses**: Rule generation, Root cause analysis, AI Chat (all via Groq llama-3.3-70b-versatile)

5. **The 3 Security Layers**: AST scanning (FixGenerator) + Restricted exec() builtins (AgentLoop) + Import stripping (before execution)

---

## Quick Reference Card

| What | Answer |
|------|--------|
| Frontend | Streamlit (localhost:8501) |
| Backend API | FastAPI (localhost:8000) |
| AI Provider | Groq Cloud |
| Primary Model | llama-3.3-70b-versatile |
| Fallback Model | llama-3.1-8b-instant |
| Database | SQLite (database/dq_guardian.db) |
| Validation Checks | 12 custom check classes |
| Agent Stages | 6 (Observe, Reason, Act, Validate, Learn, Repeat) |
| Database Tables | 5 |
| Dashboard Pages | 8 |
| API Endpoints | 8 (6 tools + health + tools list) |
| Max Agent Iterations | 3 (CLI), 2 (dashboard) |
| Confidence Scale | 0.0 to 100.0 |
| Memory Reuse Threshold | 80% success rate |
| Fix Approval Threshold | 95% improvement |
| Sandbox | exec() with _SAFE_BUILTINS + AST scan |

---

## Entry Point Reminder

```
Run: python main.py --mode dashboard
URL: http://localhost:8501
Start with: Upload & Validate page
Demo CSV: data/test1.csv
Demo Rules: rules/sales_rules.yaml
```

---

*End of Complete Knowledge Transfer Document — DQ Guardian AI*

*You now know this project better than almost anyone. Go present it with confidence.*
