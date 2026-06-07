"""Quick script to show all data stored in dq_guardian.db."""
import sqlite3
import pandas as pd

con = sqlite3.connect("database/dq_guardian.db")
cur = con.cursor()

# Tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("=== TABLES IN dq_guardian.db ===")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t}: {count} rows")

# Show validation_runs
print("\n=== VALIDATION RUNS (last 5) ===")
try:
    df = pd.read_sql("SELECT * FROM validation_runs ORDER BY timestamp DESC LIMIT 5", con)
    print(df.to_string(index=False))
except Exception as e:
    print(f"  (error: {e})")

# Show agent_memory
print("\n=== AGENT MEMORY (last 5) ===")
try:
    df2 = pd.read_sql("SELECT failure_pattern, root_cause, success_count, fail_count FROM agent_memory LIMIT 5", con)
    print(df2.to_string(index=False))
except Exception as e:
    print(f"  (error: {e})")

con.close()
