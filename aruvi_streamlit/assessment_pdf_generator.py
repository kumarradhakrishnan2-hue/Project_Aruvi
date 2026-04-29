"""
Aruvi Chapter Assessment PDF — v2

Imports all reusable constants, styles, and helpers from lp_pdf_generator.
Adds only assessment-specific styles; never redefines what is already there.

Science support added (v2.1):
  - _group_science()         groups items by stage_label
  - build_assessment_pdf()   branches on is_science for section headers / LO source
  - question_block()         normalises OPEN_TASK → open_task; handles visual_stimulus
  - json_to_assessment_data() skips period-based lo_map for Science
"""
import io
import os
import re
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from pypdf import PdfReader, PdfWriter

# ── Import everything reusable from lp_pdf_generator ─────────────────────────
from lp_pdf_generator import (
    PAGE_W, PAGE_H, L_MAR, R_MAR, T_MAR, B_MAR,
    INK, MID, MUTE, HAIRLINE, BG_META, BG_ROW, BLUE_TAG, BLUE_BG, ROW_LINE,
    LOGO_PATH,
    ST,
    _clean_text,
    on_page,
    HLine,
    LOBox,
)

# ── Assessment-only palette ───────────────────────────────────────────────────
DARK_GREY = colors.HexColor("#444444")   # Fix 8: section headers


# ── Assessment-only styles ────────────────────────────────────────────────────
def _make_ast():
    s = {}

    def st(name, **kw):
        s[name] = ParagraphStyle(name, **kw)

    # Fix 7: LO / cognitive demand rows — dark grey, left-aligned
    st("q_meta",     fontName="Helvetica",         fontSize=6.5, leading=10, textColor=DARK_GREY)
    # Question text — readable, same size as LP body
    st("q_text",     fontName="Helvetica",         fontSize=8.5, leading=13, textColor=INK)
    # Fix 9: MCQ option label — INK (not BLUE_TAG), full-stop format
    st("q_opt_lbl",  fontName="Helvetica-Bold",    fontSize=7.5, leading=11, textColor=INK)
    st("q_opt_txt",  fontName="Helvetica",         fontSize=7.5, leading=11, textColor=INK)
    # Open task field labels and bodies
    st("ot_lbl",     fontName="Helvetica-Bold",    fontSize=7.5, leading=11, textColor=INK)
    st("ot_txt",     fontName="Helvetica",         fontSize=7.5, leading=11, textColor=INK,
       leftIndent=8)
    # Fix 6: single combined italic note — 8pt
    st("combo_note", fontName="Helvetica-Oblique", fontSize=8.0, leading=12, textColor=MID)
    # Fix 8: section header — dark grey (#444444), 7.5pt, bold, centred
    st("sec_hdr",    fontName="Helvetica-Bold",    fontSize=7.5, leading=11, textColor=DARK_GREY,
       alignment=TA_CENTER)
    return s


AST = _make_ast()

# Fixed display order and display names for question-type groups
TYPE_ORDER = ["MCQ", "SCR", "ECR", "open_task"]
TYPE_NAMES = {
    "MCQ":       "Multiple Choice Questions",
    "SCR":       "Short Answer Questions",
    "ECR":       "Extended Response Questions",
    "open_task": "Open Task",
}


