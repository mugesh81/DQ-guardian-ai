# AI Usage Note

This document outlines how Artificial Intelligence (specifically Large Language Models) was utilized during the development and execution of the **DQ Guardian AI** project.

## What AI Helped With
- **Code Generation & Scaffolding:** AI assisted in generating boilerplate code for Streamlit components, FastAPI routes, and foundational Pandas data manipulation functions.
- **Validation Rule Generation:** We implemented an AI-powered auto-rules generator that profiles a DataFrame and automatically writes YAML validation rules, saving significant manual effort.
- **Root Cause Diagnosis:** The core agentic loop uses the `llama-3.3-70b-versatile` model via Groq to analyze validation failures (e.g., negative revenues, invalid emails) and explain *why* they happened in plain English.
- **Fix Generation:** AI was instrumental in dynamically generating Pandas Python code and SQL statements to remediate data issues, which are then syntax-checked and presented to the user.
- **Documentation:** AI tools helped draft comprehensive Knowledge Transfer documents, audit reports, and this very usage note.

## What AI Got Wrong (and How We Fixed It)
- **Dangerous Code Generation:** Initially, the LLM sometimes generated Python fixes containing dangerous functions like `os.system()` or `eval()`. 
  - *Fix:* We built a strict Abstract Syntax Tree (AST) validator (`FixGenerator`) to sandbox the generated code, blocking forbidden imports and functions.
- **Regex Hallucinations:** The AI occasionally produced overly complex or invalid regex patterns for email/phone validation that crashed the engine.
  - *Fix:* We implemented a `_sanitize_rules()` function that tests every generated regex against a known-good sample before applying it.
- **Rate Limiting:** Aggressive API calls during the agent loop often hit Groq's rate limits.
  - *Fix:* We implemented exponential backoff and a dual-model architecture, falling back to the faster `llama-3.1-8b` model or a local heuristic rule-based system if the API remained unavailable.

## Best Prompts Used

Here are the key prompts that drove the core intelligence of the application:

### 1. Root Cause Analysis Prompt
> "You are a data quality expert. A validation check failed on a dataset.
> Check: {check_name}, Column: {column_name}, Severity: {severity}
> Failures: {failure_count} out of {total_count} rows
> Sample bad rows: {sample_rows}
> Respond ONLY in JSON with: root_cause, business_impact, confidence_score, recommended_fix, pandas_fix, sql_fix"

### 2. Auto Rule Generation Prompt
> "You are a data validation expert. Inspect these columns and generate
> YAML validation rules. Column profiles: {column_profiles}
> Return a JSON object with a 'rules' array."

### 3. Rule Generator (Natural Language to YAML)
> "Convert this plain English rule description into a YAML validation
> rule for DQ Guardian. Description: {user_input}
> Return valid YAML only."

### 4. AI Chat Context Prompt
> "You are a data quality assistant. The user has just validated a file.
> Filename: {filename}, Total checks: {total}, Failed: {failed}
> Failed checks: {failed_checks}
> Answer the user's questions about these validation results."
