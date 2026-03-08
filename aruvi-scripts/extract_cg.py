"""
extract_cg.py
Extracts the Curricular Goals and C-codes from the NCF CG document PDF.
Returns a structured list of CGs with their competency sub-codes and
cognitive demand descriptions — the sole framework input to the mapping prompt.
"""

import sys
import json
import re
import pdfplumber


def none_ratio(table):
    if not table or not table[0]:
        return 1.0
    total = sum(len(row) for row in table)
    nones = sum(1 for row in table for cell in row if cell is None)
    return nones / total if total > 0 else 1.0


def clean_cell(cell):
    if cell is None:
        return ""
    return re.sub(r'\s+', ' ', cell.strip())


def extract_cg(pdf_path: str) -> dict:
    """
    Extract Curricular Goals and C-codes from the CG PDF.

    Returns:
        {
            "curricular_goals": [
                {
                    "cg_code": "CG-1",
                    "cg_title": "...",
                    "competencies": [
                        {
                            "c_code": "C-1.1",
                            "description": "...",
                            "cognitive_demand": "..."
                        }
                    ]
                }
            ],
            "raw_text": str   (full extracted text, for fallback)
        }
    """
    all_text_parts = []
    cg_records = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text_parts.append(text)

            tables = page.extract_tables()
            for table in tables:
                if none_ratio(table) >= 0.5:
                    continue
                # Parse CG tables: look for rows containing C-code patterns
                for row in table:
                    cleaned = [clean_cell(c) for c in row]
                    row_text = " | ".join(c for c in cleaned if c)
                    # Detect C-code rows: e.g. "C-1.1", "C-2.3"
                    c_code_match = re.search(r'C-(\d+)\.(\d+)', row_text)
                    if c_code_match:
                        all_text_parts.append(f"[TABLE ROW] {row_text}")

    raw_text = "\n".join(all_text_parts)

    # Parse CGs from raw text using regex patterns
    # Pattern: CG-N followed by title, then C-N.N entries
    cg_pattern = re.compile(
        r'(CG-\d+)[:\s]+(.+?)(?=CG-\d+|$)',
        re.DOTALL
    )
    c_code_pattern = re.compile(
        r'(C-\d+\.\d+)[:\s]+(.+?)(?=C-\d+\.\d+|CG-\d+|$)',
        re.DOTALL
    )

    for cg_match in cg_pattern.finditer(raw_text):
        cg_code = cg_match.group(1).strip()
        cg_block = cg_match.group(2).strip()

        # Extract CG title (first line of block)
        cg_lines = [l.strip() for l in cg_block.split('\n') if l.strip()]
        cg_title = cg_lines[0] if cg_lines else ""

        # Extract competencies within this CG block
        competencies = []
        for c_match in c_code_pattern.finditer(cg_block):
            c_code = c_match.group(1).strip()
            c_desc_raw = c_match.group(2).strip()
            # Clean up multi-line descriptions
            c_desc = re.sub(r'\s+', ' ', c_desc_raw.split('\n')[0]).strip()
            # Try to detect cognitive demand verb from description
            demand_verbs = ['analyse', 'analyze', 'evaluate', 'explain', 'describe',
                           'identify', 'compare', 'interpret', 'construct', 'apply',
                           'examine', 'discuss', 'argue', 'justify', 'locate']
            cognitive_demand = ""
            for verb in demand_verbs:
                if verb in c_desc.lower():
                    cognitive_demand = verb
                    break

            competencies.append({
                "c_code": c_code,
                "description": c_desc[:300],  # cap at 300 chars
                "cognitive_demand": cognitive_demand
            })

        if cg_code and competencies:
            cg_records.append({
                "cg_code": cg_code,
                "cg_title": cg_title[:150],
                "competencies": competencies
            })

    return {
        "curricular_goals": cg_records,
        "cg_count": len(cg_records),
        "c_code_count": sum(len(cg["competencies"]) for cg in cg_records),
        "raw_text": raw_text
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_cg.py <cg_pdf_path> [--json]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_json = "--json" in sys.argv

    result = extract_cg(pdf_path)

    if output_json:
        # Don't dump raw_text in JSON mode — too verbose
        output = {k: v for k, v in result.items() if k != "raw_text"}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"CGs found      : {result['cg_count']}")
        print(f"C-codes found  : {result['c_code_count']}")
        print("\nCurricular Goals:")
        for cg in result["curricular_goals"]:
            print(f"\n  {cg['cg_code']}: {cg['cg_title']}")
            for c in cg["competencies"]:
                print(f"    {c['c_code']}: {c['description'][:80]}...")