# ──────────────────────────────────────────────────────────────────────────────
# Assessment meta strip
# ──────────────────────────────────────────────────────────────────────────────
def assessment_meta_strip(chapter_num, title, total_questions, date_str):
    """
    Two-row table — labels above, values below.
    Fix 5: 5 columns — Chapter | Title | Total questions | Type | Date
    (Total periods column removed)
    """
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * f for f in [0.09, 0.40, 0.17, 0.15, 0.19]]
    lbl_row = [Paragraph(x, ST["meta_lbl"]) for x in
               ["Chapter", "Title", "Total questions", "Type", "Date"]]
    val_row = [
        Paragraph(f"Ch {chapter_num:02d}",    ST["meta_val"]),
        Paragraph(_clean_text(title),          ST["meta_val"]),
        Paragraph(str(total_questions),        ST["meta_val"]),
        Paragraph("Formative",                 ST["meta_val"]),
        Paragraph(_clean_text(date_str),       ST["meta_val"]),
    ]
    t = Table([lbl_row, val_row], colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1,  0), 4),
        ("BOTTOMPADDING", (0, 0), (-1,  0), 2),
        ("TOPPADDING",    (0, 1), (-1,  1), 2),
        ("BOTTOMPADDING", (0, 1), (-1,  1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────────
# Science grouping helper
# ──────────────────────────────────────────────────────────────────────────────
def _group_science(items):
    """
    Groups Science assessment items by stage_label, preserving insertion order
    (dict is ordered in Python 3.7+).

    Returns a list of 3-tuples:
        (stage_label: str, progression_stage: int, items: list[dict])

    Each tuple becomes one rendered section in the PDF, with section header:
        "Stage {progression_stage} · {stage_label}"

    Missing / null stage_label values are handled gracefully (grouped under "").
    """
    groups     = {}   # stage_label → [item, ...]
    stage_meta = {}   # stage_label → progression_stage
    for item in items:
        label = item.get("stage_label") or ""
        stage = item.get("progression_stage") or 0
        if label not in groups:
            groups[label]     = []
            stage_meta[label] = stage
        groups[label].append(item)
    return [(label, stage_meta[label], grp) for label, grp in groups.items()]


# ──────────────────────────────────────────────────────────────────────────────
# Visual stimulus renderer
# ──────────────────────────────────────────────────────────────────────────────
def _render_visual_stimulus(vs_text: str, uw: float, story: list):
    """
    Renders a visual_stimulus string into story flowables.

    Permitted formats per assessment constitutions:
    - Pipe-delimited table (>=2 lines, every line contains "|") — rendered as
      a ReportLab Table. Used by Science, Social Sciences, and Mathematics
      whenever the question genuinely needs tabular data.
    - Plain prose — rendered as italic body text. Used by Social Sciences
      where a brief textual stimulus precedes a question.

    Mathematics no longer permits inline SVG (Constitution v3.2 Rule 7);
    figures are referenced via the Exercise companion block instead.
    """
    vs = vs_text.strip()
    lines = [ln.strip() for ln in vs.splitlines() if ln.strip()]

    # Detect pipe-table: at least 2 lines, every line contains "|"
    is_table = len(lines) >= 2 and all("|" in ln for ln in lines)

    story.append(Spacer(1, 3))

    if is_table:
        # Parse rows: split on "|", strip each cell
        rows = []
        for ln in lines:
            cells = [c.strip() for c in ln.split("|")]
            # Remove leading/trailing empty cells caused by leading/trailing |
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            rows.append(cells)

        # Normalise column count
        max_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        # Build cell paragraphs: first row bold (header), rest normal
        para_rows = []
        for ri, row in enumerate(rows):
            style = ParagraphStyle(
                "vs_hdr" if ri == 0 else "vs_cell",
                fontName="Helvetica-Bold" if ri == 0 else "Helvetica",
                fontSize=7.5, leading=11, textColor=INK,
            )
            para_rows.append([Paragraph(_clean_text(c), style) for c in row])

        col_w = uw / max_cols
        tbl = Table(para_rows, colWidths=[col_w] * max_cols)
        tbl_style = [
            ("BACKGROUND",    (0, 0), (-1,  0), BG_META),   # header row
            ("BACKGROUND",    (0, 1), (-1, -1), colors.HexColor("#f9f9f9")),
            ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, HAIRLINE),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]
        tbl.setStyle(TableStyle(tbl_style))

        # Render label and table as separate flowables — no outer wrapper table
        # that would overlay a background fill on top of the inner table cells.
        lbl_para = Paragraph("<b>Visual stimulus</b>", AST["q_meta"])
        lbl_box = Table([[lbl_para]], colWidths=[uw])
        lbl_box.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
            ("LINEBEFORE",    (0, 0), ( 0, -1), 0.5, HAIRLINE),
            ("LINEAFTER",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ]))
        # Outer border bottom line drawn via a thin spacer-table so the box
        # appears closed underneath the data table.
        tbl_wrapper = Table([[tbl]], colWidths=[uw])
        tbl_wrapper.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBEFORE",    (0, 0), ( 0, -1), 0.5, HAIRLINE),
            ("LINEAFTER",     (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("LINEBELOW",     (0, -1), (-1, -1), 0.5, HAIRLINE),
        ]))
        story.append(lbl_box)
        story.append(tbl_wrapper)

    else:
        # Plain text / description — render in a light-grey box
        lbl_para  = Paragraph("<b>Visual stimulus</b>", AST["q_meta"])
        body_para = Paragraph(
            _clean_text(vs),
            ParagraphStyle("vs_plain", fontName="Helvetica-Oblique",
                           fontSize=7.5, leading=11, textColor=MID),
        )
        box = Table([[lbl_para], [body_para]], colWidths=[uw])
        box.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
            ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(box)

    story.append(Spacer(1, 3))


