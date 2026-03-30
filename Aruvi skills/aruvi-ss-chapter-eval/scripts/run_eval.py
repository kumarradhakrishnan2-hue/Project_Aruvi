#!/usr/bin/env python3
"""
run_eval.py — Aruvi Chapter Mapping Evaluator
Subject Group: Social Sciences

Reads a chapter mapping JSON, loads prior evaluation learnings for the
subject/grade, calls the Claude API with the evaluation framework as
system prompt, and prints structured findings to stdout.

Does NOT write any files. Stop after printing findings.
Kumar reads findings and decides. Then run stamp_eval.py.

Usage:
    python run_eval.py --subject social_sciences --grade vii --chapter 1
    python run_eval.py --subject social_sciences --grade vii --chapters 1 2 3
    python run_eval.py --subject social_sciences --grade vii --chapter 1 --dry-run
"""

import argparse
import json
import os
import sys
import glob
from datetime import datetime
from pathlib import Path
import anthropic

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def find_project_root():
    """Find project root by locating aruvi_config.json."""
    # In Cowork, project root is mnt/data/
    search_paths = [
        Path("mnt/data"),
        Path("/mnt/data"),
        Path.cwd(),
        Path.cwd().parent,
    ]
    for base in search_paths:
        config = base / "aruvi_config.json"
        if config.exists():
            return base
    raise FileNotFoundError(
        "aruvi_config.json not found. Confirm mnt/data/ maps to project root."
    )


def resolve_paths(root: Path, subject: str, grade: str, chapter_num: int):
    """Construct all paths needed for evaluation."""
    grade_dir = root / "mirror" / "chapters" / subject / f"grade_{grade}"
    mapping_path = grade_dir / "mappings" / f"ch_{chapter_num:02d}_mapping.json"
    learnings_dir = grade_dir / "evaluation_learnings"
    
    # Skill references (bundled with this skill)
    skill_dir = Path(__file__).parent.parent  # scripts/ -> skill root
    framework_path = skill_dir / "references" / "eval_framework_social_sciences.md"
    prompt_template_path = skill_dir / "references" / "eval_prompt_template.md"
    
    return {
        "mapping": mapping_path,
        "learnings_dir": learnings_dir,
        "framework": framework_path,
        "prompt_template": prompt_template_path,
        "grade_dir": grade_dir,
    }


# ---------------------------------------------------------------------------
# Prior learnings loader
# ---------------------------------------------------------------------------

def load_prior_learnings(learnings_dir: Path, current_chapter: int) -> str:
    """
    Load all ch_*_eval_learning.json files for this subject/grade,
    excluding the current chapter, and format as a numbered block.
    """
    if not learnings_dir.exists():
        return "PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:\nNone — this is the first evaluation for this subject/grade.\n"
    
    pattern = str(learnings_dir / "ch_*_eval_learning.json")
    files = sorted(glob.glob(pattern))
    
    entries = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        # Skip current chapter if it was previously evaluated
        if data.get("chapter_number") == current_chapter:
            continue
        entries.append(data)
    
    if not entries:
        return "PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:\nNone — this is the first evaluation for this subject/grade.\n"
    
    lines = ["PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:"]
    for idx, entry in enumerate(entries, 1):
        ch = entry.get("chapter_number", "?")
        title = entry.get("chapter_title", "")
        sub_disc = entry.get("chapter_sub_discipline", "unknown")
        evaluated_on = entry.get("evaluated_on", "")[:10]
        outcome = entry.get("outcome", "")
        
        # Build pattern tag summary
        tags = entry.get("pattern_tags", [])
        red = entry.get("red_flags", [])
        orange = entry.get("orange_flags", [])
        
        # Collect c_code+tag pairs from findings
        tag_details = []
        for flag in red + orange:
            for tag in flag.get("failure_pattern", "").split(","):
                tag = tag.strip()
                if tag:
                    tag_details.append(f"{tag} ({flag.get('c_code', '?')})")
        
        tag_str = ", ".join(tag_details) if tag_details else "none"
        
        # Brief findings
        red_codes = [f.get("c_code") for f in red] if red else []
        orange_codes = [f.get("c_code") for f in orange] if orange else []
        finding_parts = []
        if red_codes:
            finding_parts.append(f"red: {', '.join(red_codes)}")
        if orange_codes:
            finding_parts.append(f"orange: {', '.join(orange_codes)}")
        finding_str = "; ".join(finding_parts) if finding_parts else "no flags"
        
        lines.append(
            f"[{idx}] Ch {ch} · {title} · {sub_disc} · evaluated {evaluated_on}\n"
            f"  pattern_tags: [{tag_str}]\n"
            f"  findings: {finding_str}\n"
            f"  outcome: {outcome}"
        )
    
    lines.append(
        "\nBefore completing your analysis, check whether any pattern_tag from "
        "the above applies to the current chapter's mapping. If a pattern seen "
        "before appears again, note it explicitly in your PRIOR LEARNING MATCHES section."
    )
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_system_prompt(framework_path: Path) -> str:
    """Build the system prompt from the eval framework document."""
    framework_text = framework_path.read_text(encoding="utf-8")
    return (
        "You are an evaluator for the Aruvi chapter mapping system.\n\n"
        "Your task is a justification audit of one chapter mapping JSON record for "
        "Social Sciences. You verify that each competency assignment is supported by a "
        "justification that follows the constitutional process — naming the correct "
        "architectural container, stating a transformation the section demonstrably "
        "demands, and corresponding that transformation to the C-code.\n\n"
        "You DO NOT re-execute the mapping. You DO NOT scan the chapter summary for "
        "competency evidence independently. You read each justification against the "
        "chapter_summary in the JSON and apply the evaluation rules below.\n\n"
        "The C-code definitions are consulted only to verify that a transformation "
        "named in a justification corresponds to what the C-code defines. The CG "
        "document is not consulted for any other purpose.\n\n"
        "Output format: structured findings only. No narrative preamble. No executive "
        "summary paragraph. Follow the output format in the evaluation instruction exactly.\n\n"
        "--- EVALUATION FRAMEWORK ---\n\n"
        f"{framework_text}"
    )


