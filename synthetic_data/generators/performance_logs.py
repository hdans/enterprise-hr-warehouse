from __future__ import annotations

import random
from datetime import date

import pandas as pd

from synthetic_data.utils.common import clamp


def generate_performance_raw(
    employees_raw: pd.DataFrame,
    stores_raw: pd.DataFrame,
    attendance_events_raw: pd.DataFrame,
    date_start: date,
    date_end: date,
) -> pd.DataFrame:
    store_region = stores_raw.set_index("outlet_code")["region"].to_dict()
    store_size = stores_raw.set_index("outlet_code")["size_label"].to_dict()

    region_mult = {
        "Jabodetabek": 1.30,
        "Bali": 1.25,
        "Jawa Barat": 1.10,
        "Jawa Timur": 1.05,
        "Jawa Tengah": 1.00,
        "Sumatera": 0.95,
        "Sulawesi": 0.90,
        "Kalimantan": 0.85,
    }

    att = attendance_events_raw.copy()
    if not att.empty:
        att["event_ts"] = pd.to_datetime(att["event_ts"])
        att["day"] = att["event_ts"].dt.date
        att["iso_year"] = att["event_ts"].dt.isocalendar().year.astype(int)
        att["iso_week"] = att["event_ts"].dt.isocalendar().week.astype(int)

        in_logs = (
            att[att["event_type"] == "IN"]
            .sort_values(["employee_code", "day", "event_ts"])
            .groupby(["employee_code", "day"], as_index=False)
            .first()[["employee_code", "day", "event_ts", "shift_code"]]
            .rename(columns={"event_ts": "in_ts"})
        )
        out_logs = (
            att[att["event_type"] == "OUT"]
            .sort_values(["employee_code", "day", "event_ts"])
            .groupby(["employee_code", "day"], as_index=False)
            .last()[["employee_code", "day", "event_ts"]]
            .rename(columns={"event_ts": "out_ts"})
        )
        daily = in_logs.merge(out_logs, on=["employee_code", "day"], how="inner")
        daily["hours"] = (daily["out_ts"] - daily["in_ts"]).dt.total_seconds() / 3600
        daily["hours"] = daily["hours"].clip(lower=0)
        daily["ot"] = (daily["hours"] - 8.0).clip(lower=0)
        daily["iso_year"] = pd.to_datetime(daily["day"]).dt.isocalendar().year.astype(int)
        daily["iso_week"] = pd.to_datetime(daily["day"]).dt.isocalendar().week.astype(int)

        weekly = (
            daily.groupby(["employee_code", "iso_year", "iso_week"], as_index=False)
            .agg(
                present_days=("day", "count"),
                week_ot=("ot", "sum"),
                main_shift=("shift_code", lambda s: s.mode().iloc[0] if not s.mode().empty else "SH01"),
            )
        )
    else:
        weekly = pd.DataFrame(columns=["employee_code", "iso_year", "iso_week", "present_days", "week_ot", "main_shift"])

    mondays = pd.date_range(date_start, date_end, freq="W-MON")
    rows = []
    perf_id = 1

    for monday in mondays:
        d = monday.date()
        iso_year = int(monday.isocalendar().year)
        iso_week = int(monday.isocalendar().week)

        for _, emp in employees_raw.iterrows():
            hire = pd.to_datetime(emp["hire_dt"]).date()
            resign = pd.to_datetime(emp["resign_dt"]).date() if str(emp["resign_dt"]).strip() else None
            if hire > d:
                continue
            status = str(emp["emp_status"]).strip().lower()
            if status in ("resigned", "terminated") and resign and resign < d:
                continue

            emp_code = emp["employee_code"]
            outlet = emp["outlet_code"]
            region = store_region.get(outlet, "Jabodetabek")
            size = store_size.get(outlet, "Medium")

            w = weekly[(weekly["employee_code"] == emp_code) & (weekly["iso_year"] == iso_year) & (weekly["iso_week"] == iso_week)]
            if len(w):
                present_days = int(w["present_days"].values[0])
                week_ot = float(w["week_ot"].values[0])
                main_shift = str(w["main_shift"].values[0])
            else:
                present_days = 0
                week_ot = 0.0
                main_shift = "SH01"

            tenure = (d - hire).days / 365.0
            stability = clamp(tenure / 3.0, 0.05, 1.0)

            tasks = max(0, int(present_days * random.randint(8, 16) + random.gauss(0, 2.5 * (1 - stability))))
            rating = 3.7 + stability * 0.85 - min(week_ot / 15.0, 0.30)
            if main_shift == "SH03":
                rating -= 0.45
            rating += random.gauss(0, 0.3 * (1 - stability * 0.4))
            rating = clamp(round(rating, 2), 1.0, 5.0)

            size_mult = {"Small": 0.80, "Medium": 1.00, "Large": 1.35}.get(size, 1.0)
            sales = max(0.0, 1_600_000 * region_mult.get(region, 1.0) * size_mult * present_days * random.gauss(1.0, 0.15))

            rows.append(
                {
                    "performance_raw_id": perf_id,
                    "employee_code": emp_code,
                    "perf_date": d.strftime("%Y-%m-%d"),
                    "outlet_code": outlet,
                    "sales_amt": round(sales, 2),
                    "cust_rating": rating,
                    "tasks_done": tasks,
                }
            )
            perf_id += 1

    return pd.DataFrame(rows)
