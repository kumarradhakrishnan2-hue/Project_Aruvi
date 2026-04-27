"""
Aruvi Lesson Plan PDF  — v3
Changes from v2:
  1. _clean_text() Unicode sanitiser — strips diacritics throughout
  2. Aruvi logo in page header (replaces hand-drawn box); graceful fallback
  3. Dynamic page numbers via two-pass pypdf overlay (no "Confidential")
  4. Section anchor: first sentence only (split at '/'), "Section:" bolded
  5. "LO" label drawn inside LOBox; Spacer(1,3) added above material row
  6. "Confidential" removed from footer (subsumed by Fix 3)
  7. "Total periods" label, plain period count, weight from chapter_weight
"""
import unicodedata
import os
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Flowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from pypdf import PdfReader, PdfWriter

PAGE_W, PAGE_H = A4
L_MAR = 18 * mm
R_MAR = 18 * mm
T_MAR = 14 * mm
B_MAR = 16 * mm

# ── Palette ───────────────────────────────────────────────────────────────────
INK      = colors.HexColor("#1a1917")
MID      = colors.HexColor("#5a5754")
MUTE     = colors.HexColor("#888888")
HAIRLINE = colors.HexColor("#dddddd")
BG_META  = colors.HexColor("#f7f6f3")
BG_ROW   = colors.HexColor("#ffffff")   # activity/material rows: plain white
BLUE_TAG = colors.HexColor("#185fa5")
BLUE_BG  = colors.HexColor("#e6f1fb")
ROW_LINE = colors.HexColor("#f0ede9")   # inter-row hairline

# ── Logo path (absolute, resolved relative to this file) ─────────────────────
LOGO_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "miscellaneous", "aruvi_logo-transparent.png")
)


# ── Unicode sanitiser ────────────────────────────────────────────────────────
def _clean_text(s) -> str:
    """
    Strip combining diacritical marks so ReportLab's standard fonts
    can render the string without a UnicodeEncodeError.
    Non-string values are coerced to str first.
    """
    if s is None:
        return ""
    s = str(s)
    nfd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def make_styles():
    s = {}

    def st(name, **kw):
        s[name] = ParagraphStyle(name, **kw)

    st("base",        fontName="Helvetica",      fontSize=8.5,  leading=12, textColor=INK)
    st("mute",        fontName="Helvetica",      fontSize=6.5,  leading=9,  textColor=MUTE)
    st("micro",       fontName="Helvetica",      fontSize=5.5,  leading=8,  textColor=MUTE)
    st("brand_name",  fontName="Helvetica-Bold", fontSize=11,   leading=14, textColor=INK)
    st("hdr_right_t", fontName="Helvetica-Bold", fontSize=7.5,  leading=10, textColor=INK, alignment=TA_RIGHT)
    st("hdr_right_s", fontName="Helvetica",      fontSize=6,    leading=8,  textColor=MUTE, alignment=TA_RIGHT)
    # Meta strip — labels above, values below
    st("meta_lbl",    fontName="Helvetica-Bold", fontSize=5.5,  leading=7,  textColor=INK,  alignment=TA_CENTER)
    st("meta_val",    fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK,  alignment=TA_CENTER)
    st("meta_val_bl", fontName="Helvetica",      fontSize=7,    leading=11, textColor=BLUE_TAG, alignment=TA_CENTER)
    # Period header row (same look as time-breakdown rows)
    st("period_lbl",  fontName="Helvetica-Bold", fontSize=7.5,  leading=11, textColor=INK)
    st("period_time", fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)
    st("period_act",  fontName="Helvetica-Bold", fontSize=8.5,  leading=12, textColor=INK)
    st("period_sec",  fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)  # plain black
    # Time-breakdown rows
    st("tb_time",     fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=MID)
    st("tb_desc",     fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)
    # Material row
    st("mat_label",   fontName="Helvetica-Bold", fontSize=7.5,  leading=11, textColor=INK)
    st("mat_text",    fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)
    # LO
    st("lo_text",     fontName="Helvetica-Oblique", fontSize=8.5, leading=13, textColor=INK)
    st("lo_tag",      fontName="Helvetica-Bold", fontSize=5.5,  leading=8,  textColor=MUTE)
    # Competency table
    st("comp_hdr",     fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=INK)
    st("comp_hdr_ctr", fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=INK, alignment=TA_CENTER)
    st("comp_code",    fontName="Helvetica-Bold", fontSize=7.5,  leading=11, textColor=BLUE_TAG, alignment=TA_CENTER)
    st("comp_text",   fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)
    # Section label
    st("section_lbl", fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=MUTE,
       alignment=TA_CENTER, spaceBefore=4, spaceAfter=4, letterSpacing=1.5)
    # Footer
    st("footer",      fontName="Helvetica",      fontSize=5.5,  leading=8,  textColor=colors.HexColor("#bbbbbb"))
    # Science stage header (centre-aligned, bold, same size as period_act)
    st("sci_stage_hdr", fontName="Helvetica-Bold", fontSize=8.5, leading=12, textColor=INK, alignment=TA_CENTER)
    return s


ST = make_styles()


# ──────────────────────────────────────────────────────────────────────────────
# Thin hairline Flowable
# ──────────────────────────────────────────────────────────────────────────────
class HLine(Flowable):
    def __init__(self, width, thickness=0.4, color=HAIRLINE, sb=3, sa=3):
        super().__init__()
        self.w = width; self.t = thickness; self.c = color
        self.spaceBefore = sb; self.spaceAfter = sa

    def wrap(self, aw, ah):
        return (self.w, self.t + self.spaceBefore + self.spaceAfter)

    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(self.c)
        self.canv.setLineWidth(self.t)
        self.canv.line(0, self.spaceBefore, self.w, self.spaceBefore)
        self.canv.restoreState()


