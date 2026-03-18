from dotenv import load_dotenv
load_dotenv("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi/.env")

import base64
import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

import streamlit as st
import anthropic
import os

# ── Project root (needed by helper functions below) ───────────────────────────

PROJECT_ROOT = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")
MISC_DIR     = PROJECT_ROOT / "miscellaneous"

# ── Stage derivation ──────────────────────────────────────────────────────────

def get_stage(grade: str) -> str:
    preparatory = {"Grade III", "Grade IV", "Grade V"}
    middle       = {"Grade VI", "Grade VII", "Grade VIII"}
    if grade in preparatory: return "preparatory"
    if grade in middle:      return "middle"
    return "secondary"

def grade_to_folder(grade: str) -> str:
    return grade.lower().replace(" ", "_")

def subject_to_folder(subject: str) -> str:
    mapping = {
        "Social Science": "social_sciences",
        "Mathematics":    "mathematics",
        "Science":        "science",
        "English":        "languages",
        "Second Language":"languages",
        "EVS":            "science",
    }
    return mapping.get(subject, subject.lower().replace(" ", "_"))

# ── Path resolver ─────────────────────────────────────────────────────────────

def resolve_paths(grade: str, subject: str, chapter_number: int) -> dict:
    stage   = get_stage(grade)
    grade_f = grade_to_folder(grade)
    subj_f  = subject_to_folder(subject)
    mirror  = PROJECT_ROOT / "mirror"
    nn      = f"{chapter_number:02d}"
    return {
        "lp_constitution":  mirror / "constitutions/lesson_plan/lesson_plan_constitution.txt",
        "assessment_const": mirror / "constitutions/assessment/assessment_constitution.txt",
        "pedagogy":         mirror / f"framework/{subj_f}/{stage}/pedagogy_{stage}_{subj_f}.txt",
        "cg_doc":           mirror / f"framework/{subj_f}/{stage}/cg_{stage}_{subj_f}.txt",
        "chapter_summary":  mirror / f"chapters/{subj_f}/{grade_f}/summaries/ch_{nn}_summary.txt",
        "chapter_mapping":  mirror / f"chapters/{subj_f}/{grade_f}/mappings/ch_{nn}_mapping.json",
    }

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[FILE NOT FOUND: {path}]"

# ── API rates and token logging ───────────────────────────────────────────────

API_RATES_PATH = PROJECT_ROOT / "knowledge_commons/evaluation_mappings/api_rates.json"
TOKEN_LOG_PATH = PROJECT_ROOT / "knowledge_commons/evaluation_mappings/token_log.csv"