# ──────────────────────────────────────────────────────────────────────────────
# Math response-box helpers (SCR / NUM / ECR student-writing area)
# ──────────────────────────────────────────────────────────────────────────────
def _render_math_response_box(uw: float, story: list, lines: int):
    """
    Bordered ruled response area that a student writes their answer into.
    `lines` controls the height (each ruled line ~ 5.5 mm tall).
    """
    line_h = 5.5 * mm
    rows   = [[Paragraph("&nbsp;", AST["q_text"])] for _ in range(lines)]
    box    = Table(rows, colWidths=[uw], rowHeights=[line_h] * lines)
    box.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.4, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.25, ROW_LINE),  # ruled lines
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 3))
    story.append(box)


def _render_math_num_box(uw: float, story: list, working_lines: int):
    """
    Two-part response area for NUM items:
      "Answer: __________"   (single bordered line)
      [Working box]          (taller bordered area with ruled lines)
    """
    # Answer line
    ans_h    = 6.5 * mm
    ans_para = Paragraph("<b>Answer:</b>", AST["q_text"])
    ans_tbl  = Table(
        [[ans_para, Paragraph("&nbsp;", AST["q_text"])]],
        colWidths=[uw * 0.12, uw * 0.88],
        rowHeights=[ans_h],
    )
    ans_tbl.setStyle(TableStyle([
        ("LINEBELOW",     (1, 0), (1, 0), 0.4, HAIRLINE),  # underline answer slot
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
    ]))

    # Working box: label row + ruled body
    line_h    = 5.5 * mm
    body_rows = [[Paragraph("&nbsp;", AST["q_text"])] for _ in range(working_lines)]
    body_tbl  = Table(body_rows, colWidths=[uw], rowHeights=[line_h] * working_lines)
    body_tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.4, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.25, ROW_LINE),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    working_lbl = Paragraph("<b>Working</b>", AST["q_meta"])

    story.append(Spacer(1, 3))
    story.append(ans_tbl)
    story.append(Spacer(1, 4))
    story.append(working_lbl)
    story.append(body_tbl)


