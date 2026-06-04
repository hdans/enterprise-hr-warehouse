"""
HR Analytics Dashboard — Attendance Analysis
=============================================
File: pages/attendance_analysis.py

Employee attendance analysis by merging data from:
  - attendance_logs.csv  (~1,076,458 rows)
  - employees.csv        (~2,400 rows)

All data reader functions MUST use @st.cache_data.
Heavy operations on large datasets use Pandas aggregation
before passing to Plotly to remain responsive.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
from pathlib import Path
import components.shared as shared

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Attendance Analysis · HR Analytics",
    page_icon="🕐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
shared.inject_custom_css()

# ── Plotly Base Theme ─────────────────────────────────────────────────────────
PL = shared.get_plotly_theme()
GX  = dict(showgrid=True,  gridcolor="rgba(148,163,184,.15)", zeroline=False)
GY  = dict(showgrid=True,  gridcolor="rgba(148,163,184,.15)", zeroline=False)
NGX = dict(showgrid=False, zeroline=False)
NGY = dict(showgrid=False, zeroline=False)

C_PRESENT    = "#059669"
C_ABSENT     = "#DC2626"
C_LATE       = "#D97706"
C_LEAVE      = "#2563EB"
C_WFH        = "#7C3AED"
C_INCOMPLETE = "#EA580C"
C_EARLY      = "#8B5CF6"
STATUS_PAL = {
    "Present":      C_PRESENT,
    "Hadir":        C_PRESENT,
    "present":      C_PRESENT,
    "hadir":        C_PRESENT,
    "Late":         C_LATE,
    "Terlambat":    C_LATE,
    "late":         C_LATE,
    "Incomplete":   C_INCOMPLETE,
    "incomplete":   C_INCOMPLETE,
    "Early Leave":  C_EARLY,
    "early_leave":  C_EARLY,
    "early leave":  C_EARLY,
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Loading attendance data (1M+ rows, please wait)...")
def load_attendance() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("attendance_logs.csv"))

    # ── Detect & parse date column ────────────────────────────────────────────
    date_col = next(
        (c for c in df.columns
         if any(k in c.lower() for k in ["date", "tanggal", "log_date", "work_date", "attendance_date"])),
        None,
    )
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if date_col != "date":
            df = df.rename(columns={date_col: "date"})
    else:
        # fallback: try parsing first column
        df["date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")

    # ── Detect check-in / check-out columns ───────────────────────────────────
    for alias, target in [
        (["check_in", "time_in", "clock_in", "masuk", "checkin"], "check_in"),
        (["check_out", "time_out", "clock_out", "keluar", "checkout"], "check_out"),
    ]:
        match = next((c for c in df.columns if c.lower() in alias), None)
        if match and match != target:
            df = df.rename(columns={match: target})

    # ── Detect attendance status column ───────────────────────────────────────
    status_match = next(
        (c for c in df.columns
         if any(k in c.lower() for k in ["status", "attendance_status", "kehadiran", "type"])),
        None,
    )
    if status_match and status_match != "status":
        df = df.rename(columns={status_match: "status"})

    # ── Derived columns ───────────────────────────────────────────────────────
    if "date" in df.columns:
        df["year"]       = df["date"].dt.year
        df["month"]      = df["date"].dt.month
        df["month_name"] = df["date"].dt.strftime("%b %Y")
        df["week"]       = df["date"].dt.isocalendar().week.astype(int)
        df["weekday"]    = df["date"].dt.day_name()
        df["month_ts"]   = df["date"].dt.to_period("M").dt.to_timestamp()
        df["week_ts"]    = df["date"].dt.to_period("W").dt.to_timestamp()

    # ── Calculate work_hours if check_in & check_out present ──────────────────
    if "check_in" in df.columns and "check_out" in df.columns:
        try:
            # parse as time string, join with date
            ci = pd.to_datetime(
                df["date"].dt.strftime("%Y-%m-%d") + " " + df["check_in"].astype(str),
                errors="coerce",
            )
            co = pd.to_datetime(
                df["date"].dt.strftime("%Y-%m-%d") + " " + df["check_out"].astype(str),
                errors="coerce",
            )
            df["work_hours"] = ((co - ci).dt.total_seconds() / 3600).clip(lower=0, upper=24)
        except Exception:
            pass

    # ── Flag late if is_late / late column exists ─────────────────────────────
    late_col = next(
        (c for c in df.columns if any(k in c.lower() for k in ["late", "terlambat", "is_late"])),
        None,
    )
    if late_col and late_col != "is_late":
        df = df.rename(columns={late_col: "is_late"})

    return df


@st.cache_data(show_spinner="Loading employee data...")
def load_employees() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("employees.csv"))
    for col in ["hire_date", "birth_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading department data...")
def load_departments() -> pd.DataFrame:
    return pd.read_csv(shared.get_data_path("departments.csv"))


# ── Merge: attendance + employee info ─────────────────────────────────────────
@st.cache_data(show_spinner="Merging attendance & employee data...")
def build_att(_att: pd.DataFrame, _emp: pd.DataFrame, _dept: pd.DataFrame) -> pd.DataFrame:
    """
    Merge attendance_logs ← employees ← departments.
    Prefix '_' prevents Streamlit from hashing large DataFrames.
    """
    emp = _emp.copy()

    # Add department_name to emp if not present
    if "department_id" in emp.columns and "department_name" not in emp.columns:
        if "department_id" in _dept.columns and "department_name" in _dept.columns:
            emp = emp.merge(
                _dept[["department_id", "department_name"]],
                on="department_id", how="left",
            )

    # Minimal columns from emp to merge with att
    keep_emp = ["employee_id"] + [
        c for c in ["department_name", "department_id", "gender", "job_id",
                    "first_name", "last_name", "status"]
        if c in emp.columns
    ]

    merged = _att.merge(emp[keep_emp], on="employee_id", how="left")
    return merged


# ── Heavy aggregations cached separately ──────────────────────────────────────

@st.cache_data(show_spinner=False)
def agg_monthly(_df: pd.DataFrame) -> pd.DataFrame:
    """Monthly aggregation: attendance, late, incomplete, early leave rates."""
    if "month_ts" not in _df.columns:
        return pd.DataFrame()

    grp = _df.groupby("month_ts")
    total       = grp["employee_id"].count().rename("total_logs")
    present     = _df[_df.get("status", pd.Series(dtype=str)).isin(
                       ["Present","Hadir","present","hadir"])] \
                    .groupby("month_ts")["employee_id"].count().rename("present") \
                    if "status" in _df.columns else pd.Series(dtype=int, name="present")
    late        = _df[_df.get("status", pd.Series(dtype=str)).isin(
                       ["Late","Terlambat","late"])] \
                    .groupby("month_ts")["employee_id"].count().rename("late") \
                    if "status" in _df.columns else pd.Series(dtype=int, name="late")
    incomplete  = _df[_df.get("status", pd.Series(dtype=str)).isin(
                       ["Incomplete","incomplete"])] \
                    .groupby("month_ts")["employee_id"].count().rename("incomplete") \
                    if "status" in _df.columns else pd.Series(dtype=int, name="incomplete")
    early_leave = _df[_df.get("status", pd.Series(dtype=str)).isin(
                       ["Early Leave","early_leave","early leave"])] \
                    .groupby("month_ts")["employee_id"].count().rename("early_leave") \
                    if "status" in _df.columns else pd.Series(dtype=int, name="early_leave")

    result = pd.concat([total, present, late, incomplete, early_leave], axis=1).fillna(0).reset_index()
    result["attendance_rate"] = (result.get("present", 0) / result["total_logs"] * 100).round(2)
    result["late_rate"]       = (result.get("late",    0) / result["total_logs"] * 100).round(2)
    result["incomplete_rate"] = (result.get("incomplete", 0) / result["total_logs"] * 100).round(2)
    result["early_leave_rate"]= (result.get("early_leave", 0) / result["total_logs"] * 100).round(2)
    return result.sort_values("month_ts")


@st.cache_data(show_spinner=False)
def agg_by_status(_df: pd.DataFrame) -> pd.DataFrame:
    if "status" not in _df.columns:
        return pd.DataFrame()
    cnt = _df["status"].value_counts().reset_index()
    cnt.columns = ["status", "count"]
    cnt["pct"] = (cnt["count"] / cnt["count"].sum() * 100).round(1)
    return cnt


@st.cache_data(show_spinner=False)
def agg_by_dept(_df: pd.DataFrame) -> pd.DataFrame:
    dept_col = next((c for c in ["department_name","department_id"] if c in _df.columns), None)
    if not dept_col or "status" not in _df.columns:
        return pd.DataFrame()

    total      = _df.groupby(dept_col).size().rename("total")
    present    = _df[_df["status"].isin(["Present","Hadir","present","hadir"])]\
                   .groupby(dept_col).size().rename("present")
    incomplete = _df[_df["status"].isin(["Incomplete","incomplete"])]\
                   .groupby(dept_col).size().rename("incomplete")
    late       = _df[_df["status"].isin(["Late","Terlambat","late"])]\
                   .groupby(dept_col).size().rename("late")

    result = pd.concat([total, present, incomplete, late], axis=1).fillna(0).reset_index()
    result["att_rate"]        = (result.get("present", 0) / result["total"] * 100).round(1)
    result["incomplete_rate"] = (result.get("incomplete", 0) / result["total"] * 100).round(1)
    result["late_rate"]       = (result.get("late",    0) / result["total"] * 100).round(1)
    result.rename(columns={dept_col: "department"}, inplace=True)
    return result.sort_values("total", ascending=False)


@st.cache_data(show_spinner=False)
def agg_by_weekday(_df: pd.DataFrame) -> pd.DataFrame:
    if "weekday" not in _df.columns or "status" not in _df.columns:
        return pd.DataFrame()

    ORDER  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    LABEL  = {"Monday":"Mon","Tuesday":"Tue","Wednesday":"Wed",
              "Thursday":"Thu","Friday":"Fri","Saturday":"Sat","Sunday":"Sun"}

    total      = _df.groupby("weekday").size().rename("total")
    incomplete = _df[_df["status"].isin(["Incomplete","incomplete"])]\
                   .groupby("weekday").size().rename("incomplete")
    late       = _df[_df["status"].isin(["Late","Terlambat","late"])]\
                   .groupby("weekday").size().rename("late")

    result = pd.concat([total, incomplete, late], axis=1).fillna(0).reset_index()
    result["incomplete_rate"] = (result.get("incomplete", 0) / result["total"] * 100).round(1)
    result["late_rate"]       = (result.get("late",   0) / result["total"] * 100).round(1)
    result["weekday"]         = pd.Categorical(result["weekday"], categories=ORDER, ordered=True)
    result["label"]           = result["weekday"].map(LABEL)
    return result.sort_values("weekday")


@st.cache_data(show_spinner=False)
def worst_incomplete_logs(_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if "status" not in _df.columns:
        return pd.DataFrame()
    inc_df = _df[_df["status"].isin(["Incomplete","incomplete"])]
    result = inc_df.groupby("employee_id").size().nlargest(top_n).reset_index(name="incomplete_days")

    name_cols = [c for c in ["first_name","last_name","department_name"] if c in _df.columns]
    if name_cols:
        info = _df[["employee_id"] + name_cols].drop_duplicates("employee_id")
        result = result.merge(info, on="employee_id", how="left")

    total_days = _df.groupby("employee_id").size().rename("total_days")
    result = result.merge(total_days, on="employee_id", how="left")
    result["incomplete_rate"] = (result["incomplete_days"] / result["total_days"] * 100).round(1)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════════

try:
    att_raw  = load_attendance()
    emp_raw  = load_employees()
    dept_raw = load_departments()
    att_full = build_att(att_raw, emp_raw, dept_raw)
    data_ok  = True
except FileNotFoundError as e:
    data_ok    = False
    load_error = str(e)

# ── Dynamic Column Detection ──────────────────────────────────────────────────
if data_ok:
    HAS_STATUS  = "status" in att_full.columns
    HAS_DATE    = "date"   in att_full.columns
    HAS_LATE    = "is_late" in att_full.columns
    HAS_HOURS   = "work_hours" in att_full.columns
    DEPT_COL    = next((c for c in ["department_name","department_id"] if c in att_full.columns), None)
    GENDER_COL  = next((c for c in ["gender","sex"] if c in att_full.columns), None)

    DATE_MIN = att_full["date"].min().date() if HAS_DATE else date(2020, 1, 1)
    DATE_MAX = att_full["date"].max().date() if HAS_DATE else date.today()


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Filters
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    shared.add_sidebar_header()

    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .5rem;'>📅 Time Range</div>",
        unsafe_allow_html=True,
    )

    if data_ok and HAS_DATE:
        # ── Quick-select preset ────────────────────────────────────────────────
        preset = st.selectbox(
            "Quick Period",
            ["Custom", "Last 30 Days", "Last 90 Days",
             "Last 6 Months", "Last Year", "All Data"],
            index=5,
        )

        today = DATE_MAX
        if preset == "Last 30 Days":
            d_start, d_end = today - timedelta(days=30), today
        elif preset == "Last 90 Days":
            d_start, d_end = today - timedelta(days=90), today
        elif preset == "Last 6 Months":
            d_start, d_end = today - timedelta(days=180), today
        elif preset == "Last Year":
            d_start, d_end = today - timedelta(days=365), today
        elif preset == "All Data":
            d_start, d_end = DATE_MIN, DATE_MAX
        else:
            d_start, d_end = DATE_MIN, DATE_MAX   # default for Custom

        # ── Manual date picker (active only during Custom) ────────────────────
        disabled_picker = preset != "Custom"
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            sel_start = st.date_input(
                "From", value=d_start,
                min_value=DATE_MIN, max_value=DATE_MAX,
                disabled=disabled_picker, key="date_start",
            )
        with col_d2:
            sel_end = st.date_input(
                "To", value=d_end,
                min_value=DATE_MIN, max_value=DATE_MAX,
                disabled=disabled_picker, key="date_end",
            )

        if preset != "Custom":
            sel_start, sel_end = d_start, d_end

        # Validation
        if sel_start > sel_end:
            st.error("Start date cannot exceed end date.")
            sel_start = d_start

    else:
        sel_start = sel_end = date.today()

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .5rem;'>🔍 Additional Filters</div>",
        unsafe_allow_html=True,
    )

    if data_ok:
        dept_opts = ["All"]
        if DEPT_COL:
            dept_opts += sorted(att_full[DEPT_COL].dropna().unique().tolist())
        sel_dept = st.selectbox("🏢 Department", dept_opts)

        if HAS_STATUS:
            status_opts = ["All"] + sorted(att_full["status"].dropna().unique().tolist())
            sel_status = st.selectbox("📋 Attendance Status", status_opts)
        else:
            sel_status = "All"

        top_n_dept = st.slider("Top N Departments", 3, max(4, len(dept_opts) - 1), 8)

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.7rem;color:#64748B;padding:.5rem;line-height:1.5;'>"
        "📄 Synthetic data · Not production data</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GUARD
# ═══════════════════════════════════════════════════════════════════════════════

if not data_ok:
    st.error(
        f"❌ **File not found**: `{load_error}`\n\n"
        "Make sure the 'data/oltp/' directory contains 'attendance_logs.csv' and 'employees.csv'."
    )
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# APPLY FILTERS
# ═══════════════════════════════════════════════════════════════════════════════

df = att_full.copy()

# 1. Date Range Filter
if HAS_DATE:
    mask_date = (df["date"].dt.date >= sel_start) & (df["date"].dt.date <= sel_end)
    df = df[mask_date]

# 2. Department Filter
if sel_dept != "All" and DEPT_COL:
    df = df[df[DEPT_COL] == sel_dept]

# 3. Status Filter
if sel_status != "All" and HAS_STATUS:
    df = df[df["status"] == sel_status]

total_records = len(df)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE KPI
# ═══════════════════════════════════════════════════════════════════════════════

unique_emp     = df["employee_id"].nunique()
working_days   = df["date"].nunique() if HAS_DATE else 0

if HAS_STATUS:
    n_present     = df["status"].isin(["Present","Hadir","present","hadir"]).sum()
    n_late        = df["status"].isin(["Late","Terlambat","late"]).sum()
    n_incomplete  = df["status"].isin(["Incomplete","incomplete"]).sum()
    n_early_leave = df["status"].isin(["Early Leave","early_leave","early leave"]).sum()

    att_rate        = round(n_present     / total_records * 100, 1) if total_records else 0.0
    late_rate       = round(n_late        / total_records * 100, 1) if total_records else 0.0
    incomplete_rate = round(n_incomplete  / total_records * 100, 1) if total_records else 0.0
    early_leave_rate= round(n_early_leave / total_records * 100, 1) if total_records else 0.0
else:
    att_rate = late_rate = incomplete_rate = early_leave_rate = 0.0
    n_present = n_late = n_incomplete = n_early_leave = 0

avg_hours = df["work_hours"].mean() if HAS_HOURS else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div style="margin-bottom:1.5rem;">
        <div style="display:flex;align-items:center;gap:.75rem;">
            <span style="font-size:1.8rem;">🕐</span>
            <div>
                <h1 style="margin:0;font-size:1.8rem;font-weight:800;
                           background:linear-gradient(135deg,#059669,#2563EB);
                           -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                           background-clip:text;line-height:1.2;">
                    Attendance Analysis
                </h1>
                 <p style="margin:0;font-size:.88rem;color:var(--text-secondary);">
                     Overall employee attendance, lateness, and daily/department trends
                 </p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Info bar time range & record count ────────────────────────────────────────
date_label = (
    f"{sel_start.strftime('%d %b %Y')} — {sel_end.strftime('%d %b %Y')}"
    if HAS_DATE else "All Data"
)
badges_info = [
    ("📅", date_label),
    ("📊", f"{total_records:,} logs"),
    ("👥", f"{unique_emp:,} employees"),
    ("📆", f"{working_days:,} workdays"),
]
if sel_dept != "All":
    badges_info.append(("🏢", sel_dept))

badge_html = " &nbsp; ".join(
    f'<span style="background:rgba(5,150,105,.1);color:#065F46;'
    f'padding:.2rem .65rem;border-radius:20px;font-size:.78rem;font-weight:600;">'
    f'{icon} {label}</span>'
    for icon, label in badges_info
)
st.markdown(f'<div style="margin-bottom:1.25rem;">{badge_html}</div>', unsafe_allow_html=True)
st.markdown('<hr>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# KPI ROW
# ═══════════════════════════════════════════════════════════════════════════════

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric("🟢 Attendance Rate", f"{att_rate:.1f}%",
              delta="✓ Good" if att_rate >= 90 else "⚠ Needs Attention",
              delta_color="normal" if att_rate >= 90 else "inverse")
with k2:
    st.metric("🟠 Incomplete / Early Leave", f"{incomplete_rate:.1f}%",
              delta="⚠ High" if incomplete_rate > 20 else "✓ Normal",
              delta_color="inverse" if incomplete_rate > 20 else "normal")
with k3:
    st.metric("🟡 Late Rate", f"{late_rate:.1f}%",
              delta="⚠ High" if late_rate > 10 else "✓ Normal",
              delta_color="inverse" if late_rate > 10 else "normal")
with k4:
    st.metric("👥 Active Employees", f"{unique_emp:,}",
              delta=f"{working_days:,} workdays", delta_color="off")
with k5:
    st.metric("📋 Total Logs", f"{total_records:,}",
              delta=f"Average {total_records//max(working_days,1):,}/day" if working_days else "—",
              delta_color="off")
with k6:
    st.metric("🟣 Early Leave", f"{n_early_leave:,}",
              delta=f"{early_leave_rate:.1f}% of total" if total_records else "—",
              delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS SUMMARY BAR
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_STATUS and total_records > 0:
    status_counts = agg_by_status(df)
    if not status_counts.empty:
        items_html = ""
        for _, row in status_counts.iterrows():
            color = STATUS_PAL.get(row["status"], "#94A3B8")
            items_html += (
                f'<div style="flex:1;min-width:100px;background:var(--bg-card);'
                f'border:1px solid var(--border);border-top:3px solid {color};'
                f'border-radius:10px;padding:.8rem 1rem;text-align:center;">'
                f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.06em;color:{color};">{row["status"]}</div>'
                f'<div style="font-size:1.4rem;font-weight:800;color:var(--text-primary);">'
                f'{int(row["count"]):,}</div>'
                f'<div style="font-size:.78rem;color:var(--text-secondary);">{row["pct"]}%</div>'
                f'</div>'
            )
        st.markdown(
            f'<div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-bottom:1.5rem;">'
            f'{items_html}</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Monthly Trend",
    "📅 Daily Pattern",
    "🏢 By Department",
    "⚠️ Lateness & Incomplete Logs",
])


# ──────────────────────────────────────────────────────────────────────────────
# TAB 1 · MONTHLY TREND
# ──────────────────────────────────────────────────────────────────────────────
with tab1:
    monthly = agg_monthly(df)

    if monthly.empty:
        st.info("Monthly trend data not available. Make sure date column is correctly detected.")
    else:
        # ── Chart 1: Attendance Rate Trend ────────────────────────────────────
        col_trend, col_donut = st.columns([2.4, 1])

        with col_trend:
            fig_trend = make_subplots(specs=[[{"secondary_y": True}]])

            # Stacked bar: present, late, incomplete, early leave
            for col_name, color, label in [
                ("present",     C_PRESENT,    "Present"),
                ("late",        C_LATE,       "Late"),
                ("incomplete",  C_INCOMPLETE, "Incomplete"),
                ("early_leave", C_EARLY,      "Early Leave"),
            ]:
                if col_name in monthly.columns:
                    fig_trend.add_trace(
                        go.Bar(
                            x=monthly["month_ts"],
                            y=monthly[col_name],
                            name=label,
                            marker_color=color,
                            opacity=0.85,
                            hovertemplate=f"<b>%{{x|%b %Y}}</b><br>{label}: %{{y:,}}<extra></extra>",
                        ),
                        secondary_y=False,
                    )

            # Line: attendance rate
            fig_trend.add_trace(
                go.Scatter(
                    x=monthly["month_ts"],
                    y=monthly["attendance_rate"],
                    name="Attendance Rate (%)",
                    mode="lines+markers",
                    line=dict(color="#0F172A", width=2.5),
                    marker=dict(size=6, color="#0F172A"),
                    hovertemplate="<b>%{x|%b %Y}</b><br>Rate: %{y:.1f}%<extra></extra>",
                ),
                secondary_y=True,
            )

            fig_trend.update_layout(
                **PL,
                title=dict(text="Monthly Attendance Logs Trend", font=dict(size=13)),
                barmode="stack",
                xaxis=dict(**NGX, tickformat="%b %Y"),
                yaxis=dict(**GY, title="Log Count"),
                yaxis2=dict(
                    title="Attendance Rate (%)",
                    showgrid=False, range=[0, 110],
                    ticksuffix="%",
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # ── Donut Chart composition ───────────────────────────────────────────
        with col_donut:
            status_df = agg_by_status(df)
            if not status_df.empty:
                colors = [STATUS_PAL.get(s, "#94A3B8") for s in status_df["status"]]
                fig_donut = go.Figure(
                    go.Pie(
                        labels=status_df["status"],
                        values=status_df["count"],
                        hole=0.60,
                        marker_colors=colors,
                        textinfo="label+percent",
                        textfont=dict(size=11, family="DM Sans"),
                        hovertemplate="<b>%{label}</b><br>%{value:,} logs (%{percent})<extra></extra>",
                        pull=[0.03] * len(status_df),
                    )
                )
                fig_donut.add_annotation(
                    text=f"<b>{total_records:,}</b><br><span>Total</span>",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=15, family="DM Sans"),
                    xanchor="center", yanchor="middle",
                )
                fig_donut.update_layout(
                    **{**PL, "margin": dict(l=0, r=0, t=36, b=40)},
                    title=dict(text="Status Composition", font=dict(size=13)),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                    height=380,
                )
                st.plotly_chart(fig_donut, use_container_width=True)

        # ── Chart 2: Monthly Rate Lines ───────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        fig_rate = go.Figure()

        for col_name, color, label, dash in [
            ("attendance_rate", C_PRESENT,    "Attendance Rate", "solid"),
            ("late_rate",       C_LATE,       "Late Rate",       "dot"),
            ("incomplete_rate", C_INCOMPLETE, "Incomplete Rate", "dash"),
        ]:
            if col_name in monthly.columns:
                fig_rate.add_trace(
                    go.Scatter(
                        x=monthly["month_ts"],
                        y=monthly[col_name],
                        name=label,
                        mode="lines+markers",
                        line=dict(color=color, width=2.5, dash=dash),
                        marker=dict(size=6),
                        fill="tozeroy" if col_name == "attendance_rate" else None,
                        fillcolor="rgba(5,150,105,.06)" if col_name == "attendance_rate" else None,
                        hovertemplate=f"<b>%{{x|%b %Y}}</b><br>{label}: %{{y:.1f}}%<extra></extra>",
                    )
                )

        # Target line 90%
        fig_rate.add_hline(
            y=90, line_dash="dash", line_color="#94A3B8", line_width=1.2,
            annotation_text="Target 90%", annotation_position="bottom right",
        )
        fig_rate.update_layout(
            **PL,
            title=dict(text="Attendance & Late Rates (%)", font=dict(size=13)),
            xaxis=dict(**NGX, tickformat="%b %Y"),
            yaxis=dict(**GY, title="Percentage (%)", ticksuffix="%", range=[0, 110]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=320,
        )
        st.plotly_chart(fig_rate, use_container_width=True)

        # ── Monthly Summary Table ─────────────────────────────────────────────
        with st.expander("📋 View monthly data table", expanded=False):
            show_monthly = monthly.copy()
            show_monthly["month_ts"] = show_monthly["month_ts"].dt.strftime("%b %Y")
            show_monthly.rename(columns={
                "month_ts":        "Month",
                "total_logs":      "Total Logs",
                "present":         "Present",
                "late":            "Late",
                "incomplete":      "Incomplete",
                "early_leave":     "Early Leave",
                "attendance_rate": "Attendance Rate (%)",
                "late_rate":       "Late Rate (%)",
                "incomplete_rate": "Incomplete Rate (%)",
                "early_leave_rate":"Early Leave Rate (%)",
            }, inplace=True)
            cols_show_m = [
                "Month", "Total Logs", "Present", "Late", "Incomplete", "Early Leave",
                "Attendance Rate (%)", "Late Rate (%)", "Incomplete Rate (%)", "Early Leave Rate (%)"
            ]
            cols_show_m = [c for c in cols_show_m if c in show_monthly.columns]
            st.dataframe(show_monthly[cols_show_m], use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 2 · DAILY PATTERN
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    weekday_df = agg_by_weekday(df)

    if weekday_df.empty:
        st.info("Daily pattern data not available.")
    else:
        col_wd1, col_wd2 = st.columns(2)

        # ── Bar: Total log per day ─────────────────────────────────────────────
        with col_wd1:
            fig_wd = go.Figure(
                go.Bar(
                    x=weekday_df["label"],
                    y=weekday_df["total"],
                    marker=dict(
                        color=weekday_df["total"],
                        colorscale=[[0,"#D1FAE5"],[1,"#065F46"]],
                        showscale=False,
                    ),
                    text=weekday_df["total"].apply(lambda v: f"{v:,}"),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Total Logs: %{y:,}<extra></extra>",
                )
            )
            fig_wd.update_layout(
                **PL,
                title=dict(text="Total Attendance Logs by Day", font=dict(size=13)),
                xaxis=dict(**NGX, title=""),
                yaxis=dict(**GY, title="Log Count"),
                height=320,
            )
            st.plotly_chart(fig_wd, use_container_width=True)

        # ── Bar: Absenteeism & Late Rate per Day ──────────────────────────────
        with col_wd2:
            fig_wd2 = go.Figure()
            fig_wd2.add_trace(
                go.Bar(
                    x=weekday_df["label"], y=weekday_df["incomplete_rate"],
                    name="Incomplete Rate",
                    marker_color=C_INCOMPLETE, opacity=0.85,
                    text=weekday_df["incomplete_rate"].apply(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Incomplete: %{y:.1f}%<extra></extra>",
                )
            )
            fig_wd2.add_trace(
                go.Bar(
                    x=weekday_df["label"], y=weekday_df["late_rate"],
                    name="Late Rate",
                    marker_color=C_LATE, opacity=0.85,
                    text=weekday_df["late_rate"].apply(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Late: %{y:.1f}%<extra></extra>",
                )
            )
            fig_wd2.update_layout(
                **PL,
                title=dict(text="Incomplete & Late Rates by Day (%)", font=dict(size=13)),
                barmode="group",
                xaxis=dict(**NGX, title=""),
                yaxis=dict(**GY, title="Rate (%)", ticksuffix="%"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                height=320,
            )
            st.plotly_chart(fig_wd2, use_container_width=True)

    # ── Heatmap: Status × Weekday × Month ─────────────────────────────────────
    if HAS_STATUS and HAS_DATE and "weekday" in df.columns:
        st.markdown("<br>", unsafe_allow_html=True)
        ORDER   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        LABEL_M = {"Monday":"Mon","Tuesday":"Tue","Wednesday":"Wed",
                   "Thursday":"Thu","Friday":"Fri","Saturday":"Sat","Sunday":"Sun"}

        inc_sub = df[df["status"].isin(["Incomplete","incomplete"])].copy()
        if not inc_sub.empty and "month_ts" in inc_sub.columns:
            hm = (
                inc_sub.groupby(["month_ts", "weekday"])
                .size()
                .unstack(fill_value=0)
            )
            # sort columns
            hm = hm.reindex(columns=[c for c in ORDER if c in hm.columns])
            hm.columns = [LABEL_M.get(c, c) for c in hm.columns]
            hm.index   = hm.index.strftime("%b %Y")

            fig_hm = px.imshow(
                hm,
                color_continuous_scale=[[0,"#F8FAFC"],[0.5,"#FED7AA"],[1,"#C2410C"]],
                aspect="auto",
                text_auto=True,
                labels=dict(x="Day", y="Month", color="Incomplete Logs"),
            )
            fig_hm.update_traces(
                textfont=dict(size=10, family="DM Sans"),
                hovertemplate="<b>%{y} — %{x}</b><br>Incomplete Logs Count: %{z:,}<extra></extra>",
            )
            fig_hm.update_layout(
                **{**PL, "margin": dict(l=0, r=60, t=36, b=0)},
                title=dict(text="Incomplete Logs Heatmap: Month × Day", font=dict(size=13)),
                xaxis=dict(title="", side="bottom"),
                yaxis=dict(title=""),
                coloraxis_showscale=True,
                height=max(260, len(hm) * 26 + 80),
            )
            st.plotly_chart(fig_hm, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 3 · BY DEPARTMENT
# ──────────────────────────────────────────────────────────────────────────────
with tab3:
    dept_df_agg = agg_by_dept(df)

    if dept_df_agg.empty:
        st.info("Department data not available. Make sure department column is detected.")
    else:
        dept_top = dept_df_agg.nlargest(top_n_dept, "total")

        col_d1, col_d2 = st.columns(2)

        # ── Grouped bar: rate present, incomplete & late per dept ──────────────
        with col_d1:
            fig_dept_rate = go.Figure()
            for col_name, color, label in [
                ("att_rate",        C_PRESENT,    "Attendance Rate"),
                ("incomplete_rate", C_INCOMPLETE, "Incomplete Rate"),
                ("late_rate",       C_LATE,       "Late Rate"),
            ]:
                if col_name in dept_top.columns:
                    fig_dept_rate.add_trace(
                        go.Bar(
                            y=dept_top["department"],
                            x=dept_top[col_name],
                            name=label,
                            orientation="h",
                            marker_color=color,
                            opacity=0.85,
                            text=dept_top[col_name].apply(lambda v: f"{v:.1f}%"),
                            textposition="inside",
                            textfont=dict(size=9),
                            hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{x:.1f}}%<extra></extra>",
                        )
                    )
            fig_dept_rate.update_layout(
                **PL,
                title=dict(text=f"Attendance, Incomplete & Late Rates by Department (Top {top_n_dept})", font=dict(size=13)),
                barmode="group",
                xaxis=dict(**GX, title="Rate (%)", ticksuffix="%"),
                yaxis=dict(**NGY, title="", categoryorder="total ascending"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                height=max(320, top_n_dept * 42 + 100),
            )
            st.plotly_chart(fig_dept_rate, use_container_width=True)

        # ── Dot / lollipop: attendance rate ranking ────────────────────────────
        with col_d2:
            dept_ranked = dept_df_agg.sort_values("att_rate", ascending=True).tail(top_n_dept)
            colors_dot  = [C_PRESENT if v >= 90 else C_ABSENT for v in dept_ranked["att_rate"]]

            fig_dot = go.Figure()
            # Horizontal lines (lollipop sticks)
            for i, row in dept_ranked.iterrows():
                fig_dot.add_shape(
                    type="line",
                    x0=0, x1=row["att_rate"],
                    y0=row["department"], y1=row["department"],
                    line=dict(color="rgba(148,163,184,.35)", width=6),
                )
            # Dots
            fig_dot.add_trace(
                go.Scatter(
                    x=dept_ranked["att_rate"],
                    y=dept_ranked["department"],
                    mode="markers+text",
                    marker=dict(size=14, color=colors_dot, line=dict(color="#fff", width=2)),
                    text=dept_ranked["att_rate"].apply(lambda v: f"{v:.1f}%"),
                    textposition="middle right",
                    textfont=dict(size=10),
                    hovertemplate="<b>%{y}</b><br>Attendance Rate: %{x:.1f}%<extra></extra>",
                    showlegend=False,
                )
            )
            fig_dot.add_vline(
                x=90, line_dash="dash", line_color="#94A3B8", line_width=1.2,
                annotation_text="Target 90%", annotation_position="top",
            )
            fig_dot.update_layout(
                **PL,
                title=dict(text="Attendance Rate Ranking by Department", font=dict(size=13)),
                xaxis=dict(**GX, title="Attendance Rate (%)", ticksuffix="%", range=[0, 110]),
                yaxis=dict(**NGY, title=""),
                height=max(320, top_n_dept * 42 + 100),
            )
            st.plotly_chart(fig_dot, use_container_width=True)

        # ── Department monthly trend line chart ────────────────────────────────
        if HAS_DATE and DEPT_COL and "month_ts" in df.columns:
            st.markdown("<br>", unsafe_allow_html=True)
            top_dept_names = dept_df_agg.nlargest(min(6, top_n_dept), "total")["department"].tolist()

            dept_monthly_df = (
                df[df[DEPT_COL].isin(top_dept_names)]
                .groupby([DEPT_COL, "month_ts"])
                .apply(lambda g: pd.Series({
                    "att_rate": (g["status"].isin(["Present","Hadir","present","hadir"]).sum()
                                 / len(g) * 100) if HAS_STATUS else 0.0
                }))
                .reset_index()
            )

            if not dept_monthly_df.empty and "att_rate" in dept_monthly_df.columns:
                fig_dept_trend = px.line(
                    dept_monthly_df,
                    x="month_ts",
                    y="att_rate",
                    color=DEPT_COL,
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    labels={"month_ts": "Month", "att_rate": "Attendance Rate (%)", DEPT_COL: "Department"},
                )
                fig_dept_trend.update_traces(
                    hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %Y}: %{y:.1f}%<extra></extra>"
                )
                fig_dept_trend.add_hline(
                    y=90, line_dash="dash", line_color="#94A3B8", line_width=1.2,
                    annotation_text="Target 90%",
                )
                fig_dept_trend.update_layout(
                    **PL,
                    title=dict(text="Department Attendance Rate Trend (Monthly)", font=dict(size=13)),
                    xaxis=dict(**NGX, tickformat="%b %Y"),
                    yaxis=dict(**GY, title="Attendance Rate (%)", ticksuffix="%", range=[0, 110]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                    height=340,
                )
                st.plotly_chart(fig_dept_trend, use_container_width=True)

        # ── Department summary table ───────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        show_dept = dept_df_agg.rename(columns={
            "department":      "Department",
            "total":           "Total Logs",
            "present":         "Present",
            "incomplete":      "Incomplete",
            "late":            "Late",
            "att_rate":        "Attendance Rate (%)",
            "incomplete_rate": "Incomplete Rate (%)",
            "late_rate":       "Late Rate (%)",
        }).reset_index(drop=True)
        # Only show columns that exist
        show_cols = [c for c in [
            "Department", "Total Logs", "Present", "Incomplete", "Late",
            "Attendance Rate (%)", "Incomplete Rate (%)", "Late Rate (%)"
        ] if c in show_dept.columns]
        st.dataframe(
            show_dept[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Attendance Rate (%)": st.column_config.ProgressColumn(
                    "Attendance Rate (%)", min_value=0, max_value=100, format="%.1f%%"),
                "Incomplete Rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "Late Rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )


# ──────────────────────────────────────────────────────────────────────────────
# TAB 4 · ABSENTEEISM & LATENESS
# ──────────────────────────────────────────────────────────────────────────────
with tab4:
    # ── Late distribution ─────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:.9rem;font-weight:700;margin-bottom:.6rem;">'
        '🟡 Late Distribution & Trend</div>',
        unsafe_allow_html=True,
    )

    if HAS_STATUS:
        late_df = df[df["status"].isin(["Late","Terlambat","late"])].copy()

        if not late_df.empty:
            col_late1, col_late2 = st.columns(2)

            # ── Pie: late per dept ─────────────────────────────────────────
            with col_late1:
                if DEPT_COL and DEPT_COL in late_df.columns:
                    late_dept = late_df[DEPT_COL].value_counts().nlargest(8).reset_index()
                    late_dept.columns = ["dept", "count"]

                    fig_late_pie = go.Figure(
                        go.Pie(
                            labels=late_dept["dept"],
                            values=late_dept["count"],
                            hole=0.50,
                            marker_colors=px.colors.qualitative.Pastel,
                            textinfo="label+percent",
                            textfont=dict(size=10, family="DM Sans"),
                            hovertemplate="<b>%{label}</b><br>%{value:,} times late<extra></extra>",
                        )
                    )
                    fig_late_pie.add_annotation(
                        text=f"<b>{n_late:,}</b><br><span style='font-size:10px'>Late</span>",
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(size=15, family="DM Sans"),
                        xanchor="center", yanchor="middle",
                    )
                    fig_late_pie.update_layout(
                        **{**PL, "margin": dict(l=0, r=0, t=36, b=10)},
                        title=dict(text="Late Count by Department", font=dict(size=12)),
                        legend=dict(orientation="v", x=1, y=0.5, font=dict(size=10)),
                        height=280,
                    )
                    st.plotly_chart(fig_late_pie, use_container_width=True)

            # ── Bar: late per workday ──────────────────────────────────────
            with col_late2:
                if "weekday" in late_df.columns:
                    ORDER_  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                    LMAP    = {"Monday":"Mon","Tuesday":"Tue","Wednesday":"Wed",
                               "Thursday":"Thu","Friday":"Fri","Saturday":"Sat","Sunday":"Sun"}
                    wd_late = late_df["weekday"].value_counts().reindex(ORDER_).fillna(0).reset_index()
                    wd_late.columns = ["weekday", "count"]
                    wd_late["label"] = wd_late["weekday"].map(LMAP)

                    fig_wd_late = go.Figure(
                        go.Bar(
                            x=wd_late["label"],
                            y=wd_late["count"],
                            marker=dict(
                                color=wd_late["count"],
                                colorscale=[[0,"#FEF3C7"],[1,"#92400E"]],
                                showscale=False,
                            ),
                            text=wd_late["count"].astype(int),
                            textposition="outside",
                            hovertemplate="<b>%{x}</b><br>Late: %{y:,}<extra></extra>",
                        )
                    )
                    fig_wd_late.update_layout(
                        **PL,
                        title=dict(text="Late Count by Workday", font=dict(size=12)),
                        xaxis=dict(**NGX, title=""),
                        yaxis=dict(**GY, title="Count"),
                        height=280,
                    )
                    st.plotly_chart(fig_wd_late, use_container_width=True)
        else:
            st.info("No late data in this period.")
    else:
        st.info("Column 'status' not detected. Cannot identify late arrivals.")

    # ── Monthly late trend (full-width) ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    monthly2 = agg_monthly(df)
    if not monthly2.empty and "late" in monthly2.columns:
        fig_late_trend = go.Figure()
        fig_late_trend.add_trace(
            go.Bar(
                x=monthly2["month_ts"],
                y=monthly2["late"],
                name="Late Count",
                marker_color=C_LATE,
                opacity=0.80,
                hovertemplate="<b>%{x|%b %Y}</b><br>Late: %{y:,}<extra></extra>",
            )
        )
        fig_late_trend.add_trace(
            go.Scatter(
                x=monthly2["month_ts"],
                y=monthly2["late_rate"],
                name="Late Rate (%)",
                mode="lines+markers",
                line=dict(color="#92400E", width=2, dash="dot"),
                marker=dict(size=5),
                yaxis="y2",
                hovertemplate="<b>%{x|%b %Y}</b><br>Rate: %{y:.1f}%<extra></extra>",
            )
        )
        fig_late_trend.update_layout(
            **PL,
            title=dict(text="Monthly Late Count & Rate Trend", font=dict(size=13)),
            barmode="group",
            xaxis=dict(**NGX, tickformat="%b %Y"),
            yaxis=dict(**GY, title="Count"),
            yaxis2=dict(title="Late Rate (%)", overlaying="y", side="right",
                        showgrid=False, ticksuffix="%"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=320,
        )
        st.plotly_chart(fig_late_trend, use_container_width=True)

    # ── Top Employees with Incomplete Logs ────────────────────────────────────
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:.9rem;font-weight:700;margin-bottom:.6rem;">'
        '🟠 Top Employees with Incomplete Logs</div>',
        unsafe_allow_html=True,
    )
    inc_employees = worst_incomplete_logs(df, top_n=10)
    if not inc_employees.empty:
        # construct display table
        show_inc_emp = inc_employees.copy()
        if "first_name" in show_inc_emp.columns and "last_name" in show_inc_emp.columns:
            show_inc_emp["Employee Name"] = show_inc_emp["first_name"] + " " + show_inc_emp["last_name"]
        else:
            show_inc_emp["Employee Name"] = show_inc_emp["employee_id"]

        show_inc_emp.rename(columns={
            "employee_id":     "Employee ID",
            "department_name": "Department",
            "incomplete_days": "Incomplete Logs",
            "total_days":      "Total Days",
            "incomplete_rate": "Incomplete Rate (%)",
        }, inplace=True)

        cols_to_show = [c for c in ["Employee ID", "Employee Name", "Department", "Incomplete Logs", "Total Days", "Incomplete Rate (%)"] if c in show_inc_emp.columns]
        st.dataframe(
            show_inc_emp[cols_to_show],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Incomplete Rate (%)": st.column_config.ProgressColumn(
                    "Incomplete Rate (%)", min_value=0, max_value=100, format="%.1f%%"),
            }
        )
    else:
        st.info("No incomplete log data found for this period.")



# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;padding:1.5rem 0;'
    'font-size:.75rem;color:var(--text-muted);">'
    '🕐 Attendance Analysis · HR Analytics Dashboard &nbsp;·&nbsp; '
    'Data is synthetic for demonstration purposes</div>',
    unsafe_allow_html=True,
)