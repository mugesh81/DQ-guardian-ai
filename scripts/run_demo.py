"""Demo script: runs the DQ Guardian AI agent loop and prints full output."""
import sys
sys.path.insert(0, '.')

from pathlib import Path
from app.agent.agent_loop import AgentLoop

print("Running full AI Agent Loop on dirty_sales.csv...")
print("(Uses Groq LLM for root cause analysis + fix generation)")
print("=" * 60)

loop = AgentLoop(
    data_path=Path("data/dirty_sales.csv"),
    rules_path=Path("rules/sales_rules.yaml"),
    max_iterations=1,   # 1 pass for fast demo
)
result = loop.run()

print(f"Run ID            : {result['run_id']}")
print(f"File              : {result['filename']}")
print(f"Rules Evaluated   : {result['rules_evaluated']}")
print(f"Rules Failed      : {result['rules_failed']}")
print(f"Initial Failures  : {result['initial_failure_count']} row-issues")
print(f"Final Failures    : {result['final_failure_count']} row-issues")
print(f"Improvement       : {result['overall_improvement_percentage']}%")
print(f"Fixes from Memory : {result['fixes_from_memory']}")
print(f"Fixes from AI     : {result['fixes_new']}")
print(f"Duration          : {result['total_duration_seconds']}s")
print(f"Status            : {result['status']}")
print()
print(f"--- PROPOSED FIXES ({len(result['proposed_fixes'])}) ---")
for i, fix in enumerate(result["proposed_fixes"], 1):
    rc = fix.get("root_cause", "N/A")
    code = fix.get("fix_code", "N/A")
    print(f"[{i}] {fix['check_name']} on [{fix['column']}]")
    print(f"    Root Cause  : {rc[:90]}{'...' if len(rc) > 90 else ''}")
    print(f"    Confidence  : {fix['confidence_score']:.2f}")
    print(f"    Status      : {fix['status']}")
    print(f"    Fix Code    : {code[:100]}{'...' if len(code) > 100 else ''}")
    print()
