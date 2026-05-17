# HR Analytics Data Warehouse

Project ini memisahkan alur data menjadi:
1. Raw data generation (`data/raw`)
2. Transform ke OLTP terstandar (`data/oltp`)
3. Siap dilanjutkan ke staging dan warehouse

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python synthetic_data/generate_all.py
```

## Output

- Raw layer:
  - `data/raw/master/*.csv`
  - `data/raw/hris/employees_raw.csv`
  - `data/raw/attendance/attendance_events_raw.csv`
  - `data/raw/payroll/payroll_raw.csv`
  - `data/raw/performance/performance_raw.csv`
- OLTP layer:
  - `data/oltp/master/*.csv`
  - `data/oltp/transactional/*.csv`

## Notes

- Raw data sengaja dibuat semi-noisy (format status campur, event IN/OUT granular, missing event kecil).
- Default generator sekarang disetel untuk menghasilkan total data di atas 1 juta baris.
- Transform di `etl/transform/raw_to_oltp.py` membersihkan dan menstandarkan data ke skema OLTP.
"# enterprise-hr-warehouse" 
