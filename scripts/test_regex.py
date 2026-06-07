import re

patterns = [
    (r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', "email"),
    (r'^[+]?[0-9][0-9 .\-]{6,14}[0-9]$', "phone"),
]

tests = [
    ("john@gmail.com",   "valid email",   True),
    ("johngmail.com",    "missing @",     False),
    ("john@",           "bad email",      False),
    ("marygmail.com",   "no @",          False),
    ("9876543210",      "valid phone",   True),
    ("12345",          "too short",      False),
    ("abcdefghij",     "non-numeric",    False),
]

for pattern, label in patterns:
    print(f"\nPattern [{label}]: {pattern}")
    try:
        c = re.compile(pattern)
        for test_val, test_label, expected in tests:
            result = bool(c.match(test_val))
            status = "OK" if result == expected else "WRONG"
            print(f"  [{status}] '{test_val}' ({test_label}): {result}")
    except re.error as e:
        print(f"  COMPILE ERROR: {e}")
