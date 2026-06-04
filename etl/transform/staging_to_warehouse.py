from __future__ import annotations
import os
import numpy as np
import pandas as pd

def _read_source(stg_dir: str, oltp_dir: str, stg_name: str, oltp_name: str) -> pd.DataFrame:
    """Read from staging first; fall back to OLTP if staging file is missing."""
    stg_path = os.path.join(stg_dir, stg_name)
    if os.path.exists(stg_path):
        return pd.read_csv(stg_path)

    oltp_path = os.path.join(oltp_dir, oltp_name)
    if os.path.exists(oltp_path):
        print(f"  [fallback] Reading from OLTP: {oltp_name}")
        return pd.read_csv(oltp_path)

    raise FileNotFoundError(
        f"Source file not found.\n"
        f"  Tried: {stg_path}\n"
        f"  Tried: {oltp_path}\n"
        f"Run oltp_to_staging.py first, or ensure OLTP data exists."
    )


def _calc_hours_worked(check_in: pd.Series, check_out: pd.Series) -> pd.Series:
    """Vectorised calculation of hours worked from time strings (HH:MM:SS)."""
    base = pd.Timestamp("1900-01-01")
    ci = pd.to_datetime(check_in.astype(str), format="%H:%M:%S", errors="coerce")
    co = pd.to_datetime(check_out.astype(str), format="%H:%M:%S", errors="coerce")
    diff_seconds = (co - ci).dt.total_seconds()
    diff_seconds = diff_seconds.where(diff_seconds >= 0, diff_seconds + 86400)
    hours = (diff_seconds / 3600).round(2)
    return hours.fillna(0.0)