# ──────────────────────────────────────────────────────────────────────────────
# Curly-brace LO Flowable
# ──────────────────────────────────────────────────────────────────────────────
class LOBox(Flowable):
    """
    Draws a small "LO" tag, then a left-side curly brace {, then the italic
    LO text to its right.  Plain white background (no fill).
    """
    LO_TAG_W = 14  # points reserved for the "LO" label
    BRACE_W  = 10  # points for the brace
    PAD_L    = 4
    PAD_R    = 6
    PAD_V    = 6

    def __init__(self, text, avail_width):
        super().__init__()
        self._text    = _clean_text(text)
        self._aw      = avail_width
        self._style   = ST["lo_text"]
        self._inner_w = avail_width - self.LO_TAG_W - self.BRACE_W - self.PAD_L - self.PAD_R
        # pre-compute paragraph height
        from reportlab.platypus import Paragraph as _P
        p = _P(f"<i>{self._text}</i>", self._style)
        _, self._ph = p.wrap(self._inner_w, 9999)
        self._h = self._ph + 2 * self.PAD_V

    def wrap(self, aw, ah):
        return (self._aw, self._h)

    def draw(self):
        c = self.canv
        h = self._h
        tag_x = 0                          # "LO" label starts here
        bx    = self.LO_TAG_W + self.BRACE_W  # x where text starts

        # ── draw "LO" tag ────────────────────────────────────────────────────
        c.saveState()
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(MUTE)
        c.drawString(tag_x, h / 2 - 3, "LO")
        c.restoreState()

        # ── draw curly brace ─────────────────────────────────────────────────
        c.saveState()
        c.setStrokeColor(MUTE)
        c.setLineWidth(1.2)
        c.setLineCap(1)
        r     = 4
        mid_y = h / 2
        top_y = h - self.PAD_V
        bot_y = self.PAD_V
        tip_x = 2
        brace_right = self.LO_TAG_W + self.BRACE_W   # same as bx
        p = c.beginPath()
        p.moveTo(brace_right, bot_y)
        p.curveTo(brace_right, bot_y, brace_right - r, bot_y, brace_right - r, bot_y + r)
        p.lineTo(brace_right - r, mid_y - r)
        p.curveTo(brace_right - r, mid_y - r, brace_right - r, mid_y, brace_right - r - tip_x, mid_y)
        p.curveTo(brace_right - r - tip_x, mid_y, brace_right - r, mid_y, brace_right - r, mid_y + r)
        p.lineTo(brace_right - r, top_y - r)
        p.curveTo(brace_right - r, top_y - r, brace_right - r, top_y, brace_right, top_y)
        c.drawPath(p, stroke=1, fill=0)
        c.restoreState()

        # ── draw italic text ─────────────────────────────────────────────────
        from reportlab.platypus import Paragraph as _P
        p_obj = _P(f"<i>{self._text}</i>", self._style)
        p_obj.wrap(self._inner_w, 9999)
        text_x = bx + self.PAD_L
        text_y = self.PAD_V
        p_obj.drawOn(c, text_x, text_y)


# ──────────────────────────────────────────────────────────────────────────────
# Page header / footer
# ──────────────────────────────────────────────────────────────────────────────
def on_page(canvas_obj, doc, doc_meta):
    c = canvas_obj
    c.saveState()
    top_y = PAGE_H - T_MAR
    bx = L_MAR; by = top_y - 3 * mm

    # ── Brand logo (or fallback hand-drawn box) ───────────────────────────────
    logo_drawn = False
    brand_w    = 6.5 * mm   # effective brand block width (used for subtitle placement)
    if os.path.exists(LOGO_PATH):
        try:
            logo_h = 6.5 * mm
            logo_w = logo_h * 3.8          # approximate aspect ratio
            c.drawImage(LOGO_PATH, bx, by,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
            logo_drawn = True
            brand_w    = logo_w
        except Exception:
            pass

    if not logo_drawn:
        # Fallback: hand-drawn box with "A" letter
        c.setStrokeColor(INK); c.setLineWidth(1.2)
        c.rect(bx, by, 6.5 * mm, 6.5 * mm)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
        c.drawCentredString(bx + 3.25 * mm, by + 1.8 * mm, "A")

    # Brand text — always drawn to the right of the logo/box
    text_x = bx + brand_w + 2 * mm
    c.setFont("Helvetica-Bold", 10); c.setFillColor(INK)
    c.drawString(text_x, by + 3.5 * mm, "ARUVI")
    c.setFont("Helvetica", 6); c.setFillColor(MUTE)
    c.drawString(text_x, by + 0.8 * mm, "AI powered teaching assistant")

    rx = PAGE_W - R_MAR
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(INK)
    c.drawRightString(rx, by + 3.5 * mm, doc_meta["doc_type"])
    c.setFont("Helvetica", 5.5); c.setFillColor(MUTE)
    c.drawRightString(rx, by + 0.8 * mm, doc_meta["doc_sub"])
    rule_y = top_y - 11 * mm
    c.setStrokeColor(INK); c.setLineWidth(1.8)
    c.line(L_MAR, rule_y, PAGE_W - R_MAR, rule_y)
    c.setStrokeColor(INK); c.setLineWidth(0.4)
    c.line(L_MAR, rule_y - 1 * mm, PAGE_W - R_MAR, rule_y - 1 * mm)
    fy = B_MAR - 4 * mm
    c.setStrokeColor(HAIRLINE); c.setLineWidth(0.4)
    c.line(L_MAR, fy + 3.5 * mm, PAGE_W - R_MAR, fy + 3.5 * mm)
    c.setFont("Helvetica", 5.5); c.setFillColor(colors.HexColor("#bbbbbb"))
    c.drawString(L_MAR, fy + 1.2 * mm, doc_meta["footer_left"])
    # footer_right is blank on first pass; page numbers stamped in second pass
    if doc_meta.get("footer_right"):
        c.drawRightString(PAGE_W - R_MAR, fy + 1.2 * mm, doc_meta["footer_right"])
    c.restoreState()


# ──────────────────────────────────────────────────────────────────────────────
# Building blocks
# ──────────────────────────────────────────────────────────────────────────────
def meta_strip(chapter_num, title, weight, periods, total_time):
    """
    Two-row table: labels (bold black) on top, values below.
    C-codes removed — they go into the competency table.
    """
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * f for f in [0.09, 0.38, 0.09, 0.16, 0.14, 0.14]]
    lbl_row = [
        Paragraph("Chapter",       ST["meta_lbl"]),
        Paragraph("Title",         ST["meta_lbl"]),
        Paragraph("Weight",        ST["meta_lbl"]),
        Paragraph("Total periods", ST["meta_lbl"]),
        Paragraph("Total time",    ST["meta_lbl"]),
        Paragraph("Date",          ST["meta_lbl"]),
    ]
    val_row = [
        Paragraph(f"Ch {chapter_num:02d}",  ST["meta_val"]),
        Paragraph(_clean_text(title),        ST["meta_val"]),
        Paragraph(_clean_text(str(weight)),  ST["meta_val"]),
        Paragraph(str(periods),              ST["meta_val"]),
        Paragraph(f"{total_time} min",       ST["meta_val"]),
        Paragraph("",                        ST["meta_val"]),
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


def meta_strip_full(chapter_num, title, weight, periods, total_time, date_str):
    """Version with date filled in."""
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * f for f in [0.09, 0.44, 0.19, 0.14, 0.14]]
    lbl_row = [Paragraph(x, ST["meta_lbl"]) for x in
               ["Chapter", "Title", "Total periods", "Total time", "Date"]]
    val_row = [
        Paragraph(f"Ch {chapter_num:02d}",   ST["meta_val"]),
        Paragraph(_clean_text(title),         ST["meta_val"]),
        Paragraph(str(periods),               ST["meta_val"]),
        Paragraph(f"{total_time} min",        ST["meta_val"]),
        Paragraph(_clean_text(date_str),      ST["meta_val"]),
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


def competency_table(competencies):
    """
    Two-column table: C no. | Text of competency
    competencies = [("C-8.1", "Understands the need for a constitution..."), ...]
    """
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * 0.12, uw * 0.88]
    hdr = [Paragraph("C No.", ST["comp_hdr"]), Paragraph("Targeted competencies", ST["comp_hdr_ctr"])]
    rows = [hdr]
    for code, text in competencies:
        rows.append([
            Paragraph(_clean_text(code), ST["comp_code"]),
            Paragraph(_clean_text(text), ST["comp_text"]),
        ])
    t = Table(rows, colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("BACKGROUND",    (0, 0), (-1,  0), BG_META),
        ("BACKGROUND",    (0, 1), (-1, -1), colors.white),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ROW_LINE),
    ]))
    return t


