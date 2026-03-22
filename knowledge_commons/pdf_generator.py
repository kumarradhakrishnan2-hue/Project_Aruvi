"""
Aruvi PDF Generator
Uses Playwright + headless Chromium to render HTML templates to PDF.
This approach guarantees pixel-perfect output regardless of Unicode content,
special characters, or complex layouts — no coordinate arithmetic needed.
Used for: Allocation Report, Lesson Plan, Assessment (same pattern for all three).
"""

import base64
import json
import tempfile
import os
from pathlib import Path
from datetime import date

def render_html_to_pdf(html_content: str) -> bytes:
    """
    Renders an HTML string to PDF bytes using Playwright headless Chromium.
    Returns raw PDF bytes suitable for st.download_button.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=False,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "14mm",
                "right": "14mm"
            }
        )
        browser.close()
    return pdf_bytes


def build_allocation_pdf(
    chapters_data: list,
    period_types: list,
    grade: str,
    subject: str,
    logo_path: str = None
) -> bytes:
    """
    Builds the Period Allocation Report PDF.
    chapters_data: list of dicts with chapter_number, chapter_title,
                   chapter_weight, primary (list of competency entries
                   each with c_code, description, justification, weight)
    period_types: list of dicts with mins and count
    grade, subject: strings for header
    logo_path: absolute path to aruvi_logo-transparent.png
    """

    # Encode logo as base64 if available
    logo_b64 = ""
    if logo_path and Path(logo_path).exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")

    sorted_types = sorted(period_types, key=lambda x: -x["mins"])
    total_periods = sum(pt["count"] for pt in sorted_types)
    total_mins = sum(pt["mins"] * pt["count"] for pt in sorted_types)
    total_hrs = total_mins // 60
    total_min_rem = total_mins % 60
    time_str = f"{total_hrs}h {total_min_rem}min" if total_min_rem else f"{total_hrs}h"
    total_weight = sum(ch.get("chapter_weight", 0) for ch in chapters_data)
    period_type_str = " · ".join(f"{pt['count']}×{pt['mins']}min" for pt in sorted_types)
    today = date.today().strftime("%d %B %Y")

    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width:32px;height:32px;object-fit:contain;">'
    else:
        logo_html = '<div style="width:32px;height:32px;border:2px solid #1a1917;display:flex;align-items:center;justify-content:center;font-family:Georgia,serif;font-size:11px;font-weight:700;">A</div>'

    # Build chapter blocks
    chapter_blocks = ""
    for ch in chapters_data:
        alloc = ch.get("_alloc", {})
        period_cells = " · ".join(
            f'{alloc.get(pt["mins"], 0)}×{pt["mins"]}min'
            for pt in sorted_types
        )
        total_ch_periods = alloc.get("total", 0)
        total_ch_mins = sum(
            alloc.get(pt["mins"], 0) * pt["mins"] for pt in sorted_types
        )

        comp_rows = ""
        for idx, comp in enumerate(ch.get("primary", []), 1):
            weight_val = comp.get("weight", 0)
            dots_html = ""
            for d in range(3):
                if d < weight_val:
                    dots_html += '<span class="dot filled"></span>'
                else:
                    dots_html += '<span class="dot empty"></span>'

            comp_rows += f"""
            <tr>
                <td class="seq">{idx}</td>
                <td class="code">{comp.get("c_code","")}</td>
                <td class="competency">{comp.get("description","")}</td>
                <td class="justification">{comp.get("justification","")}</td>
                <td class="weight-dots"><div class="dots">{dots_html}</div></td>
            </tr>"""

        chapter_blocks += f"""
        <div class="chapter-block">
            <div class="chapter-header">
                <span class="ch-num">Ch {str(ch["chapter_number"]).zfill(2)}</span>
                <span class="ch-title">{ch["chapter_title"]}</span>
                <span class="ch-alloc">{period_cells} · {total_ch_periods} periods · {total_ch_mins}min</span>
                <span class="ch-weight">Weight {ch.get("chapter_weight", 0)}</span>
            </div>
            <table class="comp-table">
                <thead>
                    <tr>
                        <th class="th-seq">#</th>
                        <th class="th-code">Code</th>
                        <th class="th-comp">Competency</th>
                        <th class="th-just">Justification</th>
                        <th class="th-wt">Weight</th>
                    </tr>
                </thead>
                <tbody>{comp_rows}</tbody>
            </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 8pt; color: #1a1917; background: white; }}

  .page-header {{ display: flex; justify-content: space-between; align-items: flex-end; padding-bottom: 6px; border-bottom: 2px solid #1a1917; margin-bottom: 3px; }}
  .brand {{ display: flex; align-items: center; gap: 8px; }}
  .brand-name {{ font-size: 13pt; font-weight: 700; font-family: Georgia, serif; color: #1a1917; }}
  .brand-sub {{ font-size: 6pt; color: #999; display: block; margin-top: 1px; }}
  .report-right {{ text-align: right; }}
  .report-title {{ font-size: 9pt; font-weight: 700; }}
  .report-sub {{ font-size: 6pt; color: #999; margin-top: 2px; }}
  .header-rule2 {{ border: none; border-top: 0.5px solid #1a1917; margin-bottom: 14px; }}

  .summary {{ display: flex; gap: 0; margin-bottom: 16px; border: 0.5px solid #ddd; }}
  .sum-cell {{ flex: 1; padding: 5px 8px; border-right: 0.5px solid #ddd; text-align: center; }}
  .sum-cell:last-child {{ border-right: none; }}
  .sum-val {{ font-size: 10pt; font-weight: 700; display: block; }}
  .sum-key {{ font-size: 5.5pt; color: #999; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 1px; display: block; }}

  .chapter-block {{ margin-bottom: 18px; page-break-inside: avoid; }}
  .chapter-header {{
    display: flex; align-items: baseline; gap: 6px;
    padding-bottom: 4px; border-bottom: 1.5px solid #1a1917;
    margin-bottom: 0;
  }}
  .ch-num {{ font-size: 6.5pt; color: #999; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; white-space: nowrap; }}
  .ch-title {{ font-size: 9.5pt; font-weight: 700; font-family: Georgia, serif; flex: 1; }}
  .ch-alloc {{
    font-size: 7pt; font-weight: 600; color: white;
    background: #1a1917; padding: 2px 7px; border-radius: 3px;
    white-space: nowrap;
  }}
  .ch-weight {{ font-size: 7pt; color: #888; white-space: nowrap; padding-left: 6px; }}

  .comp-table {{ width: 100%; border-collapse: collapse; }}
  .comp-table th {{
    font-size: 6pt; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #999;
    padding: 5px 6px; text-align: left;
    border-bottom: 0.5px solid #e0ddd8;
  }}
  .th-seq {{ width: 18px; }}
  .th-code {{ width: 38px; }}
  .th-comp {{ width: 34%; }}
  .th-just {{ text-align: left; }}
  .th-wt {{ width: 40px; text-align: center; }}

  .comp-table td {{
    padding: 6px 6px; vertical-align: top;
    border-bottom: 0.5px solid #f0ede9;
    font-size: 7pt; line-height: 1.5;
  }}
  .comp-table tr:last-child td {{ border-bottom: none; }}
  .seq {{ color: #bbb; font-size: 6.5pt; text-align: right; padding-right: 4px; }}
  .code {{ font-weight: 700; font-size: 7.5pt; white-space: nowrap; }}
  .competency {{ color: #2a2a2a; }}
  .justification {{ color: #666; font-style: italic; }}
  .weight-dots {{ text-align: center; vertical-align: middle; }}
  .dots {{ display: flex; gap: 3px; justify-content: center; align-items: center; padding-top: 2px; }}
  .dot {{ width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
  .dot.filled {{ background: #1a1917; }}
  .dot.empty {{ border: 1px solid #bbb; background: transparent; }}

  .footnotes {{ margin-top: 20px; padding-top: 8px; border-top: 0.5px solid #ddd; }}
  .fn {{ font-size: 6pt; color: #bbb; line-height: 1.6; margin-bottom: 3px; }}

  .page-footer {{
    position: fixed; bottom: 0; left: 14mm; right: 14mm;
    display: flex; justify-content: space-between;
    font-size: 6pt; color: #ccc;
    border-top: 0.5px solid #eee; padding-top: 4px;
    background: white;
  }}
</style>
</head>
<body>

<div class="page-header">
  <div class="brand">
    {logo_html}
    <div>
      <span class="brand-name">ARUVI</span>
      <span class="brand-sub">NCF 2023 · Pedagogical Platform</span>
    </div>
  </div>
  <div class="report-right">
    <div class="report-title">Period Allocation Report</div>
    <div class="report-sub">{grade} · {subject} · {today}</div>
  </div>
</div>
<hr class="header-rule2">

<div class="summary">
  <div class="sum-cell"><span class="sum-val">{len(chapters_data)}</span><span class="sum-key">Chapters</span></div>
  <div class="sum-cell"><span class="sum-val">{total_periods}</span><span class="sum-key">Periods</span></div>
  <div class="sum-cell"><span class="sum-val">{time_str}</span><span class="sum-key">Total time</span></div>
  <div class="sum-cell"><span class="sum-val">{period_type_str}</span><span class="sum-key">Period types</span></div>
  <div class="sum-cell"><span class="sum-val">{total_weight}</span><span class="sum-key">Sum of weights</span></div>
</div>

{chapter_blocks}

<div class="footnotes">
  <div class="fn">(1) Periods allocated using the Largest Remainder Method (LRM), weighted by chapter competency load (W3×3 + W2×2 + W1×1).</div>
  <div class="fn">(2) Budget: {total_periods} periods · {time_str} · {grade} · {subject}</div>
</div>

<div class="page-footer">
  <span>Aruvi · Period Allocation Report · {grade} · {subject}</span>
  <span>Confidential</span>
</div>

</body>
</html>"""

    return render_html_to_pdf(html)
