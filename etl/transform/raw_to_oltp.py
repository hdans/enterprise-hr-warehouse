from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd


def _status_normalize(value: str) -> str:
    v = str(value).strip().lower()
    if v in {"active", "aktif"}:
        return "Active"
    if v in {"resigned", "resign", "quit"}:
        return "Resigned"
    if v in {"terminated", "fired"}:
        return "Terminated"
    return "Active"


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def transform_raw_to_oltp(base_dir: str) -> dict[str, int]:
    raw = os.path.join(base_dir, "data", "raw")
    oltp = os.path.join(base_dir, "data", "oltp")
    master_out = os.path.join(oltp, "master")
    trans_out = os.path.join(oltp, "transactional")
    os.makedirs(master_out, exist_ok=True)
    os.makedirs(trans_out, exist_ok=True)

    jobs_raw = pd.read_csv(os.path.join(raw, "master", "jobs_raw.csv"))
    depts_raw = pd.read_csv(os.path.join(raw, "master", "departments_raw.csv"))
    stores_raw = pd.read_csv(os.path.join(raw, "master", "stores_raw.csv"))
    shifts_raw = pd.read_csv(os.path.join(raw, "master", "shifts_raw.csv"))
    employees_raw = pd.read_csv(os.path.join(raw, "hris", "employees_raw.csv"))
    attendance_raw = pd.read_csv(os.path.join(raw, "attendance", "attendance_events_raw.csv"))
    payroll_raw = pd.read_csv(os.path.join(raw, "payroll", "payroll_raw.csv"))
    perf_raw = pd.read_csv(os.path.join(raw, "performance", "performance_raw.csv"))

    jobs = jobs_raw.copy()
    jobs.insert(0, "job_id", range(1, len(jobs) + 1))
    jobs.to_csv(os.path.join(master_out, "jobs.csv"), index=False)

    depts = depts_raw.copy()
    depts.insert(0, "department_id", range(1, len(depts) + 1))
    depts.to_csv(os.path.join(master_out, "departments.csv"), index=False)

    stores = stores_raw.copy()
    stores.insert(0, "store_id", range(1, len(stores) + 1))
    stores.to_csv(os.path.join(master_out, "stores.csv"), index=False)

    shifts = shifts_raw.copy()
    shifts.insert(0, "shift_id", range(1, len(shifts) + 1))
    shifts.to_csv(os.path.join(master_out, "shifts.csv"), index=False)

    job_map = jobs.set_index("job_code")["job_id"].to_dict()
    dept_map = depts.set_index("department_code")["department_id"].to_dict()
    store_map = stores.set_index("outlet_code")["store_id"].to_dict()
    shift_map = shifts.set_index("shift_code")["shift_id"].to_dict()

    employees = employees_raw.copy()
    employees["employment_status"] = employees["emp_status"].map(_status_normalize)
    employees["job_id"] = employees["job_code"].map(job_map)
    employees["department_id"] = employees["dept_code"].map(dept_map)
    employees["store_id"] = employees["outlet_code"].map(store_map)
    employees.insert(0, "employee_id", range(1, len(employees) + 1))
    employees["birth_date"] = employees["birth_dt"]
    employees["hire_date"] = employees["hire_dt"]
    emp_out = employees[
        [
            "employee_id",
            "employee_code",
            "full_name",
            "sex",
            "birth_date",
            "hire_date",
            "job_id",
            "department_id",
            "store_id",
            "employment_status",
        ]
    ]
    emp_out.to_csv(os.path.join(master_out, "employees.csv"), index=False)

    emp_code_to_id = emp_out.set_index("employee_code")["employee_id"].to_dict()

    if attendance_raw.empty:
        attendance_logs = pd.DataFrame(
            columns=[
                "attendance_log_id",
                "employee_id",
                "attendance_date",
                "shift_id",
                "check_in_time",
                "check_out_time",
                "attendance_status",
            ]
        )
    else:
        att = attendance_raw.copy()
        att["event_ts"] = _to_dt(att["event_ts"])
        att = att.dropna(subset=["event_ts"]) 
        att["attendance_date"] = att["event_ts"].dt.date

        in_events = (
            att[att["event_type"].str.upper() == "IN"]
            .sort_values(["employee_code", "attendance_date", "event_ts"])
            .groupby(["employee_code", "attendance_date", "shift_code"], as_index=False)
            .first()[["employee_code", "attendance_date", "shift_code", "event_ts"]]
            .rename(columns={"event_ts": "in_ts"})
        )
        out_events = (
            att[att["event_type"].str.upper() == "OUT"]
            .sort_values(["employee_code", "attendance_date", "event_ts"])
            .groupby(["employee_code", "attendance_date", "shift_code"], as_index=False)
            .last()[["employee_code", "attendance_date", "shift_code", "event_ts"]]
            .rename(columns={"event_ts": "out_ts"})
        )

        attendance_logs = in_events.merge(
            out_events,
            on=["employee_code", "attendance_date", "shift_code"],
            how="outer",
        )

        shift_time = shifts.set_index("shift_code")[["start_time", "end_time"]].to_dict("index")

        statuses = []
        check_in_values = []
        check_out_values = []

        for _, row in attendance_logs.iterrows():
            in_ts = row.get("in_ts")
            out_ts = row.get("out_ts")
            shift_code = row.get("shift_code")
            att_date = row.get("attendance_date")

            if pd.isna(in_ts) and pd.isna(out_ts):
                status = "Incomplete"
                check_in = None
                check_out = None
            elif pd.isna(in_ts) or pd.isna(out_ts):
                status = "Incomplete"
                check_in = in_ts.time() if pd.notna(in_ts) else None
                check_out = out_ts.time() if pd.notna(out_ts) else None
            else:
                start_t = datetime.strptime(shift_time[shift_code]["start_time"], "%H:%M:%S").time()
                end_t = datetime.strptime(shift_time[shift_code]["end_time"], "%H:%M:%S").time()
                shift_start = datetime.combine(att_date, start_t)
                shift_end = datetime.combine(att_date, end_t)
                if shift_end <= shift_start:
                    shift_end += timedelta(days=1)

                out_adj = out_ts
                if out_adj < in_ts:
                    out_adj += timedelta(days=1)

                late = in_ts > (shift_start + timedelta(minutes=10))
                early = out_adj < (shift_end - timedelta(minutes=20))

                if late:
                    status = "Late"
                elif early:
                    status = "Early Leave"
                else:
                    status = "Present"

                check_in = in_ts.time()
                check_out = out_ts.time()

            statuses.append(status)
            check_in_values.append(check_in)
            check_out_values.append(check_out)

        attendance_logs["attendance_status"] = statuses
        attendance_logs["check_in_time"] = check_in_values
        attendance_logs["check_out_time"] = check_out_values
        attendance_logs["employee_id"] = attendance_logs["employee_code"].map(emp_code_to_id)
        attendance_logs["shift_id"] = attendance_logs["shift_code"].map(shift_map)
        attendance_logs = attendance_logs.dropna(subset=["employee_id", "shift_id"])
        attendance_logs["employee_id"] = attendance_logs["employee_id"].astype(int)
        attendance_logs["shift_id"] = attendance_logs["shift_id"].astype(int)
        attendance_logs.insert(0, "attendance_log_id", range(1, len(attendance_logs) + 1))
        attendance_logs = attendance_logs[
            [
                "attendance_log_id",
                "employee_id",
                "attendance_date",
                "shift_id",
                "check_in_time",
                "check_out_time",
                "attendance_status",
            ]
        ]

    attendance_logs.to_csv(os.path.join(trans_out, "attendance_logs.csv"), index=False)

    payroll = payroll_raw.copy()
    payroll["employee_id"] = payroll["employee_code"].map(emp_code_to_id)
    payroll = payroll.dropna(subset=["employee_id"])
    payroll["employee_id"] = payroll["employee_id"].astype(int)
    payroll.insert(0, "payroll_transaction_id", range(1, len(payroll) + 1))
    payroll = payroll[
        [
            "payroll_transaction_id",
            "employee_id",
            "period",
            "base_pay",
            "overtime_pay",
            "bonus_pay",
            "penalty",
            "total_pay",
            "payout_date",
        ]
    ].rename(
        columns={
            "period": "payroll_period",
            "base_pay": "base_salary",
            "bonus_pay": "bonus",
            "penalty": "deduction",
            "total_pay": "total_salary",
            "payout_date": "payment_date",
        }
    )
    payroll.to_csv(os.path.join(trans_out, "payroll_transactions.csv"), index=False)

    perf = perf_raw.copy()
    perf["employee_id"] = perf["employee_code"].map(emp_code_to_id)
    perf["store_id"] = perf["outlet_code"].map(store_map)
    perf = perf.dropna(subset=["employee_id", "store_id"])
    perf["employee_id"] = perf["employee_id"].astype(int)
    perf["store_id"] = perf["store_id"].astype(int)
    perf.insert(0, "performance_log_id", range(1, len(perf) + 1))
    perf = perf[
        [
            "performance_log_id",
            "employee_id",
            "perf_date",
            "store_id",
            "sales_amt",
            "cust_rating",
            "tasks_done",
        ]
    ].rename(
        columns={
            "perf_date": "performance_date",
            "sales_amt": "sales_amount",
            "cust_rating": "customer_rating",
            "tasks_done": "tasks_completed",
        }
    )
    perf.to_csv(os.path.join(trans_out, "performance_logs.csv"), index=False)

    return {
        "jobs": len(jobs),
        "departments": len(depts),
        "stores": len(stores),
        "shifts": len(shifts),
        "employees": len(emp_out),
        "attendance_logs": len(attendance_logs),
        "payroll_transactions": len(payroll),
        "performance_logs": len(perf),
    }
