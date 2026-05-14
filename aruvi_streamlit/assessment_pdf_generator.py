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
    KeepTogether, PageBreak,
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
    # English LO row — one notch larger than q_meta (7.5pt)
    st("q_lo",       fontName="Helvetica",         fontSize=7.5, leading=11, textColor=DARK_GREY)
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
    # Section header — dark grey (#444444), 8.5pt, bold, centred (fix 1: font +1 from 7.5)
    st("sec_hdr",    fontName="Helvetica-Bold",    fontSize=8.5, leading=12, textColor=DARK_GREY,
       alignment=TA_CENTER)
    return s


AST = _make_ast()


# ──────────────────────────────────────────────────────────────────────────────
# English teacher-guide helper: break run-together numbered/lettered answers
# onto separate lines (mirrors the HTML fmtGuide() function).
# Returns a list of Paragraph flowables.
# ──────────────────────────────────────────────────────────────────────────────
def _eng_guide_paras(text: str, uw: float) -> list:
    """
    Splits a teacher-guide string on embedded newlines OR run-together numbered /
    lettered items ("1. …  2. …" or "(a) … (b) …") OR Part A / Part B labels,
    and returns one Paragraph per logical line, formatted in the guide style.
    """
    if not text:
        return []
    guide_style = ParagraphStyle(
        "eng_guide", fontName="Helvetica", fontSize=7.5, leading=11,
        textColor=colors.HexColor("#085041"), leftIndent=8,
    )
    raw = _clean_text(text)
    if "\n" in raw:
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    else:
        # Insert split markers before Part A / Part B / Part C labels
        marked = re.sub(r'\s+(Part\s+[A-Z][\s\-:—])', r'\n\1', raw)
        # Insert split markers before run-together numbered items: " 1." " 2."
        marked = re.sub(r' (\d+)\.\s+', r'\n\1. ', marked)
        # Insert split markers before lettered items: " (a)" " (b)"
        marked = re.sub(r' \(([a-zA-Z])\)\s+', r'\n(\1) ', marked)
        lines = [ln.strip() for ln in marked.split("\n") if ln.strip()]
    return [Paragraph(_clean_text(ln), guide_style) for ln in lines]


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
      a ReportLab Table. Empty cells in data rows become blank answer-line
      placeholders ("___________") so both columns are visually balanced.
    - Plain prose — rendered as italic body text.

    The "Visual stimulus" label is intentionally suppressed (fix c) — the box
    speaks for itself and the label adds unnecessary clutter.

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

        # Normalise column count (fix e: pad short rows)
        max_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        # Build cell paragraphs: first row bold (header), rest normal.
        # Empty data cells become "___________" answer-line placeholders (fix e).
        para_rows = []
        for ri, row in enumerate(rows):
            is_header = ri == 0
            style = ParagraphStyle(
                "vs_hdr" if is_header else "vs_cell",
                fontName="Helvetica-Bold" if is_header else "Helvetica",
                fontSize=7.5, leading=11, textColor=INK,
            )
            blank_style = ParagraphStyle(
                "vs_blank",
                fontName="Helvetica-Oblique",
                fontSize=7.5, leading=11,
                textColor=colors.HexColor("#999999"),
            )
            para_row = []
            for ci, c in enumerate(row):
                if not is_header and c == "":
                    para_row.append(Paragraph("___________", blank_style))
                else:
                    para_row.append(Paragraph(_clean_text(c), style))
            para_rows.append(para_row)

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

        # Render table directly — no "Visual stimulus" label (fix c).
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
        story.append(tbl_wrapper)

    else:
        # Plain text / description — render in a light-grey box (no label, fix c)
        body_para = Paragraph(
            _clean_text(vs),
            ParagraphStyle("vs_plain", fontName="Helvetica-Oblique",
                           fontSize=7.5, leading=11, textColor=MID),
        )
        # Single-row box — no label (fix c)
        box = Table([[body_para]], colWidths=[uw])
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
# Word-box renderer (Listening MATCH tasks)
# ──────────────────────────────────────────────────────────────────────────────
def _render_word_box(words: list, uw: float, story: list):
    """
    Renders a styled word-box widget matching the HTML pill layout —
    used by Listening MATCH items.  Each word appears in its own bordered
    pill cell; all pills flow in a single wrapping row.
    words: list of word strings.
    """
    if not words:
        return
    lbl_style = ParagraphStyle(
        "wb_lbl", fontName="Helvetica-Bold",
        fontSize=7, leading=10, textColor=MID,
    )
    pill_style = ParagraphStyle(
        "wb_pill", fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=INK,
        alignment=TA_CENTER,
    )
    lbl_para = Paragraph("WORD BOX", lbl_style)

    # Build a row of pill cells — each word in its own bordered cell
    clean_words = [_clean_text(w) for w in words if w.strip()]
    if clean_words:
        pill_paras  = [Paragraph(w, pill_style) for w in clean_words]
        # Equal-width columns; shrink each pill to fit inside the box
        pill_w      = (uw - 14) / len(clean_words)   # 14 = 7px left+right pad of outer box
        pills_tbl   = Table([pill_paras], colWidths=[pill_w] * len(clean_words))
        pills_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f0ede8")),
            ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
    else:
        pills_tbl = None

    rows = [[lbl_para]]
    if pills_tbl:
        rows.append([pills_tbl])

    outer_box = Table(rows, colWidths=[uw])
    outer_box.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f7f6f4")),
        ("BOX",           (0, 0), (-1, -1), 0.8, HAIRLINE),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(outer_box)
    story.append(Spacer(1, 4))


