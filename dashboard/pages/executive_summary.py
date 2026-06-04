"""
HR Analytics Dashboard — Executive Summary
==========================================
File: pages/executive_summary.py

Displays top-level metrics combining data from:
  - employees.csv
  - payroll_transactions.csv
  - performance_logs.csv
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Executive Summary · HR Analytics",
    page_icon="🏢",
    layout="wide",
)

import components.shared as shared

# ── Custom CSS ────────────────────────────────────────────────────────────────
shared.inject_custom_css()

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING — All loaders use @st.cache_data
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Loading employee data…")
def load_employees() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("employees.csv"))
    for col in ["hire_date", "birth_date", "termination_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading payroll data…")
def load_payroll() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("payroll_transactions.csv"))
    for col in ["pay_date", "payment_date", "pay_period", "payroll_period"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading performance data…")
def load_performance() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("performance_logs.csv"))
    for col in ["review_date", "performance_date", "period", "date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading department data…")
def load_departments() -> pd.DataFrame:
    return pd.read_csv(shared.get_data_path("departments.csv"))


@st.cache_data(show_spinner="Loading job data…")
def load_jobs() -> pd.DataFrame:
    return pd.read_csv(shared.get_data_path("jobs.csv"))


# ── Merge & Aggregation helpers (also cached) ─────────────────────────────────

@st.cache_data(show_spinner="Merging & aggregating data…")
def build_master(
    _emp: pd.DataFrame,
    _pay: pd.DataFrame,
    _perf: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join employees + payroll (aggregated per employee) + performance (aggregated per employee).
    Parameters prefixed with '_' so Streamlit skips hashing large DataFrames.
    """
    pay_amount_col = next(
        (c for c in _pay.columns if any(k in c.lower() for k in ["gross", "salary", "total"]) and "id" not in c.lower()),
        None,
    )
    pay_net_col = next(
        (c for c in _pay.columns if "net" in c.lower() and "id" not in c.lower()),
        None,
    )
    if pay_amount_col is None:
        raise KeyError("No salary amount column found in payroll data")

    pay_agg = (
        _pay.groupby("employee_id")
        .agg(
            total_gross=(pay_amount_col, "sum"),
            total_net=(pay_net_col, "sum") if pay_net_col else (pay_amount_col, "sum"),
            avg_gross=(pay_amount_col, "mean"),
            pay_count=(pay_amount_col, "count"),
        )
        .reset_index()
    )

    score_col = next(
        (c for c in _perf.columns if "score" in c.lower() or "rating" in c.lower()),
        _perf.columns[-1],
    )

    perf_agg = (
        _perf.groupby("employee_id")
        .agg(
            avg_score=(score_col, "mean"),
            review_count=(score_col, "count"),
            latest_score=(score_col, "last"),
        )
        .reset_index()
    )

    master = _emp.merge(pay_agg, on="employee_id", how="left")
    master = master.merge(perf_agg, on="employee_id", how="left")
    return master


@st.cache_data(show_spinner=False)
def payroll_trend(_pay: pd.DataFrame) -> pd.DataFrame:
    """Total gross pay aggregated per month."""
    date_col = next(
        (c for c in ["pay_date", "payment_date", "pay_period", "payroll_period", "period", "date"] if c in _pay.columns),
        None,
    )
    if date_col is None:
        return pd.DataFrame()

    pay_amount_col = next(
        (c for c in _pay.columns if any(k in c.lower() for k in ["gross", "salary", "total"]) and "id" not in c.lower()),
        None,
    )
    if pay_amount_col is None:
        return pd.DataFrame()

    df = _pay.copy()
    df["month"] = df[date_col].dt.to_period("M").dt.to_timestamp()
    return (
        df.groupby("month")
        .agg(total_gross=(pay_amount_col, "sum"), headcount=("employee_id", "nunique"))
        .reset_index()
        .sort_values("month")
    )


