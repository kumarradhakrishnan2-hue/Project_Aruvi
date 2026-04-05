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
            print_background=True,
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
                   chapter_weight / effort_index + signal fields,
                   primary (list of competency entries with c_code,
                   description, justification, weight)
    period_types: list of dicts with mins and count
    grade, subject: strings for header
    logo_path: absolute path to aruvi_logo-transparent.png

    Subject-group switching
    -----------------------
    Science / Mathematics → effort_index drives allocation; chapter blocks
    show an effort-index breakdown table instead of the competency table.
    All other subjects → chapter_weight drives allocation; competency table
    is shown as before.
    Adding a new subject group: add its name to the is_science condition
    below and supply its own block-rendering logic inside build_chapter_block.
    """

    # ── Subject-group detection ────────────────────────────────────────────────
    is_science = subject in ("Science", "Mathematics")

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
    period_type_str = " · ".join(f"{pt['count']}×{pt['mins']}min" for pt in sorted_types)
    today = date.today().strftime("%d %B %Y")

    # Summary strip metric: weight for social sciences, effort index sum for science
    if is_science:
        summary_metric_val = sum(ch.get("effort_index", 0) for ch in chapters_data)
        summary_metric_key = "Sum of effort idx"
    else:
        summary_metric_val = sum(ch.get("chapter_weight", 0) for ch in chapters_data)
        summary_metric_key = "Sum of weights"

    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width:32px;height:32px;object-fit:contain;">'
    else:
        logo_html = '<div style="width:32px;height:32px;border:2px solid #1a1917;display:flex;align-items:center;justify-content:center;font-family:Georgia,serif;font-size:11px;font-weight:700;">A</div>'

    def _build_chapter_block_science(ch: dict, alloc: dict) -> str:
        """Chapter block for Science / Mathematics: C-code + justification lines,
        followed by a compact effort-index summary line. No weight column or label."""
        period_cells = " · ".join(
            f'{alloc.get(pt["mins"], 0)}&times;{pt["mins"]}min'
            for pt in sorted_types
        )
        total_ch_periods = alloc.get("total", 0)
        total_ch_mins = sum(alloc.get(pt["mins"], 0) * pt["mins"] for pt in sorted_types)
        ei  = ch.get("effort_index", 0) or 0
        cd  = ch.get("conceptual_demand", 0) or 0
        ac  = ch.get("activity_count", 0) or 0
        dc  = ch.get("demo_count", 0) or 0
        el  = ch.get("exec_load", 0) or 0

        # Build one line per C-code entry: bold code + normal justification text
        comp_lines_html = ""
        for comp in ch.get("primary", []):
            c_code = comp.get("c_code", "")
            justification = comp.get("justification", "") or comp.get("description", "")
            comp_lines_html += (
                f'<div style="margin-bottom:5px;font-size:7.5pt;line-height:1.55;">'
                f'<span style="font-weight:700;">{c_code}</span>'
                f'&nbsp;&nbsp;{justification}'
                f'</div>'
            )

        # Compact effort index breakdown line (small grey)
        if ei:
            ei_summary = (
                f'Effort index: {ei}&nbsp;&nbsp;'
                f'Conceptual demand: {cd}&nbsp;&nbsp;'
                f'Activities: {ac}&nbsp;&nbsp;'
                f'Demos: {dc}&nbsp;&nbsp;'
                f'Exec load: {el}'
            )
        else:
            ei_summary = 'Effort index: not yet computed'

        return (
            f'<div class="chapter-block">'
            f'<div class="chapter-header">'
            f'<span class="ch-num">Ch {str(ch["chapter_number"]).zfill(2)}</span>'
            f'<span class="ch-title">{ch["chapter_title"]}</span>'
            f'<span class="ch-alloc">{period_cells} &middot; {total_ch_periods} periods &middot; {total_ch_mins}min</span>'
            f'</div>'
            f'<div style="padding:6px 0 3px 0;">'
            f'{comp_lines_html}'
            f'<div style="font-size:7pt;color:rgb(120,120,120);margin-top:3px;">{ei_summary}</div>'
            f'</div>'
            f'<hr style="border:none;border-top:0.5px solid rgb(220,220,220);margin:6px 0 0 0;">'
            f'</div>'
        )

    def _build_chapter_block_social(ch: dict, alloc: dict) -> str:
        """Chapter block for Social Sciences / Languages: competency mapping table."""
        period_cells = " · ".join(
            f'{alloc.get(pt["mins"], 0)}×{pt["mins"]}min'
            for pt in sorted_types
        )
        total_ch_periods = alloc.get("total", 0)
        total_ch_mins = sum(alloc.get(pt["mins"], 0) * pt["mins"] for pt in sorted_types)
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
        return f"""
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

    # Build chapter blocks using the appropriate renderer
    chapter_blocks = ""
    for ch in chapters_data:
        alloc = ch.get("_alloc", {})
        if is_science:
            chapter_blocks += _build_chapter_block_science(ch, alloc)
        else:
            chapter_blocks += _build_chapter_block_social(ch, alloc)

    # Footnote wording switches on subject group
    if is_science:
        fn1_text = (
            "(1) Periods allocated using the Largest Remainder Method (LRM), "
            "weighted by chapter effort index "
            "(conceptual demand\u00d72 + student activities\u00d71 + teacher demos\u00d71.5 + exercise load\u00d72)."
        )
    else:
        fn1_text = (
            "(1) Periods allocated using the Largest Remainder Method (LRM), "
            "weighted by chapter competency load (W3\u00d73 + W2\u00d72 + W1\u00d71)."
        )

    # Explanatory paragraph (Science only) — appears after summary strip, before chapter blocks
    if is_science:
        explanatory_para = (
            '<p style="font-size:8pt;font-style:italic;color:rgb(100,100,100);'
            'margin:10px 0 14px 0;line-height:1.6;">'
            'About effort index: Each chapter&rsquo;s effort index is a composite of four signals '
            'read from the chapter content &mdash; conceptual demand of the exercise (&times;2), '
            'number of student-executed activities (&times;1), number of teacher demonstrations '
            '(&times;1.5), and exercise execution load (&times;2). Higher effort index = more '
            'classroom time needed. Periods are allocated proportionally across chapters using '
            'the Largest Remainder Method (LRM).'
            '</p>'
        )
    else:
        explanatory_para = ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @font-face {{
    font-family: 'DejaVu Sans';
    font-style: normal;
    font-weight: 400;
    src: url('file:///usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') format('truetype');
  }}
  @font-face {{
    font-family: 'DejaVu Sans';
    font-style: normal;
    font-weight: 700;
    src: url('file:///usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf') format('truetype');
  }}
  @font-face {{
    font-family: 'DejaVu Serif';
    font-style: normal;
    font-weight: 400;
    src: url('file:///usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf') format('truetype');
  }}
  @font-face {{
    font-family: 'DejaVu Serif';
    font-style: italic;
    font-weight: 400;
    src: url('file:///usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf') format('truetype');
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 8pt; color: #1a1917; background: white; }}

  .page-header {{ display: flex; justify-content: space-between; align-items: flex-end; padding-bottom: 6px; border-bottom: 2px solid #1a1917; margin-bottom: 3px; }}
  .brand {{ display: flex; align-items: center; gap: 8px; }}
  .brand-name {{ font-size: 13pt; font-weight: 700; font-family: Georgia, serif; color: #1a1917; }}
  .brand-sub {{ font-size: 6pt; color: #999; display: block; margin-top: 1px; }}
  .report-right {{ text-align: right; }}
  .report-title {{ font-size: 9pt; font-weight: 700; }}
  .report-sub {{ font-size: 6pt; color: #999; margin-top: 2px; }}
  .header-rule2 {{ height: 0; border: none; border-top: 0.5px solid #1a1917; margin: 3px 0 10px 0; }}

  /* ── Summary strip ── */
  .summary {{ display: flex; gap: 0; margin-bottom: 10px; border: 0.5px solid #ddd; }}
  .sum-cell {{ flex: 1; padding: 4px 8px; border-right: 0.5px solid #ddd; text-align: center; }}
  .sum-cell:last-child {{ border-right: none; }}
  .sum-val {{ font-size: 10pt; font-weight: 700; display: block; }}
  .sum-key {{ font-size: 5.5pt; color: #999; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 1px; display: block; }}

  /* ── Chapter block ── #4: tighter spacing between chapters */
  .chapter-block {{ margin-bottom: 12px; page-break-inside: avoid; }}
  .chapter-header {{
    display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap;
    padding-bottom: 3px; border-bottom: 1.5px solid #1a1917;
    margin-bottom: 0;
  }}
  .ch-num {{ font-size: 6.5pt; color: #aaa; font-weight: 500; white-space: nowrap; }}
  .ch-title {{ font-size: 8.5pt; font-weight: 700; font-family: 'DejaVu Serif', Georgia, serif; flex: 1; min-width: 0; word-break: break-word; }}
  .ch-alloc {{
    font-size: 6.5pt; font-weight: 600; color: white;
    background: #1a1917; padding: 2px 6px; border-radius: 3px;
    white-space: nowrap;
  }}
  .ch-weight {{ font-size: 6.5pt; color: #aaa; white-space: nowrap; padding-left: 6px; }}

  /* ── Competency table ── */
  .comp-table {{ width: 100%; border-collapse: collapse; }}
  .comp-table th {{
    font-size: 6pt; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; color: #bbb;
    padding: 4px 6px; text-align: left;
    border-bottom: 0.5px solid #e0ddd8;
  }}
  .th-seq {{ width: 16px; }}
  .th-code {{ width: 36px; }}
  .th-comp {{ width: 32%; }}
  .th-just {{ text-align: left; }}
  /* ── #3: explicit min-width prevents dots column from collapsing into justification */
  .th-wt {{ width: 42px; min-width: 42px; text-align: center; }}

  /* ── #4: reduce cell padding — was 6px, now 4px top/bottom */
  .comp-table tr {{ break-inside: avoid; page-break-inside: avoid; }}
  .comp-table td {{
    padding: 4px 6px; vertical-align: top;
    border-bottom: 0.5px solid #f0ede9;
    font-size: 7pt; line-height: 1.45;
  }}
  .comp-table tr:last-child td {{ border-bottom: none; }}
  .seq {{ color: #bbb; font-size: 6.5pt; text-align: right; padding-right: 4px; }}
  .code {{ font-weight: 700; font-size: 7.5pt; white-space: nowrap; }}
  .competency {{ color: #2a2a2a; }}
  .justification {{ color: #555; font-style: italic; font-family: 'DejaVu Serif', Georgia, serif; padding-right: 4px; }}
  /* ── #3: overflow:hidden + explicit width keeps dots inside their column */
  .weight-dots {{ width: 42px; min-width: 42px; text-align: center; vertical-align: middle; overflow: hidden; }}
  .dots {{ display: flex; gap: 3px; justify-content: center; align-items: center; padding-top: 3px; }}
  .dot {{ width: 5px; height: 5px; border-radius: 50%; display: inline-block; flex-shrink: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; color-adjust: exact; }}
  .dot.filled {{ background: #1a1917 !important; }}
  .dot.empty {{ border: 1px solid #ccc; background: transparent; }}

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
<div class="header-rule2"></div>

<div class="summary">
  <div class="sum-cell"><span class="sum-val">{len(chapters_data)}</span><span class="sum-key">Chapters</span></div>
  <div class="sum-cell"><span class="sum-val">{total_periods}</span><span class="sum-key">Periods</span></div>
  <div class="sum-cell"><span class="sum-val">{time_str}</span><span class="sum-key">Total time</span></div>
  <div class="sum-cell"><span class="sum-val">{period_type_str}</span><span class="sum-key">Period types</span></div>
  <div class="sum-cell"><span class="sum-val">{summary_metric_val}</span><span class="sum-key">{summary_metric_key}</span></div>
</div>

{explanatory_para}
{chapter_blocks}

<div class="footnotes">
  <div class="fn">{fn1_text}</div>
  <div class="fn">(2) Budget: {total_periods} periods · {time_str} · {grade} · {subject}</div>
</div>

<div class="page-footer">
  <span>Aruvi · Period Allocation Report · {grade} · {subject}</span>
  <span>Confidential</span>
</div>

</body>
</html>"""

    return render_html_to_pdf(html)