def build_user_prompt(mapping_json: dict, prior_learnings_block: str) -> str:
    """Build the user prompt with mapping JSON and prior learnings injected."""
    mapping_str = json.dumps(mapping_json, indent=2, ensure_ascii=False)
    
    return f"""{prior_learnings_block}

CHAPTER MAPPING TO EVALUATE:
{mapping_str}

EVALUATION INSTRUCTION:
Run the evaluation framework on the chapter mapping above.

Step 1 — Pre-checks (P1–P5): Run all five. Report pass/fail for each.

Step 2 — Chapter-level rules (Rule 8, Rule 9): Check both. Report finding.

Step 3 — Competency-level audit: For each entry in the primary array,
apply the rules for its weight level (W3: R2+R3+R4 / W2: R2+R3+R5 /
W1: R2+R3+R6). For each entry in the incidental array, apply R7.
Rate each GREEN, ORANGE, or RED. State the specific rule(s) cited.
For ORANGE and RED findings, state a recommended correction.

Step 4 — Pattern tags: For each ORANGE or RED finding, assign one or more
pattern tags from the controlled vocabulary below. Reference the specific C-code.
If any pattern tag matches a tag seen in PRIOR EVALUATION LEARNINGS, note
the match explicitly (e.g. "justification_floats: also seen in Ch 3 C-2.1").
If any pattern tag has now appeared 3 or more times across this subject/grade
(including this evaluation), add a one-sentence evaluator_note recommending
it be reviewed for constitution clarification.

CONTROLLED PATTERN TAG VOCABULARY (use only these):
- dissolution_test_misread: W3 assigned to rhetorically prominent competency, not load-bearing one
- surface_match_accepted: vocabulary shared, architectural demand not confirmed
- cross_subdiscipline_w3_violation: W3 assigned outside primary sub-discipline cluster
- incidental_promoted_incorrectly: incidental entry has structural element, should be primary
- primary_demoted_incorrectly: primary entry has no structural element, should be incidental
- justification_floats: transformation stated but not anchored to named architectural section
- tie_break_not_applied: two W3 assignments without tie-break resolution
- weight_arithmetic_error: P1 failure — chapter_weight ≠ sum of primary weights
- cg_mismatch: P5 failure — cg field does not match c_code's parent CG
- container_named_imprecisely: container named too broadly (e.g. "the chapter" vs section name)

Step 5 — Summary line.

OUTPUT FORMAT (follow exactly):

PRE-CHECKS
P1: [PASS/FAIL]  P2: [PASS/FAIL]  P3: [PASS/FAIL]  P4: [PASS/FAIL]  P5: [PASS/FAIL]
[If any FAIL: state which field has the error and what the correct value should be]

CHAPTER-LEVEL
Rule 8 (sub-discipline restriction): [PASS/VIOLATION] — primary sub-discipline: [name]
Rule 9 (tie-break): [PASS/VIOLATION/NOT APPLICABLE]

COMPETENCY FINDINGS
[For each primary entry:]
CG-{{n}} | C-{{n.n}} | W{{weight}} | {{rules cited}} | {{GREEN/ORANGE/RED}}
  Container: [named correctly / named imprecisely / missing — details]
  Transformation: [confirmed / weakly stated / not grounded — details]
  C-code correspondence: [confirmed / not confirmed — details]
  [If ORANGE or RED:] Suggested correction: [specific field + corrected text]
  [If ORANGE or RED:] Pattern tag(s): [tag1, tag2]

[For each incidental entry:]
Incidental | C-{{n.n}} | R7 | {{GREEN/RED}}
  [Does chapter_summary contain any named section organising around this competency?
  If yes: should be primary — RED. If no: incidental is correct — GREEN.]

PRIOR LEARNING MATCHES
[List any pattern tags from this evaluation that match prior learning entries.
Format: {{tag}}: previously seen in Ch {{N}} (C-{{code}}). Or state: None.]

[If any tag appears 3+ times across this grade/subject including this evaluation:]
EVALUATOR NOTE: [one sentence flagging for constitution review]

SUMMARY
  Red flags: [count] — [C-codes if any, else 'none']
  Orange flags: [count] — [C-codes if any, else 'none']
  Structural errors: [count] — [P-checks if any, else 'none']
  Recommended action: [Accept / Accept with optional corrections / Correct and accept / Re-run]
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def evaluate_chapter(root: Path, subject: str, grade: str, chapter_num: int, dry_run: bool):
    paths = resolve_paths(root, subject, grade, chapter_num)
    
    print(f"\n{'='*60}")
    print(f"Aruvi Chapter Mapping Evaluator — Social Sciences")
    print(f"Subject: {subject} | Grade: {grade} | Chapter: {chapter_num:02d}")
    print(f"{'='*60}")
    
    # Verify mapping exists
    if not paths["mapping"].exists():
        print(f"ERROR: Mapping not found: {paths['mapping']}")
        sys.exit(1)
    
    # Load mapping
    with open(paths["mapping"], encoding="utf-8") as f:
        mapping_json = json.load(f)
    
    chapter_title = mapping_json.get("chapter_title", "Unknown")
    print(f"Chapter: {chapter_title}")
    
    # Check if already stamped
    if "eval_record" in mapping_json:
        stamp = mapping_json["eval_record"].get("stamp", "")
        print(f"\nWARNING: This chapter has already been evaluated.")
        print(f"  Existing stamp: {stamp}")
        print(f"  Proceeding will generate a new evaluation. Stamping will overwrite.")
        print()
    
    # Load prior learnings
    prior_learnings = load_prior_learnings(paths["learnings_dir"], chapter_num)
    prior_count = prior_learnings.count("[") - prior_learnings.count("None")
    print(f"Prior learnings loaded: {max(0, prior_count)} chapter(s)")
    
    if dry_run:
        print("\n[DRY RUN] Paths verified. No API call made.")
        print(f"  Mapping: {paths['mapping']}")
        print(f"  Learnings dir: {paths['learnings_dir']}")
        print(f"  Framework: {paths['framework']}")
        return
    
    # Verify framework exists
    if not paths["framework"].exists():
        print(f"ERROR: Eval framework not found: {paths['framework']}")
        sys.exit(1)
    
    # Build prompts
    system_prompt = build_system_prompt(paths["framework"])
    user_prompt = build_user_prompt(mapping_json, prior_learnings)
    
    # Call API
    print("\nCalling Claude API (claude-sonnet-4-6)...")
    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    findings = response.content[0].text
    
    # Print findings
    print(f"\n{'='*60}")
    print("EVALUATION FINDINGS")
    print(f"{'='*60}")
    print(findings)
    print(f"{'='*60}")
    
    # Token report
    usage = response.usage
    print(f"\nTokens — input: {usage.input_tokens} | output: {usage.output_tokens}")
    
    # Instruction to Kumar
    print(f"""
