"""Debug: show the actual rules being generated and test regex against data."""
import sys, io
sys.path.insert(0, '.')

import pandas as pd
import re
from app.agent.auto_rules_generator import generate_rules_for_dataframe

raw = open('data/test1.csv', 'rb').read()
df = pd.read_csv(io.BytesIO(raw), skip_blank_lines=True)

rules = generate_rules_for_dataframe(df, use_ai=True)
print(f"Total rules: {len(rules['rules'])}\n")

for r in rules['rules']:
    print(f"  name={r['name']}")
    print(f"    check_type={r['check_type']}, col={r['column']}, severity={r['severity']}")
    if r.get('params'):
        p = r['params']
        print(f"    params={p}")
        if 'pattern' in p:
            pattern = p['pattern']
            try:
                c = re.compile(pattern)
                col_vals = df[r['column']].dropna().astype(str).head(5).tolist()
                matches = [bool(c.match(v)) for v in col_vals]
                print(f"    sample values: {col_vals}")
                print(f"    matches:       {matches}")
            except re.error as e:
                print(f"    !! COMPILE ERROR: {e}")
    print()
