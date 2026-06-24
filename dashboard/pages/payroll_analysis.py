"""
pages/payroll_analysis.py
─────────────────────────
HR Analytics Dashboard — Payroll Analysis
Analisis pengeluaran gaji perusahaan berdasarkan payroll_transactions, employees, dan departments.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Page Config
st.set_page_config(
    page_title="Payroll Analysis · HR Analytics",
    page_icon=":material/payments:",
    layout="wide",
)

import components.shared as shared

# Custom CSS
shared.inject_custom_css()

# Plotly Theme Helper
def plotly_theme() -> dict:
    return shared.get_plotly_theme()

def fmt_currency(value: float, short: bool = False) -> str:
    """Format number as Rupiah (IDR)."""
    if short:
        if value >= 1_000_000_000:
            return f"Rp {value/1_000_000_000:.2f}B"
        if value >= 1_000_000:
            return f"Rp {value/1_000_000:.1f}M"
        return f"Rp {value:,.0f}"
    return f"Rp {value:,.0f}"

PALETTE = ["#14b8a6","#3b82f6","#8b5cf6","#f59e0b","#f43f5e",
           "#10b981","#f97316","#06b6d4","#ec4899","#84cc16"]

# Data Loaders

@st.cache_data(show_spinner=False)
def load_dates() -> pd.DataFrame:
    df = shared.load_supabase_table("dim_date")
    return df

@st.cache_data(show_spinner=False)
def load_payroll(dates_df: pd.DataFrame) -> pd.DataFrame:
    df = shared.load_supabase_table("fact_payroll")
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    
    if not dates_df.empty and "date_id" in df.columns:
        df = df.merge(dates_df[["date_id", "full_date"]], on="date_id", how="left")
        
    # Detect & parse date column
    for col in ["full_date","pay_date","payment_date","payroll_date","transaction_date","date","period"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df.rename(columns={col: "pay_date"}, inplace=True)
            break
    return df

@st.cache_data(show_spinner=False)
def load_employees() -> pd.DataFrame:
    df = shared.load_supabase_table("dim_employee")
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    return df

@st.cache_data(show_spinner=False)
def load_departments() -> pd.DataFrame:
    df = shared.load_supabase_table("dim_department")
    df.columns = df.columns.str.strip().str.lower().str.replace(r"\s+", "_", regex=True)
    return df


@st.cache_data(show_spinner=False)
def build_master(_pay: pd.DataFrame, _emp: pd.DataFrame, _dept: pd.DataFrame) -> pd.DataFrame:
    """Merge payroll → employees → departments with automatic FK detection."""

    def _find_col(df, *hints):
        for h in hints:
            for c in df.columns:
                if h in c:
                    return c
        return df.columns[0]

    emp_fk_pay  = _find_col(_pay, "employee_id", "employee_no", "emp_id", "emp")
    emp_fk_emp  = _find_col(_emp, "employee_id", "employee_no", "emp_id", "emp")
    dept_fk_emp = _find_col(_emp, "department_id", "dept_id", "department")
    dept_fk_dep = _find_col(_dept, "department_id", "dept_id", "department")

    df = pd.merge(_pay, _emp,
                  left_on=emp_fk_pay, right_on=emp_fk_emp,
                  how="left", suffixes=("", "_emp"))

    df = pd.merge(df, _dept,
                  left_on=dept_fk_emp, right_on=dept_fk_dep,
                  how="left", suffixes=("", "_dept"))

    # Normalise salary/amount column name
    for cand in ["net_salary","gross_salary","total_salary","amount","salary","pay_amount","net_pay","gross_pay"]:
        if cand in df.columns:
            df.rename(columns={cand: "salary_amount"}, inplace=True)
            break

    # Normalise department name column
    for cand in ["department_name","dept_name","department"]:
        if cand in df.columns and cand != "department_name":
            df.rename(columns={cand: "department_name"}, inplace=True)
        elif cand == "department_name":
            break

    return df

# Load Data
with st.spinner("Loading payroll data…"):
    try:
        raw_dates = load_dates()
        raw_pay  = load_payroll(raw_dates)
        raw_emp  = load_employees()
        raw_dept = load_departments()
        df = build_master(raw_pay, raw_emp, raw_dept)
        data_ok = True
    except Exception as e:
        load_error = e
        data_ok = False

if not data_ok:
    shared.render_data_load_error(load_error)
    st.stop()

if "salary_amount" not in df.columns:
    st.warning("Salary amount column not found. Ensure `payroll_transactions.csv` has a column named `salary`, `amount`, `net_salary`, or `gross_salary`.")
    st.stop()

# Page Header
st.markdown("""
<div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1.5rem;">
    <span style="display:inline-flex;color:#DC2626;">""" + shared.icon_svg("wallet", size=30, color="#DC2626") + """</span>
    <div>
        <h1 style="margin:0;font-size:1.8rem;font-weight:800;
                   background:linear-gradient(135deg,#059669,#2563EB);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                   background-clip:text;line-height:1.2;">Payroll Analysis</h1>
        <p style="margin:0;font-size:.88rem;color:var(--text-secondary);">
            Comprehensive payroll spend analysis — totals, trends, department allocation, and salary composition
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Filters
with st.sidebar:
    shared.add_sidebar_header()
    st.markdown("### Filters")

    if "department_name" in df.columns:
        all_depts = sorted(df["department_name"].dropna().unique().tolist())
        sel_depts = st.multiselect("Department", options=all_depts, default=all_depts, key="pay_dept")
    else:
        sel_depts = None

    if "pay_date" in df.columns and df["pay_date"].notna().any():
        min_d = df["pay_date"].min().date()
        max_d = df["pay_date"].max().date()
        date_range = st.date_input("Period Range", value=(min_d, max_d),
                                    min_value=min_d, max_value=max_d, key="pay_date")
    else:
        date_range = None

    granularity = st.selectbox("Trend Granularity", ["Monthly", "Quarterly", "Yearly"], index=0, key="pay_gran")

    component_cols = [c for c in df.columns if any(k in c for k in
        ["basic","allowance","bonus","overtime","deduction","tax","bpjs","insurance","tunjangan","potongan"])]

    st.markdown("---")
    st.caption("Filters apply to all visualizations on this page.")

# Apply Filters
fdf = df.copy()

if sel_depts and "department_name" in fdf.columns:
    fdf = fdf[fdf["department_name"].isin(sel_depts)]

if date_range and len(date_range) == 2 and "pay_date" in fdf.columns:
    fdf = fdf[(fdf["pay_date"].dt.date >= date_range[0]) &
              (fdf["pay_date"].dt.date <= date_range[1])]

# Derived Columns
if "pay_date" in fdf.columns and fdf["pay_date"].notna().any():
    fdf["year_month"] = fdf["pay_date"].dt.to_period("M").astype(str)
    fdf["year_q"]     = fdf["pay_date"].dt.to_period("Q").astype(str)
    fdf["year"]       = fdf["pay_date"].dt.year.astype(str)

    latest_month = fdf["pay_date"].max().to_period("M")
    prev_month   = latest_month - 1
    this_m_df    = fdf[fdf["pay_date"].dt.to_period("M") == latest_month]
    prev_m_df    = fdf[fdf["pay_date"].dt.to_period("M") == prev_month]
    has_date = True
else:
    has_date = False
    this_m_df = fdf
    prev_m_df = pd.DataFrame()

# KPI Calculations
total_all        = fdf["salary_amount"].sum()
total_this_month = this_m_df["salary_amount"].sum()
total_prev_month = prev_m_df["salary_amount"].sum() if not prev_m_df.empty else None
mom_delta        = ((total_this_month - total_prev_month) / total_prev_month * 100
                    if total_prev_month else None)

avg_per_emp     = fdf.groupby(fdf.columns[0])["salary_amount"].sum().mean() if len(fdf) > 0 else 0
n_transactions  = len(fdf)

theme = plotly_theme()

# KPI Cards
def delta_html(val):
    if val is None: return '<div class="kpi-sub">previous month not available</div>'
    icon = "▲" if val >= 0 else "▼"
    cls  = "kpi-delta-pos" if val >= 0 else "kpi-delta-neg"
    return f'<div class="{cls}">{icon} {abs(val):.1f}% vs last month</div>'

col_k1, col_k2, col_k3, col_k4 = st.columns(4)
with col_k1:
    st.metric("Total Payroll Spend", fmt_currency(total_all, short=True), "entire period after filters")
with col_k2:
    label = f"{str(latest_month) if has_date else 'Latest'} Payroll"
    st.metric(label, fmt_currency(total_this_month, short=True),
              f"{'+' if mom_delta and mom_delta >= 0 else ''}{mom_delta:.1f}% vs last month" if mom_delta else "no prior month")
with col_k3:
    st.metric("Avg per Employee", fmt_currency(avg_per_emp, short=True), "total ÷ unique employees")
with col_k4:
    st.metric("Total Transactions", f"{n_transactions:,}", "payroll entries after filters")

st.markdown("<br>", unsafe_allow_html=True)

# ROW 1 — Payroll Spend Trend (Area)
st.markdown('<div class="chart-card">', unsafe_allow_html=True)
st.markdown(f'<div class="chart-title">{shared.icon_label("trending-up", "Payroll Spend Over Time", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
st.markdown('<div class="chart-sub">Total salary paid per period — use the granularity filter in the sidebar</div>', unsafe_allow_html=True)

if has_date:
    gran_map = {"Monthly": "year_month", "Quarterly": "year_q", "Yearly": "year"}
    gran_col = gran_map[granularity]

    if "department_name" in fdf.columns:
        trend_df = (fdf.groupby([gran_col, "department_name"])["salary_amount"]
                    .sum().reset_index())
        trend_df.columns = ["period", "department_name", "salary_amount"]
        dept_list = trend_df["department_name"].dropna().unique()

        fig_trend = go.Figure()
        for i, dept in enumerate(dept_list):
            sub_df = trend_df[trend_df["department_name"] == dept]
            color  = PALETTE[i % len(PALETTE)]
            fig_trend.add_trace(go.Scatter(
                x=sub_df["period"], y=sub_df["salary_amount"],
                mode="lines", name=dept,
                line=dict(color=color, width=1.8),
                stackgroup="one",
                hovertemplate=f"<b>{dept}</b><br>Period: %{{x}}<br>Amount: Rp %{{y:,.0f}}<extra></extra>",
            ))
    else:
        trend_df = (fdf.groupby(gran_col)["salary_amount"].sum()
                    .reset_index().rename(columns={gran_col: "period"}))
        fig_trend = go.Figure(go.Scatter(
            x=trend_df["period"], y=trend_df["salary_amount"],
            mode="lines+markers",
            line=dict(color="#14b8a6", width=2.5),
            marker=dict(size=6, color="#14b8a6", line=dict(color="#fff", width=1.5)),
            fill="tozeroy", fillcolor="rgba(20,184,166,.12)",
            hovertemplate="Period: %{x}<br>Total: Rp %{y:,.0f}<extra></extra>",
        ))

    fig_trend.update_layout(**theme, height=340, showlegend="department_name" in fdf.columns,
                            legend=dict(orientation="h", y=-0.22, x=0))
    fig_trend.update_xaxes(tickangle=-35, title_text=granularity)
    fig_trend.update_yaxes(title_text="Total Salary (Rp)", tickformat=",.0f")
else:
    fig_trend = go.Figure()
    fig_trend.add_annotation(text="Date data not available",
                             xref="paper", yref="paper", x=0.5, y=0.5,
                             showarrow=False, font=dict(size=14, color="gray"))
    fig_trend.update_layout(**theme, height=300)

st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})
st.markdown('</div>', unsafe_allow_html=True)