def transform_staging_to_warehouse(base_dir: str) -> dict[str, int]:
    stg_dir      = os.path.join(base_dir, "data", "staging")
    oltp_master  = os.path.join(base_dir, "data", "oltp", "master")
    oltp_trans   = os.path.join(base_dir, "data", "oltp", "transactional")
    wh_dir       = os.path.join(base_dir, "data", "warehouse")
    os.makedirs(wh_dir, exist_ok=True)

    print("=" * 65)
    print(" OLAP Pipeline: Staging -> Data Warehouse (Star Schema)")
    print("=" * 65)

    print("\n[1/4] Loading source data ...")

    employees   = _read_source(stg_dir, oltp_master, "stg_employees.csv",              "employees.csv")
    jobs        = _read_source(stg_dir, oltp_master, "stg_jobs.csv",                   "jobs.csv")
    departments = _read_source(stg_dir, oltp_master, "stg_departments.csv",            "departments.csv")
    stores      = _read_source(stg_dir, oltp_master, "stg_stores.csv",                 "stores.csv")
    shifts      = _read_source(stg_dir, oltp_master, "stg_shifts.csv",                 "shifts.csv")
    attendance  = _read_source(stg_dir, oltp_trans,  "stg_attendance_logs.csv",         "attendance_logs.csv")
    payroll     = _read_source(stg_dir, oltp_trans,  "stg_payroll_transactions.csv",    "payroll_transactions.csv")
    performance = _read_source(stg_dir, oltp_trans,  "stg_performance_logs.csv",        "performance_logs.csv")

    print(f"  Master:        employees={len(employees)}, jobs={len(jobs)}, "
          f"departments={len(departments)}, stores={len(stores)}, shifts={len(shifts)}")
    print(f"  Transactional: attendance={len(attendance):,}, "
          f"payroll={len(payroll):,}, performance={len(performance):,}")

    print("\n[2/4] Building dimension tables ...")

    dim_job = jobs[["job_id", "job_title"]].copy()
    dim_job["job_code"] = jobs["job_code"] if "job_code" in jobs.columns else None
    dim_job["job_level"] = jobs["job_level"] if "job_level" in jobs.columns else None
    dim_job["salary_grade"] = jobs["salary_grade"] if "salary_grade" in jobs.columns else None
    dim_job = dim_job[["job_id", "job_code", "job_title", "job_level", "salary_grade"]]
    print(f"  [OK] dim_job              : {len(dim_job):>6,} rows")

    dim_department = departments[["department_id", "department_name"]].copy()
    dim_department["department_code"] = departments["department_code"] if "department_code" in departments.columns else None
    dim_department = dim_department[["department_id", "department_code", "department_name"]]
    print(f"  [OK] dim_department       : {len(dim_department):>6,} rows")

    store_name_col = next(
        (c for c in ["outlet_name", "store_name"] if c in stores.columns),
        None,
    )
    dim_store = pd.DataFrame({
        "store_id":   stores["store_id"],
        "outlet_code": stores["outlet_code"] if "outlet_code" in stores.columns else None,
        "store_name": stores[store_name_col] if store_name_col else "Unknown",
        "city":       stores["city"]   if "city"   in stores.columns else "Unknown",
        "region":     stores["region"] if "region" in stores.columns else "Unknown",
        "size_label": stores["size_label"] if "size_label" in stores.columns else None,
    })
    print(f"  [OK] dim_store            : {len(dim_store):>6,} rows")

    shift_name_col = next(
        (c for c in ["shift_name", "shift_code"] if c in shifts.columns),
        None,
    )
    dim_shift = pd.DataFrame({
        "shift_id":   shifts["shift_id"],
        "shift_code": shifts["shift_code"] if "shift_code" in shifts.columns else None,
        "shift_name": shifts[shift_name_col] if shift_name_col else "Unknown",
        "start_time": shifts["start_time"],
        "end_time":   shifts["end_time"],
    })
    print(f"  [OK] dim_shift            : {len(dim_shift):>6,} rows")

    date_series: list[pd.Series] = []
    if "attendance_date"  in attendance.columns:  date_series.append(attendance["attendance_date"])
    if "payment_date"     in payroll.columns:     date_series.append(payroll["payment_date"])
    if "performance_date" in performance.columns: date_series.append(performance["performance_date"])

    if date_series:
        all_raw = pd.concat(date_series).dropna().drop_duplicates()
        all_dates = pd.to_datetime(all_raw, errors="coerce").dropna()
        date_range = pd.date_range(start=all_dates.min(), end=all_dates.max())

        dim_date = pd.DataFrame({
            "date_id":   date_range.strftime("%Y%m%d").astype(int),
            "full_date": date_range.strftime("%Y-%m-%d"),
            "day":       date_range.day,
            "month":     date_range.month,
            "quarter":   date_range.quarter,
            "year":      date_range.year,
        })
    else:
        dim_date = pd.DataFrame(
            columns=["date_id", "full_date", "day", "month", "quarter", "year"]
        )
    print(f"  [OK] dim_date             : {len(dim_date):>6,} rows")

    dim_employee = pd.DataFrame({
        "employee_id":   employees["employee_id"],
        "employee_code": employees["employee_code"] if "employee_code" in employees.columns else None,
        "employee_name": employees["full_name"],
        "gender":        employees["sex"],
        "birth_date":    employees["birth_date"],
        "hire_date":     employees["hire_date"],
        "employment_status": employees["employment_status"] if "employment_status" in employees.columns else None,
        "job_id":        employees["job_id"],
        "department_id": employees["department_id"],
        "store_id":      employees["store_id"],
    })
    print(f"  [OK] dim_employee         : {len(dim_employee):>6,} rows")

    print("\n[3/4] Building fact tables ...")

    emp_lookup = employees.set_index("employee_id")
    emp_job_map   = emp_lookup["job_id"].to_dict()
    emp_dept_map  = emp_lookup["department_id"].to_dict()
    emp_store_map = emp_lookup["store_id"].to_dict()

    if not attendance.empty and "shift_id" in attendance.columns:
        emp_shift_mode = (
            attendance.groupby("employee_id")["shift_id"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 1)
            .to_dict()
        )
    else:
        emp_shift_mode = {}

    if not performance.empty:
        perf_date_id = pd.to_datetime(
            performance["performance_date"], errors="coerce"
        ).dt.strftime("%Y%m%d").astype(int)

        fact_employee_performance = pd.DataFrame({
            "performance_id":   performance["performance_log_id"].values,
            "employee_id":      performance["employee_id"].values,
            "date_id":          perf_date_id.values,
            "store_id":         performance["store_id"].values,
            "job_id":           performance["employee_id"].map(emp_job_map).values,
            "shift_id":         performance["employee_id"].map(emp_shift_mode).fillna(1).astype(int).values,
            "sales_amount":     performance["sales_amount"].values,
            "customer_rating":  performance["customer_rating"].values,
            "tasks_completed":  performance["tasks_completed"].values,
        })
    else:
        fact_employee_performance = pd.DataFrame(columns=[
            "performance_id", "employee_id", "date_id", "store_id",
            "job_id", "shift_id", "sales_amount", "customer_rating", "tasks_completed",
        ])
    print(f"  [OK] fact_employee_performance : {len(fact_employee_performance):>9,} rows")

    if not payroll.empty:
        pay_date_id = pd.to_datetime(
            payroll["payment_date"], errors="coerce"
        ).dt.strftime("%Y%m%d").astype(int)

        fact_payroll = pd.DataFrame({
            "payroll_id":    payroll["payroll_transaction_id"].values,
            "employee_id":   payroll["employee_id"].values,
            "date_id":       pay_date_id.values,
            "job_id":        payroll["employee_id"].map(emp_job_map).values,
            "department_id": payroll["employee_id"].map(emp_dept_map).values,
            "store_id":      payroll["employee_id"].map(emp_store_map).values,
            "payroll_period": payroll["payroll_period"].values if "payroll_period" in payroll.columns else None,
            "base_salary":   payroll["base_salary"].values,
            "bonus":         payroll["bonus"].values,
            "overtime_pay":  payroll["overtime_pay"].values,
            "deduction":     payroll["deduction"].values if "deduction" in payroll.columns else 0.0,
            "total_salary":  payroll["total_salary"].values,
        })
    else:
        fact_payroll = pd.DataFrame(columns=[
            "payroll_id", "employee_id", "date_id", "job_id",
            "department_id", "store_id", "payroll_period", "base_salary", "bonus",
            "overtime_pay", "deduction", "total_salary",
        ])
    print(f"  [OK] fact_payroll              : {len(fact_payroll):>9,} rows")

    if not attendance.empty:
        att_date_id = pd.to_datetime(
            attendance["attendance_date"], errors="coerce"
        ).dt.strftime("%Y%m%d").astype(int)

        hours_worked = _calc_hours_worked(
            attendance["check_in_time"], attendance["check_out_time"]
        )
        overtime_hours = (hours_worked - 8.0).clip(lower=0.0).round(2)

        fact_attendance = pd.DataFrame({
            "attendance_id":    attendance["attendance_log_id"].values,
            "employee_id":      attendance["employee_id"].values,
            "date_id":          att_date_id.values,
            "shift_id":         attendance["shift_id"].values,
            "store_id":         attendance["employee_id"].map(emp_store_map).values,
            "check_in_time":    attendance["check_in_time"].values if "check_in_time" in attendance.columns else None,
            "check_out_time":   attendance["check_out_time"].values if "check_out_time" in attendance.columns else None,
            "hours_worked":     hours_worked.values,
            "overtime_hours":   overtime_hours.values,
            "attendance_status": attendance["attendance_status"].values,
        })
    else:
        fact_attendance = pd.DataFrame(columns=[
            "attendance_id", "employee_id", "date_id", "shift_id",
            "store_id", "check_in_time", "check_out_time", "hours_worked", "overtime_hours", "attendance_status",
        ])
    print(f"  [OK] fact_attendance           : {len(fact_attendance):>9,} rows")

    print("\n[4/4] Saving to data/warehouse/ ...")

    tables: dict[str, pd.DataFrame] = {
        "dim_job":                      dim_job,
        "dim_department":               dim_department,
        "dim_store":                    dim_store,
        "dim_shift":                    dim_shift,
        "dim_date":                     dim_date,
        "dim_employee":                 dim_employee,
        "fact_employee_performance":    fact_employee_performance,
        "fact_payroll":                 fact_payroll,
        "fact_attendance":              fact_attendance,
    }

    counts: dict[str, int] = {}
    for name, df in tables.items():
        path = os.path.join(wh_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        counts[name] = len(df)
        print(f"  >> {name}.csv  ({len(df):,} rows)")

    print("\n" + "=" * 65)
    print(" OLAP Pipeline completed successfully!")
    print(f" Output: {wh_dir}")
    print("=" * 65)

    return counts


if __name__ == "__main__":
    base_directory = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    transform_staging_to_warehouse(base_directory)