# ──────────────────────────────────────────────────────────────────────────────
# FILL_IN markdown-table parser (English assessment Q5/6 fix)
# ──────────────────────────────────────────────────────────────────────────────
def _render_fill_in_stem(text: str, uw: float, story: list, q_num: int):
    """
    Parses a FILL_IN item_stem that may contain inline markdown tables
    (pipe-delimited, e.g.  | Word | Antonym |\\n|---|---|\\n| low | |).

    The stem is split into alternating segments:
      - text segments  → rendered as normal q_text paragraphs
      - table segments → rendered as proper PDF tables (via _render_visual_stimulus)

    The separator row "|---|---|" is stripped before rendering.
    Numbered question header (Q{n}.) is prepended to the first text segment.
    """
    # Split the stem into lines
    lines = text.split("\n")

    # We produce a list of segments: each is ("text", str) or ("table", [row_str, …])
    segments = []
    cur_text_lines = []
    cur_table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_pipe = "|" in stripped and stripped.startswith("|")
        is_sep  = bool(re.match(r"^\|[-|\s:]+\|", stripped))

        if is_pipe and not is_sep:
            # Pipe data row
            if not in_table:
                # flush accumulated text
                if cur_text_lines:
                    segments.append(("text", "\n".join(cur_text_lines)))
                    cur_text_lines = []
                in_table = True
            cur_table_lines.append(stripped)
        elif is_sep:
            # Separator row — skip but stay in table mode if we already are
            if not in_table:
                if cur_text_lines:
                    segments.append(("text", "\n".join(cur_text_lines)))
                    cur_text_lines = []
                in_table = True
        else:
            # Regular text line
            if in_table:
                # flush table
                if cur_table_lines:
                    segments.append(("table", cur_table_lines))
                    cur_table_lines = []
                in_table = False
            cur_text_lines.append(line)

    # flush remainder
    if in_table and cur_table_lines:
        segments.append(("table", cur_table_lines))
    elif cur_text_lines:
        segments.append(("text", "\n".join(cur_text_lines)))

    # Render segments
    first_text = True
    for seg_type, seg_data in segments:
        if seg_type == "text":
            seg_text = seg_data.strip()
            if not seg_text:
                continue
            if first_text:
                # Prepend Q number to first text segment
                display = f"<b>Q{q_num}.</b>  {_clean_text(seg_text)}"
                first_text = False
            else:
                display = _clean_text(seg_text)
            # Preserve embedded newlines as line breaks
            display = display.replace("\n", "<br/>")
            story.append(Paragraph(display, AST["q_text"]))
            story.append(Spacer(1, 3))
        else:
            # table segment — reuse _render_visual_stimulus with pipe format
            # Skip tables that have only a header row and no data rows
            # (e.g. Part B "| Near | Far |" with no actual entries)
            if len(seg_data) <= 1:
                continue  # header-only table — nothing meaningful to show
            pipe_text = "\n".join(seg_data)
            _render_visual_stimulus(pipe_text, uw, story)


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
    Renders one assessment question as a list of PDF flowables.

    English layout (revised):
      [Section name centred, per-question, via header_items]  (fix 1: every Q)
      [Q{n}. question text]     -- FILL_IN uses _render_fill_in_stem
      [Word box if MATCH]
      [Visual stimulus -- suppressed for FILL_IN]
      [MCQ options / open-task body]
      [Teacher Guide]
      [blank spacer]
      [Learning Outcome]            (fix 3: below teacher guide, 7.5pt font)

    Section-header font 8.5pt (fix 1: +1 from previous 7.5pt).
    LO font 7.5pt via q_lo style   (fix 3: +1 from q_meta 6.5pt).
    """
    story    = []
    qtype    = item.get("question_type", "")
    is_maths = item.get("_maths_section_code") is not None

    if qtype == "OPEN_TASK":
        qtype = "open_task"

    is_fill_in = (item.get("question_type", "") or "").upper() == "FILL_IN"

    # ── Meta block ────────────────────────────────────────────────────────────
    if is_maths:
        sec_ref   = _clean_text(item.get("section_ref", "") or "")
        qt_disp   = _clean_text((qtype or "").upper())
        goal_raw  = _clean_text(item.get("goal", "") or "")
        goal_disp = goal_raw.capitalize() if goal_raw else ""
        meta_parts = []
        if sec_ref:   meta_parts.append(f"<b>Section:</b> {sec_ref}")
        if qt_disp:   meta_parts.append(f"<b>Type:</b> {qt_disp}")
        if goal_disp: meta_parts.append(f"<b>Goal:</b> {goal_disp}")
        meta_line = " &nbsp;·&nbsp; ".join(meta_parts) if meta_parts else "<b>Section:</b> —"
        meta_rows = [[Paragraph(meta_line, AST["q_meta"])]]
    elif item.get("is_english"):
        meta_rows = []   # no top meta block for English
    else:
        lo_disp  = f"<b>LO assessed:</b> {_clean_text(lo_text)}" if lo_text else "<b>LO assessed:</b> —"
        cog_disp = f"<b>Cognitive demand:</b> {_clean_text(item.get('cognitive_demand', ''))}"
        meta_rows = [
            [Paragraph(lo_disp,  AST["q_meta"])],
            [Paragraph(cog_disp, AST["q_meta"])],
        ]

    # ── Section header (English: every question; others: first question only) ─
    if header_items:
        story.extend(header_items)

    # ── Source section label (English only, every question) ──────────────────
    src_sec_lbl = item.get("_source_section_label", "")
    if src_sec_lbl and item.get("is_english"):
        src_style = ParagraphStyle(
            "src_sec_lbl", fontName="Helvetica-Bold", fontSize=7,
            leading=10, textColor=colors.black,
            alignment=1,  # centre
            spaceBefore=1, spaceAfter=2,
        )
        story.append(Paragraph(f"Source section: {src_sec_lbl}", src_style))

    # ── Question number + text ────────────────────────────────────────────────
    if is_fill_in and item.get("is_english"):
        q_raw = item.get("question_text") or ""
        if q_raw:
            _render_fill_in_stem(q_raw, uw, story, q_num)
        else:
            story.append(Paragraph(f"<b>Q{q_num}.</b>", AST["q_text"]))
    else:
        q_raw = item.get("question_text") or ""
        if item.get("is_english") and q_raw and "\n" in q_raw:
            q_text = "<br/>".join(_clean_text(ln) for ln in q_raw.split("\n"))
        else:
            q_text = _clean_text(q_raw)

        if q_text:
            q_para = Paragraph(f"<b>Q{q_num}.</b>  {q_text}", AST["q_text"])
        else:
            q_para = Paragraph(f"<b>Q{q_num}.</b>", AST["q_text"])

        if meta_rows:
            meta_block = Table(meta_rows, colWidths=[uw])
            meta_block.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(KeepTogether([meta_block, Spacer(1, 2), q_para]))
        else:
            story.append(q_para)

    # ── Word box (MATCH items) ─────────────────────────────────────────────────
    wb_words = item.get("_word_box_words")
    if wb_words:
        _render_word_box(wb_words, uw, story)

    # ── Visual stimulus ────────────────────────────────────────────────────────
    # Suppressed for FILL_IN -- tables already rendered inline by
    # _render_fill_in_stem so visual_stimulus would be a duplicate.
    if not is_fill_in:
        vs = item.get("visual_stimulus")
        if vs and isinstance(vs, str) and vs.strip():
            _render_visual_stimulus(vs, uw, story)

    # ── MCQ options ───────────────────────────────────────────────────────────
    _is_true_false = (item.get("question_type", "") or "").upper() == "TRUE_FALSE"
    if qtype == "MCQ" and not item.get("_suppress_options") and not _is_true_false:
        label_map = {"A": "A.", "B": "B.", "C": "C.", "D": "D."}
        opt_rows = []
        for opt in item.get("options", []):
            raw_lbl     = _clean_text(opt.get("label", "")).rstrip(".")
            display_lbl = label_map.get(raw_lbl, raw_lbl + ".")
            opt_rows.append([
                Paragraph(f"<b>{display_lbl}</b>",         AST["q_opt_lbl"]),
                Paragraph(_clean_text(opt.get("text", "")), AST["q_opt_txt"]),
            ])
        if opt_rows:
            opt_t = Table(opt_rows, colWidths=[uw * 0.07, uw * 0.93])
            opt_t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), ( 0, -1), 18),
                ("LEFTPADDING",   (1, 0), ( 1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(opt_t)

    # Math SCR / NUM / ECR: response boxes suppressed (teacher-facing PDF)

    # ── Open task ─────────────────────────────────────────────────────────────
    elif qtype == "open_task":
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

    # ── English: Teacher Guide  then  Learning Outcome below (fix 3) ──────────
    if item.get("is_english"):
        _tg   = item.get("teacher_guide") or {}
        _sug  = _tg.get("suggested_answer", "") or item.get("suggested_answer", "") or ""
        _elems = _tg.get("expected_elements") or item.get("expected_elements") or []
        tg_lbl_style = ParagraphStyle(
            "eng_tg_lbl", fontName="Helvetica-Bold", fontSize=7,
            leading=10, textColor=colors.HexColor("#085041"),
        )
        if _sug or _elems:
            story.append(Spacer(1, 3))
            story.append(Paragraph("Teacher Guide", tg_lbl_style))
            if _sug:
                for gp in _eng_guide_paras(str(_sug), uw):
                    story.append(gp)
            if _elems:
                elem_style = ParagraphStyle(
                    "eng_tg_elem", fontName="Helvetica", fontSize=7.5,
                    leading=11, textColor=colors.HexColor("#085041"),
                    leftIndent=8,
                )
                for ei, elem in enumerate(_elems, 1):
                    story.append(Paragraph(f"{ei}. {_clean_text(str(elem))}", elem_style))
            story.append(Spacer(1, 3))

        # LO below teacher guide -- 7.5 pt, one blank row gap (fix 3)
        lo_after = _clean_text(lo_text or "")
        if lo_after:
            story.append(Spacer(1, 4))
            lo_tbl = Table(
                [[Paragraph(f"<b>Learning Outcome:</b> {lo_after}", AST["q_lo"])]],
                colWidths=[uw],
            )
            lo_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(lo_tbl)

    # ── Mathematics: Exercise companion card ──────────────────────────────────
    if is_maths:
        ex = item.get("exercise") or {}
        ex_book_ref    = _clean_text(ex.get("book_ref", "") or "")
        ex_description = _clean_text(ex.get("description", "") or "")
        if ex_book_ref:
            ex_label_para = Paragraph(f"<b>Exercise — {ex_book_ref}</b>", AST["q_meta"])
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

    story.append(Spacer(1, 3 * mm))

    items      = data["assessment_items"]
    lo_map     = data["lo_map"]
    is_science = data.get("is_science", False)
    is_maths   = data.get("is_maths",   False)
    is_english = data.get("is_english", False)
    q_counter  = 0

    if is_english:
        # ── English: sections grouped by spine (RFC, Listening, Speaking, …) ──
        # Each spine becomes a section header; items are in order within spine.
        # lo_text per item = source_lo (spine-cell LO from LP handoff).
        _ENG_SPINE_TITLES = {
            "reading_for_comprehension": "Reading for Comprehension",
            "listening":                 "Listening",
            "speaking":                  "Speaking",
            "writing":                   "Writing",
            "vocabulary_grammar":        "Vocabulary and Grammar",
            "beyond_text":               "Beyond the Text",
        }
        for spine_sec in items:
            if not isinstance(spine_sec, dict):
                continue
            _spine_code  = (spine_sec.get("spine_code") or "").strip().lower()
            _spine_title = (
                spine_sec.get("spine_title")
                or _ENG_SPINE_TITLES.get(_spine_code)
                or _spine_code.replace("_", " ").title()
            )
            _spine_items = spine_sec.get("items") or []
            if not _spine_items:
                continue

            sec_para  = Paragraph(_spine_title.upper(), AST["sec_hdr"])
            sec_hline = HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3)

            for idx, item in enumerate(_spine_items):
                if not isinstance(item, dict):
                    continue
                q_counter += 1
                # lo_text: prefer source_lo (v3.0 constitution), fall back to implied_lo
                lo_text = item.get("source_lo", "") or item.get("implied_lo", "") or ""
                # Mark item as English so question_block uses the right meta branch
                item["is_english"] = True
                item.setdefault("question_type", item.get("question_type", ""))
                item.setdefault("cognitive_demand", "")

                # ── Pre-process item_stem for MATCH and MCQ types (fix b,d,f) ──
                raw_stem   = item.get("item_stem", "") or ""
                qtype_here = (item.get("question_type", "") or "").strip().upper()

                if qtype_here == "MATCH" and raw_stem:
                    # Extract word-box line and strip numbered match-list lines
                    # that are already present as rows in visual_stimulus (fix b,d).
                    vs_text = item.get("visual_stimulus", "") or ""
                    vs_row_set: set = set()
                    if vs_text:
                        for vs_ln in vs_text.strip().splitlines()[1:]:  # skip header
                            vs_cells = [c.strip() for c in vs_ln.split("|") if c.strip()]
                            if vs_cells:
                                vs_row_set.add(vs_cells[0].lower())

                    word_box_words: list = []
                    clean_lines = []
                    for line in raw_stem.splitlines():
                        wb_match = re.match(
                            r"^Word\s+box\s*[:：]\s*(.+)", line.strip(), re.IGNORECASE
                        )
                        if wb_match:
                            word_box_words = [
                                w.strip() for w in re.split(r"\s{2,}|\t", wb_match.group(1))
                                if w.strip()
                            ]
                            continue  # don't include word-box line in displayed stem
                        # Strip numbered match-list lines already in vs table (fix d)
                        stripped = line.strip()
                        if re.match(r"^\d+\.", stripped) and stripped.lower() in vs_row_set:
                            continue
                        clean_lines.append(line)
                    item["question_text"] = "\n".join(clean_lines).strip()
                    # Store word-box words on item so question_block can render
                    # them between the stem and the visual_stimulus table (fix b)
                    if word_box_words:
                        item["_word_box_words"] = word_box_words

                elif qtype_here == "MCQ" and "My prediction" in raw_stem:
                    # Predict-then-listen: stem embeds questions + options inline.
                    # Suppress the flat options list to avoid duplication (fix f).
                    item["question_text"] = raw_stem
                    item["_suppress_options"] = True

                else:
                    item.setdefault("question_text", raw_stem)

                # teacher_guide already present on item; question_block reads it
                # Spine header: first question in this spine group only.
                # Source section label: every question.
                header_items = [sec_para, sec_hline] if idx == 0 else None

                src_sec_title = _clean_text(item.get("source_section_title", "") or "")
                if src_sec_title:
                    item["_source_section_label"] = src_sec_title

                story.extend(question_block(
                    q_counter, item, lo_text, uw,
                    header_items=header_items,
                ))

            story.append(Spacer(1, 4 * mm))

    elif is_maths:
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

    # ── Notes section — pushed to the bottom of the last page (fix 2) ──────────
    # Renamed from "Guidance" → "Notes" (fix 2, all subjects).
    # PageBreak pushes it to the start of a fresh page so it always appears
    # at the foot of the document and never mid-content.
    _is_maths_notes = data.get("is_maths", False)
    if _is_maths_notes:
        _notes_line2 = (
            "Teacher guidance (expected answer, method, distractors, inclusivity) is available "
            "in the online view under My Plans > Chapter Assessment."
        )
    else:
        _notes_line2 = (
            "Teacher guidance for each question, including what incorrect responses reveal and "
            "inclusivity scaffolds, is available in the Aruvi platform under "
            "My Plans > Chapter Assessment."
        )
    notes_lbl_style = ParagraphStyle(
        "notes_lbl", fontName="Helvetica-Bold", fontSize=8.5, leading=13,
        textColor=INK, spaceBefore=6,
    )
    notes_style = ParagraphStyle(
        "notes_body", fontName="Helvetica", fontSize=8.5, leading=13,
        textColor=INK, leftIndent=10,
    )
    # Notes block: keep together and only break page if not enough room remains.
    # CondPageBreak triggers a new page only when remaining space < the given height.
    # Estimated height of the Notes block: ~55pt covers label + 2 lines + spacers.
    from reportlab.platypus import CondPageBreak
    notes_block = [
        CondPageBreak(55),
        HLine(uw, thickness=0.5, color=HAIRLINE, sb=4, sa=2),
        Paragraph("Notes", notes_lbl_style),
        Spacer(1, 3),
        Paragraph(
            "1.  Marks are not prescribed — assign per question based on formative assessment "
            "weightage and cognitive demand.",
            notes_style,
        ),
        Paragraph("2.  " + _notes_line2, notes_style),
        Spacer(1, 4 * mm),
    ]
    story.extend(notes_block)

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
    is_english = (subject == "English")

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

    if is_english:
        # English assessment_items is a list of spine-section objects, each with
        # nested items[]. Total question count = sum of items across all spines.
        total_q = sum(len(sec.get("items") or []) for sec in raw_items if isinstance(sec, dict))
        return {
            "chapter_num":      j["chapter_number"],
            "chapter_title":    j["chapter_title"],
            "grade":            str(j["grade"]).replace("Grade ", ""),
            "subject":          subject,
            "date":             date_str,
            "total_questions":  total_q,
            "assessment_items": raw_items,   # spine-grouped; English renderer iterates spines
            "lo_map":           {},
            "is_science":       False,
            "is_maths":         False,
            "is_english":       True,
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
        "is_english":       False,
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
