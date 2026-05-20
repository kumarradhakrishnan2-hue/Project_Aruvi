"""
Test which Devanagari font works with ReportLab TTFont.
Run on Mac: python3 aruvi-scripts/test_devanagari_font.py
"""
import os, sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4

DEVANAGARI_TEXT = "माता भूमि: पुत्रोऽहं पृथिव्या:"

candidates = [
    ("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc", 0, "DevanagariSangam"),
    ("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc", 1, "DevanagariSangamB"),
    ("/System/Library/Fonts/Supplemental/ITFDevanagari.ttc", 0, "ITFDevanagari"),
    ("/System/Library/Fonts/Supplemental/ITFDevanagari.ttc", 1, "ITFDevanagariB"),
]

OUT = "/tmp/devanagari_test.pdf"
doc = SimpleDocTemplate(OUT, pagesize=A4)
story = []

for path, idx, name in candidates:
    if not os.path.exists(path):
        print(f"MISSING: {path}")
        continue
    try:
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
        style = ParagraphStyle(name+"_style", fontName=name, fontSize=12, leading=18)
        story.append(Paragraph(f"Font: {name} (index {idx})", style))
        story.append(Paragraph(DEVANAGARI_TEXT, style))
        story.append(Spacer(1, 12))
        print(f"OK: {name} at index {idx}")
    except Exception as e:
        print(f"FAIL: {name} index {idx} — {e}")

if story:
    doc.build(story)
    print(f"\nPDF written to {OUT} — open it to check which font renders correctly.")
else:
    print("No fonts worked.")
