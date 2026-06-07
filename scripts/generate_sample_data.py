"""Script to generate clean and dirty sales data for DQ Guardian AI validator testing.

This script creates two datasets:
1. data/clean_sales.csv - 500 completely valid sales records.
2. data/dirty_sales.csv - 500 records with exactly 130 known validation errors injected.
"""

import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("generate_sample_data")


def main() -> None:
    """Generate sample datasets for validation."""
    logger.info("Initializing sample data generation...")
    
    # Define directories
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Set seed for reproducibility
    np.random.seed(42)
    
    # Total rows
    n_rows = 500
    
    # 1. Generate Base Clean Data
    logger.info("Generating base clean dataset...")
    
    customer_ids = [f"CUST{i:03d}" for i in range(1, n_rows + 1)]
    
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    
    names = []
    emails = []
    phones = []
    
    for i in range(n_rows):
        fn = np.random.choice(first_names)
        ln = np.random.choice(last_names)
        name = f"{fn} {ln}"
        names.append(name)
        
        email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
        emails.append(email)
        
        phone = f"555-{np.random.randint(100, 999):03d}-{np.random.randint(1000, 9999):04d}"
        phones.append(phone)
        
    revenue = np.round(np.random.uniform(10.0, 5000.0, size=n_rows), 2)
    quantity = np.random.randint(1, 20, size=n_rows)
    
    # Clean order dates between 2023-01-01 and 2023-12-31
    base_date = pd.Timestamp("2023-01-01")
    order_dates = [
        (base_date + pd.Timedelta(days=int(np.random.randint(0, 365)))).strftime("%Y-%m-%d")
        for _ in range(n_rows)
    ]
    
    product_categories = ["Electronics", "Clothing", "Home", "Sports", "Books"]
    regions = ["North", "South", "East", "West"]
    statuses = ["Completed", "Pending", "Shipped", "Cancelled"]
    
    categories_col = np.random.choice(product_categories, size=n_rows)
    regions_col = np.random.choice(regions, size=n_rows)
    statuses_col = np.random.choice(statuses, size=n_rows)
    
    # Assemble Clean DataFrame
    df_clean = pd.DataFrame({
        "customer_id": customer_ids,
        "name": names,
        "email": emails,
        "revenue": revenue,
        "quantity": quantity,
        "order_date": order_dates,
        "product_category": categories_col,
        "region": regions_col,
        "status": statuses_col,
        "phone": phones
    })
    
    # Save Clean Dataset
    clean_path = data_dir / "clean_sales.csv"
    df_clean.to_csv(clean_path, index=False)
    logger.info(f"Saved clean dataset to {clean_path}")
    
    # 2. Inject Errors into Dirty Dataset
    logger.info("Injecting known errors into dirty dataset...")
    df_dirty = df_clean.copy()
    
    # Track the total number of affected rows with errors
    # Using distinct non-overlapping slices:
    # 50 rows: revenue negative OR > 1,000,000 (Indices 0 to 49)
    # - 25 rows negative, 25 rows > 1,000,000
    for idx in range(0, 25):
        df_dirty.at[idx, "revenue"] = -float(np.random.uniform(5.0, 500.0))
    for idx in range(25, 50):
        df_dirty.at[idx, "revenue"] = float(np.random.uniform(1000001.0, 2000000.0))
        
    # 30 rows: null values in email OR phone OR name (Indices 50 to 79)
    # - 10 rows null email, 10 rows null phone, 10 rows null name
    for idx in range(50, 60):
        df_dirty.at[idx, "email"] = None
    for idx in range(60, 70):
        df_dirty.at[idx, "phone"] = None
    for idx in range(70, 80):
        df_dirty.at[idx, "name"] = None
        
    # 20 rows: malformed email (missing @, no domain, spaces) (Indices 80 to 99)
    malformed_emails = [
        "john.smithexample.com",     # missing @
        "mary.j@.com",               # missing domain name
        "robert jones@example.com",  # spaces
        "alice@",                    # missing domain
        "bob@domain.",               # missing tld
    ]
    for idx in range(80, 100):
        df_dirty.at[idx, "email"] = malformed_emails[idx % len(malformed_emails)]
        
    # 15 rows: duplicate customer_id values (Indices 100 to 114)
    # We will duplicate customer_ids from existing records (e.g. from indices 200 to 214)
    for idx in range(100, 115):
        df_dirty.at[idx, "customer_id"] = df_dirty.at[idx + 100, "customer_id"]
        
    # 10 rows: invalid order_date (future date OR wrong format) (Indices 115 to 124)
    # - 5 rows future dates (e.g., 2027-12-31), 5 rows wrong formats (e.g. DD-MM-YYYY or invalid strings)
    invalid_dates = [
        "2027-12-31",      # Future date
        "2026-10-15",      # Future date
        "2027-01-01",      # Future date
        "2028-05-20",      # Future date
        "2026-08-30",      # Future date
        "31-12-2023",      # Wrong format (DD-MM-YYYY)
        "15/06/2023",      # Wrong format (DD/MM/YYYY)
        "2023.08.12",      # Wrong format
        "not-a-date",      # Invalid string
        "2023-02-31"       # Non-existent date
    ]
    for idx in range(115, 125):
        df_dirty.at[idx, "order_date"] = invalid_dates[idx - 115]
        
    # 5 rows: quantity = 0 or negative (outlier) (Indices 125 to 129)
    for idx in range(125, 128):
        df_dirty.at[idx, "quantity"] = 0
    for idx in range(128, 130):
        df_dirty.at[idx, "quantity"] = -int(np.random.randint(1, 10))
        
    # Save Dirty Dataset
    dirty_path = data_dir / "dirty_sales.csv"
    df_dirty.to_csv(dirty_path, index=False)
    logger.info(f"Saved dirty dataset to {dirty_path}")
    
    # Summary of injected errors
    total_errors_injected = 50 + 30 + 20 + 15 + 10 + 5
    print(f"Generated dirty_sales.csv: 500 rows, {total_errors_injected} known errors")


if __name__ == "__main__":
    main()