@st.cache_data(show_spinner=False)
def performance_trend(_perf: pd.DataFrame) -> pd.DataFrame:
    """Average performance score per month."""
    date_col = next(
        (c for c in ["review_date", "performance_date", "period", "date"] if c in _perf.columns),
        None,
    )
    score_col = next(
        (c for c in _perf.columns if "score" in c.lower() or "rating" in c.lower()),
        _perf.columns[-1],
    )
    if date_col is None:
        return pd.DataFrame()

    df = _perf.copy()
    df["month"] = df[date_col].dt.to_period("M").dt.to_timestamp()
    return (
        df.groupby("month")
        .agg(avg_score=(score_col, "mean"), review_count=(score_col, "count"))
        .reset_index()
        .sort_values("month")
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════════

try:
    emp_df  = load_employees()
    pay_df  = load_payroll()
    perf_df = load_performance()
    dept_df = load_departments()
    jobs_df = load_jobs()

    master_df   = build_master(emp_df, pay_df, perf_df)
    pay_trend   = payroll_trend(pay_df)
    perf_trend_ = performance_trend(perf_df)

    data_loaded = True
except FileNotFoundError as e:
    data_loaded = False
    load_error  = str(e)

PLOTLY_LAYOUT = shared.get_plotly_theme()
PALETTE = shared.get_palette()


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Global Filters
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    shared.add_sidebar_header()

    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .5rem;'>Filters</div>",
        unsafe_allow_html=True,
    )

    if data_loaded:
        # Department filter
        dept_options = ["All"]
        if "department_id" in emp_df.columns and "department_name" in dept_df.columns:
            dept_map = dict(zip(dept_df["department_id"], dept_df["department_name"]))
            dept_options += sorted(dept_df["department_name"].dropna().unique().tolist())
        sel_dept = st.selectbox("🏢 Department", dept_options)

        # Employment status filter
        status_col = next(
            (c for c in emp_df.columns if "status" in c.lower() or "employment" in c.lower()),
            None,
        )
        if status_col:
            status_opts = ["All"] + sorted(emp_df[status_col].dropna().unique().tolist())
            sel_status = st.selectbox("👤 Employment Status", status_opts)
        else:
            sel_status = "All"

        # Year filter (based on payroll trend)
        if not pay_trend.empty:
            years = sorted(pay_trend["month"].dt.year.unique(), reverse=True)
            sel_year = st.selectbox("📅 Year", ["All"] + [str(y) for y in years])
        else:
            sel_year = "All"
    else:
        st.warning("Data not available")
        sel_dept = sel_status = sel_year = "All"

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.7rem;color:#64748B;padding:.5rem;line-height:1.5;'>"
        "📄 Synthetic data · Not production data"
        "</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GUARD — Data Unavailable
# ═══════════════════════════════════════════════════════════════════════════════

if not data_loaded:
    st.error(
        f"❌ **File not found**: `{load_error}`\n\n"
        "Make sure the `data/oltp/` folder contains all required CSV files, "
        "then refresh the page."
    )
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# APPLY FILTERS
# ═══════════════════════════════════════════════════════════════════════════════

filtered_master = master_df.copy()
filtered_pay    = pay_df.copy()

# Department filter
if sel_dept != "All" and "department_name" in filtered_master.columns:
    filtered_master = filtered_master[filtered_master["department_name"] == sel_dept]
elif sel_dept != "All" and "department_id" in filtered_master.columns:
    dept_id = dept_df.loc[dept_df["department_name"] == sel_dept, "department_id"]
    if not dept_id.empty:
        filtered_master = filtered_master[filtered_master["department_id"] == dept_id.iloc[0]]

# Status filter
if sel_status != "All" and status_col:
    filtered_master = filtered_master[filtered_master[status_col] == sel_status]

# Filter payroll by already-filtered employee IDs
if sel_dept != "All" or sel_status != "All":
    valid_ids = filtered_master["employee_id"].unique()
    filtered_pay = filtered_pay[filtered_pay["employee_id"].isin(valid_ids)]