def period_card(period_num, duration_min, activity_name, anchored_section,
                time_breakdown, materials, learning_outcome):
    """
    Returns a LIST of flowables (not a KeepTogether) so that long periods
    flow naturally across page boundaries.
    Only the period header + materials row are kept together as an anchor
    block, preventing the header from orphaning at the bottom of a page.
    """
    uw = PAGE_W - L_MAR - R_MAR
    story = []

    # Fix 4: first sentence of anchored section only (split at '/')
    sec_short = _clean_text(anchored_section.split("/")[0].strip())

    # ── Period header row — Period | Duration | Activity (3 cols, no Section) ─
    hdr_data = [[
        Paragraph(f"<b>Period {period_num}</b>",              ST["period_lbl"]),
        Paragraph(f"{duration_min} min",                       ST["period_time"]),
        Paragraph(f"<b>{_clean_text(activity_name)}</b>",      ST["period_act"]),
    ]]
    hdr_t = Table(hdr_data, colWidths=[uw * f for f in [0.13, 0.09, 0.78]])
    hdr_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("LINEABOVE",     (0, 0), (-1, -1), 1.0, INK),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    # ── Materials row — inject "(Section: ...)" after "Textbook" ─────────────
    import re as _re
    mat_display = _clean_text(str(materials))
    if sec_short:
        mat_display = _re.sub(
            r'(Textbook)',
            f'Textbook (Section: {sec_short})',
            mat_display, count=1, flags=_re.IGNORECASE,
        )
    mat_row = [[
        Paragraph("<b>Material</b>", ST["mat_label"]),
        Paragraph(mat_display,       ST["mat_text"]),
    ]]
    mat_t = Table(mat_row, colWidths=[uw * 0.10, uw * 0.90])
    mat_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
        ("LEFTPADDING",   (1, 0), ( 1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    # Anchor: keep header + spacer + materials together so the header never
    # orphans at the bottom of a page without at least the materials row.
    story.append(KeepTogether([hdr_t, Spacer(1, 3), mat_t]))

    # ── Time breakdown rows — flow freely across pages ────────────────────────
    tb_rows = []
    for span, desc in time_breakdown:
        tb_rows.append([
            Paragraph(_clean_text(str(span)), ST["tb_time"]),
            Paragraph(_clean_text(str(desc)), ST["tb_desc"]),
        ])
    if tb_rows:
        tb_t = Table(tb_rows, colWidths=[uw * 0.10, uw * 0.90])
        tb_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
            ("LEFTPADDING",   (1, 0), ( 1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ROW_LINE),
            ("LINEBELOW",     (0,-1), (-1, -1), 0.5, HAIRLINE),
        ]))
        story.append(tb_t)

    # ── Learning outcome — plain white bg, "LO" label, { brace, italic ───────
    story.append(LOBox(_clean_text(learning_outcome), uw))
    story.append(Spacer(1, 4 * mm))
    return story   # list of flowables — NOT wrapped in KeepTogether


def period_card_maths(period_num, duration_min, activity_name, anchored_section,
                      time_breakdown, materials, pedagogical_approach, teacher_notes):
    """
    Mathematics-specific period card.

    Differences from period_card() (SS/Social Sciences):
      1. Materials row has a right-aligned "Pedagogical approach:" column.
      2. LOBox is replaced by a Teacher Notes row (when notes are present).
      3. "Items used:" prefix is NOT shown here — already stripped in adapter.

    Science and Social Sciences are NOT affected — they continue to use
    period_card() or _science_period_block().
    """
    uw = PAGE_W - L_MAR - R_MAR
    story = []

    # Anchor: first segment only (split at ',') for §-locators
    sec_short = _clean_text(str(anchored_section).split(",")[0].strip())

    # ── Period header row (identical style to SS) ─────────────────────────────
    hdr_data = [[
        Paragraph(f"<b>Period {period_num}</b>",              ST["period_lbl"]),
        Paragraph(f"{duration_min} min",                       ST["period_time"]),
        Paragraph(f"<b>{_clean_text(activity_name)}</b>",      ST["period_act"]),
    ]]
    hdr_t = Table(hdr_data, colWidths=[uw * f for f in [0.13, 0.09, 0.78]])
    hdr_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("LINEABOVE",     (0, 0), (-1, -1), 1.0, INK),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    # ── Materials row — 3 columns: label | material text | pedagogical approach ─
    mat_display = _clean_text(str(materials))
    ped_display = _clean_text(str(pedagogical_approach)) if pedagogical_approach else ""

    if ped_display:
        mat_row = [[
            Paragraph("<b>Material</b>",                         ST["mat_label"]),
            Paragraph(mat_display,                               ST["mat_text"]),
            Paragraph(
                f"<b>Pedagogical approach:</b> {ped_display}",
                ST["mat_text"],
            ),
        ]]
        mat_col_ws = [uw * 0.10, uw * 0.55, uw * 0.35]
    else:
        mat_row = [[
            Paragraph("<b>Material</b>", ST["mat_label"]),
            Paragraph(mat_display,       ST["mat_text"]),
        ]]
        mat_col_ws = [uw * 0.10, uw * 0.90]

    mat_t = Table(mat_row, colWidths=mat_col_ws)
    mat_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
        ("LEFTPADDING",   (1, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    story.append(KeepTogether([hdr_t, Spacer(1, 3), mat_t]))

    # ── Time breakdown rows ───────────────────────────────────────────────────
    tb_rows = []
    for span, desc in time_breakdown:
        tb_rows.append([
            Paragraph(_clean_text(str(span)), ST["tb_time"]),
            Paragraph(_clean_text(str(desc)), ST["tb_desc"]),
        ])
    if tb_rows:
        tb_t = Table(tb_rows, colWidths=[uw * 0.10, uw * 0.90])
        tb_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
            ("LEFTPADDING",   (1, 0), ( 1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ROW_LINE),
            ("LINEBELOW",     (0,-1), (-1, -1), 0.5, HAIRLINE),
        ]))
        story.append(tb_t)

    # ── Teacher Notes row (replaces LOBox for Maths) ─────────────────────────
    tn = _clean_text(str(teacher_notes)) if teacher_notes else ""
    if tn:
        tn_row = [[
            Paragraph("<b>Teacher Notes</b>", ST["mat_label"]),
            Paragraph(tn,                     ST["mat_text"]),
        ]]
        tn_t = Table(tn_row, colWidths=[uw * 0.15, uw * 0.85])
        tn_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BLUE_BG),
            ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
            ("LEFTPADDING",   (1, 0), ( 1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tn_t)

    story.append(Spacer(1, 4 * mm))
    return story


# ──────────────────────────────────────────────────────────────────────────────
# Science-specific building blocks
# ──────────────────────────────────────────────────────────────────────────────

def _science_stage_summary(stages, uw):
    """
    Section 1 for Science PDFs.
    Three-column table: Stage No. | Progression Stage | Description
    One header row + one data row per progression stage.
    """
    col_ws = [uw * 0.12, uw * 0.25, uw * 0.63]
    hdr = [
        Paragraph("Stage No.",         ST["comp_hdr"]),
        Paragraph("Progression Stage", ST["comp_hdr"]),
        Paragraph("Description",       ST["comp_hdr"]),
    ]
    rows = [hdr]
    for stage in stages:
        rows.append([
            Paragraph(_clean_text(str(stage.get("stage_number") or "—")), ST["comp_code"]),
            Paragraph(_clean_text(str(stage.get("stage_label")  or "—")), ST["comp_text"]),
            Paragraph(_clean_text(str(stage.get("description")  or "—")), ST["comp_text"]),
        ])
    t = Table(rows, colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("BACKGROUND",    (0, 0), (-1,  0), BG_META),
        ("BACKGROUND",    (0, 1), (-1, -1), colors.white),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ROW_LINE),
    ]))
    return t


