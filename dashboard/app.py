"""
HR Analytics Dashboard
======================
Main entry file: app.py
Handles global configuration and sidebar navigation.
"""

import streamlit as st
import components.shared as shared

# Page Configuration
st.set_page_config(
    page_title="HR Analytics Dashboard",
    page_icon=":material/groups:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS: Light & Dark Mode
shared.inject_custom_css()

# Sidebar Header
with st.sidebar:
    shared.add_sidebar_header()

    st.markdown(
        """
        <div style="font-size: 0.7rem; font-weight: 700; letter-spacing: .1em;
                    text-transform: uppercase; color: #64748B; padding: 0 .5rem .5rem;">
            Navigation
        </div>
        """,
        unsafe_allow_html=True,
    )

# Landing Page
st.markdown(
    f"""
    <div style="text-align: center; padding: 4rem 2rem 2rem;">
        <div style="display:flex;justify-content:center;margin-bottom:1rem;color:#2563EB;">
            {shared.icon_svg("bar-chart", size=54, color="#2563EB")}
        </div>
        <h1 style="font-size: 2.4rem; font-weight: 700; margin-bottom: .5rem;
                   background: linear-gradient(135deg, #2563EB, #7C3AED);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                   background-clip: text;">
            HR Analytics Dashboard
        </h1>
        <p style="font-size: 1.05rem; color: var(--text-secondary); max-width: 520px; margin: 0 auto 2rem;">
            Unified HR intelligence platform — from executive summaries to payroll and performance reports.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Quick-Nav Cards
pages = [
    {
        "icon": "building",
        "title": "Executive Summary",
        "desc": "Top-level metrics: total headcount, performance scores, and payroll spend.",
        "color": "#2563EB",
        "path": "pages/executive_summary.py",
    },
    {
        "icon": "users",
        "title": "Workforce Analysis",
        "desc": "Demographics, department distribution, job roles, and turnover.",
        "color": "#7C3AED",
        "path": "pages/workforce_analysis.py",
    },
    {
        "icon": "clock",
        "title": "Attendance Analysis",
        "desc": "Attendance rates, lateness, absenteeism, and time-series trends.",
        "color": "#059669",
        "path": "pages/attendance_analysis.py",
    },
    {
        "icon": "star",
        "title": "Performance Analysis",
        "desc": "Performance scores, rating distributions, and trends by period.",
        "color": "#D97706",
        "path": "pages/performance_analysis.py",
    },
    {
        "icon": "wallet",
        "title": "Payroll Analysis",
        "desc": "Payroll trends, salary distributions, and spend by department.",
        "color": "#DC2626",
        "path": "pages/payroll_analysis.py",
    },
]

cols = st.columns(3)
for i, page in enumerate(pages):
    with cols[i % 3]:
        st.markdown(
            f"""
            <div style="
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 1.4rem 1.2rem;
                margin-bottom: 1rem;
                box-shadow: var(--shadow-sm);
                border-top: 3px solid {page['color']};
                transition: box-shadow .2s, transform .2s;
            ">
                <div style="margin-bottom:.7rem;color:{page['color']};">
                    {shared.icon_svg(page['icon'], size=30, color=page['color'])}
                </div>
                <div style="font-size: 1rem; font-weight: 700;
                            color: var(--text-primary); margin-bottom: .3rem;">
                    {page['title']}
                </div>
                <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5;">
                    {page['desc']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Footer
st.markdown(
    """
    <div style="text-align: center; padding: 2rem 0 1rem;
                font-size: 0.75rem; color: var(--text-muted);">
        HR Analytics Dashboard &nbsp;·&nbsp; Synthetic data for demonstration purposes
    </div>
    """,
    unsafe_allow_html=True,
)
