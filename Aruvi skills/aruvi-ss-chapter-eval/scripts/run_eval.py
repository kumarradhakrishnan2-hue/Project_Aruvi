#!/usr/bin/env python3
"""
run_eval.py — Aruvi Chapter Mapping Evaluator
Subject Group: Social Sciences

Full evaluation pipeline in one script:
1. Reads chapter mapping JSON + prior learnings
2. Calls Claude API — produces RAG findings
3. Displays findings in clean numbered rows
4. Asks: which row numbers do you accept?
5. Calls stamp_eval.py internally with your decision
6. Done — mapping JSON stamped, learning entry written

Usage:
    python run_eval.py --subject social_sciences --grade vii --chapter 10
    python run_eval.py --subject social_sciences --grade vii --chapter 10 --mode rubberstamp
    python run_eval.py --subject social_sciences --grade vii --chapter 10 --dry-run
"""

import argparse
import json
import re
import sys
import glob
import subprocess
from datetime import datetime
from pathlib import Path
import anthropic

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def find_project_root():
    search_paths = [
        Path("mnt/data"),
        Path("/mnt/data"),
        Path.cwd(),
        Path.cwd().parent,
    ]
    for base in search_paths:
        if (base / "aruvi_config.json").exists():
            return base
    raise FileNotFoundError(
        "aruvi_config.json not found. Confirm mnt/data/ maps to project root."
    )


def resolve_paths(root: Path, subject: str, grade: str, chapter_num: int):
    grade_dir = root / "mirror" / "chapters" / subject / f"grade_{grade}"
    skill_dir = Path(__file__).parent.parent
    return {
        "mapping":       grade_dir / "mappings" / f"ch_{chapter_num:02d}_mapping.json",
        "learnings_dir": grade_dir / "evaluation_learnings",
        "framework":     skill_dir / "references" / "eval_framework_social_sciences.md",
        "stamp_script":  Path(__file__).parent / "stamp_eval.py",
    }


# ---------------------------------------------------------------------------
# Prior learnings loader
# ---------------------------------------------------------------------------

