# Sample Data & Expected Outputs

This folder contains the sample datasets used to demonstrate the capabilities of **DQ Guardian AI**.

## Input Files

| File | Description | Purpose |
|---|---|---|
| `dirty_sales.csv` | Synthetic retail dataset containing deliberate errors (negative revenue, invalid emails, future dates). | Primary test file to demonstrate the full agent loop, root cause analysis, and fix generation. |
| `clean_sales.csv` | The clean, corrected version of the sales dataset. | Used as a reference point for post-fix validation. |
| `SETCbustimings_1_0.csv` | Real-world bus timings dataset. | Tests the system's ability to handle messy real-world strings and time data. |
| `routes.csv`, `route_stops.csv` | Supplementary real-world data. | Tests multi-column parsing and basic entity validation. |

## Expected Outputs Generated

When `dirty_sales.csv` is processed by the DQ Guardian agent using `rules/sales_rules.yaml`, the system is expected to generate the following outputs:

1. **Validation Report:** 
   - Fails `NullCheck` on the `email` column.
   - Fails `NegativeValueCheck` on the `revenue` column.
   - Fails `FutureDateCheck` on the `order_date` column.
   - Fails `RegexCheck` on phone numbers.

2. **Root Cause Analysis (AI Output):**
   - Explanation that revenue cannot be negative in a retail context.
   - Explanation that emails are missing domain information.

3. **Generated Fixes (Python & SQL):**
   - *Revenue:* Code to take the absolute value (`df['revenue'] = df['revenue'].abs()`) or drop negative rows.
   - *Dates:* Code to filter out dates > today.

4. **In-Memory Transformation:**
   - After user approval, the DataFrame is updated in memory, and the validation score improves from ~60% to ~95%+.

The final fixed datasets can be saved to the `fixes/` directory during an active session.