# Year filter
if sel_year != "All":
    yr = int(sel_year)
    pay_trend_filtered  = pay_trend[pay_trend["month"].dt.year == yr]   if not pay_trend.empty  else pay_trend
    perf_trend_filtered = perf_trend_[perf_trend_["month"].dt.year == yr] if not perf_trend_.empty else perf_trend_
else:
    pay_trend_filtered  = pay_trend
    perf_trend_filtered = perf_trend_


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE KPIs
# ═══════════════════════════════════════════════════════════════════════════════

total_employees  = len(filtered_master)
active_employees = (
    len(filtered_master[filtered_master[status_col] == "Active"])
    if status_col and "Active" in filtered_master[status_col].values
    else total_employees
)

avg_performance = filtered_master["avg_score"].mean() if "avg_score" in filtered_master.columns else 0.0
pay_value_col = next(
    (c for c in filtered_pay.columns if any(k in c.lower() for k in ["gross", "salary", "total"]) and "id" not in c.lower()),
    None,
)
total_payroll = filtered_pay[pay_value_col].sum() if pay_value_col else 0.0
avg_salary    = filtered_master["avg_gross"].mean() if "avg_gross" in filtered_master.columns else 0.0

# Turnover rate — use employment_status column (Resigned + Terminated)
if status_col:
    resigned_n   = (filtered_master[status_col] == "Resigned").sum()
    terminated_n = (filtered_master[status_col] == "Terminated").sum()
    turnover_count = resigned_n + terminated_n
    turnover_rate  = (turnover_count / total_employees * 100) if total_employees else 0.0
elif "termination_date" in emp_df.columns:
    turnover_count = filtered_master["termination_date"].notna().sum()
    turnover_rate  = (turnover_count / total_employees * 100) if total_employees else 0.0
else:
    turnover_rate = 0.0

# Performance distribution
score_col_master = "avg_score" if "avg_score" in filtered_master.columns else None
high_perf = (filtered_master[score_col_master] >= 4.0).sum() if score_col_master else 0
low_perf  = (filtered_master[score_col_master] < 2.5).sum()  if score_col_master else 0


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div style="margin-bottom: 1.5rem;">
        <div style="display:flex; align-items:center; gap:.75rem; margin-bottom:.25rem;">
            <span style="font-size:1.8rem;">🏢</span>
            <div>
                <h1 style="margin:0; font-size:1.8rem; font-weight:800;
                           background:linear-gradient(135deg,#2563EB,#7C3AED);
                           -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                           background-clip:text; line-height:1.2;">
                    Executive Summary
                </h1>
                <p style="margin:0; font-size:.88rem; color:var(--text-secondary);">
                    Top-level HR metrics · Real-time data from OLTP
                </p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Active filter badges
if any(f != "All" for f in [sel_dept, sel_status, sel_year]):
    badges = []
    if sel_dept   != "All": badges.append(f"🏢 {sel_dept}")
    if sel_status != "All": badges.append(f"👤 {sel_status}")
    if sel_year   != "All": badges.append(f"📅 {sel_year}")

    badge_html = " &nbsp;·&nbsp; ".join(
        f'<span style="background:rgba(37,99,235,.1);color:#2563EB;'
        f'padding:.2rem .6rem;border-radius:20px;font-size:.78rem;font-weight:600;">'
        f'{b}</span>'
        for b in badges
    )
    st.markdown(
        f'<div style="margin-bottom:1.25rem;">'
        f'<span style="font-size:.78rem;color:var(--text-muted);margin-right:.5rem;">Active filters:</span>'
        f'{badge_html}</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# KPI ROW
# ═══════════════════════════════════════════════════════════════════════════════

def fmt_currency(v: float) -> str:
    """Format large numbers as Rp X.X M / B."""
    if v >= 1_000_000_000:
        return f"Rp {v/1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"Rp {v/1_000_000:.1f}M"
    return f"Rp {v:,.0f}"


col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="👥 Total Employees",
        value=f"{total_employees:,}",
        delta=f"{active_employees:,} Active",
        delta_color="normal",
    )

with col2:
    st.metric(
        label="⭐ Avg. Performance",
        value=f"{avg_performance:.2f}" if avg_performance else "N/A",
        delta="out of 5.0 scale",
        delta_color="off",
    )

with col3:
    st.metric(
        label="💰 Total Payroll Spend",
        value=fmt_currency(total_payroll),
        delta=f"Avg {fmt_currency(avg_salary)}/person",
        delta_color="off",
    )

with col4:
    st.metric(
        label="🔄 Turnover Rate",
        value=f"{turnover_rate:.1f}%",
        delta="needs attention" if turnover_rate > 10 else "within normal range",
        delta_color="inverse" if turnover_rate > 10 else "normal",
    )

with col5:
    perf_rate = (high_perf / total_employees * 100) if total_employees else 0.0
    st.metric(
        label="🌟 High Performers",
        value=f"{high_perf:,}",
        delta=f"{perf_rate:.1f}% of total",
        delta_color="normal",
    )

st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VISUALIZATION TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Payroll Trend", "⭐ Performance Trend", "🏢 By Department", "🔍 Distribution"]
)


