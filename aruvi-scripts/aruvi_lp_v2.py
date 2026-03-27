"""
Aruvi Lesson Plan PDF  — v2
Changes from v1:
  1. Period pill: same font/bg as activity rows (no dark pill)
  2. Anchored section prefixed with "Section:" in normal black
  3. Materials: thin-border row, same bg/fg as time rows, 'Material' bold, no amber tint
  4. Anchored section: normal weight, black
  5. Meta strip: label row ABOVE value row, label in black
  6. LO handoff removed
  7. "Competencies targeted" table added below meta strip (C no. | Competency text)
  8. Learning outcome: plain white bg, italic, with a { brace accent on the left
"""

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

def make_styles():
    s = {}
    def st(name, **kw):
        s[name] = ParagraphStyle(name, **kw)
    st("base",        fontName="Helvetica",      fontSize=8.5,  leading=12, textColor=INK)
    st("mute",        fontName="Helvetica",      fontSize=6.5,  leading=9,  textColor=MUTE)
    st("micro",       fontName="Helvetica",      fontSize=5.5,  leading=8,  textColor=MUTE)
    st("brand_name",  fontName="Helvetica-Bold", fontSize=11,   leading=14, textColor=INK)
    st("hdr_right_t", fontName="Helvetica-Bold", fontSize=7.5,  leading=10, textColor=INK, alignment=TA_RIGHT)
    st("hdr_right_s", fontName="Helvetica",      fontSize=6,    leading=8,  textColor=MUTE,alignment=TA_RIGHT)
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
    st("lo_text",     fontName="Helvetica-Oblique", fontSize=7.5, leading=12, textColor=INK)
    # Competency table
    st("comp_hdr",    fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=INK)
    st("comp_code",   fontName="Helvetica-Bold", fontSize=7.5,  leading=11, textColor=BLUE_TAG, alignment=TA_CENTER)
    st("comp_text",   fontName="Helvetica",      fontSize=7.5,  leading=11, textColor=INK)
    # Section label
    st("section_lbl", fontName="Helvetica-Bold", fontSize=6.5,  leading=9,  textColor=MUTE,
       alignment=TA_CENTER, spaceBefore=4, spaceAfter=4, letterSpacing=1.5)
    # Footer
    st("footer",      fontName="Helvetica",      fontSize=5.5,  leading=8,  textColor=colors.HexColor("#bbbbbb"))
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
    Draws a left-side curly brace { then the italic LO text to its right.
    Plain white background (no fill).
    """
    BRACE_W = 10  # points
    PAD_L   = 4
    PAD_R   = 6
    PAD_V   = 6

    def __init__(self, text, avail_width):
        super().__init__()
        self._text   = text
        self._aw     = avail_width
        self._style  = ST["lo_text"]
        self._inner_w = avail_width - self.BRACE_W - self.PAD_L - self.PAD_R
        # pre-compute paragraph height
        from reportlab.platypus import Paragraph as _P
        p = _P(f"<i>{text}</i>", self._style)
        _, self._ph = p.wrap(self._inner_w, 9999)
        self._h = self._ph + 2 * self.PAD_V

    def wrap(self, aw, ah):
        return (self._aw, self._h)

    def draw(self):
        c = self.canv
        h = self._h
        bx = self.BRACE_W  # x where text starts

        # ── draw curly brace ─────────────────────────────────────────────────
        c.saveState()
        c.setStrokeColor(MUTE)
        c.setLineWidth(1.2)
        c.setLineCap(1)

        # We draw a simple { using three bezier arcs
        r  = 4          # corner radius
        mid_y = h / 2
        top_y = h - self.PAD_V
        bot_y = self.PAD_V
        tip_x = 2       # how far the tip of { protrudes left

        p = c.beginPath()
        # bottom arm
        p.moveTo(bx, bot_y)
        p.curveTo(bx, bot_y, bx - r, bot_y, bx - r, bot_y + r)
        p.lineTo(bx - r, mid_y - r)
        # bottom tip
        p.curveTo(bx - r, mid_y - r, bx - r, mid_y, bx - r - tip_x, mid_y)
        # top tip
        p.curveTo(bx - r - tip_x, mid_y, bx - r, mid_y, bx - r, mid_y + r)
        p.lineTo(bx - r, top_y - r)
        # top arm
        p.curveTo(bx - r, top_y - r, bx - r, top_y, bx, top_y)
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

    # Brand box
    bx = L_MAR; by = top_y - 3*mm
    c.setStrokeColor(INK); c.setLineWidth(1.2)
    c.rect(bx, by, 6.5*mm, 6.5*mm)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(INK)
    c.drawCentredString(bx + 3.25*mm, by + 1.8*mm, "A")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(bx + 8.5*mm, by + 3.5*mm, "ARUVI")
    c.setFont("Helvetica", 5.5); c.setFillColor(MUTE)
    c.drawString(bx + 8.5*mm, by + 0.8*mm, "NCF 2023 · Pedagogical Platform")

    rx = PAGE_W - R_MAR
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(INK)
    c.drawRightString(rx, by + 3.5*mm, doc_meta["doc_type"])
    c.setFont("Helvetica", 5.5); c.setFillColor(MUTE)
    c.drawRightString(rx, by + 0.8*mm, doc_meta["doc_sub"])

    rule_y = top_y - 11*mm
    c.setStrokeColor(INK); c.setLineWidth(1.8)
    c.line(L_MAR, rule_y, PAGE_W - R_MAR, rule_y)
    c.setStrokeColor(INK); c.setLineWidth(0.4)
    c.line(L_MAR, rule_y - 1*mm, PAGE_W - R_MAR, rule_y - 1*mm)

    fy = B_MAR - 4*mm
    c.setStrokeColor(HAIRLINE); c.setLineWidth(0.4)
    c.line(L_MAR, fy + 3.5*mm, PAGE_W - R_MAR, fy + 3.5*mm)
    c.setFont("Helvetica", 5.5); c.setFillColor(colors.HexColor("#bbbbbb"))
    c.drawString(L_MAR, fy + 1.2*mm, doc_meta["footer_left"])
    c.drawRightString(PAGE_W - R_MAR, fy + 1.2*mm, doc_meta["footer_right"])
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
        Paragraph("Chapter",    ST["meta_lbl"]),
        Paragraph("Title",      ST["meta_lbl"]),
        Paragraph("Weight",     ST["meta_lbl"]),
        Paragraph("Periods",    ST["meta_lbl"]),
        Paragraph("Total time", ST["meta_lbl"]),
        Paragraph("Date",       ST["meta_lbl"]),
    ]
    val_row = [
        Paragraph(f"Ch {chapter_num:02d}",  ST["meta_val"]),
        Paragraph(title,                    ST["meta_val"]),
        Paragraph(str(weight),              ST["meta_val"]),
        Paragraph(f"{periods} × 40-min",    ST["meta_val"]),
        Paragraph(f"{total_time} min",      ST["meta_val"]),
        Paragraph("",                       ST["meta_val"]),   # filled at runtime
    ]

    t = Table([lbl_row, val_row], colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), BG_META),
        ("BOX",          (0,0), (-1,-1), 0.5, HAIRLINE),
        ("INNERGRID",    (0,0), (-1,-1), 0.5, HAIRLINE),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,0),  4),
        ("BOTTOMPADDING",(0,0), (-1,0),  2),
        ("TOPPADDING",   (0,1), (-1,1),  2),
        ("BOTTOMPADDING",(0,1), (-1,1),  5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    return t


def meta_strip_full(chapter_num, title, weight, periods, total_time, date_str):
    """Version with date filled in."""
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * f for f in [0.09, 0.38, 0.09, 0.16, 0.14, 0.14]]

    lbl_row = [Paragraph(x, ST["meta_lbl"]) for x in
               ["Chapter", "Title", "Weight", "Periods", "Total time", "Date"]]
    val_row = [
        Paragraph(f"Ch {chapter_num:02d}",  ST["meta_val"]),
        Paragraph(title,                    ST["meta_val"]),
        Paragraph(str(weight),              ST["meta_val"]),
        Paragraph(f"{periods} × 40-min",    ST["meta_val"]),
        Paragraph(f"{total_time} min",      ST["meta_val"]),
        Paragraph(date_str,                 ST["meta_val"]),
    ]
    t = Table([lbl_row, val_row], colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), BG_META),
        ("BOX",          (0,0), (-1,-1), 0.5, HAIRLINE),
        ("INNERGRID",    (0,0), (-1,-1), 0.5, HAIRLINE),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,0),  4),
        ("BOTTOMPADDING",(0,0), (-1,0),  2),
        ("TOPPADDING",   (0,1), (-1,1),  2),
        ("BOTTOMPADDING",(0,1), (-1,1),  5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    return t


def competency_table(competencies):
    """
    Two-column table: C no. | Text of competency
    competencies = [("C-8.1", "Understands the need for a constitution..."), ...]
    """
    uw = PAGE_W - L_MAR - R_MAR
    col_ws = [uw * 0.12, uw * 0.88]

    hdr = [Paragraph("C No.", ST["comp_hdr"]), Paragraph("Text of competency", ST["comp_hdr"])]
    rows = [hdr]
    for code, text in competencies:
        rows.append([
            Paragraph(code, ST["comp_code"]),
            Paragraph(text, ST["comp_text"]),
        ])

    t = Table(rows, colWidths=col_ws)
    t.setStyle(TableStyle([
        ("BOX",          (0,0), (-1,-1), 0.5, HAIRLINE),
        ("INNERGRID",    (0,0), (-1,-1), 0.5, HAIRLINE),
        ("BACKGROUND",   (0,0), (-1,0),  BG_META),
        ("BACKGROUND",   (0,1), (-1,-1), colors.white),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW",    (0,0), (-1,-2), 0.3, ROW_LINE),
    ]))
    return t


def period_card(period_num, duration_min, activity_name, anchored_section,
                time_breakdown, materials, learning_outcome):
    uw = PAGE_W - L_MAR - R_MAR
    story = []

    # ── Period header row — same look as time rows ────────────────────────────
    # Col layout: [Period N label | duration | activity name | Section: ...]
    hdr_data = [[
        Paragraph(f"<b>Period {period_num}</b>", ST["period_lbl"]),
        Paragraph(f"{duration_min} min",         ST["period_time"]),
        Paragraph(f"<b>{activity_name}</b>",     ST["period_act"]),
        Paragraph(f"Section: {anchored_section}", ST["period_sec"]),
    ]]
    hdr_t = Table(hdr_data, colWidths=[uw * f for f in [0.13, 0.09, 0.40, 0.38]])
    hdr_t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), BG_META),
        ("LINEABOVE",    (0,0), (-1,-1), 1.0, INK),
        ("LINEBELOW",    (0,0), (-1,-1), 0.5, HAIRLINE),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(hdr_t)

    # ── Time breakdown rows ───────────────────────────────────────────────────
    tb_rows = []
    for span, desc in time_breakdown:
        tb_rows.append([
            Paragraph(span, ST["tb_time"]),
            Paragraph(desc, ST["tb_desc"]),
        ])
    if tb_rows:
        tb_t = Table(tb_rows, colWidths=[uw * 0.10, uw * 0.90])
        tb_t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), colors.white),
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (0,0),   8),
            ("LEFTPADDING",  (1,0), (1,-1),  6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW",    (0,0), (-1,-2), 0.3, ROW_LINE),
            ("LINEBELOW",    (0,-1),(-1,-1), 0.5, HAIRLINE),
        ]))
        story.append(tb_t)

    # ── Materials row (thin gap lines, same style as time rows) ──────────────
    mat_row = [[
        Paragraph("<b>Material</b>", ST["mat_label"]),
        Paragraph(materials,         ST["mat_text"]),
    ]]
    mat_t = Table(mat_row, colWidths=[uw * 0.10, uw * 0.90])
    mat_t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), colors.white),
        ("LINEABOVE",    (0,0), (-1,0),  0.5, HAIRLINE),
        ("LINEBELOW",    (0,0), (-1,-1), 0.5, HAIRLINE),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (0,0),   8),
        ("LEFTPADDING",  (1,0), (1,-1),  6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(mat_t)

    # ── Learning outcome — plain white bg, { brace, italic ───────────────────
    story.append(LOBox(learning_outcome, uw))
    story.append(Spacer(1, 4*mm))

    return KeepTogether(story)


# ──────────────────────────────────────────────────────────────────────────────
# Main build
# ──────────────────────────────────────────────────────────────────────────────
def build_lp_pdf(output_path, data):
    doc_meta = {
        "doc_type":    "Lesson Plan",
        "doc_sub":     f"Grade {data['grade']} · {data['subject']} · {data['date']}",
        "footer_left": f"Aruvi · Lesson Plan · Grade {data['grade']} · {data['subject']} · Ch {data['chapter_num']:02d}",
        "footer_right":"Page 1 of 1 · Confidential",
    }
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=L_MAR, rightMargin=R_MAR,
        topMargin=T_MAR + 14*mm,
        bottomMargin=B_MAR + 8*mm,
    )
    uw = PAGE_W - L_MAR - R_MAR
    story = []

    # LESSON PLAN label
    story.append(Paragraph("LESSON PLAN", ST["section_lbl"]))
    story.append(HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=4))

    # Meta strip
    story.append(meta_strip_full(
        data["chapter_num"], data["chapter_title"], data["weight"],
        len(data["periods"]),
        sum(p["duration"] for p in data["periods"]),
        data["date"],
    ))
    story.append(Spacer(1, 3*mm))

    # Competencies targeted
    story.append(Paragraph("COMPETENCIES TARGETED", ST["section_lbl"]))
    story.append(HLine(uw, thickness=0.4, color=HAIRLINE, sb=1, sa=3))
    story.append(competency_table(data["competencies"]))
    story.append(Spacer(1, 4*mm))

    # Period cards
    for p in data["periods"]:
        story.append(period_card(
            p["num"], p["duration"],
            p["activity_name"], p["anchored_section"],
            p["time_breakdown"], p["materials"], p["learning_outcome"],
        ))

    # Footnote
    story.append(Paragraph(
        "(1) Period plan designed per Aruvi Lesson Plan Constitution V1.2 "
        "· NCF 2023 Middle Stage pedagogy principles applied throughout.",
        ST["footer"]
    ))

    doc.build(
        story,
        onFirstPage=lambda c, d: on_page(c, d, doc_meta),
        onLaterPages=lambda c, d: on_page(c, d, doc_meta),
    )
    print(f"✓  {output_path}")


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
                ("0–5",   "Teacher presents a brief scenario: two teams in a school sports competition disagree on a rule — there is no official rulebook. Ask students: How would you resolve this? Take three or four quick responses."),
                ("5–12",  "Students read silently the sections 'What Is a Constitution?' and 'Why Do We Need a Constitution?' in the textbook, each marking one sentence that best answers: What does a constitution actually do?"),
                ("12–22", "Small group task (groups of 3–4): Each group receives a scenario card describing a governance dispute. Groups identify which constitutional function would resolve their dispute and explain why, in two sentences."),
                ("22–32", "Whole-class share-out: Each group presents their scenario and function match. Teacher facilitates probing. Students record the four constitutional functions on the board collaboratively."),
                ("32–40", "Exit card: Each student writes one sentence completing — 'A constitution is needed because without it...' — anchored to their group's scenario."),
            ],
            "materials":       "Textbook, Board and chalk/marker, Strips of paper with scenario cards describing disputes in a classroom without rules",
            "learning_outcome":"Students will be able to match a described governance or rights dispute to the specific constitutional function that addresses it, and explain the connection in their own words.",
        },
        {
            "num": 2, "duration": 40,
            "activity_name":    "Preamble: Values, Ideals and the National Movement",
            "anchored_section": "The Preamble; Ideas of the National Movement",
            "time_breakdown": [
                ("0–8",   "Teacher reads the Preamble aloud once; students follow in the textbook. Each student circles two words or phrases they find interesting or surprising."),
                ("8–18",  "Paired discussion: Share your two circled terms with your partner. Together, connect one term to an event from India's freedom struggle. Groups of four share their connection."),
                ("18–30", "Class activity: On the board write the six key Preamble values. Students match each to an episode from the national movement using textbook evidence."),
                ("30–38", "Teacher-led discussion: Why were these specific values chosen? What does 'We, the People' signal about who holds power?"),
                ("38–40", "Exit card: 'The Preamble reflects the national movement because...'"),
            ],
            "materials":       "Textbook, Printed copy of the Preamble (one per student), Sticky notes or chalk",
            "learning_outcome":"Students will be able to identify at least three key values in the Preamble and explain how each is rooted in ideas or events from India's national movement.",
        },
        {
            "num": 3, "duration": 40,
            "activity_name":    "Fundamental Rights and Directive Principles",
            "anchored_section": "Fundamental Rights; Directive Principles of State Policy",
            "time_breakdown": [
                ("0–5",   "Quick review: Teacher asks three oral questions on the Preamble from the previous period. Students respond without opening books."),
                ("5–20",  "Jigsaw reading: Class split into four expert groups, each reading one cluster — Right to Equality, Right to Freedom, Right Against Exploitation, Directive Principles — and preparing a 90-second summary."),
                ("20–32", "Expert groups share summaries. Class fills a four-column chart: Right / What it protects / Who it protects / One real-life situation where it matters."),
                ("32–38", "Discussion: Fundamental Rights are justiciable; Directive Principles are not. Why might the constitution make this distinction?"),
                ("38–40", "Exit card: Name one Fundamental Right and one situation where it could be violated."),
            ],
            "materials":       "Textbook, Four-column chart template (printed or drawn on board), Markers",
            "learning_outcome":"Students will be able to distinguish between Fundamental Rights and Directive Principles, and apply at least one right to a real-life situation they can describe in their own words.",
        },
    ],
}

if __name__ == "__main__":
    build_lp_pdf("/home/claude/aruvi_lp_v2.pdf", SAMPLE)
