"""
Aruvi · NCF 2023-Aligned Pedagogical Platform
Streamlit prototype shell — UI only, no API calls wired.

Layout
  Fixed top bar : [Logo + wordmark/slogan row] left  |  Teacher/Principal pills centre  |  empty right
  Left sidebar  : Grade · Subject · contextual inputs · user footer
  Right workspace: tab content for the active role
"""

import base64
import json
from pathlib import Path

import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────

PROJECT_ROOT  = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")
MAPPINGS_DIR  = PROJECT_ROOT / "mirror/chapters/social_sciences/grade_vii/mappings"
SUMMARIES_DIR = PROJECT_ROOT / "mirror/chapters/social_sciences/grade_vii/summaries"
MISC_DIR      = PROJECT_ROOT / "miscellaneous"
LOGO_PATH     = MISC_DIR / "aruvi_logo-transparent.png"

DURATION_OPTIONS = [30, 35, 40, 45, 50, 60]
WEIGHT_LABEL     = {3: "Central", 2: "Substantive", 1: "Present"}

GRADES = [
    "Grade III", "Grade IV", "Grade V", "Grade VI",
    "Grade VII", "Grade VIII", "Grade IX", "Grade X",
]

SUBJECTS = [
    "English", "EVS", "Mathematics", "Science",
    "Second Language", "Social Science",
]

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Aruvi",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Role from URL ─────────────────────────────────────────────────────────────

query = st.query_params

if "role" in query:
    st.session_state.role = query["role"]

# Default role on first load
if "role" not in st.session_state:
    st.session_state.role = "Teacher"

# ── Image helpers ─────────────────────────────────────────────────────────────

