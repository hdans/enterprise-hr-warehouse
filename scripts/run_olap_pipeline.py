"""
Script: Run OLAP Pipeline
=========================
Single entry-point that runs the complete OLAP pipeline:

  1. OLTP -> Staging   (copy with stg_ prefix)
  2. Staging -> Warehouse  (star-schema transform)
  3. Warehouse -> Exports  (dashboard-ready CSVs)

Usage:
    python scripts/run_olap_pipeline.py
"""

from __future__ import annotations

import os
import sys
import time

# Ensure project root is on the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from etl.transform.oltp_to_staging import transform_oltp_to_staging
from etl.transform.staging_to_warehouse import transform_staging_to_warehouse
from etl.transform.warehouse_to_exports import transform_warehouse_to_exports
from etl.load.warehouse_to_supabase import load_to_supabase


def main() -> None:
    print()
    print("=" * 65)
    print("  HR Analytics -- OLAP Pipeline Orchestrator")
    print("=" * 65)
    print()

    t0 = time.perf_counter()

    # -- Step 1: OLTP -> Staging ------------------------------------------------
    print("-" * 65)
    print(" STEP 1/4: OLTP -> Staging")
    print("-" * 65)
    transform_oltp_to_staging(ROOT_DIR)

    # -- Step 2: Staging -> Warehouse -------------------------------------------
    print()
    print("-" * 65)
    print(" STEP 2/4: Staging -> Warehouse (Star Schema)")
    print("-" * 65)
    warehouse_counts = transform_staging_to_warehouse(ROOT_DIR)

    # -- Step 3: Warehouse -> Exports -------------------------------------------
    print()
    print("-" * 65)
    print(" STEP 3/4: Warehouse -> Exports (Dashboard)")
    print("-" * 65)
    export_counts = transform_warehouse_to_exports(ROOT_DIR)

    # -- Step 4: Exports -> Supabase --------------------------------------------
    print()
    print("-" * 65)
    print(" STEP 4/4: Upload Exports -> Supabase (Analytical Data)")
    print("-" * 65)
    load_to_supabase()


    elapsed = time.perf_counter() - t0

    # -- Summary ----------------------------------------------------------------
    print()
    print("=" * 65)
    print("  PIPELINE COMPLETE")
    print("=" * 65)

    total_rows = sum(warehouse_counts.values())
    print(f"  Total tables generated : {len(warehouse_counts)}")
    print(f"  Total rows             : {total_rows:,}")
    print(f"  Elapsed time           : {elapsed:.2f}s")
    print()
    print("  Table Breakdown:")
    for name, count in warehouse_counts.items():
        print(f"    {name:<38s} {count:>10,} rows")

    print()
    print("  >> Dashboard data ready at: data/exports/")
    print("  >> Run: cd dashboard && streamlit run app.py")
    print()


if __name__ == "__main__":
    main()