# ─── TAB 1: Payroll Trend ──────────────────────────────────────────────────────
with tab1:
    st.markdown(
        '<div class="section-header" style="font-size:1rem;font-weight:700;'
        'border-bottom:2px solid #2563EB;display:inline-block;padding-bottom:.3rem;'
        'margin-bottom:1rem;">Monthly Total Payroll Spend</div>',
        unsafe_allow_html=True,
    )

    if pay_trend_filtered.empty:
        st.info("Payroll trend data not available for the selected filters.")
    else:
        fig_pay = make_subplots(specs=[[{"secondary_y": True}]])

        fig_pay.add_trace(
            go.Bar(
                x=pay_trend_filtered["month"],
                y=pay_trend_filtered["total_gross"],
                name="Total Gross Pay",
                marker_color="#2563EB",
                opacity=0.85,
                hovertemplate="<b>%{x|%b %Y}</b><br>Total: Rp %{y:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

        fig_pay.add_trace(
            go.Scatter(
                x=pay_trend_filtered["month"],
                y=pay_trend_filtered["headcount"],
                name="Headcount",
                mode="lines+markers",
                line=dict(color="#059669", width=2.5, dash="dot"),
                marker=dict(size=6),
                hovertemplate="<b>%{x|%b %Y}</b><br>Headcount: %{y:,}<extra></extra>",
            ),
            secondary_y=True,
        )

        fig_pay.update_layout(
            **PLOTLY_LAYOUT,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, tickformat="%b %Y"),
            yaxis=dict(
                title="Total Gross Pay (Rp)",
                gridcolor="rgba(148,163,184,.15)",
                tickformat=",.0f",
            ),
            yaxis2=dict(
                title="Headcount",
                gridcolor="rgba(148,163,184,.0)",
                showgrid=False,
            ),
            height=380,
        )

        st.plotly_chart(fig_pay, use_container_width=True)

        # Summary cards below chart
        c1, c2, c3 = st.columns(3)
        with c1:
            peak_month = pay_trend_filtered.loc[pay_trend_filtered["total_gross"].idxmax(), "month"]
            st.markdown(
                f'<div style="background:var(--bg-card);border:1px solid var(--border-color);'
                f'border-radius:10px;padding:1rem;text-align:center;">'
                f'<div style="font-size:.75rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.06em;color:var(--text-secondary);">Peak Month</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:#2563EB;margin-top:.3rem;">'
                f'{peak_month.strftime("%b %Y")}</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            monthly_avg = pay_trend_filtered["total_gross"].mean()
            st.markdown(
                f'<div style="background:var(--bg-card);border:1px solid var(--border-color);'
                f'border-radius:10px;padding:1rem;text-align:center;">'
                f'<div style="font-size:.75rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.06em;color:var(--text-secondary);">Monthly Average</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:#7C3AED;margin-top:.3rem;">'
                f'{fmt_currency(monthly_avg)}</div></div>',
                unsafe_allow_html=True,
            )
        with c3:
            growth = (
                (pay_trend_filtered["total_gross"].iloc[-1] / pay_trend_filtered["total_gross"].iloc[0] - 1) * 100
                if len(pay_trend_filtered) > 1 else 0.0
            )
            color = "#059669" if growth >= 0 else "#DC2626"
            st.markdown(
                f'<div style="background:var(--bg-card);border:1px solid var(--border-color);'
                f'border-radius:10px;padding:1rem;text-align:center;">'
                f'<div style="font-size:.75rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.06em;color:var(--text-secondary);">Period Growth</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:{color};margin-top:.3rem;">'
                f'{"+" if growth >= 0 else ""}{growth:.1f}%</div></div>',
                unsafe_allow_html=True,
            )


# ─── TAB 2: Performance Trend ──────────────────────────────────────────────────
with tab2:
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;border-bottom:2px solid #7C3AED;'
        'display:inline-block;padding-bottom:.3rem;margin-bottom:1rem;">'
        'Monthly Average Performance Score Trend</div>',
        unsafe_allow_html=True,
    )

    if perf_trend_filtered.empty:
        st.info("Performance trend data not available for the selected filters.")
    else:
        fig_perf = go.Figure()

        fig_perf.add_trace(
            go.Scatter(
                x=perf_trend_filtered["month"],
                y=perf_trend_filtered["avg_score"],
                mode="lines+markers",
                name="Avg Score",
                line=dict(color="#7C3AED", width=3),
                marker=dict(size=7, color="#7C3AED"),
                fill="tozeroy",
                fillcolor="rgba(124,58,237,.08)",
                hovertemplate="<b>%{x|%b %Y}</b><br>Avg Score: %{y:.2f}<extra></extra>",
            )
        )

        fig_perf.add_hline(
            y=3.5,
            line_dash="dash",
            line_color="#D97706",
            line_width=1.5,
            annotation_text="Target 3.5",
            annotation_position="top right",
        )

        fig_perf.update_layout(
            **PLOTLY_LAYOUT,
            xaxis=dict(showgrid=False, tickformat="%b %Y"),
            yaxis=dict(
                title="Average Score",
                gridcolor="rgba(148,163,184,.15)",
                range=[0, 5.5],
            ),
            height=380,
        )

        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.plotly_chart(fig_perf, use_container_width=True)

        with col_right:
            latest_score = perf_trend_filtered["avg_score"].iloc[-1] if len(perf_trend_filtered) else 0.0
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=latest_score,
                    number={"valueformat": ".2f", "font": {"size": 32, "family": "DM Sans"}},
                    gauge={
                        "axis": {"range": [0, 5], "tickfont": {"size": 10}},
                        "bar":  {"color": "#7C3AED", "thickness": .25},
                        "steps": [
                            {"range": [0, 2.5],   "color": "rgba(220,38,38,.15)"},
                            {"range": [2.5, 3.75], "color": "rgba(217,119,6,.15)"},
                            {"range": [3.75, 5],   "color": "rgba(5,150,105,.15)"},
                        ],
                        "threshold": {
                            "line": {"color": "#D97706", "width": 2},
                            "thickness": .75,
                            "value": 3.5,
                        },
                    },
                    title={"text": "Latest Score", "font": {"size": 13, "family": "DM Sans"}},
                )
            )
            fig_gauge.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=20),
                height=220,
                font_family="DM Sans",
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

            best  = perf_trend_filtered["avg_score"].max()
            worst = perf_trend_filtered["avg_score"].min()
            for label, val, color in [
                ("Best", best, "#059669"),
                ("Worst", worst, "#DC2626"),
            ]:
                st.markdown(
                    f'<div style="background:var(--bg-card);border:1px solid var(--border-color);'
                    f'border-radius:8px;padding:.75rem;text-align:center;margin-bottom:.5rem;">'
                    f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.06em;color:var(--text-secondary);">{label}</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:{color};">{val:.2f}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ─── TAB 3: By Department ─────────────────────────────────────────────────────
with tab3:
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;border-bottom:2px solid #059669;'
        'display:inline-block;padding-bottom:.3rem;margin-bottom:1rem;">'
        'Cross-Department Metrics Comparison</div>',
        unsafe_allow_html=True,
    )

    dept_data = filtered_master.copy()
    if "department_name" not in dept_data.columns and "department_id" in dept_data.columns:
        dept_data = dept_data.merge(dept_df, on="department_id", how="left")

    dept_col = "department_name" if "department_name" in dept_data.columns else (
        "department_id" if "department_id" in dept_data.columns else None
    )

    if dept_col is None:
        st.warning("Department column not found in data.")
    else:
        dept_summary = (
            dept_data.groupby(dept_col)
            .agg(
                headcount=(dept_col, "count"),
                avg_perf=("avg_score", "mean") if "avg_score" in dept_data.columns
                         else (dept_col, "count"),
                total_gross=("total_gross", "sum") if "total_gross" in dept_data.columns
                             else (dept_col, "count"),
            )
            .reset_index()
            .sort_values("headcount", ascending=True)
        )

        col_l, col_r = st.columns(2)

        with col_l:
            fig_hc = go.Figure(
                go.Bar(
                    x=dept_summary["headcount"],
                    y=dept_summary[dept_col],
                    orientation="h",
                    marker=dict(
                        color=dept_summary["headcount"],
                        colorscale=[[0, "#DBEAFE"], [1, "#1D4ED8"]],
                        showscale=False,
                    ),
                    text=dept_summary["headcount"],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Headcount: %{x:,}<extra></extra>",
                )
            )
            fig_hc.update_layout(
                **PLOTLY_LAYOUT,
                title=dict(text="Headcount by Department", font=dict(size=13, family="DM Sans")),
                xaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,.15)"),
                yaxis=dict(showgrid=False),
                height=350,
            )
            st.plotly_chart(fig_hc, use_container_width=True)

        with col_r:
            if "avg_perf" in dept_summary.columns:
                fig_sc = px.scatter(
                    dept_summary,
                    x="headcount",
                    y="avg_perf",
                    text=dept_col,
                    size="total_gross" if "total_gross" in dept_summary.columns else "headcount",
                    color="avg_perf",
                    color_continuous_scale="Blues",
                    labels={
                        "headcount": "Employee Count",
                        "avg_perf":  "Avg. Performance",
                        dept_col:    "Department",
                    },
                )
                fig_sc.update_traces(
                    textposition="top center",
                    textfont=dict(size=9, family="DM Sans"),
                    hovertemplate="<b>%{text}</b><br>Headcount: %{x:,}<br>Avg Perf: %{y:.2f}<extra></extra>",
                )
                fig_sc.update_layout(
                    **PLOTLY_LAYOUT,
                    title=dict(text="Headcount vs Avg. Performance", font=dict(size=13)),
                    coloraxis_showscale=False,
                    height=350,
                )
                st.plotly_chart(fig_sc, use_container_width=True)

        # Department summary table
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;">'
            '📋 Department Summary Table</div>',
            unsafe_allow_html=True,
        )

        display_cols = [dept_col, "headcount"]
        rename_map   = {dept_col: "Department", "headcount": "Headcount"}

        if "avg_perf" in dept_summary.columns:
            dept_summary["avg_perf"] = dept_summary["avg_perf"].round(2)
            display_cols.append("avg_perf")
            rename_map["avg_perf"] = "Avg. Performance"

        if "total_gross" in dept_summary.columns:
            dept_summary["total_gross_fmt"] = dept_summary["total_gross"].apply(fmt_currency)
            display_cols.append("total_gross_fmt")
            rename_map["total_gross_fmt"] = "Total Salary"

        st.dataframe(
            dept_summary[display_cols]
            .rename(columns=rename_map)
            .sort_values("Headcount", ascending=False)
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )


