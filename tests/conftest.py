"""Shared pytest fixtures for the DQ Guardian AI testing suite.

Defines mock dataframes, mock YAML rule paths, mock API responses, and transient database instances.
"""

import json
from pathlib import Path
from typing import Generator
import numpy as np
import pandas as pd
import pytest

from app.agent.memory_engine import MemoryEngine


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Generates a transient 20-row dataframe containing intentional errors for testing.

    Errors included:
    - Row 0-2: nulls in name, email, phone
    - Row 3-4: negative revenue
    - Row 5-6: invalid order_date format
    - Row 7-8: duplicate customer_ids
    """
    np.random.seed(42)
    rows = 20
    customer_ids = [f"CUST{i:03d}" for i in range(1, rows + 1)]
    # Introduce duplicates
    customer_ids[8] = customer_ids[7]
    
    names = [f"User {i}" for i in range(1, rows + 1)]
    names[0] = None
    
    emails = [f"user{i}@example.com" for i in range(1, rows + 1)]
    emails[1] = "bademail.com"  # missing @ and domain
    
    revenue = [100.0 * i for i in range(1, rows + 1)]
    revenue[3] = -50.0
    revenue[4] = 2000000.0  # Out of range
    
    quantity = [int(i % 5 + 1) for i in range(rows)]
    quantity[9] = -2  # outlier/negative
    
    order_dates = ["2023-01-15"] * rows
    order_dates[5] = "2027-12-31"  # future date
    order_dates[6] = "15/01/2023"  # invalid format
    
    phones = [f"555-010{i}" for i in range(rows)]
    phones[2] = None

    return pd.DataFrame({
        "customer_id": customer_ids,
        "name": names,
        "email": emails,
        "revenue": revenue,
        "quantity": quantity,
        "order_date": order_dates,
        "product_category": ["Electronics"] * rows,
        "region": ["North"] * rows,
        "status": ["Completed"] * rows,
        "phone": phones
    })


@pytest.fixture
def sample_rules_yaml(tmp_path: Path) -> Path:
    """Creates a temporary rules YAML file containing test validations."""
    rules_content = """
rules:
  - id: TEST_01
    name: "name_null_check"
    column: "name"
    check_type: "null_check"
    severity: "critical"
    description: "Name must not be null"
    
  - id: TEST_02
    name: "revenue_range_check"
    column: "revenue"
    check_type: "range_check"
    severity: "high"
    params:
      min: 0.0
      max: 1000000.0
    description: "Revenue between 0 and 1,000,000"
    
  - id: TEST_03
    name: "email_regex_check"
    column: "email"
    check_type: "regex_check"
    severity: "medium"
    params:
      pattern: "^[\\\\w.-]+@[\\\\w.-]+\\\\.\\\\w+$"
    description: "Email must be valid format"
"""
    rules_file = tmp_path / "test_rules.yaml"
    rules_file.write_text(rules_content, encoding="utf-8")
    return rules_file


@pytest.fixture
def mock_groq_response() -> dict:
    """Mock JSON response payload from the Groq completions endpoint."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "root_cause": "The dataset contains nulls in target columns.",
                        "business_impact": "Operational decisions rely on missing details.",
                        "confidence_score": 0.90,
                        "recommended_fix": "Impute missing emails using standard format.",
                        "pandas_fix": "df['email'] = df['email'].fillna('missing@example.com')",
                        "sql_fix": "UPDATE sales SET email = 'missing@example.com' WHERE email IS NULL"
                    })
                }
            }
        ]
    }


@pytest.fixture
def in_memory_engine(tmp_path: Path) -> Generator[MemoryEngine, None, None]:
    """Provides a fresh, isolated sqlite database memory engine for test cases."""
    db_file = tmp_path / "test_dq_guardian.db"
    engine = MemoryEngine(db_path=db_file)
    yield engine