def _img_src(path: Path) -> str:
    """Load a PNG file as a base64 data URI. Returns '' if the file is missing."""
    try:
        b64 = base64.b64encode(path.read_bytes()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


LOGO_SRC    = _img_src(LOGO_PATH)
GRADE_SRC   = _img_src(MISC_DIR / "grade.png")
SUBJECT_SRC = _img_src(MISC_DIR / "subject.png")
CHAPTER_SRC = _img_src(MISC_DIR / "chapter.png")
PERIOD_SRC  = _img_src(MISC_DIR / "period.png")


# ── CSS + JS ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>

/* ═══════════════════════════════════════════════════
   FIXED TOP NAV BAR
   Change 1: width 100vw, left 0 — spans full viewport
   including over the sidebar. overflow:visible ensures
   logo/brand are never clipped regardless of sidebar state.
   ═══════════════════════════════════════════════════ */
.aruvi-topnav {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    z-index: 99999 !important;
    background: #f5f3ef;
    border-bottom: 1px solid #d9d6d0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 1.5rem;
    box-sizing: border-box;
    min-height: 72px;
    overflow: visible;
}

/* Left: logo + brand — never clip or hide */
.topnav-left {
    flex: 0 0 auto;
    min-width: 180px;
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
    overflow: visible;
}
.topnav-left img {
    width: 56px;
    height: 56px;
    object-fit: contain;
    display: block;
    background: transparent;
    flex-shrink: 0;
}
/* Brand: wordmark above slogan */
.topnav-brand {
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
    overflow: visible;
    white-space: nowrap;
}
.topnav-wordmark {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #5a5754;
    white-space: nowrap;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    line-height: 1;
}
.topnav-slogan {
    font-size: 0.55rem;
    font-weight: 400;
    letter-spacing: 0.01em;
    color: #5a5754;
    white-space: nowrap;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    line-height: 1;
}

/* Centre: pill toggle */
.topnav-center {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Right: empty balancer */
.topnav-right {
    flex: 0 0 auto;
    min-width: 180px;
}

/* Pill container */
.aruvi-topnav-inner {
    display: inline-flex;
    align-items: center;
    background: #e8e5e0;
    border-radius: 999px;
    padding: 3px 4px;
    gap: 2px;
}

/* Individual pills */
.aruvi-pill {
    display: inline-block;
    padding: 0.3rem 1.45rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 500;
    letter-spacing: 0.01em;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    color: #6b6866;          /* warm grey matching logo palette */
    background: transparent;
    border: none;
    text-decoration: none !important;
    user-select: none;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}
.aruvi-pill:hover,
.aruvi-pill:focus,
.aruvi-pill:visited,
.aruvi-pill:active,
.aruvi-pill:link {
    text-decoration: none !important;
}
.aruvi-pill:hover { color: #2c2a27; background: rgba(0,0,0,0.04); }
.aruvi-pill.active {
    background: #ffffff;
    color: #2c2a27;          /* same dark tone as topnav wordmark */
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
}


/* ═══════════════════════════════════════════════════
   HIDDEN ADD-BLOCK BUTTON  (triggered by JS via ⊕ icon)
   ═══════════════════════════════════════════════════ */
.st-key-add_block_icon {
    display: none !important;
}

/* ═══════════════════════════════════════════════════
   PUSH CONTENT DOWN below the fixed top nav
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 5.8rem !important;
    display: flex !important;
    flex-direction: column !important;
    min-height: 100vh !important;
    box-sizing: border-box !important;
}
.main .block-container {
    padding: 5.8rem 3rem 2rem 2.5rem !important;
    max-width: none;
}
header[data-testid="stHeader"] {
    background: rgba(0,0,0,0) !important;
    top: 72px !important;
}

/* ═══════════════════════════════════════════════════
   GLOBAL
   ═══════════════════════════════════════════════════ */
html, body, .stApp {
    background-color: #f5f3ef;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR — must render below our topnav
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background-color: #eeece8;
    border-right: 1px solid #d9d6d0;
    z-index: 100 !important;
}

/* ═══════════════════════════════════════════════════
   PREVENT STACKING-CONTEXT BREAKS
   Streamlit may apply CSS transforms to app containers
   for animations. Any ancestor with transform:non-none
   makes position:fixed children act like position:absolute,
   breaking left:0/width:100vw on the topnav.
   Force transforms off on every Streamlit wrapper.
   ═══════════════════════════════════════════════════ */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"],
.main {
    transform: none !important;
    will-change: auto !important;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR FIELD LABEL ROW  (icon + uppercase name)
   Rendered above each selectbox via st.markdown.
   ═══════════════════════════════════════════════════ */
.sidebar-field-label {
    display: flex;
    align-items: center;
    gap: 0.38rem;
    margin-top: 0.85rem;
    margin-bottom: 0.05rem;
}
.field-icon {
    width: 15px;
    height: 15px;
    object-fit: contain;
    opacity: 0.72;
    flex-shrink: 0;
}
.field-label-text {
    font-size: 0.70rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a5754;
    line-height: 1;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR SELECTBOX: flat / no-box style
   The box border and background are stripped away.
   Value sits flush-left directly below the label row.
   A › chevron (via ::after) signals the dropdown.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
    position: relative !important;
    margin-top: 0 !important;
    margin-bottom: 0.5rem !important;
}
/* Strip box chrome from the BaseUI select control */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 1.2rem 0 0 !important;
    min-height: 28px !important;
}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="base-input"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}
/* Value text: flush left, medium-dark grey */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="value"],
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div > div > div {
    color: #3d3b38 !important;
    font-size: 0.84rem !important;
    padding: 0 !important;
    line-height: 1.4 !important;
}
/* › chevron via pseudo-element, right-aligned */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] {
    position: relative !important;
}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"]::after {
    content: '›';
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    color: #9c9693;
    font-size: 1.0rem;
    pointer-events: none;
    line-height: 1;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR SECTION LABEL
   ═══════════════════════════════════════════════════ */
.sect-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #9c9693;
    margin: 1rem 0 0.35rem 0;
    display: flex;
    align-items: center;
    gap: 0.35rem;
}

/* ═══════════════════════════════════════════════════
   PERIOD ⊕ ICON  (clickable, adds a period block)
   ═══════════════════════════════════════════════════ */
