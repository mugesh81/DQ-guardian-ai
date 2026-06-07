"""Audit helper script: checks schema, performance, imports, and security."""
import sqlite3
import os
import time
import importlib
import sys
from pathlib import Path

print("=" * 60)
print("DATABASE SCHEMA AUDIT")
print("=" * 60)
db_path = Path("database/dq_guardian.db")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Tables found: {tables}")
    for t in tables:
        cursor.execute(f"PRAGMA table_info({t})")
        cols = cursor.fetchall()
        print(f"\n  {t}:")
        for c in cols:
            print(f"    {c['name']} {c['type']} {'NOT NULL' if c['notnull'] else ''} {'PK' if c['pk'] else ''}")
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        print(f"  Row count: {count}")
    # Check indexes
    cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
    indexes = cursor.fetchall()
    print(f"\nIndexes: {[r[0] for r in indexes]}")
    conn.close()
else:
    print("DB file does not exist yet.")

print("\n" + "=" * 60)
print("IMPORT VERIFICATION")
print("=" * 60)
modules = [
    "app.agent.validator",
    "app.agent.agent_loop",
    "app.agent.memory_engine",
    "app.agent.root_cause_analyzer",
    "app.agent.fix_generator",
    "app.agent.confidence_engine",
    "app.mcp.server",
]
for mod in modules:
    try:
        importlib.import_module(mod)
        print(f"  OK  {mod}")
    except Exception as e:
        print(f"  FAIL {mod}: {e}")

print("\n" + "=" * 60)
print("PERFORMANCE TEST")
print("=" * 60)
import pandas as pd
import numpy as np
from app.agent.validator import ValidationEngine

engine = ValidationEngine()
engine.load_rules_from_yaml(Path("rules/sales_rules.yaml"))

for n_rows in [500, 10_000, 100_000]:
    np.random.seed(42)
    df = pd.DataFrame({
        "customer_id": [f"CUST{i:06d}" for i in range(n_rows)],
        "email": [f"user{i}@example.com" for i in range(n_rows)],
        "revenue": np.random.uniform(0, 100000, n_rows),
        "quantity": np.random.randint(1, 100, n_rows),
        "order_date": ["2023-06-15"] * n_rows,
        "phone": [f"+1555{i:07d}" for i in range(n_rows)],
    })
    t0 = time.perf_counter()
    report = engine.run_all_checks(df, filename=f"perf_{n_rows}.csv")
    elapsed = time.perf_counter() - t0
    print(f"  {n_rows:>8} rows: {elapsed:.3f}s  success={report.success_rate:.1f}%")

print("\n" + "=" * 60)
print("REQUIREMENTS CHECK")
print("=" * 60)
req_file = Path("requirements.txt")
for line in req_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    pkg = line.split(">=")[0].split("==")[0].split("~=")[0].strip()
    try:
        importlib.import_module(pkg.replace("-", "_").lower())
        print(f"  OK  {line}")
    except ImportError:
        # Try alternate names
        alt = pkg.lower().replace("-", "")
        try:
            importlib.import_module(alt)
            print(f"  OK  {line} (as {alt})")
        except:
            print(f"  MISS {line}")
    except Exception as e:
        print(f"  ERR {line}: {e}")
