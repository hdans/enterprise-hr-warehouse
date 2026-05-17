from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.transform.raw_to_oltp import transform_raw_to_oltp
from synthetic_data.generators.attendance_logs import generate_attendance_events_raw
from synthetic_data.generators.employees import (
    generate_departments,
    generate_employees_raw,
    generate_jobs,
    generate_shifts,
)
from synthetic_data.generators.payroll_transactions import generate_payroll_raw
from synthetic_data.generators.performance_logs import generate_performance_raw
from synthetic_data.generators.stores import generate_stores
from synthetic_data.utils.common import ensure_dirs, init_seed, save_csv


def _load_config() -> dict:
    load_dotenv(ROOT / ".env")
    return {
        "seed": int(os.getenv("SEED", "42")),
        "n_employees": int(os.getenv("N_EMPLOYEES", "2400")),
        "n_stores": int(os.getenv("N_STORES", "90")),
        "date_start": date.fromisoformat(os.getenv("DATE_START", "2023-01-01")),
        "date_end": date.fromisoformat(os.getenv("DATE_END", "2025-05-31")),
    }


def main() -> None:
    cfg = _load_config()
    fake = init_seed(cfg["seed"])

    raw_dir = ROOT / "data" / "raw"
    ensure_dirs(
        [
            str(raw_dir / "master"),
            str(raw_dir / "hris"),
            str(raw_dir / "attendance"),
            str(raw_dir / "payroll"),
            str(raw_dir / "performance"),
            str(ROOT / "data" / "oltp" / "master"),
            str(ROOT / "data" / "oltp" / "transactional"),
        ]
    )

    print("=" * 72)
    print("RAW -> OLTP SYNTHETIC PIPELINE")
    print("=" * 72)

    print("\n[1/3] Generating RAW master + hris data...")
    jobs = generate_jobs()
    depts = generate_departments()
    stores = generate_stores(cfg["n_stores"])
    shifts = generate_shifts()
    employees = generate_employees_raw(
        fake=fake,
        jobs=jobs,
        depts=depts,
        stores=stores,
        n_employees=cfg["n_employees"],
        date_end=cfg["date_end"],
    )

    save_csv(jobs, str(raw_dir / "master"), "jobs_raw.csv")
    save_csv(depts, str(raw_dir / "master"), "departments_raw.csv")
    save_csv(stores, str(raw_dir / "master"), "stores_raw.csv")
    save_csv(shifts, str(raw_dir / "master"), "shifts_raw.csv")
    save_csv(employees, str(raw_dir / "hris"), "employees_raw.csv")

    print("\n[2/3] Generating RAW transactional data...")
    attendance = generate_attendance_events_raw(
        employees_raw=employees,
        shifts_raw=shifts,
        stores_raw=stores,
        date_start=cfg["date_start"],
        date_end=cfg["date_end"],
    )
    payroll = generate_payroll_raw(
        employees_raw=employees,
        jobs_raw=jobs,
        attendance_events_raw=attendance,
        date_start=cfg["date_start"],
        date_end=cfg["date_end"],
    )
    performance = generate_performance_raw(
        employees_raw=employees,
        stores_raw=stores,
        attendance_events_raw=attendance,
        date_start=cfg["date_start"],
        date_end=cfg["date_end"],
    )

    save_csv(attendance, str(raw_dir / "attendance"), "attendance_events_raw.csv")
    save_csv(payroll, str(raw_dir / "payroll"), "payroll_raw.csv")
    save_csv(performance, str(raw_dir / "performance"), "performance_raw.csv")

    print("\n[3/3] Transforming RAW -> OLTP...")
    summary = transform_raw_to_oltp(str(ROOT))

    print("\n" + "=" * 72)
    print("PIPELINE COMPLETE")
    print("=" * 72)
    for k, v in summary.items():
        print(f"{k:<24s}: {v:>10,} rows")
    print("\nOutput:")
    print(f"- RAW : {ROOT / 'data' / 'raw'}")
    print(f"- OLTP: {ROOT / 'data' / 'oltp'}")


if __name__ == "__main__":
    main()