.period-icon {
    width: 20px;
    height: 20px;
    object-fit: contain;
    cursor: pointer;
    opacity: 0.65;
    transition: opacity 0.15s;
    flex-shrink: 0;
    vertical-align: middle;
}
.period-icon:hover { opacity: 1.0; }
/* Text fallback when PNG is missing */
.period-icon-text {
    font-size: 1.0rem;
    line-height: 1;
    cursor: pointer;
    color: #9c9693;
    user-select: none;
    transition: color 0.15s, opacity 0.15s;
    opacity: 0.75;
}
.period-icon-text:hover { color: #c96442; opacity: 1.0; }

/* ═══════════════════════════════════════════════════
   PERIOD BLOCK COLUMN HEADERS  (Change 4)
   Match .sect-label style but zero top-margin for first row
   ═══════════════════════════════════════════════════ */
.block-col-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #9c9693;
    margin: 0.5rem 0 0.15rem 0;
    line-height: 1;
    display: block;
}

/* ═══════════════════════════════════════════════════
   REMOVE DROPDOWN ARROW from all sidebar selectboxes
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [data-baseweb="select"] svg {
    display: none !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] [class*="arrow"],
section[data-testid="stSidebar"] [data-baseweb="select"] [class*="Arrow"],
section[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stIcon"] {
    display: none !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div > div:last-child svg,
section[data-testid="stSidebar"] [data-baseweb="select"] [class*="indicator"] {
    display: none !important;
}

/* ═══════════════════════════════════════════════════
   WORKSPACE TABS  (inner tab strip)
   ═══════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #d9d6d0 !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #9c9693 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 0.5rem 1.4rem 0.45rem !important;
    font-size: 0.82rem !important;
    font-weight: 400 !important;
    letter-spacing: 0.01em;
    margin-bottom: -1px !important;
    transition: color 0.12s;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #5a5754 !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #1a1a1a !important;
    border-bottom: 2px solid #1a1a1a !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 1.5rem 0 0 0 !important;
}

/* ═══════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════ */
div.stButton > button {
    background: transparent;
    border: 1px solid #d9d6d0;
    color: #5a5754;
    border-radius: 5px;
    font-size: 0.82rem;
    transition: border-color 0.15s, color 0.15s, background 0.15s;
}
div.stButton > button:hover {
    border-color: #c96442;
    color: #1a1a1a;
    background: rgba(201, 100, 66, 0.05);
}
div.stButton > button[kind="primary"] {
    background: #c96442 !important;
    border: none !important;
    color: #fff !important;
    font-weight: 500 !important;
}
div.stButton > button[kind="primary"]:hover {
    background: #d97050 !important;
}
div.stButton > button[disabled],
div.stButton > button:disabled {
    background: #eeece8 !important;
    border: 1px solid #d9d6d0 !important;
    color: #c8c4be !important;
}

/* ═══════════════════════════════════════════════════
   TOTAL / ALLOCATION LINE
   ═══════════════════════════════════════════════════ */
.total-line {
    font-size: 0.79rem;
    color: #c96442;
    margin: 0.4rem 0 0.25rem 0;
}
.over-line {
    font-size: 0.76rem;
    color: #c04040;
    margin: 0.1rem 0;
}

/* ═══════════════════════════════════════════════════
   WORKSPACE: CHAPTER HEADER
   ═══════════════════════════════════════════════════ */
.ch-title {
    font-size: 1.35rem;
    font-weight: 400;
    color: #1a1a1a;
    margin-bottom: 0.2rem;
    line-height: 1.3;
}
.ch-meta {
    font-size: 0.74rem;
    color: #9c9693;
    margin-bottom: 1.75rem;
    letter-spacing: 0.015em;
}

/* ═══════════════════════════════════════════════════
   COMPETENCY ROW
   ═══════════════════════════════════════════════════ */