NEXT STEP — run stamp_eval.py with your decision:

  python stamp_eval.py \\
    --subject {subject} --grade {grade} --chapter {chapter_num} \\
    --outcome "Accept" \\
    --amendments '[]' \\
    --red-flags '[]' \\
    --orange-flags '[]'

  Change --outcome to "Correct and accept" and populate --amendments if
  you are accepting any corrections. Use --red-flags and --orange-flags
  to record which C-codes had findings (even if corrections were rejected).
  
  For rubberstamp (reject all changes): use --outcome "Accept" with empty --amendments.
""")


def main():
    parser = argparse.ArgumentParser(description="Aruvi SS Chapter Mapping Evaluator")
    parser.add_argument("--subject", required=True, help="Subject group (e.g. social_sciences)")
    parser.add_argument("--grade", required=True, help="Grade (e.g. vii)")
    parser.add_argument("--chapter", type=int, help="Single chapter number")
    parser.add_argument("--chapters", type=int, nargs="+", help="Multiple chapter numbers")
    parser.add_argument("--dry-run", action="store_true", help="Verify paths only, no API call")
    args = parser.parse_args()
    
    if not args.chapter and not args.chapters:
        print("ERROR: Specify --chapter N or --chapters N1 N2 ...")
        sys.exit(1)
    
    chapters = [args.chapter] if args.chapter else args.chapters
    root = find_project_root()
    
    for ch in chapters:
        evaluate_chapter(root, args.subject, args.grade, ch, args.dry_run)
        if len(chapters) > 1:
            print(f"\n--- Completed Chapter {ch:02d}. Review findings before continuing. ---\n")


if __name__ == "__main__":
    main()
