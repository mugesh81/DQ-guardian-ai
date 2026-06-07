"""DQ Guardian AI — Premium Streamlit Dashboard.

Full redesign with dark glassmorphism theme, custom metric cards,
consistent Plotly charts, stage-by-stage progress, and polished UX
across all 8 pages.
"""

import json
import os
import time
from pathlib import Path

# Load .env file so GROQ_API_KEY and other vars are available in Streamlit
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on system environment

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yaml

from app.agent.agent_loop import AgentLoop
from app.agent.memory_engine import MemoryEngine
from app.agent.validator import ValidationEngine
from app.agent.auto_rules_generator import generate_rules_for_dataframe, profile_dataframe


# ──────────────────────────────────────────────────────────────────────────────
# Page configuration (MUST be first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DQ Guardian AI",
    page_icon=":shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Global Design System — Enterprise Light Theme
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
  @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css');

  /* ── Font Awesome icon sizing in headers ── */
  .hero-icon { color: #2563EB; margin-right: 8px; font-size: 18px; }
  .fa-nav    { margin-right: 6px; font-size: 13px; color: #2563EB; }

  /* ── Core Reset ── */
  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
  .stApp { background-color: #F8FAFC !important; }

  /* ── Main content area ── */
  .main .block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1400px !important;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
  }
  [data-testid="stSidebar"] * { color: #475569 !important; }
  [data-testid="stSidebar"] .stRadio > div > label {
    border-radius: 6px !important;
    padding: 8px 12px !important;
    margin: 2px 0 !important;
    transition: all 0.15s !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #475569 !important;
  }
  [data-testid="stSidebar"] .stRadio > div > label:hover {
    background: #F1F5F9 !important;
    color: #2563EB !important;
  }
  [data-testid="stSidebar"] .stRadio > div > label[data-baseweb="radio"] > div:first-child {
    background: #2563EB !important;
  }

  /* ── Metric Cards ── */
  .metric-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px 24px;
    transition: box-shadow 0.2s, border-color 0.2s;
    height: 100%;
  }
  .metric-card:hover {
    border-color: #93C5FD;
    box-shadow: 0 4px 12px rgba(37,99,235,0.08);
  }
  .metric-label {
    font-size: 11px;
    color: #64748B;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 8px;
    font-weight: 600;
  }
  .metric-value { font-size: 28px; font-weight: 700; color: #0F172A; line-height: 1.2; }
  .metric-delta { font-size: 12px; margin-top: 6px; font-weight: 500; }
  .delta-up   { color: #16A34A; }
  .delta-down { color: #DC2626; }
  .delta-neutral { color: #64748B; }

  /* ── Status Badges ── */
  .badge-pass     { background:#DCFCE7; color:#16A34A; border:1px solid #BBF7D0; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }
  .badge-fail     { background:#FEE2E2; color:#DC2626; border:1px solid #FECACA; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }
  .badge-critical { background:#FEE2E2; color:#B91C1C; border:1px solid #FCA5A5; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }
  .badge-high     { background:#FEF3C7; color:#D97706; border:1px solid #FDE68A; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }
  .badge-medium   { background:#FEF9C3; color:#CA8A04; border:1px solid #FEF08A; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }
  .badge-low      { background:#DBEAFE; color:#2563EB; border:1px solid #BFDBFE; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:600; display:inline-block; }

  /* ── Section headers ── */
  .section-header { font-size: 22px; font-weight: 700; color: #0F172A; margin: 0 0 4px; letter-spacing: -0.3px; }
  .section-sub    { font-size: 14px; color: #64748B; margin: 0 0 24px; }

  /* ── Page header hero area ── */
  .page-hero {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 24px;
  }
  .page-hero-title { font-size: 20px; font-weight: 700; color: #0F172A; margin: 0 0 4px; }
  .page-hero-desc  { font-size: 14px; color: #64748B; margin: 0; }

  /* ── Buttons ── */
  .stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: all 0.15s !important;
    border: 1px solid #E2E8F0 !important;
    color: #0F172A !important;
    background: #FFFFFF !important;
  }
  .stButton > button:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.12) !important;
  }
  .stButton > button[kind="primary"] {
    background: #2563EB !important;
    color: #FFFFFF !important;
    border-color: #2563EB !important;
  }
  .stButton > button[kind="primary"]:hover {
    background: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.25) !important;
  }

  /* ── Progress bar ── */
  .stProgress > div > div { background: #2563EB !important; border-radius: 4px !important; }
  .stProgress > div { background: #E2E8F0 !important; border-radius: 4px !important; }

  /* ── Expander ── */
  .streamlit-expanderHeader {
    font-weight: 600 !important;
    color: #0F172A !important;
    font-size: 14px !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
  }
  .streamlit-expanderContent {
    border: 1px solid #E2E8F0 !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    background: #FAFAFA !important;
  }

  /* ── Chat messages ── */
  [data-testid="stChatMessage"] {
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    background: #FFFFFF !important;
    margin-bottom: 8px !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    border: 2px dashed #CBD5E1 !important;
    border-radius: 12px !important;
    background: #F8FAFC !important;
    transition: border-color 0.2s !important;
  }
  [data-testid="stFileUploader"]:hover { border-color: #2563EB !important; }

  /* ── Alert boxes ── */
  [data-testid="stInfo"]    { border-radius: 8px; border-left: 3px solid #3B82F6; background: #EFF6FF; color: #1E40AF; }
  [data-testid="stWarning"] { border-radius: 8px; border-left: 3px solid #F59E0B; background: #FFFBEB; color: #92400E; }
  [data-testid="stError"]   { border-radius: 8px; border-left: 3px solid #DC2626; background: #FEF2F2; color: #991B1B; }
  [data-testid="stSuccess"] { border-radius: 8px; border-left: 3px solid #16A34A; background: #F0FDF4; color: #166534; }

  /* ── Dataframe ── */
  [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; border: 1px solid #E2E8F0 !important; }
  [data-testid="stDataFrame"] table { font-size: 13px !important; }
  [data-testid="stDataFrame"] thead { background: #F8FAFC !important; }
  [data-testid="stDataFrame"] thead th { color: #475569 !important; font-weight: 600 !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.04em; }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] { gap: 0; background: transparent; border-bottom: 2px solid #E2E8F0; }
  .stTabs [data-baseweb="tab"] { border-radius: 0 !important; font-weight: 500 !important; color: #64748B !important; padding: 10px 20px !important; font-size: 14px !important; background: transparent !important; border-bottom: 2px solid transparent !important; margin-bottom: -2px !important; }
  .stTabs [aria-selected="true"] { color: #2563EB !important; border-bottom: 2px solid #2563EB !important; font-weight: 600 !important; }

  /* ── Code blocks ── */
  .stCodeBlock { border-radius: 8px !important; border: 1px solid #E2E8F0 !important; }
  .stCodeBlock pre { font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important; }

  /* ── Text input / text area ── */
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea,
  .stSelectbox > div > div {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    font-size: 14px !important;
  }
  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
  }

  /* ── Selectbox ── */
  .stSelectbox [data-baseweb="select"] > div {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
  }

  /* ── Metrics (native st.metric) ── */
  [data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px 20px;
  }
  [data-testid="stMetricLabel"] > div { color: #64748B !important; font-size: 12px !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.05em; }
  [data-testid="stMetricValue"] > div { color: #0F172A !important; font-size: 26px !important; font-weight: 700 !important; }

  /* ── Checkbox ── */
  .stCheckbox > label { color: #0F172A !important; font-size: 14px !important; }

  /* ── Divider ── */
  hr { border-color: #E2E8F0 !important; margin: 20px 0 !important; }

  /* ── Status indicator chip ── */
  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
  }
  .status-chip.connected { background: #F0FDF4; color: #16A34A; border: 1px solid #BBF7D0; }
  .status-chip.warning   { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; }
  .status-chip.neutral   { background: #F8FAFC; color: #64748B; border: 1px solid #E2E8F0; }
  .status-chip.active    { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; }

  /* ── Hide Streamlit branding ── */
  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
  header    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────

# Plotly light theme helper
# ──────────────────────────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#475569", family="Inter", size=13),
    colorway=["#2563EB", "#16A34A", "#DC2626", "#F59E0B", "#7C3AED", "#0891B2", "#DB2777"],
    xaxis=dict(gridcolor="#F1F5F9", linecolor="#E2E8F0", tickfont=dict(color="#64748B", size=12)),
    yaxis=dict(gridcolor="#F1F5F9", linecolor="#E2E8F0", tickfont=dict(color="#64748B", size=12)),
    margin=dict(l=0, r=0, t=44, b=0),
    hoverlabel=dict(bgcolor="#0F172A", font_color="#F8FAFC", bordercolor="#1E293B"),
    title_font=dict(color="#0F172A", size=15, family="Inter"),
)

# ──────────────────────────────────────────────────────────────────────────────
# Core helpers
# ──────────────────────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = "", positive: bool = True) -> str:
    """Render a premium metric card as HTML."""
    if delta:
        arrow = "↑" if positive else "↓"
        cls = "delta-up" if positive else "delta-down"
        delta_html = f'<div class="metric-delta {cls}">{arrow} {delta}</div>'
    else:
        delta_html = ""
    return f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      {delta_html}
    </div>
    """


def badge(text: str, kind: str = "medium") -> str:
    return f'<span class="badge-{kind}">{text}</span>'


def query_groq(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """Query Groq API directly from Streamlit."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "WARNING: GROQ_API_KEY is not set. Please add it to your .env file."
    payload: dict = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"].strip()
        return f"API Error (HTTP {res.status_code}): {res.text[:200]}"
    except Exception as exc:
        return f"Request Error: {exc}"


def _run_sql_fix(sql_code: str, df: pd.DataFrame) -> tuple[bool, str, "pd.DataFrame | None"]:
    """Execute a SQL DML statement against an in-memory SQLite copy of *df*.

    The DataFrame is loaded as table ``data`` inside a transient SQLite database.
    Only UPDATE, INSERT, and DELETE statements are permitted — DROP, ALTER,
    CREATE, TRUNCATE are blocked before execution.

    Args:
        sql_code: The SQL statement string to execute (may contain comments).
        df: The source DataFrame to operate on.

    Returns:
        Tuple of (success: bool, message: str, result_df: DataFrame | None).
        *result_df* is None when execution fails.
    """
    import sqlite3 as _sqlite3
    import io as _io2

    # ── Strip comment lines and blank lines to get the executable statement ──
    executable_lines = [
        line for line in sql_code.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    clean_sql = " ".join(executable_lines).strip()

    if not clean_sql:
        return False, "No executable SQL statement found (only comments or blank lines).", None

    # ── Safety gate: block destructive DDL ──────────────────────────────────
    first_keyword = clean_sql.split()[0].upper()
    _ALLOWED_KEYWORDS = {"UPDATE", "INSERT", "DELETE"}
    _BLOCKED_PATTERNS = ["DROP ", "TRUNCATE ", "ALTER ", "CREATE ", "GRANT ", "REVOKE "]
    if first_keyword not in _ALLOWED_KEYWORDS:
        return (
            False,
            f"Blocked: only UPDATE / INSERT / DELETE are permitted. "
            f"Got: `{first_keyword}`. DDL statements are not allowed on in-memory data.",
            None,
        )
    for pat in _BLOCKED_PATTERNS:
        if pat in clean_sql.upper():
            return False, f"Blocked: dangerous SQL pattern detected: `{pat.strip()}`.", None

    try:
        # ── Load DataFrame into in-memory SQLite ──────────────────────────
        con = _sqlite3.connect(":memory:")
        df.to_sql("data", con, index=False, if_exists="replace")

        # ── Execute DML ──────────────────────────────────────────────────
        cursor = con.cursor()
        cursor.execute(clean_sql)
        rows_affected = cursor.rowcount
        con.commit()

        # ── Read result back ──────────────────────────────────────────────
        result_df = pd.read_sql("SELECT * FROM data", con)
        con.close()

        return True, f"✅ SQL executed successfully — **{rows_affected} row(s) affected**.", result_df

    except Exception as exc:
        return False, f"SQL execution error: {exc}", None



# ──────────────────────────────────────────────────────────────────────────────
# Singleton engines  (cached to avoid re-init on every rerun)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_memory() -> MemoryEngine:
    return MemoryEngine()


@st.cache_resource
def get_validator() -> ValidationEngine:
    return ValidationEngine()


memory = get_memory()
validator = get_validator()

# ──────────────────────────────────────────────────────────────────────────────
# Session state bootstrap
# ──────────────────────────────────────────────────────────────────────────────
_defaults = {
    "run_result":        None,
    "df":                None,
    "original_df":       None,   # preserved before any fix is applied
    "fixes_applied":     0,      # counter — drives Download Cleaned File button
    "validation_report": None,
    "current_run_id":    None,
    "chat_history":      [],
    "yaml_output":       None,
    "fixes":             {},
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 20px 16px 20px; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom: 6px;">
        <span style="display:inline-flex; align-items:center; justify-content:center; width:36px; height:36px;
                     background:linear-gradient(135deg,#2563EB,#1D4ED8); border-radius:8px; flex-shrink:0;">
          <i class="fa-solid fa-shield-halved" style="color:#fff; font-size:16px;"></i>
        </span>
        <div>
          <div style="font-size:16px; font-weight:700; color:#0F172A; letter-spacing:-0.3px;">DQ Guardian</div>
          <div style="font-size:10px; color:#94A3B8; text-transform:uppercase; letter-spacing:0.08em; font-weight:600;">AI Data Quality Platform</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        options=[
            "Dashboard",
            "Upload & Validate",
            "Validation Results",
            "Failure Explorer",
            "AI Suggestions",
            "Rule Generator",
            "AI Chat",
            "Memory Center",
        ],
        label_visibility="collapsed",
        key="nav_radio",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    pipeline_ok = bool(st.session_state.run_result)
    st.markdown(f"""
    <div style="padding: 12px 16px; background: #F8FAFC; border-radius: 8px; border: 1px solid #E2E8F0;">
      <div style="font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:10px;">System Status</div>
      <div style="display:flex; flex-direction:column; gap:6px;">
        <div style="display:flex; align-items:center; gap:8px; font-size:13px; color:#475569;">
          <span style="width:8px; height:8px; border-radius:50%; background:{'#16A34A' if groq_ok else '#DC2626'}; display:inline-block; flex-shrink:0;"></span>
          Groq API {'Connected' if groq_ok else 'Not configured'}
        </div>
        <div style="display:flex; align-items:center; gap:8px; font-size:13px; color:#475569;">
          <span style="width:8px; height:8px; border-radius:50%; background:#2563EB; display:inline-block; flex-shrink:0;"></span>
          SQLite Memory Active
        </div>
        <div style="display:flex; align-items:center; gap:8px; font-size:13px; color:#475569;">
          <span style="width:8px; height:8px; border-radius:50%; background:{'#16A34A' if pipeline_ok else '#CBD5E1'}; display:inline-block; flex-shrink:0;"></span>
          Pipeline {'Loaded' if pipeline_ok else 'No data'}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 1 — Dashboard
# ──────────────────────────────────────────────────────────────────────────────
if page == "Dashboard":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-chart-line hero-icon"></i>Platform Overview</div>
      <div class="page-hero-desc">Global data quality metrics and performance trends across all pipeline runs.</div>
    </div>
    """, unsafe_allow_html=True)

    stats = memory.get_memory_stats()
    runs_history = memory.get_run_history(limit=20)

    avg_score   = stats.get("avg_success_rate", 0.0)
    total_runs  = stats.get("total_runs", 0)
    total_fixes = stats.get("total_fixes", 0)
    is_healthy  = avg_score >= 80.0

    # Compute AI fix success rate (valid fixes / total fixes generated)
    try:
        with memory._get_connection() as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT COUNT(*) FROM generated_fixes WHERE fix_valid = 1")
            _valid = _cur.fetchone()[0] or 0
        fix_success_pct = round((_valid / total_fixes * 100), 1) if total_fixes > 0 else 0.0
    except Exception:
        fix_success_pct = 0.0

    # Compute total rows validated across all runs
    total_rows_validated = sum(r.get("total_rows", 0) for r in runs_history)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Avg Quality Score",  f"{avg_score:.1f}%", delta="", positive=is_healthy), unsafe_allow_html=True)
    c2.markdown(metric_card("Pipelines Run",      str(total_runs)), unsafe_allow_html=True)
    c3.markdown(metric_card("Fixes Generated",    str(total_fixes)), unsafe_allow_html=True)

    # ── AI Fix Success Rate card (replaces Most Common Failure) ────────────────
    if fix_success_pct >= 75:
        _fix_color, _fix_label = "#16A34A", "Excellent"
    elif fix_success_pct >= 50:
        _fix_color, _fix_label = "#F59E0B", "Moderate"
    elif total_fixes == 0:
        _fix_color, _fix_label = "#94A3B8", "No data"
    else:
        _fix_color, _fix_label = "#DC2626", "Low"

    c4.markdown(f"""
    <div class="metric-card">
      <div style="font-size:11px; font-weight:600; color:#64748B; text-transform:uppercase;
                  letter-spacing:0.07em; margin-bottom:10px;">AI Fix Success Rate</div>
      <div style="font-size:28px; font-weight:800; color:#0F172A; line-height:1; margin-bottom:6px;">
        {fix_success_pct:.0f}%
      </div>
      <div style="display:flex; align-items:center; gap:6px; margin-top:4px;">
        <span style="width:8px; height:8px; border-radius:50%; background:{_fix_color};
                     display:inline-block; flex-shrink:0;"></span>
        <span style="font-size:12px; color:{_fix_color}; font-weight:600;">{_fix_label}</span>
        <span style="font-size:11px; color:#94A3B8; margin-left:2px;">({_valid}/{total_fixes} valid)</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if runs_history:
        hist_df = pd.DataFrame(runs_history)

        col_left, col_right = st.columns(2)

        with col_left:
            if "timestamp" in hist_df.columns and "success_rate" in hist_df.columns:
                hist_sorted = hist_df.sort_values("timestamp")
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist_sorted["timestamp"],
                    y=hist_sorted["success_rate"],
                    mode="lines+markers",
                    line=dict(color="#2563EB", width=2.5),
                    marker=dict(size=7, color="#2563EB", line=dict(color="#FFFFFF", width=2)),
                    fill="tozeroy",
                    fillcolor="rgba(37,99,235,0.06)",
                    name="Quality Score",
                ))
                fig.update_layout(title="Quality Score Trend", **PLOTLY_LAYOUT)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_right:
            if "failed_checks" in hist_df.columns:
                fig2 = px.bar(
                    hist_df.tail(10),
                    x="filename",
                    y="failed_checks",
                    title="Failed Checks by Run",
                    color="failed_checks",
                    color_continuous_scale=["#DBEAFE", "#DC2626"],
                )
                fig2.update_layout(**PLOTLY_LAYOUT)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        st.markdown("<div style='font-size:13px; font-weight:600; color:#0F172A; margin: 8px 0 12px;'>Recent Runs</div>", unsafe_allow_html=True)
        display_cols = [c for c in ["timestamp", "filename", "total_rows", "passed_checks", "failed_checks", "success_rate"] if c in hist_df.columns]
        st.dataframe(hist_df[display_cols].head(10), use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:80px 20px; background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;">
          <div style="margin-bottom:16px;">
            <i class="fa-solid fa-shield-halved" style="font-size:52px; color:#2563EB; opacity:0.35;"></i>
          </div>
          <div style="font-size:18px; font-weight:700; color:#0F172A; margin-bottom:8px;">No pipelines yet</div>
          <div style="font-size:14px; color:#64748B;">Upload a dataset on the <strong>Upload &amp; Validate</strong> page to get started.</div>
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 2 — Upload & Validate
# ──────────────────────────────────────────────────────────────────────────────
elif page == "Upload & Validate":
    import io as _io

    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-upload hero-icon"></i>Upload &amp; Validate</div>
      <div class="page-hero-desc">Upload any CSV or Parquet dataset — the AI pipeline inspects your columns and auto-generates rules. No YAML required.</div>
    </div>
    """, unsafe_allow_html=True)

    AGENT_STAGES = [
        ("[1]", "Observing",   "Loading data and running all validation checks"),
        ("[2]", "Reasoning",   "Analyzing failures and checking memory for similar patterns"),
        ("[3]", "Acting",      "Generating AI-powered root cause analysis and fix suggestions"),
        ("[4]", "Validating",  "Testing fixes on data copies and measuring improvement"),
        ("[5]", "Learning",    "Saving results to memory for future reuse"),
        ("[6]", "Completing",  "Finalising agent run and generating report"),
    ]

    # ── File uploaders ────────────────────────────────────────────────────────
    col_u, col_r = st.columns(2)
    with col_u:
        uploaded_data = st.file_uploader(
            "📄 Dataset (CSV / Parquet) — **required**",
            type=["csv", "parquet"], key="upload_data",
        )
    with col_r:
        uploaded_rules = st.file_uploader(
            "📋 Rules File (YAML) — optional, AI generates rules if omitted",
            type=["yaml", "yml"], key="upload_rules",
        )

    # ── Immediately cache file bytes into session_state on upload ─────────────
    # This avoids seek() issues — Streamlit UploadedFile can only be read once
    # per render cycle. We cache bytes so Run button always has the data.
    if uploaded_data is not None:
        file_key = f"_cached_file_{uploaded_data.name}_{uploaded_data.size}"
        if st.session_state.get("_cached_file_key") != file_key:
            st.session_state["_cached_file_bytes"] = bytes(uploaded_data.getbuffer())
            st.session_state["_cached_file_name"]  = uploaded_data.name
            st.session_state["_cached_file_key"]   = file_key
    else:
        # Clear cache when file is removed
        for k in ("_cached_file_bytes", "_cached_file_name", "_cached_file_key"):
            st.session_state.pop(k, None)

    if uploaded_rules is not None:
        rules_key = f"_cached_rules_{uploaded_rules.name}_{uploaded_rules.size}"
        if st.session_state.get("_cached_rules_key") != rules_key:
            st.session_state["_cached_rules_bytes"] = bytes(uploaded_rules.getbuffer())
            st.session_state["_cached_rules_name"]  = uploaded_rules.name
            st.session_state["_cached_rules_key"]   = rules_key
    else:
        for k in ("_cached_rules_bytes", "_cached_rules_name", "_cached_rules_key"):
            st.session_state.pop(k, None)

    # ── Helper: read DataFrame from cached bytes ──────────────────────────────
    def _read_bytes_to_df(raw_bytes: bytes, filename: str) -> pd.DataFrame:
        """Parse CSV or Parquet bytes into a DataFrame with full error handling."""
        fname = filename.lower()
        if len(raw_bytes) == 0:
            raise ValueError(f"'{filename}' is empty (0 bytes). Please upload a valid file.")
        if fname.endswith(".parquet"):
            try:
                return pd.read_parquet(_io.BytesIO(raw_bytes))
            except Exception as e:
                raise ValueError(f"Could not read Parquet file '{filename}': {e}") from e
        elif fname.endswith(".csv"):
            try:
                df = pd.read_csv(
                    _io.BytesIO(raw_bytes),
                    skip_blank_lines=True,
                    on_bad_lines="warn",
                    encoding_errors="replace",
                )
            except pd.errors.EmptyDataError:
                raise ValueError(f"'{filename}' has no data rows (only headers or blank).")
            except Exception as e:
                raise ValueError(f"Could not parse CSV '{filename}': {e}") from e
            if df.empty:
                raise ValueError(f"'{filename}' was read but contains no data rows.")
            if len(df.columns) == 0:
                raise ValueError(f"'{filename}' has no columns — check the delimiter.")
            return df
        else:
            raise ValueError(
                f"Unsupported format '{filename}'. Upload a .csv or .parquet file."
            )

    # ── Schema profiling panel (shown immediately on upload) ──────────────────
    cached_bytes = st.session_state.get("_cached_file_bytes")
    cached_name  = st.session_state.get("_cached_file_name", "")

    if cached_bytes:
        try:
            preview_df = _read_bytes_to_df(cached_bytes, cached_name)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.markdown("""
            <div style='font-size:13px; font-weight:600; color:#0F172A; text-transform:uppercase;
                        letter-spacing:0.05em; margin-bottom:12px; padding-bottom:8px;
                        border-bottom:1px solid #E2E8F0;'>📋 Dataset Profile</div>
            """, unsafe_allow_html=True)

            pa, pb, pc, pd_ = st.columns(4)
            pa.markdown(metric_card("File Name",   cached_name), unsafe_allow_html=True)
            pb.markdown(metric_card("Rows",        f"{len(preview_df):,}"), unsafe_allow_html=True)
            pc.markdown(metric_card("Columns",     str(len(preview_df.columns))), unsafe_allow_html=True)
            null_cells = int(preview_df.isna().sum().sum())
            pd_.markdown(metric_card("Null Cells", f"{null_cells:,}"), unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            col_prof = st.columns(2)
            with col_prof[0]:
                st.markdown("<div style='font-size:13px; font-weight:600; color:#0F172A; margin-bottom:8px;'>Column Schema</div>", unsafe_allow_html=True)
                prof = profile_dataframe(preview_df)
                schema_rows = []
                for col_name, info in prof.items():
                    schema_rows.append({
                        "Column":  col_name,
                        "Dtype":   info["dtype"],
                        "Type":    info["inferred_type"],
                        "Null %":  f"{info['null_pct']}%",
                        "Unique":  info["unique_count"],
                        "Samples": ", ".join(info["sample_values"][:2]),
                    })
                st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)

            with col_prof[1]:
                st.markdown("<div style='font-size:13px; font-weight:600; color:#0F172A; margin-bottom:8px;'>Data Preview (first 8 rows)</div>", unsafe_allow_html=True)
                st.dataframe(preview_df.head(8), use_container_width=True, hide_index=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        except ValueError as profile_err:
            st.error(f"❌ **File Error:** {profile_err}")
            cached_bytes = None  # prevent Run button

    # ── Run button ────────────────────────────────────────────────────────────
    run_btn = st.button(
        "▶ Run AI Pipeline", type="primary", use_container_width=True,
        disabled=(not cached_bytes),
    )

    if run_btn and cached_bytes:
        # 1. Parse dataset from cached bytes (no seek() needed)
        try:
            df_uploaded = _read_bytes_to_df(cached_bytes, cached_name)
        except ValueError as read_err:
            st.error(f"❌ **Cannot read file:** {read_err}")
            st.stop()

        # 2. Save to disk for AgentLoop
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        data_path = data_dir / cached_name
        data_path.write_bytes(cached_bytes)

        # 3. Determine rules source
        rules_path_obj = None
        rules_dict_obj = None
        rules_bytes    = st.session_state.get("_cached_rules_bytes")
        rules_fname    = st.session_state.get("_cached_rules_name", "rules.yaml")

        if rules_bytes:
            rules_dir = Path("rules")
            rules_dir.mkdir(exist_ok=True)
            rules_path_obj = rules_dir / rules_fname
            rules_path_obj.write_bytes(rules_bytes)
            rules_source_label = f"📋 User-supplied rules: `{rules_fname}`"
        else:
            rules_source_label = "🤖 Auto-generated rules (Groq AI + heuristics)"

        # 4. Progress UI
        progress_bar   = st.progress(0)
        stage_display  = st.empty()
        detail_display = st.empty()
        error_display  = st.empty()

        def _advance(i: int, icon: str, name: str, detail: str) -> None:
            stage_display.markdown(f"**{icon} Stage {i+1}/{len(AGENT_STAGES)}: {name}**")
            detail_display.caption(detail)
            progress_bar.progress(min((i + 1) / len(AGENT_STAGES), 1.0))

        _advance(0, "🔍", "Observing", "Inspecting uploaded dataset structure…")

        # 5. Auto-generate rules
        if rules_dict_obj is None and rules_path_obj is None:
            _advance(1, "🤖", "Generating Rules",
                     "Calling Groq AI to create validation rules for your columns…")
            try:
                rules_dict_obj = generate_rules_for_dataframe(df_uploaded, use_ai=True)
                n_rules = len(rules_dict_obj.get("rules", []))
                st.info(
                    f"**{n_rules} validation rules auto-generated** for "
                    f"{len(df_uploaded.columns)} columns. {rules_source_label}"
                )
            except Exception as rg_err:
                st.warning(f"⚠️ Rule generation issue ({rg_err}). Using heuristics.")
                from app.agent.auto_rules_generator import _build_heuristic_rules, _sanitize_rules
                rules_dict_obj = {"rules": _sanitize_rules(_build_heuristic_rules(df_uploaded))}

        _advance(2, "⚙️", "Agent Running", "Analyzing failures and generating fixes. This may take a moment...")

        # 6. Run agent pipeline
        try:
            with st.spinner("Executing Data Quality Agent Loop..."):
                agent = AgentLoop(
                    data_path=data_path,
                    rules_path=rules_path_obj,
                    rules_dict=rules_dict_obj,
                    max_iterations=2,
                )
                result = agent.run()

            # Store all results in session_state
            st.session_state.run_result        = result
            st.session_state.current_run_id    = result["run_id"]
            st.session_state.df                = df_uploaded
            st.session_state.rules_dict        = rules_dict_obj
            st.session_state.last_filename     = cached_name

            # Build fresh validation report for Results page
            eng2 = ValidationEngine()
            if rules_dict_obj:
                eng2.load_rules_from_dict(rules_dict_obj)
            elif rules_path_obj:
                eng2.load_rules_from_yaml(rules_path_obj)
            st.session_state.validation_report = eng2.run_all_checks(
                df_uploaded, filename=cached_name
            )
            memory.save_run({
                **result,
                # Inject row count from the uploaded DataFrame
                "total_rows": len(df_uploaded),
            })

            stage_display.empty()
            detail_display.empty()
            progress_bar.progress(1.0)

            improvement = result.get("overall_improvement_percentage", 0)
            st.success(
                f"**Pipeline complete!** Quality improved by **{improvement:.1f}%** "
                f"| {rules_source_label}"
            )

            ka, kb, kc, kd = st.columns(4)
            ka.metric("Rules Evaluated", result.get("rules_evaluated", 0))
            kb.metric("Rules Failed",    result.get("rules_failed", 0))
            kc.metric("Fixes Generated", len(result.get("proposed_fixes", [])))
            kd.metric("Improvement",     f"{improvement:.1f}%")

            st.markdown("<br>", unsafe_allow_html=True)
            btn_col, _, _ = st.columns([1, 1, 1])
            def nav_to_results():
                st.session_state["nav_radio"] = "Validation Results"

            btn_col.button("View Validation Results →", type="primary", use_container_width=True, on_click=nav_to_results)

            st.markdown(
                "<p style='font-size:13px;color:#64748B;margin-top:8px;'>"
                "Or use the sidebar to navigate to <strong>Failure Explorer</strong> "
                "and <strong>AI Suggestions</strong>.</p>",
                unsafe_allow_html=True,
            )

        except Exception as exc:
            stage_display.empty()
            detail_display.empty()
            import traceback
            st.error(f"❌ **Pipeline failed:** {exc}")
            with st.expander("🔍 Full error traceback"):
                st.code(traceback.format_exc(), language="python")




# ──────────────────────────────────────────────────────────────────────────────
# PAGE 3 — Validation Results
# ──────────────────────────────────────────────────────────────────────────────
elif page == "Validation Results":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-clipboard-check hero-icon"></i>Validation Results</div>
      <div class="page-hero-desc">Full check-by-check quality report for the last pipeline run.</div>
    </div>
    """, unsafe_allow_html=True)

    rep = st.session_state.validation_report
    if rep is None:
        st.info("No validation report yet. Run a pipeline on the **Upload & Validate** page first.")
    else:
        # KPI row
        c1, c2, c3, c4 = st.columns(4)
        sr = rep.success_rate
        c1.markdown(metric_card("Total Checks",  str(rep.total_checks)), unsafe_allow_html=True)
        c2.markdown(metric_card("Passed",  str(rep.passed),  f"{sr:.1f}%",       sr >= 80), unsafe_allow_html=True)
        c3.markdown(metric_card("Failed",  str(rep.failed),  f"{100-sr:.1f}% fail rate", False), unsafe_allow_html=True)
        c4.markdown(metric_card("Success Rate", f"{sr:.1f}%", delta="", positive=sr >= 80), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Pie chart + table side by side
        col_chart, col_table = st.columns([1, 2])

        with col_chart:
            fig_pie = go.Figure(data=[go.Pie(
                labels=["Passed", "Failed"],
                values=[rep.passed, rep.failed],
                hole=0.62,
                marker=dict(colors=["#16A34A", "#DC2626"]),
                textfont=dict(color="#0F172A", size=13),
            )])
            fig_pie.update_layout(
                title="Pass / Fail Split",
                showlegend=True,
                legend=dict(font=dict(color="#475569", size=13)),
                **PLOTLY_LAYOUT,
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

        with col_table:
            rows = []
            for r in rep.results:
                status_label = "PASS" if r.status == "PASS" else ("FAIL" if r.status == "FAIL" else "ERR")
                sev_map = {"critical": "[C]", "high": "[H]", "medium": "[M]", "low": "[L]"}
                rows.append({
                    "Check":      r.check_name,
                    "Column":     r.column,
                    "Status":     f"{status_label}",
                    "Issues":     r.failure_count,
                    "Fail %":     f"{r.failure_percentage:.1f}%",
                    "Severity":   f"{sev_map.get(r.severity, '')} {r.severity.upper()}",
                })
            styled_df = pd.DataFrame(rows)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Severity bar chart
        sev_counts = {}
        for r in rep.results:
            if r.status == "FAIL":
                sev_counts[r.severity] = sev_counts.get(r.severity, 0) + 1
        if sev_counts:
            sev_df = pd.DataFrame(
                list(sev_counts.items()), columns=["Severity", "Count"]
            ).sort_values("Count", ascending=False)
            fig_sev = px.bar(
                sev_df, x="Severity", y="Count",
                title="Failures by Severity",
                color="Severity",
                color_discrete_map={"critical": "#DC2626", "high": "#F59E0B", "medium": "#EAB308", "low": "#2563EB"},
            )
            fig_sev.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_sev, use_container_width=True, config={"displayModeBar": False})


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 4 — Failure Explorer
# ──────────────────────────────────────────────────────────────────────────────
elif page == "Failure Explorer":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-magnifying-glass hero-icon"></i>Failure Explorer</div>
      <div class="page-hero-desc">Drill into individual check failures and inspect the exact rows causing issues.</div>
    </div>
    """, unsafe_allow_html=True)

    rep = st.session_state.validation_report
    if rep is None:
        st.info("No validation report yet. Run a pipeline first.")
    else:
        failed = [r for r in rep.results if r.status == "FAIL"]
        if not failed:
            st.success("No failures detected! Data is clean.")
        else:
            check_names = [r.check_name for r in failed]
            selected    = st.selectbox("Select a failed check to inspect:", check_names)

            chosen = next((r for r in failed if r.check_name == selected), None)
            if chosen:
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Failure Count",      chosen.failure_count)
                col_b.metric("Failure Rate",        f"{chosen.failure_percentage:.1f}%")
                col_c.metric("Severity",            chosen.severity.upper())

                st.markdown(f"**Target Column:** `{chosen.column}`")

                col_stats = chosen.column_stats
                if col_stats:
                    cs1, cs2, cs3, cs4 = st.columns(4)
                    cs1.metric("Null Count",   col_stats.get("null_count", 0))
                    cs2.metric("Unique Count", col_stats.get("unique_count", 0))
                    cs3.metric("Mean",         f"{col_stats.get('mean'):.2f}" if col_stats.get("mean") is not None else "N/A")
                    cs4.metric("Std Dev",      f"{col_stats.get('std'):.2f}"  if col_stats.get("std")  is not None else "N/A")

                if chosen.sample_bad_rows:
                    st.subheader(f"Sample Bad Rows (up to {min(10, len(chosen.sample_bad_rows))})")
                    st.dataframe(pd.DataFrame(chosen.sample_bad_rows[:10]), use_container_width=True, hide_index=True)
                    csv_export = pd.DataFrame(chosen.sample_bad_rows).to_csv(index=False)
                    st.download_button(
                        "Download Bad Rows CSV",
                        csv_export,
                        f"bad_rows_{selected}.csv",
                        "text/csv",
                    )
                else:
                    st.info("No sample bad rows captured for this check.")


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 5 — AI Suggestions
# ──────────────────────────────────────────────────────────────────────────────
elif page == "AI Suggestions":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-robot hero-icon"></i>AI-Generated Fix Suggestions</div>
      <div class="page-hero-desc">Review, approve, and apply AI-generated repair scripts for each validation failure.</div>
    </div>
    """, unsafe_allow_html=True)

    run = st.session_state.run_result
    df  = st.session_state.df

    if run is None:
        st.info("No pipeline run found. Go to **Upload & Validate** first.")
    else:
        fixes = run.get("proposed_fixes", [])
        if not fixes:
            st.success("✅ No fixes required — the dataset passed all checks!")
        else:
            for idx, fix in enumerate(fixes):
                check_name = fix.get("check_name", "Unknown")
                conf = fix.get("confidence_score", 0.0)
                # Normalise confidence to 0-1 range
                conf_pct = conf / 100.0 if conf > 1.0 else conf
                status = fix.get("status", "")
                valid = "FAILED" not in status

                hdr_icon = "[OK]" if valid else "[!]"
                with st.expander(f"{hdr_icon} **{check_name}** — Column: `{fix.get('column', '')}` — Confidence: {conf_pct*100:.0f}%", expanded=False):
                    col_info, col_conf = st.columns([3, 1])
                    with col_info:
                        st.info(f"**Root Cause:** {fix.get('root_cause', 'N/A')}")
                        if fix.get("explanation"):
                            st.warning(f"**Recommended Fix:** {fix.get('explanation', '')}")
                    with col_conf:
                        st.markdown("**Confidence**")
                        st.progress(float(min(conf_pct, 1.0)))
                        tier = "High" if conf_pct >= 0.75 else ("Medium" if conf_pct >= 0.5 else "Low")
                        st.caption(f"{tier} ({conf_pct*100:.0f}%)")

                    tab_py, tab_sql = st.tabs(["Python (Pandas) Fix", "SQL Fix"])
                    with tab_py:
                        code = fix.get("fix_code", "# No fix code generated")
                        if valid:
                            st.code(code, language="python")
                        else:
                            st.error("This fix failed validation and cannot be safely applied.")
                            st.code(code, language="python")

                    with tab_sql:
                        sql_code = fix.get("sql_fix")
                        if sql_code:
                            st.code(sql_code, language="sql")

                            if df is not None:
                                st.markdown(
                                    """
                                    <div style='font-size:12px; color:#64748B; margin-top:4px;'>
                                    Executes against an <strong>in-memory SQLite copy</strong> of your
                                    dataset (table <code>data</code>). Nothing is written to disk until
                                    you click <em>Download Cleaned File</em>.
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                sql_run_btn = st.button(
                                    "▶ Run SQL Fix",
                                    key=f"sql_run_{check_name}_{idx}",
                                    type="primary",
                                )
                                if sql_run_btn:
                                    with st.spinner("Executing SQL against in-memory copy…"):
                                        ok, msg, result_df = _run_sql_fix(sql_code, st.session_state.df)
                                    if ok and result_df is not None:
                                        # Preserve original before first mutation
                                        if st.session_state.fixes_applied == 0:
                                            st.session_state.original_df = st.session_state.df.copy()
                                        st.session_state.df = result_df
                                        st.session_state.fixes_applied += 1
                                        st.success(msg)
                                        st.markdown(
                                            f"<div style='font-size:12px;color:#64748B;'>Preview of updated dataset "
                                            f"({len(result_df):,} rows × {len(result_df.columns)} cols):</div>",
                                            unsafe_allow_html=True,
                                        )
                                        st.dataframe(result_df.head(8), use_container_width=True, hide_index=True)
                                    else:
                                        st.error(msg)
                        else:
                            st.code("-- SQL equivalent not available from agent loop.\n-- Use the MCP /tools/generate_fix endpoint for full SQL output.", language="sql")

                    if valid and df is not None:
                        reviewed = st.checkbox(
                            "I have reviewed this fix and accept responsibility for applying it.",
                            key=f"review_{check_name}_{idx}",
                        )
                        apply_btn = st.button(
                            "Apply Fix to In-Memory DataFrame",
                            key=f"apply_{check_name}_{idx}",
                            disabled=not reviewed,
                            type="primary",
                        )
                        if apply_btn and reviewed:
                            with st.spinner("Applying fix…"):
                                try:
                                    import numpy as _np
                                    _safe_builtins = {
                                        "str": str, "int": int, "float": float, "bool": bool,
                                        "list": list, "dict": dict, "set": set, "tuple": tuple,
                                        "len": len, "abs": abs, "round": round, "range": range,
                                        "min": min, "max": max, "sum": sum, "sorted": sorted,
                                        "enumerate": enumerate, "zip": zip, "isinstance": isinstance,
                                        "None": None, "True": True, "False": False,
                                    }
                                    clean_code = "\n".join(
                                        line for line in code.splitlines()
                                        if not line.strip().startswith("#")
                                        and not line.strip().startswith("import ")
                                        and not line.strip().startswith("from ")
                                    )
                                    _exec_globals = {
                                        "__builtins__": _safe_builtins,
                                        "pd": pd,
                                        "np": _np,
                                    }
                                    local_vars = {"df": st.session_state.df.copy()}
                                    exec(clean_code, _exec_globals, local_vars)  # nosec
                                    # Preserve original before first mutation
                                    if st.session_state.fixes_applied == 0:
                                        st.session_state.original_df = st.session_state.df.copy()
                                    st.session_state.df = local_vars.get("df", st.session_state.df)
                                    st.session_state.fixes_applied += 1
                                    st.success("Fix applied successfully! Dataset updated in memory.")
                                except Exception as exc:
                                    st.error(f"Failed to apply fix: {exc}")

        # ── Download Cleaned File panel ──────────────────────────────────────
        st.markdown("---")
        _fixes_done = st.session_state.get("fixes_applied", 0)
        _cleaned_df = st.session_state.get("df")
        _original_df = st.session_state.get("original_df")
        _last_fname = st.session_state.get("last_filename", "data.csv")
        _stem = Path(_last_fname).stem

        st.markdown(
            """<div style='font-size:15px; font-weight:700; color:#0F172A; margin-bottom:4px;'>
            📥 Export Dataset
            </div>
            <div style='font-size:13px; color:#64748B; margin-bottom:16px;'>
            Download the current in-memory dataset. Apply fixes above to get a cleaned version.
            </div>""",
            unsafe_allow_html=True,
        )

        dl_c1, dl_c2, dl_c3 = st.columns(3)

        if _cleaned_df is not None:
            _csv_bytes = _cleaned_df.to_csv(index=False).encode("utf-8")
            if _fixes_done > 0:
                dl_c1.download_button(
                    label=f"⬇ Download Cleaned File ({_fixes_done} fix{'es' if _fixes_done != 1 else ''} applied)",
                    data=_csv_bytes,
                    file_name=f"{_stem}_cleaned.csv",
                    mime="text/csv",
                    type="primary",
                    key="dl_cleaned_main",
                    use_container_width=True,
                )
            else:
                dl_c1.info("Apply at least one fix above to enable the cleaned file download.")

            dl_c2.download_button(
                label="⬇ Download Current CSV",
                data=_csv_bytes,
                file_name=f"{_stem}_current.csv",
                mime="text/csv",
                key="dl_current_main",
                use_container_width=True,
            )

        if _original_df is not None:
            _orig_bytes = _original_df.to_csv(index=False).encode("utf-8")
            dl_c3.download_button(
                label="⬇ Download Original (pre-fix)",
                data=_orig_bytes,
                file_name=f"{_stem}_original.csv",
                mime="text/csv",
                key="dl_original_main",
                use_container_width=True,
            )



# ──────────────────────────────────────────────────────────────────────────────
# PAGE 6 — Rule Generator
# ──────────────────────────────────────────────────────────────────────────────
elif page == "Rule Generator":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-gear hero-icon"></i>Rule Generator</div>
      <div class="page-hero-desc">Describe validation requirements in plain English and get production-ready YAML rules instantly.</div>
    </div>
    """, unsafe_allow_html=True)

    examples = [
        "Email must not be null and must match standard email format",
        "Revenue must be a positive number between 0 and 1,000,000",
        "Order date must be in YYYY-MM-DD format and not in the future",
        "Customer ID must be unique and not null",
    ]
    st.markdown("""
    <div style='font-size:12px; font-weight:600; color:#64748B; text-transform:uppercase;
                letter-spacing:0.06em; margin-bottom:10px;'>Example prompts</div>
    """, unsafe_allow_html=True)
    ex_cols = st.columns(len(examples))
    for col, ex in zip(ex_cols, examples):
        if col.button(ex[:30] + "…", key=f"ex_{ex[:15]}", help=ex):
            st.session_state["_nl_input"] = ex

    nl_input = st.text_area(
        "Describe your validation rules:",
        height=140,
        value=st.session_state.get("_nl_input", ""),
        placeholder="e.g. Revenue must be positive, email must be unique…",
        key="nl_area",
    )

    gen_btn = st.button("Generate YAML Rules", type="primary")

    if gen_btn:
        if not nl_input.strip():
            st.warning("Please enter a description.")
        else:
            with st.spinner("Generating YAML rules via Groq…"):
                sys_p = (
                    "You are a data quality assistant. Respond ONLY with valid YAML — "
                    "no markdown fences, no explanations. "
                    "CRITICAL: For any regex 'pattern' values use single-quoted YAML strings "
                    "(e.g.  pattern: '^[a-z]+$') NOT double-quoted strings, "
                    "so backslash characters are treated as literals. "
                    "You support a special check_type called 'cross_column_check' for rules that "
                    "compare two columns per row, e.g. 'end_date must be after start_date'. "
                    "For cross_column_check rules use this schema: "
                    "column: <left_col>, check_type: cross_column_check, "
                    "params: {left_col: <left>, right_col: <right>, operator: gt|gte|lt|lte|eq|ne, parse_dates: true/false}."
                )
                usr_p = f"""Convert to YAML data quality rules using this structure:
rules:
  - id: RULE_01
    name: rule_name
    column: target_column
    check_type: 'null_check'
    severity: 'high'
    params:
      min: 0
      max: 1000000
      pattern: '^[a-z]+$'
      expected_type: 'float64'
    description: English explanation

IMPORTANT: All regex pattern values MUST use single quotes. Never double-quote a pattern.

User request: {nl_input}"""
                raw_yaml = query_groq(sys_p, usr_p)
                # Detect error strings returned by query_groq (start with WARNING: or contain 'Error')
                if raw_yaml.startswith("WARNING:") or "Error" in raw_yaml[:60] or "not set" in raw_yaml:
                    st.error(raw_yaml)
                    st.session_state.yaml_output = None
                else:
                    # Strip any accidental markdown fences
                    if raw_yaml.startswith("```"):
                        lines = raw_yaml.splitlines()
                        raw_yaml = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                    raw_yaml = raw_yaml.strip()
                    # ── Sanitize double-quoted regex patterns → single-quoted ──────────
                    # LLMs often produce:  pattern: "^[a-zA-Z0-9._%+-]+@..."
                    # which is invalid YAML due to unknown escape characters like \. \w etc.
                    # Fix: convert every  pattern: "..."  to  pattern: '...'
                    import re as _re2
                    def _fix_dq_patterns(text: str) -> str:
                        def _replacer(m: "_re2.Match") -> str:
                            val = m.group(1)
                            # Escape any single quotes inside the value for YAML single-quoted style
                            val = val.replace("'", "''")
                            return f"pattern: '{val}'"
                        return _re2.sub(r'pattern:\s*"([^"]*?)"', _replacer, text)
                    raw_yaml = _fix_dq_patterns(raw_yaml)
                    st.session_state.yaml_output = raw_yaml

    if st.session_state.yaml_output:
        col_yaml, col_summary = st.columns(2)
        with col_yaml:
            st.markdown("<div style='font-size:13px; font-weight:600; color:#0F172A; margin-bottom:8px;'>Generated YAML Rules</div>", unsafe_allow_html=True)
            st.code(st.session_state.yaml_output, language="yaml")

        with col_summary:
            st.markdown("<div style='font-size:13px; font-weight:600; color:#0F172A; margin-bottom:8px;'>Parsed Rule Summary</div>", unsafe_allow_html=True)
            try:
                parsed = yaml.safe_load(st.session_state.yaml_output)
                if not isinstance(parsed, dict):
                    st.warning("Generated output is not a valid YAML dictionary.")
                else:
                    rules_list = parsed.get("rules", []) if parsed else []
                    if rules_list and isinstance(rules_list, list):
                        rule_df = pd.DataFrame([{
                            "Rule":     r.get("name", "—") if isinstance(r, dict) else "—",
                            "Column":   r.get("column", "—") if isinstance(r, dict) else "—",
                            "Type":     r.get("check_type", "—") if isinstance(r, dict) else "—",
                            "Severity": r.get("severity", "—") if isinstance(r, dict) else "—",
                        } for r in rules_list])
                        st.dataframe(rule_df, use_container_width=True, hide_index=True)
                        st.caption(f"**{len(rules_list)}** rules generated")
                    else:
                        st.warning("No rules found in generated YAML.")
            except Exception as e:
                # Don't crash — show a warning but still allow download/use
                st.warning(
                    f"Could not auto-parse YAML summary: `{type(e).__name__}`. "
                    "The YAML may still be valid — check the left panel. "
                    "You can still download and use it."
                )

        d1, d2, d3 = st.columns(3)
        d1.download_button("Download YAML", st.session_state.yaml_output, "custom_rules.yaml", "text/yaml")
        if d2.button("Save to Library"):
            memory.save_rule(nl_input, st.session_state.yaml_output)
            st.success("Rule set saved to memory library!")
        if d3.button("Use for Next Validation"):
            rules_dir = Path("rules")
            rules_dir.mkdir(exist_ok=True)
            (rules_dir / "custom_rules.yaml").write_text(st.session_state.yaml_output, encoding="utf-8")
            st.success("Saved as `rules/custom_rules.yaml` — select it on the Upload page.")


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 7 — AI Chat
# ──────────────────────────────────────────────────────────────────────────────
elif page == "AI Chat":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-comments hero-icon"></i>AI Copilot Chat</div>
      <div class="page-hero-desc">Ask anything about your data quality results. Get instant, contextual AI analysis.</div>
    </div>
    """, unsafe_allow_html=True)

    suggestions = [
        "Why did this file fail validation?",
        "Which column has the most issues?",
        "Explain the revenue range check",
        "How can I improve data quality?",
        "What are the critical failures?",
    ]

    st.markdown("""
    <div style='font-size:12px; font-weight:600; color:#64748B; text-transform:uppercase;
                letter-spacing:0.06em; margin-bottom:10px;'>Quick questions</div>
    """, unsafe_allow_html=True)
    sug_cols = st.columns(len(suggestions))
    for col, sug in zip(sug_cols, suggestions):
        if col.button(sug[:22] + "…", key=f"sug_{sug[:15]}", help=sug):
            st.session_state.chat_history.append({"role": "user", "content": sug})
            st.rerun()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask anything about your data…")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analysing your data…"):
                rep = st.session_state.validation_report
                run = st.session_state.run_result
                ctx_parts = []
                if rep:
                    ctx_parts.append(f"Validation Report: {rep.total_checks} checks, {rep.passed} passed, {rep.failed} failed, {rep.success_rate:.1f}% success rate on file '{rep.filename}'.")
                    failed_desc = "; ".join(
                        f"{r.check_name} on '{r.column}' ({r.failure_count} rows, {r.severity} severity)"
                        for r in rep.results if r.status == "FAIL"
                    )
                    if failed_desc:
                        ctx_parts.append(f"Failed checks: {failed_desc}")
                if run:
                    ctx_parts.append(f"Agent proposed {len(run.get('proposed_fixes', []))} fixes with {run.get('overall_improvement_percentage', 0):.1f}% overall improvement.")

                context = " | ".join(ctx_parts) if ctx_parts else "No pipeline data loaded yet."
                sys_p = "You are DQ Guardian AI, an expert data quality assistant. Answer concisely and reference specific column names and metrics when available."
                usr_p = f"Context: {context}\n\nUser question: {prompt}"
                answer = query_groq(sys_p, usr_p)
                st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    if st.session_state.chat_history:
        if st.button("Clear Chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# PAGE 8 — Memory Center
# ──────────────────────────────────────────────────────────────────────────────
elif page == "Memory Center":
    st.markdown("""
    <div class="page-hero">
      <div class="page-hero-title"><i class="fa-solid fa-brain hero-icon"></i>Memory Center</div>
      <div class="page-hero-desc">Browse the AI fix knowledge base, historical run database, and saved rule library.</div>
    </div>
    """, unsafe_allow_html=True)

    stats = memory.get_memory_stats()
    runs  = memory.get_run_history(limit=50)

    ms1, ms2, ms3 = st.columns(3)
    ms1.markdown(metric_card("Total Runs",      str(stats.get("total_runs", 0))), unsafe_allow_html=True)
    ms2.markdown(metric_card("Total Fixes",     str(stats.get("total_fixes", 0))), unsafe_allow_html=True)
    ms3.markdown(metric_card("Avg Quality",     f"{stats.get('avg_success_rate', 0):.1f}%"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_runs, tab_mem, tab_rules = st.tabs(["Run History", "Fix Memory", "Rule Library"])

    with tab_runs:
        if runs:
            runs_df = pd.DataFrame(runs)
            # Prefer these columns in order; show all available ones (never blank)
            preferred = ["timestamp", "filename", "total_rows", "passed_checks",
                         "failed_checks", "success_rate", "duration_seconds", "iterations"]
            display = [c for c in preferred if c in runs_df.columns]
            if not display:
                display = list(runs_df.columns)  # fallback: show everything
            st.dataframe(
                runs_df[display].reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Export Run History",
                runs_df.to_csv(index=False),
                "run_history.csv",
                "text/csv",
                key="export_runs",
            )
        else:
            st.markdown("""
            <div style="text-align:center; padding:60px 20px; background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;">
              <div style="margin-bottom:16px;">
                <i class="fa-solid fa-brain" style="font-size:48px; color:#2563EB; opacity:0.3;"></i>
              </div>
              <div style="font-size:18px; font-weight:600; color:#0F172A; margin-bottom:8px;">Memory is empty</div>
              <div style="font-size:14px; color:#64748B;">Run a validation pipeline to start building your fix memory bank.</div>
            </div>
            """, unsafe_allow_html=True)

    with tab_mem:
        query = st.text_input("Search fix memory:", placeholder="e.g. null, revenue, email — leave blank to see all")
        mem_results = memory.search_memory(query) if query else memory.search_memory("")
        if mem_results:
            for rec in mem_results[:20]:
                total_attempts = rec.get("success_count", 0) + rec.get("fail_count", 0)
                sr = rec["success_count"] / total_attempts * 100 if total_attempts > 0 else 0
                sr_color = "#16A34A" if sr >= 75 else ("#F59E0B" if sr >= 50 else "#DC2626")
                with st.expander(f"Fix: {rec.get('failure_pattern', 'Unknown')} — {sr:.0f}% success rate"):
                    col_l, col_r = st.columns(2)
                    with col_l:
                        st.markdown(
                            f"<div style='margin-bottom:8px;'>"
                            f"<div style='font-size:11px; font-weight:600; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:3px;'>Root Cause</div>"
                            f"<div style='font-size:14px; color:#0F172A;'>{rec.get('root_cause', 'N/A')}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Success", rec.get('success_count', 0))
                        c2.metric("Failures", rec.get('fail_count', 0))
                        c3.metric("Avg Improvement", f"{rec.get('avg_improvement', 0):.1f}%")
                        st.caption(f"Last seen: {rec.get('last_seen', 'N/A')}")
                    with col_r:
                        if rec.get("successful_fix"):
                            st.markdown("<div style='font-size:12px; font-weight:600; color:#0F172A; margin-bottom:4px;'>Best Fix Script</div>", unsafe_allow_html=True)
                            st.code(rec["successful_fix"], language="python")
        else:
            st.info("No memory records found. Run more pipelines to build the fix knowledge base.")

    with tab_rules:
        all_rules = memory.get_all_rules()
        if all_rules:
            for _rule_idx, rule_rec in enumerate(all_rules):
                # Use a unique label: truncated NL input + creation date suffix
                nl_label = rule_rec.get('natural_language_input', 'Rule') or 'Rule'
                created  = rule_rec.get('created_at', '')[:10]  # YYYY-MM-DD
                rule_id_short = rule_rec.get('id', f'rule{_rule_idx}')[:8]
                expander_label = f"Rule [{_rule_idx+1}] {nl_label[:60]}{'...' if len(nl_label) > 60 else ''} — {created}"
                with st.expander(expander_label):
                    st.code(rule_rec.get("yaml_output", ""), language="yaml")
                    col_meta, col_dl = st.columns(2)
                    col_meta.caption(
                        f"ID: {rule_id_short} | "
                        f"Created: {rule_rec.get('created_at', 'N/A')} | "
                        f"Used: {rule_rec.get('times_used', 0)} times"
                    )
                    col_dl.download_button(
                        "Download",
                        rule_rec.get("yaml_output", ""),
                        f"rule_{rule_id_short}.yaml",
                        "text/yaml",
                        key=f"dl_{rule_id_short}_{_rule_idx}",
                    )

            if st.checkbox("I understand this will permanently delete all history."):
                st.markdown("""
                <div style='background:#FEF2F2; border:1px solid #FECACA; border-radius:8px; padding:12px 16px; margin:8px 0;'>
                  <div style='font-size:13px; font-weight:600; color:#991B1B; margin-bottom:4px;'>Danger Zone</div>
                  <div style='font-size:12px; color:#B91C1C;'>This will permanently erase all run history, fix memory, and saved rules. This cannot be undone.</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Wipe Database", type="primary"):
                    with memory._get_connection() as conn:
                        cur = conn.cursor()
                        for tbl in ["validation_runs", "validation_failures", "generated_fixes", "agent_memory", "generated_rules"]:
                            cur.execute(f"DELETE FROM {tbl}")  # nosec
                        conn.commit()
                    st.success("Database wiped successfully.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("No rules in library yet. Use the Rule Generator page to create and save YAML rules.")
