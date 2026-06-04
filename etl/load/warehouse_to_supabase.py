import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

def load_to_supabase():
    load_dotenv()
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("[-] SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
        return
    
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"[-] Failed to initialize Supabase client: {e}")
        return
    
    root_dir = Path(__file__).resolve().parents[2]
    exports_dir = root_dir / "data" / "exports"
    
    # Ordered list to handle foreign key dependencies (dimensions first, facts later)
    tables = [
        "dim_job",
        "dim_department",
        "dim_store",
        "dim_shift",
        "dim_date",
        "dim_employee",
        "fact_employee_performance",
        "fact_payroll",
        "fact_attendance"
    ]
    
    print("[*] Starting upload to Supabase 'Analytical Data HR Analytics'...")
    
    for table in tables:
        csv_file = exports_dir / f"{table}.csv"
        if not csv_file.exists():
            print(f"[-] Missing file: {csv_file.name}")
            continue
            
        print(f"[*] Uploading {table} to Supabase...")
        df = pd.read_csv(csv_file)
        
        if df.empty:
            print(f"    - Table is empty, skipping.")
            continue
            
        # Convert NaN to None for JSON serialization compatibility
        df = df.replace({float('nan'): None})
        
        records = df.to_dict(orient="records")
        
        # Upsert in chunks to handle rate limits and payload sizes
        chunk_size = 1000
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            try:
                # Assuming tables have primary keys, upsert will update existing rows
                supabase.table(table).upsert(chunk).execute()
                print(f"    - Uploaded chunk {i//chunk_size + 1} ({len(chunk)} rows)")
            except Exception as e:
                print(f"    [!] Error uploading chunk {i//chunk_size + 1} for {table}: {e}")
                
    print("[+] Supabase upload complete!")

if __name__ == "__main__":
    load_to_supabase()
