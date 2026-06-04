"""
pages/performance_analysis.py
─────────────────────────────
HR Analytics Dashboard — Performance Analysis
Employee performance evaluation based on performance_logs, employees, and departments.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Performance Analysis · HR Analytics",
    page_icon="📊",
    layout="wide",
)

import components.shared as shared

# ── Custom CSS ────────────────────────────────────────────────────────────────
shared.inject_custom_css()

# ── Plotly Theme Helper ────────────────────────────────────────────────────────
def plotly_theme() -> dict:
    return shared.get_plotly_theme()

PALETTE = [
    "#4f8ef7", "#a78bfa", "#22c55e", "#f59e0b",
    "#ef4444", "#06b6d4", "#f97316", "#ec4899",
]

# ── Data Loaders (cached) ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_performance_logs() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("performance_logs.csv"))
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    for col in ["review_date", "date", "period_date", "log_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df.rename(columns={col: "review_date"}, inplace=True)
            break
    return df

@st.cache_data(show_spinner=False)
def load_employees() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("employees.csv"))
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    return df

@st.cache_data(show_spinner=False)
def load_departments() -> pd.DataFrame:
    df = pd.read_csv(shared.get_data_path("departments.csv"))
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    return df


@st.cache_data(show_spinner=False)
def build_master(_perf: pd.DataFrame, _emp: pd.DataFrame, _dept: pd.DataFrame) -> pd.DataFrame:
    """
    Merge performance_logs → employees → departments.
    Tries common FK column names; falls back gracefully.
    """
    emp_id_col_perf = next(
        (c for c in _perf.columns if "employee" in c and ("id" in c or "no" in c)), None
    ) or next((c for c in _perf.columns if "emp" in c), _perf.columns[0])

    emp_id_col_emp = next(
        (c for c in _emp.columns if "employee" in c and ("id" in c or "no" in c)), None
    ) or next((c for c in _emp.columns if "emp" in c), _emp.columns[0])

    dept_id_col_emp  = next((c for c in _emp.columns  if "department" in c or "dept" in c), None)
    dept_id_col_dept = next((c for c in _dept.columns if "department" in c or "dept" in c), None)

    df = pd.merge(
        _perf, _emp,
        left_on=emp_id_col_perf, right_on=emp_id_col_emp,
        how="left", suffixes=("", "_emp"),
    )

    if dept_id_col_emp and dept_id_col_dept:
        df = pd.merge(
            df, _dept,
            left_on=dept_id_col_emp, right_on=dept_id_col_dept,
            how="left", suffixes=("", "_dept"),
        )

    score_candidates = [c for c in df.columns if "score" in c or "rating" in c or "point" in c]
    if score_candidates and "performance_score" not in df.columns:
        df.rename(columns={score_candidates[0]: "performance_score"}, inplace=True)

    dept_name_candidates = [c for c in df.columns if "department_name" in c or ("dept" in c and "name" in c)]
    if dept_name_candidates and "department_name" not in df.columns:
        df.rename(columns={dept_name_candidates[0]: "department_name"}, inplace=True)

    return df


# ── Grade Helper ───────────────────────────────────────────────────────────────
def score_to_grade(score: float, max_score: float = 100.0) -> str:
    pct = score / max_score * 100
    if pct >= 90: return "Excellent"
    if pct >= 75: return "Good"
    if pct >= 60: return "Average"
    if pct >= 45: return "Below Average"
    return "Poor"

GRADE_COLOR = {
    "Excellent":     "#22c55e",
    "Good":          "#4f8ef7",
    "Average":       "#f59e0b",
    "Below Average": "#f97316",
    "Poor":          "#ef4444",
}

# ── Load Data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading performance data…"):
    try:
        raw_perf = load_performance_logs()
        raw_emp  = load_employees()
        raw_dept = load_departments()
        df = build_master(raw_perf, raw_emp, raw_dept)
        data_ok = True
    except FileNotFoundError as e:
        st.error(f"❌ File not found: `{e.filename}`. Make sure `data/oltp/` contains all required CSV files.")
        data_ok = False
    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        data_ok = False

if not data_ok:
    st.stop()

# ── Page Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1.5rem;">
    <span style="font-size:1.8rem;">📊</span>
    <div>
        <h1 style="margin:0;font-size:1.8rem;font-weight:800;
                   background:linear-gradient(135deg,#D97706,#DC2626);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;line-height:1.2;">Performance Analysis</h1>
        <p style="margin:0;font-size:.88rem;color:var(--text-secondary);">
            Comprehensive employee performance evaluation — scores, distributions, trends, and cross-department comparisons
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar Filters ────────────────────────────────────────────────────────────
with st.sidebar:
    shared.add_sidebar_header()
    st.markdown("### 🎛️ Filters")

    if "department_name" in df.columns:
        all_depts = sorted(df["department_name"].dropna().unique().tolist())
        selected_depts = st.multiselect(
            "Department",
            options=all_depts,
            default=all_depts,
            key="perf_dept_filter",
        )
    else:
        selected_depts = None

    if "review_date" in df.columns and df["review_date"].notna().any():
        min_date = df["review_date"].min().date()
        max_date = df["review_date"].max().date()
        date_range = st.date_input(
            "Review Period Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="perf_date_filter",
        )
    else:
        date_range = None

    if "performance_score" in df.columns:
        score_min = float(df["performance_score"].min())
        score_max = float(df["performance_score"].max())
        score_range = st.slider(
            "Score Range",
            min_value=score_min,
            max_value=score_max,
            value=(score_min, score_max),
            step=0.5,
            key="perf_score_filter",
        )
    else:
        score_range = None

    st.markdown("---")
    st.caption("💡 Filters apply to all charts on this page.")

# ── Apply Filters ──────────────────────────────────────────────────────────────
fdf = df.copy()

if selected_depts and "department_name" in fdf.columns:
    fdf = fdf[fdf["department_name"].isin(selected_depts)]

if date_range and len(date_range) == 2 and "review_date" in fdf.columns:
    fdf = fdf[
        (fdf["review_date"].dt.date >= date_range[0]) &
        (fdf["review_date"].dt.date <= date_range[1])
    ]

if score_range and "performance_score" in fdf.columns:
    fdf = fdf[
        (fdf["performance_score"] >= score_range[0]) &
        (fdf["performance_score"] <= score_range[1])
    ]

# ── Validate Score Column ──────────────────────────────────────────────────────
if "performance_score" not in fdf.columns:
    st.warning("⚠️ Performance score column not found. Ensure `performance_logs.csv` has a column named `score`, `performance_score`, or `rating`.")
    st.stop()

score_col = "performance_score"
max_possible = fdf[score_col].max() if fdf[score_col].max() <= 10 else 100.0

fdf["grade"] = fdf[score_col].apply(lambda x: score_to_grade(x, max_possible))

# ── KPI Metrics ────────────────────────────────────────────────────────────────
avg_score      = fdf[score_col].mean()
median_score   = fdf[score_col].median()
total_reviews  = len(fdf)
excellent_pct  = (fdf["grade"] == "Excellent").mean() * 100
below_avg_pct  = (fdf["grade"].isin(["Below Average", "Poor"])).mean() * 100

theme = plotly_theme()

col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
with col_k1:
    st.metric("⭐ Avg Score", f"{avg_score:.2f}", f"out of {max_possible:.0f} max")
with col_k2:
    st.metric("📊 Median Score", f"{median_score:.2f}", "distribution midpoint")
with col_k3:
    st.metric("📋 Total Reviews", f"{total_reviews:,}", "entries after filter")
with col_k4:
    st.metric("🌟 Excellent Rate", f"{excellent_pct:.1f}%", "employees in Excellent tier")
with col_k5:
    st.metric("⚠️ Below Average Rate", f"{below_avg_pct:.1f}%", "Below Avg + Poor tier")

st.markdown("<br>", unsafe_allow_html=True)

# ── ROW 1 — Score Distribution + Grade Donut ──────────────────────────────────
col1, col2 = st.columns([3, 2], gap="medium")

with col1:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Performance Score Distribution</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Histogram with KDE curve — view the spread of employee scores</div>', unsafe_allow_html=True)

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=fdf[score_col],
        nbinsx=50,
        marker_color="#4f8ef7",
        marker_line_color="rgba(255,255,255,.15)",
        marker_line_width=0.5,
        opacity=0.85,
        name="Frequency",
        hovertemplate="Score: %{x}<br>Count: %{y}<extra></extra>",
    ))
    from scipy.stats import gaussian_kde
    try:
        scores_clean = fdf[score_col].dropna().values
        kde = gaussian_kde(scores_clean)
        x_range = np.linspace(scores_clean.min(), scores_clean.max(), 300)
        kde_y = kde(x_range) * len(scores_clean) * (scores_clean.max() - scores_clean.min()) / 50
        fig_hist.add_trace(go.Scatter(
            x=x_range, y=kde_y,
            mode="lines",
            line=dict(color="#a78bfa", width=2.5),
            name="KDE",
            hovertemplate="Score: %{x:.1f}<extra>KDE</extra>",
        ))
    except Exception:
        pass

    fig_hist.add_vline(
        x=avg_score, line_dash="dot", line_color="#f59e0b", line_width=2,
        annotation_text=f"Avg: {avg_score:.1f}",
        annotation_position="top right",
        annotation_font_color="#f59e0b",
    )
    fig_hist.update_layout(**theme, height=360, showlegend=True,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                           margin=dict(t=60, b=40, l=40, r=20))
    st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Performance Grade Breakdown</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Composition of grade categories from total reviews</div>', unsafe_allow_html=True)

    grade_counts = fdf["grade"].value_counts().reindex(GRADE_COLOR.keys()).dropna()
    fig_donut = go.Figure(go.Pie(
        labels=grade_counts.index,
        values=grade_counts.values,
        hole=0.58,
        marker_colors=[GRADE_COLOR[g] for g in grade_counts.index],
        textinfo="label+percent",
        textfont=dict(family="DM Sans, sans-serif", size=12),
        hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>Share: %{percent}<extra></extra>",
        pull=[0.04 if g == "Excellent" else 0 for g in grade_counts.index],
    ))
    fig_donut.update_layout(**theme, height=300,
                            annotations=[dict(text=f"<b>{total_reviews:,}</b><br>Reviews",
                                              x=0.5, y=0.5, font_size=13, showarrow=False)])
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 2 — Avg Score by Department ───────────────────────────────────────────
if "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Average Performance Score by Department</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Compare performance across departments — sorted by highest score</div>', unsafe_allow_html=True)

    dept_avg = (
        fdf.groupby("department_name")[score_col]
        .agg(avg_score_dept="mean", total_review="count", std_score="std")
        .reset_index()
        .sort_values("avg_score_dept", ascending=True)
    )

    fig_dept = go.Figure()
    fig_dept.add_trace(go.Bar(
        x=dept_avg["avg_score_dept"],
        y=dept_avg["department_name"],
        orientation="h",
        marker=dict(
            color=dept_avg["avg_score_dept"],
            colorscale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#22c55e"]],
            cmin=dept_avg["avg_score_dept"].min(),
            cmax=dept_avg["avg_score_dept"].max(),
            showscale=True,
            colorbar=dict(title="Avg Score", thickness=10, len=0.7),
        ),
        error_x=dict(
            type="data",
            array=dept_avg["std_score"].fillna(0),
            color="rgba(128,128,128,.4)",
            thickness=1.5,
        ),
        text=dept_avg["avg_score_dept"].round(2),
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Avg Score: %{x:.2f}<br>"
            "Total Reviews: %{customdata[0]:,}<extra></extra>"
        ),
        customdata=dept_avg[["total_review"]].values,
    ))
    fig_dept.add_vline(
        x=avg_score, line_dash="dot", line_color="#4f8ef7", line_width=1.5,
        annotation_text=f"Global avg: {avg_score:.2f}",
        annotation_position="top",
        annotation_font_color="#4f8ef7",
        annotation_font_size=11,
    )
    n_dept = len(dept_avg)
    fig_dept.update_layout(**theme, height=max(280, n_dept * 42 + 60))
    fig_dept.update_xaxes(title_text="Average Score")
    st.plotly_chart(fig_dept, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 3 — Score Distribution by Department ─────────────────────────────────
if "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Score Distribution by Department</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Box plot — view spread, median, and outliers per department</div>', unsafe_allow_html=True)

    dept_order = (
        fdf.groupby("department_name")[score_col]
        .mean()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig_box = px.box(
        fdf.dropna(subset=["department_name", score_col]),
        x="department_name",
        y=score_col,
        color="department_name",
        color_discrete_sequence=PALETTE,
        category_orders={"department_name": dept_order},
        points="outliers",
        notched=False,
        labels={"department_name": "Department", score_col: "Performance Score"},
    )
    fig_box.update_traces(
        marker_size=3,
        marker_opacity=0.5,
        line_width=1.5,
    )
    fig_box.update_layout(**theme, height=320, showlegend=False)
    fig_box.update_xaxes(tickangle=-35)
    st.plotly_chart(fig_box, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 4 — Grade Heatmap by Dept ─────────────────────────────────────────────
if "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Grade Heatmap by Department</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Percentage of employees in each grade category per department</div>', unsafe_allow_html=True)

    grade_order = ["Excellent", "Good", "Average", "Below Average", "Poor"]
    heatmap_df = (
        fdf.groupby(["department_name", "grade"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=[g for g in grade_order if g in fdf["grade"].unique()], fill_value=0)
    )
    heatmap_pct = heatmap_df.div(heatmap_df.sum(axis=1), axis=0) * 100

    fig_heat = go.Figure(go.Heatmap(
        z=heatmap_pct.values,
        x=heatmap_pct.columns.tolist(),
        y=heatmap_pct.index.tolist(),
        colorscale="RdYlGn",
        zmin=0, zmax=100,
        text=np.round(heatmap_pct.values, 1),
        texttemplate="%{text}%",
        textfont=dict(size=11, family="DM Mono, monospace"),
        hovertemplate="Dept: %{y}<br>Grade: %{x}<br>Percentage: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="% Employees", thickness=12, len=0.85),
    ))
    fig_heat.update_layout(**theme, height=max(250, len(heatmap_pct) * 38 + 80))
    st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 5 — Raw Data Preview ───────────────────────────────────────────────────
with st.expander("🗂️ Raw Data Preview (after filters)", expanded=False):
    preview_cols = [c for c in [
        "employee_id", "employee_name", "department_name",
        score_col, "grade", "review_date",
    ] if c in fdf.columns]
    if not preview_cols:
        preview_cols = fdf.columns[:8].tolist()

    st.dataframe(
        fdf[preview_cols].head(500),
        use_container_width=True,
        height=320,
    )
    st.caption(f"Showing first 500 rows of {len(fdf):,} rows matching current filters.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem; opacity: .35; font-size: .78rem;">
    HR Analytics Dashboard &nbsp;·&nbsp; Performance Analysis
    &nbsp;·&nbsp; Synthetic data for demonstration purposes
</div>
""", unsafe_allow_html=True)