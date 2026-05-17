from __future__ import annotations

import random
from datetime import date

import pandas as pd


def generate_payroll_raw(
    employees_raw: pd.DataFrame,
    jobs_raw: pd.DataFrame,
    attendance_events_raw: pd.DataFrame,
    date_start: date,
    date_end: date,
) -> pd.DataFrame:
    salary_map = {1: 4_000_000, 2: 6_500_000, 3: 10_500_000, 4: 18_500_000, 5: 36_000_000}
    job_level = jobs_raw.set_index("job_code")["job_level"].to_dict()

    emp_base = {}
    for _, emp in employees_raw.iterrows():
        lvl = int(job_level.get(emp["job_code"], 1))
        emp_base[emp["employee_code"]] = round(salary_map[lvl] * random.uniform(0.92, 1.08), 0)

    att = attendance_events_raw.copy()
    if not att.empty:
        att["event_ts"] = pd.to_datetime(att["event_ts"])
        att["attendance_date"] = att["event_ts"].dt.date
        att["ym"] = att["event_ts"].dt.strftime("%Y-%m")

        in_logs = (
            att[att["event_type"] == "IN"]
            .sort_values(["employee_code", "attendance_date", "event_ts"])
            .groupby(["employee_code", "attendance_date"], as_index=False)
            .first()[["employee_code", "attendance_date", "event_ts"]]
            .rename(columns={"event_ts": "in_ts"})
        )
        out_logs = (
            att[att["event_type"] == "OUT"]
            .sort_values(["employee_code", "attendance_date", "event_ts"])
            .groupby(["employee_code", "attendance_date"], as_index=False)
            .last()[["employee_code", "attendance_date", "event_ts"]]
            .rename(columns={"event_ts": "out_ts"})
        )

        merged = in_logs.merge(out_logs, on=["employee_code", "attendance_date"], how="inner")
        merged["hours"] = (merged["out_ts"] - merged["in_ts"]).dt.total_seconds() / 3600
        merged["hours"] = merged["hours"].clip(lower=0)
        merged["ot_hours"] = (merged["hours"] - 8.0).clip(lower=0)
        merged["ym"] = pd.to_datetime(merged["attendance_date"]).dt.strftime("%Y-%m")

        monthly_ot = merged.groupby(["employee_code", "ym"], as_index=False)["ot_hours"].sum()
        monthly_present = merged.groupby(["employee_code", "ym"], as_index=False).size().rename(columns={"size": "present_days"})
    else:
        monthly_ot = pd.DataFrame(columns=["employee_code", "ym", "ot_hours"])
        monthly_present = pd.DataFrame(columns=["employee_code", "ym", "present_days"])

    months = pd.date_range(date_start.replace(day=1), date_end.replace(day=1), freq="MS")

    rows = []
    txn_id = 1
    for _, emp in employees_raw.iterrows():
        emp_code = emp["employee_code"]
        hire_dt = pd.to_datetime(emp["hire_dt"]).date()
        resign_dt = pd.to_datetime(emp["resign_dt"]).date() if str(emp["resign_dt"]).strip() else None

        for m in months:
            ym = m.strftime("%Y-%m")
            month_start = m.date()
            if hire_dt > month_start:
                continue
            if resign_dt and (month_start.year, month_start.month) > (resign_dt.year, resign_dt.month):
                continue

            ot_row = monthly_ot[(monthly_ot["employee_code"] == emp_code) & (monthly_ot["ym"] == ym)]
            ot_hours = float(ot_row["ot_hours"].values[0]) if len(ot_row) else 0.0

            pr_row = monthly_present[(monthly_present["employee_code"] == emp_code) & (monthly_present["ym"] == ym)]
            present_days = int(pr_row["present_days"].values[0]) if len(pr_row) else 0
            attendance_rate = min(present_days / 26.0, 1.0)

            base = emp_base[emp_code]
            overtime_pay = round(ot_hours * 25_000, 2)
            bonus = round(base * attendance_rate * 0.05, 2)
            penalty = round(max(0, 26 - present_days) * 5_000, 2)
            total = round(base + overtime_pay + bonus - penalty, 2)

            rows.append(
                {
                    "txn_id": txn_id,
                    "employee_code": emp_code,
                    "period": ym,
                    "base_pay": base,
                    "overtime_pay": overtime_pay,
                    "bonus_pay": bonus,
                    "penalty": penalty,
                    "total_pay": total,
                    "payout_date": f"{ym}-25",
                }
            )
            txn_id += 1

    return pd.DataFrame(rows)