def load_prior_learnings(learnings_dir: Path, current_chapter: int) -> str:
    if not learnings_dir.exists():
        return "PRIOR EVALUATION LEARNINGS:\nNone — first evaluation for this subject/grade.\n"

    files = sorted(glob.glob(str(learnings_dir / "ch_*_eval_learning.json")))
    entries = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("chapter_number") != current_chapter:
            entries.append(data)

    if not entries:
        return "PRIOR EVALUATION LEARNINGS:\nNone — first evaluation for this subject/grade.\n"

    lines = ["PRIOR EVALUATION LEARNINGS:"]
    for idx, entry in enumerate(entries, 1):
        ch = entry.get("chapter_number", "?")
        title = entry.get("chapter_title", "")
        sub_disc = entry.get("chapter_sub_discipline", "unknown")
        outcome = entry.get("outcome", "")
        red = [f.get("c_code") for f in entry.get("red_flags", [])]
        orange = [f.get("c_code") for f in entry.get("orange_flags", [])]
        tags = entry.get("pattern_tags", [])

        finding_parts = []
        if red:
            finding_parts.append(f"red: {', '.join(red)}")
        if orange:
            finding_parts.append(f"orange: {', '.join(orange)}")
        finding_str = "; ".join(finding_parts) if finding_parts else "no flags"
        tag_str = ", ".join(tags) if tags else "none"

        lines.append(
            f"[{idx}] Ch {ch} · {title} · {sub_disc}\n"
            f"  tags: [{tag_str}] | findings: {finding_str} | outcome: {outcome}"
        )

    lines.append(
        "\nCheck whether any pattern_tag from the above applies to the current "
        "chapter. If a pattern seen before appears again, note it explicitly."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_system_prompt(framework_path: Path) -> str:
    framework_text = framework_path.read_text(encoding="utf-8")
    return (
        "You are an evaluator for the Aruvi chapter mapping system.\n\n"
        "Your task is a justification audit of one Social Sciences chapter mapping JSON. "
        "Verify that each competency assignment is supported by a justification that names "
        "the correct architectural container, states a transformation the section "
        "demonstrably demands, and corresponds that transformation to the C-code.\n\n"
        "You DO NOT re-execute the mapping. You DO NOT scan the chapter summary for "
        "competency evidence independently. The C-code is consulted only to verify that "
        "the transformation named in the justification corresponds to what it defines.\n\n"
        "CRITICAL OUTPUT REQUIREMENT: Your response must end with a JSON block "
        "between the markers <<<JSON_START>>> and <<<JSON_END>>>. "
        "This block is machine-parsed — follow the schema exactly.\n\n"
        "--- EVALUATION FRAMEWORK ---\n\n"
        f"{framework_text}"
    )


def build_user_prompt(mapping_json: dict, prior_learnings_block: str) -> str:
    mapping_str = json.dumps(mapping_json, indent=2, ensure_ascii=False)

    return f"""{prior_learnings_block}

CHAPTER MAPPING TO EVALUATE:
{mapping_str}

EVALUATION INSTRUCTION:

Step 1 — Pre-checks (P1-P5): Run all five mechanically.

Step 2 — Chapter-level (Rule 8, Rule 9): Check both.

Step 3 — Competency-level audit: For each primary entry apply rules for its
weight (W3: R2+R3+R4 / W2: R2+R3+R5 / W1: R2+R3+R6). For each incidental
entry apply R7. Rate GREEN / ORANGE / RED with rules cited. For ORANGE and
RED state a specific recommended correction.

Step 4 — Pattern tags: Tag each ORANGE/RED finding using only the controlled
vocabulary. Note prior learning matches. If a tag appears 3+ times add an
evaluator_note.

CONTROLLED PATTERN TAG VOCABULARY:
- dissolution_test_misread
- surface_match_accepted
- cross_subdiscipline_w3_violation
- incidental_promoted_incorrectly
- primary_demoted_incorrectly
- justification_floats
- tie_break_not_applied
- weight_arithmetic_error
- cg_mismatch
- container_named_imprecisely

Step 5 — Write the human-readable findings section, then the JSON block.

OUTPUT FORMAT (follow exactly):

--- FINDINGS ---

PRE-CHECKS: P1:[PASS/FAIL] P2:[PASS/FAIL] P3:[PASS/FAIL] P4:[PASS/FAIL] P5:[PASS/FAIL]
[If any FAIL: which field and what the correct value should be]

CHAPTER-LEVEL:
Rule 8: [PASS/VIOLATION] - primary sub-discipline: [name]
Rule 9: [PASS/VIOLATION/NOT APPLICABLE]

COMPETENCY AUDIT:
[For each GREEN entry - one line only:]
[C-code] W[n] - GREEN

[For each ORANGE or RED entry:]
[C-code] W[n] - [ORANGE/RED] ([rules cited])
  What was found: [one clear sentence describing the specific problem]
  Suggested change: [field] - [specific correction]
  Pattern tag(s): [tags]

INCIDENTAL:
[For each incidental entry - one line:]
[C-code] - [GREEN: incidental correct / RED: has structural element, move to primary]

PRIOR LEARNING MATCHES: [tag: Ch N (C-code) / None]
[EVALUATOR NOTE: one sentence if tag appears 3+ times]

SUMMARY:
Red flags: [n] - [C-codes or none]
Orange flags: [n] - [C-codes or none]
Structural errors: [n] - [P-checks or none]

--- END FINDINGS ---

<<<JSON_START>>>
{{
  "sub_discipline": "[geography/history/political_science/economics]",
  "structural_errors": [],
  "evaluator_note": "",
  "prior_pattern_matches": [],
  "suggested_changes": [
    {{
      "c_code": "C-x.x",
      "rag": "RED or ORANGE",
      "rule_cited": "R4",
      "what_was_found": "one sentence describing the problem",
      "pattern_tags": ["tag1"],
      "amendment": {{
        "field": "weight or justification or move_to_incidental or move_to_primary",
        "from": "current value or null",
        "to": "corrected value or null",
        "weight": null,
        "justification": null
      }}
    }}
  ],
  "green_entries": ["C-x.x", "C-y.y"],
  "incidental_green": ["C-x.x"],
  "incidental_red": []
}}
<<<JSON_END>>>
"""


# ---------------------------------------------------------------------------
# Parse the machine-readable JSON block from API response
# ---------------------------------------------------------------------------

def parse_eval_json(raw_text: str) -> dict:
    match = re.search(r'<<<JSON_START>>>(.*?)<<<JSON_END>>>', raw_text, re.DOTALL)
    if not match:
        raise ValueError("Could not find <<<JSON_START>>>...<<<JSON_END>>> in API response.")
    return json.loads(match.group(1).strip())


def extract_findings_text(raw_text: str) -> str:
    match = re.search(r'--- FINDINGS ---(.*?)--- END FINDINGS ---', raw_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    json_start = raw_text.find("<<<JSON_START>>>")
    return raw_text[:json_start].strip() if json_start > 0 else raw_text.strip()


# ---------------------------------------------------------------------------
# Display and interactive consent
# ---------------------------------------------------------------------------

def display_findings(chapter_title: str, findings_text: str, suggested_changes: list, mode: str):
    print(f"\n{'='*65}")
    print(f"EVALUATION FINDINGS — {chapter_title}")
    if mode == "rubberstamp":
        print("Mode: RUBBERSTAMP — existing mapping is finalised")
    print(f"{'='*65}")
    print(findings_text)

    if not suggested_changes:
        print("\nNo changes suggested. All competency assignments pass.")
        return

    print(f"\n{'='*65}")
    print("SUGGESTED CHANGES")
    print(f"{'='*65}")
    for idx, change in enumerate(suggested_changes, 1):
        rag      = change.get("rag", "")
        c_code   = change.get("c_code", "")
        what     = change.get("what_was_found", "")
        amendment = change.get("amendment", {})
        field    = amendment.get("field", "")
        from_val = amendment.get("from")
        to_val   = amendment.get("to")
        tags     = ", ".join(change.get("pattern_tags", []))

        if field == "weight":
            change_desc = f"Change weight {from_val} -> {to_val}"
        elif field == "move_to_incidental":
            change_desc = "Move from primary to incidental"
        elif field == "move_to_primary":
            change_desc = f"Move from incidental to primary (W{amendment.get('weight', 1)})"
        elif field == "justification":
            change_desc = "Rewrite justification"
        else:
            change_desc = f"{field}: {to_val}"

        print(f"\nRow {idx} | {rag} | {c_code}")
        print(f"  Found  : {what}")
        print(f"  Change : {change_desc}")
        print(f"  Tag(s) : {tags}")


def get_accepted_rows(suggested_changes: list, mode: str) -> list:
    if not suggested_changes:
        return []

    n = len(suggested_changes)
    row_nums = " ".join(str(i) for i in range(1, n + 1))

    print(f"\n{'='*65}")
    if mode == "rubberstamp":
        print("Default is to reject all and stamp existing mapping as-is.")
    print(f"Rows available: {row_nums}")
    print("Enter row numbers to ACCEPT (space-separated), or press Enter to reject all:")
    print(">>> ", end="", flush=True)

    try:
        user_input = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNo input. Rejecting all changes.")
        user_input = ""

    if not user_input:
        return []

    accepted = []
    for token in user_input.split():
        try:
            row = int(token)
            if 1 <= row <= n:
                accepted.append(row - 1)
            else:
                print(f"  Warning: Row {row} out of range — ignored.")
        except ValueError:
            print(f"  Warning: '{token}' is not a valid row number — ignored.")

    return accepted


# ---------------------------------------------------------------------------
# Build stamp_eval arguments and call it
# ---------------------------------------------------------------------------

def run_stamp(
    root: Path, subject: str, grade: str, chapter_num: int,
    eval_data: dict, accepted_indices: list, mode: str, stamp_script: Path,
):
    suggested = eval_data.get("suggested_changes", [])
    accepted_changes  = [suggested[i] for i in accepted_indices]

    # Amendments — only accepted changes
    amendments = []
    for change in accepted_changes:
        amendment = change.get("amendment", {})
        field  = amendment.get("field", "")
        c_code = change.get("c_code")
        entry  = {"field": field, "c_code": c_code}
        if field == "weight":
            entry["from"] = amendment.get("from")
            entry["to"]   = amendment.get("to")
        elif field == "justification":
            entry["to"] = amendment.get("to", "")
        elif field == "move_to_primary":
            entry["weight"]        = amendment.get("weight", 1)
            entry["justification"] = amendment.get("justification", "")
        amendments.append(entry)

    red_flags    = [c.get("c_code") for c in suggested if c.get("rag") == "RED"]
    orange_flags = [c.get("c_code") for c in suggested if c.get("rag") == "ORANGE"]
    findings     = {c.get("c_code"): c.get("what_was_found", "") for c in suggested}

    all_tags = []
    for change in suggested:
        for tag in change.get("pattern_tags", []):
            if tag not in all_tags:
                all_tags.append(tag)

    if not suggested:
        outcome = "Accept"
    elif accepted_changes:
        outcome = "Correct and accept"
    elif mode == "rubberstamp":
        outcome = "Reject changes and stamp"
    else:
        outcome = "Accept"

    args = [
        sys.executable, str(stamp_script),
        "--subject",        subject,
        "--grade",          grade,
        "--chapter",        str(chapter_num),
        "--outcome",        outcome,
        "--mode",           mode,
        "--sub-discipline", eval_data.get("sub_discipline", "unknown"),
        "--amendments",     json.dumps(amendments),
        "--red-flags",      json.dumps(red_flags),
        "--orange-flags",   json.dumps(orange_flags),
        "--findings",       json.dumps(findings),
        "--pattern-tags",   json.dumps(all_tags),
        "--prior-matches",  json.dumps(eval_data.get("prior_pattern_matches", [])),
        "--evaluator-note", eval_data.get("evaluator_note", ""),
    ]

    print(f"\nOutcome : {outcome}")
    print("Stamping...")
    result = subprocess.run(args)
    if result.returncode != 0:
        print("ERROR: stamp_eval.py failed.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def evaluate_chapter(root: Path, subject: str, grade: str, chapter_num: int,
                     dry_run: bool, mode: str):
    paths = resolve_paths(root, subject, grade, chapter_num)

    print(f"\n{'='*65}")
    print(f"Aruvi Evaluator — Social Sciences")
    print(f"Subject: {subject} | Grade: {grade} | Chapter: {chapter_num:02d} | Mode: {mode}")
    print(f"{'='*65}")

    if not paths["mapping"].exists():
        print(f"ERROR: Mapping not found: {paths['mapping']}")
        sys.exit(1)

    with open(paths["mapping"], encoding="utf-8") as f:
        mapping_json = json.load(f)

    chapter_title = mapping_json.get("chapter_title", "Unknown")
    print(f"Chapter : {chapter_title}")

    if "eval_record" in mapping_json:
        stamp = mapping_json["eval_record"].get("stamp", "")
        print(f"\nWARNING: Already evaluated — stamp: {stamp}")
        print("Proceeding will overwrite the existing eval_record.\n")

    prior_learnings = load_prior_learnings(paths["learnings_dir"], chapter_num)
    prior_count = prior_learnings.count("\n[")
    print(f"Prior learnings: {prior_count} chapter(s)")

    if dry_run:
        print(f"\n[DRY RUN] All paths verified. No API call made.")
        return

    if not paths["framework"].exists():
        print(f"ERROR: Framework not found: {paths['framework']}")
        sys.exit(1)

    system_prompt = build_system_prompt(paths["framework"])
    user_prompt   = build_user_prompt(mapping_json, prior_learnings)

    print("\nCalling Claude API...")
    client   = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw   = response.content[0].text
    usage = response.usage
    print(f"Done. Tokens — input: {usage.input_tokens} | output: {usage.output_tokens}")

    try:
        eval_data = parse_eval_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"\nERROR parsing evaluator JSON: {e}")
        print("Raw response:\n", raw)
        sys.exit(1)

    findings_text    = extract_findings_text(raw)
    suggested_changes = eval_data.get("suggested_changes", [])

    display_findings(chapter_title, findings_text, suggested_changes, mode)
    accepted_indices = get_accepted_rows(suggested_changes, mode)

    # Confirm summary
    print(f"\n{'='*65}")
    if not suggested_changes:
        print("No changes — stamping as-is.")
    elif accepted_indices:
        accepted_codes = [suggested_changes[i]["c_code"] for i in accepted_indices]
        rejected_codes = [suggested_changes[i]["c_code"] for i in range(len(suggested_changes))
                          if i not in accepted_indices]
        print(f"Accepted : {', '.join(accepted_codes)}")
        if rejected_codes:
            print(f"Rejected : {', '.join(rejected_codes)}")
    else:
        print("All changes rejected — stamping existing mapping as-is.")

    run_stamp(
        root=root, subject=subject, grade=grade, chapter_num=chapter_num,
        eval_data=eval_data, accepted_indices=accepted_indices,
        mode=mode, stamp_script=paths["stamp_script"],
    )


def main():
    parser = argparse.ArgumentParser(description="Aruvi SS Chapter Mapping Evaluator")
    parser.add_argument("--subject",  required=True)
    parser.add_argument("--grade",    required=True)
    parser.add_argument("--chapter",  type=int, help="Single chapter number")
    parser.add_argument("--chapters", type=int, nargs="+", help="Multiple chapter numbers")
    parser.add_argument("--mode",     default="evaluate_and_stamp",
                        choices=["evaluate_and_stamp", "rubberstamp"])
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    if not args.chapter and not args.chapters:
        print("ERROR: Specify --chapter N or --chapters N1 N2 ...")
        sys.exit(1)

    chapters = [args.chapter] if args.chapter else args.chapters
    root     = find_project_root()

    for ch in chapters:
        evaluate_chapter(root, args.subject, args.grade, ch, args.dry_run, args.mode)
        if len(chapters) > 1:
            print(f"\n--- Chapter {ch:02d} complete ---\n")


if __name__ == "__main__":
    main()
