import os
import pandas as pd

def transform_staging_to_warehouse(base_dir: str):
    stg_dir = os.path.join(base_dir, "data", "staging")
    wh_dir = os.path.join(base_dir, "data", "warehouse")
    os.makedirs(wh_dir, exist_ok=True)

    # 1. Load Staged Data
    try:
        employees = pd.read_csv(os.path.join(stg_dir, "stg_employees.csv"))
        jobs = pd.read_csv(os.path.join(stg_dir, "stg_jobs.csv"))
        departments = pd.read_csv(os.path.join(stg_dir, "stg_departments.csv"))
        stores = pd.read_csv(os.path.join(stg_dir, "stg_stores.csv"))
        shifts = pd.read_csv(os.path.join(stg_dir, "stg_shifts.csv"))

        attendance = pd.read_csv(os.path.join(stg_dir, "stg_attendance_logs.csv"))
        payroll = pd.read_csv(os.path.join(stg_dir, "stg_payroll_transactions.csv"))
        performance = pd.read_csv(os.path.join(stg_dir, "stg_performance_logs.csv"))
    except FileNotFoundError as e:
        print(f"Error loading staged files: {e}")
        print("Make sure you run oltp_to_staging.py first.")
        return

    # 2. Process Dimensions
    dim_employee = employees[['employee_id', 'employee_code', 'full_name', 'sex', 'birth_date', 'hire_date', 'employment_status']].copy()
    dim_job = jobs[['job_id', 'job_code', 'job_title']].copy()
    dim_department = departments[['department_id', 'department_code', 'department_name']].copy()
    dim_store = stores[['store_id', 'outlet_code']].copy()
    dim_shift = shifts[['shift_id', 'shift_code', 'start_time', 'end_time']].copy()

    # Create dim_date
    dates_attendance = attendance['attendance_date'].dropna()
    dates_payroll = payroll['payment_date'].dropna()
    dates_performance = performance['performance_date'].dropna()

    all_dates = pd.concat([dates_attendance, dates_payroll, dates_performance]).drop_duplicates()
    all_dates = pd.to_datetime(all_dates).dt.date
    
    if len(all_dates) == 0:
        print("No dates found in staged transactional data. dim_date will be empty.")
        dim_date = pd.DataFrame(columns=['date_id', 'full_date', 'day', 'month', 'year', 'quarter', 'day_of_week', 'is_weekend'])
    else:
        min_date = all_dates.min()
        max_date = all_dates.max()
        date_range = pd.date_range(start=min_date, end=max_date)
        
        dim_date = pd.DataFrame({'full_date': date_range})
        dim_date['full_date_str'] = dim_date['full_date'].dt.strftime('%Y-%m-%d')
        dim_date['date_id'] = dim_date['full_date'].dt.strftime('%Y%m%d').astype(int)
        dim_date['day'] = dim_date['full_date'].dt.day
        dim_date['month'] = dim_date['full_date'].dt.month
        dim_date['year'] = dim_date['full_date'].dt.year
        dim_date['quarter'] = dim_date['full_date'].dt.quarter
        dim_date['day_of_week'] = dim_date['full_date'].dt.dayofweek + 1 # 1=Monday, 7=Sunday
        dim_date['is_weekend'] = dim_date['day_of_week'].isin([6, 7])
        
        dim_date = dim_date[['date_id', 'full_date_str', 'day', 'month', 'year', 'quarter', 'day_of_week', 'is_weekend']]
        dim_date = dim_date.rename(columns={'full_date_str': 'full_date'})

    # 3. Process Facts
    # Fact Attendance
    fact_attendance = attendance.copy()
    if not fact_attendance.empty:
        fact_attendance['date_id'] = pd.to_datetime(fact_attendance['attendance_date']).dt.strftime('%Y%m%d').astype(int)
        fact_attendance = fact_attendance[['attendance_log_id', 'employee_id', 'date_id', 'shift_id', 'check_in_time', 'check_out_time', 'attendance_status']]
    else:
        fact_attendance['date_id'] = pd.Series(dtype=int)
        fact_attendance = fact_attendance[['attendance_log_id', 'employee_id', 'date_id', 'shift_id', 'check_in_time', 'check_out_time', 'attendance_status']]

    # Fact Payroll
    fact_payroll = payroll.copy()
    if not fact_payroll.empty:
        fact_payroll['date_id'] = pd.to_datetime(fact_payroll['payment_date']).dt.strftime('%Y%m%d').astype(int)
        fact_payroll = fact_payroll[['payroll_transaction_id', 'employee_id', 'date_id', 'base_salary', 'overtime_pay', 'bonus', 'deduction', 'total_salary']]
    else:
        fact_payroll['date_id'] = pd.Series(dtype=int)
        fact_payroll = fact_payroll[['payroll_transaction_id', 'employee_id', 'date_id', 'base_salary', 'overtime_pay', 'bonus', 'deduction', 'total_salary']]

    # Fact Performance
    fact_performance = performance.copy()
    if not fact_performance.empty:
        fact_performance['date_id'] = pd.to_datetime(fact_performance['performance_date']).dt.strftime('%Y%m%d').astype(int)
        fact_performance = fact_performance[['performance_log_id', 'employee_id', 'store_id', 'date_id', 'sales_amount', 'customer_rating', 'tasks_completed']]
    else:
        fact_performance['date_id'] = pd.Series(dtype=int)
        fact_performance = fact_performance[['performance_log_id', 'employee_id', 'store_id', 'date_id', 'sales_amount', 'customer_rating', 'tasks_completed']]

    # 4. Save to Warehouse
    dim_employee.to_csv(os.path.join(wh_dir, "dim_employee.csv"), index=False)
    dim_job.to_csv(os.path.join(wh_dir, "dim_job.csv"), index=False)
    dim_department.to_csv(os.path.join(wh_dir, "dim_department.csv"), index=False)
    dim_store.to_csv(os.path.join(wh_dir, "dim_store.csv"), index=False)
    dim_shift.to_csv(os.path.join(wh_dir, "dim_shift.csv"), index=False)
    dim_date.to_csv(os.path.join(wh_dir, "dim_date.csv"), index=False)
    
    fact_attendance.to_csv(os.path.join(wh_dir, "fact_attendance.csv"), index=False)
    fact_payroll.to_csv(os.path.join(wh_dir, "fact_payroll.csv"), index=False)
    fact_performance.to_csv(os.path.join(wh_dir, "fact_performance.csv"), index=False)

    print("Staging to Data Warehouse ETL successfully completed. Files saved to data/warehouse/")

if __name__ == "__main__":
    base_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    transform_staging_to_warehouse(base_directory)
