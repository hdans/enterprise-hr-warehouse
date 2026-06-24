"""
HR Analytics Dashboard — Workforce Analysis
============================================
File: pages/workforce_analysis.py

Employee demography analysis by merging data from:
  - employees.csv
  - departments.csv
  - jobs.csv
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date

# Page Configuration
st.set_page_config(
    page_title="Workforce Analysis · HR Analytics",
    page_icon=":material/groups:",
    layout="wide",
)

import components.shared as shared

# Custom CSS
shared.inject_custom_css()

# Plotly Theme
PLOTLY_BASE = shared.get_plotly_theme()
GRID_X = dict(showgrid=True, gridcolor="rgba(148,163,184,.15)", zeroline=False)
GRID_Y = dict(showgrid=True, gridcolor="rgba(148,163,184,.15)", zeroline=False)
NO_GRID = dict(showgrid=False, zeroline=False)

PALETTE_GENDER  = ["#7C3AED", "#EC4899", "#06B6D4"]
PALETTE_DEPT    = px.colors.qualitative.Bold
PALETTE_AGE     = ["#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8", "#1E3A8A"]
PALETTE_STATUS  = {"Active": "#059669", "Inactive": "#DC2626", "On Leave": "#D97706"}


# DATA LOADING

@st.cache_data(show_spinner="Loading employee data...")
def load_employees() -> pd.DataFrame:
    df = shared.load_supabase_table("dim_employee")
    for col in ["hire_date", "birth_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


@st.cache_data(show_spinner="Loading department data...")
def load_departments() -> pd.DataFrame:
    return shared.load_supabase_table("dim_department")


@st.cache_data(show_spinner="Loading job title data...")
def load_jobs() -> pd.DataFrame:
    return shared.load_supabase_table("dim_job")


@st.cache_data(show_spinner="Merging & enriching data...")
def build_workforce(_emp: pd.DataFrame, _dept: pd.DataFrame, _jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Merge employees ← departments ← jobs using pd.merge.
    Prefix '_' prevents Streamlit from hashing large DataFrames.
    """
    df = _emp.copy()

    # Merge with departments
    if "department_id" in df.columns and "department_id" in _dept.columns:
        df = df.merge(_dept, on="department_id", how="left", suffixes=("", "_dept"))

    # Merge with jobs
    job_key = next(
        (k for k in ["job_id", "position_id", "role_id"] if k in df.columns and k in _jobs.columns),
        None,
    )
    if job_key:
        df = df.merge(_jobs, on=job_key, how="left", suffixes=("", "_job"))

    # Derived Columns

    # Age
    today = pd.Timestamp(date.today())
    if "birth_date" in df.columns:
        df["age"] = ((today - df["birth_date"]).dt.days / 365.25).round(1)
        df["age_group"] = pd.cut(
            df["age"],
            bins=[0, 25, 30, 35, 40, 45, 50, 55, 200],
            labels=["< 25", "25–29", "30–34", "35–39", "40–44", "45–49", "50–54", "55+"],
            right=False,
        )

    # Tenure years
    if "hire_date" in df.columns:
        df["tenure_years"] = ((today - df["hire_date"]).dt.days / 365.25).round(1)
        df["tenure_group"] = pd.cut(
            df["tenure_years"],
            bins=[0, 1, 3, 5, 10, 15, 200],
            labels=["< 1 yr", "1–2 yrs", "3–4 yrs", "5–9 yrs", "10–14 yrs", "15+ yrs"],
            right=False,
        )

    # Normalize gender column
    gender_col = next(
        (c for c in df.columns if "gender" in c.lower() or "sex" in c.lower()), None
    )
    if gender_col and gender_col != "gender":
        df["gender"] = df[gender_col]
    elif gender_col:
        df["gender"] = df[gender_col]

    # Normalize status column
    status_col = next(
        (c for c in df.columns if c.lower() in ["status", "employment_status", "emp_status"]),
        None,
    )
    if status_col and status_col != "status":
        df["status"] = df[status_col]

    return df


# LOAD DATA

try:
    emp_raw  = load_employees()
    dept_raw = load_departments()
    jobs_raw = load_jobs()
    wf       = build_workforce(emp_raw, dept_raw, jobs_raw)
    data_ok  = True
except Exception as e:
    data_ok    = False
    load_error = e


# DETECT DYNAMIC COLUMNS

if data_ok:
    DEPT_COL     = next((c for c in ["department_name", "dept_name", "department_id"] if c in wf.columns), None)
    JOB_COL      = next((c for c in ["job_title", "position_title", "role_name", "title", "job_name"] if c in wf.columns), None)
    GENDER_COL   = next((c for c in ["gender", "sex"] if c in wf.columns), None)
    STATUS_COL   = next((c for c in ["status", "employment_status", "emp_status"] if c in wf.columns), None)
    EDUC_COL     = next((c for c in wf.columns if "educ" in c.lower() or "degree" in c.lower()), None)
    MARITAL_COL  = next((c for c in wf.columns if "marital" in c.lower() or "married" in c.lower()), None)
    HAS_AGE      = "age" in wf.columns
    HAS_TENURE   = "tenure_years" in wf.columns


