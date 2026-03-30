#!/usr/bin/env python3
"""
stamp_eval.py — Aruvi Chapter Mapping Eval Stamper
Subject Group: Social Sciences

Writes the eval_record field to the chapter mapping JSON and writes
the chapter's eval_learning.json to the evaluation_learnings/ folder.

Does NOT call the Claude API. This is a pure write operation.
Run only after reviewing findings from run_eval.py and deciding.

Usage:
    python stamp_eval.py \\
        --subject social_sciences --grade vii --chapter 1 \\
        --outcome "Accept" \\
        --amendments '[]' \\
        --red-flags '[]' \\
        --orange-flags '["C-2.2"]'

    python stamp_eval.py \\
        --subject social_sciences --grade vii --chapter 1 \\
        --outcome "Correct and accept" \\
        --amendments '[{"field":"weight","c_code":"C-3.1","from":3,"to":2,"approved_by":"Kumar"}]' \\
        --red-flags '["C-3.1"]' \\
        --orange-flags '[]'

Outcomes:
    Accept              — mapping stamped as-is, no amendments
    Correct and accept  — amendments applied before stamping
    Re-run              — do not stamp; re-run mapping pipeline first
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


CONSTITUTION_VERSION = "V1.1"
SUBJECT_ABBREV = {"social_sciences": "SS", "languages": "LA", "mathematics": "MA", "science": "SC"}

VALID_PATTERN_TAGS = {
    "dissolution_test_misread",
    "surface_match_accepted",
    "cross_subdiscipline_w3_violation",
    "incidental_promoted_incorrectly",
    "primary_demoted_incorrectly",
    "justification_floats",
    "tie_break_not_applied",
    "weight_arithmetic_error",
    "cg_mismatch",
    "container_named_imprecisely",
}

SUB_DISCIPLINES = {
    "history": ["CG-1", "CG-2", "CG-3"],
    "geography": ["CG-6", "CG-7"],
    "political_science": ["CG-4", "CG-8", "CG-10"],
    "economics": ["CG-9"],
    "cross_cutting": ["CG-5"],
}


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
        config = base / "aruvi_config.json"
        if config.exists():
            return base
    raise FileNotFoundError(
        "aruvi_config.json not found. Confirm mnt/data/ maps to project root."
    )


def resolve_paths(root: Path, subject: str, grade: str, chapter_num: int):
    grade_dir = root / "mirror" / "chapters" / subject / f"grade_{grade}"
    return {
        "mapping": grade_dir / "mappings" / f"ch_{chapter_num:02d}_mapping.json",
        "learnings_dir": grade_dir / "evaluation_learnings",
        "learning_file": grade_dir / "evaluation_learnings" / f"ch_{chapter_num:02d}_eval_learning.json",
    }


# ---------------------------------------------------------------------------
# Amendment application
# ---------------------------------------------------------------------------

def apply_amendments(mapping_json: dict, amendments: list) -> dict:
    """Apply approved amendments to the mapping JSON in-memory."""
    if not amendments:
        return mapping_json
    
    for amendment in amendments:
        c_code = amendment.get("c_code")
        field = amendment.get("field")
        new_value = amendment.get("to")
        
        if field == "weight":
            for entry in mapping_json.get("primary", []):
                if entry.get("c_code") == c_code:
                    print(f"  Applying: {c_code} weight {entry['weight']} → {new_value}")
                    entry["weight"] = new_value
            # Recalculate chapter_weight
            mapping_json["chapter_weight"] = sum(
                e.get("weight", 0) for e in mapping_json.get("primary", [])
            )
            print(f"  Recalculated chapter_weight: {mapping_json['chapter_weight']}")
        
        elif field == "justification":
            for entry in mapping_json.get("primary", []):
                if entry.get("c_code") == c_code:
                    print(f"  Applying: {c_code} justification updated")
                    entry["justification"] = new_value
        
        elif field == "move_to_incidental":
            # Move from primary to incidental
            primary = mapping_json.get("primary", [])
            incidental = mapping_json.get("incidental", [])
            entry_to_move = next((e for e in primary if e.get("c_code") == c_code), None)
            if entry_to_move:
                primary.remove(entry_to_move)
                cg = entry_to_move.get("cg")
                incidental.append({"cg": cg, "c_code": c_code})
                print(f"  Applying: {c_code} moved from primary to incidental")
                mapping_json["chapter_weight"] = sum(
                    e.get("weight", 0) for e in primary
                )
        
        elif field == "move_to_primary":
            # Move from incidental to primary — requires weight and justification in amendment
            incidental = mapping_json.get("incidental", [])
            primary = mapping_json.get("primary", [])
            entry_to_move = next((e for e in incidental if e.get("c_code") == c_code), None)
            if entry_to_move:
                incidental.remove(entry_to_move)
                primary.append({
                    "cg": entry_to_move.get("cg"),
                    "c_code": c_code,
                    "weight": amendment.get("weight", 1),
                    "justification": amendment.get("justification", ""),
                })
                print(f"  Applying: {c_code} moved from incidental to primary (W{amendment.get('weight',1)})")
                mapping_json["chapter_weight"] = sum(
                    e.get("weight", 0) for e in primary
                )
    
    return mapping_json


# ---------------------------------------------------------------------------
# Stamp construction
# ---------------------------------------------------------------------------

def build_stamp(subject: str, grade: str, chapter_num: int) -> str:
    abbrev = SUBJECT_ABBREV.get(subject, subject[:2].upper())
    date_str = datetime.now().strftime("%Y%m%d")
    return f"EVAL_{abbrev}_{grade.upper()}_CH{chapter_num:02d}_{CONSTITUTION_VERSION}_{date_str}"


def build_eval_record(
    outcome: str,
    amendments: list,
    red_flags: list,
    orange_flags: list,
    subject: str,
    grade: str,
    chapter_num: int,
    mode: str,
) -> dict:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "evaluated_on": now_iso,
        "mode": mode,
        "gross_violations_found": red_flags,
        "amendments_applied": amendments,
        "outcome": outcome,
        "constitution_version": CONSTITUTION_VERSION,
        "stamp": build_stamp(subject, grade, chapter_num),
    }


# ---------------------------------------------------------------------------
# Learning entry construction
# ---------------------------------------------------------------------------

def build_learning_entry(
    mapping_json: dict,
    eval_record: dict,
    red_flags: list,
    orange_flags: list,
    amendments: list,
    chapter_sub_discipline: str,
    evaluator_note: str,
    pattern_tags: list,
    prior_pattern_matches: list,
    findings: dict,
) -> dict:
    """Build the ch_NN_eval_learning.json content.

    findings: dict keyed by c_code with one-line description of what was found.
    e.g. {"C-6.2": "dissolution test fails — chapter reorganises without it"}
    """
    chapter_num = mapping_json.get("chapter_number")
    chapter_title = mapping_json.get("chapter_title", "")

    # Build red flag entries
    red_entries = []
    for c_code in red_flags:
        amendment = next((a for a in amendments if a.get("c_code") == c_code), None)
        red_entries.append({
            "c_code": c_code,
            "rule_cited": "",
            "failure_pattern": "",
            "what_was_found": findings.get(c_code, ""),
            "corrected_to": amendment.get("to") if amendment else None,
        })

    # Build orange flag entries
    orange_entries = []
    for c_code in orange_flags:
        amendment = next((a for a in amendments if a.get("c_code") == c_code), None)
        orange_entries.append({
            "c_code": c_code,
            "rule_cited": "",
            "failure_pattern": "",
            "what_was_found": findings.get(c_code, ""),
            "corrected_to": amendment.get("to") if amendment else None,
        })
    
    return {
        "chapter_number": chapter_num,
        "chapter_title": chapter_title,
        "evaluated_on": eval_record["evaluated_on"],
        "chapter_sub_discipline": chapter_sub_discipline,
        "outcome": eval_record["outcome"],
        "structural_errors": [],        # Populated if P-checks failed
        "red_flags": red_entries,
        "orange_flags": orange_entries,
        "pattern_tags": pattern_tags,
        "prior_pattern_match": prior_pattern_matches,
        "evaluator_note": evaluator_note,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def stamp_chapter(
    root: Path,
    subject: str,
    grade: str,
    chapter_num: int,
    outcome: str,
    amendments: list,
    red_flags: list,
    orange_flags: list,
    mode: str,
    chapter_sub_discipline: str,
    evaluator_note: str,
    pattern_tags: list,
    prior_pattern_matches: list,
    findings: dict,
):
    paths = resolve_paths(root, subject, grade, chapter_num)
    
    print(f"\n{'='*60}")
    print(f"Aruvi Eval Stamper — Social Sciences")
    print(f"Subject: {subject} | Grade: {grade} | Chapter: {chapter_num:02d}")
    print(f"Outcome: {outcome} | Mode: {mode}")
    print(f"{'='*60}")
    
    if outcome == "Re-run":
        print("Outcome is Re-run. No files written. Re-run the mapping pipeline first.")
        return
    
    # Load mapping
    if not paths["mapping"].exists():
        print(f"ERROR: Mapping not found: {paths['mapping']}")
        sys.exit(1)
    
    with open(paths["mapping"], encoding="utf-8") as f:
        mapping_json = json.load(f)
    
    chapter_title = mapping_json.get("chapter_title", "Unknown")
    print(f"Chapter: {chapter_title}")
    
    # Apply amendments if any
    if amendments:
        print("\nApplying approved amendments:")
        mapping_json = apply_amendments(mapping_json, amendments)
    else:
        print("No amendments to apply.")
    
    # Build eval_record
    eval_record = build_eval_record(
        outcome=outcome,
        amendments=amendments,
        red_flags=red_flags,
        orange_flags=orange_flags,
        subject=subject,
        grade=grade,
        chapter_num=chapter_num,
        mode=mode,
    )
    
    # Write eval_record to mapping JSON
    mapping_json["eval_record"] = eval_record
    
    with open(paths["mapping"], "w", encoding="utf-8") as f:
        json.dump(mapping_json, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ eval_record written to: {paths['mapping'].name}")
    print(f"  Stamp: {eval_record['stamp']}")
    
    # Build and write learning entry
    paths["learnings_dir"].mkdir(parents=True, exist_ok=True)
    
    learning_entry = build_learning_entry(
        mapping_json=mapping_json,
        eval_record=eval_record,
        red_flags=red_flags,
        orange_flags=orange_flags,
        amendments=amendments,
        chapter_sub_discipline=chapter_sub_discipline,
        evaluator_note=evaluator_note,
        pattern_tags=pattern_tags,
        prior_pattern_matches=prior_pattern_matches,
        findings=findings,
    )
    
    with open(paths["learning_file"], "w", encoding="utf-8") as f:
        json.dump(learning_entry, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Learning entry written to: {paths['learning_file'].name}")
    print(f"\nEvaluation complete for Chapter {chapter_num:02d}.")


def main():
    parser = argparse.ArgumentParser(description="Aruvi SS Chapter Eval Stamper")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--outcome", required=True,
                        choices=["Accept", "Correct and accept", "Reject changes and stamp", "Re-run"],
                        help="Evaluation outcome")
    parser.add_argument("--amendments", default="[]",
                        help="JSON array of approved amendments")
    parser.add_argument("--red-flags", default="[]",
                        help="JSON array of C-codes with red RAG rating")
    parser.add_argument("--orange-flags", default="[]",
                        help="JSON array of C-codes with orange RAG rating")
    parser.add_argument("--mode", default="evaluate_and_stamp",
                        choices=["evaluate_and_stamp", "rubberstamp"],
                        help="Evaluation mode")
    parser.add_argument("--sub-discipline", default="unknown",
                        help="Primary sub-discipline of this chapter (e.g. geography, history)")
    parser.add_argument("--evaluator-note", default="",
                        help="Optional note if a pattern has appeared 3+ times")
    parser.add_argument("--pattern-tags", default="[]",
                        help="JSON array of pattern tags from this evaluation")
    parser.add_argument("--prior-matches", default="[]",
                        help="JSON array of prior pattern match descriptions")
    parser.add_argument("--findings", default="{}",
                        help='JSON object keyed by C-code with one-line what_was_found description. '
                             'e.g. \'{"C-6.2": "dissolution test fails — chapter reorganises without it"}\'')

    args = parser.parse_args()

    # Parse JSON args
    try:
        amendments = json.loads(args.amendments)
        red_flags = json.loads(args.red_flags)
        orange_flags = json.loads(args.orange_flags)
        pattern_tags = json.loads(args.pattern_tags)
        prior_matches = json.loads(args.prior_matches)
        findings = json.loads(args.findings)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON argument: {e}")
        sys.exit(1)

    root = find_project_root()

    stamp_chapter(
        root=root,
        subject=args.subject,
        grade=args.grade,
        chapter_num=args.chapter,
        outcome=args.outcome,
        amendments=amendments,
        red_flags=red_flags,
        orange_flags=orange_flags,
        mode=args.mode,
        chapter_sub_discipline=args.sub_discipline,
        evaluator_note=args.evaluator_note,
        pattern_tags=pattern_tags,
        prior_pattern_matches=prior_matches,
        findings=findings,
    )


if __name__ == "__main__":
    main()
