from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker


def generate_jobs() -> pd.DataFrame:
    rows = [
        ("J01", "Barista", 1, "G1A"),
        ("J02", "Cashier", 1, "G1B"),
        ("J03", "Kitchen Crew", 1, "G1C"),
        ("J04", "Delivery Rider", 1, "G1D"),
        ("J05", "Inventory Staff", 2, "G2A"),
        ("J06", "Store Supervisor", 2, "G2B"),
        ("J07", "Shift Leader", 2, "G2C"),
        ("J08", "HR Staff", 2, "G2D"),
        ("J09", "Finance Staff", 2, "G2E"),
        ("J10", "Marketing Staff", 2, "G2F"),
        ("J11", "Store Manager", 3, "G3A"),
        ("J12", "Area Manager", 4, "G4A"),
        ("J13", "Regional HR Manager", 4, "G4B"),
        ("J14", "Finance Manager", 4, "G4C"),
        ("J15", "Operations Manager", 4, "G4D"),
        ("J16", "Regional Director", 5, "G5A"),
        ("J17", "HR Director", 5, "G5B"),
        ("J18", "Finance Director", 5, "G5C"),
        ("J19", "Chief Operations Officer", 5, "G5D"),
    ]
    return pd.DataFrame(rows, columns=["job_code", "job_title", "job_level", "salary_grade"])


def generate_departments() -> pd.DataFrame:
    names = [
        "Operations",
        "Human Resources",
        "Finance & Accounting",
        "Marketing",
        "Supply Chain",
        "Quality Assurance",
        "IT & Digital",
        "Customer Experience",
    ]
    return pd.DataFrame({"department_code": [f"D{i:02d}" for i in range(1, len(names) + 1)], "department_name": names})


def generate_shifts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("SH01", "Morning", "06:00:00", "14:00:00"),
            ("SH02", "Afternoon", "14:00:00", "22:00:00"),
            ("SH03", "Night", "22:00:00", "06:00:00"),
            ("SH04", "Split", "10:00:00", "18:00:00"),
        ],
        columns=["shift_code", "shift_name", "start_time", "end_time"],
    )


def generate_employees_raw(
    fake: Faker,
    jobs: pd.DataFrame,
    depts: pd.DataFrame,
    stores: pd.DataFrame,
    n_employees: int,
    date_end: date,
) -> pd.DataFrame:
    job_codes = jobs["job_code"].tolist()
    job_levels = jobs.set_index("job_code")["job_level"].to_dict()
    dept_codes = depts["department_code"].tolist()
    store_codes = stores["outlet_code"].tolist()

    job_weights = np.array([1 / (job_levels[j] ** 2.0) for j in job_codes], dtype=float)
    job_weights /= job_weights.sum()

    status_choices = ["ACTIVE", "active", "Resigned", "TERMINATED", "Active"]
    status_probs = [0.42, 0.18, 0.15, 0.05, 0.20]

    rows = []
    for i in range(1, n_employees + 1):
        hire_date = fake.date_between(start_date=date(2019, 1, 1), end_date=date_end - timedelta(days=60))
        raw_status = str(np.random.choice(status_choices, p=status_probs))
        norm_status = raw_status.strip().lower()

        resign_date = None
        if norm_status in ("resigned", "terminated"):
            resign_start = hire_date + timedelta(days=90)
            if resign_start <= date_end:
                resign_date = fake.date_between(start_date=resign_start, end_date=date_end)
            else:
                raw_status = "Active"

        rows.append(
            {
                "employee_code": f"EMP{i:05d}",
                "full_name": fake.name(),
                "sex": random.choice(["M", "F"]),
                "birth_dt": fake.date_of_birth(minimum_age=18, maximum_age=45).strftime("%Y-%m-%d"),
                "hire_dt": hire_date.strftime("%Y-%m-%d"),
                "job_code": str(np.random.choice(job_codes, p=job_weights)),
                "dept_code": random.choice(dept_codes),
                "outlet_code": random.choice(store_codes),
                "emp_status": raw_status,
                "resign_dt": resign_date.strftime("%Y-%m-%d") if resign_date else "",
            }
        )

    return pd.DataFrame(rows)