# SIDEBAR — Filters

with st.sidebar:
    shared.add_sidebar_header()

    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .5rem;'>Filters</div>",
        unsafe_allow_html=True,
    )

    if data_ok:
        # Department Filter
        dept_opts = ["All"]
        if DEPT_COL:
            dept_opts += sorted(wf[DEPT_COL].dropna().unique().tolist())
        sel_dept = st.selectbox("Department", dept_opts)

        # Gender Filter
        gender_opts = ["All"]
        if GENDER_COL:
            gender_opts += sorted(wf[GENDER_COL].dropna().unique().tolist())
        sel_gender = st.selectbox("Gender", gender_opts)

        # Status Filter
        status_opts = ["All"]
        if STATUS_COL:
            status_opts += sorted(wf[STATUS_COL].dropna().unique().tolist())
        sel_status = st.selectbox("Status", status_opts)

        # Hire Year Filter
        hire_years = ["All"]
        if "hire_date" in wf.columns:
            years = sorted(wf["hire_date"].dt.year.dropna().unique().astype(int), reverse=True)
            hire_years += [str(y) for y in years]
        sel_year = st.selectbox("Hire Year", hire_years)

        st.markdown("---")

        # Display Options
        st.markdown(
            "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
            "text-transform:uppercase;color:#64748B;padding:0 .5rem .5rem;'>Display Options</div>",
            unsafe_allow_html=True,
        )
        show_table = st.toggle("Show detailed table", value=False)
        top_n_dept = st.slider("Top N Departments", min_value=3, max_value=len(dept_opts) - 1 if len(dept_opts) > 2 else 8, value=8)

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.7rem;color:#64748B;padding:.5rem;line-height:1.5;'>"
        f"{shared.icon_label('database', 'Synthetic data · Not production data', color='#94A3B8', size=14)}</div>",
        unsafe_allow_html=True,
    )


# GUARD

if not data_ok:
    shared.render_data_load_error(load_error)
    st.stop()


# APPLY FILTERS

df = wf.copy()

if sel_dept   != "All" and DEPT_COL:
    df = df[df[DEPT_COL] == sel_dept]
if sel_gender != "All" and GENDER_COL:
    df = df[df[GENDER_COL] == sel_gender]
if sel_status != "All" and STATUS_COL:
    df = df[df[STATUS_COL] == sel_status]
if sel_year   != "All" and "hire_date" in df.columns:
    df = df[df["hire_date"].dt.year == int(sel_year)]


# COMPUTE KPI

total_emp     = len(df)
active_emp    = (df[STATUS_COL] == "Active").sum() if STATUS_COL and "Active" in df[STATUS_COL].values else total_emp
avg_age       = df["age"].mean() if HAS_AGE else None
avg_tenure    = df["tenure_years"].mean() if HAS_TENURE else None
num_depts     = df[DEPT_COL].nunique() if DEPT_COL else None
num_jobs      = df[JOB_COL].nunique()  if JOB_COL  else None

# Gender ratio
gender_ratio_str = "N/A"
if GENDER_COL:
    gc = df[GENDER_COL].value_counts()
    if len(gc) >= 2:
        vals = gc.values[:2]
        gender_ratio_str = f"{vals[0]:,} : {vals[1]:,}"

# New hires in last 12 months — anchor to max hire_date in data, not today
new_hires = 0
if "hire_date" in df.columns:
    max_hire = df["hire_date"].max()
    cutoff   = max_hire - pd.DateOffset(months=12)
    new_hires = (df["hire_date"] >= cutoff).sum()


# PAGE HEADER

