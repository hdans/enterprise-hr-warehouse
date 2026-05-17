from __future__ import annotations

import random
from datetime import date, datetime, time

import pandas as pd

from synthetic_data.utils.common import add_minutes, to_date


def _shift_map(shifts_raw: pd.DataFrame) -> dict[str, tuple[time, time]]:
    out: dict[str, tuple[time, time]] = {}
    for _, row in shifts_raw.iterrows():
        start = pd.to_datetime(row["start_time"]).time()
        end = pd.to_datetime(row["end_time"]).time()
        out[row["shift_code"]] = (start, end)
    return out


def generate_attendance_events_raw(
    employees_raw: pd.DataFrame,
    shifts_raw: pd.DataFrame,
    stores_raw: pd.DataFrame,
    date_start: date,
    date_end: date,
) -> pd.DataFrame:
    shift_lookup = _shift_map(shifts_raw)
    store_size = stores_raw.set_index("outlet_code")["size_label"].to_dict()

    date_range = pd.date_range(date_start, date_end, freq="D")
    rows: list[dict] = []
    event_id = 1

    for d in date_range:
        d_date = d.date()
        is_weekend = d.dayofweek >= 5

        for _, emp in employees_raw.iterrows():
            hire_date = to_date(emp["hire_dt"])
            resign_date = to_date(emp["resign_dt"])
            status = str(emp["emp_status"]).strip().lower()

            if hire_date and hire_date > d_date:
                continue
            if status in ("resigned", "terminated") and resign_date and resign_date < d_date:
                continue

            outlet_code = emp["outlet_code"]
            size = store_size.get(outlet_code, "Medium")

            sched_p = 6 / 7 if size == "Large" else 5 / 7
            if is_weekend and size != "Large":
                sched_p *= 0.55
            if random.random() > sched_p:
                continue

            if str(emp["job_code"]) <= "J04":
                shift_code = random.choices(["SH01", "SH02", "SH03", "SH04"], [0.35, 0.38, 0.20, 0.07])[0]
            else:
                shift_code = random.choices(["SH01", "SH02", "SH03", "SH04"], [0.45, 0.33, 0.10, 0.12])[0]

            start_t, end_t = shift_lookup[shift_code]
            in_dt = datetime.combine(d_date, start_t)
            out_dt = datetime.combine(d_date, end_t)
            if out_dt <= in_dt:
                out_dt = add_minutes(out_dt, 24 * 60)

            state_roll = random.random()
            if shift_code == "SH03":
                absent_prob = 0.13
            else:
                absent_prob = 0.08

            if state_roll < absent_prob:
                continue

            if state_roll < absent_prob + 0.10:
                in_dt = add_minutes(in_dt, random.randint(10, 90))
            else:
                in_dt = add_minutes(in_dt, random.randint(-10, 12))

            if random.random() < 0.12:
                out_dt = add_minutes(out_dt, -random.randint(20, 110))
            elif random.random() < (0.28 if size == "Large" else 0.15):
                out_dt = add_minutes(out_dt, random.randint(30, 220))
            else:
                out_dt = add_minutes(out_dt, random.randint(-8, 10))

            rows.append(
                {
                    "event_id": event_id,
                    "employee_code": emp["employee_code"],
                    "event_ts": in_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "IN",
                    "outlet_code": outlet_code,
                    "shift_code": shift_code,
                    "source_device": random.choice(["fingerprint", "mobile_app", "face_recognition"]),
                }
            )
            event_id += 1

            rows.append(
                {
                    "event_id": event_id,
                    "employee_code": emp["employee_code"],
                    "event_ts": out_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": "OUT",
                    "outlet_code": outlet_code,
                    "shift_code": shift_code,
                    "source_device": random.choice(["fingerprint", "mobile_app", "face_recognition"]),
                }
            )
            event_id += 1

            if random.random() < 0.01:
                rows.append(
                    {
                        "event_id": event_id,
                        "employee_code": emp["employee_code"],
                        "event_ts": add_minutes(in_dt, random.randint(1, 3)).strftime("%Y-%m-%d %H:%M:%S"),
                        "event_type": "IN",
                        "outlet_code": outlet_code,
                        "shift_code": shift_code,
                        "source_device": "fingerprint",
                    }
                )
                event_id += 1

        if d.day == 1:
            print(f"   raw attendance events: {d.strftime('%Y-%m')} | rows: {len(rows):,}")

    return pd.DataFrame(rows)
