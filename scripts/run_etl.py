"""
Script: Run Full ETL Pipeline
==============================
Single entry-point that runs the COMPLETE data pipeline:

  Phase 1  -  RAW -> OLTP        (raw_to_oltp.py)
  Phase 2  -  OLTP -> Staging    (oltp_to_staging.py)
  Phase 3  -  Staging -> Warehouse  (staging_to_warehouse.py -- OLAP star schema)
  Phase 4  -  Warehouse -> Exports  (warehouse_to_exports.py -- dashboard-ready)

Usage:
    python scripts/run_etl.py              # full pipeline
    python scripts/run_etl.py --olap-only  # only phases 2-4 (skip raw->oltp)
"""

from __future__ import annotations

import os
import sys
import time

# Ensure project root is on the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)


def main() -> None:
    olap_only = "--olap-only" in sys.argv

    print()
    print("=" * 65)
    print("  HR Analytics -- Full ETL Pipeline")
    print("=" * 65)
    print()

    t0 = time.perf_counter()

    # -- Phase 1: RAW -> OLTP --------------------------------------------------
    if not olap_only:
        print("-" * 65)
        print(" PHASE 1/4: RAW -> OLTP")
        print("-" * 65)
        from etl.transform.raw_to_oltp import transform_raw_to_oltp
        oltp_counts = transform_raw_to_oltp(ROOT_DIR)
        print(f"\n  OLTP tables created: {oltp_counts}")
    else:
        print("  >> Skipping Phase 1 (--olap-only flag)\n")

    # -- Phase 2: OLTP -> Staging ----------------------------------------------
    print("-" * 65)
    print(" PHASE 2/4: OLTP -> Staging")
    print("-" * 65)
    from etl.transform.oltp_to_staging import transform_oltp_to_staging
    transform_oltp_to_staging(ROOT_DIR)

    # -- Phase 3: Staging -> Warehouse -----------------------------------------
    print()
    print("-" * 65)
    print(" PHASE 3/4: Staging -> Warehouse (OLAP Star Schema)")
    print("-" * 65)
    from etl.transform.staging_to_warehouse import transform_staging_to_warehouse
    warehouse_counts = transform_staging_to_warehouse(ROOT_DIR)

    # -- Phase 4: Warehouse -> Exports -----------------------------------------
    print()
    print("-" * 65)
    print(" PHASE 4/4: Warehouse -> Exports")
    print("-" * 65)
    from etl.transform.warehouse_to_exports import transform_warehouse_to_exports
    transform_warehouse_to_exports(ROOT_DIR)

    elapsed = time.perf_counter() - t0

    # -- Summary ---------------------------------------------------------------
    print()
    print("=" * 65)
    print("  FULL PIPELINE COMPLETE")
    print("=" * 65)

    total_rows = sum(warehouse_counts.values())
    print(f"  Warehouse tables : {len(warehouse_counts)}")
    print(f"  Total rows       : {total_rows:,}")
    print(f"  Elapsed time     : {elapsed:.2f}s")
    print()
    print("  >> Dashboard data ready at: data/exports/")
    print("  >> Run: cd dashboard && streamlit run app.py")
    print()


if __name__ == "__main__":
    main()
