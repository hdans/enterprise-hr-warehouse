import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

def fetch_all_from_supabase(supabase: Client, table_name: str) -> pd.DataFrame:
    """Fetch all rows from a Supabase table handling pagination."""
    all_data = []
    page_size = 1000
    offset = 0
    
    while True:
        try:
            response = supabase.table(table_name).select("*").range(offset, offset + page_size - 1).execute()
            data = response.data
            if not data:
                break
            all_data.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
        except Exception as e:
            print(f"Error fetching from {table_name}: {e}")
            break
            
    return pd.DataFrame(all_data)

def transform_oltp_to_staging(base_dir: str):
    load_dotenv(os.path.join(base_dir, '.env'))
    url = os.environ.get("OLTP_SUPABASE_URL")
    key = os.environ.get("OLTP_SUPABASE_KEY")
    
    if not url or not key:
        print("Error: OLTP_SUPABASE_URL or OLTP_SUPABASE_KEY not found in .env")
        return
        
    supabase: Client = create_client(url, key)
    
    stg_dir = os.path.join(base_dir, "data", "staging")
    os.makedirs(stg_dir, exist_ok=True)

    tables_to_stage = [
        ("employees", "stg_employees.csv"),
        ("jobs", "stg_jobs.csv"),
        ("departments", "stg_departments.csv"),
        ("stores", "stg_stores.csv"),
        ("shifts", "stg_shifts.csv"),
        ("attendance_logs", "stg_attendance_logs.csv"),
        ("payroll_transactions", "stg_payroll_transactions.csv"),
        ("performance_logs", "stg_performance_logs.csv"),
    ]

    print("[*] Fetching OLTP data from Supabase to Staging...")

    for table_name, target_file in tables_to_stage:
        target_path = os.path.join(stg_dir, target_file)
        print(f"    -> Fetching {table_name}...")
        
        df = fetch_all_from_supabase(supabase, table_name)
        
        if not df.empty:
            df.to_csv(target_path, index=False)
            print(f"       Saved {target_file} ({len(df)} rows)")
        else:
            print(f"       Warning: Table {table_name} is empty or failed to fetch.")

    print("[+] Data Staging successfully completed. Files saved to data/staging/")

if __name__ == "__main__":
    base_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    transform_oltp_to_staging(base_directory)
