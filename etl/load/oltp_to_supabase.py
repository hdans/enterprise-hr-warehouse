import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

def load_oltp_to_supabase():
    # Load .env from project root
    root_dir = Path(__file__).resolve().parents[2]
    load_dotenv(root_dir / '.env')
    
    url = os.environ.get("OLTP_SUPABASE_URL")
    key = os.environ.get("OLTP_SUPABASE_KEY")
    
    if not url or not key:
        print("[-] OLTP_SUPABASE_URL or OLTP_SUPABASE_KEY not found in environment variables.")
        return
    
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"[-] Failed to initialize Supabase client: {e}")
        return
    
    base_dir = root_dir / "data" / "oltp"
    master_dir = base_dir / "master"
    txn_dir = base_dir / "transactional"
    
    # Ordered list to handle foreign key dependencies
    files_to_import = [
        # Master Data
        (master_dir / "departments.csv", "departments"),
        (master_dir / "jobs.csv", "jobs"),
        (master_dir / "stores.csv", "stores"),
        (master_dir / "shifts.csv", "shifts"),
        (master_dir / "employees.csv", "employees"),
        
        # Transactional Data
        (txn_dir / "attendance_logs.csv", "attendance_logs"),
        (txn_dir / "payroll_transactions.csv", "payroll_transactions"),
        (txn_dir / "performance_logs.csv", "performance_logs"),
    ]
    
    print("[*] Starting OLTP upload to Supabase via REST API...")
    
    for csv_file, table in files_to_import:
        if not csv_file.exists():
            print(f"[-] Missing file: {csv_file.name}")
            continue
            
        print(f"[*] Uploading {table} to Supabase...")
        
        try:
            # We process large files in chunks from pandas as well to save memory
            chunk_size_read = 50000
            for df_chunk in pd.read_csv(csv_file, chunksize=chunk_size_read):
                if df_chunk.empty:
                    continue
                    
                # Convert NaN to None for JSON serialization compatibility
                df_chunk = df_chunk.replace({float('nan'): None})
                
                records = df_chunk.to_dict(orient="records")
                
                # Upsert in chunks to handle rate limits and payload sizes
                chunk_size_upload = 1000
                for i in range(0, len(records), chunk_size_upload):
                    chunk = records[i:i + chunk_size_upload]
                    try:
                        # Assuming tables have primary keys, upsert will update existing rows
                        supabase.table(table).upsert(chunk).execute()
                        print(f"    - Uploaded chunk ({len(chunk)} rows) to {table}")
                    except Exception as e:
                        print(f"    [!] Error uploading chunk for {table}: {e}")
        except Exception as e:
            print(f"[-] Error reading {csv_file.name}: {e}")
                
    print("[+] Supabase OLTP upload complete!")

if __name__ == "__main__":
    load_oltp_to_supabase()