# ──────────────────────────────────────────────────────────────────────────────
# Question block — returns a list of flowables for one assessment item
# ──────────────────────────────────────────────────────────────────────────────
def question_block(q_num, item, lo_text, uw, header_items=None):
    """
    Fix 3: KeepTogether wraps only meta_block + q_para (not entire question).
    Fix 4: header_items (section header flowables) embedded in KeepTogether
           for the first question of each section to prevent orphaning.
    Fix 7: LO + cog demand as 2-row single-col table with BG_META background.
    Fix 9: Q number plain INK; option labels 'A.', 'B.', etc. in INK, tighter cols.
    Fix 1: No 'Look for' blocks for SCR or ECR.
    Fix 2: open_task backward-compatible ('task' key first, then 'task_instructions').

    Science v2.1 additions (no-op for SS):
    - OPEN_TASK (uppercase) normalised to open_task before branching so the
      same rendering path handles both subjects.
    - visual_stimulus: if present and non-empty, a note is printed after the
      question stem. SS items never carry this field so the check is always
      a no-op for SS.
    """
    story = []
    qtype    = item.get("question_type", "")
    is_maths = item.get("_maths_section_code") is not None  # True for maths items

    # Science uses OPEN_TASK (uppercase); normalise to open_task so the shared
    # rendering path below handles both subjects identically.
    if qtype == "OPEN_TASK":
        qtype = "open_task"

    # ── Meta block: differs for Maths vs Science/SS ──────────────────────────────────────
    if is_maths:
        # Mathematics: Section \u00b7 Question Type \u00b7 Goal (no LO / Cognitive demand \u2014
        # math uses goal recall/reason/apply instead of Bloom's cognitive_demand).
        sec_ref   = _clean_text(item.get("section_ref", "") or "")
        qt_disp   = _clean_text((qtype or "").upper())
        goal_raw  = _clean_text(item.get("goal", "") or "")
        goal_disp = goal_raw.capitalize() if goal_raw else ""

        meta_parts = []
        if sec_ref:
            meta_parts.append(f"<b>Section:</b> {sec_ref}")
        if qt_disp:
            meta_parts.append(f"<b>Type:</b> {qt_disp}")
        if goal_disp:
            meta_parts.append(f"<b>Goal:</b> {goal_disp}")
        meta_line = " &nbsp;\u00b7&nbsp; ".join(meta_parts) if meta_parts else "<b>Section:</b> \u2014"

        meta_rows = [
            [Paragraph(meta_line, AST["q_meta"])],
        ]
    else:
        # Science / Social Sciences: LO assessed + Cognitive demand
        lo_disp  = f"<b>LO assessed:</b> {_clean_text(lo_text)}" if lo_text else "<b>LO assessed:</b> \u2014"
        cog_disp = f"<b>Cognitive demand:</b> {_clean_text(item.get('cognitive_demand', ''))}"
        meta_rows = [
            [Paragraph(lo_disp,  AST["q_meta"])],
            [Paragraph(cog_disp, AST["q_meta"])],
        ]
    meta_block = Table(meta_rows, colWidths=[uw])
    meta_block.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    # ── Question number + text ────────────────────────────────────────────────
    # open_task items may have no question_text — show number only
    q_raw  = item.get("question_text") or ""
    q_text = _clean_text(q_raw)
    if q_text:
        q_para = Paragraph(f"<b>Q{q_num}.</b>  {q_text}", AST["q_text"])
    else:
        q_para = Paragraph(f"<b>Q{q_num}.</b>", AST["q_text"])

    # Section header flows freely — not constrained by KeepTogether
    if header_items:
        story.extend(header_items)
    # Single narrow KeepTogether: only meta_block + q_para prevents LO orphaning
    story.append(KeepTogether([meta_block, Spacer(1, 2), q_para]))

    # ── Visual stimulus — render after question stem ──────────────────────────
    vs = item.get("visual_stimulus")
    if vs and isinstance(vs, str) and vs.strip():
        _render_visual_stimulus(vs, uw, story)

    # ── MCQ options ───────────────────────────────────────────────────────────
    if qtype == "MCQ":
        # Fix 9: labels "A.", "B.", "C.", "D." with full stop; INK colour
        label_map = {"A": "A.", "B": "B.", "C": "C.", "D": "D."}
        opt_rows = []
        for opt in item.get("options", []):
            raw_lbl     = _clean_text(opt.get("label", "")).rstrip(".")
            display_lbl = label_map.get(raw_lbl, raw_lbl + ".")
            opt_rows.append([
                Paragraph(f"<b>{display_lbl}</b>",               AST["q_opt_lbl"]),
                Paragraph(_clean_text(opt.get("text", "")),       AST["q_opt_txt"]),
            ])
        if opt_rows:
            # Label col indented right (not flush with Q number); answer col full width
            opt_t = Table(opt_rows, colWidths=[uw * 0.07, uw * 0.93])
            opt_t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), ( 0, -1), 18),  # shift A/B/C/D right
                ("LEFTPADDING",   (1, 0), ( 1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(opt_t)

    # ── Math SCR / NUM / ECR: response boxes suppressed ──────────────────────
    # Previously rendered ruled writing areas for students. Suppressed now
    # because the PDF is teacher-facing only; guide is in the online HTML.
    # Science / SS are unaffected — they never entered these elif branches.

    # ── Open task — task / scaffold / format_of_output ────────────────────────
    elif qtype == "open_task":
        # Fix 2: check "task" first (new format), fall back to "task_instructions"
        task_txt = _clean_text(item.get("task") or item.get("task_instructions") or "")
        if task_txt:
            story.append(Spacer(1, 3))
            story.append(Paragraph("<b>Task</b>", AST["ot_lbl"]))
            story.append(Paragraph(task_txt, AST["ot_txt"]))
            story.append(Spacer(1, 3))

        scaffold = item.get("scaffold", "")
        if isinstance(scaffold, dict):
            scaf_txt = _clean_text(scaffold.get("description", ""))
        else:
            scaf_txt = _clean_text(str(scaffold)) if scaffold else ""
        if scaf_txt:
            story.append(Paragraph("<b>Scaffold</b>", AST["ot_lbl"]))
            story.append(Paragraph(scaf_txt, AST["ot_txt"]))
            story.append(Spacer(1, 3))

        # Fix 2: format_of_output may be a list (new) or dict with format_type (old)
        fmt = item.get("format_of_output") or item.get("open_task_format")
        if fmt:
            story.append(Paragraph("<b>Format of output</b>", AST["ot_lbl"]))
            if isinstance(fmt, list):
                for idx, line in enumerate(fmt, 1):
                    story.append(Paragraph(f"{idx}. {_clean_text(str(line))}", AST["ot_txt"]))
            elif isinstance(fmt, dict):
                fmt_type = _clean_text(fmt.get("format_type", ""))
                if fmt_type:
                    story.append(Paragraph(f"1. {fmt_type}", AST["ot_txt"]))

    # ── Mathematics: Guide block suppressed in PDF ───────────────────────────
    # Guide (expected_answer, method, what_each_option_reveals, inclusivity)
    # is available in the online HTML only. The PDF shows only question prompt
    # and the Exercise companion card below.
    if is_maths:
        # ── Exercise companion card (Constitution v3.2 Rule 9) ─────────────
        # Pointer to the textbook item that anchors this goal (exercise,
        # worked example, or activity per the LP's gamut walk). Skipped
        # silently when both fields are empty — no "[Fallback]" text.
        ex = item.get("exercise") or {}
        ex_book_ref    = _clean_text(ex.get("book_ref", "") or "")
        ex_description = _clean_text(ex.get("description", "") or "")
        if ex_book_ref:
            ex_label_para = Paragraph(
                f"<b>Exercise — {ex_book_ref}</b>",
                AST["q_meta"],
            )
            ex_rows = [[ex_label_para]]
            if ex_description:
                ex_rows.append([Paragraph(ex_description, AST["ot_txt"])])
            ex_tbl = Table(ex_rows, colWidths=[uw])
            ex_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fff8ec")),
                ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(Spacer(1, 3))
            story.append(ex_tbl)

    # ── Separator ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4))
    story.append(HLine(uw, thickness=0.3, color=ROW_LINE, sb=2, sa=2))

    return story


# ──────────────────────────────────────────────────────────────────────────────
# Main build
# ──────────────────────────────────────────────────────────────────────────────
def build_assessment_pdf(output_path, data):
    doc_meta = {
        "doc_type":    "Chapter Assessment",
        "doc_sub":     f"Grade {data['grade']} \u00b7 {data['subject']} \u00b7 {data['date']}",
        "footer_left": (f"Aruvi \u00b7 Assessment \u00b7 Grade {data['grade']} "
                        f"\u00b7 {data['subject']} \u00b7 Ch {data['chapter_num']:02d}"),
        "footer_right": "",   # blank on pass 1; page numbers stamped in pass 2
    }
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=L_MAR, rightMargin=R_MAR,
        topMargin=T_MAR + 14 * mm,
        bottomMargin=B_MAR + 8 * mm,
    )
    uw = PAGE_W - L_MAR - R_MAR
    story = []

    # ── Meta strip (Fix 5: no total_periods argument) ─────────────────────────
    story.append(assessment_meta_strip(
        data["chapter_num"], data["chapter_title"],
        data["total_questions"],
        data["date"],
    ))
    story.append(Spacer(1, 3 * mm))

    _is_maths_note = data.get("is_maths", False)
    if _is_maths_note:
        _note_text = (
            "Marks are not prescribed — assign per question based on formative assessment "
            "weightage and cognitive demand.<br/>"
            "Teacher guidance (expected answer, method, distractors, inclusivity) is available "
            "in the online view under My Plans &gt; Chapter Assessment."
        )
    else:
        _note_text = (
            "Marks are not prescribed — assign per question based on formative assessment "
            "weightage and cognitive demand.<br/>"
            "Teacher guidance for each question, including what incorrect responses reveal and "
            "inclusivity scaffolds, is available in the Aruvi platform under "
            "My Plans &gt; Chapter Assessment."
        )
    story.append(Paragraph(_note_text, AST["combo_note"]))
    story.append(Spacer(1, 5 * mm))

    items      = data["assessment_items"]
    lo_map     = data["lo_map"]
    is_science = data.get("is_science", False)
    is_maths   = data.get("is_maths",   False)
    q_counter  = 0

    if is_maths:
        # ── Mathematics: sections grouped by section_code (A/B/C) ──────────────
        # Items have already been flattened with _maths_section_code carried
        # per item by json_to_assessment_data().  Section header text is
        # "SECTION X — TITLE" (e.g., "SECTION A — RECALL AND APPLY").
        # The "LO" slot on each question carries the item's book_ref (or
        # blank for composed items) — Maths does not have per-LO routing.
        from collections import OrderedDict
        groups = OrderedDict()
        for it in items:
            code = it.get("_maths_section_code", "")
            if code not in groups:
                groups[code] = {
                    "title": it.get("_maths_section_title", ""),
                    "items": [],
                }
            groups[code]["items"].append(it)

        for code in ("A", "B", "C"):
            if code not in groups:
                continue
            grp_title = groups[code]["title"] or ""
            sec_text  = (f"Section {code} — {grp_title}".upper()
                         if grp_title else f"Section {code}".upper())
            sec_para  = Paragraph(sec_text, AST["sec_hdr"])
            sec_hline = HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3)

            for idx, item in enumerate(groups[code]["items"]):
                q_counter += 1
                # book_ref serves as the per-item provenance line. Composed
                # items carry blank book_ref — display dash in that case.
                _bref = item.get("book_ref", "")
                lo_text = (f"From textbook — {_bref}"
                           if (item.get("source") == "textbook" and _bref)
                           else "Composed item")

                header_items = [sec_para, sec_hline] if idx == 0 else None
                story.extend(question_block(
                    q_counter, item, lo_text, uw,
                    header_items=header_items,
                ))

            story.append(Spacer(1, 4 * mm))

    elif is_science:
        # ── Science: sections grouped by stage_label ───────────────────────────
        # Section header: "STAGE N · LABEL"
        # LO label:       item["implied_lo_assessed"]  (carried on each item)
        groups = _group_science(items)
        for stage_label, progression_stage, group_items in groups:
            sec_text  = f"Stage {progression_stage} \u00b7 {stage_label}"
            sec_para  = Paragraph(sec_text.upper(), AST["sec_hdr"])
            sec_hline = HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3)

            for idx, item in enumerate(group_items):
                q_counter += 1
                lo_text = item.get("implied_lo_assessed") or ""

                header_items = [sec_para, sec_hline] if idx == 0 else None
                story.extend(question_block(
                    q_counter, item, lo_text, uw,
                    header_items=header_items,
                ))

            story.append(Spacer(1, 4 * mm))

    else:
        # ── SS: sections grouped by question_type in fixed order ───────────────
        # This block is identical to the original code — do not modify.
        for qtype in TYPE_ORDER:
            # Normalise OPEN_TASK (uppercase) to open_task before matching
            group = [it for it in items
                     if (it.get("question_type") or "").replace("OPEN_TASK", "open_task") == qtype]
            if not group:
                continue

            # Fix 8: section header flowables — dark grey (#444444), 7.5pt, bold
            sec_para  = Paragraph(TYPE_NAMES[qtype].upper(), AST["sec_hdr"])
            sec_hline = HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3)

            for idx, item in enumerate(group):
                q_counter += 1

                # Resolve implied LO directly from the assessment item
                lo_text = item.get("implied_lo", "")

                # Fix 4: pass section header into first question of each group only
                if idx == 0:
                    header_items = [sec_para, sec_hline]
                else:
                    header_items = None

                story.extend(question_block(
                    q_counter, item, lo_text, uw,
                    header_items=header_items,
                ))

            story.append(Spacer(1, 4 * mm))

    # ── Pass 1: build PDF without page numbers ─────────────────────────────────
    doc.build(
        story,
        onFirstPage=lambda c, d: on_page(c, d, doc_meta),
        onLaterPages=lambda c, d: on_page(c, d, doc_meta),
    )

    # ── Pass 2: stamp "Page N of M" onto every page using pypdf ───────────────
    reader = PdfReader(output_path)
    total  = len(reader.pages)
    writer = PdfWriter()
    fy     = B_MAR - 4 * mm

    for i, page in enumerate(reader.pages):
        packet  = io.BytesIO()
        stamp_c = rl_canvas.Canvas(packet, pagesize=A4)
        stamp_c.setFont("Helvetica", 5.5)
        stamp_c.setFillColor(colors.HexColor("#bbbbbb"))
        stamp_c.drawRightString(
            PAGE_W - R_MAR, fy + 1.2 * mm,
            f"Page {i + 1} of {total}",
        )
        stamp_c.save()
        packet.seek(0)
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with open(output_path, "wb") as out_f:
        writer.write(out_f)

    print(f"✓  {output_path}  ({total} page{'s' if total != 1 else ''})")


