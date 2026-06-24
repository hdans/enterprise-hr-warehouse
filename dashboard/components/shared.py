import os
import socket
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
_supabase_init_error = None


class DataLoadError(Exception):
    """Raised when dashboard data cannot be loaded from the configured source."""


_ICON_PATHS = {
    "alert": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "bar-chart": '<path d="M3 3v18h18"/><path d="M7 15v2"/><path d="M12 9v8"/><path d="M17 5v12"/>',
    "briefcase": '<path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1"/><path d="M3 7h18v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 13h18"/><path d="M10 13v2h4v-2"/>',
    "building": '<path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 7h1"/><path d="M14 7h1"/><path d="M9 11h1"/><path d="M14 11h1"/><path d="M9 15h1"/><path d="M14 15h1"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/>',
    "check": '<path d="m20 6-11 11-5-5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>',
    "filter": '<path d="M22 3H2l8 9.46V19l4 2v-8.54Z"/>',
    "gauge": '<path d="M12 14l4-4"/><path d="M4.93 19a10 10 0 1 1 14.14 0"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "layout": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 7.5A9 9 0 1 1 12 3Z"/>',
    "package": '<path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
    "pie-chart": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10Z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>',
    "settings": '<path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"/><path d="M19.43 12.98c.04-.32.07-.65.07-.98s-.02-.66-.07-.98l2.11-1.65-2-3.46-2.49 1a7.8 7.8 0 0 0-1.69-.98L15 3h-4l-.36 2.93c-.6.23-1.16.55-1.69.98l-2.49-1-2 3.46 2.11 1.65a7.93 7.93 0 0 0 0 1.96l-2.11 1.65 2 3.46 2.49-1c.53.43 1.09.75 1.69.98L11 21h4l.36-2.93c.6-.23 1.16-.55 1.69-.98l2.49 1 2-3.46-2.11-1.65Z"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "table": '<path d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 10h18"/><path d="M10 3v18"/>',
    "trending-down": '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "trending-up": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "wallet": '<path d="M19 7V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/><path d="M3 7h16a2 2 0 0 1 2 2v4h-5a2 2 0 0 1 0-4h5"/>',
}


def icon_svg(name: str, size: int = 20, color: str = "currentColor", stroke_width: float = 2) -> str:
    """Return an inline SVG icon using a compact Lucide-style stroke system."""
    path = _ICON_PATHS.get(name, _ICON_PATHS["info"])
    return (
        f'<svg class="ui-icon ui-icon-{name}" xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def icon_label(icon_name: str, label: str, color: str = "currentColor", size: int = 16) -> str:
    """Return HTML for an inline icon plus text label."""
    return (
        f'<span class="icon-label" style="display:inline-flex;align-items:center;gap:.35rem;">'
        f'{icon_svg(icon_name, size=size, color=color)}<span>{label}</span></span>'
    )


def _mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return "not set"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"


def _supabase_host() -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(_SUPABASE_URL).hostname or ""
    except Exception:
        return ""


if _SUPABASE_URL and _SUPABASE_KEY:
    try:
        supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    except Exception as e:
        supabase = None
        _supabase_init_error = str(e)
else:
    supabase = None

@st.cache_data(show_spinner=False)
def load_supabase_table(table_name: str) -> pd.DataFrame:
    """Fetch all rows from a Supabase table."""
    if not supabase:
        if _supabase_init_error:
            raise DataLoadError(f"Supabase client could not be initialized: {_supabase_init_error}")
        raise DataLoadError("Supabase credentials are not configured in .env")
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        raise DataLoadError(f"Failed to load {table_name} from Supabase: {e}") from e


def get_supabase_diagnostics() -> dict:
    """Return non-sensitive Supabase configuration diagnostics for UI/debugging."""
    host = _supabase_host()
    dns_ok = None
    dns_error = None
    if host:
        try:
            socket.getaddrinfo(host, 443)
            dns_ok = True
        except Exception as e:
            dns_ok = False
            dns_error = str(e)

    return {
        "url_set": bool(_SUPABASE_URL),
        "key_set": bool(_SUPABASE_KEY),
        "url": _SUPABASE_URL or "not set",
        "host": host or "not detected",
        "key_preview": _mask_secret(_SUPABASE_KEY),
        "client_ready": supabase is not None,
        "client_init_error": _supabase_init_error,
        "dns_ok": dns_ok,
        "dns_error": dns_error,
    }


def render_data_load_error(error: object):
    """Show a clear, non-crashing data-source error message in Streamlit."""
    message = str(error)
    diag = get_supabase_diagnostics()

    st.error(
        "**Data could not be loaded from Supabase.**\n\n"
        f"`{message}`"
    )

    with st.expander("Connection diagnostics", expanded=True):
        st.write(f"Supabase URL configured: `{diag['url_set']}`")
        st.write(f"Supabase key configured: `{diag['key_set']}`")
        st.write(f"Supabase URL: `{diag['url']}`")
        st.write(f"Supabase host: `{diag['host']}`")
        st.write(f"Supabase key preview: `{diag['key_preview']}`")
        st.write(f"Supabase client ready: `{diag['client_ready']}`")
        if diag["client_init_error"]:
            st.write(f"Client initialization error: `{diag['client_init_error']}`")
        if diag["dns_ok"] is not None:
            st.write(f"DNS lookup works: `{diag['dns_ok']}`")
        if diag["dns_error"]:
            st.write(f"DNS error: `{diag['dns_error']}`")

    st.info(
        "Check `.env`, internet/VPN/proxy/DNS access, and the Supabase project URL. "
        "The dashboard page is still open, but charts are hidden until data can be loaded."
    )

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
        f"""
        <div style="padding: 1rem 0 1.5rem; text-align: center; border-bottom: 1px solid #334155; margin-bottom: 1rem;">
            <div style="display:flex;justify-content:center;margin-bottom:.55rem;">
                {icon_svg("users", size=34, color="#93C5FD")}
            </div>
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
    btn_icon = "moon" if theme == "light" else "sun"
    btn_label = "Dark Mode" if theme == "light" else "Light Mode"
    
    st.markdown(
        "<div style='font-size:.7rem;font-weight:700;letter-spacing:.1em;"
        "text-transform:uppercase;color:#64748B;padding:0 .5rem .25rem;'>Appearance</div>",
        unsafe_allow_html=True,
    )
    
    if st.button(f"Switch to {btn_label}", key="toggle_theme_btn"):
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
