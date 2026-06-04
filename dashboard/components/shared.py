import os
import streamlit as st
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Paths Configuration
ROOT_DIR    = Path(__file__).resolve().parents[2]
EXPORTS_DIR = ROOT_DIR / "data" / "exports"      # OLAP star-schema (preferred)
DATA_DIR    = ROOT_DIR / "data" / "oltp"          # OLTP fallback

# Supabase Configuration
load_dotenv(ROOT_DIR / ".env")
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
if _SUPABASE_URL and _SUPABASE_KEY:
    supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
else:
    supabase = None

@st.cache_data(show_spinner=False)
def load_supabase_table(table_name: str) -> pd.DataFrame:
    """Fetch all rows from a Supabase table."""
    if not supabase:
        raise Exception("Supabase credentials not configured in .env")
    try:
        # Fetch all rows from Supabase
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        raise Exception(f"Failed to load {table_name} from Supabase: {e}")

def get_data_path(filename: str) -> str:
    """
    Dynamically searches for CSV data files, prioritising the OLAP
    exports layer and falling back to OLTP when exports are unavailable.

    Search order:
      1. data/exports/           (OLAP warehouse exports — preferred)
      2. data/oltp/master/       (OLTP master tables)
      3. data/oltp/transactional/(OLTP transactional tables)
      4. data/oltp/              (direct)
      5. Recursive workspace search
    """
    # 1. Check OLAP exports (star-schema data) — exact filename match only
    export_path = EXPORTS_DIR / filename
    if export_path.exists():
        return str(export_path)

    # 2. Check OLTP master folder
    master_path = DATA_DIR / "master" / filename
    if master_path.exists():
        return str(master_path)

    # 3. Check OLTP transactional folder
    trans_path = DATA_DIR / "transactional" / filename
    if trans_path.exists():
        return str(trans_path)

    # 4. Check directly in root data/oltp
    direct_path = DATA_DIR / filename
    if direct_path.exists():
        return str(direct_path)

    # 5. Recursive search in data/oltp
    if DATA_DIR.exists():
        matches = list(DATA_DIR.rglob(filename))
        if matches:
            return str(matches[0])

    # 6. Search in the entire workspace
    matches = list(ROOT_DIR.rglob(filename))
    if matches:
        return str(matches[0])

    raise FileNotFoundError(f"File '{filename}' not found in '{EXPORTS_DIR}', '{DATA_DIR}', or workspace.")


