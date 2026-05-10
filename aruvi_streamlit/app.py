from dotenv import load_dotenv
load_dotenv("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi/.env")

import base64
import csv
import io
import json
import re
from datetime import datetime, date
from pathlib import Path
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

import math
import threading
import queue

import uuid
import streamlit as st
import streamlit.components.v1 as components
from streamlit.runtime.scriptrunner import add_script_run_ctx
import anthropic
import os
# ── Ask Aruvi backend toggle ──────────────────────────────────────────────────
# Set USE_MANAGED_AGENT = True  → new managed-agent path (ask_aruvi_agent.py)
# Set USE_MANAGED_AGENT = False → original Haiku path  (ask_aruvi_qa.py)
# The old module is NOT deleted — flip the flag to revert instantly.
USE_MANAGED_AGENT = False

if USE_MANAGED_AGENT:
    from ask_aruvi_agent import ask as aruvi_ask          # ← managed agent
else:
    from ask_aruvi_qa import ask as aruvi_ask             # ← original Haiku (immobilised)

from ask_aruvi_feedback import write_thumbs_feedback, write_general_feedback

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
    """Return the folder name for a grade — matches the roman-numeral dirs in mirror/."""
    _mapping = {
        "Grade I":    "i",    "Grade II":   "ii",   "Grade III": "iii",
        "Grade IV":   "iv",   "Grade V":    "v",    "Grade VI":  "vi",
        "Grade VII":  "vii",  "Grade VIII": "viii",
        "Grade IX":   "ix",   "Grade X":    "x",
    }
    return _mapping.get(grade, grade.lower().replace("grade ", ""))

def subject_to_folder(subject: str) -> str:
    mapping = {
        "Social Science": "social_sciences",
        "Mathematics":    "mathematics",
        "Science":        "science",
        "English":        "english",
        "Second Language":"languages",
        "EVS":            "evs",
    }
    return mapping.get(subject, subject.lower().replace(" ", "_"))

# Subjects whose chapter summaries are JSON (structured for downstream LP/A
# constitutions). All others are plain .txt.
_JSON_SUMMARY_SUBJECTS = {"mathematics", "english"}

# ── Path resolver ─────────────────────────────────────────────────────────────

def resolve_paths(grade: str, subject: str, chapter_number: int) -> dict:
    stage  = get_stage(grade)
    grade_f = grade_to_folder(grade)
    subj_f  = subject_to_folder(subject)
    mirror  = PROJECT_ROOT / "mirror"
    nn      = f"{chapter_number:02d}"
    return {
        "lp_constitution":  mirror / f"constitutions/lesson_plan/{subj_f}/lesson_plan_constitution.txt",
        "assessment_const": mirror / f"constitutions/assessment/{subj_f}/assessment_constitution.txt",
        "pedagogy":         mirror / f"framework/{subj_f}/{stage}/pedagogy_{stage}_{subj_f}.txt",
        # Mathematics and English summaries are .json (structured for LP/A
        # constitutions); all others are plain .txt.
        "chapter_summary":  (
            mirror / f"chapters/{subj_f}/{grade_f}/summaries/ch_{nn}_summary.json"
            if subj_f in _JSON_SUMMARY_SUBJECTS
            else mirror / f"chapters/{subj_f}/{grade_f}/summaries/ch_{nn}_summary.txt"
        ),
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

ASK_ARUVI_LOG_PATH = PROJECT_ROOT / "knowledge_commons/evaluation_mappings/ask_aruvi.csv"

def log_ask_aruvi_tokens(
    session_id:    str,
    query:         str,
    category:      str,
    tab:           str,
    subject:       str,
    grade:         str,
    input_tokens:  int,
    output_tokens: int,
) -> None:
    try:
        cost_inr      = calculate_cost_inr("claude-haiku-4-5-20251001", input_tokens, output_tokens)
        query_snippet = query[:60]
        category_val  = category if category else "none"
        write_header  = not ASK_ARUVI_LOG_PATH.exists()
        with open(ASK_ARUVI_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow([
                    "timestamp", "session_id", "tab", "subject", "grade",
                    "category", "query_snippet",
                    "input_tokens", "output_tokens", "total_tokens", "cost_inr",
                ])
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                session_id,
                tab,
                subject,
                grade,
                category_val,
                query_snippet,
                input_tokens,
                output_tokens,
                input_tokens + output_tokens,
                cost_inr,
            ])
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

    lp = ""  # temporarily stubbed — export not yet updated for JSON shape
    # lp = result.get("lesson_plan", "")
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

    lp = ""  # temporarily stubbed — export not yet updated for JSON shape
    # lp = result.get("lesson_plan", "")

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

    asmt = ""  # temporarily stubbed — export not yet updated for JSON shape
    # asmt = result.get("assessment", "")
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

    asmt = ""  # temporarily stubbed — export not yet updated for JSON shape
    # asmt = result.get("assessment", "")
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

# ── Saved plans — local file storage ─────────────────────────────────────────

def _saved_plans_dir(grade: str, subject: str) -> Path:
    subj_f  = subject_to_folder(subject)
    grade_f = grade_to_folder(grade)
    d = PROJECT_ROOT / "mirror" / "saved_plans" / subj_f / grade_f
    d.mkdir(parents=True, exist_ok=True)
    return d