@st.cache_data
def load_api_rates() -> dict:
    try:
        return json.loads(API_RATES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def calculate_cost_inr(model: str, input_tokens: int, output_tokens: int) -> float:
    rates       = load_api_rates()
    usd_to_inr  = rates.get("usd_to_inr", 84.0)
    model_rates = rates.get("models", {}).get(model, {})
    input_rate  = model_rates.get("input_per_1k_usd",  0.003)
    output_rate = model_rates.get("output_per_1k_usd", 0.015)
    cost_usd    = (input_tokens  / 1000) * input_rate + \
                  (output_tokens / 1000) * output_rate
    return round(cost_usd * usd_to_inr, 4)

def grade_to_roman(grade: str) -> str:
    mapping = {
        "Grade III": "iii", "Grade IV": "iv",  "Grade V":   "v",
        "Grade VI":  "vi",  "Grade VII": "vii", "Grade VIII":"viii",
        "Grade IX":  "ix",  "Grade X":   "x",
    }
    return mapping.get(grade, grade.lower().replace("grade ", ""))

def log_tokens(
    call_type:      str,
    grade:          str,
    subject:        str,
    chapter_number: int,
    chapter_title:  str,
    input_tokens:   int,
    output_tokens:  int,
    model:          str = "claude-sonnet-4-6",
):
    cost_inr = calculate_cost_inr(model, input_tokens, output_tokens)
    row = [
        datetime.now().isoformat(timespec="seconds"),
        call_type,
        subject_to_folder(subject),
        grade_to_roman(grade),
        chapter_number,
        chapter_title,
        input_tokens,
        output_tokens,
        input_tokens + output_tokens,
        cost_inr,
    ]
    try:
        with open(TOKEN_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception:
        pass  # never crash the app over a logging failure

# ── Export helpers ────────────────────────────────────────────────────────────

# ── Export helpers ────────────────────────────────────────────────────────────

def add_markdown_content(doc, text):
    """Add markdown text to a python-docx Document — handles headings, bullets, bold."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
            continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        elif re.match(r"^\d+\.\s", stripped):
            doc.add_paragraph(
                re.sub(r"^\d+\.\s", "", stripped),
                style="List Number"
            )
        else:
            para = doc.add_paragraph()
            parts = re.split(r"\*\*(.+?)\*\*", stripped)
            for j, part in enumerate(parts):
                run = para.add_run(part)
                if j % 2 == 1:
                    run.bold = True


def generate_docx_bytes_lp(result: dict, chapter: dict, grade: str, subject: str) -> bytes:
    """DOCX export — Lesson Plan only, no Assessment."""
    doc = Document()

    title = doc.add_heading("Aruvi · Lesson Plan", level=1)
    title.runs[0].font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)

    meta = doc.add_table(rows=4, cols=2)
    meta.style = "Table Grid"
    for i, (lbl, val) in enumerate(zip(
        ["Grade", "Subject", "Chapter", "Chapter Weight"],
        [grade, subject, chapter.get("chapter_title", ""), str(chapter.get("chapter_weight", ""))]
    )):
        meta.rows[i].cells[0].text = lbl
        meta.rows[i].cells[1].text = val
        meta.rows[i].cells[0].paragraphs[0].runs[0].bold = True
    doc.add_paragraph()

    lp = result.get("lesson_plan", "")
    if "```json" in lp:
        lp = lp[:lp.index("```json")].strip()
    add_markdown_content(doc, lp)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_pdf_bytes_lp(result: dict, chapter: dict, grade: str, subject: str) -> bytes:
    """PDF export — Lesson Plan only, no Assessment."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(44, 62, 80)
    pdf.set_x(10)
    pdf.cell(190, 10, "Aruvi - Lesson Plan", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Grade: {grade}   Subject: {subject}", ln=True)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Chapter: {chapter.get('chapter_title', '')}", ln=True)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Chapter Weight: {chapter.get('chapter_weight', '')}", ln=True)
    pdf.ln(4)
    pdf.set_draw_color(44, 62, 80)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    lp = result.get("lesson_plan", "")
    if "```json" in lp:
        lp = lp[:lp.index("```json")].strip()

    pdf.set_text_color(30, 30, 30)
    for line in lp.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        stripped = re.sub(r"^#{1,3}\s+", "", stripped)
        stripped = re.sub(r"^[-*]\s+", "- ", stripped)
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(44, 62, 80)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(44, 62, 80)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
        pdf.set_x(10)
        try:
            pdf.multi_cell(190, 5, stripped)
        except Exception:
            try:
                pdf.set_x(10)
                pdf.multi_cell(190, 5, stripped.encode("latin-1", "replace").decode("latin-1"))
            except Exception:
                pass  # skip lines that cannot render

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def generate_docx_bytes_assess(result: dict, chapter: dict, grade: str, subject: str) -> bytes:
    """DOCX export — Assessment only, no Lesson Plan."""
    doc = Document()

    title = doc.add_heading("Aruvi · Chapter Assessment", level=1)
    title.runs[0].font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)

    meta = doc.add_table(rows=4, cols=2)
    meta.style = "Table Grid"
    for i, (lbl, val) in enumerate(zip(
        ["Grade", "Subject", "Chapter", "Chapter Weight"],
        [grade, subject, chapter.get("chapter_title", ""), str(chapter.get("chapter_weight", ""))]
    )):
        meta.rows[i].cells[0].text = lbl
        meta.rows[i].cells[1].text = val
        meta.rows[i].cells[0].paragraphs[0].runs[0].bold = True
    doc.add_paragraph()

    asmt = result.get("assessment", "")
    add_markdown_content(doc, asmt)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_pdf_bytes_assess(result: dict, chapter: dict, grade: str, subject: str) -> bytes:
    """PDF export — Assessment only, no Lesson Plan."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(44, 62, 80)
    pdf.set_x(10)
    pdf.cell(190, 10, "Aruvi - Chapter Assessment", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Grade: {grade}   Subject: {subject}", ln=True)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Chapter: {chapter.get('chapter_title', '')}", ln=True)
    pdf.set_x(10)
    pdf.cell(190, 6, f"Chapter Weight: {chapter.get('chapter_weight', '')}", ln=True)
    pdf.ln(4)
    pdf.set_draw_color(44, 62, 80)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    asmt = result.get("assessment", "")
    pdf.set_text_color(30, 30, 30)
    for line in asmt.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        stripped = re.sub(r"^#{1,3}\s+", "", stripped)
        stripped = re.sub(r"^[-*]\s+", "- ", stripped)
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(44, 62, 80)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(44, 62, 80)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
        pdf.set_x(10)
        try:
            pdf.multi_cell(190, 5, stripped)
        except Exception:
            try:
                pdf.set_x(10)
                pdf.multi_cell(190, 5, stripped.encode("latin-1", "replace").decode("latin-1"))
            except Exception:
                pass  # skip lines that cannot render

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def format_period_schedule(period_rows: list, session: dict) -> str:
    lines = []
    total_periods = 0
    total_minutes = 0
    for i, rid in enumerate(period_rows):
        dur = session.get(f"dur_sel_{rid}", 40)
        cnt = session.get(f"cnt_{rid}", 1)
        total_periods += cnt
        total_minutes += dur * cnt
        lines.append(
            f"  Row {i+1}: {dur} minutes × {cnt} period{'s' if cnt != 1 else ''} = {dur*cnt} minutes"
        )
    h, m = divmod(total_minutes, 60)
    time_str = f"{h}h {m}min" if h > 0 else f"{m} minutes"
    return (
        f"Period schedule:\n" + "\n".join(lines) +
        f"\nTotal: {total_periods} periods · {time_str}"
    )

def generate_lpa(
    grade: str,
    subject: str,
    chapter: dict,
    period_rows: list,
    session: dict,
) -> dict:
    paths = resolve_paths(grade, subject, chapter["chapter_number"])

    lp_const     = read_file(paths["lp_constitution"])
    assess_const = read_file(paths["assessment_const"])
    pedagogy     = read_file(paths["pedagogy"])
    cg_doc       = read_file(paths["cg_doc"])
    summary      = read_file(paths["chapter_summary"])
    mapping_raw  = read_file(paths["chapter_mapping"])
    period_sched = format_period_schedule(period_rows, session)

    system_prompt = f"""You are Aruvi's lesson plan and assessment generator.

You operate under two constitutions that govern every decision you make.
These constitutions are binding. No instruction in the user prompt overrides them.

=== LESSON PLAN GENERATION CONSTITUTION ===
{lp_const}

=== ASSESSMENT CONSTITUTION ===
{assess_const}
"""

    user_prompt = f"""Generate a complete lesson plan and chapter assessment for the following chapter.

=== PEDAGOGY DOCUMENT ===
{pedagogy}

=== CURRICULAR GOALS DOCUMENT ===
{cg_doc}

=== CHAPTER SUMMARY ===
{summary}

=== CHAPTER MAPPING JSON ===
{mapping_raw}

=== TEACHER PERIOD SCHEDULE ===
{period_sched}

=== INSTRUCTIONS ===
1. Generate the period-by-period lesson plan first. Every period gets exactly one activity. Each activity must be anchored to a named section from the chapter summary. Each activity must develop a mapped competency. Activity depth must be calibrated to that period's specific duration.

2. Immediately after the lesson plan, produce the LO handoff as a JSON code block. The JSON must follow the schema defined in Amendment A2 of the Lesson Plan Constitution exactly — one object per period with fields: period_number, period_duration_minutes, chapter_section, activity_summary, implied_lo, c_code, cg, weight.

3. After the LO handoff JSON, generate the chapter assessment. Use the LO handoff as the sole structural input. Competency weight governs question type, question count, and annotation depth exactly as the Assessment Constitution specifies.

4. State each implied LO clearly in the lesson plan against its activity, and again in the assessment as the stated purpose of each question cluster.

Output format:
## Lesson Plan
[period-by-period plan]

## LO Handoff
```json
[array]
```

## Assessment
[assessment with full annotation layer]
"""

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        full_output = response.content[0].text

        log_tokens(
            call_type      = "lpa_generation",
            grade          = grade,
            subject        = subject,
            chapter_number = chapter["chapter_number"],
            chapter_title  = chapter.get("chapter_title", ""),
            input_tokens   = response.usage.input_tokens,
            output_tokens  = response.usage.output_tokens,
        )

        lo_handoff = []
        if "```json" in full_output:
            try:
                json_block = full_output.split("```json")[1].split("```")[0].strip()
                lo_handoff = json.loads(json_block)
            except Exception:
                lo_handoff = []

        lp_part = ""
        assess_part = ""
        if "## Assessment" in full_output:
            parts       = full_output.split("## Assessment", 1)
            lp_part     = parts[0].strip()
            assess_part = "## Assessment" + parts[1]
        else:
            lp_part = full_output

        return {
            "lesson_plan":  lp_part,
            "lo_handoff":   lo_handoff,
            "assessment":   assess_part,
            "input_tokens": response.usage.input_tokens,
            "output_tokens":response.usage.output_tokens,
            "cost_inr":     calculate_cost_inr(
                                "claude-sonnet-4-6",
                                response.usage.input_tokens,
                                response.usage.output_tokens,
                            ),
            "error":        None,
        }

    except Exception as e:
        return {
            "lesson_plan": "",
            "lo_handoff":  [],
            "assessment":  "",
            "error":       str(e),
        }

# ── Constants ─────────────────────────────────────────────────────────────────

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

# ── Restore state from URL query params (survives pill-click reloads) ─────────

query = st.query_params

if "role"    in query and query["role"]    in ("Teach", "Plan"):
    st.session_state.role    = query["role"]
if "grade"   in query and query["grade"]   in GRADES:
    st.session_state.grade   = query["grade"]
if "subject" in query and query["subject"] in SUBJECTS:
    st.session_state.subject = query["subject"]
if "ch"      in query:
    try: st.session_state.teacher_ch_idx = int(query["ch"])
    except ValueError: pass

# Defaults on first load
if "role"    not in st.session_state: st.session_state.role    = "Plan"
if "grade"   not in st.session_state: st.session_state.grade   = None
if "subject" not in st.session_state: st.session_state.subject = None

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
PERIOD_SRC      = _img_src(MISC_DIR / "period.png")       # row header add-icon
TIME_SRC        = _img_src(MISC_DIR / "time.png")         # "Available time" label icon
FULL_PERIOD_SRC = _img_src(MISC_DIR / "full_period.png")  # Principal "Period Budget" label icon
WATERMARK_SRC   = _img_src(MISC_DIR / "aruvi_logo-transparent.png")  # Main body watermark


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
.aruvi-pill:link    { color: #6b6866 !important; text-decoration: none !important; }
.aruvi-pill:visited { color: #6b6866 !important; text-decoration: none !important; }
.aruvi-pill:active  { color: #6b6866 !important; text-decoration: none !important; }
.aruvi-pill:focus   { color: #6b6866 !important; text-decoration: none !important; }
.aruvi-pill:hover   { color: #2c2a27 !important; text-decoration: none !important; background: rgba(0,0,0,0.04); }
.aruvi-pill.active {
    background: #ffffff;
    color: #2c2a27;          /* same dark tone as topnav wordmark */
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12);
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
    background-color: #ffffff !important;
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
html, body {
    background-color: #f5f3ef;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}
.stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}
[data-testid="stAppViewContainer"] {
    background-color: #ffffff !important;
}

/* ═══════════════════════════════════════════════════
   MAIN BODY WATERMARK
   Aruvi logo rendered as a very-light-grey centred
   watermark behind all content. Uses ::before so the
   opacity does not bleed through to child elements.
   ═══════════════════════════════════════════════════ */
[data-testid="stMain"] {
    background-color: #ffffff !important;
    position: relative;
}
/* watermark rule injected below via f-string */

/* 24 × 24 px grid — very faint lines */
[data-testid="stMain"]::after {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(180, 174, 165, 0.07) 1px, transparent 1px),
        linear-gradient(90deg, rgba(180, 174, 165, 0.07) 1px, transparent 1px);
    background-size: 24px 24px;
    pointer-events: none;
    z-index: 0;
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
    margin-bottom: 0.75rem;
}
.field-icon {
    width: 23px;
    height: 23px;
    object-fit: contain;
    opacity: 0.72;
    flex-shrink: 0;
}
.field-icon-grade {
    width: 27px;
    height: 27px;
    object-fit: contain;
    opacity: 1.0;
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

/* ═══════════════════════════════════════════════════
   GRADE / SUBJECT / CHAPTER SELECTBOX
   Grey rounded box (filled with sidebar bg) + smaller
   dark-grey value font.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] div[class*="st-key-grade_select"] [data-baseweb="select"] > div:first-child,
section[data-testid="stSidebar"] div[class*="st-key-subject_select"] [data-baseweb="select"] > div:first-child,
section[data-testid="stSidebar"] div[class*="st-key-teacher_ch_select"] [data-baseweb="select"] > div:first-child {
    border: 1px solid #d0cdc9 !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    padding: 6px 8px 6px 10px !important;
    box-shadow: none !important;
    min-height: 34px !important;
    display: flex !important;
    align-items: center !important;
}
/* Value text + placeholder: legible size, high-contrast dark */
section[data-testid="stSidebar"] div[class*="st-key-grade_select"] [data-baseweb="select"] [data-baseweb="value"],
section[data-testid="stSidebar"] div[class*="st-key-grade_select"] [data-baseweb="select"] [data-baseweb="placeholder"],
section[data-testid="stSidebar"] div[class*="st-key-grade_select"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] div[class*="st-key-subject_select"] [data-baseweb="select"] [data-baseweb="value"],
section[data-testid="stSidebar"] div[class*="st-key-subject_select"] [data-baseweb="select"] [data-baseweb="placeholder"],
section[data-testid="stSidebar"] div[class*="st-key-subject_select"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] div[class*="st-key-teacher_ch_select"] [data-baseweb="select"] [data-baseweb="value"],
section[data-testid="stSidebar"] div[class*="st-key-teacher_ch_select"] [data-baseweb="select"] [data-baseweb="placeholder"],
section[data-testid="stSidebar"] div[class*="st-key-teacher_ch_select"] [data-baseweb="select"] span {
    font-size: 0.76rem !important;
    color: #2c2a27 !important;
}

/* ═══════════════════════════════════════════════════
   DURATION SELECTBOX  — centre value text
   Targets dur_sel_0 (Teacher) and dur_sel_p0 (Principal).
   Strategy:
     • Remove the right-offset padding on the control container
       (the arrow div is a flex-sibling, so it stays right naturally).
     • Give the VALUE sub-container flex:1 + justify-content:center
       so it fills remaining space and centres its content.
     • Force every text node inside it to centre.
   ═══════════════════════════════════════════════════ */

/* 1. Control container: flex row, no extra right padding */
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="select"] > div:first-child {
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
}
/* 2. Value sub-container (first child of control): fill width, centre */
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="select"] > div:first-child > div:first-child {
    flex: 1 1 0% !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    min-width: 0 !important;
}
/* 3. Value / placeholder text nodes — block + centred */
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="value"],
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="placeholder"],
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="select"] > div:first-child span {
    display: block !important;
    text-align: center !important;
    width: 100% !important;
}
/* 4. White rounded box — overrides the flat/no-border style */
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="select"] > div:first-child {
    border: 1px solid #d0cdc9 !important;
    border-radius: 8px !important;
    background: #ffffff !important;
    padding: 4px 6px !important;
}
section[data-testid="stSidebar"] div[class*="st-key-dur_sel_"] [data-baseweb="select"] > div:first-child > div {
    background: #ffffff !important;
}

/* ═══════════════════════════════════════════════════
   COUNT NUMBER INPUT  — centre value, hide built-in steps
   Applies to all cnt_ keys (Teacher cnt_0/1/… and
   Principal cnt_p0/1/…). Custom +/− buttons are used.
   ═══════════════════════════════════════════════════ */
/* Hide Streamlit's built-in step buttons — custom ±
   st.buttons are used on both Teacher and Principal. */
section[data-testid="stSidebar"] [class*="st-key-cnt_"] [data-testid="stNumberInput"] button {
    display: none !important;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR SECTION LABEL
   ═══════════════════════════════════════════════════ */
.sect-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #5a5754 !important;
    margin: 0.5rem 0 0.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.35rem;
}

/* ═══════════════════════════════════════════════════
   TIGHTER SIDEBAR VERTICAL RHYTHM
   Reduces Streamlit's default block-container gaps
   so Grade / Subject / Chapter / Generate sit closer.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
/* Collapse space between a sect-label row and the row immediately below it */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div[data-testid="element-container"]:has(.sect-label) + div[data-testid="element-container"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] .sidebar-field-label {
    margin-top: 0.55rem !important;
    margin-bottom: 0.45rem !important;
}
section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
    margin-bottom: 0.3rem !important;
}
section[data-testid="stSidebar"] hr,
section[data-testid="stSidebar"] [data-testid="stDivider"] {
    margin-top: 0.5rem !important;
    margin-bottom: 0.5rem !important;
}

/* ═══════════════════════════════════════════════════
   PERIOD ⊕ ICON  (clickable, adds a period block)
   ═══════════════════════════════════════════════════ */
.period-icon {
    width: 20px;
    height: 20px;
    object-fit: contain;
    cursor: pointer;
    opacity: 1.0;
    transition: opacity 0.15s;
    flex-shrink: 0;
    vertical-align: middle;
}
.period-icon:hover { opacity: 0.75; }
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
   REMOVE-ROW ✕ BUTTON  — dark, vertically centred
   ═══════════════════════════════════════════════════ */
/* Align the whole rm column contents to centre vertically */
section[data-testid="stSidebar"] div[class*="st-key-rm_"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
}
section[data-testid="stSidebar"] div[class*="st-key-rm_"] button {
    color: #3d3b38 !important;
    font-size: 0.85rem !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    min-height: unset !important;
    line-height: 1 !important;
}
section[data-testid="stSidebar"] div[class*="st-key-rm_"] button:hover {
    color: #c0392b !important;
    background: transparent !important;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR BUTTONS — ensure text always visible
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] button,
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] button span,
section[data-testid="stSidebar"] button div {
    color: #3d3b38 !important;
    visibility: visible !important;
    opacity: 1 !important;
}

/* ═══════════════════════════════════════════════════
   PERIOD COUNT STEPPER  (+/− buttons)
   ::after pseudo-elements supply the visible symbol.
   Streamlit's theme cannot override ::after content
   color, so this always renders on the native background.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [class*="st-key-plus_"] button,
section[data-testid="stSidebar"] [class*="st-key-minus_"] button {
    background: transparent !important;
    border: 1px solid #c8c4be !important;
    border-radius: 4px !important;
    min-height: 28px !important;
    padding: 0 !important;
    position: relative !important;
}
/* Hide Streamlit's own (theme-coloured) label */
section[data-testid="stSidebar"] [class*="st-key-plus_"] button *,
section[data-testid="stSidebar"] [class*="st-key-minus_"] button * {
    visibility: hidden !important;
}
/* Overlay our own symbol via ::after — CSS-owned, theme-proof */
section[data-testid="stSidebar"] [class*="st-key-plus_"] button::after {
    content: "+";
    color: #3d3b38;
    font-size: 1.05rem;
    font-weight: 500;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    visibility: visible !important;
    pointer-events: none;
}
section[data-testid="stSidebar"] [class*="st-key-minus_"] button::after {
    content: "−";
    color: #3d3b38;
    font-size: 1.05rem;
    font-weight: 500;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    visibility: visible !important;
    pointer-events: none;
}
section[data-testid="stSidebar"] [class*="st-key-plus_"] button:hover,
section[data-testid="stSidebar"] [class*="st-key-minus_"] button:hover {
    background: #e8e5e0 !important;
    border-color: #9c9693 !important;
}

/* ═══════════════════════════════════════════════════
   DURATION NUMBER INPUT  (replaces selectbox)
   In the time-per-period column — keep native arrows
   so user can step through values or type directly.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [class*="st-key-dur_"] input,
section[data-testid="stSidebar"] [class*="st-key-dur_p"] input {
    font-size: 0.84rem !important;
    color: #3d3b38 !important;
    padding: 0.25rem 0.4rem !important;
}

/* ═══════════════════════════════════════════════════
   COUNT NUMBER INPUT  (editable, flanked by +/−)
   Hide native spin arrows — custom buttons are used.
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [class*="st-key-cnt_"] input {
    font-size: 0.84rem !important;
    color: #3d3b38 !important;
    text-align: center !important;
    padding: 0.25rem 0.1rem !important;
    -moz-appearance: textfield !important;
}
section[data-testid="stSidebar"] [class*="st-key-cnt_"] input::-webkit-outer-spin-button,
section[data-testid="stSidebar"] [class*="st-key-cnt_"] input::-webkit-inner-spin-button {
    -webkit-appearance: none !important;
    margin: 0 !important;
}
/* White rounded box on all count inputs (Teacher + Principal) */
section[data-testid="stSidebar"] [class*="st-key-cnt_"] [data-baseweb="input"] {
    background: #ffffff !important;
    border: 1px solid #d0cdc9 !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
/* BaseUI renders a nested inner-wrapper div inside [data-baseweb="input"]
   that carries its own background — override it to match white. */
section[data-testid="stSidebar"] [class*="st-key-cnt_"] [data-baseweb="input"] > div {
    background: #ffffff !important;
}
/* Keep the inner <input> element transparent so the
   container background shows through cleanly */
section[data-testid="stSidebar"] [class*="st-key-cnt_"] input {
    background: transparent !important;
}

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
   SELECTBOX DROPDOWN OPTION LIST
   BaseUI portals the menu outside the sidebar so these
   must be global. Match chosen-value font / size / colour.
   ═══════════════════════════════════════════════════ */
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] [role="listbox"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif !important;
    background: #f5f3ef !important;
    border: 1px solid #d9d6d0 !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.10) !important;
}
[data-baseweb="popover"] [role="option"] {
    font-size: 0.76rem !important;
    color: #2c2a27 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif !important;
    background: transparent !important;
    padding: 0.42rem 0.75rem !important;
}
[data-baseweb="popover"] [role="option"]:hover {
    background: #e8e5e0 !important;
    color: #1a1a1a !important;
}
[data-baseweb="popover"] [aria-selected="true"] {
    background: #e0ddd8 !important;
    color: #1a1a1a !important;
}
/* Placeholder text — same size & colour as selected value */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="placeholder"] {
    font-size: 0.84rem !important;
    color: #3d3b38 !important;
}

/* ═══════════════════════════════════════════════════
   DROPDOWN ARROW — keep native SVG, just size + colour it
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] [data-baseweb="select"] svg {
    display: block !important;
    width: 14px !important;
    height: 14px !important;
    color: #9c9693 !important;
    opacity: 0.8;
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
    border-bottom: 2px solid #2c3e50 !important;
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

/* ═══════════════════════════════════════════════════
   GENERATE BUTTONS  — Teacher + Principal, tall pill style
   Dark slate background · white text · bold · centred
   ═══════════════════════════════════════════════════ */
section[data-testid="stSidebar"] div[class*="st-key-teacher_gen"] button,
section[data-testid="stSidebar"] div[class*="st-key-principal_gen"] button {
    height: 56px !important;
    min-height: 56px !important;
    border-radius: 12px !important;
    background: #2c3e50 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    letter-spacing: 0.02em !important;
    justify-content: center !important;
}
section[data-testid="stSidebar"] div[class*="st-key-teacher_gen"] button:hover,
section[data-testid="stSidebar"] div[class*="st-key-principal_gen"] button:hover {
    background: #3d5166 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.24) !important;
}
section[data-testid="stSidebar"] div[class*="st-key-teacher_gen"] button *,
section[data-testid="stSidebar"] div[class*="st-key-principal_gen"] button * {
    color: #ffffff !important;
    visibility: visible !important;
}
/* ✦ icon via ::before — theme-proof on both buttons */
section[data-testid="stSidebar"] div[class*="st-key-teacher_gen"] button::before,
section[data-testid="stSidebar"] div[class*="st-key-principal_gen"] button::before {
    content: "✦";
    font-size: 0.85rem;
    color: #ffffff;
    flex-shrink: 0;
    visibility: visible !important;
    margin-right: 0.35rem;
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
   CHECKBOX — label text, box size, spacing, tick colour
   ═══════════════════════════════════════════════════ */

/* Label text — identical to Select All / field-label-text
   Target every element Streamlit may use: span, p, or bare div  */
section[data-testid="stSidebar"] .stCheckbox label span,
section[data-testid="stSidebar"] .stCheckbox label p,
section[data-testid="stSidebar"] .stCheckbox label > div,
section[data-testid="stSidebar"] [data-baseweb="checkbox"] > div,
section[data-testid="stSidebar"] [data-baseweb="checkbox"] > div p,
section[data-testid="stSidebar"] [data-baseweb="checkbox"] > div span {
    font-size: 0.70rem !important;
    color: #5a5754 !important;
    font-weight: 500 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif !important;
}

/* Shrink the tick-box itself */
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"] {
    width: 13px !important;
    height: 13px !important;
    min-width: 13px !important;
    min-height: 13px !important;
    border-radius: 3px !important;
    flex-shrink: 0 !important;
}

/* Checked state — dark grey fill, white tick.
   BaseUI injects background as an inline style attribute which
   defeats stylesheet !important rules.  The ::before pseudo-element
   is a child layer that paints ON TOP of the parent's own background,
   so it covers the orange regardless of how it was applied.          */
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"] {
    border-color: #c8c4be !important;   /* unchecked border warm grey */
}
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] {
    border-color: #2c3e50 !important;
    background: #2c3e50 !important;
    background-color: #2c3e50 !important;
    position: relative !important;
    overflow: hidden !important;
}
/* ::before covers any BaseUI inline-style orange injection */
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"]::before {
    content: "" !important;
    position: absolute !important;
    inset: 0 !important;
    background: #2c3e50 !important;
    background-color: #2c3e50 !important;
    z-index: 0 !important;
    pointer-events: none !important;
}
/* Also target the inner div BaseUI may use as the colour layer */
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] > div {
    background: #2c3e50 !important;
    background-color: #2c3e50 !important;
}
/* SVG sits above all layers so the tick stays white */
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] svg {
    position: relative !important;
    z-index: 1 !important;
    width: 10px !important;
    height: 10px !important;
}
section[data-testid="stSidebar"] [data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] svg path {
    fill: #ffffff !important;
    stroke: #ffffff !important;
}

/* Minimum row spacing between chapters */
section[data-testid="stSidebar"] .stCheckbox {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
}
section[data-testid="stSidebar"] .stCheckbox > label {
    padding-top: 0.03rem !important;
    padding-bottom: 0.03rem !important;
    min-height: 0 !important;
    line-height: 1.2 !important;
    gap: 0.35rem !important;
}
/* Collapse the flex gap on every vertical block that contains checkboxes.
   This is the real source of the large inter-row spacing in Streamlit —
   the parent block's gap property, not the checkbox's own margins.     */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(.stCheckbox) {
    gap: 0 !important;
}
/* Also zero the element-container wrapper Streamlit puts around each widget */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(.stCheckbox)
    > div[data-testid="element-container"] {
    margin: 0 !important;
    padding: 0 !important;
}

/* ═══════════════════════════════════════════════════
   SELECT ALL / DESELECT ALL  — workspace body (Plan workspace)
   Dark slate, matches Generate button
   ═══════════════════════════════════════════════════ */
div[class*="st-key-sel_all"] button,
div[class*="st-key-desel_all"] button {
    background: #2c3e50 !important;
    border: none !important;
    border-radius: 6px !important;
    color: #ffffff !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 10px !important;
}
div[class*="st-key-sel_all"] button:hover,
div[class*="st-key-desel_all"] button:hover {
    background: #3d5166 !important;
}
div[class*="st-key-sel_all"] button *,
div[class*="st-key-desel_all"] button * {
    color: #ffffff !important;
    visibility: visible !important;
}

/* ═══════════════════════════════════════════════════
   CHAPTER TILE CHECKBOXES — styled as clean tiles
   ═══════════════════════════════════════════════════ */
[data-testid="stMain"] div[class*="st-key-chk_"] label {
    background: #f5f3ef !important;
    border: 1px solid #d0cdc9 !important;
    border-radius: 8px !important;
    padding: 10px 12px !important;
    width: 100% !important;
    margin-bottom: 8px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: flex-start !important;
    gap: 8px !important;
    min-height: 52px !important;
}
[data-testid="stMain"] div[class*="st-key-chk_"] label:hover {
    border-color: #2c3e50 !important;
    background: #f0f3f6 !important;
}
[data-testid="stMain"] div[class*="st-key-chk_"] input:checked + label,
[data-testid="stMain"] div[class*="st-key-chk_"] [aria-checked="true"] ~ div {
    border-color: #2c3e50 !important;
    background: #f0f3f6 !important;
}
[data-testid="stMain"] div[class*="st-key-chk_"] label span,
[data-testid="stMain"] div[class*="st-key-chk_"] label p {
    font-size: 0.76rem !important;
    color: #2c2a27 !important;
    line-height: 1.35 !important;
}

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
   ASK ARUVI PANEL  — session-state driven, fixed right
   ═══════════════════════════════════════════════════ */
/* Toggle button — fixed vertical tab on right edge */
div[class*="st-key-ask_aruvi_toggle"] button {
    position: fixed !important;
    right: 0 !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    z-index: 99999 !important;
    width: 28px !important;
    height: 88px !important;
    padding: 0 !important;
    border-radius: 6px 0 0 6px !important;
    border: 1px solid #d9d6d0 !important;
    border-right: none !important;
    background: #f5f3ef !important;
    color: #5a5754 !important;
    font-size: 0.62rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    writing-mode: vertical-rl !important;
    white-space: nowrap !important;
    cursor: pointer !important;
    box-shadow: -2px 0 6px rgba(0,0,0,0.06) !important;
}
div[class*="st-key-ask_aruvi_toggle"] button:hover {
    background: #eae8e4 !important;
    color: #2c2a27 !important;
    border-color: #2c3e50 !important;
}
div[class*="st-key-ask_aruvi_toggle"] button * {
    writing-mode: vertical-rl !important;
    text-orientation: mixed !important;
}
/* Panel — slides in from right */
.aruvi-chat-panel {
    position: fixed;
    top: 72px;
    right: 0;
    width: 260px;
    height: calc(100vh - 72px);
    background: #f5f3ef;
    border-left: 1px solid #d9d6d0;
    z-index: 99998;
    display: flex;
    flex-direction: column;
    box-shadow: -4px 0 16px rgba(0,0,0,0.08);
}
.aruvi-chat-panel-header {
    padding: 14px 16px 10px;
    border-bottom: 1px solid #d9d6d0;
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a5754;
}
.aruvi-chat-panel-body {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    font-size: 0.72rem;
    color: #9c9693;
    text-align: center;
    line-height: 1.6;
}

/* ═══════════════════════════════════════════════════
   EXPORT BUTTONS
   ═══════════════════════════════════════════════════ */
div[class*="st-key-export_docx"] button,
div[class*="st-key-export_pdf"] button {
    background: transparent !important;
    border: 1px solid #2c3e50 !important;
    border-radius: 6px !important;
    color: #2c3e50 !important;
    font-size: 0.76rem !important;
    font-weight: 500 !important;
    height: 32px !important;
    min-height: 32px !important;
}
div[class*="st-key-export_docx"] button:hover,
div[class*="st-key-export_pdf"] button:hover {
    background: #2c3e50 !important;
    color: #ffffff !important;
}
div[class*="st-key-export_docx"] button *,
div[class*="st-key-export_pdf"] button * {
    color: inherit !important;
    visibility: visible !important;
}

/* ═══════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
   ═══════════════════════════════════════════════════ */
#MainMenu, footer { visibility: hidden; }

</style>

""", unsafe_allow_html=True)