# ──────────────────────────────────────────────────────────────────────────────
# Adapter: LPA JSON → data dict expected by build_assessment_pdf()
# ──────────────────────────────────────────────────────────────────────────────
def json_to_assessment_data(j: dict) -> dict:
    """
    Converts the Aruvi LPA output JSON dict into the data dict expected by
    build_assessment_pdf().  Mirrors the pattern of json_to_lp_data() in
    lp_pdf_generator.

    Science v2.1: skips period-based lo_map construction for Science payloads
    (Science items carry implied_lo_assessed directly on each item).
    """
    from datetime import datetime

    dt = datetime.fromisoformat(j["saved_at"])
    date_str = dt.strftime("%-d %B %Y")

    subject    = j.get("subject", "")
    is_science = (subject == "Science")
    is_maths   = (subject == "Mathematics")

    raw_items = (j.get("result") or {}).get("assessment_items", []) or []

    if is_maths:
        # Maths assessment ships as a list of section-objects (A/B/C), each
        # with its own nested items[]. Flatten while carrying the section
        # context per item; map maths field names to those question_block()
        # already understands (question_text, options[], etc.). Per
        # Assessment Constitution Rule 10, NEVER expose the internal
        # source_ref to the teacher — only book_ref is rendered.
        flat = []
        for sec in raw_items:
            if not isinstance(sec, dict):
                continue
            _code   = sec.get("section_code", "")
            _title  = sec.get("section_title", "")
            for it in (sec.get("items") or []):
                if not isinstance(it, dict):
                    continue
                _qtype  = it.get("question_type", "")
                _prompt = it.get("prompt", "")
                _flat = dict(it)  # carry through all body fields
                _flat["question_text"]            = _prompt
                _flat["question_type"]            = _qtype
                _flat["cognitive_demand"]         = ""   # Maths has none
                _flat["marking_guidance"]         = ""
                _flat["task"]                     = it.get("task", "")
                _flat["task_instructions"]        = ""
                _flat["_maths_section_code"]      = _code
                _flat["_maths_section_title"]     = _title
                # Visual stimulus (CB items) — carry as-is for renderer
                _flat["visual_stimulus"]          = it.get("visual_stimulus", None)
                flat.append(_flat)

        return {
            "chapter_num":      j["chapter_number"],
            "chapter_title":    j["chapter_title"],
            "grade":            str(j["grade"]).replace("Grade ", ""),
            "subject":          subject,
            "date":             date_str,
            "total_questions":  len(flat),
            "assessment_items": flat,
            "lo_map":           {},          # Maths has no per-LO routing
            "is_science":       False,
            "is_maths":         True,
        }

    if is_science:
        # Science items carry implied_lo_assessed directly — no period map needed.
        lo_map = {}
    else:
        # SS: Build LO lookup: period_number → implied_lo  (from LP periods in same JSON)
        lo_map = {
            p["period_number"]: p["implied_lo"]
            for p in j["result"]["lesson_plan"]["periods"]
        }

    return {
        "chapter_num":      j["chapter_number"],
        "chapter_title":    j["chapter_title"],
        "grade":            str(j["grade"]).replace("Grade ", ""),  # "Grade VII" → "VII"
        "subject":          subject,
        "date":             date_str,
        "total_questions":  len(raw_items),
        "assessment_items": raw_items,
        "lo_map":           lo_map,
        "is_science":       is_science,
        "is_maths":         False,
    }


def build_assessment_pdf_bytes(j: dict) -> bytes:
    """
    Streamlit adapter: takes the raw LPA JSON dict, returns PDF as bytes
    (for use with st.download_button).  Same pattern as build_lp_pdf_bytes().
    """
    data = json_to_assessment_data(j)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_path = f.name
    build_assessment_pdf(tmp_path, data)
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(tmp_path)
    return pdf_bytes