def _science_period_block(period, uw):
    """
    Returns a list of flowables for one Science period block.

    Row 1  — Period header  (Period | Time | Activity Name)
    Row 2  — Materials      (single full-width cell, "Materials:" bold prefix)
    Row 3  — Activity Desc  (single full-width cell, "Activity Description:" bold prefix)
    Row 4+ — Phase rows     (Minutes | Activity), mirroring SS time_bands style
    No LO row for Science.
    """
    story = []

    period_num  = period.get("period_number") or "—"
    duration    = period.get("period_duration_minutes") or "—"
    act_title   = _clean_text(str(period.get("activity_title") or "—"))
    materials   = period.get("materials") or ""
    act_desc    = _clean_text(str(period.get("activity_description") or "—"))
    phases      = period.get("phases") or []

    # ── Row 1: Period header (same proportions / style as SS) ─────────────────
    hdr_data = [[
        Paragraph(f"<b>Period {period_num}</b>",  ST["period_lbl"]),
        Paragraph(f"{duration} min",               ST["period_time"]),
        Paragraph(f"<b>{act_title}</b>",           ST["period_act"]),
    ]]
    hdr_t = Table(hdr_data, colWidths=[uw * f for f in [0.13, 0.09, 0.78]])
    hdr_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("LINEABOVE",     (0, 0), (-1, -1), 1.0, INK),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    # ── Row 2: Materials (single full-width cell, same bg/padding as SS mat) ──
    mat_t = Table(
        [[Paragraph(f"<b>Materials:</b> {_clean_text(str(materials))}", ST["mat_text"])]],
        colWidths=[uw],
    )
    mat_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    # Anchor: keep period header + materials together (mirrors SS anchor pattern)
    story.append(KeepTogether([hdr_t, Spacer(1, 3), mat_t]))

    # ── Row 3: Activity Description (same styling as Materials row) ───────────
    act_t = Table(
        [[Paragraph(f"<b>Activity Description:</b> {act_desc}", ST["mat_text"])]],
        colWidths=[uw],
    )
    act_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("LINEABOVE",     (0, 0), (-1,  0), 0.5, HAIRLINE),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(act_t)

    # ── Rows 4+: Phase rows (mirrors SS time_bands style) ────────────────────
    if phases:
        phase_rows = []
        for ph in phases:
            mins = _clean_text(str(ph.get("minutes") or "—"))
            desc = _clean_text(str(ph.get("description") or "—"))
            phase_rows.append([
                Paragraph(mins, ST["tb_time"]),
                Paragraph(desc, ST["tb_desc"]),
            ])
        phase_t = Table(phase_rows, colWidths=[uw * 0.10, uw * 0.90])
        phase_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), ( 0,  0), 8),
            ("LEFTPADDING",   (1, 0), ( 1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEBELOW",     (0, 0), (-1, -2), 0.3, ROW_LINE),
            ("LINEBELOW",     (0,-1), (-1, -1), 0.5, HAIRLINE),
        ]))
        story.append(phase_t)

    story.append(Spacer(1, 2 * mm))
    return story


def _science_stage_block(stage, uw):
    """
    Returns a list of flowables for one Science progression stage:
      - a full-width, centre-aligned stage header row
      - one period block per period in the stage
    """
    story = []

    stage_num   = _clean_text(str(stage.get("stage_number") or "—"))
    stage_label = _clean_text(str(stage.get("stage_label")  or "—"))

    # Stage header: full-width, centre-aligned, BG_META shading + INK rule above
    # (visually mirrors the SS competency table header)
    stage_hdr_t = Table(
        [[Paragraph(f"<b>Stage {stage_num}: {stage_label}</b>", ST["sci_stage_hdr"])]],
        colWidths=[uw],
    )
    stage_hdr_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BG_META),
        ("LINEABOVE",     (0, 0), (-1, -1), 1.5, INK),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(stage_hdr_t)

    for period in stage.get("periods") or []:
        story.extend(_science_period_block(period, uw))

    story.append(Spacer(1, 2 * mm))
    return story


# ──────────────────────────────────────────────────────────────────────────────
# Science main renderer  (called only when subject == "Science")
# ──────────────────────────────────────────────────────────────────────────────