# ROW 2 — Department Allocation (Bar) + Donut Share
col1, col2 = st.columns([3, 2], gap="medium")

with col1:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("building", "Payroll Allocation by Department", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Compare total spend and average salary per department</div>', unsafe_allow_html=True)

    if "department_name" in fdf.columns:
        dept_df = (fdf.groupby("department_name")["salary_amount"]
                   .agg(total="sum", mean="mean", count="count")
                   .reset_index()
                   .sort_values("total", ascending=True))

        fig_dept = make_subplots(specs=[[{"secondary_y": True}]])
        fig_dept.add_trace(go.Bar(
            x=dept_df["total"],
            y=dept_df["department_name"],
            orientation="h",
            name="Total Salary",
            marker=dict(
                color=dept_df["total"],
                colorscale=[[0,"#0f766e"],[0.5,"#14b8a6"],[1,"#5eead4"]],
                showscale=False,
            ),
            text=[fmt_currency(v, short=True) for v in dept_df["total"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Total: Rp %{x:,.0f}<br>Headcount: %{customdata}<extra></extra>",
            customdata=dept_df["count"],
        ), secondary_y=False)

        fig_dept.add_trace(go.Scatter(
            x=dept_df["mean"],
            y=dept_df["department_name"],
            mode="markers",
            name="Avg/Person",
            marker=dict(symbol="diamond", size=9, color="#f59e0b",
                        line=dict(color="#fff", width=1.5)),
            hovertemplate="<b>%{y}</b><br>Average: Rp %{x:,.0f}<extra></extra>",
        ), secondary_y=True)

        fig_dept.update_layout(**theme, height=360,
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                               margin=dict(t=70, b=40, l=40, r=20))
        fig_dept.update_xaxes(title_text="Total Salary (Rp)", tickformat=",.0f")
        fig_dept.update_yaxes(secondary_y=False, showgrid=False)
        fig_dept.update_yaxes(secondary_y=True, title_text="Avg Salary (Rp)",
                              tickformat=",.0f", showgrid=False)
    else:
        fig_dept = go.Figure()
        fig_dept.add_annotation(text="Department column not available",
                                xref="paper", yref="paper", x=0.5, y=0.5,
                                showarrow=False, font=dict(size=13, color="gray"))
        fig_dept.update_layout(**theme, height=320)

    st.plotly_chart(fig_dept, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("pie-chart", "Budget Share by Department", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Each department\'s contribution to total payroll</div>', unsafe_allow_html=True)

    if "department_name" in fdf.columns:
        donut_df = (fdf.groupby("department_name")["salary_amount"]
                    .sum().reset_index()
                    .sort_values("salary_amount", ascending=False))

        fig_donut = go.Figure(go.Pie(
            labels=donut_df["department_name"],
            values=donut_df["salary_amount"],
            hole=0.55,
            marker_colors=PALETTE[:len(donut_df)],
            textinfo="label+percent",
            textfont=dict(family="DM Sans, sans-serif", size=11),
            hovertemplate="<b>%{label}</b><br>Total: Rp %{value:,.0f}<br>Share: %{percent}<extra></extra>",
            pull=[0.04] + [0] * (len(donut_df) - 1),
        ))
        fig_donut.update_layout(
            **theme, height=320,
            annotations=[dict(text=f"<b>{fmt_currency(total_all, short=True)}</b><br>Total",
                              x=0.5, y=0.5, font_size=12, showarrow=False)],
        )
    else:
        fig_donut = go.Figure()
        fig_donut.add_annotation(text="Data not available",
                                 xref="paper", yref="paper", x=0.5, y=0.5,
                                 showarrow=False, font=dict(size=13, color="gray"))
        fig_donut.update_layout(**theme, height=320)

    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ROW 3 — Salary Components + Distribution
col3, col4 = st.columns([2, 3], gap="medium")

with col3:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("layout", "Salary Component Composition", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Breakdown of components within total payroll</div>', unsafe_allow_html=True)

    if component_cols:
        comp_totals = fdf[component_cols].sum().sort_values(ascending=False)
        comp_labels = [c.replace("_", " ").title() for c in comp_totals.index]
        colors_comp = PALETTE[:len(comp_totals)]

        fig_comp = go.Figure(go.Bar(
            x=comp_labels,
            y=comp_totals.values,
            marker_color=colors_comp,
            text=[fmt_currency(v, short=True) for v in comp_totals.values],
            textposition="outside",
            hovertemplate="%{x}<br>Total: Rp %{y:,.0f}<extra></extra>",
        ))
        fig_comp.update_layout(**theme, height=280)
        fig_comp.update_yaxes(tickformat=",.0f", title_text="Rp")
    else:
        if has_date and total_prev_month:
            delta_val = total_this_month - total_prev_month
            fig_comp = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "total"],
                x=["Last Month", "Change", "This Month"],
                y=[total_prev_month, delta_val, total_this_month],
                textposition="outside",
                text=[fmt_currency(total_prev_month, True),
                      ("+" if delta_val >= 0 else "") + fmt_currency(abs(delta_val), True),
                      fmt_currency(total_this_month, True)],
                connector=dict(line=dict(color="rgba(128,128,128,.3)")),
                increasing=dict(marker=dict(color="#f43f5e")),
                decreasing=dict(marker=dict(color="#10b981")),
                totals=dict(marker=dict(color="#14b8a6")),
            ))
            fig_comp.update_layout(**theme, height=280)
            fig_comp.update_yaxes(tickformat=",.0f")
        else:
            fig_comp = go.Figure()
            fig_comp.add_annotation(
                text="Salary component columns<br>not detected in CSV",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font=dict(size=13, color="gray"),
            )
            fig_comp.update_layout(**theme, height=280)

    st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("trending-down", "Salary Amount Distribution per Transaction", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Individual salary value spread — histogram + KDE</div>', unsafe_allow_html=True)

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=fdf["salary_amount"],
        nbinsx=60,
        marker_color="#3b82f6",
        marker_line_color="rgba(255,255,255,.1)",
        marker_line_width=0.4,
        opacity=0.82,
        name="Frequency",
        hovertemplate="Salary: Rp %{x:,.0f}<br>Count: %{y}<extra></extra>",
    ))
    try:
        from scipy.stats import gaussian_kde
        vals = fdf["salary_amount"].dropna().values
        kde  = gaussian_kde(vals)
        xr   = np.linspace(vals.min(), vals.max(), 400)
        kde_y = kde(xr) * len(vals) * (vals.max() - vals.min()) / 60
        fig_hist.add_trace(go.Scatter(
            x=xr, y=kde_y, mode="lines",
            line=dict(color="#14b8a6", width=2.5),
            name="KDE",
        ))
    except Exception:
        pass

    mean_sal   = fdf["salary_amount"].mean()
    median_sal = fdf["salary_amount"].median()
    fig_hist.add_vline(x=mean_sal, line_dash="dot", line_color="#f59e0b", line_width=2,
                       annotation_text=f"Mean: {fmt_currency(mean_sal, True)}",
                       annotation_font_color="#f59e0b", annotation_position="top right")
    fig_hist.add_vline(x=median_sal, line_dash="dot", line_color="#8b5cf6", line_width=2,
                       annotation_text=f"Median: {fmt_currency(median_sal, True)}",
                       annotation_font_color="#8b5cf6", annotation_position="top left")

    fig_hist.update_layout(**theme, height=320,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                           margin=dict(t=70, b=40, l=40, r=20))
    fig_hist.update_xaxes(title_text="Salary Amount (Rp)", tickformat=",.0f")
    st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ROW 4 — Monthly Heatmap per Department
if has_date and "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("calendar", "Monthly Payroll Heatmap by Department", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Color intensity shows spend magnitude — spot seasonal patterns or anomalies</div>', unsafe_allow_html=True)

    heat_df = (fdf.groupby(["year_month", "department_name"])["salary_amount"]
               .sum().unstack(fill_value=0))
    heat_df = heat_df.iloc[-18:] if len(heat_df) > 18 else heat_df

    fig_heat = go.Figure(go.Heatmap(
        z=heat_df.values,
        x=heat_df.columns.tolist(),
        y=heat_df.index.tolist(),
        colorscale="Teal",
        hovertemplate="Period: %{y}<br>Dept: %{x}<br>Total: Rp %{z:,.0f}<extra></extra>",
        colorbar=dict(title="Rp", thickness=12, len=0.8),
        text=[[fmt_currency(v, short=True) for v in row] for row in heat_df.values],
        texttemplate="%{text}",
        textfont=dict(size=9, family="DM Mono, monospace"),
    ))
    fig_heat.update_layout(**theme, height=max(300, len(heat_df) * 34 + 80))
    st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ROW 5 — Salary Distribution Box Plot
if "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("package", "Salary Distribution by Department", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Box plot — compare median, IQR, and outliers across departments</div>', unsafe_allow_html=True)

    dept_order = (fdf.groupby("department_name")["salary_amount"]
                  .median().sort_values(ascending=False).index.tolist())

    fig_box = px.box(
        fdf.dropna(subset=["department_name", "salary_amount"]),
        x="department_name", y="salary_amount",
        color="department_name",
        color_discrete_sequence=PALETTE,
        category_orders={"department_name": dept_order},
        points="outliers",
        labels={"department_name": "Department", "salary_amount": "Salary (Rp)"},
    )
    fig_box.update_traces(marker_size=3, marker_opacity=0.45, line_width=1.5)
    fig_box.update_layout(**theme, height=320, showlegend=False)
    fig_box.update_xaxes(tickangle=-30)
    fig_box.update_yaxes(tickformat=",.0f")
    st.plotly_chart(fig_box, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ROW 6 — Department Summary Table
if "department_name" in fdf.columns:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="chart-title">{shared.icon_label("table", "Payroll Summary by Department", color="#14b8a6", size=16)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-sub">Aggregate table for the selected period</div>', unsafe_allow_html=True)

    summary_df = (
        fdf.groupby("department_name")["salary_amount"]
        .agg(
            total_payroll="sum",
            average="mean",
            median="median",
            minimum="min",
            maximum="max",
            transactions="count",
        )
        .reset_index()
        .sort_values("total_payroll", ascending=False)
    )
    summary_df.columns = [
        "Department", "Total Payroll", "Average",
        "Median", "Minimum", "Maximum", "Transactions",
    ]
    for col in ["Total Payroll", "Average", "Median", "Minimum", "Maximum"]:
        summary_df[col] = summary_df[col].apply(lambda x: fmt_currency(x))
    summary_df["Transactions"] = summary_df["Transactions"].apply(lambda x: f"{x:,}")

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
        height=min(420, (len(summary_df) + 1) * 38 + 10),
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Raw Data Preview
with st.expander("Raw Data Preview (after filters)", expanded=False):
    preview_cols = [c for c in [
        "employee_id", "employee_name", "department_name",
        "salary_amount", "pay_date",
    ] + component_cols if c in fdf.columns]
    if not preview_cols:
        preview_cols = fdf.columns[:8].tolist()

    st.dataframe(fdf[preview_cols].head(500), use_container_width=True, height=300)
    st.caption(f"Showing first 500 rows of {len(fdf):,} rows matching current filters.")

# Footer
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem; opacity:.32; font-size:.76rem;">
    HR Analytics Dashboard &nbsp;·&nbsp; Payroll Analysis
    &nbsp;·&nbsp; Synthetic data for demonstration purposes
</div>
""", unsafe_allow_html=True)