# ─── TAB 4: Distribution ──────────────────────────────────────────────────────
with tab4:
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;border-bottom:2px solid #D97706;'
        'display:inline-block;padding-bottom:.3rem;margin-bottom:1rem;">'
        'Employee Performance & Payroll Distributions</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        if score_col_master and score_col_master in filtered_master.columns:
            perf_data = filtered_master[score_col_master].dropna()
            fig_hist = go.Figure(
                go.Histogram(
                    x=perf_data,
                    nbinsx=30,
                    marker_color="#7C3AED",
                    opacity=0.8,
                    hovertemplate="Score: %{x:.1f}<br>Count: %{y:,}<extra></extra>",
                )
            )
            mean_val = perf_data.mean()
            fig_hist.add_vline(
                x=mean_val,
                line_color="#D97706",
                line_width=2,
                line_dash="dash",
                annotation_text=f"Mean: {mean_val:.2f}",
                annotation_position="top",
            )
            fig_hist.update_layout(
                **PLOTLY_LAYOUT,
                title=dict(text="Employee Performance Score Distribution", font=dict(size=13)),
                xaxis=dict(title="Performance Score", showgrid=False),
                yaxis=dict(title="Employee Count", gridcolor="rgba(148,163,184,.15)"),
                height=340,
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("Performance score column not available.")

    with c2:
        if "avg_gross" in filtered_master.columns:
            sal_data = filtered_master["avg_gross"].dropna()
            fig_sal = go.Figure(
                go.Histogram(
                    x=sal_data,
                    nbinsx=30,
                    marker_color="#2563EB",
                    opacity=0.8,
                    hovertemplate="Salary: Rp %{x:,.0f}<br>Count: %{y:,}<extra></extra>",
                )
            )
            mean_sal = sal_data.mean()
            fig_sal.add_vline(
                x=mean_sal,
                line_color="#059669",
                line_width=2,
                line_dash="dash",
                annotation_text=f"Mean: {fmt_currency(mean_sal)}",
                annotation_position="top",
            )
            fig_sal.update_layout(
                **PLOTLY_LAYOUT,
                title=dict(text="Average Salary Distribution per Employee", font=dict(size=13)),
                xaxis=dict(title="Average Salary (Rp)", showgrid=False, tickformat=",.0f"),
                yaxis=dict(title="Employee Count", gridcolor="rgba(148,163,184,.15)"),
                height=340,
            )
            st.plotly_chart(fig_sal, use_container_width=True)
        else:
            st.info("Average salary column not available.")

    # Box plot: performance by department
    st.markdown("<br>", unsafe_allow_html=True)
    if score_col_master and dept_col and dept_col in filtered_master.columns:
        box_data = filtered_master[[dept_col, score_col_master]].dropna()
        fig_box = px.box(
            box_data,
            x=dept_col,
            y=score_col_master,
            color=dept_col,
            points="outliers",
            labels={dept_col: "Department", score_col_master: "Performance Score"},
            color_discrete_sequence=PALETTE,
        )
        fig_box.update_layout(
            **PLOTLY_LAYOUT,
            title=dict(text="Performance Score Box Plot by Department", font=dict(size=13)),
            xaxis=dict(showgrid=False, tickangle=-30),
            yaxis=dict(gridcolor="rgba(148,163,184,.15)"),
            showlegend=False,
            height=360,
        )
        st.plotly_chart(fig_box, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;padding:1.5rem 0;'
    'font-size:.75rem;color:var(--text-muted);">'
    '🏢 Executive Summary · HR Analytics Dashboard &nbsp;·&nbsp; '
    'Synthetic data for demonstration purposes</div>',
    unsafe_allow_html=True,
)