def _build_science_lp(output_path, data):
    """
    Renders the Science LP PDF.
    Reuses all page setup, header, colour constants, styles, and footer
    logic from the SS path.  Only the story (content flowables) differs.
    """
    doc_meta = {
        "doc_type":     "Lesson Plan",
        "doc_sub":      f"Grade {data['grade']} · {data['subject']} · {data['date']}",
        "footer_left":  (
            f"Aruvi · Lesson Plan · Grade {data['grade']} · "
            f"{data['subject']} · Ch {data['chapter_num']:02d}"
        ),
        "footer_right": "",   # blank on first pass; page numbers stamped in 2nd pass
    }
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=L_MAR, rightMargin=R_MAR,
        topMargin=T_MAR + 14 * mm,
        bottomMargin=B_MAR + 8 * mm,
    )
    uw = PAGE_W - L_MAR - R_MAR

    # Derived totals for meta strip
    all_periods   = [p for s in data["progression_stages"] for p in s.get("periods") or []]
    total_periods = len(all_periods)
    total_time    = sum(
        (p.get("period_duration_minutes") or 0) for p in all_periods
    )

    story = []

    # Meta strip (shared helper — identical to SS)
    story.append(meta_strip_full(
        data["chapter_num"], data["chapter_title"], data["weight"],
        total_periods, total_time, data["date"],
    ))
    story.append(Spacer(1, 3 * mm))

    # Competency table — c_code + canonical description, sourced from chapter mapping
    if data.get("competencies"):
        story.append(competency_table(data["competencies"]))
        story.append(Spacer(1, 4 * mm))

    # Section 1 — Progression Stage Summary Table
    story.append(_science_stage_summary(data["progression_stages"], uw))
    story.append(Spacer(1, 4 * mm))

    # Section 2 — Period blocks grouped by progression stage
    for stage in data["progression_stages"]:
        story.extend(_science_stage_block(stage, uw))

    # ── Pass 1: build PDF without page numbers ────────────────────────────────
    doc.build(
        story,
        onFirstPage=lambda c, d: on_page(c, d, doc_meta),
        onLaterPages=lambda c, d: on_page(c, d, doc_meta),
    )

    # ── Pass 2: stamp "Page N of M" (identical logic to SS pass) ─────────────
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
# Main build
# ──────────────────────────────────────────────────────────────────────────────
def build_lp_pdf(output_path, data):
    # ── Subject routing ───────────────────────────────────────────────────────
    if data.get("subject") == "Science":
        _build_science_lp(output_path, data)
        return
    # ── Social Science (and all other subjects) — unchanged below ─────────────
    doc_meta = {
        "doc_type":    "Lesson Plan",
        "doc_sub":     f"Grade {data['grade']} · {data['subject']} · {data['date']}",
        "footer_left": f"Aruvi · Lesson Plan · Grade {data['grade']} · {data['subject']} · Ch {data['chapter_num']:02d}",
        "footer_right": "",   # Fix 3/6: blank on first pass; page numbers stamped in 2nd pass
    }
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=L_MAR, rightMargin=R_MAR,
        topMargin=T_MAR + 14 * mm,
        bottomMargin=B_MAR + 8 * mm,
    )
    uw = PAGE_W - L_MAR - R_MAR
    story = []
    # Meta strip
    story.append(meta_strip_full(
        data["chapter_num"], data["chapter_title"], data["weight"],
        len(data["periods"]),
        sum(p["duration"] for p in data["periods"]),
        data["date"],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(competency_table(data["competencies"]))
    story.append(Spacer(1, 4 * mm))
    # Period cards — route Mathematics through period_card_maths();
    # all other subjects (Social Sciences etc.) use period_card().
    # period_card() / period_card_maths() return lists; extend so each
    # flowable is added individually and can split across page boundaries.
    is_maths = data.get("subject") == "Mathematics"
    for p in data["periods"]:
        if is_maths:
            story.extend(period_card_maths(
                p["num"], p["duration"],
                p["activity_name"], p["anchored_section"],
                p["time_breakdown"], p["materials"],
                p.get("pedagogical_approach", ""),
                p.get("teacher_notes", ""),
            ))
        else:
            story.extend(period_card(
                p["num"], p["duration"],
                p["activity_name"], p["anchored_section"],
                p["time_breakdown"], p["materials"], p["learning_outcome"],
            ))
    # ── Pass 1: build PDF without page numbers ────────────────────────────────
    doc.build(
        story,
        onFirstPage=lambda c, d: on_page(c, d, doc_meta),
        onLaterPages=lambda c, d: on_page(c, d, doc_meta),
    )

    # ── Pass 2: stamp "Page N of M" onto every page using pypdf ──────────────
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
            f"Page {i + 1} of {total}"
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
# Adapter: Aruvi LPA JSON → build_lp_pdf() data dict
# ──────────────────────────────────────────────────────────────────────────────
def json_to_lp_data(j: dict) -> dict:
    """
    Converts the Aruvi LPA output JSON dict (as saved to disk / stored in
    session state) into the data dict expected by build_lp_pdf().
    """
    from collections import OrderedDict
    from datetime import datetime

    # Date: take the date portion of saved_at ("2026-03-26T11:28:26" → "26 March 2026")
    dt = datetime.fromisoformat(j["saved_at"])
    date_str = dt.strftime("%-d %B %Y")

    # Weight: look up from the chapter_mappings JSON in knowledge_commons.
    # Path pattern:  <project_root>/mirror/chapters/{subject_group}/{grade}/mappings/chapter_mappings_{subject_group}_{grade}.json
    # subject_group: "Social Science" → "social_sciences" etc. (mirrors app.py subject_to_folder)
    # grade:         "Grade VII" → "vii"  (roman-numeral folder name, matching mirror/ layout)
    _subject_map = {
        "Social Science":  "social_sciences",
        "Mathematics":     "mathematics",
        "Science":         "science",
        "English":         "languages",
        "Second Language": "languages",
        "EVS":             "science",
    }
    _grade_map = {
        "Grade I":    "i",    "Grade II":   "ii",   "Grade III": "iii",
        "Grade IV":   "iv",   "Grade V":    "v",    "Grade VI":  "vi",
        "Grade VII":  "vii",  "Grade VIII": "viii",
        "Grade IX":   "ix",   "Grade X":    "x",
    }
    _subject_grp  = _subject_map.get(j.get("subject", ""), j.get("subject", "").lower().replace(" ", "_"))
    _raw_grade    = j.get("grade", "")
    _grade_folder = _grade_map.get(_raw_grade, _raw_grade.lower().replace("grade ", ""))  # "Grade VII" → "vii"
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _map_path     = os.path.join(
        _project_root, "mirror", "chapters", _subject_grp, _grade_folder, "mappings",
        f"chapter_mappings_{_subject_grp}_{_grade_folder}.json"
    )
    weight = "—"
    try:
        import json as _json
        _entries = _json.load(open(_map_path, encoding="utf-8"))
        _ch_num  = j.get("chapter_number")
        _entry   = next((e for e in _entries if e.get("chapter_number") == _ch_num), None)
        if _entry:
            weight = _entry.get("chapter_weight", "—")
    except Exception:
        pass   # file not found or malformed — fall back to "—"

    # ── Subject routing: Science uses a different JSON structure ──────────────
    if j.get("subject") == "Science":
        return _json_to_science_lp_data(j, date_str, weight)

    # ── Subject routing: Mathematics uses v2.1 LP shape ───────────────────────
    if j.get("subject") == "Mathematics":
        return _json_to_maths_lp_data(j, date_str, weight)

    # ── Load canonical competency descriptions from framework JSON ────────────
    # The AI-generated competency_text in each period is unreliable (it tends
    # to paraphrase the mapping justification rather than use the canonical
    # framework description).  Always prefer the lookup from comp_descs.
    _stage_map = {
        "i": "primary", "ii": "primary", "iii": "primary",
        "iv": "primary", "v": "primary",
        "vi": "middle",  "vii": "middle", "viii": "middle",
        "ix": "secondary", "x": "secondary",
    }
    _stage_for_comp = _stage_map.get(_grade_folder, "middle")
    _comp_desc_path = os.path.join(
        _project_root, "mirror", "framework", _subject_grp, _stage_for_comp,
        f"competency_descriptions_{_stage_for_comp}.json",
    )
    _comp_descs: dict = {}
    try:
        with open(_comp_desc_path, encoding="utf-8") as _f:
            _raw = _json.load(_f)
        # Two formats: flat {c_code: text} (SS/Lang) or nested {curricular_goals:[…]} (Science)
        if "curricular_goals" in _raw:
            for _cg in _raw["curricular_goals"]:
                for _comp in _cg.get("competencies", []):
                    _comp_descs[_comp.get("code", "")] = _comp.get("description", "")
        else:
            _comp_descs = _raw
    except Exception:
        pass  # fall back to AI-generated text if file missing

    # Collect unique competencies in order of first appearance
    # Prefer canonical description from comp_descs; fall back to AI-generated text.
    seen = OrderedDict()
    for p in j["result"]["lesson_plan"]["periods"]:
        c = p["competency"]
        c_code = c["c_code"]
        if c_code not in seen:
            seen[c_code] = _comp_descs.get(c_code, "") or c.get("competency_text", "")
    competencies = list(seen.items())   # list of (c_code, text)

    # Build period list
    periods = []
    for p in j["result"]["lesson_plan"]["periods"]:
        # Support both old ("material") and new ("materials") field names
        mat = p.get("material") or p.get("materials") or ""
        if isinstance(mat, list):
            mat = ", ".join(str(m) for m in mat)
        periods.append({
            "num":              p["period_number"],
            "duration":         p["period_duration_minutes"],
            # Support both old ("activity_name") and new ("activity_title") field names
            "activity_name":    p.get("activity_name") or p.get("activity_title", ""),
            "anchored_section": p["section_anchor"],
            "time_breakdown":   [(tb["minutes"], tb["activity"]) for tb in p["time_bands"]],
            "materials":        mat,
            "learning_outcome": p["implied_lo"],
        })

    return {
        "chapter_num":   j["chapter_number"],
        "chapter_title": j["chapter_title"],
        "grade":         str(j["grade"]).replace("Grade ", ""),   # "Grade VII" → "VII"
        "subject":       j["subject"],
        "date":          date_str,
        "weight":        weight,
        "competencies":  competencies,
        "periods":       periods,
    }


def _json_to_science_lp_data(j: dict, date_str: str, weight) -> dict:
    """
    Parse a Science LP JSON dict into the data dict consumed by
    _build_science_lp().  Missing / null fields are replaced with "—".

    Actual JSON layout
    ------------------
    result.lesson_plan.cognitive_progression  — list of stage summary dicts
        {stage_number, stage_label, description}
    result.lesson_plan.periods                — flat list of all periods
        {period_number, period_duration_minutes, progression_stage (int),
         activity_title, activity_description, materials (list), phases (list)}

    We group the flat periods list by progression_stage to produce the nested
    progression_stages structure expected by _build_science_lp().
    """
    import json as _json

    lp = (j.get("result") or {}).get("lesson_plan") or {}

    # ── Load competencies from chapter mapping + framework description files ──
    _subject_map = {
        "Science": "science", "EVS": "science",
    }
    _grade_map = {
        "Grade I":    "i",    "Grade II":   "ii",   "Grade III": "iii",
        "Grade IV":   "iv",   "Grade V":    "v",    "Grade VI":  "vi",
        "Grade VII":  "vii",  "Grade VIII": "viii",
        "Grade IX":   "ix",   "Grade X":    "x",
    }
    _stage_map = {
        "i": "primary", "ii": "primary", "iii": "primary",
        "iv": "primary", "v": "primary",
        "vi": "middle",  "vii": "middle", "viii": "middle",
        "ix": "secondary", "x": "secondary",
    }
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _subject_grp  = _subject_map.get(j.get("subject", ""), "science")
    _raw_grade    = j.get("grade", "")
    _grade_folder = _grade_map.get(_raw_grade, _raw_grade.lower().replace("grade ", ""))
    _stage        = _stage_map.get(_grade_folder, "middle")
    _ch_num       = j.get("chapter_number", 0)

    # Step 1 — read the per-chapter mapping JSON for c_codes
    _ch_map_path = os.path.join(
        _project_root, "mirror", "chapters", _subject_grp, _grade_folder, "mappings",
        f"ch_{_ch_num:02d}_mapping.json",
    )
    _c_codes = []
    try:
        _ch_map = _json.load(open(_ch_map_path, encoding="utf-8"))
        for entry in _ch_map.get("primary") or []:
            code = entry.get("c_code", "")
            if code and code not in _c_codes:
                _c_codes.append(code)
    except Exception:
        pass

    # Step 2 — read competency descriptions and build lookup dict
    _comp_desc_path = os.path.join(
        _project_root, "mirror", "framework", _subject_grp, _stage,
        f"competency_descriptions_{_stage}.json",
    )
    _comp_descs: dict = {}
    try:
        _raw = _json.load(open(_comp_desc_path, encoding="utf-8"))
        if "curricular_goals" in _raw:
            for _cg in _raw["curricular_goals"]:
                for _comp in _cg.get("competencies", []):
                    _comp_descs[_comp.get("code", "")] = _comp.get("description", "")
        else:
            _comp_descs = _raw
    except Exception:
        pass

    competencies = [(code, _comp_descs.get(code, "")) for code in _c_codes]

    # ── Build stage summary rows from cognitive_progression ───────────────────
    cog_stages = lp.get("cognitive_progression") or []
    # Index by stage_number so we can attach periods later
    stage_map = {}
    for s in cog_stages:
        sn = s.get("stage_number") or "—"
        stage_map[sn] = {
            "stage_number": sn,
            "stage_label":  s.get("stage_label")  or "—",
            "description":  s.get("description")  or "—",
            "periods":      [],
        }

    # ── Parse flat periods list and bucket into their stage ───────────────────
    for p in lp.get("periods") or []:
        raw_mat = p.get("materials") or []
        if isinstance(raw_mat, list):
            mat_str = ", ".join(str(m) for m in raw_mat if m)
        else:
            mat_str = str(raw_mat) if raw_mat else ""

        period_entry = {
            "period_number":           p.get("period_number") or "—",
            "period_duration_minutes": p.get("period_duration_minutes") or "—",
            "activity_title":          p.get("activity_title") or "—",
            "materials":               mat_str,
            "activity_description":    p.get("activity_description") or "—",
            "phases":                  p.get("phases") or [],
        }

        sn = p.get("progression_stage") or "—"
        if sn in stage_map:
            stage_map[sn]["periods"].append(period_entry)
        else:
            # Orphan period — create a stage entry on the fly
            if sn not in stage_map:
                stage_map[sn] = {
                    "stage_number": sn,
                    "stage_label":  p.get("stage_label") or "—",
                    "description":  "—",
                    "periods":      [],
                }
            stage_map[sn]["periods"].append(period_entry)

    # ── Preserve stage order (cognitive_progression order, then any orphans) ──
    ordered_keys = [s.get("stage_number") or "—" for s in cog_stages]
    for k in stage_map:
        if k not in ordered_keys:
            ordered_keys.append(k)
    progression_stages = [stage_map[k] for k in ordered_keys if k in stage_map]

    return {
        "chapter_num":        j["chapter_number"],
        "chapter_title":      j["chapter_title"],
        "grade":              str(j["grade"]).replace("Grade ", ""),
        "subject":            j["subject"],
        "date":               date_str,
        "weight":             weight,
        "competencies":       competencies,
        "progression_stages": progression_stages,
    }


def _json_to_maths_lp_data(j: dict, date_str: str, weight) -> dict:
    """
    Adapter for Mathematics LP v2.1 → data dict consumed by build_lp_pdf().

    Maths-specific shape (per LP Constitution v2.1):
      result.lesson_plan = {
        chapter_number, chapter_title, core_cg, core_competencies[],
        adjunct_competencies[], periods_allocated, dissolution_test,
        periods: [ <maths_period>, ... ]
      }
      <maths_period> = {
        period_number, period_duration_minutes, textbook_segments[],
        section_goal, activity_title, pedagogical_method,
        textbook_items_in_class[{id,type,source_section,book_ref}],
        homework[], phases[{minutes (range str), description}],
        materials[], teacher_notes
      }

    Competencies are loaded from the chapter mapping JSON + framework
    descriptions file (same pattern as Science), NOT from LP output, so
    they always match the authoritative mapping.

    Period dict includes pedagogical_approach and teacher_notes so
    period_card_maths() can render them directly.
    """
    import json as _json

    lp = (j.get("result") or {}).get("lesson_plan") or {}

    # ── Resolve paths ─────────────────────────────────────────────────────────
    _grade_map = {
        "Grade I":    "i",    "Grade II":   "ii",   "Grade III": "iii",
        "Grade IV":   "iv",   "Grade V":    "v",    "Grade VI":  "vi",
        "Grade VII":  "vii",  "Grade VIII": "viii",
        "Grade IX":   "ix",   "Grade X":    "x",
    }
    _stage_map = {
        "i": "primary", "ii": "primary", "iii": "primary",
        "iv": "primary", "v": "primary",
        "vi": "middle",  "vii": "middle", "viii": "middle",
        "ix": "secondary", "x": "secondary",
    }
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _raw_grade    = j.get("grade", "")
    _grade_folder = _grade_map.get(_raw_grade, _raw_grade.lower().replace("grade ", ""))
    _stage        = _stage_map.get(_grade_folder, "middle")
    _ch_num       = j.get("chapter_number", 0)

    # ── Chapter-level competencies: load from mapping + descriptions (like Science) ──
    # Step 1: c_codes from per-chapter mapping JSON
    _ch_map_path = os.path.join(
        _project_root, "mirror", "chapters", "mathematics", _grade_folder,
        "mappings", f"ch_{_ch_num:02d}_mapping.json",
    )
    _c_codes = []
    try:
        _ch_map = _json.load(open(_ch_map_path, encoding="utf-8"))
        for entry in (_ch_map.get("core_competencies") or []) + (_ch_map.get("adjunct_competencies") or []):
            code = entry.get("c_code", "")
            if code and code not in _c_codes:
                _c_codes.append(code)
    except Exception:
        pass   # mapping file not yet generated — fall back below

    # Step 2: competency descriptions from framework JSON
    _comp_desc_path = os.path.join(
        _project_root, "mirror", "framework", "mathematics", _stage,
        f"competency_descriptions_{_stage}.json",
    )
    _comp_descs: dict = {}
    try:
        _raw = _json.load(open(_comp_desc_path, encoding="utf-8"))
        # Maths framework uses {curricular_goals: {CG-n: {competency_codes: {C-n.m: text}}}}
        if "curricular_goals" in _raw:
            cg_val = _raw["curricular_goals"]
            if isinstance(cg_val, dict):
                for _cg in cg_val.values():
                    for code, desc in (_cg.get("competency_codes") or {}).items():
                        _comp_descs[code] = desc
            elif isinstance(cg_val, list):
                for _cg in cg_val:
                    for _comp in (_cg.get("competencies") or []):
                        _comp_descs[_comp.get("code", "")] = _comp.get("description", "")
        else:
            _comp_descs = _raw
    except Exception:
        pass

    # Build competency tuples; fall back to LP output if mapping file missing
    if _c_codes:
        competencies = [(code, _comp_descs.get(code, "")) for code in _c_codes]
    else:
        # Fallback: read from LP output (original behaviour)
        competencies = []
        seen = set()
        for c in (lp.get("core_competencies") or []) + (lp.get("adjunct_competencies") or []):
            if not isinstance(c, dict):
                continue
            code = c.get("c_code", "")
            if code and code not in seen:
                competencies.append((code, _comp_descs.get(code, "") or c.get("competency_text", "")))
                seen.add(code)

    # ── Periods ───────────────────────────────────────────────────────────────
    periods = []
    for p in lp.get("periods") or []:
        # Anchor display: §-locators joined
        _segs = p.get("textbook_segments") or []
        anchor = ", ".join(_segs) if isinstance(_segs, list) else str(_segs)

        # Phases → time_breakdown (minutes is already a range string in v2.1)
        time_breakdown = []
        for ph in (p.get("phases") or []):
            time_breakdown.append((
                str(ph.get("minutes", "")),
                ph.get("description", ""),
            ))

        # Materials list → joined string only (no "Items used:" appended here;
        # that prefix was moved to Teacher Notes / removed per design update).
        raw_mat = p.get("materials") or []
        if isinstance(raw_mat, list):
            mat_str = ", ".join(str(m) for m in raw_mat if m)
        else:
            mat_str = str(raw_mat) if raw_mat else ""

        periods.append({
            "num":                 p.get("period_number"),
            "duration":            p.get("period_duration_minutes"),
            "activity_name":       p.get("activity_title", ""),
            "anchored_section":    anchor,
            "time_breakdown":      time_breakdown,
            "materials":           mat_str,
            "learning_outcome":    "",   # not used for Maths (period_card_maths ignores it)
            "pedagogical_approach": p.get("pedagogical_method", ""),
            "teacher_notes":       p.get("teacher_notes", ""),
        })

    return {
        "chapter_num":   j["chapter_number"],
        "chapter_title": j["chapter_title"],
        "grade":         str(j["grade"]).replace("Grade ", ""),
        "subject":       j["subject"],
        "date":          date_str,
        "weight":        weight,
        "competencies":  competencies,
        "periods":       periods,
    }


def build_lp_pdf_bytes(j: dict) -> bytes:
    """
    Convenience function for Streamlit: takes the LPA JSON dict,
    returns PDF as bytes (for st.download_button).
    """
    import tempfile
    data = json_to_lp_data(j)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp_path = f.name
    build_lp_pdf(tmp_path, data)
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(tmp_path)
    return pdf_bytes


# ──────────────────────────────────────────────────────────────────────────────
# Sample data
# ──────────────────────────────────────────────────────────────────────────────
SAMPLE = {
    "chapter_num":   10,
    "chapter_title": "The Constitution of India — An Introduction",
    "grade":         "VII",
    "subject":       "Social Science",
    "date":          "27 March 2026",
    "weight":        10,
    "competencies": [
        ("C-8.1", "Understands the need for a constitution for any country and the ideas and ideals of the Indian national movement enshrined in it as well as those drawn from its civilisational heritage."),
        ("C-3.1", "Analyses how social, political and economic changes occur over time and how they shape the present."),
        ("C-5.2", "Explains the structures and functions of democratic institutions and the rights and duties of citizens."),
    ],
    "periods": [
        {
            "num": 1, "duration": 40,
            "activity_name":    "What Is a Constitution and Why Do We Need One?",
            "anchored_section": "What Is a Constitution? / Why Do We Need a Constitution?",
            "time_breakdown": [
                ("0-5",   "Teacher presents a brief scenario: two teams in a school sports competition disagree on a rule — there is no official rulebook. Ask students: How would you resolve this? Take three or four quick responses."),
                ("5-12",  "Students read silently the sections 'What Is a Constitution?' and 'Why Do We Need a Constitution?' in the textbook, each marking one sentence that best answers: What does a constitution actually do?"),
                ("12-22", "Small group task (groups of 3-4): Each group receives a scenario card describing a governance dispute. Groups identify which constitutional function would resolve their dispute and explain why, in two sentences."),
                ("22-32", "Whole-class share-out: Each group presents their scenario and function match. Teacher facilitates probing. Students record the four constitutional functions on the board collaboratively."),
                ("32-40", "Exit card: Each student writes one sentence completing — 'A constitution is needed because without it...' — anchored to their group's scenario."),
            ],
            "materials":       "Textbook, Board and chalk/marker, Strips of paper with scenario cards describing disputes in a classroom without rules",
            "learning_outcome": "Students will be able to match a described governance or rights dispute to the specific constitutional function that addresses it, and explain the connection in their own words.",
        },
        {
            "num": 2, "duration": 40,
            "activity_name":    "Preamble: Values, Ideals and the National Movement",
            "anchored_section": "The Preamble / Ideas of the National Movement",
            "time_breakdown": [
                ("0-8",   "Teacher reads the Preamble aloud once; students follow in the textbook. Each student circles two words or phrases they find interesting or surprising."),
                ("8-18",  "Paired discussion: Share your two circled terms with your partner. Together, connect one term to an event from India's freedom struggle. Groups of four share their connection."),
                ("18-30", "Class activity: On the board write the six key Preamble values. Students match each to an episode from the national movement using textbook evidence."),
                ("30-38", "Teacher-led discussion: Why were these specific values chosen? What does 'We, the People' signal about who holds power?"),
                ("38-40", "Exit card: 'The Preamble reflects the national movement because...'"),
            ],
            "materials":       "Textbook, Printed copy of the Preamble (one per student), Sticky notes or chalk",
            "learning_outcome": "Students will be able to identify at least three key values in the Preamble and explain how each is rooted in ideas or events from India's national movement.",
        },
        {
            "num": 3, "duration": 40,
            "activity_name":    "Fundamental Rights and Directive Principles",
            "anchored_section": "Fundamental Rights / Directive Principles of State Policy",
            "time_breakdown": [
                ("0-5",   "Quick review: Teacher asks three oral questions on the Preamble from the previous period. Students respond without opening books."),
                ("5-20",  "Jigsaw reading: Class split into four expert groups, each reading one cluster — Right to Equality, Right to Freedom, Right Against Exploitation, Directive Principles — and preparing a 90-second summary."),
                ("20-32", "Expert groups share summaries. Class fills a four-column chart: Right / What it protects / Who it protects / One real-life situation where it matters."),
                ("32-38", "Discussion: Fundamental Rights are justiciable; Directive Principles are not. Why might the constitution make this distinction?"),
                ("38-40", "Exit card: Name one Fundamental Right and one situation where it could be violated."),
            ],
            "materials":       "Textbook, Four-column chart template (printed or drawn on board), Markers",
            "learning_outcome": "Students will be able to distinguish between Fundamental Rights and Directive Principles, and apply at least one right to a real-life situation they can describe in their own words.",
        },
    ],
}

if __name__ == "__main__":
    build_lp_pdf("/home/claude/aruvi_lp_v3.pdf", SAMPLE)