# CSS Theme Injection
def inject_custom_css():
    """
    Injects global CSS into the Streamlit application to unify designs.
    Supports dynamic Light Mode & Dark Mode based on session state.
    """
    # Initialize default theme if not present
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
        
    theme = st.session_state["theme"]
    
    if theme == "dark":
        css_theme = """
        :root {
            --bg-page:         #0F172A;
            --bg-card:         #1E293B;
            --text-primary:    #F8FAFC;
            --text-secondary:  #94A3B8;
            --text-muted:      #64748B;
            --border-color:    #334155;
            --shadow-sm:       0 1px 3px rgba(0,0,0,.35);
            --shadow-md:       0 4px 6px rgba(0,0,0,.45);
        }
        
        /* Overrides Streamlit Native components in dark mode */
        div[data-testid="stMetricValue"] {
            color: #F8FAFC !important;
        }
        div[data-testid="stMetricLabel"] > div {
            color: #94A3B8 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            background-color: #1E293B !important;
            border-color: #334155 !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #94A3B8 !important;
        }
        .stTabs [aria-selected="true"] {
            color: #FFFFFF !important;
            background-color: var(--brand-primary) !important;
        }
        div[data-testid="stAppViewContainer"] {
            background-color: #0F172A !important;
        }
        .stAlert {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            color: #F8FAFC !important;
        }
        [data-testid="stDataFrame"] {
            background-color: #1E293B !important;
            border-color: #334155 !important;
        }
        .stMarkdown, p, span, h1, h2, h3, h4, h5, h6, label {
            color: #F8FAFC !important;
        }
        /* Fix sidebar input labels text color in dark mode */
        [data-testid="stSidebar"] label {
            color: #F1F5F9 !important;
        }
        """
    else:
        css_theme = """
        :root {
            --bg-page:         #F8FAFC;
            --bg-card:         #FFFFFF;
            --text-primary:    #0F172A;
            --text-secondary:  #475569;
            --text-muted:      #94A3B8;
            --border-color:    #E2E8F0;
            --shadow-sm:       0 1px 3px rgba(0,0,0,.08);
            --shadow-md:       0 4px 6px rgba(0,0,0,.07);
        }
        
        div[data-testid="stMetricValue"] {
            color: #0F172A !important;
        }
        div[data-testid="stMetricLabel"] > div {
            color: #475569 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            background-color: #FFFFFF !important;
            border-color: #E2E8F0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #475569 !important;
        }
        .stTabs [aria-selected="true"] {
            color: #FFFFFF !important;
            background-color: var(--brand-primary) !important;
        }
        div[data-testid="stAppViewContainer"] {
            background-color: #F8FAFC !important;
        }
        """

    # Global CSS injection
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500&display=swap');

        /* Brand palette colors */
        :root {{
            --brand-primary:   #2563EB;
            --brand-secondary: #7C3AED;
            --brand-accent:    #059669;
            --brand-warn:      #D97706;
            --brand-danger:    #DC2626;
            --text-on-dark:    #F1F5F9;
            --radius-card:     12px;
        }}

        {css_theme}

        /* Font styles */
        html, body, [class*="css"] {{
            font-family: 'DM Sans', sans-serif !important;
        }}

        /* Hide Streamlit Header & Footer */
        #MainMenu, footer, header {{
            visibility: hidden !important;
        }}

        /* Main Container Background */
        .stApp {{
            background-color: var(--bg-page) !important;
        }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
            border-right: 1px solid #334155 !important;
        }}
        [data-testid="stSidebar"] * {{
            color: var(--text-on-dark) !important;
        }}

        /* Sidebar Nav Links */
        [data-testid="stSidebarNav"] a {{
            border-radius: 8px !important;
            padding: 0.5rem 0.75rem !important;
            margin: 2px 0 !important;
            transition: background .15s ease !important;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background: rgba(255,255,255,0.08) !important;
        }}
        [data-testid="stSidebarNav"] a[aria-selected="true"] {{
            background: rgba(37,99,235,0.35) !important;
            border-left: 3px solid #2563EB !important;
        }}

        /* Metric Cards */
        [data-testid="stMetric"] {{
            background: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: var(--radius-card) !important;
            padding: 1.25rem 1.5rem !important;
            box-shadow: var(--shadow-sm) !important;
            transition: box-shadow .2s ease, transform .2s ease !important;
        }}
        [data-testid="stMetric"]:hover {{
            box-shadow: var(--shadow-md) !important;
            transform: translateY(-2px) !important;
        }}

        /* Plotly Charts rounding */
        .js-plotly-plot .plotly {{
            border-radius: var(--radius-card) !important;
        }}

        /* Custom Cards for page specific layouts */
        .kpi-card, .chart-card {{
            background: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: var(--radius-card) !important;
            padding: 1.25rem 1.5rem !important;
            box-shadow: var(--shadow-sm) !important;
            margin-bottom: 1.25rem !important;
            transition: box-shadow .2s ease, transform .2s ease !important;
        }}
        .kpi-card:hover, .chart-card:hover {{
            box-shadow: var(--shadow-md) !important;
        }}

        /* Dividers */
        hr {{
            border: none !important;
            border-top: 1px solid var(--border-color) !important;
            margin: 1.5rem 0 !important;
        }}

        /* Selectboxes & Inputs */
        [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div,
        [data-testid="stDateInput"] input {{
            border-radius: 8px !important;
        }}

        /* Dataframe / Table */
        [data-testid="stDataFrame"] {{
            border-radius: var(--radius-card) !important;
            overflow: hidden !important;
            border: 1px solid var(--border-color) !important;
        }}

        /* Tab styling */
        [data-baseweb="tab-list"] {{
            gap: 4px !important;
            padding: 4px !important;
            border-radius: 10px !important;
            border: 1px solid var(--border-color) !important;
        }}
        [data-baseweb="tab"] {{
            border-radius: 7px !important;
            padding: .4rem 1rem !important;
            font-weight: 500 !important;
            font-size: .9rem !important;
            transition: background .15s !important;
        }}

        /* Custom headings */
        .section-header {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 1.5rem 0 .75rem;
            padding-bottom: .4rem;
            border-bottom: 2px solid var(--brand-primary);
            display: inline-block;
        }}

        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: #94A3B8; border-radius: 3px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #64748B; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# Sidebar Layout & Theme Switcher
def add_sidebar_header():
    """
    Renders sidebar header (title) and the Light/Dark mode switcher button.
    Should be called inside 'with st.sidebar:' at the top.
    """
    # Header Logo/Title
    st.markdown(
        """
        <div style="padding: 1rem 0 1.5rem; text-align: center; border-bottom: 1px solid #334155; margin-bottom: 1rem;">
            <div style="font-size: 2.2rem; margin-bottom: .3rem;">👥</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #F1F5F9; letter-spacing: .02em;">
                HR Analytics
            </div>
            <div style="font-size: 0.75rem; color: #94A3B8; margin-top: .15rem;">
                People Intelligence Platform
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Custom Theme Toggle
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"
        
    theme = st.session_state["theme"]
    btn_emoji = "🌙" if theme == "light" else "☀️"
    btn_label = "Dark Mode" if theme == "light" else "Light Mode"
    
    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .25rem;'>Appearance</div>",
        unsafe_allow_html=True,
    )
    
    if st.button(f"{btn_emoji} Switch to {btn_label}", key="toggle_theme_btn"):
        st.session_state["theme"] = "dark" if theme == "light" else "light"
        st.rerun()
        
    st.markdown("---")


# Plotly Responsive Layout Dict
def get_plotly_theme() -> dict:
    """
    Returns the base Plotly layout dict, dynamically adapted to the active color mode.
    """
    is_dark = st.session_state.get("theme", "light") == "dark"
    bg = "rgba(0,0,0,0)"
    grid = "rgba(148,163,184,.15)"
    font_color = "#F1F5F9" if is_dark else "#0F172A"
    
    return dict(
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(family="DM Sans, sans-serif", color=font_color, size=11),
        hoverlabel=dict(
            bgcolor="#1E293B" if is_dark else "#FFFFFF",
            font_color="#F1F5F9" if is_dark else "#0F172A",
            bordercolor=grid,
            font_family="DM Sans, sans-serif",
        ),
    )


# Colors Palette
def get_palette() -> list:
    """
    Consistent default color palette for all charts.
    """
    return [
        "#2563EB",  # Royal Blue
        "#7C3AED",  # Purple
        "#059669",  # Emerald Green
        "#D97706",  # Amber
        "#DC2626",  # Red
        "#06B6D4",  # Cyan
        "#F97316",  # Orange
        "#EC4899",  # Pink
        "#84CC16"   # Lime
    ]