# ── MutationObserver: override BaseUI inline-style orange on checkboxes ───────
st.markdown("""<script>
(function() {
    var TARGET_COLOR = '#2c3e50';
    var SIDEBAR_SELECTOR = 'section[data-testid="stSidebar"]';

    function fixCheckbox(el) {
        if (el && el.getAttribute('role') === 'checkbox' &&
                el.getAttribute('aria-checked') === 'true') {
            el.style.setProperty('background', TARGET_COLOR, 'important');
            el.style.setProperty('background-color', TARGET_COLOR, 'important');
            el.style.setProperty('border-color', TARGET_COLOR, 'important');
            var inner = el.querySelector('div');
            if (inner) {
                inner.style.setProperty('background', TARGET_COLOR, 'important');
                inner.style.setProperty('background-color', TARGET_COLOR, 'important');
            }
        }
    }

    function fixAll() {
        var sidebar = document.querySelector(SIDEBAR_SELECTOR);
        if (!sidebar) return;
        sidebar.querySelectorAll('[role="checkbox"][aria-checked="true"]')
               .forEach(fixCheckbox);
    }

    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            if (m.type === 'attributes') {
                fixCheckbox(m.target);
            } else {
                m.addedNodes.forEach(function(n) {
                    if (n.nodeType === 1) {
                        if (n.getAttribute && n.getAttribute('role') === 'checkbox') {
                            fixCheckbox(n);
                        }
                        n.querySelectorAll && n.querySelectorAll('[role="checkbox"]')
                                               .forEach(fixCheckbox);
                    }
                });
            }
        });
    });

    function attach() {
        var sidebar = document.querySelector(SIDEBAR_SELECTOR);
        if (sidebar) {
            fixAll();
            observer.observe(sidebar, {
                childList: true, subtree: true,
                attributes: true, attributeFilter: ['aria-checked', 'style']
            });
        } else {
            setTimeout(attach, 300);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attach);
    } else {
        attach();
    }
})();
</script>""", unsafe_allow_html=True)

