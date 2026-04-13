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
    qtype = item.get("question_type", "")

    # Science uses OPEN_TASK (uppercase); normalise to open_task so the shared
    # rendering path below handles both subjects identically.
    if qtype == "OPEN_TASK":
        qtype = "open_task"

    # ── Fix 7: 2-row single-col meta table (BG_META background, dark grey text) ─
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

    # ── Visual stimulus note ──────────────────────────────────────────────────
    # Science items carry visual_stimulus; SS items do not — this is always a
    # no-op for SS since .get() returns None and the branch is never entered.
    visual = item.get("visual_stimulus") or ""
    if visual:
        story.append(Paragraph(
            "<i>A visual stimulus is provided for this question.</i>",
            AST["combo_note"],
        ))

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

    # Fix 1: SCR — "Look for" / expected_elements block removed entirely
    # Fix 1: ECR — "Look for" / look_for block removed entirely

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

    # ── Fix 6: single combined italic note ────────────────────────────────────
    story.append(Paragraph(
        "Marks are not prescribed \u2014 assign per question based on formative assessment "
        "weightage and cognitive demand.<br/>"
        "Teacher guidance for each question, including what incorrect responses reveal and "
        "inclusivity scaffolds, is available in the Aruvi platform under "
        "My Plans &gt; Chapter Assessment.",
        AST["combo_note"],
    ))
    story.append(Spacer(1, 5 * mm))

    items      = data["assessment_items"]
    lo_map     = data["lo_map"]
    is_science = data.get("is_science", False)
    q_counter  = 0

    if is_science:
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
            group = [it for it in items if it.get("question_type") == qtype]
            if not group:
                continue

            # Fix 8: section header flowables — dark grey (#444444), 7.5pt, bold
            sec_para  = Paragraph(TYPE_NAMES[qtype].upper(), AST["sec_hdr"])
            sec_hline = HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3)

            for idx, item in enumerate(group):
                q_counter += 1

                # Resolve implied LO from LP period(s)
                lo_ref = item.get("guide", {}).get("learning_outcome", {})
                if "periods" in lo_ref:
                    lo_text = "Multiple periods"
                else:
                    pn = lo_ref.get("period")
                    lo_text = lo_map.get(pn, "") if pn is not None else ""

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

    # ── Footnote ──────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "(1) Assessment designed per Aruvi Assessment Constitution V1.4 "
        "\u00b7 Competency weight governs question distribution "
        "\u00b7 One open task per assessment.",
        ST["footer"],
    ))

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
        "total_questions":  len(j["result"]["assessment_items"]),
        "assessment_items": j["result"]["assessment_items"],
        "lo_map":           lo_map,
        "is_science":       is_science,
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
