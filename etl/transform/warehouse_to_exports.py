"""
ETL Transform: Warehouse → Exports
====================================
Copies warehouse star-schema CSVs to the data/exports/ directory,
which is the data source consumed by the Streamlit dashboard.

This step provides a clean separation between the warehouse layer
(analytical processing) and the presentation layer (dashboard).
"""

from __future__ import annotations

import os
import shutil

import pandas as pd


def transform_warehouse_to_exports(base_dir: str) -> dict[str, int]:
    """
    Copy all warehouse CSV files to data/exports/ for dashboard consumption.

    Parameters
    ----------
    base_dir : str
        Project root directory.

    Returns
    -------
    dict  filename → row_count
    """

    wh_dir  = os.path.join(base_dir, "data", "warehouse")
    exp_dir = os.path.join(base_dir, "data", "exports")
    os.makedirs(exp_dir, exist_ok=True)

    if not os.path.exists(wh_dir):
        raise FileNotFoundError(
            f"Warehouse directory not found: {wh_dir}\n"
            "Run staging_to_warehouse.py first."
        )

    csv_files = sorted(f for f in os.listdir(wh_dir) if f.endswith(".csv"))

    if not csv_files:
        print("  [WARN] No CSV files found in data/warehouse/. Nothing to export.")
        return {}

    print("=" * 55)
    print(" Export: Warehouse -> Exports (Dashboard)")
    print("=" * 55)

    counts: dict[str, int] = {}

    for filename in csv_files:
        src = os.path.join(wh_dir, filename)
        dst = os.path.join(exp_dir, filename)

        # Read to get row count, then copy
        df = pd.read_csv(src)
        row_count = len(df)

        shutil.copy2(src, dst)
        counts[filename] = row_count
        print(f"  >> {filename:<40s} -> exports/  ({row_count:,} rows)")

    print(f"\n [OK] Exported {len(counts)} files to {exp_dir}")
    return counts


if __name__ == "__main__":
    base_directory = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    transform_warehouse_to_exports(base_directory)
