# AI Usage Note — DQ Guardian AI

**Project:** DQ Guardian AI
**Document Type:** AI Transparency & Collaboration Record
**Audience:** Internal Teams, HR, Project Reviewers

---

## Overview

This document provides a transparent account of how Artificial Intelligence — specifically Large Language Models (LLMs) — was utilized during the development and execution of the **DQ Guardian AI** project. It is intended to give reviewers, stakeholders, and team members a clear picture of where AI accelerated our work, where human expertise was essential, and how our team critically evaluated and corrected AI-generated output throughout the process.

> **Important:** AI was a collaborator, not a replacement. Every significant output in this project was reviewed, validated, refined, and owned by a human team member before being integrated.

---

## Where AI Contributed

### Code Generation & Scaffolding
AI helped accelerate the early stages of development by generating boilerplate code for Streamlit UI components, FastAPI route definitions, and foundational Pandas data manipulation functions. This freed up the engineering team to focus on higher-order design decisions and business logic rather than repetitive setup tasks.

### Validation Rule Generation
One of the most impactful AI applications in this project was an **auto-rules generator** that profiles an incoming DataFrame and automatically writes YAML validation rules. This capability saved significant manual effort — what previously took hours of handcrafted configuration could now be generated in seconds and refined by the team. A human review step was retained to ensure business relevance and accuracy.

### Root Cause Diagnosis
The core agentic loop uses the `llama-3.3-70b-versatile` model via the Groq API to analyze validation failures — such as negative revenue values or malformed email addresses — and explain *why* they likely occurred in plain English. This brought a layer of interpretability to data quality issues that would otherwise have required deep manual investigation.

### Fix Generation
AI played a key role in dynamically generating both **Pandas Python code** and **SQL statements** to remediate identified data issues. These fixes were syntax-checked through an Abstract Syntax Tree (AST) validator before being presented to the user, ensuring they were safe and actionable.

### Documentation
AI tools assisted in drafting Knowledge Transfer documents, audit reports, and this usage note. All documentation was reviewed and edited by team members to ensure accuracy, appropriate tone, and organizational alignment.

---

## Human Contributions & Oversight

While AI handled automation and pattern recognition, the real depth of this project came from the expertise and judgment of our human team:

- **Architecture decisions** — the overall system design, pipeline structure, and fallback mechanisms were entirely team-driven
- **Quality assurance** — every AI-generated rule, code block, and diagnosis was reviewed before deployment
- **Risk management** — the team proactively identified failure modes in AI outputs (see next section) and built robust safeguards
- **Prompt engineering** — crafting effective prompts required deep domain knowledge in both data quality and LLM behavior, and went through multiple human-led iterations
- **Stakeholder alignment** — business context, edge case handling, and final deliverables were shaped by the team's understanding of real-world data challenges

---

## What AI Got Wrong — and How We Fixed It

A critical part of working responsibly with AI is acknowledging its limitations. Our team encountered and resolved the following issues:

### Dangerous Code Generation
Early in development, the LLM occasionally generated Python fix suggestions containing potentially dangerous constructs such as `os.system()` or `eval()`.

**Our Fix:** We built a strict **Abstract Syntax Tree (AST) validator** inside the `FixGenerator` module that sandboxes all generated code, blocking forbidden imports and functions before they reach the user interface.

### Regex Hallucinations
The AI sometimes produced overly complex or syntactically invalid regular expressions for email and phone number validation that caused the engine to crash.

**Our Fix:** We implemented a `_sanitize_rules()` function that tests every AI-generated regex pattern against a known-good sample dataset before it is applied to live data. Invalid patterns are automatically rejected.

### Rate Limiting
During stress testing, aggressive API call patterns during the agentic loop frequently triggered Groq's rate limits, degrading the user experience.

**Our Fix:** We implemented **exponential backoff** retry logic and a **dual-model architecture** — falling back to the faster `llama-3.1-8b` model when primary limits were hit, and further falling back to a local, heuristic rule-based system when the API remained unavailable. This ensured resilience and uninterrupted service.

---

## Core Prompts Powering the Intelligence

Prompt design was a critical human-led activity. Below are the key prompts that drive the application's core intelligence, developed iteratively by the project team.

### 1. Root Cause Analysis Prompt
Used to diagnose *why* a validation check failed and recommend a course of action.

```
You are a data quality expert. A validation check failed on a dataset.
Check: {check_name}, Column: {column_name}, Severity: {severity}
Failures: {failure_count} out of {total_count} rows
Sample bad rows: {sample_rows}
Respond ONLY in JSON with: root_cause, business_impact, confidence_score,
recommended_fix, pandas_fix, sql_fix
```

### 2. Auto Rule Generation Prompt
Used to automatically profile a DataFrame and generate structured YAML validation rules.

```
You are a data validation expert. Inspect these columns and generate
YAML validation rules. Column profiles: {column_profiles}
Return a JSON object with a 'rules' array.
```

### 3. Natural Language to YAML Rule Converter
Enables non-technical users to describe a validation rule in plain English and have it converted to machine-readable YAML.

```
Convert this plain English rule description into a YAML validation
rule for DQ Guardian. Description: {user_input}
Return valid YAML only.
```

### 4. AI Chat Context Prompt
Powers the conversational assistant that helps users interpret their validation results after a file has been processed.

```
You are a data quality assistant. The user has just validated a file.
Filename: {filename}, Total checks: {total}, Failed: {failed}
Failed checks: {failed_checks}
Answer the user's questions about these validation results.
```

---

## AI Conversation Logs & References

The following links document real AI-assisted working sessions that contributed to this project. These are provided for transparency and audit purposes.

| Session | Description | Link |
|---------|-------------|------|
| Session 1 | Core development conversation | [View on Claude.ai](https://claude.ai/share/44e0516e-3b37-4d41-8267-b2056c7ab853) |
| Session 2 | Validation & rule generation work | [View on Claude.ai](https://claude.ai/share/b971825a-1509-4474-84b4-cf1be93235e5) |
| Session 3 | Fix generation & agentic loop | [View on Claude.ai](https://claude.ai/share/9e55977f-296b-4e28-b142-8fa48335bea5) |

---

## Summary

DQ Guardian AI is a product of genuine **human-AI collaboration**. The AI provided speed, scale, and pattern recognition; our team provided context, judgment, and accountability. Every point at which AI fell short became an opportunity to engineer a more robust, safe, and reliable system.

This project reflects our team's commitment to using AI responsibly — transparently documenting its role, actively correcting its failures, and ensuring that human expertise remained the final authority on every decision.

---

*Document maintained by the DQ Guardian AI Project Team.*