st.markdown(
    f"""
    <div style="margin-bottom:1.5rem;">
        <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.25rem;">
            <span style="display:inline-flex;color:#7C3AED;">{shared.icon_svg("users", size=30, color="#7C3AED")}</span>
            <div>
                <h1 style="margin:0;font-size:1.8rem;font-weight:800;
                           background:linear-gradient(135deg,#7C3AED,#2563EB);
                           -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                           background-clip:text;line-height:1.2;">
                    Workforce Analysis
                </h1>
                <p style="margin:0;font-size:.88rem;color:var(--text-secondary);">
                    Demographics, distribution, and overall employee composition
                </p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Filter badges
active_filters = {
    "building": sel_dept,
    "users": sel_gender,
    "check": sel_status,
    "calendar": sel_year,
}
badges = [shared.icon_label(icon, val, color="#7C3AED", size=14) for icon, val in active_filters.items() if val != "All"]
if badges:
    badge_html = " &nbsp; · &nbsp; ".join(
        f'<span style="background:rgba(124,58,237,.1);color:#7C3AED;'
        f'padding:.2rem .6rem;border-radius:20px;font-size:.78rem;font-weight:600;">{b}</span>'
        for b in badges
    )
    st.markdown(
        f'<div style="margin-bottom:1.25rem;">'
        f'<span style="font-size:.78rem;color:var(--text-muted);margin-right:.5rem;">Active filters:</span>'
        f'{badge_html}</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr>', unsafe_allow_html=True)


# KPI ROW

kpi_cols = st.columns(6)

kpi_data = [
    ("Total Employees",    f"{total_emp:,}",                       f"{active_emp:,} active"),
    ("Departments",        str(num_depts) if num_depts else "N/A",  "active business units"),
    ("Job Titles",         str(num_jobs)  if num_jobs  else "N/A",  "distinct positions"),
    ("Average Age",        f"{avg_age:.1f} yrs" if avg_age else "N/A",    "years"),
    ("Average Tenure",     f"{avg_tenure:.1f} yrs" if avg_tenure else "N/A", "tenure length"),
    ("New Hires (12 mo)",  f"{new_hires:,}",                        "new employee(s)"),
]

for col, (label, value, delta) in zip(kpi_cols, kpi_data):
    with col:
        st.metric(label=label, value=value, delta=delta, delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)


# TABS

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Gender",
    "Age Group",
    "Department",
    "Job & Tenure",
    "Recruitment Trend",
])


# TAB 1 · GENDER
with tab1:
    if not GENDER_COL:
        st.info("Gender column not found in data.")
    else:
        gender_counts = df[GENDER_COL].value_counts().reset_index()
        gender_counts.columns = ["gender", "count"]
        gender_counts["pct"] = (gender_counts["count"] / gender_counts["count"].sum() * 100).round(1)

        col_donut, col_bar, col_detail = st.columns([1.2, 1.8, 1])

        # Donut Chart
        with col_donut:
            fig_donut = go.Figure(
                go.Pie(
                    labels=gender_counts["gender"],
                    values=gender_counts["count"],
                    hole=0.62,
                    marker_colors=PALETTE_GENDER,
                    textinfo="label+percent",
                    textfont=dict(size=12, family="DM Sans"),
                    hovertemplate="<b>%{label}</b><br>Headcount: %{value:,}<br>Proportion: %{percent}<extra></extra>",
                    pull=[0.03] * len(gender_counts),
                )
            )
            # Center annotation
            fig_donut.add_annotation(
                text=f"<b>{total_emp:,}</b><br><span style='font-size:11px'>Total</span>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, family="DM Sans"),
                xanchor="center", yanchor="middle",
            )
            fig_donut.update_layout(
                **{**PLOTLY_BASE, "margin": dict(l=0, r=0, t=36, b=30)},
                title=dict(text="Gender Distribution", font=dict(size=13)),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15),
                height=320,
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        # Gender per Department
        with col_bar:
            if DEPT_COL:
                gdept = (
                    df.groupby([DEPT_COL, GENDER_COL])
                    .size()
                    .reset_index(name="count")
                )
                # Get top N departments based on headcount
                top_depts = (
                    gdept.groupby(DEPT_COL)["count"].sum()
                    .nlargest(top_n_dept)
                    .index
                )
                gdept = gdept[gdept[DEPT_COL].isin(top_depts)]

                fig_gdept = px.bar(
                    gdept,
                    x="count",
                    y=DEPT_COL,
                    color=GENDER_COL,
                    orientation="h",
                    barmode="stack",
                    color_discrete_sequence=PALETTE_GENDER,
                    labels={"count": "Employee Count", DEPT_COL: "Department"},
                    text="count",
                )
                fig_gdept.update_traces(
                    textposition="inside",
                    textfont=dict(size=10),
                    hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x:,}<extra></extra>",
                )
                fig_gdept.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text=f"Gender by Department (Top {top_n_dept})", font=dict(size=13)),
                    xaxis=dict(**GRID_X, title="Count"),
                    yaxis=dict(**NO_GRID, title="", categoryorder="total ascending"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                    height=340,
                )
                st.plotly_chart(fig_gdept, use_container_width=True)
            else:
                st.info("Department column not found.")

        # Gender Stats Cards
        with col_detail:
            st.markdown(
                '<div style="font-size:.85rem;font-weight:700;margin-bottom:.75rem;">'
                'Gender Statistics</div>',
                unsafe_allow_html=True,
            )
            for _, row in gender_counts.iterrows():
                color = PALETTE_GENDER[_ % len(PALETTE_GENDER)]
                avg_t = (
                    df[df[GENDER_COL] == row["gender"]]["tenure_years"].mean()
                    if HAS_TENURE else None
                )
                avg_a = (
                    df[df[GENDER_COL] == row["gender"]]["age"].mean()
                    if HAS_AGE else None
                )
                st.markdown(
                    f'<div style="background:var(--bg-card);border:1px solid var(--border-color);'
                    f'border-left:4px solid {color};border-radius:10px;'
                    f'padding:.9rem 1rem;margin-bottom:.6rem;">'
                    f'<div style="font-weight:700;font-size:.95rem;">{row["gender"]}</div>'
                    f'<div style="font-size:1.6rem;font-weight:800;color:{color};">'
                    f'{row["count"]:,} <span style="font-size:.75rem;font-weight:500;'
                    f'color:var(--text-secondary);">({row["pct"]}%)</span></div>'
                    + (f'<div style="font-size:.78rem;color:var(--text-secondary);margin-top:.3rem;">'
                       f'Avg Age: {avg_a:.1f} yrs · Tenure: {avg_t:.1f} yrs</div>'
                       if avg_a and avg_t else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )

        # Gender × Status
        if STATUS_COL:
            st.markdown("<br>", unsafe_allow_html=True)
            gs = (
                df.groupby([GENDER_COL, STATUS_COL])
                .size()
                .reset_index(name="count")
            )
            fig_gs = px.bar(
                gs,
                x=GENDER_COL,
                y="count",
                color=STATUS_COL,
                barmode="group",
                color_discrete_map=PALETTE_STATUS,
                labels={"count": "Headcount", GENDER_COL: "Gender"},
                text="count",
            )
            fig_gs.update_traces(textposition="outside", textfont=dict(size=11))
            fig_gs.update_layout(
                **PLOTLY_BASE,
                title=dict(text="Gender × Employment Status", font=dict(size=13)),
                xaxis=dict(**NO_GRID),
                yaxis=dict(**GRID_Y, title="Headcount"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                height=280,
            )
            st.plotly_chart(fig_gs, use_container_width=True)


# TAB 2 · AGE GROUP
with tab2:
    if not HAS_AGE:
        st.info("Column `birth_date` not found. Cannot compute age.")
    else:
        col_pyr, col_line = st.columns([1.4, 1.6])

        # Population Pyramid (Gender × Age Group)
        with col_pyr:
            if GENDER_COL and "age_group" in df.columns:
                pyramid_data = (
                    df.groupby(["age_group", GENDER_COL])
                    .size()
                    .reset_index(name="count")
                )
                genders = pyramid_data[GENDER_COL].unique()

                fig_pyr = go.Figure()
                colors = PALETTE_GENDER

                for i, gender in enumerate(genders):
                    sub = pyramid_data[pyramid_data[GENDER_COL] == gender]
                    # Left (negative) for first gender, right for others
                    multiplier = -1 if i == 0 else 1
                    fig_pyr.add_trace(
                        go.Bar(
                            y=sub["age_group"].astype(str),
                            x=sub["count"] * multiplier,
                            name=gender,
                            orientation="h",
                            marker_color=colors[i % len(colors)],
                            hovertemplate=f"<b>{gender}</b><br>Age Group: %{{y}}<br>Headcount: %{{customdata:,}}<extra></extra>",
                            customdata=sub["count"],
                        )
                    )

                max_val = pyramid_data["count"].max()
                tick_vals = list(range(-int(max_val * 1.1), int(max_val * 1.1) + 1, max(1, int(max_val // 4))))
                tick_text = [str(abs(v)) for v in tick_vals]

                fig_pyr.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text="Population Pyramid (Gender × Age Group)", font=dict(size=13)),
                    barmode="relative",
                    xaxis=dict(
                        tickvals=tick_vals, ticktext=tick_text,
                        showgrid=True, gridcolor="rgba(148,163,184,.15)", zeroline=True,
                        zerolinecolor="rgba(148,163,184,.5)", zerolinewidth=1.5,
                        title="Employee Count",
                    ),
                    yaxis=dict(**NO_GRID, title=""),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                    height=400,
                )
                st.plotly_chart(fig_pyr, use_container_width=True)
            else:
                # Fallback: simple bar if gender not present
                age_cnt = df["age_group"].value_counts().sort_index().reset_index()
                age_cnt.columns = ["age_group", "count"]
                fig_age_bar = px.bar(
                    age_cnt, x="age_group", y="count",
                    color="count",
                    color_continuous_scale="Blues",
                    labels={"age_group": "Age Group", "count": "Headcount"},
                    text="count",
                )
                fig_age_bar.update_traces(textposition="outside")
                fig_age_bar.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text="Age Group Distribution", font=dict(size=13)),
                    xaxis=dict(**NO_GRID), yaxis=dict(**GRID_Y),
                    coloraxis_showscale=False, height=360,
                )
                st.plotly_chart(fig_age_bar, use_container_width=True)

        # Box Plot Age per Department
        with col_line:
            if DEPT_COL:
                top_d = (
                    df[DEPT_COL].value_counts()
                    .nlargest(top_n_dept)
                    .index
                )
                box_df = df[df[DEPT_COL].isin(top_d)]

                fig_box = px.violin(
                    box_df,
                    y="age",
                    x=DEPT_COL,
                    color=DEPT_COL,
                    box=True,
                    points=False,
                    color_discrete_sequence=PALETTE_DEPT,
                    labels={"age": "Age (years)", DEPT_COL: "Department"},
                )
                fig_box.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text=f"Age Distribution by Department (Top {top_n_dept})", font=dict(size=13)),
                    xaxis=dict(**NO_GRID, tickangle=-25, title=""),
                    yaxis=dict(**GRID_Y, title="Age (yrs)"),
                    showlegend=False,
                    height=400,
                )
                st.plotly_chart(fig_box, use_container_width=True)
            else:
                # Age Histogram
                fig_hist_age = px.histogram(
                    df, x="age", nbins=30,
                    color_discrete_sequence=["#7C3AED"],
                    labels={"age": "Age"},
                )
                fig_hist_age.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text="Employee Age Histogram", font=dict(size=13)),
                    xaxis=dict(**NO_GRID), yaxis=dict(**GRID_Y),
                    height=380,
                )
                st.plotly_chart(fig_hist_age, use_container_width=True)

        # Age Group Stats Table
        st.markdown("<br>", unsafe_allow_html=True)
        age_stats = (
            df.groupby("age_group", observed=True)
            .agg(
                jumlah=("age", "count"),
                usia_min=("age", "min"),
                usia_max=("age", "max"),
                usia_rata=("age", "mean"),
            )
            .reset_index()
        )
        age_stats["proporsi"] = (age_stats["jumlah"] / age_stats["jumlah"].sum() * 100).round(1)
        age_stats["usia_rata"] = age_stats["usia_rata"].round(1)
        age_stats.columns = ["Age Group", "Headcount", "Min Age", "Max Age", "Average", "Proportion (%)"]

        st.markdown(
            '<div style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;">'
            f'{shared.icon_label("table", "Age Group Summary", color="#7C3AED", size=16)}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            age_stats.reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Proportion (%)": st.column_config.ProgressColumn(
                    "Proportion (%)", min_value=0, max_value=100, format="%.1f%%"
                ),
                "Headcount": st.column_config.NumberColumn("Headcount", format="%d"),
            },
        )


# TAB 3 · DEPARTMENT
with tab3:
    if not DEPT_COL:
        st.info("Department column not found in data.")
    else:
        dept_summary = (
            df.groupby(DEPT_COL)
            .agg(
                headcount=(DEPT_COL, "count"),
                avg_age=("age", "mean") if HAS_AGE else (DEPT_COL, "count"),
                avg_tenure=("tenure_years", "mean") if HAS_TENURE else (DEPT_COL, "count"),
            )
            .reset_index()
        )
        if HAS_AGE:
            dept_summary["avg_age"] = dept_summary["avg_age"].round(1)
        if HAS_TENURE:
            dept_summary["avg_tenure"] = dept_summary["avg_tenure"].round(1)

        dept_top = dept_summary.nlargest(top_n_dept, "headcount")

        col_bar, col_treemap = st.columns([1.6, 1.4])

        # Horizontal Bar Headcount
        with col_bar:
            dept_sorted = dept_top.sort_values("headcount", ascending=True)
            fig_dept_bar = go.Figure(
                go.Bar(
                    y=dept_sorted[DEPT_COL],
                    x=dept_sorted["headcount"],
                    orientation="h",
                    marker=dict(
                        color=dept_sorted["headcount"],
                        colorscale=[[0, "#C4B5FD"], [1, "#5B21B6"]],
                        showscale=False,
                    ),
                    text=dept_sorted["headcount"].apply(lambda v: f"{v:,}"),
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Headcount: %{x:,}<extra></extra>",
                )
            )
            fig_dept_bar.update_layout(
                **PLOTLY_BASE,
                title=dict(text=f"Headcount by Department (Top {top_n_dept})", font=dict(size=13)),
                xaxis=dict(**GRID_X, title="Employee Count"),
                yaxis=dict(**NO_GRID, title=""),
                height=380,
            )
            st.plotly_chart(fig_dept_bar, use_container_width=True)

        # Treemap
        with col_treemap:
            fig_tree = px.treemap(
                dept_summary,
                path=[DEPT_COL],
                values="headcount",
                color="headcount",
                color_continuous_scale="Purples",
                custom_data=[dept_summary["headcount"]],
            )
            fig_tree.update_traces(
                texttemplate="<b>%{label}</b><br>%{value:,}",
                hovertemplate="<b>%{label}</b><br>Headcount: %{value:,}<extra></extra>",
                textfont=dict(family="DM Sans", size=12),
            )
            fig_tree.update_layout(
                **{**PLOTLY_BASE, "margin": dict(l=0, r=0, t=36, b=0)},
                title=dict(text="Headcount Proportion (Treemap)", font=dict(size=13)),
                coloraxis_showscale=False,
                height=380,
            )
            st.plotly_chart(fig_tree, use_container_width=True)

        # Scatter: Headcount vs Avg Age / Tenure
        st.markdown("<br>", unsafe_allow_html=True)
        col_sc1, col_sc2 = st.columns(2)

        if HAS_AGE:
            with col_sc1:
                fig_sc_age = px.scatter(
                    dept_summary,
                    x="headcount",
                    y="avg_age",
                    text=DEPT_COL,
                    size="headcount",
                    color="avg_age",
                    color_continuous_scale="Purples",
                    labels={"headcount": "Headcount", "avg_age": "Average Age"},
                )
                fig_sc_age.update_traces(
                    textposition="top center",
                    textfont=dict(size=9),
                    hovertemplate="<b>%{text}</b><br>Headcount: %{x:,}<br>Avg Age: %{y:.1f} yrs<extra></extra>",
                )
                fig_sc_age.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text="Headcount vs Average Age by Dept.", font=dict(size=13)),
                    xaxis=dict(**GRID_X, title="Headcount"),
                    yaxis=dict(**GRID_Y, title="Average Age"),
                    coloraxis_showscale=False,
                    height=340,
                )
                st.plotly_chart(fig_sc_age, use_container_width=True)

        if HAS_TENURE:
            with col_sc2:
                fig_sc_ten = px.scatter(
                    dept_summary,
                    x="headcount",
                    y="avg_tenure",
                    text=DEPT_COL,
                    size="headcount",
                    color="avg_tenure",
                    color_continuous_scale="Blues",
                    labels={"headcount": "Headcount", "avg_tenure": "Average Tenure"},
                )
                fig_sc_ten.update_traces(
                    textposition="top center",
                    textfont=dict(size=9),
                    hovertemplate="<b>%{text}</b><br>Headcount: %{x:,}<br>Tenure: %{y:.1f} yrs<extra></extra>",
                )
                fig_sc_ten.update_layout(
                    **PLOTLY_BASE,
                    title=dict(text="Headcount vs Average Tenure by Dept.", font=dict(size=13)),
                    xaxis=dict(**GRID_X, title="Headcount"),
                    yaxis=dict(**GRID_Y, title="Average Tenure (yrs)"),
                    coloraxis_showscale=False,
                    height=340,
                )
                st.plotly_chart(fig_sc_ten, use_container_width=True)

        # Detail Table
        st.markdown(
            '<div style="font-size:.85rem;font-weight:600;margin:.5rem 0;">'
            f'{shared.icon_label("table", "Department Detail Table", color="#7C3AED", size=16)}</div>',
            unsafe_allow_html=True,
        )
        display_cols  = [DEPT_COL, "headcount"]
        rename_map_d  = {DEPT_COL: "Department", "headcount": "Headcount"}
        col_cfg       = {"Headcount": st.column_config.NumberColumn("Headcount", format="%d")}

        if HAS_AGE:
            display_cols.append("avg_age")
            rename_map_d["avg_age"] = "Avg. Age (yrs)"
        if HAS_TENURE:
            display_cols.append("avg_tenure")
            rename_map_d["avg_tenure"] = "Avg. Tenure (yrs)"

        dept_summary["pct"] = (dept_summary["headcount"] / dept_summary["headcount"].sum() * 100).round(1)
        display_cols.append("pct")
        rename_map_d["pct"] = "Proportion (%)"
        col_cfg["Proportion (%)"] = st.column_config.ProgressColumn(
            "Proportion (%)", min_value=0, max_value=100, format="%.1f%%"
        )

        st.dataframe(
            dept_summary[display_cols]
            .rename(columns=rename_map_d)
            .sort_values("Headcount", ascending=False)
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
            column_config=col_cfg,
        )


# TAB 4 · JOB & TENURE
with tab4:
    col_job, col_ten = st.columns(2)

    # Top Job Titles
    with col_job:
        if not JOB_COL:
            st.info("Job title column not found in data.")
        else:
            job_counts = (
                df[JOB_COL].value_counts()
                .nlargest(15)
                .reset_index()
            )
            job_counts.columns = ["job", "count"]
            job_counts["pct"] = (job_counts["count"] / job_counts["count"].sum() * 100).round(1)

            fig_job = go.Figure(
                go.Bar(
                    y=job_counts["job"],
                    x=job_counts["count"],
                    orientation="h",
                    marker=dict(
                        color=job_counts["count"],
                        colorscale=[[0, "#BFDBFE"], [1, "#1D4ED8"]],
                        showscale=False,
                    ),
                    text=job_counts["count"].apply(lambda v: f"{v:,}"),
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Headcount: %{x:,}<extra></extra>",
                )
            )
            fig_job.update_layout(
                **PLOTLY_BASE,
                title=dict(text="Top 15 Job Titles", font=dict(size=13)),
                xaxis=dict(**GRID_X, title="Headcount"),
                yaxis=dict(**NO_GRID, title="", autorange="reversed", tickfont=dict(size=11)),
                height=460,
            )
            st.plotly_chart(fig_job, use_container_width=True)

    # Tenure Distribution
    with col_ten:
        if not HAS_TENURE:
            st.info("Column `hire_date` not found. Cannot compute tenure.")
        else:
            ten_grp = (
                df["tenure_group"]
                .value_counts()
                .reindex(["< 1 yr", "1–2 yrs", "3–4 yrs", "5–9 yrs", "10–14 yrs", "15+ yrs"])
                .fillna(0)
                .reset_index()
            )
            ten_grp.columns = ["tenure_group", "count"]
            ten_grp["pct"]  = (ten_grp["count"] / ten_grp["count"].sum() * 100).round(1)

            fig_ten = go.Figure()
            fig_ten.add_trace(
                go.Bar(
                    x=ten_grp["tenure_group"],
                    y=ten_grp["count"],
                    marker_color=PALETTE_AGE * 2,
                    text=ten_grp.apply(lambda r: f"{int(r['count']):,}\n({r['pct']}%)", axis=1),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Headcount: %{y:,}<extra></extra>",
                )
            )
            fig_ten.update_layout(
                **PLOTLY_BASE,
                title=dict(text="Tenure Distribution", font=dict(size=13)),
                xaxis=dict(**NO_GRID, title="Tenure Group"),
                yaxis=dict(**GRID_Y, title="Employee Count"),
                height=320,
            )
            st.plotly_chart(fig_ten, use_container_width=True)

            # Average Tenure Gauge
            avg_t = df["tenure_years"].mean()
            fig_g = go.Figure(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=round(avg_t, 1),
                    number={"suffix": " yrs", "font": {"size": 28, "family": "DM Sans"}},
                    delta={"reference": 5, "valueformat": ".1f"},
                    gauge={
                        "axis":  {"range": [0, 20], "tickfont": {"size": 10}},
                        "bar":   {"color": "#7C3AED", "thickness": .2},
                        "steps": [
                            {"range": [0, 3],  "color": "rgba(220,38,38,.12)"},
                            {"range": [3, 7],  "color": "rgba(217,119,6,.12)"},
                            {"range": [7, 20], "color": "rgba(5,150,105,.12)"},
                        ],
                        "threshold": {"line": {"color": "#D97706", "width": 2}, "thickness": .75, "value": 5},
                    },
                    title={"text": "Average Tenure", "font": {"size": 12, "family": "DM Sans"}},
                )
            )
            fig_g.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=40, b=10),
                height=180,
                font_family="DM Sans",
            )
            st.plotly_chart(fig_g, use_container_width=True)

    # Tenure per Department (Heatmap)
    if HAS_TENURE and DEPT_COL:
        st.markdown("<br>", unsafe_allow_html=True)
        ten_dept = (
            df.groupby([DEPT_COL, "tenure_group"], observed=True)
            .size()
            .unstack(fill_value=0)
        )
        # Sort columns to standard categories order
        col_order = [c for c in ["< 1 yr", "1–2 yrs", "3–4 yrs", "5–9 yrs", "10–14 yrs", "15+ yrs"]
                     if c in ten_dept.columns]
        ten_dept  = ten_dept[col_order]

        fig_heat = px.imshow(
            ten_dept,
            color_continuous_scale="Purples",
            aspect="auto",
            text_auto=True,
            labels=dict(x="Tenure Group", y="Department", color="Headcount"),
        )
        fig_heat.update_traces(
            textfont=dict(size=11, family="DM Sans"),
            hovertemplate="<b>%{y}</b><br>Tenure: %{x}<br>Headcount: %{z:,}<extra></extra>",
        )
        fig_heat.update_layout(
            **{**PLOTLY_BASE, "margin": dict(l=0, r=60, t=36, b=0)},
            title=dict(text="Tenure Distribution by Department Heatmap", font=dict(size=13)),
            xaxis=dict(title="", side="bottom"),
            yaxis=dict(title=""),
            coloraxis_showscale=True,
            height=max(280, len(ten_dept) * 32 + 80),
        )
        st.plotly_chart(fig_heat, use_container_width=True)


# TAB 5 · RECRUITMENT TREND
with tab5:
    if "hire_date" not in df.columns:
        st.info("Column `hire_date` not found in data.")
    else:
        hire_monthly = (
            df.groupby(df["hire_date"].dt.to_period("M").dt.to_timestamp())
            .size()
            .reset_index(name="new_hires")
            .sort_values("hire_date")
        )
        hire_monthly["cumulative"] = hire_monthly["new_hires"].cumsum()
        hire_monthly["rolling_12"] = hire_monthly["new_hires"].rolling(12, min_periods=1).mean().round(1)

        col_trend, col_annual = st.columns([2, 1])

        # Monthly Trend Area Chart
        with col_trend:
            fig_hire = make_subplots(specs=[[{"secondary_y": True}]])

            fig_hire.add_trace(
                go.Bar(
                    x=hire_monthly["hire_date"],
                    y=hire_monthly["new_hires"],
                    name="New Hires/Month",
                    marker_color="#7C3AED",
                    opacity=0.75,
                    hovertemplate="<b>%{x|%b %Y}</b><br>New Hires: %{y:,}<extra></extra>",
                ),
                secondary_y=False,
            )
            fig_hire.add_trace(
                go.Scatter(
                    x=hire_monthly["hire_date"],
                    y=hire_monthly["rolling_12"],
                    name="Rolling Avg (12M)",
                    mode="lines",
                    line=dict(color="#D97706", width=2.5, dash="dot"),
                    hovertemplate="<b>%{x|%b %Y}</b><br>Rolling Avg: %{y:.1f}<extra></extra>",
                ),
                secondary_y=False,
            )
            fig_hire.add_trace(
                go.Scatter(
                    x=hire_monthly["hire_date"],
                    y=hire_monthly["cumulative"],
                    name="Cumulative",
                    mode="lines",
                    line=dict(color="#059669", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(5,150,105,.06)",
                    hovertemplate="<b>%{x|%b %Y}</b><br>Cumulative: %{y:,}<extra></extra>",
                ),
                secondary_y=True,
            )
            fig_hire.update_layout(
                **PLOTLY_BASE,
                title=dict(text="Monthly Recruitment Trend", font=dict(size=13)),
                xaxis=dict(showgrid=False, tickformat="%b %Y"),
                yaxis=dict(title="New Hires/Month", **GRID_Y),
                yaxis2=dict(title="Cumulative Total", showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
            )
            st.plotly_chart(fig_hire, use_container_width=True)

        # Recruitment by Year
        with col_annual:
            hire_yearly = (
                df.groupby(df["hire_date"].dt.year)
                .size()
                .reset_index(name="count")
            )
            hire_yearly.columns = ["year", "count"]
            hire_yearly = hire_yearly.sort_values("year")

            fig_yr = go.Figure(
                go.Bar(
                    x=hire_yearly["year"].astype(str),
                    y=hire_yearly["count"],
                    marker=dict(
                        color=hire_yearly["count"],
                        colorscale=[[0, "#EDE9FE"], [1, "#5B21B6"]],
                        showscale=False,
                    ),
                    text=hire_yearly["count"].apply(lambda v: f"{v:,}"),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Recruits: %{y:,}<extra></extra>",
                )
            )
            fig_yr.update_layout(
                **PLOTLY_BASE,
                title=dict(text="Recruitment by Year", font=dict(size=13)),
                xaxis=dict(**NO_GRID, title="Year", tickangle=-45),
                yaxis=dict(**GRID_Y, title="Count"),
                height=380,
            )
            st.plotly_chart(fig_yr, use_container_width=True)

        # Recruitment per Department (Stacked Bar per Year)
        if DEPT_COL:
            st.markdown("<br>", unsafe_allow_html=True)
            text_top_n_dept = str(top_n_dept)
            hire_dept = (
                df.assign(hire_year=df["hire_date"].dt.year)
                .groupby(["hire_year", DEPT_COL])
                .size()
                .reset_index(name="count")
            )
            # Filter top N dept to prevent chart cluttering
            top_d_hire = df[DEPT_COL].value_counts().nlargest(top_n_dept).index
            hire_dept  = hire_dept[hire_dept[DEPT_COL].isin(top_d_hire)]

            fig_hd = px.bar(
                hire_dept,
                x="hire_year",
                y="count",
                color=DEPT_COL,
                barmode="stack",
                color_discrete_sequence=PALETTE_DEPT,
                labels={"hire_year": "Year", "count": "Count", DEPT_COL: "Department"},
                text="count",
            )
            fig_hd.update_traces(
                textposition="inside",
                textfont=dict(size=9),
                hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,}<extra></extra>",
            )
            fig_hd.update_layout(
                **PLOTLY_BASE,
                title=dict(
                    text=f"Recruitment by Year × Department (Top {top_n_dept})",
                    font=dict(size=13)
                ),
                xaxis=dict(**NO_GRID, title="Year", type="category"),
                yaxis=dict(**GRID_Y, title="Count"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                height=380,
            )
            st.plotly_chart(fig_hd, use_container_width=True)


# OPTIONAL DETAIL TABLE

if show_table:
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;margin-bottom:.75rem;">'
        f'{shared.icon_label("table", "Detailed Employee Data", color="#7C3AED", size=16)}</div>',
        unsafe_allow_html=True,
    )

    display_cols_emp = ["employee_id"]
    rename_emp = {"employee_id": "ID"}

    for col, label in [
        ("first_name", "First Name"),   ("last_name", "Last Name"),
        (GENDER_COL, "Gender"),         (DEPT_COL,   "Department"),
        (JOB_COL,    "Job Title"),      ("age",       "Age"),
        ("hire_date", "Hire Date"),     ("tenure_years", "Tenure (yrs)"),
        (STATUS_COL, "Status"),
    ]:
        if col and col in df.columns:
            display_cols_emp.append(col)
            rename_emp[col] = label

    display_cols_emp = [c for c in display_cols_emp if c in df.columns]

    show_df = (
        df[display_cols_emp]
        .rename(columns=rename_emp)
        .reset_index(drop=True)
    )

    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
        height=420,
    )

    st.caption(f"Showing {len(show_df):,} rows out of {len(wf):,} total employees")


# FOOTER

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;padding:1.5rem 0;'
    'font-size:.75rem;color:var(--text-muted);">'
    'Workforce Analysis · HR Analytics Dashboard &nbsp;·&nbsp; '
    'Data is synthetic for demonstration purposes</div>',
    unsafe_allow_html=True,
)
