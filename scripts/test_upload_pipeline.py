"""End-to-end test: load test1.csv and validate with auto-generated rules."""
import sys, io
sys.path.insert(0, '.')

import pandas as pd
from pathlib import Path
from app.agent.auto_rules_generator import generate_rules_for_dataframe, profile_dataframe
from app.agent.validator import ValidationEngine
from app.agent.agent_loop import AgentLoop

# ── 1. Load test file ────────────────────────────────────────────────────────
raw = open('data/test1.csv', 'rb').read()
df = pd.read_csv(io.BytesIO(raw), skip_blank_lines=True)
print(f"Loaded test1.csv: {df.shape[0]} rows x {df.shape[1]} columns")
print(f"Columns: {list(df.columns)}")
print()

# ── 2. Profile ───────────────────────────────────────────────────────────────
prof = profile_dataframe(df)
for col, info in prof.items():
    print(f"  {col:15s} | type={info['inferred_type']:8s} | null={info['null_pct']:5.1f}% | unique={info['unique_count']}")
print()

# ── 3. Auto-generate rules (Groq AI) ─────────────────────────────────────────
rules = generate_rules_for_dataframe(df, use_ai=True)
n = len(rules.get('rules', []))
print(f"Generated {n} rules:")
for r in rules['rules']:
    print(f"  [{r['severity']:8s}] {r['name']:40s} | check={r['check_type']}")
print()

# ── 4. Run validation ────────────────────────────────────────────────────────
eng = ValidationEngine()
eng.load_rules_from_dict(rules)
report = eng.run_all_checks(df, filename='test1.csv')

print(f"=== VALIDATION REPORT ===")
print(f"Total checks : {report.total_checks}")
print(f"Passed       : {report.passed}")
print(f"Failed       : {report.failed}")
print(f"Success Rate : {report.success_rate:.1f}%")
print()
for r in report.results:
    icon = 'PASS' if r.status == 'PASS' else 'FAIL'
    print(f"[{icon}] {r.check_name:38s} | issues={r.failure_count:3d} ({r.failure_percentage:.1f}%) | {r.severity}")