.comp-row {
    display: flex;
    align-items: baseline;
    gap: 0.7rem;
    margin-bottom: 0.15rem;
}
.comp-code   { font-size: 0.92rem; color: #1a1a1a; }
.comp-cg     { font-size: 0.74rem; color: #9c9693; }
.comp-weight {
    font-size: 0.72rem; color: #5a5754;
    background: #e8e5e0; padding: 1px 7px; border-radius: 3px;
}

/* ═══════════════════════════════════════════════════
   INCIDENTAL FOOTNOTE
   ═══════════════════════════════════════════════════ */
.incidental-line {
    font-size: 0.73rem;
    color: #9c9693;
    margin-top: 1.75rem;
    line-height: 1.7;
}

/* ═══════════════════════════════════════════════════
   WORKSPACE PLACEHOLDER
   ═══════════════════════════════════════════════════ */
.ws-placeholder {
    color: #9c9693;
    font-size: 0.88rem;
    padding: 5rem 0 3rem 0;
    text-align: center;
    letter-spacing: 0.01em;
}

/* ═══════════════════════════════════════════════════
   NO-DATA SIDEBAR NOTICE
   ═══════════════════════════════════════════════════ */
.no-data-notice {
    font-size: 0.78rem;
    color: #9c9693;
    margin-top: 1.25rem;
    line-height: 1.6;
}

/* ═══════════════════════════════════════════════════
   EXPANDER
   ═══════════════════════════════════════════════════ */
details > summary {
    font-size: 0.76rem !important;
    color: #5a5754 !important;
    padding: 0.2rem 0 !important;
}
details[open] > summary { color: #1a1a1a !important; }
details > div {
    font-size: 0.82rem !important;
    color: #5a5754 !important;
    line-height: 1.7 !important;
    padding: 0.4rem 0 0.2rem 0 !important;
}

/* ═══════════════════════════════════════════════════
   INFO / WARNING
   ═══════════════════════════════════════════════════ */
div[data-testid="stInfo"] {
    background: #fef8f5 !important;
    border: 1px solid #e8d0c0 !important;
    color: #8b5e4a !important;
    border-radius: 6px !important;
}
div[data-testid="stWarning"] {
    background: #fdf8ec !important;
    border: 1px solid #e8d898 !important;
    color: #7a6520 !important;
    border-radius: 6px !important;
}

/* ═══════════════════════════════════════════════════
   CHECKBOX LABELS
   ═══════════════════════════════════════════════════ */
.stCheckbox label span { font-size: 0.79rem !important; color: #5a5754 !important; }

/* ═══════════════════════════════════════════════════
   DIVIDERS
   ═══════════════════════════════════════════════════ */
hr { border-color: #d9d6d0 !important; }

/* ═══════════════════════════════════════════════════
   SIDEBAR USER FOOTER
   Sticky at bottom of sidebar via flex-column parent
   ═══════════════════════════════════════════════════ */
.sidebar-spacer {
    flex: 1 1 auto;
    min-height: 1.5rem;
}
.sidebar-user-footer {
    flex-shrink: 0;
    position: sticky;
    bottom: 0;
    padding-top: 0;
    padding-bottom: 1rem;
    background: #eeece8;
}
.user-footer-inner {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding-top: 0.65rem;
}
.user-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #d9d6d0;
    color: #5a5754;
    font-size: 0.72rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    letter-spacing: 0.02em;
    user-select: none;
}
.user-info { display: flex; flex-direction: column; gap: 0.1rem; }
.user-name {
    font-size: 0.82rem;
    font-weight: 500;
    color: #1a1a1a;
    line-height: 1;
}
.user-plan {
    font-size: 0.72rem;
    color: #9c9693;
    line-height: 1;
}

/* ═══════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
   ═══════════════════════════════════════════════════ */
#MainMenu, footer { visibility: hidden; }

</style>

""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_all_chapters() -> list[dict]:
    chapters = []
    for i in range(1, 13):
        path = MAPPINGS_DIR / f"ch_{i:02d}_mapping.json"
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        chapters.append(data)
    chapters.sort(key=lambda c: c["chapter_number"])
    return chapters


chapters = load_all_chapters()


def ch_label(ch: dict) -> str:
    return f"Ch {ch['chapter_number']:02d} — {ch['chapter_title']}"


def ch_short(ch: dict) -> str:
    t = ch["chapter_title"]
    return f"Ch {ch['chapter_number']:02d} · {t[:24]}{'…' if len(t) > 24 else ''}"


# ── Session state ─────────────────────────────────────────────────────────────

if "role"              not in st.session_state: st.session_state.role              = "Teacher"
if "grade"             not in st.session_state: st.session_state.grade             = "Grade VII"
if "subject"           not in st.session_state: st.session_state.subject           = "Social Science"

# Teacher
if "period_blocks"     not in st.session_state: st.session_state.period_blocks     = [{"id": 0, "duration": 45, "count": 5}]
if "next_block_id"     not in st.session_state: st.session_state.next_block_id     = 1
if "teacher_generated" not in st.session_state: st.session_state.teacher_generated = False
if "teacher_ch_idx"    not in st.session_state: st.session_state.teacher_ch_idx    = 0

# Principal
if "principal_total"     not in st.session_state: st.session_state.principal_total     = 120
if "ch_selected"         not in st.session_state: st.session_state.ch_selected         = {ch["chapter_number"]: True for ch in chapters}
if "ch_periods"          not in st.session_state: st.session_state.ch_periods          = {ch["chapter_number"]: 6    for ch in chapters}
if "principal_generated" not in st.session_state: st.session_state.principal_generated = False

# Only Grade VII + Social Science has chapter data currently
has_chapter_data = (
    st.session_state.grade   == "Grade VII" and
    st.session_state.subject == "Social Science"
)

# ── Fixed top nav bar ─────────────────────────────────────────────────────────
# Pure HTML pills — no Streamlit radio widget, no orange circles.
# onclick calls aruviSetRole() which clicks a hidden st.button in the sidebar.

t_active = "active" if st.session_state.role == "Teacher"   else ""
p_active = "active" if st.session_state.role == "Principal" else ""

logo_img_tag = (
    f'<img src="{LOGO_SRC}" alt="Aruvi logo">'
    if LOGO_SRC else '<div style="width:56px;height:56px;"></div>'
)

st.markdown(f"""
<div class="aruvi-topnav">

  <div class="topnav-left">
    {logo_img_tag}
    <div class="topnav-brand">
      <span class="topnav-wordmark">Aruvi</span>
      <span class="topnav-slogan">AI powered teaching assistant</span>
    </div>
  </div>

  <div class="topnav-center">
    <div class="aruvi-topnav-inner">
      <a class="aruvi-pill {t_active}" href="?role=Teacher">Teacher</a>
      <a class="aruvi-pill {p_active}" href="?role=Principal">Principal</a>
    </div>
  </div>

  <div class="topnav-right"></div>

</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
# Change 3: Grade / Subject / Chapter selectboxes use label_visibility="visible".
#           CSS floats each label inside the selectbox border at top-left.
#           No separate icon-label-row div above each selectbox.

with st.sidebar:

    # ── Grade selector — flat style, icon + label above, no box ──────────────
    _g_icon = f'<img src="{GRADE_SRC}" class="field-icon" alt="">' if GRADE_SRC else ""
    st.markdown(
        f'<div class="sidebar-field-label">{_g_icon}'
        f'<span class="field-label-text">Grade</span></div>',
        unsafe_allow_html=True,
    )
    grade = st.selectbox(
        "Grade",
        GRADES,
        index=GRADES.index(st.session_state.grade),
        label_visibility="collapsed",
        key="grade_select",
    )
    if grade != st.session_state.grade:
        st.session_state.grade             = grade
        st.session_state.teacher_ch_idx    = 0
        st.session_state.teacher_generated = False
        st.session_state.principal_generated = False
        st.rerun()

    # ── Subject selector — flat style, icon + label above, no box ────────────
    _s_icon = f'<img src="{SUBJECT_SRC}" class="field-icon" alt="">' if SUBJECT_SRC else ""
    st.markdown(
        f'<div class="sidebar-field-label">{_s_icon}'
        f'<span class="field-label-text">Subject</span></div>',
        unsafe_allow_html=True,
    )
    subject = st.selectbox(
        "Subject",
        SUBJECTS,
        index=SUBJECTS.index(st.session_state.subject),
        label_visibility="collapsed",
        key="subject_select",
    )
    if subject != st.session_state.subject:
        st.session_state.subject           = subject
        st.session_state.teacher_ch_idx    = 0
        st.session_state.teacher_generated = False
        st.session_state.principal_generated = False
        st.rerun()

    # ── No data for this combination ──────────────────────────────────────────
    if not has_chapter_data:
        st.markdown(
            '<div class="no-data-notice">'
            f'Chapter data for {st.session_state.subject}, '
            f'{st.session_state.grade} is not available yet.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Teacher inputs ────────────────────────────────────────────────────────
    elif st.session_state.role == "Teacher":

        st.divider()

        # Chapter selector — flat style, icon + label above, no box
        _c_icon = f'<img src="{CHAPTER_SRC}" class="field-icon" alt="">' if CHAPTER_SRC else ""
        st.markdown(
            f'<div class="sidebar-field-label">{_c_icon}'
            f'<span class="field-label-text">Chapter</span></div>',
            unsafe_allow_html=True,
        )
        ch_labels = [ch_label(ch) for ch in chapters]
        sel_label = st.selectbox(
            "Chapter",
            ch_labels,
            index=st.session_state.teacher_ch_idx,
            label_visibility="collapsed",
            key="teacher_ch_select",
        )
        new_idx = ch_labels.index(sel_label)
        if new_idx != st.session_state.teacher_ch_idx:
            st.session_state.teacher_ch_idx    = new_idx
            st.session_state.teacher_generated = False

        st.divider()

        # ── Available Time section ─────────────────────────────────────────────
        # Change 5: no visible "+ Add period block" button.
        # Change 6: ⊕ icon (period.png or Unicode fallback) triggers add via JS.
        # Hidden button stays in DOM so aruviAddBlock() has something to click.
        add_via_icon = st.button("", key="add_block_icon")

        if PERIOD_SRC:
            period_icon_html = (
                f'<img src="{PERIOD_SRC}" class="period-icon"'
                f' onclick="aruviAddBlock()" title="Add period block" alt="⊕">'
            )
        else:
            period_icon_html = (
                '<span class="period-icon-text"'
                ' onclick="aruviAddBlock()" title="Add period block">⊕</span>'
            )

        st.markdown(
            f'<div class="sect-label">{period_icon_html}'
            f'<span>Available time</span></div>',
            unsafe_allow_html=True,
        )

        # Change 4: column headers styled like sect-label (block-col-label)
        hdr_dur, hdr_cnt, hdr_rm = st.columns([3, 3, 1])
        with hdr_dur:
            st.markdown(
                '<span class="block-col-label">Time per period</span>',
                unsafe_allow_html=True,
            )
        with hdr_cnt:
            st.markdown(
                '<span class="block-col-label">No. of periods</span>',
                unsafe_allow_html=True,
            )

        block_to_remove = None

        for i, block in enumerate(st.session_state.period_blocks):
            bid = block["id"]
            dk  = f"dur_{bid}"
            ck  = f"cnt_{bid}"

            c_dur, c_cnt, c_rm = st.columns([3, 3, 1])

            with c_dur:
                dur_idx = DURATION_OPTIONS.index(block["duration"]) \
                          if block["duration"] in DURATION_OPTIONS else 3
                dur = st.selectbox(
                    "Time per period",
                    DURATION_OPTIONS,
                    index=dur_idx,
                    label_visibility="collapsed",
                    key=dk,
                    format_func=lambda x: f"{x} min",
                )

            with c_cnt:
                cnt = st.number_input(
                    "No. of Periods",
                    min_value=1,
                    max_value=60,
                    value=block["count"],
                    step=1,
                    label_visibility="collapsed",
                    key=ck,
                )

            with c_rm:
                st.markdown('<div style="padding-top:0.3rem;">', unsafe_allow_html=True)
                if len(st.session_state.period_blocks) > 1:
                    if st.button("✕", key=f"rm_{bid}", help="Remove block"):
                        block_to_remove = i
                else:
                    st.markdown(
                        '<div style="color:#d9d6d0;font-size:0.85rem;'
                        'text-align:center;padding-top:0.45rem;">✕</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown('</div>', unsafe_allow_html=True)

            st.session_state.period_blocks[i]["duration"] = st.session_state.get(dk, dur)
            st.session_state.period_blocks[i]["count"]    = st.session_state.get(ck, cnt)

        if block_to_remove is not None:
            removed = st.session_state.period_blocks.pop(block_to_remove)
            for k in [f"dur_{removed['id']}", f"cnt_{removed['id']}"]:
                st.session_state.pop(k, None)
            st.rerun()

        # Change 5: only the hidden icon-triggered add remains (no visible button)
        if add_via_icon:
            nid = st.session_state.next_block_id
            st.session_state.next_block_id += 1
            st.session_state.period_blocks.append({"id": nid, "duration": 45, "count": 1})
            st.rerun()

        total_p = sum(b["count"] for b in st.session_state.period_blocks)
        total_m = sum(
            st.session_state.get(f"dur_{b['id']}", b["duration"])
            * st.session_state.get(f"cnt_{b['id']}", b["count"])
            for b in st.session_state.period_blocks
        )
        st.markdown(
            f'<div class="total-line">'
            f'Total: {total_p} periods · {total_m} min · {total_m / 60:.1f} hrs'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        can_gen = any(
            st.session_state.get(f"cnt_{b['id']}", b["count"]) >= 1
            for b in st.session_state.period_blocks
        )
        if st.button(
            "Generate Lesson Plan & Assessment",
            disabled=not can_gen,
            type="primary",
            use_container_width=True,
            key="teacher_gen",
        ):
            st.session_state.teacher_generated = True
            st.rerun()

    # ── Principal inputs ──────────────────────────────────────────────────────
    else:

        st.divider()

        st.markdown(
            '<div class="sect-label">📊 &nbsp;Period Budget</div>',
            unsafe_allow_html=True,
        )
        total_available = st.number_input(
            "Total periods available",
            min_value=1,
            max_value=999,
            value=st.session_state.principal_total,
            step=1,
            label_visibility="collapsed",
            key="principal_total_input",
        )
        st.session_state.principal_total = total_available

        st.divider()

        st.markdown(
            '<div class="sect-label">📋 &nbsp;Chapter Selection</div>',
            unsafe_allow_html=True,
        )

        sa_col, da_col = st.columns(2)
        with sa_col:
            if st.button("Select All", key="sel_all", use_container_width=True):
                for ch in chapters:
                    st.session_state.ch_selected[ch["chapter_number"]] = True
                st.rerun()
        with da_col:
            if st.button("Deselect All", key="desel_all", use_container_width=True):
                for ch in chapters:
                    st.session_state.ch_selected[ch["chapter_number"]] = False
                st.rerun()

        st.markdown('<div style="height:0.3rem;"></div>', unsafe_allow_html=True)

        total_allocated = 0
        for ch in chapters:
            ch_num = ch["chapter_number"]
            ck_col, p_col = st.columns([5, 3])
            with ck_col:
                checked = st.checkbox(
                    ch_short(ch),
                    value=st.session_state.ch_selected.get(ch_num, True),
                    key=f"chk_{ch_num}",
                )
                st.session_state.ch_selected[ch_num] = checked
            with p_col:
                if checked:
                    p = st.number_input(
                        "p",
                        min_value=1,
                        max_value=60,
                        value=st.session_state.ch_periods.get(ch_num, 6),
                        step=1,
                        label_visibility="collapsed",
                        key=f"per_{ch_num}",
                    )
                    st.session_state.ch_periods[ch_num] = p
                    total_allocated += p
                else:
                    st.markdown(
                        '<div style="color:#d9d6d0;font-size:0.8rem;'
                        'padding-top:0.45rem;text-align:center;">—</div>',
                        unsafe_allow_html=True,
                    )

        st.divider()

        over       = total_allocated > total_available
        line_color = "#c04040" if over else "#c96442"
        st.markdown(
            f'<div class="total-line" style="color:{line_color};">'
            f'Total allocated: {total_allocated} of {total_available} periods'
            f'</div>',
            unsafe_allow_html=True,
        )
        if over:
            st.markdown(
                f'<div class="over-line">'
                f'Over by {total_allocated - total_available} periods</div>',
                unsafe_allow_html=True,
            )

        if st.button(
            "Generate Allocation Report",
            type="primary",
            use_container_width=True,
            key="principal_gen",
        ):
            st.session_state.principal_generated = True
            st.rerun()

    # ── Sidebar spacer + user footer (sticky at bottom) ───────────────────────
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    st.markdown("""
<div class="sidebar-user-footer">
  <hr style="border:none;border-top:1px solid #d9d6d0;margin:0;" />
  <div class="user-footer-inner">
    <div class="user-avatar">RT</div>
    <div class="user-info">
      <span class="user-name">Ramesh Tripathi</span>
      <span class="user-plan">Free plan</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Workspace ─────────────────────────────────────────────────────────────────

if not has_chapter_data:
    st.markdown(
        '<div class="ws-placeholder">'
        f'No content available yet for '
        f'{st.session_state.subject}, {st.session_state.grade}.'
        '</div>',
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════
#  TEACHER WORKSPACE
#  Change 2: tabs = Competencies · Lesson Plan · Assessment
# ═════════════════════════════════════════════════
elif st.session_state.role == "Teacher":

    selected_ch = chapters[st.session_state.teacher_ch_idx]
    tab_comp, tab_lp, tab_assess = st.tabs(
        ["Competencies", "Lesson Plan", "Assessment"]
    )

    with tab_comp:
        st.markdown(
            f'<div class="ch-title">{selected_ch["chapter_title"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="ch-meta">Grade VII · Social Sciences · '
            f'Chapter weight: {selected_ch.get("chapter_weight", "—")}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="sect-label" style="margin-top:0;">Primary Competencies</div>',
            unsafe_allow_html=True,
        )

        for comp in selected_ch.get("primary", []):
            w      = comp.get("weight", "—")
            wlabel = WEIGHT_LABEL.get(w, str(w))
            st.markdown(
                f'<div class="comp-row">'
                f'<span class="comp-code">{comp["c_code"]}</span>'
                f'<span class="comp-cg">{comp["cg"]}</span>'
                f'<span class="comp-weight">{wlabel}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Justification"):
                st.write(comp.get("justification", ""))
            st.markdown('<div style="height:0.4rem;"></div>', unsafe_allow_html=True)

        incidental = selected_ch.get("incidental", [])
        if incidental:
            codes = "  ·  ".join(c["c_code"] for c in incidental)
            st.markdown(
                f'<div class="incidental-line">'
                f'Incidental (not assessed)&ensp;·&ensp;{codes}</div>',
                unsafe_allow_html=True,
            )

    with tab_lp:
        if not st.session_state.teacher_generated:
            st.markdown(
                '<div class="ws-placeholder">'
                'Select a chapter and period budget, then generate.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Lesson plan will appear here once the API call is wired.")

    with tab_assess:
        if not st.session_state.teacher_generated:
            st.markdown(
                '<div class="ws-placeholder">'
                'Generate a lesson plan first — the assessment follows automatically.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Assessment will appear here once the API call is wired.")

# ═════════════════════════════════════════════════
#  PRINCIPAL WORKSPACE
#  tabs = Period Allocation · Competency Report
# ═════════════════════════════════════════════════
else:

    tab_alloc, tab_cov = st.tabs(
        ["Period Allocation", "Competency Report"]
    )

    with tab_alloc:
        if not st.session_state.principal_generated:
            st.markdown(
                '<div class="ws-placeholder">'
                'Configure the period budget and chapter selection, then generate.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Period allocation will appear here once the API call is wired.")

    with tab_cov:
        if not st.session_state.principal_generated:
            st.markdown(
                '<div class="ws-placeholder">'
                'Generate the period allocation to see competency coverage.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Competency report will appear here once the API call is wired.")
