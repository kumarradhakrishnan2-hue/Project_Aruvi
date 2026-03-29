"""
extract_cg.py
Extracts the Curricular Goals and C-codes from the pre-extracted CG mirror .txt.
Returns a structured list of CGs with their competency sub-codes and
cognitive demand descriptions — the sole framework input to the mapping prompt.

txt_path is provided by config_resolver.resolve_paths() as paths["cg_text_path"],
which always points to:
  mirror/framework/{subject_group}/{stage}/cg_{stage}_{subject_group}.txt

No runtime PDF extraction — the mirror .txt is the source of truth.
"""

import sys
import json
import re
from pathlib import Path


def extract_cg(txt_path: str) -> dict:
    """
    Extract Curricular Goals and C-codes from the pre-extracted mirror .txt.

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
            "cg_count": int,
            "c_code_count": int,
            "raw_text": str   (full text, for fallback)
        }
    """
    raw_text = Path(txt_path).read_text(encoding="utf-8")

    cg_records = []

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
        print("Usage: python extract_cg.py <cg_txt_path> [--json]")
        sys.exit(1)

    txt_path = sys.argv[1]
    output_json = "--json" in sys.argv

    result = extract_cg(txt_path)

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