# ── Watermark: inject separately so we can embed the base64 data URI ──────────
if WATERMARK_SRC:
    st.markdown(f"""<style>
[data-testid="stMain"]::before {{
    content: "";
    position: fixed;
    inset: 0;
    background-image: url('{WATERMARK_SRC}');
    background-repeat: no-repeat;
    background-position: center center;
    background-size: 480px auto;
    opacity: 0.025;
    filter: grayscale(100%);
    pointer-events: none;
    z-index: 0;
}}
</style>""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_all_chapters(grade: str, subject: str) -> list[dict]:
    """Load chapter mapping JSONs for the given grade and subject."""
    subj_f  = subject_to_folder(subject)
    grade_f = grade_to_folder(grade)
    mappings_dir = PROJECT_ROOT / f"mirror/chapters/{subj_f}/{grade_f}/mappings"
    chapters = []
    if not mappings_dir.exists():
        return []
    for path in sorted(mappings_dir.glob("ch_*_mapping.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            chapters.append(data)
        except Exception:
            continue
    chapters.sort(key=lambda c: c["chapter_number"])
    return chapters


if st.session_state.grade and st.session_state.subject:
    chapters = load_all_chapters(st.session_state.grade, st.session_state.subject)
else:
    chapters = []


def ch_label(ch: dict) -> str:
    return f"Ch {ch['chapter_number']:02d} — {ch['chapter_title']}"


def ch_short(ch: dict) -> str:
    t = ch["chapter_title"]
    # Drop any subtitle after " - " or ":" — whichever comes first
    for sep in [" - ", ":"]:
        if sep in t:
            t = t.split(sep)[0].strip()
            break
    return f"Ch {ch['chapter_number']:02d} · {t}"


# ── Period-row callbacks (run before script on each interaction) ───────────────

def _cb_add_row():
    _new_id = st.session_state["_next_row_id"]
    st.session_state["_next_row_id"] = _new_id + 1
    st.session_state["period_rows"] = st.session_state["period_rows"] + [_new_id]

def _cb_del_row(rid):
    st.session_state["period_rows"] = [
        r for r in st.session_state["period_rows"] if r != rid
    ]

def _cb_inc_cnt(rid, delta):
    st.session_state[f"cnt_{rid}"] = max(
        1, min(999, st.session_state.get(f"cnt_{rid}", 1) + delta)
    )

def _cb_add_row_p():
    _new_id = st.session_state["_next_row_id_p"]
    st.session_state["_next_row_id_p"] = _new_id + 1
    st.session_state["period_rows_p"] = st.session_state["period_rows_p"] + [_new_id]

def _cb_del_row_p(rid):
    st.session_state["period_rows_p"] = [
        r for r in st.session_state["period_rows_p"] if r != rid
    ]


# ── Session state ─────────────────────────────────────────────────────────────

if "role"              not in st.session_state: st.session_state.role              = "Plan"
if "grade"             not in st.session_state: st.session_state.grade             = None
if "subject"           not in st.session_state: st.session_state.subject           = None

# Teacher
if "period_blocks"     not in st.session_state: st.session_state.period_blocks     = [{"id": 0, "duration": None, "count": None}]
if "next_block_id"     not in st.session_state: st.session_state.next_block_id     = 1
if "teacher_generated" not in st.session_state: st.session_state.teacher_generated = False
if "teacher_ch_idx"    not in st.session_state: st.session_state.teacher_ch_idx    = None

# Principal
if "principal_period_blocks"  not in st.session_state: st.session_state.principal_period_blocks  = [{"id": 0, "duration": None, "count": None}]
if "principal_next_block_id"  not in st.session_state: st.session_state.principal_next_block_id  = 1
if "ch_selected"              not in st.session_state: st.session_state.ch_selected              = {ch["chapter_number"]: False for ch in chapters}
if "ch_periods"               not in st.session_state: st.session_state.ch_periods               = {ch["chapter_number"]: 6    for ch in chapters}
if "principal_generated"      not in st.session_state: st.session_state.principal_generated      = False
if "ask_aruvi_open"           not in st.session_state: st.session_state.ask_aruvi_open           = False
if "lpa_confirm_pending"      not in st.session_state: st.session_state.lpa_confirm_pending      = False
if "lpa_result"               not in st.session_state: st.session_state.lpa_result               = None
if "lpa_generating"           not in st.session_state: st.session_state.lpa_generating           = False

has_chapter_data = len(chapters) > 0

# ── Fixed top nav bar ─────────────────────────────────────────────────────────
# Pure HTML pills — no Streamlit radio widget, no orange circles.
# onclick calls aruviSetRole() which clicks a hidden st.button in the sidebar.

t_active = "active" if st.session_state.role == "Teach" else ""
p_active = "active" if st.session_state.role == "Plan"  else ""

# Build shared query params so grade/subject survive a pill-click reload
import urllib.parse as _up
_qs_dict = {}
if st.session_state.grade:   _qs_dict["grade"]   = st.session_state.grade
if st.session_state.subject: _qs_dict["subject"]  = st.session_state.subject
_ch_idx = st.session_state.get("teacher_ch_idx")
if _ch_idx is not None:      _qs_dict["ch"]       = _ch_idx
_qs = _up.urlencode(_qs_dict)
_sep = "&" if _qs else ""
_t_href = f"?role=Teach{_sep}{_qs}"
_p_href = f"?role=Plan{_sep}{_qs}"

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
      <a class="aruvi-pill {p_active}" href="{_p_href}">Plan</a>
      <a class="aruvi-pill {t_active}" href="{_t_href}">Teach</a>
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

    # ── Grade selector — label above, value below (left-aligned) ─────────────
    _g_icon = f'<img src="{GRADE_SRC}" class="field-icon-grade" alt="">' if GRADE_SRC else ""
    st.markdown(
        f'<div class="sidebar-field-label">{_g_icon}'
        f'<span class="field-label-text">Grade</span></div>',
        unsafe_allow_html=True,
    )
    grade = st.selectbox(
        "Grade",
        GRADES,
        index=None if st.session_state.grade is None
              else GRADES.index(st.session_state.grade),
        placeholder="Choose a grade",
        label_visibility="collapsed",
        key="grade_select",
    )
    if grade != st.session_state.grade:
        st.session_state.grade               = grade
        st.session_state.teacher_ch_idx      = None
        st.session_state.teacher_generated   = False
        st.session_state.principal_generated = False
        if grade:
            st.query_params["grade"] = grade
        st.rerun()

    # ── Subject selector — label above, value below (left-aligned) ───────────
    _s_icon = f'<img src="{SUBJECT_SRC}" class="field-icon" alt="">' if SUBJECT_SRC else ""
    st.markdown(
        f'<div class="sidebar-field-label">{_s_icon}'
        f'<span class="field-label-text">Subject</span></div>',
        unsafe_allow_html=True,
    )
    subject = st.selectbox(
        "Subject",
        SUBJECTS,
        index=None if st.session_state.subject is None
              else SUBJECTS.index(st.session_state.subject),
        placeholder="Choose a subject",
        label_visibility="collapsed",
        key="subject_select",
    )
    if subject != st.session_state.subject:
        st.session_state.subject             = subject
        st.session_state.teacher_ch_idx      = None
        st.session_state.teacher_generated   = False
        st.session_state.principal_generated = False
        if subject:
            st.query_params["subject"] = subject
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
    elif st.session_state.role == "Teach":

        st.divider()

        # Chapter selector — label above, value below (left-aligned)
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
            placeholder="Choose a chapter",
            label_visibility="collapsed",
            key="teacher_ch_select",
        )
        if sel_label is not None:
            new_idx = ch_labels.index(sel_label)
            if new_idx != st.session_state.teacher_ch_idx:
                st.session_state.teacher_ch_idx    = new_idx
                st.session_state.teacher_generated = False
                st.query_params["ch"] = str(new_idx)

        st.divider()

        # ── Available Time section ─────────────────────────────────────────────
        # "Available time" label — uses time.png icon
        if TIME_SRC:
            time_icon_html = f'<img src="{TIME_SRC}" class="period-icon" alt="⏱">'
        else:
            time_icon_html = ''
        st.markdown(
            f'<div class="sect-label">{time_icon_html}'
            f'<span>Available time</span></div>',
            unsafe_allow_html=True,
        )

        # ── Multi-row period state bootstrap ──────────────────────────────────
        if "period_rows" not in st.session_state:
            st.session_state["period_rows"] = [0]
            st.session_state["_next_row_id"] = 1

        # Ensure cnt is initialised for every active row (new rows only)
        for _rid in st.session_state["period_rows"]:
            if f"cnt_{_rid}" not in st.session_state:
                st.session_state[f"cnt_{_rid}"] = 1

        # Inject dynamic CSS: add-row button shows period.png icon
        if PERIOD_SRC:
            st.markdown(
                f"""<style>
section[data-testid="stSidebar"] div[class*="st-key-add_period_row"] button {{
    background: url('{PERIOD_SRC}') center / 16px 16px no-repeat transparent !important;
    color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: 22px !important;
}}
section[data-testid="stSidebar"] div[class*="st-key-add_period_row"] button:hover {{
    opacity: 0.60;
    background: url('{PERIOD_SRC}') center / 16px 16px no-repeat transparent !important;
}}
</style>""",
                unsafe_allow_html=True,
            )

        # ── Column header labels — rendered once above the first row ──────────
        _hc_dur, _hc_cnt, _hc_add = st.columns([4, 4, 1])
        with _hc_dur:
            st.markdown('<div style="font-size:0.68rem;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;color:#5a5754;margin-bottom:0.15rem;">Mins / Period</div>', unsafe_allow_html=True)
        with _hc_cnt:
            st.markdown('<div style="font-size:0.68rem;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;color:#5a5754;margin-bottom:0.15rem;">No. of Periods</div>', unsafe_allow_html=True)
        with _hc_add:
            st.button(
                "⊕",
                key="add_period_row",
                use_container_width=True,
                help="Add another period type",
                on_click=_cb_add_row,
            )

        # ── Period rows — all [4, 4, 1]; first row's delete slot stays empty ──
        for _rid in st.session_state["period_rows"]:
            _is_first = (_rid == st.session_state["period_rows"][0])
            c_dur, c_cnt, c_del = st.columns([4, 4, 1])

            with c_dur:
                st.selectbox("Time per period", options=DURATION_OPTIONS, index=DURATION_OPTIONS.index(40),
                             label_visibility="collapsed", key=f"dur_sel_{_rid}")

            with c_cnt:
                cm, cv, cp = st.columns([1, 3, 1])
                with cm:
                    st.button("−", key=f"minus_{_rid}",
                              use_container_width=True,
                              on_click=_cb_inc_cnt, args=(_rid, -1))
                with cv:
                    st.number_input(
                        "count",
                        min_value=1,
                        max_value=999,
                        step=1,
                        label_visibility="collapsed",
                        key=f"cnt_{_rid}",
                    )
                with cp:
                    st.button("+", key=f"plus_{_rid}",
                              use_container_width=True,
                              on_click=_cb_inc_cnt, args=(_rid, 1))

            with c_del:
                if not _is_first:
                    st.button("×", key=f"del_{_rid}",
                              use_container_width=True,
                              on_click=_cb_del_row, args=(_rid,))

        # Total across all rows
        total_m = sum(
            (st.session_state.get(f"dur_sel_{r}") or 0) * (st.session_state.get(f"cnt_{r}") or 0)
            for r in st.session_state["period_rows"]
        )
        if total_m > 0:
            _h, _min = divmod(total_m, 60)
            if _h == 0:
                _time_str = f"{_min} minute{'s' if _min != 1 else ''}"
            elif _min == 0:
                _time_str = f"{_h} hour{'s' if _h != 1 else ''}"
            else:
                _time_str = f"{_h} hour{'s' if _h != 1 else ''} and {_min} minute{'s' if _min != 1 else ''}"
            st.markdown(
                f'<div style="font-size:0.79rem;color:#3d3b38;margin:0.4rem 0 0.25rem 0;">'
                f'Total · {_time_str}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        can_gen = (
            len(st.session_state.get("period_rows", [])) > 0
            and all(
                (st.session_state.get(f"dur_sel_{r}") or 0) >= 1
                and (st.session_state.get(f"cnt_{r}") or 0) >= 1
                for r in st.session_state.get("period_rows", [])
            )
        )
        if st.button(
            "Generate Lesson Plan & Assessment",
            disabled=not can_gen,
            type="primary",
            use_container_width=True,
            key="teacher_gen",
        ):
            st.session_state.lpa_confirm_pending = True
            st.session_state.lpa_result          = None
            st.rerun()

    # ── Principal inputs ──────────────────────────────────────────────────────
    else:

        # ── Period Budget section — same block architecture as Teacher ─────────
        if FULL_PERIOD_SRC:
            fp_icon_html = f'<img src="{FULL_PERIOD_SRC}" class="period-icon" alt="">'
        else:
            fp_icon_html = ''
        st.markdown(
            f'<div class="sect-label" style="margin-bottom:0.45rem;">{fp_icon_html}'
            f'<span>Period Budget</span></div>',
            unsafe_allow_html=True,
        )

        # ── Multi-row period state bootstrap (Principal) ──────────────────────
        if "period_rows_p" not in st.session_state:
            st.session_state["period_rows_p"] = [0]
            st.session_state["_next_row_id_p"] = 1

        # Ensure cnt is initialised (default 1) for every active row (new rows only)
        for _rid_p in st.session_state["period_rows_p"]:
            if f"cnt_p{_rid_p}" not in st.session_state:
                st.session_state[f"cnt_p{_rid_p}"] = 1

        # Dynamic CSS: ⊕ add-row button shows period.png icon (Plan)
        if PERIOD_SRC:
            st.markdown(
                f"""<style>
section[data-testid="stSidebar"] div[class*="st-key-add_period_row_p"] button {{
    background: url('{PERIOD_SRC}') center / 16px 16px no-repeat transparent !important;
    color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: 22px !important;
}}
section[data-testid="stSidebar"] div[class*="st-key-add_period_row_p"] button:hover {{
    opacity: 0.60;
    background: url('{PERIOD_SRC}') center / 16px 16px no-repeat transparent !important;
}}
</style>""",
                unsafe_allow_html=True,
            )

        # ── Column header labels — rendered once above the first row ──────────
        _hc_dur_p, _hc_cnt_p, _hc_add_p = st.columns([4, 4, 1])
        with _hc_dur_p:
            st.markdown('<div style="font-size:0.68rem;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;color:#5a5754;margin-bottom:0.15rem;">Mins / Period</div>', unsafe_allow_html=True)
        with _hc_cnt_p:
            st.markdown('<div style="font-size:0.68rem;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;color:#5a5754;margin-bottom:0.15rem;">No. of Periods</div>', unsafe_allow_html=True)
        with _hc_add_p:
            st.button(
                "⊕",
                key="add_period_row_p",
                use_container_width=True,
                help="Add another period type",
                on_click=_cb_add_row_p,
            )

        # ── Period rows — all [4, 4, 1]; first row's delete slot stays empty ──
        for _rid_p in st.session_state["period_rows_p"]:
            _is_first_p = (_rid_p == st.session_state["period_rows_p"][0])
            pc_dur, pc_cnt, pc_del = st.columns([4, 4, 1])

            with pc_dur:
                st.selectbox("Time per period", options=DURATION_OPTIONS, index=DURATION_OPTIONS.index(40),
                             label_visibility="collapsed", key=f"dur_sel_p{_rid_p}")

            with pc_cnt:
                st.number_input(
                    "count",
                    min_value=1,
                    max_value=999,
                    step=1,
                    label_visibility="collapsed",
                    key=f"cnt_p{_rid_p}",
                )

            with pc_del:
                if not _is_first_p:
                    st.button("×", key=f"del_p{_rid_p}",
                              use_container_width=True,
                              on_click=_cb_del_row_p, args=(_rid_p,))

        # Total across all rows
        p_total_m = sum(
            (st.session_state.get(f"dur_sel_p{r}") or 0) * (st.session_state.get(f"cnt_p{r}") or 0)
            for r in st.session_state["period_rows_p"]
        )
        if p_total_m > 0:
            _ph, _pmin = divmod(p_total_m, 60)
            if _ph == 0:
                _p_time_str = f"{_pmin} minute{'s' if _pmin != 1 else ''}"
            elif _pmin == 0:
                _p_time_str = f"{_ph} hour{'s' if _ph != 1 else ''}"
            else:
                _p_time_str = f"{_ph} hour{'s' if _ph != 1 else ''} and {_pmin} minute{'s' if _pmin != 1 else ''}"
            st.markdown(
                f'<div style="font-size:0.79rem;color:#3d3b38;margin:0.4rem 0 0.25rem 0;">'
                f'Total · {_p_time_str}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        if st.button("Generate Allocation Report", type="primary",
                     use_container_width=True, key="principal_gen"):
            any_selected = any(
                st.session_state.ch_selected.get(ch["chapter_number"], False)
                for ch in chapters
            )
            if not any_selected:
                st.warning("Please select at least one chapter before generating.")
            else:
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
    if st.session_state.grade is None or st.session_state.subject is None:
        _msg = "Choose a grade and subject to get started."
    else:
        _msg = f"No content available yet for {st.session_state.subject}, {st.session_state.grade}."
    st.markdown(
        f'<div class="ws-placeholder">{_msg}</div>',
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════
#  TEACHER WORKSPACE
#  Change 2: tabs = Competencies · Lesson Plan · Assessment
# ═════════════════════════════════════════════════
elif st.session_state.role == "Teach":

    if st.session_state.teacher_ch_idx is None:
        st.markdown(
            '<div class="ws-placeholder">Choose a chapter to get started.</div>',
            unsafe_allow_html=True,
        )
    else:
        selected_ch = chapters[st.session_state.teacher_ch_idx]

        # ── Confirmation panel ────────────────────────────────────────────────
        if st.session_state.lpa_confirm_pending:
            period_rows = st.session_state.get("period_rows", [0])
            sched_str   = format_period_schedule(
                period_rows, st.session_state
            )
            st.markdown(
                '<div style="background:#fef8f5;border:1px solid #e8d0c0;'
                'border-radius:8px;padding:1.2rem 1.5rem;margin-bottom:1.5rem;">'
                '<div style="font-size:0.72rem;font-weight:500;letter-spacing:0.08em;'
                'text-transform:uppercase;color:#8b5e4a;margin-bottom:0.75rem;">'
                'Confirm Generation</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"""
| Parameter | Value |
|---|---|
| Grade | {st.session_state.grade} |
| Subject | {st.session_state.subject} |
| Chapter | {selected_ch['chapter_title']} |
| Chapter weight | {selected_ch.get('chapter_weight', '—')} |
""")
            st.code(sched_str, language=None)
            st.markdown('</div>', unsafe_allow_html=True)

            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button(
                    "Confirm — Generate",
                    type="primary",
                    use_container_width=True,
                    key="lpa_confirm",
                ):
                    st.session_state.lpa_confirm_pending = False
                    st.session_state.lpa_generating      = True
                    st.rerun()
            with col_cancel:
                if st.button(
                    "Cancel",
                    use_container_width=True,
                    key="lpa_cancel",
                ):
                    st.session_state.lpa_confirm_pending = False
                    st.rerun()

        # ── Generation ────────────────────────────────────────────────────────
        if st.session_state.lpa_generating:
            with st.spinner("Generating lesson plan and assessment — this takes about 30 seconds…"):
                result = generate_lpa(
                    grade       = st.session_state.grade,
                    subject     = st.session_state.subject,
                    chapter     = selected_ch,
                    period_rows = st.session_state.get("period_rows", [0]),
                    session     = st.session_state,
                )
            st.session_state.lpa_result        = result
            st.session_state.lpa_generating    = False
            st.session_state.teacher_generated = True
            st.rerun()

        # ── Workspace tabs ────────────────────────────────────────────────────
        tab_comp, tab_lp, tab_assess = st.tabs(
            ["Competencies", "Lesson Plan", "Assessment"]
        )

        with tab_comp:
            st.markdown(
                f'<div class="ch-title">{selected_ch["chapter_title"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="ch-meta">{st.session_state.grade} · {st.session_state.subject} · '
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
            result = st.session_state.lpa_result
            if result is None:
                st.markdown(
                    '<div class="ws-placeholder">'
                    'Select a chapter and period budget, then generate.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif result.get("error"):
                st.error(f"Generation failed: {result['error']}")
            else:
                # ── Export buttons ────────────────────────────────────────────────────────
                _exp_col1, _exp_col2, _exp_spacer = st.columns([1, 1, 3])

                _chapter_export = chapters[st.session_state.teacher_ch_idx]
                _safe_title = re.sub(r"[^\w\s-]", "", _chapter_export.get("chapter_title", "chapter")).strip().replace(" ", "_")[:40]
                _filename_stem = f"Aruvi_{_safe_title}"

                with _exp_col1:
                    st.download_button(
                        label="⬇ Download DOCX",
                        data=generate_docx_bytes_lp(
                            result, _chapter_export,
                            st.session_state.grade, st.session_state.subject,
                        ),
                        file_name=f"{_filename_stem}_LP.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="export_docx",
                        use_container_width=True,
                    )

                with _exp_col2:
                    st.download_button(
                        label="⬇ Download PDF",
                        data=generate_pdf_bytes_lp(
                            result, _chapter_export,
                            st.session_state.grade, st.session_state.subject,
                        ),
                        file_name=f"{_filename_stem}_LP.pdf",
                        mime="application/pdf",
                        key="export_pdf",
                        use_container_width=True,
                    )

                st.markdown('<div style="height:0.75rem;"></div>', unsafe_allow_html=True)

                st.markdown(result["lesson_plan"])
                st.markdown(
                    f'<div style="font-size:0.70rem;color:#9c9693;margin-top:2rem;'
                    f'border-top:1px solid #e8e5e0;padding-top:0.75rem;">'
                    f'Tokens — input: {result["input_tokens"]:,} · '
                    f'output: {result["output_tokens"]:,} · '
                    f'cost: ₹{result["cost_inr"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        with tab_assess:
            result = st.session_state.lpa_result
            if result is None:
                st.markdown(
                    '<div class="ws-placeholder">'
                    'Generate a lesson plan first — the assessment follows automatically.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif result.get("error"):
                st.error(f"Generation failed: {result['error']}")
            else:
                # ── Export buttons ────────────────────────────────────────────────────────
                _exp_col1a, _exp_col2a, _exp_spacer_a = st.columns([1, 1, 3])

                _chapter_export_a = chapters[st.session_state.teacher_ch_idx]
                _safe_title_a = re.sub(r"[^\w\s-]", "", _chapter_export_a.get("chapter_title", "chapter")).strip().replace(" ", "_")[:40]
                _filename_stem_a = f"Aruvi_{_safe_title_a}"

                with _exp_col1a:
                    st.download_button(
                        label="⬇ Download DOCX",
                        data=generate_docx_bytes_assess(
                            result, _chapter_export_a,
                            st.session_state.grade, st.session_state.subject,
                        ),
                        file_name=f"{_filename_stem_a}_Assessment.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="export_docx_a",
                        use_container_width=True,
                    )

                with _exp_col2a:
                    st.download_button(
                        label="⬇ Download PDF",
                        data=generate_pdf_bytes_assess(
                            result, _chapter_export_a,
                            st.session_state.grade, st.session_state.subject,
                        ),
                        file_name=f"{_filename_stem_a}_Assessment.pdf",
                        mime="application/pdf",
                        key="export_pdf_a",
                        use_container_width=True,
                    )

                st.markdown('<div style="height:0.75rem;"></div>', unsafe_allow_html=True)

                st.markdown(result["assessment"])

# ═════════════════════════════════════════════════
#  PLAN WORKSPACE
# ═════════════════════════════════════════════════
else:

    # ── Chapter selection panel (always visible, above tabs) ──────────────────

    # Header row: label left, Select All / Deselect All right
    _cs_head_l, _cs_head_r = st.columns([1, 1])
    with _cs_head_l:
        _ch_sel_icon = f'<img src="{CHAPTER_SRC}" class="field-icon" alt="">' if CHAPTER_SRC else ''
        st.markdown(
            f'<div class="sect-label" style="margin-bottom:0;">{_ch_sel_icon}'
            f'<span>Chapter Selection</span></div>',
            unsafe_allow_html=True,
        )
    with _cs_head_r:
        _sa2, _da2 = st.columns(2)
        with _sa2:
            if st.button("Select All", key="sel_all", use_container_width=True):
                for ch in chapters:
                    st.session_state.ch_selected[ch["chapter_number"]] = True
                    st.session_state[f"chk_{ch['chapter_number']}"] = True
                st.rerun()
        with _da2:
            if st.button("Deselect All", key="desel_all", use_container_width=True):
                for ch in chapters:
                    st.session_state.ch_selected[ch["chapter_number"]] = False
                    st.session_state[f"chk_{ch['chapter_number']}"] = False
                st.rerun()

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

    # 3-column chapter tile grid
    _cols = st.columns(3)
    for _i, ch in enumerate(chapters):
        ch_num = ch["chapter_number"]
        _is_sel = st.session_state.get(f"chk_{ch_num}",
                  st.session_state.ch_selected.get(ch_num, False))
        with _cols[_i % 3]:
            _new_val = st.checkbox(
                f"Ch {ch_num:02d} · {ch['chapter_title']}",
                value=_is_sel,
                key=f"chk_{ch_num}",
            )
            if _new_val != _is_sel:
                st.session_state.ch_selected[ch_num] = _new_val
                st.rerun()

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    st.divider()

    # ── Allocation tabs ────────────────────────────────────────────────────────
    tab_alloc, tab_cov = st.tabs(["Period Allocation", "Competency Report"])

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

# ── Ask Aruvi toggle button (always visible, fixed to right edge) ─────────────
_toggle_label = "Close" if st.session_state.ask_aruvi_open else "Ask Aruvi"
if st.button(_toggle_label, key="ask_aruvi_toggle", help="Ask Aruvi"):
    st.session_state.ask_aruvi_open = not st.session_state.ask_aruvi_open
    st.rerun()

# ── Ask Aruvi panel content (shown when open) ─────────────────────────────────
if st.session_state.ask_aruvi_open:
    st.markdown(
        '<div class="aruvi-chat-panel">'
        '<div class="aruvi-chat-panel-header">Ask Aruvi</div>'
        '<div class="aruvi-chat-panel-body">Chat coming soon</div>'
        '</div>',
        unsafe_allow_html=True,
    )
