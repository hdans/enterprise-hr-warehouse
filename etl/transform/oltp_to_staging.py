import os
import pandas as pd

def transform_oltp_to_staging(base_dir: str):
    oltp_master = os.path.join(base_dir, "data", "oltp", "master")
    oltp_trans = os.path.join(base_dir, "data", "oltp", "transactional")
    stg_dir = os.path.join(base_dir, "data", "staging")
    os.makedirs(stg_dir, exist_ok=True)

    # Dictionary of (source_dir, source_file, staging_file)
    files_to_stage = [
        (oltp_master, "employees.csv", "stg_employees.csv"),
        (oltp_master, "jobs.csv", "stg_jobs.csv"),
        (oltp_master, "departments.csv", "stg_departments.csv"),
        (oltp_master, "stores.csv", "stg_stores.csv"),
        (oltp_master, "shifts.csv", "stg_shifts.csv"),
        (oltp_trans, "attendance_logs.csv", "stg_attendance_logs.csv"),
        (oltp_trans, "payroll_transactions.csv", "stg_payroll_transactions.csv"),
        (oltp_trans, "performance_logs.csv", "stg_performance_logs.csv"),
    ]

    for source_dir, source_file, target_file in files_to_stage:
        source_path = os.path.join(source_dir, source_file)
        target_path = os.path.join(stg_dir, target_file)
        
        if os.path.exists(source_path):
            df = pd.read_csv(source_path)
            # In a real scenario, we might cast types or handle nulls here
            df.to_csv(target_path, index=False)
            print(f"Staged {source_file} to {target_file} ({len(df)} rows)")
        else:
            print(f"Warning: Source file {source_path} not found.")

    print("Data Staging successfully completed. Files saved to data/staging/")

if __name__ == "__main__":
    base_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    transform_oltp_to_staging(base_directory)