def save_plan(
    grade:       str,
    subject:     str,
    chapter:     dict,
    period_rows: list,
    session:     dict,
    result:      dict,
) -> None:
    d        = _saved_plans_dir(grade, subject)
    nn       = f"{chapter['chapter_number']:02d}"
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ch_{nn}_{ts}.json"
    sched    = format_period_schedule(period_rows, session)
    payload  = {
        "filename":               filename,
        "saved_at":               datetime.now().isoformat(timespec="seconds"),
        "grade":                  grade,
        "subject":                subject,
        "chapter_number":         chapter["chapter_number"],
        "chapter_title":          chapter.get("chapter_title", ""),
        "period_schedule_display": sched,
        "period_rows_snapshot": [
            {
                "id":       r,
                "duration": session.get(f"dur_sel_{r}", 40),
                "count":    session.get(f"cnt_{r}", 1),
            }
            for r in (period_rows or [])
        ],
        "result": {
            "lesson_plan":      result.get("lesson_plan", {}),
            "coverage_handoff": result.get("coverage_handoff", {}),
            "assessment_items": result.get("assessment_items", []),
            "input_tokens":     result.get("input_tokens", 0),
            "output_tokens":    result.get("output_tokens", 0),
            "cost_inr":         result.get("cost_inr", 0),
        },
    }
    (d / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def load_saved_plans(grade: str, subject: str) -> list:
    d = _saved_plans_dir(grade, subject)
    plans = []
    for f in sorted(d.glob("ch_*.json")):
        try:
            plans.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return plans

def delete_saved_plan(grade: str, subject: str, filename: str) -> None:
    d = _saved_plans_dir(grade, subject)
    target = d / filename
    try:
        target.unlink(missing_ok=True)
    except Exception:
        pass

def _build_lpa_prompts_english(
    grade: str,
    subject: str,
    chapter: dict,
    period_sched: str,
    paths: dict,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for English LP+A generation.

    English uses a two-axis schema (main_section × spine). The chapter
    summary is JSON (produced by the cowork prompt
    `chapter_summary_competency_mapping_english.md`) and is the source
    of truth for the LP and assessment. C-codes do not appear in LP/A
    output; the Allocate page reads `spine_to_cg.json` separately.
    """
    stage = get_stage(grade)

    lp_const     = read_file(paths["lp_constitution"])
    assess_const = read_file(paths["assessment_const"])
    pedagogy     = read_file(paths["pedagogy"])
    summary      = read_file(paths["chapter_summary"])

    # Stage-aware rubric depth (Assessment Constitution Rule 10).
    rubric_bullets = (
        "3"   if stage == "preparatory"
        else "3-4" if stage == "middle"
        else "4-5"
    )

    system_prompt = f"""You are Aruvi's English lesson plan and assessment generator.

You operate under two constitutions that govern every decision you make.
These constitutions are binding. No instruction in the user prompt overrides them.

=== ENGLISH LESSON PLAN CONSTITUTION ===
{lp_const}

=== ENGLISH ASSESSMENT CONSTITUTION ===
{assess_const}
"""

    user_prompt = f"""Generate a complete lesson plan and chapter assessment for the following English chapter.

=== NCF LANGUAGES PEDAGOGY ({stage} stage) ===
{pedagogy}

=== CHAPTER SUMMARY (JSON, two-axis: main_sections × spines) ===
{summary}

=== TEACHER PERIOD SCHEDULE ===
{period_sched}

=== INSTRUCTIONS ===
Follow the English LP Constitution and Assessment Constitution exactly.
Produce a SINGLE valid JSON object with this top-level structure:

{{
  "grade": "{grade}",
  "subject": "{subject}",
  "stage": "{stage}",
  "chapter_number": {chapter["chapter_number"]},
  "chapter_title": "{chapter.get('chapter_title', '')}",
  "period_schedule": <derived from teacher period schedule above>,

  "main_sections_inventory": [
    {{ "section_id": "A|B|C", "title": "...", "type": "prose|poem|narrative|dialogue|informational" }}
  ],

  "periods_allocated": <integer = total period count from the teacher schedule>,

  "lesson_plan": {{
    "periods": [
      <one object per period per LP Constitution Rule 1+2 — each period
       anchors to ONE main_section + 1-2 spines within it; periods walk
       main_sections in textbook order then spines within each section.
       Required fields: period_number, period_duration_minutes,
       section_id, section_title, spines_taught, activity_title,
       pedagogical_methods (object keyed by each spine in spines_taught;
       each value is one method drawn from that spine's permitted list
       in LP Rule 4 for the stage — keys MUST equal spines_taught
       exactly), tasks_in_class (each {{spine, task_index, task_brief}}),
       homework, phases (tile 0..duration with no gaps), teacher_notes
       (2-3 sentences max, grounded in main_section's prose_summary or
       poem_appreciation_summary), materials.>
    ]
  }},

  "coverage_handoff": {{
    "reading_for_comprehension": {{ "section_contributions": [<contribution>] }},
    "listening":                 {{ "section_contributions": [...] }},
    "speaking":                  {{ "section_contributions": [...] }},
    "writing":                   {{ "section_contributions": [...] }},
    "vocabulary_grammar":        {{ "section_contributions": [...] }},
    "beyond_text":               {{ "section_contributions": [...] }}
  }},

  "assessment_items": [
    {{
      "spine_code":  "reading_for_comprehension|listening|speaking|writing|vocabulary_grammar|beyond_text",
      "spine_title": "Reading for Comprehension|Listening|Speaking|Writing|Vocabulary and Grammar|Beyond the Text",
      "note":        "<empty unless an empty-spine note applies>",
      "items": [
        <one COMPOSITE item per main_section that contains this spine,
         per Assessment Rule 2: lift the FIRST task object from
         summary.<spine>.tasks_verbatim — copy task_text into
         task_prompt and copy ALL its nested question_bank entries
         verbatim into sub_items[]. Generate ONLY when the cell has
         no task at all. Required fields per outer item: id,
         source_section_id, source_section_title, source_section_type,
         source_spine_section, source ("lifted"|"generated"),
         source_task_index (the lifted task's index in tasks_verbatim;
         -1 if generated), task_prompt, question_type (only when
         sub_items is empty; else ""), transcript_ref (listening only;
         "" otherwise), sub_items (each carrying stem, question_type,
         options ([] unless MCQ), visual_stimulus (pipe-table or ""),
         teacher_guide {{ suggested_answer (CLOSED sub-item only),
         expected_elements (OPEN sub-item only — 3 to 5 short bullets
         per stage rubric depth in Rule 10), note (empty unless
         fallback) }}, verified), teacher_guide (populated only when
         sub_items is empty — same shape as sub-item teacher_guide),
         verified (true only when every closed sub-item is verified).>
      ]
    }}
  ]
}}

CRITICAL CONSTRAINTS:
- Total LP period count = the teacher schedule's period_count. Distribute
  across (section × spine) cells in textbook order (LP Rule 1+2), with
  per-section period share roughly proportional to the section's
  char_count + total task count (±1 period tolerance).
- Total assessment item count = number_of_main_sections × 6 (one
  composite item per (section × spine) cell, per Assessment Rule 2).
  For VII Ch 1 with 3 main_sections, that's 18 items. For each cell,
  lift the FIRST task object from summary.<spine>.tasks_verbatim:
  copy `task_text` into `task_prompt` AND copy ALL entries of the
  task's nested `question_bank` verbatim into `sub_items[]`,
  preserving each sub-item's stem, type, options, table, and
  page_ref. Set source="lifted", source_task_index=0. If the cell
  has no task at all, generate ONE typed item from the main_section's
  prose_summary / poem_text + poem_appreciation_summary
  (source="generated", source_task_index=-1, sub_items=[]). Subsequent
  tasks in the cell are NOT lifted.
- C-codes MUST NOT appear anywhere in the LP or assessment JSON.
- `pedagogical_methods` per period MUST be an object whose keys equal
  `spines_taught` exactly. Each value MUST be drawn from that spine's
  permitted method list in LP Constitution Rule 4 for the {stage}
  stage. Do NOT invent methods. Do NOT collapse multiple spines onto
  a single method.
- Listening items: `transcript_ref` format is `"p.NN"` at preparatory
  and middle (transcript inside chapter PDF) or `"appendix p.NN"` at
  secondary (transcript in a separate appendix file). The summary
  carries the value verbatim.
- The answer layer applies PER SUB-ITEM. A closed sub-item (MCQ,
  FILL_IN, MATCH, TRUE_FALSE, factual SCR) carries
  `teacher_guide.suggested_answer` (verified). An open sub-item
  (ORAL_PROMPT, WRITING_TASK, PROJECT, ECR, reflective SCR) carries
  `teacher_guide.expected_elements` ({rubric_bullets} short bullets,
  each ≤ 12 words). No sub-item carries both fields. When the outer
  composite has `sub_items: []` (open task with no textbook
  sub-items, or a generated item), the OUTER `teacher_guide` carries
  the same shape — populated according to the outer `question_type`.

LENGTH CONSTRAINTS:
- Each phase `description`: 2-3 sentences maximum.
- Each `teacher_notes`: 2-3 sentences maximum.
- Each `suggested_answer`: 1-2 sentences plain prose.
- Each `expected_elements` bullet: ≤ 12 words.

Output only the raw JSON object. No markdown. No prose. No headers. No ```json fences.
"""

    return system_prompt, user_prompt


def generate_lpa(
    grade: str,
    subject: str,
    chapter: dict,
    period_rows: list,
    session: dict,
    result_queue: "queue.Queue | None" = None,
    stop_event:   "threading.Event | None" = None,
) -> dict:
    """Generate lesson plan + assessment.

    When called from the background-thread path, *result_queue* and
    *stop_event* are provided:
      • result_queue – the completed (or stopped) result dict is put here.
      • stop_event   – checked on every streamed chunk; if set, the stream
                       is abandoned and a stopped-result dict is returned.

    When called synchronously (legacy path / tests), both are None and the
    function returns the result dict directly as before.
    """
    paths = resolve_paths(grade, subject, chapter["chapter_number"])

    period_sched = format_period_schedule(period_rows, session)

    # ── Subject dispatch ──────────────────────────────────────────────────
    # English uses a two-axis (main_section × spine) schema and has no
    # per-chapter competency mapping; the prompt is built differently.
    if subject_to_folder(subject) == "english":
        system_prompt, user_prompt = _build_lpa_prompts_english(
            grade, subject, chapter, period_sched, paths
        )
    else:
        # ── Math / Science / Social Sciences (existing path) ──────────────
        lp_const     = read_file(paths["lp_constitution"])
        assess_const = read_file(paths["assessment_const"])
        pedagogy     = read_file(paths["pedagogy"])
        summary      = read_file(paths["chapter_summary"])
        mapping_raw  = read_file(paths["chapter_mapping"])

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

=== CHAPTER SUMMARY ===
{summary}

=== CHAPTER MAPPING JSON ===
{mapping_raw}

=== TEACHER PERIOD SCHEDULE ===
{period_sched}

=== INSTRUCTIONS ===
Follow the Lesson Plan Constitution and Assessment Constitution exactly.
Produce your entire output as a single valid JSON object with this top-level structure:

{{
  "grade": "{grade}",
  "subject": "{subject}",
  "chapter_number": {chapter["chapter_number"]},
  "chapter_title": "{chapter.get('chapter_title', '')}",
  "period_schedule": <derived from teacher period schedule above>,
  "lesson_plan": {{ "periods": [ <one object per period per LP constitution> ] }},
  "coverage_handoff": {{
    "section_a": {{ "goal_cluster": ["recall"], "goals": [ {{"section_ref": "§X.Y", "section_title": "...", "goal": "recall", "anchor_id": "E-N | WE-N | A-N", "anchor_book_ref": "...", "anchor_description": "..."}} ] }},
    "section_b": {{ "goal_cluster": ["reason"], "goals": [ ... ] }},
    "section_c": {{ "goal_cluster": ["apply"],  "goals": [ ... ] }}
  }},
  "assessment_items": [ <one object per section per Assessment Constitution> ]
}}

For Mathematics, `coverage_handoff` is REQUIRED per LP Constitution
Rule 11 — emit it every time, even if a cluster has no goals. Anchor
selection walks `enumerated_exercises` → `enumerated_worked_examples`
→ `enumerated_activities` in priority order; emit empty strings only
when all three pools are exhausted for the section.
For Science and Social Sciences, `coverage_handoff` MAY be omitted.

LENGTH CONSTRAINTS (strictly enforced to keep output compact):
- Each phase `description`: 2–3 sentences maximum.
- Each `teacher_notes` field: 2–3 sentences maximum.
- Each Mathematics assessment `teacher_guide`: structured object per
  Assessment Constitution v3.2 Rule 6 — {{ expected_answer,
  method_one_line, what_each_option_reveals (MCQ only), inclusivity }}.
  Each string field one sentence only.

Output only the raw JSON object. No markdown. No prose. No section headers. No ```json fences.
"""

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        full_output = ""
        input_tokens = 0
        output_tokens = 0

        import time as _time
        progress_placeholder = st.empty()
        # Separate placeholder for the live timer badge — rendered via
        # components.html so that JS actually executes (st.markdown strips
        # <script> tags, which is why the badge previously stayed at 00:00).
        timer_placeholder = st.empty()

        # ── Record start time (ms epoch) for the timer ────────────────────────
        _gen_start_ms = int(_time.time() * 1000)

        # ── Shared CSS (animations) ───────────────────────────────────────────
        _pcss = (
            "<style>"
            "@keyframes aruviPulse{0%,100%{opacity:1}50%{opacity:.3}}"
            "@keyframes spin{to{transform:rotate(360deg)}}"
            "</style>"
        )

        # ── Live timer badge (separate components.html block) ────────────────
        # Streamlit's components.html mounts in a sandboxed iframe and DOES run
        # scripts, but st.markdown(unsafe_allow_html=True) silently strips
        # <script> — that's why the badge previously stayed at 00:00. We give
        # the iframe a real height so its content is visible, and use Streamlit
        # CSS to float the iframe wrapper at the bottom-right of the viewport.
        _timer_widget_html = (
            '<!doctype html><html><head><style>'
            'html,body{margin:0;padding:0;background:transparent;text-align:right;}'
            '#aruvi-timer{'
            '  font-family:monospace;font-size:10px;color:#000000;'
            '  background:transparent;border:none;border-radius:0;'
            '  padding:3px 8px;display:inline-block;margin:4px 6px 0 0;'
            '}'
            '</style></head><body>'
            '<div id="aruvi-timer">00:00</div>'
            '<script>'
            '(function(){'
            f'  var _start={_gen_start_ms};'
            '  function _tick(){'
            '    var el=document.getElementById("aruvi-timer");'
            '    if(!el){return;}'
            '    var s=Math.floor((Date.now()-_start)/1000);'
            '    var m=Math.floor(s/60);var sc=s%60;'
            '    el.textContent=(m<10?"0"+m:m)+":"+(sc<10?"0"+sc:sc);'
            '  }'
            '  _tick();'
            '  setInterval(_tick,1000);'
            '})();'
            '</script>'
            '</body></html>'
        )
        # Float the iframe over the popup at bottom-right of the viewport.
        # We rely on the fact that Streamlit wraps each components.html call
        # in <iframe srcdoc="…">, so we can match by the unique 'aruvi-timer'
        # string in the srcdoc attribute.
        st.markdown(
            "<style>"
            "iframe[srcdoc*='aruvi-timer']{"
            "  position:fixed !important;"
            "  top:340px !important;"
            "  right:24px !important;"
            "  width:96px !important;"
            "  height:30px !important;"
            "  border:0 !important;"
            "  z-index:10000 !important;"
            "  background:transparent !important;"
            "}"
            "</style>",
            unsafe_allow_html=True,
        )
        with timer_placeholder.container():
            components.html(_timer_widget_html, height=30, scrolling=False)
        # _timer_js / _timer_badge kept as no-ops so the existing markdown
        # blocks (which append them) continue to work without the JS injection.
        _timer_js = ""
        _timer_badge = (
            '<div style="display:flex;justify-content:flex-end;padding:4px 12px 8px 0;">'
            '<span style="font-family:monospace;font-size:10px;color:transparent;'
            'padding:2px 6px;">&nbsp;</span></div>'
        )
        # ── Icon snippets ─────────────────────────────────────────────────────
        _tick_icon = (
            '<div style="width:12px;height:12px;border-radius:50%;background:#d4f0e4;'
            'display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">'
            '<div style="width:5px;height:3px;border-left:1.5px solid #2d8a5e;'
            'border-bottom:1.5px solid #2d8a5e;transform:rotate(-45deg);'
            'margin-top:-1px;"></div></div>'
        )
        _spin_icon = (
            '<div style="width:12px;height:12px;border-radius:50%;'
            'border:1.5px solid #e8a83e;border-top-color:transparent;'
            'animation:spin 0.7s linear infinite;flex-shrink:0;'
            'margin-top:1px;box-sizing:border-box;"></div>'
        )
        _dot_icon = (
            '<div style="width:12px;height:12px;display:flex;align-items:center;'
            'justify-content:center;flex-shrink:0;margin-top:1px;">'
            '<div style="width:6px;height:6px;background:#d9d6d0;border-radius:50%;"></div></div>'
        )

        def _row_done(text):
            return (
                f'<div style="display:flex;align-items:flex-start;gap:8px;'
                f'font-size:12px;color:#9c9895;">{_tick_icon}<span>{text}</span></div>'
            )
        def _row_active(text):
            return (
                f'<div style="display:flex;align-items:flex-start;gap:8px;'
                f'font-size:12px;color:#3d3b38;font-weight:500;">'
                f'{_spin_icon}<span>{text}</span></div>'
            )
        def _row_pending(text):
            return (
                f'<div style="display:flex;align-items:flex-start;gap:8px;'
                f'font-size:12px;opacity:0.45;">{_dot_icon}<span>{text}</span></div>'
            )

        _steps = [
            "Reading LP &amp; Assessment Constitutions",
            "Reading chapter summary",
            "Loading matched competencies",
            "Loading stage pedagogy",
            "Building period-by-period activities&#8230;",
            "Writing assessment questions",
        ]
        _note_html = (
            '<div style="display:flex;flex-direction:column;align-items:center;'
            'gap:0.5rem;padding:8px 0 4px 0;">'
            f'<img src="{_rotate_logo_src}" style="width:48px;height:48px;'
            'animation:aruviSpin 3.5s linear infinite;" alt="Aruvi">'
            '<style>@keyframes aruviSpin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}</style>'
            '<span style="font-size:12px;color:#5c5a56;font-style:italic;">'
            'Running in the background \u2014 keep this tab open until complete.'
            '</span></div>'
        )
        _box_open = (
            '<div class="aruvi-progress-box" style="position:fixed;top:80px;right:24px;'
            'width:280px;z-index:9999;background:white;border:1px solid #d9d6d0;'
            'border-radius:10px;overflow:hidden;">'
        )
        _hdr_working = (
            '<div style="padding:8px 12px;border-bottom:1px solid #ece9e4;'
            'display:flex;gap:8px;align-items:center;">'
            '<div style="width:10px;height:10px;border-radius:50%;background:#e8a83e;'
            'animation:aruviPulse 1.4s infinite;flex-shrink:0;"></div>'
            '<span style="font-size:11px;color:#7a776f;font-weight:500;flex:1;">'
            'Aruvi is working&#8230;</span>'
            '<button onclick="window.parent.postMessage({type:\'aruvi_stop\'},\'*\')" '
            'style="display:inline-flex;align-items:center;gap:4px;font-size:10px;'
            'color:#9c9895;background:#f2f0ec;border:1px solid #dddad5;'
            'border-radius:4px;padding:3px 7px;cursor:pointer;white-space:nowrap;'
            'font-family:inherit;line-height:1;">'
            '<span style="width:7px;height:7px;background:#9c9895;border-radius:1px;'
            'display:inline-block;flex-shrink:0;"></span>'
            'stop</button>'
            '</div>'
        )
        _body_open = (
            '<div style="padding:10px 12px 12px;display:flex;flex-direction:column;gap:2px;">'
        )

        # Phase 1: 4 ticked · step 5 (activities) active · step 6 (assessment) pending
        PROGRESS_HTML_WORKING = (
            _pcss + _box_open + _hdr_working + _body_open
            + _row_done(_steps[0])
            + _row_done(_steps[1])
            + _row_done(_steps[2])
            + _row_done(_steps[3])
            + _row_active(_steps[4])
            + _row_pending(_steps[5])
            + _note_html
            + '</div>'
            + _timer_badge
            + '</div>'
            + _timer_js
        )
        # Phase 2: 5 ticked · step 6 (assessment questions) active
        PROGRESS_HTML_ASSESSMENT_ACTIVE = (
            _pcss + _box_open + _hdr_working + _body_open
            + _row_done(_steps[0])
            + _row_done(_steps[1])
            + _row_done(_steps[2])
            + _row_done(_steps[3])
            + _row_done(_steps[4])
            + _row_active(_steps[5])
            + _note_html
            + '</div>'
            + _timer_badge
            + '</div>'
            + _timer_js
        )

        # Stage 0 (immediately): step 1 active, steps 2–6 pending
        progress_placeholder.markdown(
            _pcss + _box_open + _hdr_working + _body_open
            + _row_active(_steps[0])
            + _row_pending(_steps[1])
            + _row_pending(_steps[2])
            + _row_pending(_steps[3])
            + _row_pending(_steps[4])
            + _row_pending(_steps[5])
            + _note_html + '</div>' + _timer_badge + '</div>' + _timer_js,
            unsafe_allow_html=True,
        )
        _time.sleep(5)

        # Stage 1: step 1 done, step 2 active, steps 3–6 pending
        progress_placeholder.markdown(
            _pcss + _box_open + _hdr_working + _body_open
            + _row_done(_steps[0])
            + _row_active(_steps[1])
            + _row_pending(_steps[2])
            + _row_pending(_steps[3])
            + _row_pending(_steps[4])
            + _row_pending(_steps[5])
            + _note_html + '</div>' + _timer_badge + '</div>' + _timer_js,
            unsafe_allow_html=True,
        )
        _time.sleep(5)

        # Stage 2: steps 1–2 done, step 3 active, steps 4–6 pending
        progress_placeholder.markdown(
            _pcss + _box_open + _hdr_working + _body_open
            + _row_done(_steps[0])
            + _row_done(_steps[1])
            + _row_active(_steps[2])
            + _row_pending(_steps[3])
            + _row_pending(_steps[4])
            + _row_pending(_steps[5])
            + _note_html + '</div>' + _timer_badge + '</div>' + _timer_js,
            unsafe_allow_html=True,
        )
        _time.sleep(5)

        # Stage 3: steps 1–3 done, step 4 active, steps 5–6 pending
        progress_placeholder.markdown(
            _pcss + _box_open + _hdr_working + _body_open
            + _row_done(_steps[0])
            + _row_done(_steps[1])
            + _row_done(_steps[2])
            + _row_active(_steps[3])
            + _row_pending(_steps[4])
            + _row_pending(_steps[5])
            + _note_html + '</div>' + _timer_badge + '</div>' + _timer_js,
            unsafe_allow_html=True,
        )
        _time.sleep(5)

        # Stage 4: steps 1–4 done, step 5 active, step 6 pending — PROGRESS_HTML_WORKING
        progress_placeholder.markdown(PROGRESS_HTML_WORKING, unsafe_allow_html=True)

        # ── Stream loop ───────────────────────────────────────────────────────
        streamed_text = ""
        _assessment_triggered = False
        _stopped_by_user = False

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=32000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                # ── Stop-button check ─────────────────────────────────────────
                if stop_event is not None and stop_event.is_set():
                    _stopped_by_user = True
                    break
                streamed_text += text
                if not _assessment_triggered and '"assessment_items"' in streamed_text:
                    _assessment_triggered = True
                    progress_placeholder.markdown(
                        PROGRESS_HTML_ASSESSMENT_ACTIVE, unsafe_allow_html=True
                    )

        full_output = streamed_text

        # ── If user stopped, record partial tokens and return a stopped result ─
        if _stopped_by_user:
            try:
                _partial_usage = stream.get_current_message_snapshot().usage
                input_tokens  = getattr(_partial_usage, "input_tokens",  0)
                output_tokens = getattr(_partial_usage, "output_tokens", 0)
            except Exception:
                input_tokens  = 0
                output_tokens = 0
            log_tokens(
                call_type      = "lpa_generation_stopped",
                grade          = grade,
                subject        = subject,
                chapter_number = chapter["chapter_number"],
                chapter_title  = chapter.get("chapter_title", ""),
                input_tokens   = input_tokens,
                output_tokens  = output_tokens,
                model          = "claude-sonnet-4-6",
            )
            progress_placeholder.empty()
            timer_placeholder.empty()
            _stopped_result = {
                "grade":          grade,
                "subject":        subject,
                "chapter_number": chapter["chapter_number"],
                "chapter_title":  chapter.get("chapter_title", ""),
                "lesson_plan":    {},
                "coverage_handoff": {},
                "assessment_items": [],
                "input_tokens":   input_tokens,
                "output_tokens":  output_tokens,
                "cost_inr":       calculate_cost_inr("claude-sonnet-4-6", input_tokens, output_tokens),
                "stopped":        True,
            }
            if result_queue is not None:
                result_queue.put(_stopped_result)
            return _stopped_result

        usage = stream.get_final_message().usage
        input_tokens  = usage.input_tokens
        output_tokens = usage.output_tokens

        log_tokens(
            call_type      = "lpa_generation",
            grade          = grade,
            subject        = subject,
            chapter_number = chapter["chapter_number"],
            chapter_title  = chapter.get("chapter_title", ""),
            input_tokens   = input_tokens,
            output_tokens  = output_tokens,
            model          = "claude-sonnet-4-6",
        )

        parsed = {}
        _raw = full_output.strip()
        # Strip ```json ... ``` fences if the model wrapped output despite instructions
        if _raw.startswith("```"):
            _fence_end = _raw.find("```", 3)
            _raw = (_raw[_raw.index("\n") + 1 : _fence_end] if _fence_end > 3 else _raw).strip()
        # Strip any prose preamble before the opening brace (model sometimes
        # reasons aloud before emitting JSON despite instructions)
        _brace_pos = _raw.find("{")
        if _brace_pos > 0:
            _raw = _raw[_brace_pos:]
        try:
            parsed = json.loads(_raw)
            # ── Final elapsed time (computed server-side, baked into HTML) ──
            _elapsed_s = max(0, int(_time.time() * 1000 - _gen_start_ms) // 1000)
            _final_mmss = f"{_elapsed_s // 60:02d}:{_elapsed_s % 60:02d}"
            # ── Phase 3: completion box (built after parse so numbers are real) ─
            _n_periods = len(parsed.get("lesson_plan", {}).get("periods", []))
            _n_acts    = sum(
                len(p.get("activities", []))
                for p in parsed.get("lesson_plan", {}).get("periods", [])
            )
            _c_codes   = {
                (_c.get("c_code", "") if isinstance(_c, dict) else str(_c))
                for _p2 in parsed.get("lesson_plan", {}).get("periods", [])
                for _c  in _p2.get("competencies", [])
            }
            _n_comps   = len(_c_codes - {""})
            _n_qs      = len(parsed.get("assessment_items", []))
            _sv        = "color:#2d8a5e;font-weight:500;"
            _summary   = (
                '<div style="font-family:monospace;font-size:10.5px;background:#f7f5f2;'
                'border-radius:6px;padding:8px 10px;margin-bottom:8px;">'
                f'Lesson plan: <span style="{_sv}">{_n_periods}</span> periods'
                f' &#183; <span style="{_sv}">{_n_acts}</span> activities<br>'
                f'Competencies: <span style="{_sv}">{_n_comps}</span> mapped<br>'
                f'Assessment: <span style="{_sv}">{_n_qs}</span> questions'
                '</div>'
            )
            _tick_sm   = (
                '<div style="width:10px;height:10px;border-radius:50%;background:#d4f0e4;'
                'display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;">'
                '<div style="width:4px;height:2.5px;border-left:1.5px solid #2d8a5e;'
                'border-bottom:1.5px solid #2d8a5e;transform:rotate(-45deg);'
                'margin-top:-0.5px;"></div></div>'
            )
            def _row_sm(text):
                return (
                    f'<div style="display:flex;align-items:flex-start;gap:8px;'
                    f'font-size:11px;color:#b0ada8;">'
                    f'{_tick_sm}<span>{text}</span></div>'
                )
            PROGRESS_HTML_DONE = (
                _pcss
                + '<div class="aruvi-progress-box" style="position:fixed;top:80px;right:24px;'
                'width:280px;z-index:9999;background:white;border:1px solid #d9d6d0;'
                'border-radius:10px;overflow:hidden;">'
                '<div style="padding:8px 12px;border-bottom:1px solid #ece9e4;'
                'display:flex;gap:8px;align-items:center;">'
                '<div style="width:10px;height:10px;border-radius:50%;background:#2d8a5e;'
                'flex-shrink:0;"></div>'
                '<span style="font-size:11px;color:#7a776f;font-weight:500;flex:1;">'
                'Generation complete</span>'
                '<button onclick="this.closest(\'.aruvi-progress-box\').style.display=\'none\'"'
                ' style="font-size:10px;background:#f2f0ec;border:1px solid #dddad5;'
                'border-radius:4px;padding:3px 7px;cursor:pointer;color:#9c9895;">'
                'collapse &#8250;</button>'
                '</div>'
                '<div style="padding:10px 12px 12px;display:flex;flex-direction:column;gap:3px;">'
                + _summary
                + _row_sm(_steps[0])
                + _row_sm(_steps[1])
                + _row_sm(_steps[2])
                + _row_sm(_steps[3])
                + _row_sm(_steps[4])
                + _row_sm(_steps[5])
                + '<div style="display:flex;justify-content:flex-end;padding:4px 12px 8px 0;">'
                '<span style="font-family:monospace;font-size:10px;color:#2d8a5e;'
                'background:#f0faf5;border:1px solid #b8e8d0;border-radius:4px;'
                f'padding:2px 6px;" id="aruvi-timer-final">{_final_mmss}</span>'
                '</div>'
                + '</div></div>'
            )
            progress_placeholder.markdown(PROGRESS_HTML_DONE, unsafe_allow_html=True)
            # Stop the live ticker iframe and remove the floating badge it
            # injected into the parent document, so the only visible time is
            # the static green final-time inside the completion box.
            # Clear the live ticker iframe — the static green final-time inside
            # the completion box now shows the elapsed time.
            timer_placeholder.empty()
        except Exception as _je:
            progress_placeholder.empty()
            # Tear down the live timer + floating badge on the error path too,
            # so the ticker doesn't keep running after generation has aborted.
            try:
                timer_placeholder.empty()
                components.html(
                    '<script>try{'
                    'if(window.parent && window.parent.document){'
                    '  var f=window.parent.document.getElementById("aruvi-timer-fixed");'
                    '  if(f){f.remove();}'
                    '}'
                    '}catch(e){}</script>',
                    height=0,
                    scrolling=False,
                )
            except Exception:
                pass
            # ── DEBUG: dump full raw output to file so we can inspect it ──────
            try:
                import datetime as _dt
                _debug_dir = Path(__file__).parent.parent / "mirror" / "debug"
                _debug_dir.mkdir(parents=True, exist_ok=True)
                _debug_file = _debug_dir / f"raw_output_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                _debug_file.write_text(_raw, encoding="utf-8")
                _debug_path_str = str(_debug_file)
            except Exception as _dfe:
                _debug_path_str = f"(could not write debug file: {_dfe})"
            _preview = _raw[:500] + (" … [truncated] … " + _raw[-200:] if len(_raw) > 700 else "")
            st.warning(
                f"⚠️ JSON parse failed ({_je}). "
                f"output_tokens={output_tokens}. "
                f"Full raw output saved to: {_debug_path_str}\n\n"
                f"Raw output preview:\n\n```\n{_preview}\n```"
            )
            parsed = {}
        lp_part = ""
        assess_part = ""
        lo_block_part = ""

        _final_result = {
            "grade":            grade,
            "subject":          subject,
            "chapter_number":   chapter["chapter_number"],
            "chapter_title":    chapter.get("chapter_title", ""),
            "lesson_plan":      parsed.get("lesson_plan", {}),
            "coverage_handoff": parsed.get("coverage_handoff", {}),
            "assessment_items": parsed.get("assessment_items", []),
            "input_tokens":     input_tokens,
            "output_tokens":    output_tokens,
            "cost_inr":         calculate_cost_inr("claude-sonnet-4-6", input_tokens, output_tokens),
        }
        if result_queue is not None:
            result_queue.put(_final_result)
        return _final_result

    except Exception as e:
        _err_result = {
            "grade":            grade,
            "subject":          subject,
            "chapter_number":   chapter["chapter_number"],
            "chapter_title":    chapter.get("chapter_title", ""),
            "lesson_plan":      {},
            "coverage_handoff": {},
            "assessment_items": [],
            "error":            str(e),
        }
        if result_queue is not None:
            result_queue.put(_err_result)
        return _err_result

# ── LPA normalisation helpers ─────────────────────────────────────────────────
# These bridge the old (lo_handoff flat list) and new (A3 lesson_plan.periods)
# JSON shapes so that lpa_page.html always receives the same field names.

def _normalise_lo_handoff(result: dict, comp_descs: dict) -> list:
    """
    Return per-period dicts in the shape lpa_page.html lo_handoff expects.

    New A3 format:  result["lesson_plan"]["periods"]  — nested competency{},
                    time_bands[{minutes,activity}], material as list,
                    section_anchor, visual_representation{}
    Old format:     result["lo_handoff"]              — flat per-period objects
    """
    lp = result.get("lesson_plan")
    if isinstance(lp, dict) and lp.get("periods"):
        # English: build section_id → section_type lookup from
        # main_sections_inventory if present (the field lives at result-level,
        # not on each period). Saved plans pre-inventory have no type info,
        # so the renderer simply omits the type pill.
        _eng_type_by_sec = {}
        _inv = result.get("main_sections_inventory") or []
        if isinstance(_inv, list):
            for _s in _inv:
                if isinstance(_s, dict) and _s.get("section_id"):
                    _eng_type_by_sec[_s["section_id"]] = _s.get("type", "") or _s.get("section_type", "") or ""
        out = []
        for p in lp["periods"]:
            # ── Mathematics format detection (v2.1 shape) ─────────────────────
            # Only Maths LP carries `textbook_segments` (array of §-locators) +
            # `textbook_items_in_class` (typed item pointers). These two together
            # are unique to Maths and absent from Science / Social Sciences.
            _is_maths = (
                isinstance(p.get("textbook_segments"), list)
                and (
                    "textbook_items_in_class" in p
                    or "section_goal" in p
                )
            )
            if _is_maths:
                mat = p.get("materials", "")
                if isinstance(mat, list):
                    mat = ", ".join(mat)
                # phases [{minutes (range string), description}] → time_slots
                time_slots = [
                    {"time": ph.get("minutes", ""), "desc": ph.get("description", "")}
                    for ph in (p.get("phases") or [])
                ]
                # Anchor display: §-locators joined ("§5.1" or "§5.4, §5.5").
                # Constitution shape is [{"ref": "§5.1", "title": "..."}], but
                # older saved plans may still hold plain strings — handle both.
                _segs = p.get("textbook_segments") or []
                if isinstance(_segs, list):
                    _seg_refs = [
                        (s.get("ref") or "").strip() if isinstance(s, dict)
                        else str(s).strip()
                        for s in _segs
                    ]
                    _anchor = ", ".join(r for r in _seg_refs if r)
                    # Collect section titles for display (prefer title over ref)
                    _seg_titles = [
                        (s.get("title") or "").strip() if isinstance(s, dict)
                        else ""
                        for s in _segs
                    ]
                    _section_title = ", ".join(t for t in _seg_titles if t)
                else:
                    _anchor = str(_segs)
                    _section_title = ""
                # Build a teacher-facing list of textbook items used in class,
                # rendered by book_ref (NEVER by internal id) per LP Rule 10.
                _items_inclass = p.get("textbook_items_in_class") or []
                _items_homework = p.get("homework") or []
                _ic_lines = "; ".join(
                    (it.get("book_ref") or "").strip()
                    for it in _items_inclass
                    if it.get("book_ref")
                )
                _hw_lines = "; ".join(
                    (it.get("book_ref") or "").strip()
                    for it in _items_homework
                    if it.get("book_ref")
                )
                out.append({
                    "period_number":           p.get("period_number"),
                    "period_duration_minutes": p.get("period_duration_minutes"),
                    "chapter_section":         _anchor,
                    "activity_name":           p.get("activity_title", ""),
                    "activity_summary":        p.get("activity_title", ""),
                    "time_slots":              time_slots,
                    "material":                mat,
                    # Maths has no per-period implied LO; show pedagogical method
                    # in this slot so teachers see SOMETHING informative.
                    "implied_lo":              p.get("pedagogical_method", ""),
                    "c_code":                  "",
                    "cg":                      "",
                    "weight":                  0,
                    "competency_text":         "",
                    "visual_representation":   None,
                    # ── Maths-specific fields surfaced to lpa_page.html ─────────
                    # The HTML may safely ignore unknown keys; new renderers can
                    # use these for richer display.
                    "is_mathematics":          True,
                    "section_title":           _section_title,
                    "section_goal":            p.get("section_goal", ""),
                    "pedagogical_method":      p.get("pedagogical_method", ""),
                    "textbook_segments":       _segs,
                    "textbook_items_in_class": _items_inclass,
                    "homework":                _items_homework,
                    "items_in_class_book_refs": _ic_lines,
                    "homework_book_refs":      _hw_lines,
                    "teacher_notes":           p.get("teacher_notes", ""),
                    # NOTE: deliberately do NOT set `activity_title` or
                    # `stage_label` at the top level — lpa_page.html uses
                    # `activity_title !== undefined || stage_label !== undefined`
                    # to detect Science. Maths uses `activity_name` (SS field)
                    # so the HTML routes Maths through the SS render path,
                    # which displays activity_name + time_slots correctly.
                })
                continue
            # ── English format detection (section × spine schema) ───────────
            # Unique signals: section_id (A/B/C) + spines_taught (list).
            # Maths uses textbook_segments; Science uses stage_label;
            # SS uses competency. None of these collide with English.
            _is_english = (
                isinstance(p.get("spines_taught"), list)
                and p.get("section_id") is not None
            )
            if _is_english:
                mat = p.get("materials", "")
                if isinstance(mat, list):
                    mat = ", ".join(mat)
                time_slots = [
                    {"time": ph.get("minutes", ""), "desc": ph.get("description", "")}
                    for ph in (p.get("phases") or [])
                ]
                _sec_id    = p.get("section_id", "") or ""
                _sec_title = p.get("section_title", "") or ""
                # section_type prefers the per-period field (newer schema);
                # falls back to inventory lookup; finally empty.
                _sec_type  = (
                    p.get("section_type", "")
                    or _eng_type_by_sec.get(_sec_id, "")
                    or ""
                )
                _chapter_section = (
                    f"Section {_sec_id} · {_sec_title}"
                    if _sec_id and _sec_title else (_sec_title or _sec_id or "")
                )
                # pedagogical_methods is a dict spine→method per the
                # constitution. Tolerate the singular `pedagogical_method`
                # string used by saved plans pre-dict — broadcast it to
                # every spine in spines_taught.
                _ped = p.get("pedagogical_methods")
                if not isinstance(_ped, dict) or not _ped:
                    _single = p.get("pedagogical_method") or ""
                    _spines = p.get("spines_taught") or []
                    _ped = {s: _single for s in _spines if isinstance(s, str)} if _single else {}
                out.append({
                    "period_number":           p.get("period_number"),
                    "period_duration_minutes": p.get("period_duration_minutes"),
                    "chapter_section":         _chapter_section,
                    "activity_name":           p.get("activity_title", ""),
                    "activity_summary":        p.get("activity_title", ""),
                    "time_slots":              time_slots,
                    "material":                mat,
                    "implied_lo":              "",
                    "c_code":                  "",
                    "cg":                      "",
                    "weight":                  0,
                    "competency_text":         "",
                    "visual_representation":   None,
                    # ── English-specific fields surfaced to lpa_page.html ────
                    # The HTML's English render branch reads these by name.
                    # Do NOT set stage_label / activity_title at top level —
                    # the HTML now dispatches on d.subject, but belt-and-braces
                    # keeps any residual data-shape detection from misrouting.
                    "is_english":              True,
                    "section_id":              _sec_id,
                    "section_title":           _sec_title,
                    "section_type":            _sec_type,
                    "spines_taught":           p.get("spines_taught") or [],
                    "pedagogical_methods":     _ped,
                    "tasks_in_class":          p.get("tasks_in_class") or [],
                    "homework":                p.get("homework") or [],
                    "teacher_notes":           p.get("teacher_notes", ""),
                })
                continue
            # ── Science format detection ────────────────────────────────────
            # Only use truly Science-specific fields (stage_label / progression_stage).
            # activity_title is NOT a reliable Science signal — Social Sciences plans
            # may also use that field name (e.g. ch_04 generated with activity_title
            # instead of activity_name), which would wrongly set c_code="" and break
            # competency-based collapsible grouping for Social Sciences.
            if p.get("stage_label") is not None or p.get("progression_stage") is not None:
                mat = p.get("materials", "")
                if isinstance(mat, list):
                    mat = ", ".join(mat)
                time_slots = [
                    {"time": ph.get("minutes", ""), "desc": ph.get("description", "")}
                    for ph in (p.get("phases") or [])
                ]
                out.append({
                    "period_number":           p.get("period_number"),
                    "period_duration_minutes": p.get("period_duration_minutes"),
                    "chapter_section":         p.get("stage_label", ""),
                    "activity_name":           p.get("activity_title", ""),
                    "activity_summary":        p.get("activity_title", ""),
                    "time_slots":              time_slots,
                    "material":                mat,
                    "implied_lo":              (p.get("activity_description") or "")[:200],
                    "c_code":                  "",
                    "cg":                      "",
                    "weight":                  p.get("progression_stage", 1),
                    "competency_text":         p.get("pedagogical_approach", ""),
                    "visual_representation":   None,
                    # ── Science-detection fields for lpa_page.html ───────────────
                    # The HTML checks periods[0].stage_label / activity_title to
                    # detect Science; these must be present as top-level keys.
                    "stage_label":             p.get("stage_label", ""),
                    "activity_title":          p.get("activity_title", ""),
                    "progression_stage":       p.get("progression_stage", 0),
                    "description":             p.get("description", ""),
                    # ── Lesson view panel fields for lpa_page.html ───────────────
                    "activity_description":    p.get("activity_description", ""),
                    "actors":                  p.get("roles", []),
                    "pedagogical_approach":    p.get("pedagogical_approach", ""),
                })
            else:
                # ── Social Sciences A3 format ────────────────────────────────
                comp = p.get("competency") or {}
                # time_bands [{minutes, activity}] → time_slots [{time, desc}]
                time_slots = [
                    {"time": tb.get("minutes", ""), "desc": tb.get("activity", "")}
                    for tb in (p.get("time_bands") or [])
                ]
                # material / materials (plural alias used by some generated plans)
                # → comma-joined string
                mat = p.get("material") if p.get("material") is not None else p.get("materials", "")
                if isinstance(mat, list):
                    mat = ", ".join(mat)
                c_code = comp.get("c_code", "")
                out.append({
                    "period_number":           p.get("period_number"),
                    "period_duration_minutes": p.get("period_duration_minutes"),
                    "chapter_section":         p.get("section_anchor", ""),
                    # activity_name is the canonical SS field; activity_title is an
                    # accepted alias used by some generated plans (e.g. ch_04).
                    "activity_name":           p.get("activity_name") or p.get("activity_title", ""),
                    "activity_summary":        p.get("activity_name") or p.get("activity_title", ""),
                    "time_slots":              time_slots,
                    "material":                mat,
                    "implied_lo":              p.get("implied_lo", ""),
                    "c_code":                  c_code,
                    "cg":                      comp.get("cg", ""),
                    "weight":                  comp.get("weight", 1),
                    "competency_text":         comp_descs.get(c_code, "") or comp.get("competency_text", ""),
                    "visual_representation":   p.get("visual_representation"),
                })
        return out

    # Old flat lo_handoff — enrich competency_text from comp_descs
    lo_list = result.get("lo_handoff", [])
    for lo in lo_list:
        if not lo.get("competency_text"):
            lo["competency_text"] = comp_descs.get(lo.get("c_code", ""), "")
    return lo_list


def _normalise_assessment_sections(result: dict, comp_descs: dict = None) -> list:
    """
    Return assessment_sections[] in the shape lpa_page.html renderAssessment() expects.

    New format:  result["assessment_items"] — flat list of question objects.
                 Each item must have: c_code, question_type, question_text,
                 options[], annotation, period_ref, weight_label,
                 competency_text, chapter_section.
    Legacy:      result["assessment_sections"] already populated — return as-is.
    Falls back to [] when neither is present.
    """
    if result.get("assessment_sections"):
        return result["assessment_sections"]

    items = result.get("assessment_items", [])
    if not items:
        return []

    # ── Mathematics format detection (v2.1 shape) ──────────────────────────
    # Maths assessment ships as a list of section-objects, each with its own
    # nested `items[]` array — distinct from the flat per-item list used by
    # Science and Social Sciences. Detect on the presence of `section_code`
    # ("A" / "B" / "C") at the top level of the first element with a nested
    # `items` array.
    _is_maths_assessment = (
        isinstance(items, list)
        and len(items) > 0
        and isinstance(items[0], dict)
        and "section_code" in items[0]
        and isinstance(items[0].get("items"), list)
    )
    if _is_maths_assessment:
        _MATHS_SECTION_DESC = {
            "A": "Recall and Apply — short answers, definitions, and procedural fluency.",
            "B": "Reason and Explain — proofs, justifications, and constructions.",
            "C": "Apply in Context — case-based and multi-concept problems.",
        }
        _maths_sections = []
        for sec in items:
            if not isinstance(sec, dict):
                continue
            _code  = sec.get("section_code", "")
            _title = sec.get("section_title", "")
            _note  = sec.get("note", "")
            _qs    = []
            for it in (sec.get("items") or []):
                if not isinstance(it, dict):
                    continue
                _qtype = it.get("question_type", "")
                _prompt = it.get("prompt", "")
                # Exercise companion (Constitution v3.2 Rule 9) — pointer to
                # textbook item that anchors this goal. Both fields empty when
                # the LP gamut walk found no anchor.
                _ex            = it.get("exercise") or {}
                _ex_book_ref   = _ex.get("book_ref", "") or ""
                _ex_description = _ex.get("description", "") or ""
                # ── Parse structured teacher_guide (v3.2) ────────────────────
                # teacher_guide is a JSON object:
                #   { expected_answer, method_one_line,
                #     what_each_option_reveals, inclusivity }
                # Tolerate legacy piped string for any saved plans pre-v3.2.
                _tg = it.get("teacher_guide", {}) or {}
                if isinstance(_tg, str):
                    _parts = [p.strip() for p in _tg.split(" | ")]
                    _tg_legacy_expected = _parts[1] if len(_parts) > 1 else ""
                    if _tg_legacy_expected.lower().startswith("expected answer:"):
                        _tg_legacy_expected = _tg_legacy_expected[len("expected answer:"):].strip()
                    _tg = {
                        "expected_answer":          _tg_legacy_expected,
                        "method_one_line":          "",
                        "what_each_option_reveals": {},
                        "inclusivity":              _parts[2] if len(_parts) > 2 else "",
                    }
                _tg_expected      = _tg.get("expected_answer", "") or ""
                _tg_method        = _tg.get("method_one_line", "") or ""
                _tg_what_reveals  = _tg.get("what_each_option_reveals", {}) or {}
                _tg_inclusivity   = _tg.get("inclusivity", "") or ""
                _maths_guide = {
                    "expected_answer":          _tg_expected,
                    "method_one_line":          _tg_method,
                    "what_each_option_reveals": _tg_what_reveals,
                    "inclusivity":              _tg_inclusivity,
                }
                _qs.append({
                    "type":               _qtype,
                    "question":           _prompt,
                    # OPEN_TASK is not a Mathematics question type per Constitution
                    # v3.2 Rule 10; these fields stay empty for math items.
                    "task":               "",
                    "scaffold":           "",
                    "format_of_output":   [],
                    "task_instructions":  "",
                    "options":            it.get("options", []) or [],
                    "annotation":         _ex_book_ref,
                    "period_ref":         _ex_book_ref,
                    "title":              (
                        (_qtype + ": " + (_prompt[:56] + "…" if len(_prompt) > 56 else _prompt))
                        if _prompt else _qtype
                    ),
                    "expected": (
                        next(
                            (o.get("text", "") for o in (it.get("options") or [])
                             if isinstance(o, dict) and o.get("is_correct")),
                            ""
                        )
                        if _qtype == "MCQ" else _tg_expected
                    ),
                    "cognitive_demand":         "",
                    "guide":                    _maths_guide,
                    "what_each_option_reveals": _tg_what_reveals,
                    "inclusivity":              _tg_inclusivity,
                    "visual_stimulus":          it.get("visual_stimulus", None),
                    "correct_answer":           "",
                    "implied_lo":               "",
                    # ── Maths-specific question fields surfaced to renderer ──
                    "is_mathematics":           True,
                    "section_ref":              it.get("section_ref", ""),
                    "section_title":            it.get("section_title", ""),
                    "goal":                     it.get("goal", ""),
                    "expected_answer":          _tg_expected,
                    # Exercise companion (Constitution v3.2 Rule 9)
                    "exercise":                 {
                        "book_ref":    _ex_book_ref,
                        "description": _ex_description,
                    },
                })
            _types_in_order = []
            for q in _qs:
                t = q["type"]
                if t and t not in _types_in_order:
                    _types_in_order.append(t)
            _maths_sections.append({
                # Maps onto SS-shape fields the HTML already knows how to
                # render. The HTML's SS branch renders these as:
                #   c_code (badge) | weight_label (right-side label)
                #   competency_short (description below)
                "c_code":           ("Section " + _code) if _code else "",
                "weight_label":     _title,
                "competency_short": _note or _MATHS_SECTION_DESC.get(_code, ""),
                "drawing_on":       _title,
                "question_types":   " · ".join(_types_in_order),
                "questions":        _qs,
                "is_science":       False,
                "is_mathematics":   True,
                "section_code":     _code,
                "section_title":    _title,
                "stage_label":      None,
            })
        return _maths_sections

    # ── English format detection (spine-grouped schema) ─────────────────────
    # English assessment ships as a list of spine-objects, each with its own
    # nested `items[]` array. Spines: reading_for_comprehension, listening,
    # speaking, writing, vocabulary_grammar, beyond_text. Detect on
    # `spine_code` at the top level of the first element with a nested
    # `items[]` array.
    _is_english_assessment = (
        isinstance(items, list)
        and len(items) > 0
        and isinstance(items[0], dict)
        and "spine_code" in items[0]
        and isinstance(items[0].get("items"), list)
    )
    if _is_english_assessment:
        _ENGLISH_SPINE_DESC = {
            "reading_for_comprehension": "Encountering text and demonstrating comprehension — recall, inference, reflection.",
            "listening":                 "Active listening — meaning, attitude, summarisation.",
            "speaking":                  "Structured talk — conversation, discussion, debate.",
            "writing":                   "Drafting and editing — formal and creative composition.",
            "vocabulary_grammar":        "Word-building and grammar embedded in context.",
            "beyond_text":               "Library work, projects, and interdisciplinary extensions.",
        }
        # Closed types render `teacher_guide.suggested_answer`; open types
        # render `teacher_guide.expected_elements` as bullets.
        _ENG_CLOSED_TYPES = {"MCQ", "FILL_IN", "MATCH", "TRUE_FALSE"}

        def _eng_resolve_answer(qtype: str, tg: dict) -> tuple[str, list]:
            qtype_u = (qtype or "").strip().upper()
            tg = tg if isinstance(tg, dict) else {}
            sug = tg.get("suggested_answer", "") or ""
            exp = tg.get("expected_elements") or []
            if not isinstance(exp, list):
                exp = []
            is_closed = qtype_u in _ENG_CLOSED_TYPES
            expected = sug if is_closed else "\n".join(str(e) for e in exp)
            return expected, exp

        _eng_sections = []
        for sec in items:
            if not isinstance(sec, dict):
                continue
            _spine_code  = (sec.get("spine_code") or "").strip().lower()
            _spine_title = sec.get("spine_title") or _spine_code.replace("_", " ").title()
            _qs = []
            for it in (sec.get("items") or []):
                if not isinstance(it, dict):
                    continue
                # New shape carries task_prompt + sub_items[]; legacy carries
                # prompt + question_type + teacher_guide. Read task_prompt
                # first, fall back to legacy prompt.
                _task_prompt = it.get("task_prompt") or it.get("item_stem") or it.get("prompt") or ""
                _outer_qtype = (it.get("question_type") or "").strip().upper()
                _outer_tg    = it.get("teacher_guide") or {}
                _sub_items_raw = it.get("sub_items")
                if not isinstance(_sub_items_raw, list):
                    _sub_items_raw = []

                # Build a normalised sub_items list for the renderer. When the
                # composite has no sub_items (open task with no textbook
                # sub-items, or a generated item), we synthesise ONE pseudo
                # sub-item from the outer task_prompt + outer teacher_guide so
                # the downstream HTML can always iterate sub_items.
                _sub_items_render = []
                if _sub_items_raw:
                    for si in _sub_items_raw:
                        if not isinstance(si, dict):
                            continue
                        _si_qtype = (si.get("question_type") or "").strip().upper()
                        _si_tg    = si.get("teacher_guide") or {}
                        _si_expected, _si_exp_elems = _eng_resolve_answer(_si_qtype, _si_tg)
                        _sub_items_render.append({
                            "stem":              si.get("stem", "") or "",
                            "type":              _si_qtype,
                            "options":           si.get("options") or [],
                            "visual_stimulus":   si.get("visual_stimulus", "") or "",
                            "expected":          _si_expected,
                            "expected_elements": _si_exp_elems,
                            "suggested_answer":  (_si_tg or {}).get("suggested_answer", "") or "",
                            "verified":          bool(si.get("verified", False)),
                        })
                else:
                    # Outer task itself owns the answer layer.
                    _outer_expected, _outer_exp_elems = _eng_resolve_answer(_outer_qtype, _outer_tg)
                    _sub_items_render.append({
                        "stem":              _task_prompt,
                        "type":              _outer_qtype,
                        "options":           it.get("options") or [],
                        "visual_stimulus":   it.get("visual_stimulus", "") or "",
                        "expected":          _outer_expected,
                        "expected_elements": _outer_exp_elems,
                        "suggested_answer":  (_outer_tg if isinstance(_outer_tg, dict) else {}).get("suggested_answer", "") or "",
                        "verified":          bool(it.get("verified", False)),
                    })

                # Card-level type chip: when the composite has explicit
                # sub-items, leave the outer type empty (the card shows the
                # task framing only); otherwise reflect the outer task's type.
                _card_type = "" if _sub_items_raw else _outer_qtype
                _card_title = (
                    (_card_type + ": " + (_task_prompt[:56] + "…" if len(_task_prompt) > 56 else _task_prompt))
                    if (_card_type and _task_prompt) else (_card_type or "Task")
                )
                # Card-level expected: when the outer task owns the answer
                # layer (no sub_items), surface it; otherwise leave empty —
                # the per-sub-item rows carry their own answers.
                _card_expected = ""
                _card_exp_elems = []
                _card_suggested = ""
                if not _sub_items_raw:
                    _card_expected, _card_exp_elems = _eng_resolve_answer(_outer_qtype, _outer_tg)
                    _card_suggested = (_outer_tg if isinstance(_outer_tg, dict) else {}).get("suggested_answer", "") or ""

                _qs.append({
                    "type":               _card_type,
                    "question":           _task_prompt,
                    "task":               "",
                    "scaffold":           "",
                    "format_of_output":   [],
                    "task_instructions":  "",
                    "options":            it.get("options") or [],
                    "annotation":         "",
                    "period_ref":         "",
                    "title":              _card_title,
                    "expected":           _card_expected,
                    "cognitive_demand":   "",
                    "guide":              {},
                    "expected_elements":  _card_exp_elems,
                    "look_for":           [],
                    "what_each_option_reveals": {},
                    "inclusivity":        "",
                    "visual_stimulus":    it.get("visual_stimulus", "") or "",
                    "correct_answer":     "",
                    "implied_lo":         it.get("source_lo", "") or it.get("implied_lo", "") or "",
                    # ── English-specific question fields surfaced to renderer ──
                    "is_english":           True,
                    "task_prompt":          _task_prompt,
                    "sub_items":            _sub_items_render,
                    "has_sub_items":        bool(_sub_items_raw),
                    "suggested_answer":     _card_suggested,
                    "source_section_id":    it.get("source_section_id", "") or "",
                    "source_section_title": it.get("source_section_title", "") or "",
                    "source_section_type":  it.get("source_section_type", "") or "",
                    "source_spine_section": it.get("source_spine_section", "") or "",
                    "source":               it.get("source", "") or "",
                    "source_task_index":    it.get("source_task_index", -1),
                    "transcript_ref":       it.get("transcript_ref", "") or "",
                    "verified":             bool(it.get("verified", False)),
                })
            _types_in_order = []
            for q in _qs:
                # When the composite carries sub_items, the spine-level type
                # chip strip should reflect the sub-items' types; otherwise
                # use the outer card type.
                _src_types = (
                    [si.get("type") for si in (q.get("sub_items") or [])]
                    if q.get("has_sub_items")
                    else [q.get("type")]
                )
                for t in _src_types:
                    if t and t not in _types_in_order:
                        _types_in_order.append(t)
            _eng_sections.append({
                "c_code":           _spine_title,
                "weight_label":     "",
                "competency_short": sec.get("note") or _ENGLISH_SPINE_DESC.get(_spine_code, ""),
                "drawing_on":       "",
                "question_types":   " · ".join(_types_in_order),
                "questions":        _qs,
                "is_science":       False,
                "is_mathematics":   False,
                "is_english":       True,
                "spine_code":       _spine_code,
                "stage_label":      None,
            })
        return _eng_sections

    # ── Fix 1 helper: short title ≤ 60 chars from type + first words of text ──
    def _build_title(qtype: str, qtext: str) -> str:
        prefix = (qtype or "Q").strip()
        budget = 58 - len(prefix)          # leaves 2 chars for ": "
        if budget <= 0:
            return prefix[:60]
        snippet = (qtext or "").strip()
        if len(snippet) > budget:
            snippet = snippet[:budget].rsplit(" ", 1)[0]
        return (prefix + ": " + snippet) if snippet else prefix

    # ── Fix 2 helper: derive expected-answer text by question type ─────────────
    def _build_expected(item: dict) -> str:
        qtype = (item.get("question_type") or "").strip().upper()
        if qtype == "MCQ":
            opts = item.get("options") or []
            if isinstance(opts, dict):
                # Science format: {"A": "text", ...} + separate "correct_answer" key
                correct_key = item.get("correct_answer", "")
                text = opts.get(correct_key, "")
                return (correct_key + ": " + text).strip(": ") if correct_key else ""
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                if opt.get("is_correct"):
                    label = opt.get("label", opt.get("key", ""))
                    text  = opt.get("text",  opt.get("value", ""))
                    return (label + ": " + text).strip(": ") if label else text
            return ""
        if qtype == "SCR":
            elems = item.get("expected_elements") or []
            return "\n".join(str(e) for e in elems)
        if qtype == "ECR":
            elems = item.get("look_for") or []
            return "\n".join(str(e) for e in elems)
        if qtype == "OPEN_TASK":
            # New schema: format_of_output is a list; join for display
            fof = item.get("format_of_output") or []
            if isinstance(fof, list):
                return "\n".join(str(f) for f in fof)
            return str(fof)
        return ""

    # Weight integer → label, mirroring WEIGHT_LABEL in lpa_page.html
    _WLBL = {3: "Central", 2: "Substantive", 1: "Present"}

    from collections import OrderedDict
    sections: dict = OrderedDict()
    for item in items:
        # ── Science format detection ────────────────────────────────────────
        # Science items carry at least one of these fields; SS items never do.
        _is_science = (
            item.get("stage_label") is not None or
            item.get("implied_lo_assessed") is not None or
            bool(item.get("marking_guidance")) or          # Science-only field
            bool(item.get("what_each_option_reveals")) or  # Science MCQ top-level
            bool(item.get("correct_answer"))               # Science MCQ correct key
        )

        if _is_science:
            _comp      = {}
            c_code     = ""
            _group_key = item.get("stage_label") or item.get("implied_lo_assessed") or f"_sci_{len(sections)}"
        else:
            # c_code may be a top-level field OR nested under item["competency"]["c_code"],
            # exactly as in lesson-plan periods (see _normalise_lo_handoff).
            _comp = item.get("competency") or {}
            if not isinstance(_comp, dict):
                _comp = {}
            c_code     = item.get("c_code") or _comp.get("c_code", "")
            _group_key = c_code

        if _group_key not in sections:
            if _is_science:
                _wlabel     = item.get("stage_label", "")
                _ctext      = item.get("implied_lo_assessed", "")
                _drawing_on = item.get("stage_label", "")
            else:
                # weight_label: prefer explicit string; fall back to integer from competency
                _wlabel = item.get("weight_label") or ""
                if not _wlabel:
                    _w = _comp.get("weight")
                    try:
                        _wlabel = _WLBL.get(int(_w), "") if _w is not None else ""
                    except (TypeError, ValueError):
                        _wlabel = ""

                # competency_text: prefer canonical lookup from comp_descs (authoritative
                # framework descriptions); fall back to AI-generated text only if the
                # lookup misses (e.g. comp_descs not loaded).
                _ctext = (
                    (comp_descs.get(c_code, "") if comp_descs and c_code else "") or
                    item.get("competency_text") or
                    _comp.get("competency_text", "") or
                    _comp.get("text", "")
                )
                _drawing_on = item.get("chapter_section", "")

            sections[_group_key] = {
                "c_code":           c_code,
                "weight_label":     _wlabel,
                "competency_short": _ctext,
                "drawing_on":       _drawing_on,
                "question_types":   "",
                "questions":        [],
                # ── Science-detection fields for lpa_page.html renderAssessment() ──
                # is_science is the canonical flag; stage_label carried for display.
                "is_science":  _is_science,
                "stage_label": item.get("stage_label", "") if _is_science else None,
            }
        qtype = item.get("question_type", "")
        sections[_group_key]["questions"].append({
            "type":               qtype,
            "question":           item.get("question_text", ""),
            "task":               item.get("task", ""),
            "scaffold":           item.get("scaffold", ""),
            "format_of_output":   item.get("format_of_output", []),
            "task_instructions":  item.get("task_instructions", ""),
            "options":            item.get("options", []),
            "annotation":         item.get("marking_guidance", "") if _is_science else item.get("annotation", ""),
            "period_ref":         item.get("period_ref", ""),
            "title":              _build_title(qtype, item.get("task", "") or item.get("question_text", "")),
            "expected":           _build_expected(item),
            "cognitive_demand":   item.get("cognitive_demand", ""),
            "guide":                    item.get("guide", {}),
            "expected_elements":        item.get("expected_elements", []),
            "look_for":                 item.get("look_for", []),
            # Science-specific fields for HTML rendering.
            # Science MCQ stores distractor notes at item["guide"]["MCQ"][...];
            # try top-level first (flat schema), fall back to the nested path.
            "what_each_option_reveals": (
                item.get("what_each_option_reveals")
                or (item.get("guide") or {}).get(qtype.upper() if qtype else "MCQ", {}).get("what_each_option_reveals", {})
                or {}
            ),
            "inclusivity": (
                item.get("inclusivity")
                or (item.get("guide") or {}).get(qtype.upper() if qtype else "MCQ", {}).get("inclusivity", "")
                or ""
            ),
            "visual_stimulus":          item.get("visual_stimulus", None),
            "correct_answer":           item.get("correct_answer", ""),
            # Learning Outcome for Assessment Question column display.
            # Science: sourced from implied_lo_assessed on the item itself.
            # Social Science: sourced from implied_lo on the item itself (not competency_text).
            "implied_lo": (
                item.get("implied_lo_assessed", "")
                if _is_science else
                item.get("implied_lo", "")
            ),
        })

    # Fix 3: populate question_types — unique types in order of first appearance
    for sec in sections.values():
        seen: list = []
        for q in sec["questions"]:
            t = q["type"]
            if t and t not in seen:
                seen.append(t)
        sec["question_types"] = " · ".join(seen)

    return list(sections.values())


# ── LRM allocation helpers ────────────────────────────────────────────────────

def _ch_w3_codes(ch: dict) -> list:
    return [item["c_code"] for item in ch.get("primary", []) if item.get("weight") == 3]

def _ch_w2_codes(ch: dict) -> list:
    return [item["c_code"] for item in ch.get("primary", []) if item.get("weight") == 2]

def _ch_w1_codes(ch: dict) -> list:
    return [item["c_code"] for item in ch.get("primary", []) if item.get("weight") == 1]

def _alloc_chapter_weight(ch: dict) -> int:
    """Competency-load weight: W3×3 + W2×2 + W1×1, using pre-stored chapter_weight if available."""
    stored = ch.get("chapter_weight")
    if isinstance(stored, (int, float)) and stored > 0:
        return int(stored)
    # Science: use effort_index as allocation weight
    effort = ch.get("effort_index")
    if isinstance(effort, (int, float)) and effort > 0:
        return int(round(effort))
    return sum(item.get("weight", 0) for item in ch.get("primary", []))

def _lrm(raw_floats: list, total: int) -> list:
    """Largest Remainder Method: distribute `total` integer slots proportionally."""
    floors = [math.floor(f) for f in raw_floats]
    remainders = sorted(enumerate(raw_floats), key=lambda x: -(x[1] - math.floor(x[1])))
    deficit = total - sum(floors)
    result = floors[:]
    for k in range(deficit):
        result[remainders[k][0]] += 1
    return result

def _compute_allocation(chs: list, period_types: list) -> list:
    """
    Returns one allocation dict per chapter.
    Each dict has {mins: count, ..., 'total': int}.
    """
    if not chs or not period_types:
        return []
    if len(chs) == 1:
        alloc = {pt["mins"]: pt["count"] for pt in period_types}
        alloc["total"] = sum(pt["count"] for pt in period_types)
        return [alloc]

    weights  = [_alloc_chapter_weight(ch) for ch in chs]
    sum_w    = sum(weights) or 1
    sorted_types  = sorted(period_types, key=lambda pt: -pt["mins"])
    total_periods = sum(pt["count"] for pt in sorted_types)

    pass1     = _lrm([w / sum_w * total_periods for w in weights], total_periods)
    remaining = pass1[:]
    allocs    = [{} for _ in chs]

    for pt in sorted_types[:-1]:
        raw    = [min(w / sum_w * pt["count"], remaining[i]) for i, w in enumerate(weights)]
        result = _lrm(raw, pt["count"])
        for i, v in enumerate(result):
            allocs[i][pt["mins"]]  = v
            remaining[i]          -= v

    shortest = sorted_types[-1]
    for i, v in enumerate(remaining):
        allocs[i][shortest["mins"]] = max(0, v)

    for i in range(len(chs)):
        allocs[i]["total"] = pass1[i]

    return allocs


def _generate_pdf_bytes_alloc(
    chs: list,
    allocs: list,
    sorted_pts: list,
    grade: str,
    subject: str,
) -> bytes:
    """PDF export for the period allocation report (landscape)."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 9, "Aruvi - Period Allocation Report", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Grade: {grade}   Subject: {subject}", ln=True)
    pdf.ln(3)

    # Detect subject group for column layout and footnote wording
    is_science = subject in ("Science", "Mathematics")
    is_english = subject == "English"
    uses_effort_index = is_science or is_english

    # Column layout — switches on subject group
    pt_headers = [f"{pt['mins']}min" for pt in sorted_pts]
    if uses_effort_index:
        # Science / Mathematics / English: single Effort Index column
        all_headers = ["#", "Chapter", "Effort Idx"] + pt_headers + ["Total", "Minutes"]
        fixed_w     = [8, 96, 24]
    else:
        # Social Sciences / other languages: three competency-weight columns
        all_headers = ["#", "Chapter", "W3", "W2", "W1"] + pt_headers + ["Total", "Minutes"]
        fixed_w     = [8, 68, 28, 28, 28]
    pt_w       = [16] * len(sorted_pts)
    tail_w     = [16, 18]
    col_widths = fixed_w + pt_w + tail_w

    # Header row
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(all_headers, col_widths):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(30, 30, 30)
    grand_p = 0
    grand_m = 0
    col_sums = {pt["mins"]: 0 for pt in sorted_pts}

    for idx, (ch, alloc) in enumerate(zip(chs, allocs)):
        if uses_effort_index:
            ei = ch.get("effort_index", 0)
            ei_str = str(ei) if (isinstance(ei, (int, float)) and ei > 0) else "-"
        else:
            w3 = ", ".join(_ch_w3_codes(ch)) or "-"
            w2 = ", ".join(_ch_w2_codes(ch)) or "-"
            w1 = ", ".join(_ch_w1_codes(ch)) or "-"
        tp = alloc.get("total", 0)
        tm = sum(alloc.get(pt["mins"], 0) * pt["mins"] for pt in sorted_pts)
        grand_p += tp
        grand_m += tm
        fill = (idx % 2 == 0)
        if fill:
            pdf.set_fill_color(248, 247, 245)

        if uses_effort_index:
            row_vals = [f"{ch['chapter_number']:02d}", ch.get("chapter_title", "")[:54], ei_str]
        else:
            row_vals = [
                f"{ch['chapter_number']:02d}",
                ch.get("chapter_title", "")[:44],
                w3[:22], w2[:22], w1[:22],
            ]
        for pt in sorted_pts:
            v = alloc.get(pt["mins"], 0)
            col_sums[pt["mins"]] += v
            row_vals.append(str(v))
        row_vals += [str(tp), str(tm)]

        for val, w in zip(row_vals, col_widths):
            align = "L" if w >= 40 else "C"
            try:
                pdf.cell(w, 6, val, border=1, fill=fill, align=align)
            except Exception:
                pdf.cell(w, 6, val.encode("latin-1", "replace").decode("latin-1"),
                         border=1, fill=fill, align=align)
        pdf.ln()

    # Footer row
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(214, 228, 248)
    # Number of blank cells before the period-type sums mirrors the fixed column count
    foot_vals = ["", "Total"] + [""] * (len(fixed_w) - 2)
    for pt in sorted_pts:
        foot_vals.append(str(col_sums[pt["mins"]]))
    foot_vals += [str(grand_p), str(grand_m)]
    for val, w in zip(foot_vals, col_widths):
        pdf.cell(w, 6, val, border=1, fill=True, align="C")
    pdf.ln()

    # Footnote — wording depends on subject group
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    h_g, m_g = divmod(grand_m, 60)
    time_str = f"{h_g}h {m_g}min" if h_g else f"{m_g} min"
    if is_english:
        footnote = (
            f"Total: {grand_p} periods · {time_str}   |   "
            "Periods allocated using the Largest Remainder Method (LRM) weighted by chapter effort index."
        )
    elif is_science:
        footnote = (
            f"Total: {grand_p} periods · {time_str}   |   "
            "Periods allocated using the Largest Remainder Method (LRM) weighted by chapter effort index."
        )
    else:
        footnote = (
            "Periods allocated using the Largest Remainder Method (LRM) "
            f"weighted by chapter competency load.   "
            f"Total: {grand_p} periods · {time_str}"
        )
    pdf.cell(0, 5, footnote, ln=True)

    # ── "About the Effort Index" block — English and Science/Mathematics ──────
    if is_english:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(26, 68, 128)
        pdf.cell(0, 5, "About the Effort Index", ln=True)
        pdf.set_draw_color(147, 188, 232)
        pdf.set_line_width(0.3)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
        pdf.ln(1)

        _ei_rows_en = [
            ("What it measures:",
             "The effort index tells you how much classroom time a chapter typically needs compared to other"
             " chapters in the subject. Chapters with a higher effort index get more periods; chapters with"
             " a lower one get fewer. It is calculated from four signals, each scored on a simple scale."),
            ("Spine load (x2):",
             "How many types of classroom work (reading for comprehension, listening, speaking, writing,"
             " vocabulary, beyond-text) appear on average per section. More types = higher score."),
            ("Task density (x1.5):",
             "How many tasks appear on average within each block of work. More tasks per block = higher score."),
            ("Writing demand (x1.5):",
             "Total exercise items under Writing and Beyond-the-Text across the chapter. These take longer"
             " to complete and assess, so a heavier count raises the score."),
            ("Project load (x1):",
             "How many Beyond-the-Text sections the chapter has. Each one adds to the score as these"
             " activities need extra planning time."),
            ("Note:",
             "The four scores are combined with fixed weights to give the effort index. Only relative values"
             " matter — it is used to share your available periods across chapters in proportion to their load."),
        ]
        _lbl_w = 44
        _body_w = 180 - _lbl_w
        for lbl, body in _ei_rows_en:
            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(26, 68, 128)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(_lbl_w, 4, lbl, ln=False)
            y1 = pdf.get_y()
            pdf.set_xy(pdf.l_margin + _lbl_w, y0)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(75, 75, 75)
            pdf.multi_cell(_body_w, 4, body)
            y2 = pdf.get_y()
            pdf.set_y(max(y1, y2))
            pdf.ln(1)

    elif is_science:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(26, 68, 128)
        pdf.cell(0, 5, "About the Effort Index", ln=True)
        pdf.set_draw_color(147, 188, 232)
        pdf.set_line_width(0.3)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
        pdf.ln(1)

        _ei_rows_sci = [
            ("What it measures:",
             "The effort index tells you how much classroom time a chapter typically needs compared to other"
             " chapters in the subject. Chapters with a higher effort index get more periods; chapters with"
             " a lower one get fewer. It is calculated from four signals read from the chapter content."),
            ("Conceptual demand (x2):",
             "The cognitive complexity of exercises and questions in the chapter. High-order thinking or"
             " multi-step reasoning raises the score."),
            ("Student activities (x1):",
             "The number of hands-on activities that students perform themselves. Each activity adds"
             " classroom time for setup, execution and discussion."),
            ("Teacher demonstrations (x1.5):",
             "The number of demonstrations the teacher must conduct. These need preparation and focused"
             " class attention."),
            ("Exercise execution load (x2):",
             "The total exercise items students must complete. A heavier exercise count means more time"
             " for guided practice and assessment."),
            ("Note:",
             "The four signals are combined with fixed weights to give the effort index. Only relative values"
             " matter — it is used to share your available periods across chapters in proportion to their load."),
        ]
        _lbl_w = 50
        _body_w = 180 - _lbl_w
        for lbl, body in _ei_rows_sci:
            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(26, 68, 128)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(_lbl_w, 4, lbl, ln=False)
            y1 = pdf.get_y()
            pdf.set_xy(pdf.l_margin + _lbl_w, y0)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(75, 75, 75)
            pdf.multi_cell(_body_w, 4, body)
            y2 = pdf.get_y()
            pdf.set_y(max(y1, y2))
            pdf.ln(1)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


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

if "role"    in query and query["role"]    in ("Allocate", "Generate", "My Plans"):
    _prev_role = st.session_state.get("role", "")
    st.session_state.role    = query["role"]
    if query["role"] == "My Plans" and _prev_role != "My Plans":
        st.session_state.myplans_should_collapse = True
if "grade" not in query and st.session_state.get("grade"):
    pass  # keep existing session state grade
if "subject" not in query and st.session_state.get("subject"):
    pass  # keep existing session state subject
if "grade"   in query and query["grade"]   in GRADES:
    st.session_state.grade   = query["grade"]
if "subject" in query and query["subject"] in SUBJECTS:
    st.session_state.subject = query["subject"]
if "ch"      in query:
    try: st.session_state.teacher_ch_idx = int(query["ch"])
    except ValueError: pass

# Persist alloc_chs and alloc_pts from URL into session state
# so they survive across reruns and are available wherever the tab renders
if "alloc_chs" in query and query["alloc_chs"]:
    st.session_state["alloc_chs"] = query["alloc_chs"]
if "alloc_pts" in query and query["alloc_pts"]:
    st.session_state["alloc_pts"] = query["alloc_pts"]
# Clear them if a fresh load (no alloc params in URL)
if "alloc_chs" not in query and "alloc_pts" not in query:
    if "alloc_chs" in st.session_state: del st.session_state["alloc_chs"]
    if "alloc_pts" in st.session_state: del st.session_state["alloc_pts"]

# Defaults on first load
if "role"    not in st.session_state: st.session_state.role    = "Allocate"
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
_rotate_logo_src = _img_src(
    PROJECT_ROOT / "aruvi_streamlit" / "static" / "aruvi_logo_rotate.png"
)                                                                        # Progress popup spinning logo


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
   NAV PILL BUTTONS — lift into fixed top nav bar
   ═══════════════════════════════════════════════════ */
div[class*="st-key-nav_allocate"],
div[class*="st-key-nav_generate"],
div[class*="st-key-nav_myplans"] {
    position: fixed !important;
    top: 18px !important;
    z-index: 100000 !important;
    margin: 0 !important;
    padding: 0 !important;
}
div[class*="st-key-nav_allocate"] { left: calc(50% - 148px) !important; }
div[class*="st-key-nav_generate"] { left: calc(50% - 44px)  !important; }
div[class*="st-key-nav_myplans"]  { left: calc(50% + 60px)  !important; }

/* Style all three as pill-shaped */
div[class*="st-key-nav_allocate"] button,
div[class*="st-key-nav_generate"] button,
div[class*="st-key-nav_myplans"]  button {
    background: transparent !important;
    border: none !important;
    border-radius: 999px !important;
    color: #6b6866 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 0.3rem 1.45rem !important;
    box-shadow: none !important;
    transition: background 0.15s, color 0.15s !important;
}
div[class*="st-key-nav_allocate"] button:hover,
div[class*="st-key-nav_generate"] button:hover,
div[class*="st-key-nav_myplans"]  button:hover {
    background: rgba(0,0,0,0.04) !important;
    color: #2c2a27 !important;
    border: none !important;
}
/* Active pill — white background with shadow, matching original design */
div[class*="st-key-nav_allocate"] button[kind="primary"],
div[class*="st-key-nav_generate"] button[kind="primary"],
div[class*="st-key-nav_myplans"]  button[kind="primary"] {
    background: #ffffff !important;
    color: #2c2a27 !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.12) !important;
    border: none !important;
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
div[class*="st-key-lpa_confirm"] button {
    background: #2c3e50 !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-radius: 9px !important;
}
div[class*="st-key-lpa_confirm"] button:hover {
    background: #3d5166 !important;
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
   ASK ARUVI FAB  — fixed bottom-right floating button
   ═══════════════════════════════════════════════════ */
div[class*="st-key-ask_aruvi_fab"] button {
    position: fixed !important;
    bottom: 28px !important;
    right: 28px !important;
    width: 52px !important;
    height: 52px !important;
    border-radius: 50% !important;
    background: #1B2A3B !important;
    color: #ffffff !important;
    font-size: 1.3rem !important;
    border: none !important;
    z-index: 99999 !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18) !important;
    min-height: unset !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_fab"] button:hover {
    background: #2C7A7B !important;
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
   MY PLANS — VIEW / PDF BUTTONS
   ═══════════════════════════════════════════════════ */
div[class*="st-key-view_"] button,
div[class*="st-key-pdf_"] button {
    background: #2c3e50 !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    border-radius: 8px !important;
}
div[class*="st-key-view_"] button:hover,
div[class*="st-key-pdf_"] button:hover {
    background: #3d5166 !important;
}

/* MY PLANS — BACK BUTTONS (match primary / Generate button colours) */
div[class*="st-key-mp_back_"] button {
    background: #c96442 !important;
    border: none !important;
    color: #ffffff !important;
}
div[class*="st-key-mp_back_"] button:hover {
    background: #d97050 !important;
}


/* ═══════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
   ═══════════════════════════════════════════════════ */
#MainMenu, footer { visibility: hidden; }

/* Hide Streamlit's built-in running / status indicator (cyclist / runner animation) */
[data-testid="stStatusWidget"],
[data-testid="stDecoration"],
div[class*="StatusWidget"],
.stSpinner > div > div { display: none !important; }

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

def _mappings_cache_key(grade: str, subject: str) -> str:
    """Return a string that changes whenever the mappings directory contents change."""
    subj_f  = subject_to_folder(subject)
    grade_f = grade_to_folder(grade)
    mappings_dir = PROJECT_ROOT / f"mirror/chapters/{subj_f}/{grade_f}/mappings"
    if not mappings_dir.exists():
        return "empty"
    files = sorted(mappings_dir.glob("ch_*_mapping.json"))
    return f"{len(files)}:{':'.join(f.name for f in files)}"


@st.cache_data
def load_all_chapters(grade: str, subject: str, _cache_key: str = "") -> list[dict]:
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
    chapters = load_all_chapters(
        st.session_state.grade,
        st.session_state.subject,
        _cache_key=_mappings_cache_key(st.session_state.grade, st.session_state.subject),
    )
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
    if "_next_row_id" not in st.session_state:
        st.session_state["_next_row_id"] = len(st.session_state.get("period_rows", [0])) + 1
    _new_id = st.session_state["_next_row_id"]
    st.session_state["_next_row_id"] = _new_id + 1
    st.session_state["period_rows"] = st.session_state.get("period_rows", []) + [_new_id]

def _cb_del_row(rid):
    st.session_state["period_rows"] = [
        r for r in st.session_state.get("period_rows", []) if r != rid
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

if "role"              not in st.session_state: st.session_state.role              = "Allocate"
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
# Always sync ch_selected / ch_periods with the live chapter list so that
# newly-added chapters (e.g. English after mappings are generated) appear
# immediately without requiring a full session restart.
if "ch_selected" not in st.session_state:
    st.session_state.ch_selected = {ch["chapter_number"]: False for ch in chapters}
else:
    for ch in chapters:
        st.session_state.ch_selected.setdefault(ch["chapter_number"], False)

if "ch_periods" not in st.session_state:
    st.session_state.ch_periods = {ch["chapter_number"]: 6 for ch in chapters}
else:
    for ch in chapters:
        st.session_state.ch_periods.setdefault(ch["chapter_number"], 6)
if "principal_generated"      not in st.session_state: st.session_state.principal_generated      = False
if "ask_aruvi_open"           not in st.session_state: st.session_state.ask_aruvi_open           = False
st.session_state.setdefault("ask_aruvi_session_id",   str(uuid.uuid4()))
st.session_state.setdefault("ask_aruvi_category",     None)
st.session_state.setdefault("ask_aruvi_response",     "")
st.session_state.setdefault("ask_aruvi_last_query",   "")
st.session_state.setdefault("ask_aruvi_show_thumbs",  False)
st.session_state.setdefault("ask_aruvi_thumb_done",   False)
st.session_state.setdefault("ask_aruvi_show_followup", False)
st.session_state.setdefault("ask_aruvi_detail_cat", None)
st.session_state.setdefault("ask_aruvi_fb_sent",    False)
st.session_state.setdefault("ask_aruvi_fb_reset",   0)
# Managed-agent secondary panel state
st.session_state.setdefault("ask_aruvi_agent_open",         False)
st.session_state.setdefault("ask_aruvi_agent_response",     "")
st.session_state.setdefault("ask_aruvi_agent_last_query",   "")
st.session_state.setdefault("ask_aruvi_agent_show_thumbs",  False)
st.session_state.setdefault("ask_aruvi_agent_thumb_done",   False)
st.session_state.setdefault("ask_aruvi_agent_show_followup",False)
st.session_state.setdefault("ask_aruvi_agent_fb_sent",      False)
st.session_state.setdefault("ask_aruvi_agent_fb_reset",     0)
if "lpa_result"               not in st.session_state: st.session_state.lpa_result               = None
if "lpa_generating"           not in st.session_state: st.session_state.lpa_generating           = False
if "lpa_start_ts"             not in st.session_state: st.session_state.lpa_start_ts             = None
if "lpa_stop_event"           not in st.session_state: st.session_state.lpa_stop_event           = None
if "no_chapter_warning"       not in st.session_state: st.session_state.no_chapter_warning       = False
if "plan_just_saved"          not in st.session_state: st.session_state.plan_just_saved          = False

@st.dialog(" ")
def _no_chapter_dialog():
    st.markdown(
        '<div style="text-align:center;padding:4px 0 8px;">'
        '<div style="font-size:2.2rem;margin-bottom:10px;">📖</div>'
        '<div style="font-size:1rem;font-weight:600;color:#3d3b38;margin-bottom:8px;">'
        'No chapter selected</div>'
        '<div style="font-size:0.85rem;color:#6b6965;margin-bottom:4px;">'
        'Please pick a chapter from the sidebar<br>before generating.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        if st.button("OK", key="no_chapter_ok_dlg", type="primary", use_container_width=True):
            st.session_state.no_chapter_warning = False
            st.rerun()
if "mp_viewing_plan"          not in st.session_state: st.session_state.mp_viewing_plan          = None
if "period_rows"              not in st.session_state: st.session_state["period_rows"]            = []
if "myplans_should_collapse"  not in st.session_state: st.session_state.myplans_should_collapse  = False
if "show_save_prompt"         not in st.session_state: st.session_state.show_save_prompt         = False
if "plan_already_saved"       not in st.session_state: st.session_state.plan_already_saved       = False

has_chapter_data = len(chapters) > 0

# ── Fixed top nav bar ─────────────────────────────────────────────────────────
# Logo/brand rendered as HTML; pill buttons rendered as CSS-positioned st.buttons.

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
  <div class="topnav-center" id="aruvi-pill-anchor"></div>
  <div class="topnav-right"></div>
</div>
""", unsafe_allow_html=True)

_nc1, _nc2, _nc3, _nc4, _nc5 = st.columns([2, 1, 1, 1, 2])
with _nc2:
    if st.button("Allocate", key="nav_allocate", type="primary" if st.session_state.role == "Allocate" else "secondary"):
        st.session_state.role = "Allocate"
        st.query_params["role"] = "Allocate"
        st.rerun()
with _nc3:
    if st.button("Generate", key="nav_generate", type="primary" if st.session_state.role == "Generate" else "secondary"):
        st.session_state.role = "Generate"
        st.query_params["role"] = "Generate"
        st.rerun()
with _nc4:
    if st.button("My Plans", key="nav_myplans", type="primary" if st.session_state.role == "My Plans" else "secondary"):
        st.session_state.role = "My Plans"
        st.session_state.myplans_should_collapse = True
        st.query_params["role"] = "My Plans"
        st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────
# Change 3: Grade / Subject / Chapter selectboxes use label_visibility="visible".
#           CSS floats each label inside the selectbox border at top-left.
#           No separate icon-label-row div above each selectbox.

with st.sidebar:
    if st.session_state.role == "My Plans":
        st.markdown('<div style="display:none"></div>', unsafe_allow_html=True)
    else:

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
        elif st.session_state.role == "Generate":

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
            if not st.session_state.get("period_rows"):
                st.session_state["period_rows"] = [0]
                st.session_state["_next_row_id"] = 1

            # Ensure cnt is initialised for every active row (new rows only)
            for _rid in st.session_state.get("period_rows", []):
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
            for _rid in st.session_state.get("period_rows", []):
                _is_first = (_rid == st.session_state.get("period_rows", [0])[0])
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
                for r in st.session_state.get("period_rows", [])
            )
            total_p = sum(
                (st.session_state.get(f"cnt_{r}") or 0)
                for r in st.session_state.get("period_rows", [])
            )
            if total_m > 0:
                _h, _min = divmod(total_m, 60)
                if _h == 0:
                    _time_str = f"{_min} minute{'s' if _min != 1 else ''}"
                elif _min == 0:
                    _time_str = f"{_h} hour{'s' if _h != 1 else ''}"
                else:
                    _time_str = f"{_h} hour{'s' if _h != 1 else ''} and {_min} minute{'s' if _min != 1 else ''}"
                _p_label = f"{total_p} period{'s' if total_p != 1 else ''}"
                st.markdown(
                    f'<div style="font-size:0.79rem;color:#3d3b38;margin:0.4rem 0 0.25rem 0;">'
                    f'Total · {_time_str}, {_p_label}'
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
                if st.session_state.teacher_ch_idx is None:
                    st.session_state.no_chapter_warning = True
                else:
                    st.session_state.no_chapter_warning  = False
                    st.session_state.lpa_generating      = True
                    st.session_state.lpa_result          = None
                    st.session_state.plan_already_saved  = False
                    st.rerun()

            # ── No-chapter warning popup ──────────────────────────────────────────
            if st.session_state.get("no_chapter_warning"):
                _no_chapter_dialog()

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
            p_total_p = sum(
                (st.session_state.get(f"cnt_p{r}") or 0)
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
                _pp_label = f"{p_total_p} period{'s' if p_total_p != 1 else ''}"
                st.markdown(
                    f'<div style="font-size:0.79rem;color:#3d3b38;margin:0.4rem 0 0.25rem 0;">'
                    f'Total · {_p_time_str}, {_pp_label}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

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

if not has_chapter_data and st.session_state.role != "My Plans" and st.session_state.lpa_result is None:
    if st.session_state.grade is None or st.session_state.subject is None:
        _msg = "Choose a grade and subject to get started."
    else:
        _msg = f"No content available yet for {st.session_state.subject}, {st.session_state.grade}."
    st.markdown(
        f'<div class="ws-placeholder">{_msg}</div>',
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════
#  GENERATE WORKSPACE
#  Change 2: tabs = Competencies · Lesson Plan · Assessment
# ═════════════════════════════════════════════════
elif st.session_state.role == "Generate":

    # ── Generation (needs chapter selected) ──────────────────────────────────
    if st.session_state.lpa_generating and st.session_state.teacher_ch_idx is not None and st.session_state.teacher_ch_idx < len(chapters):
        if st.session_state.teacher_ch_idx >= len(chapters):
            st.session_state.lpa_generating = False
            st.session_state.teacher_ch_idx = None
            st.rerun()
        selected_ch = chapters[st.session_state.teacher_ch_idx]
        if st.session_state.lpa_generating:

            # ── Launch background thread (once) and block until done ─────────
            # generate_lpa calls st.* inside the thread for progress rendering.
            # add_script_run_ctx propagates the current Streamlit script context
            # to the thread so those calls are valid and non-silent.
            _stop_ev = threading.Event()
            _rq      = queue.Queue()
            st.session_state.lpa_stop_event   = _stop_ev
            st.session_state.lpa_result_queue = _rq
            _t = threading.Thread(
                target=generate_lpa,
                kwargs=dict(
                    grade        = st.session_state.grade,
                    subject      = st.session_state.subject,
                    chapter      = selected_ch,
                    period_rows  = st.session_state.get("period_rows", [0]),
                    session      = st.session_state,
                    result_queue = _rq,
                    stop_event   = _stop_ev,
                ),
                daemon=True,
            )
            add_script_run_ctx(_t)   # allow st.* calls from the thread
            _t.start()
            st.session_state.lpa_thread = _t

            # ── Hidden Streamlit stop button + JS bridge ──────────────────────
            # The visible stop pill lives inside the progress box HTML header.
            # It fires a postMessage; the components.html listener below catches
            # it and clicks this hidden Streamlit button to set the stop_event.
            st.markdown(
                '<style>'
                'div[class*="st-key-btn_stop_generation"]{display:none!important;}'
                'div[data-testid="stDeployButton"]{display:none!important;}'
                '</style>',
                unsafe_allow_html=True,
            )
            if st.button("stop", key="btn_stop_generation"):
                if st.session_state.lpa_stop_event is not None:
                    st.session_state.lpa_stop_event.set()
            components.html(
                '<script>'
                'window.addEventListener("message",function(e){'
                '  if(e.data&&e.data.type==="aruvi_stop"){'
                '    var btns=window.parent.document'
                '      .querySelectorAll(\'button\');'
                '    for(var i=0;i<btns.length;i++){'
                '      if(btns[i].innerText.trim()==="stop"){'
                '        btns[i].click();break;'
                '      }'
                '    }'
                '  }'
                '});'
                '</script>',
                height=0,
                scrolling=False,
            )

            # ── Block until the thread puts a result on the queue ─────────────
            # This is intentionally blocking on the main thread — no rerun loop,
            # no flashing. generate_lpa drives all progress rendering itself via
            # progress_placeholder / timer_placeholder (valid because we passed
            # the script run context above). When the thread finishes (completed
            # or stopped), it puts the result dict on _rq and we continue.
            result = _rq.get()   # blocks until thread is done

            st.session_state.lpa_thread       = None
            st.session_state.lpa_stop_event   = None
            st.session_state.lpa_result_queue = None

            if result.get("stopped"):
                # User stopped — silently reset to state before Generate was pressed
                st.session_state.lpa_generating = False
                st.session_state.lpa_result     = None
                st.rerun()
            else:
                st.session_state.lpa_result        = result
                st.session_state.lpa_generating    = False
                st.session_state.teacher_generated = True
                st.session_state.show_save_prompt  = True
                st.session_state.grade             = None
                st.session_state.subject           = None
                st.session_state.period_rows       = []
                st.rerun()

    # ── Result block ─────────────────────────────────────────────────────────
    result = st.session_state.lpa_result
    if result is None and st.session_state.teacher_ch_idx is None:
        st.markdown(
            '<div class="ws-placeholder">Choose a chapter to get started, '
            'or view a saved plan from My Plans.</div>',
            unsafe_allow_html=True,
        )
    elif result is None:
        st.markdown(
            '<div class="ws-placeholder">'
            'Set your period budget and click Generate Lesson Plan &amp; Assessment.'
            '</div>',
            unsafe_allow_html=True,
        )
    elif result.get("error"):
        st.error(f"Generation failed: {result['error']}")
    else:
        # Get chapter data — from index if available, else use result metadata
        if st.session_state.teacher_ch_idx is not None and st.session_state.teacher_ch_idx < len(chapters):
            _chapter_export = chapters[st.session_state.teacher_ch_idx]
        else:
            # result now carries grade/subject/chapter_title/chapter_number from generate_lpa
            _ch_num_from_result = result.get("chapter_number")
            _chapter_export = next(
                (c for c in chapters if c["chapter_number"] == _ch_num_from_result),
                None
            )
            if _chapter_export is None:
                # Fallback: also try lo_handoff for backwards compat with old saved results
                _lo_list = result.get("lo_handoff", [])
                _ch_num_from_lo = _lo_list[0].get("chapter_number") if _lo_list else None
                _chapter_export = next(
                    (c for c in chapters if c["chapter_number"] == _ch_num_from_lo),
                    None
                )
            if _chapter_export is None:
                # Reconstruct minimal chapter dict from result metadata
                _chapter_export = {
                    "chapter_title":   result.get("chapter_title", "Chapter"),
                    "chapter_number":  result.get("chapter_number") or 0,
                    "chapter_weight":  "",
                    "primary":         [],
                }
        _safe_title = re.sub(r"[^\w\s-]", "", _chapter_export.get("chapter_title", "chapter")).strip().replace(" ", "_")[:40]
        _filename_stem = f"Aruvi_{_safe_title}"

        # ── Resolve grade / subject for PDF and save operations ───────────────
        # After generation, session grade/subject are cleared; use result's own copy.
        _res_grade   = st.session_state.grade   or result.get("grade",   "Grade VII")
        _res_subject = st.session_state.subject or result.get("subject", "Social Science")

        # ── "Do you want to save the plan?" popup — shown once after generation ─
        if st.session_state.get("show_save_prompt"):
            st.markdown("""<style>
div[class*="st-key-save_prompt_box"] {
    background:#fff;
    border:1px solid #d9d6d0;
    border-radius:10px;
    padding:1rem 1.25rem;
    margin-bottom:1rem;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);
}
div[class*="st-key-save_prompt_yes"] button {
    background-color:#2c3e50 !important;
    color:#fff !important;
    border:none !important;
}
div[class*="st-key-save_prompt_no"] button {
    background-color:#f2f0ec !important;
    color:#3d3b38 !important;
    border:1px solid #d9d6d0 !important;
}
</style>""", unsafe_allow_html=True)
            with st.container(key="save_prompt_box"):
                st.markdown(
                    '<div style="font-size:0.95rem;font-weight:500;color:#3d3b38;'
                    'margin-bottom:0.75rem;">Do you want to save the plan?</div>',
                    unsafe_allow_html=True,
                )
                _sp_c1, _sp_c2, _sp_rest = st.columns([1, 1, 3])
                with _sp_c1:
                    if st.button("Yes", key="save_prompt_yes", type="primary",
                                 use_container_width=True):
                        save_plan(
                            grade       = _res_grade,
                            subject     = _res_subject,
                            chapter     = _chapter_export,
                            period_rows = st.session_state.get("period_rows_snapshot",
                                          st.session_state.get("period_rows", [])),
                            session     = st.session_state,
                            result      = result,
                        )
                        st.session_state.show_save_prompt  = False
                        st.session_state.plan_just_saved   = True
                        st.session_state.plan_already_saved = True
                        st.rerun()
                with _sp_c2:
                    if st.button("No", key="save_prompt_no",
                                 use_container_width=True):
                        st.session_state.show_save_prompt = False
                        st.rerun()

        # ── Primary-style LP / Assessment / Save / Clear buttons ─────────────
        # CSS: match Generate button colour scheme; orange for Save button;
        #      Clear uses Streamlit primary style (same as LP / Assessment).
        st.markdown("""<style>
div[data-testid="stDownloadButton"] button[kind="primary"] {
    font-size: 0.82rem !important;
}
div[class*="st-key-gen_save_top"] button,
div[class*="st-key-gen-save-top"] button,
div[class*="st-key-gen_save_bot"] button,
div[class*="st-key-gen-save-bot"] button {
    background-color: #E87722 !important;
    color: #ffffff !important;
    border: none !important;
    font-size: 0.82rem !important;
}
div[class*="st-key-gen_clear_top"] button,
div[class*="st-key-gen-clear-top"] button,
div[class*="st-key-gen_clear_bot"] button,
div[class*="st-key-gen-clear-bot"] button {
    background-color: #1e2a38 !important;
    color: #ffffff !important;
    border: none !important;
    font-size: 0.82rem !important;
}
div[class*="st-key-gen_clear_top"] button:hover,
div[class*="st-key-gen-clear-top"] button:hover,
div[class*="st-key-gen_clear_bot"] button:hover,
div[class*="st-key-gen-clear-bot"] button:hover {
    background-color: #2c3e52 !important;
    color: #ffffff !important;
    border: none !important;
}
div[class*="st-key-gen_clear_top"] button p,
div[class*="st-key-gen-clear-top"] button p,
div[class*="st-key-gen_clear_bot"] button p,
div[class*="st-key-gen-clear-bot"] button p {
    color: #ffffff !important;
}
</style>""", unsafe_allow_html=True)
        _pdl_c1, _pdl_c2, _pdl_c3, _pdl_c4, _pdl_spc = st.columns([1, 1, 1, 1, 1])
        with _pdl_c1:
            try:
                from lp_pdf_generator import build_lp_pdf_bytes as _blpb_gen
                _gen_lp_payload = {
                    "saved_at":       datetime.now().isoformat(timespec="seconds"),
                    "grade":          _res_grade,
                    "subject":        _res_subject,
                    "chapter_number": _chapter_export.get("chapter_number", 0),
                    "chapter_title":  _chapter_export.get("chapter_title",  ""),
                    "result":         {"lesson_plan": result.get("lesson_plan", {})},
                }
                _gen_lp_bytes = _blpb_gen(_gen_lp_payload)
                st.download_button(
                    label="Lesson plan  ⬇",
                    data=_gen_lp_bytes,
                    file_name=f"{_filename_stem}_LP.pdf",
                    mime="application/pdf",
                    key="gen_lp_primary_dl",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as _gen_lp_err:
                st.caption(f"LP PDF error: {_gen_lp_err}")
        with _pdl_c2:
            try:
                from assessment_pdf_generator import build_assessment_pdf_bytes as _bapb_gen
                _gen_assess_payload = {
                    "saved_at":       datetime.now().isoformat(timespec="seconds"),
                    "grade":          _res_grade,
                    "subject":        _res_subject,
                    "chapter_number": _chapter_export.get("chapter_number", 0),
                    "chapter_title":  _chapter_export.get("chapter_title",  ""),
                    "result": {
                        "lesson_plan":      result.get("lesson_plan", {}),
                        "assessment_items": result.get("assessment_items", []),
                    },
                }
                _gen_assess_bytes = _bapb_gen(_gen_assess_payload)
            except Exception as _gen_assess_err:
                _gen_assess_bytes = b""
            st.download_button(
                label="Assessment  ⬇",
                data=_gen_assess_bytes if _gen_assess_bytes else b"",
                file_name=f"{_filename_stem}_Assessment.pdf",
                mime="application/pdf",
                key="gen_assess_primary_dl",
                type="primary",
                use_container_width=True,
            )
        with _pdl_c3:
            _already_saved = st.session_state.get("plan_already_saved", False)
            if st.button(
                "Saved ✓" if _already_saved else "Save to my plans",
                key="gen_save_top",
                use_container_width=True,
                disabled=_already_saved,
            ):
                save_plan(
                    grade       = _res_grade,
                    subject     = _res_subject,
                    chapter     = _chapter_export,
                    period_rows = st.session_state.get("period_rows", [0]),
                    session     = st.session_state,
                    result      = result,
                )
                st.session_state.plan_just_saved    = True
                st.session_state.plan_already_saved = True
                st.rerun()
        with _pdl_c4:
            if st.button(
                "Clear",
                key="gen_clear_top",
                use_container_width=True,
            ):
                st.session_state.lpa_result         = None
                st.session_state.show_save_prompt   = False
                st.session_state.plan_already_saved = False
                st.session_state.plan_just_saved    = False
                st.rerun()
        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

        # ── LPA HTML page ─────────────────────────────────────────────────
        _lpa_html_path = PROJECT_ROOT / "lpa_page.html"
        try:
            _lpa_tpl = _lpa_html_path.read_text(encoding="utf-8")
        except Exception:
            _lpa_tpl = "<p>lpa_page.html not found.</p>"

        if st.session_state.teacher_ch_idx is not None and st.session_state.teacher_ch_idx < len(chapters):
            _ch_data = chapters[st.session_state.teacher_ch_idx]
        else:
            _ch_data = _chapter_export
        _period_schedule = " · ".join(
            f'{st.session_state.get(f"cnt_{r}", 1)} × {st.session_state.get(f"dur_sel_{r}", 40)}-min'
            for r in st.session_state.get("period_rows", [0])
        )

        # ── Normalise to lpa_page.html-compatible shape (handles old + new JSON) ─
        _grade_ctx   = _res_grade
        _subject_ctx = _res_subject
        _stage  = get_stage(_grade_ctx)
        _subj_f = subject_to_folder(_subject_ctx)
        try:
            _comp_descs = json.loads(
                (PROJECT_ROOT / f"mirror/framework/{_subj_f}/{_stage}"
                 / f"competency_descriptions_{_stage}.json")
                .read_text(encoding="utf-8")
            )
        except Exception:
            _comp_descs = {}

        _lo_handoff          = _normalise_lo_handoff(result, _comp_descs)
        _assessment_sections = _normalise_assessment_sections(result, _comp_descs)

        _lpa_data = {
            "chapter_title":       _ch_data.get("chapter_title", ""),
            "chapter_number":      _ch_data.get("chapter_number", ""),
            "grade":               _res_grade,
            "subject":             _res_subject,
            "period_schedule":     _period_schedule,
            "lo_handoff":          _lo_handoff,
            "assessment_sections": _assessment_sections,
        }
        _lpa_inject = "window.LPA_DATA = " + json.dumps(_lpa_data, ensure_ascii=False) + ";\n"
        _lpa_html = _lpa_tpl.replace("/* __LPA_DATA__ */", _lpa_inject)
        _lpa_height_script = """
<script>
(function() {
  /* Measure the actual .lpa content element — avoids the scrollHeight==viewport
     problem (scrollHeight equals iframe height when content is shorter). */
  function fitIframe() {
    var lpa = document.querySelector('.lpa');
    if (!lpa) return;
    var h = Math.ceil(lpa.getBoundingClientRect().height) + 24;
    if (h < 100) return;

    /* Method A: window.frameElement (works when Streamlit serves component
       via a same-origin URL, i.e. localhost:8501/component/...) */
    try {
      var fe = window.frameElement;
      if (fe) {
        fe.style.height = h + 'px';
        var p1 = fe.parentElement;
        if (p1) { p1.style.height = h + 'px'; p1.style.minHeight = '0'; }
        var p2 = p1 && p1.parentElement;
        if (p2) { p2.style.height = h + 'px'; p2.style.minHeight = '0'; }
      }
    } catch(e) {}

    /* Method B: access the Streamlit page DOM directly from the parent window
       (same-origin: Streamlit app and component URL share localhost:8501).
       Find the component iframe by its Streamlit-assigned height attribute and
       collapse it + its wrapper containers to the measured content height. */
    try {
      var pDoc = window.parent.document;
      /* Streamlit renders: <iframe height="2200" ...> inside a wrapper div */
      var targets = pDoc.querySelectorAll('iframe[height="2200"]');
      for (var i = 0; i < targets.length; i++) {
        var fr = targets[i];
        fr.setAttribute('height', String(h));
        fr.style.height = h + 'px';
        var w1 = fr.parentElement;
        if (w1) { w1.style.height = h + 'px'; w1.style.minHeight = '0'; }
        var w2 = w1 && w1.parentElement;
        if (w2) { w2.style.height = h + 'px'; w2.style.minHeight = '0'; }
      }
    } catch(e) {}

    /* Method C: Streamlit postMessage protocol (both recognised formats) */
    try {
      window.parent.postMessage({ type: 'streamlit:setFrameHeight', height: h }, '*');
      window.parent.postMessage(
        { isStreamlitMessage: true, type: 'streamlit:setFrameHeight', height: h }, '*'
      );
    } catch(e) {}
  }

  /* lpa_page.html fires its own (broken) reportHeight at 100 ms, 400 ms, 800 ms.
     Those calls measure scrollHeight which equals the 2200 px viewport height and
     would override a correct value. We fire JUST AFTER each one to win the race,
     plus an early shot and a late cleanup pass. */
  setTimeout(fitIframe,   50);
  setTimeout(fitIframe,  150);  /* override broken 100 ms call  */
  setTimeout(fitIframe,  450);  /* override broken 400 ms call  */
  setTimeout(fitIframe,  850);  /* override broken 800 ms call  */
  setTimeout(fitIframe, 1200);  /* final cleanup                */

  /* Re-fit on every collapsible expand / collapse */
  var t = null;
  function dFit() { clearTimeout(t); t = setTimeout(fitIframe, 150); }
  if (document.body) {
    new MutationObserver(dFit).observe(
      document.body, { childList: true, subtree: true, attributes: true }
    );
  }
})();
</script>
"""
        _lpa_html = _lpa_html + _lpa_height_script
        components.html(_lpa_html, height=2200, scrolling=False)

        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
        _bot_c1, _bot_c2, _bot_c3, _bot_c4, _bot_spc = st.columns([1, 1, 1, 1, 1])
        with _bot_c1:
            try:
                from lp_pdf_generator import build_lp_pdf_bytes as _blpb_bot
                _bot_lp_payload = {
                    "saved_at":       datetime.now().isoformat(timespec="seconds"),
                    "grade":          _res_grade,
                    "subject":        _res_subject,
                    "chapter_number": _chapter_export.get("chapter_number", 0),
                    "chapter_title":  _chapter_export.get("chapter_title",  ""),
                    "result":         {"lesson_plan": result.get("lesson_plan", {})},
                }
                _bot_lp_bytes = _blpb_bot(_bot_lp_payload)
                st.download_button(
                    label="Lesson plan  ⬇",
                    data=_bot_lp_bytes,
                    file_name=f"{_filename_stem}_LP.pdf",
                    mime="application/pdf",
                    key="gen_lp_bot_dl",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as _bot_lp_err:
                st.caption(f"LP PDF error: {_bot_lp_err}")
        with _bot_c2:
            try:
                from assessment_pdf_generator import build_assessment_pdf_bytes as _bapb_bot
                _bot_assess_payload = {
                    "saved_at":       datetime.now().isoformat(timespec="seconds"),
                    "grade":          _res_grade,
                    "subject":        _res_subject,
                    "chapter_number": _chapter_export.get("chapter_number", 0),
                    "chapter_title":  _chapter_export.get("chapter_title",  ""),
                    "result": {
                        "lesson_plan":      result.get("lesson_plan", {}),
                        "assessment_items": result.get("assessment_items", []),
                    },
                }
                _bot_assess_bytes = _bapb_bot(_bot_assess_payload)
            except Exception:
                _bot_assess_bytes = b""
            st.download_button(
                label="Assessment  ⬇",
                data=_bot_assess_bytes if _bot_assess_bytes else b"",
                file_name=f"{_filename_stem}_Assessment.pdf",
                mime="application/pdf",
                key="gen_assess_bot_dl",
                type="primary",
                use_container_width=True,
            )
        with _bot_c3:
            _already_saved_bot = st.session_state.get("plan_already_saved", False)
            if st.button(
                "Saved ✓" if _already_saved_bot else "Save to my plans",
                key="gen_save_bot",
                use_container_width=True,
                disabled=_already_saved_bot,
            ):
                save_plan(
                    grade       = _res_grade,
                    subject     = _res_subject,
                    chapter     = _chapter_export,
                    period_rows = st.session_state.get("period_rows", [0]),
                    session     = st.session_state,
                    result      = result,
                )
                st.session_state.plan_just_saved    = True
                st.session_state.plan_already_saved = True
                st.rerun()
        with _bot_c4:
            if st.button(
                "Clear",
                key="gen_clear_bot",
                use_container_width=True,
            ):
                st.session_state.lpa_result         = None
                st.session_state.show_save_prompt   = False
                st.session_state.plan_already_saved = False
                st.session_state.plan_just_saved    = False
                st.rerun()
        if st.session_state.get("plan_just_saved"):
            st.success("Saved — view it in My Plans.")
            st.session_state.plan_just_saved = False


# ═════════════════════════════════════════════════
#  ALLOCATE WORKSPACE
# ═════════════════════════════════════════════════
elif st.session_state.role == "Allocate":

    # ── Gather period types from sidebar state ─────────────────────────────────
    _pt_rows = st.session_state.get("period_rows_p", [0])
    _period_types = [
        {
            "mins":  int(st.session_state.get(f"dur_sel_p{r}") or 40),
            "count": int(st.session_state.get(f"cnt_p{r}")     or 1),
        }
        for r in _pt_rows
    ]
    _period_types = [pt for pt in _period_types if pt["mins"] > 0 and pt["count"] > 0]
    _sorted_pts   = sorted(_period_types, key=lambda pt: -pt["mins"])

    # ── Load full mapping JSONs for all chapters ───────────────────────────────
    def _load_chapter_mappings(grade, subject):
        _stage  = get_stage(grade)
        _subj_f = subject_to_folder(subject)

        # Load competency descriptions lookup (keyed by c_code → description text)
        _comp_desc_path = (
            PROJECT_ROOT
            / f"mirror/framework/{_subj_f}/{_stage}"
            / f"competency_descriptions_{_stage}.json"
        )
        try:
            _raw_descs = json.loads(_comp_desc_path.read_text(encoding="utf-8"))
            # Three formats exist:
            #   Science:     {curricular_goals: [{cg_code, competencies: [{code, description}]}]}  ← list of objects
            #   Mathematics: {curricular_goals: {"CG-1": {competency_codes: {"C-1.1": "text"}}}}   ← dict of dicts
            #   SS/Lang:     {c_code: description_string, ...}                                      ← flat dict
            if "curricular_goals" in _raw_descs:
                _cg_val = _raw_descs["curricular_goals"]
                _comp_descs = {}
                if isinstance(_cg_val, list):
                    # Science format: list of CG objects
                    for _cg in _cg_val:
                        for _comp in _cg.get("competencies", []):
                            _comp_descs[_comp.get("code", "")] = _comp.get("description", "")
                elif isinstance(_cg_val, dict):
                    # Mathematics format: dict keyed by CG code
                    for _cg_code, _cg_body in _cg_val.items():
                        _ccodes = _cg_body.get("competency_codes", {})
                        for _c_code, _desc in _ccodes.items():
                            _comp_descs[_c_code] = _desc
            else:
                _comp_descs = _raw_descs
        except Exception:
            _comp_descs = {}

        _result = []
        for _ch in chapters:
            _paths = resolve_paths(grade, subject, _ch["chapter_number"])
            try:
                _mapping = json.loads(
                    _paths["chapter_mapping"].read_text(encoding="utf-8")
                )
            except Exception:
                _mapping = {}

            # Enrich primary competencies with full description text.
            # Key order: "primary" (Science VII), "competencies" (VI schema),
            # then Mathematics which uses "core_competencies" + "adjunct_competencies".
            if "primary" in _mapping or "competencies" in _mapping:
                _primary_entries = _mapping.get("primary", _mapping.get("competencies", []))
            else:
                # Mathematics schema: merge core + adjunct
                _primary_entries = (
                    _mapping.get("core_competencies", []) +
                    _mapping.get("adjunct_competencies", [])
                )
            _enriched_primary = []
            for _entry in _primary_entries:
                _e = dict(_entry)
                _e["description"] = _comp_descs.get(_entry.get("c_code", ""), "")
                _enriched_primary.append(_e)

            _result.append({
                "chapter_number":    _ch["chapter_number"],
                "chapter_title":     _ch.get("chapter_title", ""),
                "chapter_weight":    _mapping.get("chapter_weight", 0),
                "effort_index":      _mapping.get("effort_index", 0),
                # Science signals
                "conceptual_demand": _mapping.get("conceptual_demand", 0),
                "activity_count":    _mapping.get("activity_count", 0),
                "demo_count":        _mapping.get("demo_count", 0),
                "exec_load":         _mapping.get("exec_load", 0),
                # English signals
                "spine_load":        _mapping.get("spine_load", 0),
                "task_density":      _mapping.get("task_density", 0),
                "writing_demand":    _mapping.get("writing_demand", 0),
                "project_load":      _mapping.get("project_load", 0),
                "primary":           _enriched_primary,
                "incidental":        _mapping.get("incidental", []),
            })
        return _result

    _chapters_data = _load_chapter_mappings(
        st.session_state.grade, st.session_state.subject
    )

    # ── Load HTML template and inject data ────────────────────────────────────
    _html_path = PROJECT_ROOT / "allocate_page.html"
    _html_tpl  = _html_path.read_text(encoding="utf-8")

    import base64 as _b64
    _logo_path = PROJECT_ROOT / "miscellaneous/aruvi_logo-transparent.png"
    try:
        _logo_b64 = _b64.b64encode(_logo_path.read_bytes()).decode()
    except Exception:
        _logo_b64 = ""

    # Load English spine data for the PDF report (textbook_section_names + competency codes)
    _english_spine_data = {}
    if st.session_state.subject == "English":
        _stage = get_stage(st.session_state.grade)
        _spine_path = PROJECT_ROOT / f"mirror/framework/english/{_stage}/spine_to_cg.json"
        try:
            _spine_raw = json.loads(_spine_path.read_text(encoding="utf-8"))
            _english_spine_data = _spine_raw.get("spines", {})
        except Exception:
            _english_spine_data = {}

    _inject = (
        f"const CHAPTERS_DATA  = {json.dumps(_chapters_data, ensure_ascii=False)};\n"
        f"const PERIOD_TYPES   = {json.dumps(_sorted_pts)};\n"
        f"const GRADE_LABEL    = {json.dumps(st.session_state.grade    or '')};\n"
        f"const SUBJECT_LABEL  = {json.dumps(st.session_state.subject  or '')};\n"
        f"const IS_SCIENCE     = {json.dumps(st.session_state.subject in ('Science', 'Mathematics'))};\n"
        f"const IS_ENGLISH     = {json.dumps(st.session_state.subject == 'English')};\n"
        f"const ARUVI_LOGO_B64 = {json.dumps(_logo_b64)};\n"
        f"const ENGLISH_SPINE_DATA = {json.dumps(_english_spine_data, ensure_ascii=False)};\n"
    )
    _html = _html_tpl.replace("/* __CHAPTERS_DATA__ */", _inject)

    # Inject the correct footnote text directly into the static HTML so it is
    # correct on first render, before any JS runs.
    _subject = st.session_state.subject or ""
    if _subject == "English":
        _fn1_text = (
            '<div class="about-ei">'
            '<h4>About the Effort Index</h4>'
            '<p>The effort index is a number that tells you how much classroom '
            'time a chapter typically needs compared to other chapters in the '
            'subject. Chapters with a higher effort index get more periods; '
            'chapters with a lower one get fewer. It is calculated from four '
            'signals, each scored on a simple scale.</p>'
            '<ul>'
            '<li><b>Spine load</b> — How many types of classroom work '
            '(reading for comprehension, listening, speaking, writing, '
            'vocabulary, beyond-text) appear on average per section. '
            'More types = higher score.</li>'
            '<li><b>Task density</b> — How many tasks appear on average '
            'within each block of work. More tasks per block = higher '
            'score.</li>'
            '<li><b>Writing demand</b> — Total exercise items under '
            'Writing and Beyond-the-Text across the chapter. These take '
            'longer to complete and assess, so a heavier count raises the '
            'score.</li>'
            '<li><b>Project load</b> — How many Beyond-the-Text sections '
            'the chapter has. Each one adds to the score as these activities '
            'need extra planning time.</li>'
            '</ul>'
            '<p class="about-ei-close">The four scores are combined with '
            'fixed weights to give the effort index. Only relative values '
            'matter — it is used to share your available periods across '
            'chapters in proportion to their load.</p>'
            '</div>'
        )
    elif _subject in ("Science", "Mathematics"):
        _fn1_text = (
            '<div class="about-ei">'
            '<h4>About the Effort Index</h4>'
            '<p>The effort index is a number that tells you how much classroom '
            'time a chapter typically needs compared to other chapters in the '
            'subject. Chapters with a higher effort index get more periods; '
            'chapters with a lower one get fewer. It is calculated from four '
            'signals read from the chapter content.</p>'
            '<ul>'
            '<li><b>Conceptual demand (×2)</b> — The cognitive complexity of exercises and questions '
            'in the chapter. High-order thinking or multi-step reasoning raises the score.</li>'
            '<li><b>Student activities (×1)</b> — The number of hands-on activities that students '
            'perform themselves. Each activity adds classroom time for setup, execution and discussion.</li>'
            '<li><b>Teacher demonstrations (×1.5)</b> — The number of demonstrations the teacher must '
            'conduct. These need preparation and focused class attention.</li>'
            '<li><b>Exercise execution load (×2)</b> — The total exercise items students must complete. '
            'A heavier exercise count means more time for guided practice and assessment.</li>'
            '</ul>'
            '<p class="about-ei-close">The four signals are combined with fixed weights to give the '
            'effort index. Only relative values matter — it is used to share your available periods '
            'across chapters in proportion to their load.</p>'
            '</div>'
        )
    else:
        _fn1_text = (
            "Periods allocated using the Largest Remainder Method (LRM), "
            "weighted by chapter competency load (W3 × 3 +"
            " W2 × 2 + W1 × 1)."
        )
    _html = _html.replace('<p id="fn1"></p>', f'<p id="fn1">{_fn1_text}</p>')

    components.html(_html, height=950, scrolling=True)

else:
    # ═════════════════════════════════════════════════
    #  MY PLANS WORKSPACE
    # ═════════════════════════════════════════════════

    if "mp_grade_filter"   not in st.session_state: st.session_state.mp_grade_filter   = "All"
    if "mp_subject_filter" not in st.session_state: st.session_state.mp_subject_filter = "All"

    _sp_root = PROJECT_ROOT / "mirror" / "saved_plans"

    # ── Detail view — shown when a plan row's View button has been clicked ────
    if st.session_state.mp_viewing_plan is not None:
        _vp       = st.session_state.mp_viewing_plan
        _vgrade   = _vp.get("grade",   "")
        _vsubject = _vp.get("subject", "")
        _v_ch_num   = _vp.get("chapter_number", 0)
        _v_ch_title = _vp.get("chapter_title",  "")

        # ── Back button (top) ─────────────────────────────────────────────────
        if st.button("← Back to My Plans", key="mp_back_top"):
            st.session_state.mp_viewing_plan = None
            st.rerun()

        st.markdown('<div style="height:0.25rem;"></div>', unsafe_allow_html=True)

        # ── Resolve chapter export dict ───────────────────────────────────────
        _v_all_chapters = load_all_chapters(_vgrade, _vsubject) if (_vgrade and _vsubject) else []
        _v_chapter_export = next(
            (c for c in _v_all_chapters if c["chapter_number"] == _v_ch_num), None
        )
        if _v_chapter_export is None:
            _v_chapter_export = {
                "chapter_title":  _v_ch_title,
                "chapter_number": _v_ch_num,
                "chapter_weight": "",
                "primary":        [],
            }

        _vresult = dict(_vp["result"])

        # ── Competency descriptions ───────────────────────────────────────────
        _v_stage  = get_stage(_vgrade)          if _vgrade   else "middle"
        _v_subj_f = subject_to_folder(_vsubject) if _vsubject else "social_sciences"
        try:
            _v_comp_descs = json.loads(
                (PROJECT_ROOT / f"mirror/framework/{_v_subj_f}/{_v_stage}"
                 / f"competency_descriptions_{_v_stage}.json")
                .read_text(encoding="utf-8")
            )
        except Exception:
            _v_comp_descs = {}

        # ── Normalise to lpa_page.html-compatible shape (handles old + new JSON) ─
        _v_lo_handoff          = _normalise_lo_handoff(_vresult, _v_comp_descs)
        _v_assessment_sections = _normalise_assessment_sections(_vresult, _v_comp_descs)

        # ── Render LPA HTML page ──────────────────────────────────────────────
        try:
            _v_lpa_tpl = (PROJECT_ROOT / "lpa_page.html").read_text(encoding="utf-8")
        except Exception:
            _v_lpa_tpl = "<p>lpa_page.html not found.</p>"

        _v_lpa_data = {
            "chapter_title":       _v_ch_title,
            "chapter_number":      _v_ch_num,
            "grade":               _vgrade,
            "subject":             _vsubject,
            "period_schedule":     _vp.get("period_schedule_display", ""),
            "lo_handoff":          _v_lo_handoff,
            "assessment_sections": _v_assessment_sections,
        }
        _v_lpa_inject = "window.LPA_DATA = " + json.dumps(_v_lpa_data, ensure_ascii=False) + ";\n"
        _v_lpa_height_script = """
<script>
(function() {
  /* Measure the .lpa content element directly — avoids the scrollHeight==viewport
     problem that occurs when the iframe is taller than its content. */
  function fitIframe() {
    var lpa = document.querySelector('.lpa');
    if (!lpa) return;
    var h = Math.ceil(lpa.getBoundingClientRect().height) + 20;
    if (h < 100) return;
    /* Primary: set the parent <iframe> height directly (same-origin) */
    try {
      if (window.frameElement) {
        window.frameElement.style.height = h + 'px';
      }
    } catch(e) {}
    /* Fallback: Streamlit postMessage protocol */
    try {
      window.parent.postMessage(
        { isStreamlitMessage: true, type: 'streamlit:setFrameHeight', height: h }, '*'
      );
    } catch(e) {}
  }
  /* Fire at staggered intervals to cover all JS rendering phases */
  setTimeout(fitIframe, 50);
  setTimeout(fitIframe, 250);
  setTimeout(fitIframe, 600);
  setTimeout(fitIframe, 1000);
  /* Re-fit whenever collapsible sections expand / collapse */
  var debounceTimer = null;
  function debouncedFit() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fitIframe, 150);
  }
  if (document.body) {
    new MutationObserver(debouncedFit).observe(
      document.body, { childList: true, subtree: true, attributes: true }
    );
  }
})();
</script>
"""
        _v_lpa_html = _v_lpa_tpl.replace("/* __LPA_DATA__ */", _v_lpa_inject) + _v_lpa_height_script
        components.html(
            _v_lpa_html,
            height=2200, scrolling=False,
        )

        st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)
        st.divider()

        # ── Back button (bottom) ──────────────────────────────────────────────
        if st.button("← Back to My Plans", key="mp_back_bottom"):
            st.session_state.mp_viewing_plan = None
            st.rerun()


    if st.session_state.mp_viewing_plan is None:
        # Load ALL saved plans across all grades/subjects
        _all_plans = []
        if _sp_root.exists():
            for _f in sorted(_sp_root.rglob("ch_*.json"), reverse=True):
                try:
                    _all_plans.append(json.loads(_f.read_text(encoding="utf-8")))
                except Exception:
                    pass

        # Filter dropdowns — inline, no sidebar
        _f_grade, _f_subject, _f_spacer = st.columns([2, 2, 5])
        with _f_grade:
            _grade_opts = ["All"] + GRADES
            _g_idx = _grade_opts.index(st.session_state.mp_grade_filter) if st.session_state.mp_grade_filter in _grade_opts else 0
            _new_g = st.selectbox("Grade", _grade_opts, index=_g_idx, label_visibility="collapsed", key="mp_grade_sel")
            if _new_g != st.session_state.mp_grade_filter:
                st.session_state.mp_grade_filter = _new_g
                st.rerun()
        with _f_subject:
            _subj_opts = ["All"] + SUBJECTS
            _s_idx = _subj_opts.index(st.session_state.mp_subject_filter) if st.session_state.mp_subject_filter in _subj_opts else 0
            _new_s = st.selectbox("Subject", _subj_opts, index=_s_idx, label_visibility="collapsed", key="mp_subject_sel")
            if _new_s != st.session_state.mp_subject_filter:
                st.session_state.mp_subject_filter = _new_s
                st.rerun()

        # Apply filters
        _visible = [
            p for p in _all_plans
            if (st.session_state.mp_grade_filter   == "All" or p.get("grade")   == st.session_state.mp_grade_filter)
            and (st.session_state.mp_subject_filter == "All" or p.get("subject") == st.session_state.mp_subject_filter)
        ]

        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

        if not _visible:
            st.markdown(
                '<div class="ws-placeholder">No saved plans yet. '
                'Generate a plan and click Save to My Plans.</div>',
                unsafe_allow_html=True,
            )
        else:
            # ── Pure-Streamlit column table (header + inline buttons per row) ───────
            st.markdown("""
    <style>
    .mp-th       { font-size:0.65rem; font-weight:600; letter-spacing:0.08em;
                   text-transform:uppercase; color:#5a5754; padding-bottom:2px; }
    .mp-ch-title { font-size:0.88rem; font-weight:500; color:#1a1917; margin-bottom:2px; }
    .mp-ch-meta  { font-size:0.72rem; color:#9c9693; }
    .mp-cell     { font-size:0.82rem; color:#3d3b38; padding-top:6px; }
    </style>
    """, unsafe_allow_html=True)

            # Header row
            _hc = st.columns([3, 1, 1.5, 0.8, 1.2, 1.2])
            _hc[0].markdown('<div class="mp-th">Chapter</div>',       unsafe_allow_html=True)
            _hc[1].markdown('<div class="mp-th">Grade</div>',         unsafe_allow_html=True)
            _hc[2].markdown('<div class="mp-th">Saved</div>',         unsafe_allow_html=True)
            _hc[3].markdown('<div class="mp-th">Display</div>',       unsafe_allow_html=True)
            _hc[4].markdown('<div class="mp-th" style="text-align:left;">Lesson plan</div>',   unsafe_allow_html=True)
            _hc[5].markdown('<div class="mp-th" style="text-align:left;">Assessment</div>',    unsafe_allow_html=True)
            st.markdown(
                '<hr style="margin:4px 0 6px;border:none;border-top:1px solid #e8e5e0;">',
                unsafe_allow_html=True,
            )

            # One row per plan
            for _p in _visible:
                _ch_num   = _p.get("chapter_number", 0)
                _ch_title = _p.get("chapter_title", "")
                _grade    = _p.get("grade", "")
                _subject  = _p.get("subject", "")
                _saved_at = _p.get("saved_at", "")[:10]
                _filename = _p.get("filename", "")
                _safe_fn  = re.sub(r"[^a-zA-Z0-9_]", "_", _filename)
                try:
                    from datetime import datetime as _dt
                    _saved_disp = _dt.fromisoformat(_saved_at).strftime("%-d %b %Y")
                except Exception:
                    _saved_disp = _saved_at
                _ch_for_pdf = next(
                    (c for c in chapters if c["chapter_number"] == _ch_num),
                    {"chapter_title": _ch_title, "chapter_weight": "",
                     "chapter_number": _ch_num, "primary": []}
                )
                # LP PDF via lp_pdf_generator (new ReportLab format)
                try:
                    from lp_pdf_generator import build_lp_pdf_bytes as _blpb_mp
                    _mp_lp_payload = {
                        "saved_at":       _p.get("saved_at", datetime.now().isoformat(timespec="seconds")),
                        "grade":          _grade,
                        "subject":        _subject,
                        "chapter_number": _ch_num,
                        "chapter_title":  _ch_title,
                        "result":         {"lesson_plan": _p["result"].get("lesson_plan", {})},
                    }
                    _mp_lp_bytes = _blpb_mp(_mp_lp_payload)
                except Exception:
                    _mp_lp_bytes = b""
                # Assessment PDF — new ReportLab format
                try:
                    from assessment_pdf_generator import build_assessment_pdf_bytes as _bapb_mp
                    _mp_assess_bytes = _bapb_mp(_p)
                except Exception:
                    _mp_assess_bytes = b""
                _safe_t = re.sub(r"[^\w\s-]", "", _ch_title).strip().replace(" ", "_")[:40]

                _rc = st.columns([3, 1, 1.5, 0.8, 1.2, 1.2])
                _rc[0].markdown(
                    f'<div class="mp-ch-title">{_ch_title}</div>'
                    f'<div class="mp-ch-meta">Ch {str(_ch_num).zfill(2)} · {_subject}</div>',
                    unsafe_allow_html=True,
                )
                _rc[1].markdown(f'<div class="mp-cell">{_grade}</div>',       unsafe_allow_html=True)
                _rc[2].markdown(f'<div class="mp-cell">{_saved_disp}</div>',  unsafe_allow_html=True)
                with _rc[3]:
                    if st.button("View", key=f"view_{_safe_fn}", use_container_width=True):
                        st.session_state.mp_viewing_plan = _p
                        st.rerun()
                with _rc[4]:
                    st.download_button(
                        label="PDF ⬇",
                        data=_mp_lp_bytes,
                        file_name=f"Aruvi_{_safe_t}_LP.pdf",
                        mime="application/pdf",
                        key=f"mp_lp_{_safe_fn}",
                        type="primary",
                    )
                with _rc[5]:
                    st.download_button(
                        label="PDF ⬇",
                        data=_mp_assess_bytes if _mp_assess_bytes else b"",
                        file_name=f"Aruvi_{_safe_t}_Assessment.pdf",
                        mime="application/pdf",
                        key=f"mp_assess_{_safe_fn}",
                        type="primary",
                    )
                st.markdown(
                    '<hr style="margin:2px 0;border:none;border-top:0.5px solid #f0ede9;">',
                    unsafe_allow_html=True,
                )

# ── Ask Aruvi FAB + Bottom Drawer ────────────────────────────────────────────
CATEGORY_LABELS = {
    "cat_c": "The competency framework",
    "cat_a": "How Aruvi plans lessons",
    "cat_b": "How Aruvi builds assessments",
    "cat_d": "Using the platform",
    "cat_e": "What Aruvi cannot do",
}
st.markdown("""
<style>
/* ── Popup card ── */
div[class*="st-key-ask_aruvi_popup"] {
    position: fixed !important;
    bottom: 90px !important;
    right: 28px !important;
    width: 320px !important;
    max-height: 75vh !important;
    background: #FFFFFF !important;
    border-radius: 16px !important;
    border: 1px solid #E0DDD8 !important;
    z-index: 99998 !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.20), 0 4px 16px rgba(0,0,0,0.10) !important;
    overflow-y: auto !important;
    padding: 0 !important;
}
/* ── Secondary popup (Q&A + Feedback) — taller than category popup ── */
div[class*="st-key-ask_aruvi_agent_popup"] {
    position: fixed !important;
    bottom: 90px !important;
    right: 28px !important;
    width: 320px !important;
    max-height: 83vh !important;
    background: #FFFFFF !important;
    border-radius: 16px !important;
    border: 1px solid #E0DDD8 !important;
    z-index: 99999 !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.20), 0 4px 16px rgba(0,0,0,0.10) !important;
    overflow-y: auto !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] [data-testid="stVerticalBlock"] {
    gap: 0px !important;
    row-gap: 0px !important;
    padding-bottom: 40px !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] [data-testid="element-container"],
div[class*="st-key-ask_aruvi_agent_popup"] [data-testid="stVerticalBlockBorderWrapper"] {
    margin: 0 !important;
    padding: 0 !important;
}
/* Agent panel — reuse same chip/button/textarea rules via agent selector */
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_query_input"] {
    padding: 0 12px 0 12px !important;
    margin: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_query_input"] [data-baseweb="textarea"],
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_query_input"] > div {
    overflow: visible !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_query_input"] textarea {
    height: 104px !important;
    min-height: 104px !important;
    font-size: 0.85rem !important;
    border-radius: 10px !important;
    border: 1px solid #E0DDD8 !important;
    resize: none !important;
    line-height: 1.5 !important;
    padding: 10px 36px 10px 12px !important;
    background: #FAFAF8 !important;
    color: #5A5754 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_query_input"] textarea::placeholder {
    color: #C0BCB8 !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_text"] {
    padding: 0 12px 0 12px !important;
    margin: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_text"] [data-baseweb="textarea"],
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_text"] > div {
    overflow: visible !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_text"] textarea {
    height: 104px !important;
    min-height: 104px !important;
    font-size: 0.85rem !important;
    border-radius: 10px !important;
    border: 1px solid #E0DDD8 !important;
    resize: none !important;
    line-height: 1.5 !important;
    padding: 10px 36px 10px 12px !important;
    background: #FAFAF8 !important;
    color: #5A5754 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_text"] textarea::placeholder {
    color: #C0BCB8 !important;
}
/* Submit buttons (↑) inside agent panel */
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_submit"],
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_submit"] {
    position: relative !important;
    height: 0 !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_submit"] > div,
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_submit"] > div > div,
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_submit"] > div,
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_submit"] > div > div {
    height: 0 !important;
    width: 100% !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_submit"] button,
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_submit"] button {
    position: absolute !important;
    top: 4px !important;
    right: 14px !important;
    width: 26px !important;
    height: 26px !important;
    min-height: 26px !important;
    min-width: 26px !important;
    max-width: 26px !important;
    border-radius: 50% !important;
    background: #E8682A !important;
    border: none !important;
    color: #FFFFFF !important;
    font-size: 0.85rem !important;
    padding: 0 !important;
    z-index: 20 !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_submit"] button:hover,
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_fb_submit"] button:hover {
    background: #C95820 !important;
}
/* Back + close buttons inside agent panel */
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-aa_agent_back_btn"] button {
    background: transparent !important;
    border: none !important;
    color: #2C7A7B !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    padding: 12px 16px 10px 16px !important;
    min-height: unset !important;
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-bottom: 1px solid #F0EDE9 !important;
    border-radius: 0 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_close"] button {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid #F0EDE9 !important;
    border-radius: 0 !important;
    color: #2C7A7B !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    padding: 12px 16px 10px 16px !important;
    min-height: unset !important;
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[class*="st-key-ask_aruvi_agent_popup"] div[class*="st-key-ask_aruvi_agent_close"] button:hover {
    background: #F5F9F9 !important;
    color: #1B2A3B !important;
}
/* Entry-point button in main popup — style as a subdued link row */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_open_agent_panel"] button {
    background: transparent !important;
    border: none !important;
    border-top: 1px solid #F0EDE9 !important;
    border-radius: 0 !important;
    color: #2C7A7B !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    width: 100% !important;
    padding: 12px 16px !important;
    min-height: unset !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_open_agent_panel"] button:hover {
    background: #F5F9F9 !important;
    color: #1B2A3B !important;
}
/* Kill all Streamlit internal spacing */
div[class*="st-key-ask_aruvi_popup"] [data-testid="stVerticalBlock"] {
    gap: 0px !important;
    row-gap: 0px !important;
}
div[class*="st-key-ask_aruvi_popup"] [data-testid="element-container"],
div[class*="st-key-ask_aruvi_popup"] [data-testid="stVerticalBlockBorderWrapper"] {
    margin: 0 !important;
    padding: 0 !important;
}
/* Header bar */
.aa-header {
    padding: 14px 16px 10px 16px;
    border-bottom: 1px solid #F0EDE9;
}
.aa-header-title {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #2C7A7B;
    margin: 0;
}
.aa-header-sub {
    font-size: 0.7rem;
    color: #9C9693;
    margin-top: 2px;
}
/* Category cards */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] {
    margin: 0 !important;
    padding: 0 8px !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] button,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] [data-testid="stBaseButton-secondary"],
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] [data-testid="stBaseButton-primary"] {
    background: #FAFAF8 !important;
    border: none !important;
    border-bottom: 1px solid #F0EDE9 !important;
    border-radius: 0 !important;
    color: #2C2A27 !important;
    font-size: 0.75rem !important;
    font-weight: 400 !important;
    padding: 11px 12px !important;
    width: 100% !important;
    min-height: 40px !important;
    height: auto !important;
    text-align: left !important;
    justify-content: space-between !important;
    letter-spacing: 0 !important;
    line-height: 1.3 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] button *,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] [data-testid] * {
    font-size: 0.75rem !important;
    color: #2C2A27 !important;
    line-height: 1.3 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] button:hover,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-chip_"] button:hover * {
    background: #F0F7F7 !important;
    color: #1B2A3B !important;
}
div[class*="st-key-ask_aruvi_popup"] [data-testid="stBaseButton-primary"],
div[class*="st-key-ask_aruvi_popup"] [data-testid="stBaseButton-primary"] * {
    background: #EAF4F4 !important;
    color: #2C7A7B !important;
    font-weight: 600 !important;
    border: none !important;
    border-bottom: 1px solid #C8E8E8 !important;
}
/* Query box area */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] {
    padding: 0 12px 0 12px !important;
    margin: 0 !important;
    overflow: visible !important;
}
/* BaseWeb textarea wrapper has overflow:hidden by default — must override or bottom border clips */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] [data-baseweb="textarea"],
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] > div {
    overflow: visible !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] textarea {
    height: 80px !important;
    min-height: 80px !important;
    font-size: 0.75rem !important;
    border-radius: 10px !important;
    border: 1px solid #E0DDD8 !important;
    resize: none !important;
    line-height: 1.5 !important;
    padding: 10px 36px 10px 12px !important;
    background: #FAFAF8 !important;
    color: #2C2A27 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] textarea::placeholder {
    color: #C0BCB8 !important;
    opacity: 1 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] textarea:focus {
    border-color: #2C7A7B !important;
    outline: none !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] p,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_query_input"] small {
    font-size: 0.58rem !important;
    color: #B8B4B0 !important;
}
/* Send button — CRITICAL: width:100% prevents fit-content from breaking right: anchor */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_submit"] {
    position: relative !important;
    height: 0 !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_submit"] > div,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_submit"] > div > div {
    height: 0 !important;
    width: 100% !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_submit"] button {
    position: absolute !important;
    top: 4px !important;
    right: 14px !important;
    width: 26px !important;
    height: 26px !important;
    min-height: 26px !important;
    min-width: 26px !important;
    max-width: 26px !important;
    border-radius: 50% !important;
    background: #E8682A !important;
    border: none !important;
    color: #FFFFFF !important;
    font-size: 0.85rem !important;
    padding: 0 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 20 !important;
    pointer-events: all !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_submit"] button:hover {
    background: #C95820 !important;
}
/* Response box */
.aa-response-wrap {
    padding: 0 12px 8px 12px;
}
.aruvi-response-box {
    background: #F5F9F9;
    border-left: 3px solid #2C7A7B;
    padding: 10px 13px;
    font-size: 0.75rem;
    color: #2C2A27;
    margin-top: 6px;
    border-radius: 0 8px 8px 0;
    line-height: 1.6;
}
/* Clear button */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_clear"] button {
    background: transparent !important;
    border: none !important;
    color: #B8B4B0 !important;
    font-size: 0.62rem !important;
    padding: 2px 0 0 0 !important;
    min-height: unset !important;
    text-decoration: underline !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_clear"] button:hover {
    color: #5A5754 !important;
}
/* Divider — hidden to reduce gap */
.aa-divider {
    display: none !important;
    margin: 0 !important;
}
/* Feedback section label */
.aa-fb-label {
    padding: 4px 16px 0 16px;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #2C7A7B;
}
/* Feedback textarea */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] {
    padding: 0 12px 0 12px !important;
    margin: 0 !important;
    overflow: visible !important;
}
/* BaseWeb textarea wrapper has overflow:hidden by default — must override or bottom border clips */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] [data-baseweb="textarea"],
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] > div {
    overflow: visible !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] textarea {
    height: 80px !important;
    min-height: 80px !important;
    font-size: 0.75rem !important;
    border-radius: 10px !important;
    border: 1px solid #E0DDD8 !important;
    resize: none !important;
    line-height: 1.5 !important;
    padding: 10px 36px 10px 12px !important;
    background: #FAFAF8 !important;
    color: #2C2A27 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] textarea::placeholder {
    color: #C0BCB8 !important;
    opacity: 1 !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_text"] textarea:focus {
    border-color: #2C7A7B !important;
    outline: none !important;
}
/* Feedback send button — CRITICAL: width:100% prevents fit-content from breaking right: anchor */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_submit"] {
    position: relative !important;
    height: 0 !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_submit"] > div,
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_submit"] > div > div {
    height: 0 !important;
    width: 100% !important;
    overflow: visible !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_submit"] button {
    position: absolute !important;
    top: 4px !important;
    right: 14px !important;
    width: 26px !important;
    height: 26px !important;
    min-height: 26px !important;
    min-width: 26px !important;
    max-width: 26px !important;
    border-radius: 50% !important;
    background: #E8682A !important;
    border: none !important;
    color: #FFFFFF !important;
    font-size: 0.85rem !important;
    padding: 0 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 20 !important;
    pointer-events: all !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-ask_aruvi_fb_submit"] button:hover {
    background: #C95820 !important;
}
/* Thumbs buttons */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-thumb_"] button {
    background: transparent !important;
    border: 1px solid #E0DDD8 !important;
    border-radius: 50% !important;
    font-size: 0.75rem !important;
    width: 28px !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 !important;
    filter: grayscale(1) brightness(0.42) !important;
}
/* FAB */
div[class*="st-key-ask_aruvi_fab"] button {
    position: fixed !important;
    bottom: 28px !important;
    right: 28px !important;
    width: 48px !important;
    height: 48px !important;
    border-radius: 50% !important;
    background: #1B2A3B !important;
    color: #ffffff !important;
    font-size: 1.2rem !important;
    border: none !important;
    z-index: 99999 !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.20) !important;
    min-height: unset !important;
    padding: 0 !important;
}
div[class*="st-key-ask_aruvi_fab"] button:hover {
    background: #2C7A7B !important;
}
html { overflow-y: scroll !important; }
/* ── Detail view panel ── */
.aa-detail-panel {
    padding: 0;
}
.aa-detail-back {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 12px 16px 10px 16px;
    border-bottom: 1px solid #F0EDE9;
    cursor: pointer;
}
.aa-detail-back-arrow {
    font-size: 0.85rem;
    color: #2C7A7B;
}
.aa-detail-back-label {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #2C7A7B;
}
.aa-detail-cat-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: #1B2A3B;
    padding: 14px 16px 4px 16px;
}
.aa-detail-cat-desc {
    font-size: 0.68rem;
    color: #9C9693;
    padding: 0 16px 12px 16px;
    border-bottom: 1px solid #F0EDE9;
}
.aa-qa-pair {
    padding: 12px 16px;
    border-bottom: 1px solid #F5F3EF;
}
.aa-qa-q {
    font-size: 0.75rem;
    font-weight: 600;
    color: #1B2A3B;
    margin-bottom: 5px;
    line-height: 1.4;
}
.aa-qa-a {
    font-size: 0.72rem;
    color: #5A5754;
    line-height: 1.6;
}
/* Back button inside popup */
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-aa_back_btn"] button {
    background: transparent !important;
    border: none !important;
    color: #2C7A7B !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    padding: 12px 16px 10px 16px !important;
    min-height: unset !important;
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-bottom: 1px solid #F0EDE9 !important;
    border-radius: 0 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[class*="st-key-ask_aruvi_popup"] div[class*="st-key-aa_back_btn"] button:hover {
    background: #F5F9F9 !important;
    color: #1B2A3B !important;
}
/* Hide CMD+Enter hint — keep 0/140 counter (it's the last child) */
div[class*="st-key-ask_aruvi_popup"] [data-testid="InputInstructions"] > *:first-child {
    display: none !important;
}
/* Follow-up textarea font size */
div[class*="st-key-ask_aruvi_followup"] textarea {
    font-size: 0.65rem !important;
}
/* Follow-up Submit and Skip buttons */
div[class*="st-key-fu_submit"] button,
div[class*="st-key-fu_skip"] button {
    background-color: #4A4A4A !important;
    color: #FFFFFF !important;
    font-size: 0.62rem !important;
    border-radius: 6px !important;
    border: none !important;
}
/* Feedback confirmation div */
.aruvi-fb-confirm {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 12px;
    font-family: inherit;
    font-weight: 700;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    color: #2C7A7B;
    background: transparent;
}
.aruvi-fb-confirm-text {
    flex: 1;
}
/* Character counter padding — query input */
div[class*="st-key-ask_aruvi_query_input"] small,
div[class*="st-key-ask_aruvi_query_input"] p {
    padding-right: 10px !important;
    margin-right: 10px !important;
    width: calc(100% - 12px) !important;
}
/* Character counter padding — feedback textarea */
div[class*="st-key-ask_aruvi_fb_text"] small,
div[class*="st-key-ask_aruvi_fb_text"] p {
    padding-right: 10px !important;
    margin-right: 10px !important;
    width: calc(100% - 12px) !important;
}
</style>
""", unsafe_allow_html=True)

# FAB button — Streamlit button styled to look like FAB
_fab_label = "✕" if st.session_state.ask_aruvi_open else "💬"
_fab_col = st.container()
with _fab_col:
    if st.button(_fab_label, key="ask_aruvi_fab"):
        st.session_state.ask_aruvi_open = not st.session_state.ask_aruvi_open
        st.session_state.ask_aruvi_response = ""
        st.session_state.ask_aruvi_show_thumbs = False
        st.session_state.ask_aruvi_thumb_done = False
        st.session_state.ask_aruvi_show_followup = False
        st.rerun()

if st.session_state.ask_aruvi_open:
    with st.container(key="ask_aruvi_popup"):

        # ── Load Q&A knowledge base for detail view ───────────────────────────
        import json as _json
        _qa_kb_path = PROJECT_ROOT / "mirror/ask_aruvi/qa_knowledge_base.json"
        try:
            _qa_kb = _json.loads(_qa_kb_path.read_text(encoding="utf-8"))
        except Exception:
            _qa_kb = {"categories": {}}

        # ── DETAIL VIEW — show Q&A pairs for selected category ────────────────
        if st.session_state.ask_aruvi_detail_cat is not None:
            _dcat_key = st.session_state.ask_aruvi_detail_cat
            _dcat     = _qa_kb.get("categories", {}).get(_dcat_key, {})
            _dcat_label = CATEGORY_LABELS.get(_dcat_key, "")
            _dcat_desc  = _dcat.get("description", "")
            _dpairs     = _dcat.get("pairs", [])

            # Back button
            if st.button("‹  Back to Ask Aruvi", key="aa_back_btn",
                          use_container_width=True):
                st.session_state.ask_aruvi_detail_cat = None
                st.rerun()

            # Category title and description
            st.markdown(
                f'<div class="aa-detail-cat-title">{_dcat_label}</div>'
                f'<div class="aa-detail-cat-desc">{_dcat_desc}</div>',
                unsafe_allow_html=True,
            )

            # Q&A pairs
            for _pair in _dpairs:
                st.markdown(
                    f'<div class="aa-qa-pair">'
                    f'<div class="aa-qa-q">{_pair.get("q", "")}</div>'
                    f'<div class="aa-qa-a">{_pair.get("a", "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

        # ── RESPONSE VIEW — Q&A detail after submitting a question ───────────
        elif st.session_state.ask_aruvi_response:

            # Back button — resets to the state before the question was typed
            if st.button("‹  Back to Ask Aruvi", key="aa_back_btn",
                          use_container_width=True):
                st.session_state.ask_aruvi_response      = ""
                st.session_state.ask_aruvi_last_query    = ""
                st.session_state.ask_aruvi_show_thumbs   = False
                st.session_state.ask_aruvi_thumb_done    = False
                st.session_state.ask_aruvi_show_followup = False
                st.rerun()

            # Question + answer in the same Q&A pair format as category detail
            st.markdown(
                f'<div class="aa-qa-pair">'
                f'<div class="aa-qa-q">{st.session_state.ask_aruvi_last_query}</div>'
                f'<div class="aa-qa-a">{st.session_state.ask_aruvi_response}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Thumbs
            if st.session_state.ask_aruvi_show_thumbs and \
                    not st.session_state.ask_aruvi_thumb_done:
                _t1, _t2, _t3 = st.columns([1, 1, 8])
                with _t1:
                    if st.button("👍", key="thumb_up"):
                        write_thumbs_feedback(
                            session_id=st.session_state.ask_aruvi_session_id,
                            rating="up",
                            query=st.session_state.ask_aruvi_last_query,
                            response_excerpt=st.session_state.ask_aruvi_response[:200],
                            category_selected=st.session_state.ask_aruvi_category or "",
                        )
                        st.session_state.ask_aruvi_thumb_done = True
                        st.rerun()
                with _t2:
                    if st.button("👎", key="thumb_down"):
                        st.session_state.ask_aruvi_show_followup = True
                        st.rerun()

            if st.session_state.ask_aruvi_show_followup and \
                    not st.session_state.ask_aruvi_thumb_done:
                _fu_text = st.text_area(
                    "followup",
                    placeholder="Please provide feedback on what is missing?",
                    label_visibility="collapsed",
                    key="ask_aruvi_followup",
                    max_chars=140,
                    height=90,
                )
                _fu1, _fu2 = st.columns([1, 1])
                with _fu1:
                    if st.button("Submit", key="fu_submit"):
                        write_thumbs_feedback(
                            session_id=st.session_state.ask_aruvi_session_id,
                            rating="down",
                            query=st.session_state.ask_aruvi_last_query,
                            response_excerpt=st.session_state.ask_aruvi_response[:200],
                            category_selected=st.session_state.ask_aruvi_category or "",
                            follow_up_text=_fu_text or None,
                        )
                        st.session_state.ask_aruvi_thumb_done = True
                        st.rerun()
                with _fu2:
                    if st.button("Skip", key="fu_skip"):
                        write_thumbs_feedback(
                            session_id=st.session_state.ask_aruvi_session_id,
                            rating="down",
                            query=st.session_state.ask_aruvi_last_query,
                            response_excerpt=st.session_state.ask_aruvi_response[:200],
                            category_selected=st.session_state.ask_aruvi_category or "",
                        )
                        st.session_state.ask_aruvi_thumb_done = True
                        st.rerun()

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

        # ── MAIN VIEW ─────────────────────────────────────────────────────────
        else:

            # Header
            st.markdown(
                '<div class="aa-header">'
                '<div class="aa-header-title">Ask Aruvi</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Category cards — click opens detail view
            for _i, (_key, _label) in enumerate(CATEGORY_LABELS.items(), start=1):
                _active = st.session_state.ask_aruvi_category == _key
                _chip_text = f"{_i}. {_label}  ›"
                if st.button(
                    ("✓  " if _active else "") + _chip_text,
                    key=f"chip_{_key}",
                    type="primary" if _active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.ask_aruvi_detail_cat = _key
                    st.rerun()

            # ── Entry-point button — always visible, opens secondary panel ────
            # Border-top styling applied via CSS on ask_aruvi_open_agent_panel.
            if st.button(
                "💬  Ask a specific question or share feedback  ›",
                key="ask_aruvi_open_agent_panel",
                use_container_width=True,
            ):
                st.session_state.ask_aruvi_agent_open = True
                st.session_state.ask_aruvi_open = False   # hide category popup
                st.rerun()

# ── Ask Aruvi — secondary panel (Q&A + Feedback) ────────────────────────────
# Opens when the teacher clicks "Ask a specific question or share feedback".
# Uses aruvi_ask (Haiku when USE_MANAGED_AGENT=False, managed agent when True).
# Sits pixel-perfect on top of the category popup via matching CSS geometry.
if st.session_state.ask_aruvi_agent_open:
    with st.container(key="ask_aruvi_agent_popup"):

        # ── RESPONSE VIEW ─────────────────────────────────────────────────────
        if st.session_state.ask_aruvi_agent_response:

            if st.button("‹  Back", key="aa_agent_back_btn",
                          use_container_width=True):
                st.session_state.ask_aruvi_agent_response      = ""
                st.session_state.ask_aruvi_agent_last_query    = ""
                st.session_state.ask_aruvi_agent_show_thumbs   = False
                st.session_state.ask_aruvi_agent_thumb_done    = False
                st.session_state.ask_aruvi_agent_show_followup = False
                st.rerun()

            st.markdown(
                f'<div class="aa-qa-pair">'
                f'<div class="aa-qa-q">{st.session_state.ask_aruvi_agent_last_query}</div>'
                f'<div class="aa-qa-a">{st.session_state.ask_aruvi_agent_response}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Thumbs feedback
            if st.session_state.ask_aruvi_agent_show_thumbs and \
                    not st.session_state.ask_aruvi_agent_thumb_done:
                _at1, _at2, _at3 = st.columns([1, 1, 8])
                with _at1:
                    if st.button("👍", key="agent_thumb_up"):
                        write_thumbs_feedback(
                            session_id        = st.session_state.ask_aruvi_session_id,
                            rating            = "up",
                            query             = st.session_state.ask_aruvi_agent_last_query,
                            response_excerpt  = st.session_state.ask_aruvi_agent_response[:200],
                            category_selected = "managed_agent",
                        )
                        st.session_state.ask_aruvi_agent_thumb_done = True
                        st.rerun()
                with _at2:
                    if st.button("👎", key="agent_thumb_down"):
                        st.session_state.ask_aruvi_agent_show_followup = True
                        st.rerun()

            if st.session_state.ask_aruvi_agent_show_followup and \
                    not st.session_state.ask_aruvi_agent_thumb_done:
                _afu_text = st.text_area(
                    "agent_followup",
                    placeholder="Please provide feedback on what is missing?",
                    label_visibility="collapsed",
                    key="ask_aruvi_agent_followup",
                    max_chars=140,
                    height=90,
                )
                _afu1, _afu2 = st.columns([1, 1])
                with _afu1:
                    if st.button("Submit", key="agent_fu_submit"):
                        write_thumbs_feedback(
                            session_id        = st.session_state.ask_aruvi_session_id,
                            rating            = "down",
                            query             = st.session_state.ask_aruvi_agent_last_query,
                            response_excerpt  = st.session_state.ask_aruvi_agent_response[:200],
                            category_selected = "managed_agent",
                            follow_up_text    = _afu_text or None,
                        )
                        st.session_state.ask_aruvi_agent_thumb_done = True
                        st.rerun()
                with _afu2:
                    if st.button("Skip", key="agent_fu_skip"):
                        write_thumbs_feedback(
                            session_id        = st.session_state.ask_aruvi_session_id,
                            rating            = "down",
                            query             = st.session_state.ask_aruvi_agent_last_query,
                            response_excerpt  = st.session_state.ask_aruvi_agent_response[:200],
                            category_selected = "managed_agent",
                        )
                        st.session_state.ask_aruvi_agent_thumb_done = True
                        st.rerun()

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

        # ── MAIN VIEW — ask + feedback ────────────────────────────────────────
        else:
            # Back button — mirrors the category detail back button in style
            if st.button("‹  Back to Ask Aruvi", key="ask_aruvi_agent_close",
                          use_container_width=True):
                st.session_state.ask_aruvi_agent_open = False
                st.session_state.ask_aruvi_open = True    # restore category popup
                st.session_state.ask_aruvi_agent_fb_sent = False  # clear confirmation
                st.rerun()

            # Q&A box
            st.markdown('<div class="aa-fb-label">Ask a question</div>',
                        unsafe_allow_html=True)
            _agent_query = st.text_area(
                "agent_query",
                placeholder="Type your question on the platform.",
                label_visibility="collapsed",
                key="ask_aruvi_agent_query_input",
                height=104,
                max_chars=140,
            )
            _agent_ask_clicked = st.button("↑", key="ask_aruvi_agent_submit",
                                            use_container_width=False)

            if _agent_ask_clicked and _agent_query.strip():
                with st.spinner(""):
                    _agent_result = aruvi_ask(
                        query      = _agent_query.strip(),
                        session_id = st.session_state.ask_aruvi_session_id,
                        tab        = st.session_state.role,
                        subject    = st.session_state.get("subject", ""),
                        grade      = st.session_state.get("grade", ""),
                    )
                st.session_state.ask_aruvi_agent_response      = _agent_result["response"]
                st.session_state.ask_aruvi_agent_last_query    = _agent_query.strip()
                st.session_state.ask_aruvi_agent_show_thumbs   = True
                st.session_state.ask_aruvi_agent_thumb_done    = False
                st.session_state.ask_aruvi_agent_show_followup = False
                log_ask_aruvi_tokens(
                    session_id    = st.session_state.ask_aruvi_session_id,
                    query         = _agent_query.strip(),
                    category      = "managed_agent",
                    tab           = st.session_state.role,
                    subject       = st.session_state.get("subject", ""),
                    grade         = st.session_state.get("grade", ""),
                    input_tokens  = _agent_result.get("input_tokens", 0),
                    output_tokens = _agent_result.get("output_tokens", 0),
                )
                st.rerun()

            # Feedback box
            st.markdown('<hr class="aa-divider">', unsafe_allow_html=True)
            st.markdown('<div class="aa-fb-label">Share feedback on Aruvi</div>',
                        unsafe_allow_html=True)
            _agent_fb_text = st.text_area(
                "agent_feedback",
                placeholder="Tell us anything about your experience.",
                label_visibility="collapsed",
                key=f"ask_aruvi_agent_fb_text_{st.session_state.ask_aruvi_agent_fb_reset}",
                height=104,
                max_chars=140,
            )
            if st.button("↑", key="ask_aruvi_agent_fb_submit"):
                if _agent_fb_text.strip():
                    write_general_feedback(
                        session_id    = st.session_state.ask_aruvi_session_id,
                        feedback_text = _agent_fb_text.strip(),
                        tab           = st.session_state.role,
                        subject       = st.session_state.get("subject", ""),
                        grade         = st.session_state.get("grade", ""),
                    )
                    st.session_state.ask_aruvi_agent_fb_sent  = True
                    st.session_state.ask_aruvi_agent_fb_reset += 1
                    st.rerun()
            if st.session_state.ask_aruvi_agent_fb_sent:
                st.markdown(
                    '<div class="aruvi-fb-confirm">'
                    '<span class="aruvi-fb-confirm-text">Thank you for your feedback.</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
