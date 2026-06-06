#!/usr/bin/env python3
"""
lint_lp_teacher_prose.py — Rule 9 verification pass for English lesson plans.

Teacher-facing text MUST NOT expose internal planning machinery: task indices
("task 3", "Tasks 5 and 6"), the `task_index` key, internal item IDs (e.g.
Q-RFC-A-1, A-1, WE-3), schema/planner keys, rule numbers, C-codes, or internal
question-type codes (MCQ, ECR, EXTRACT_ANALYSIS, MATCH, …). Tasks must be named
by their teacher-facing anchor (the spine subheading, e.g. "Reading for
Meaning", "Critical Reflection") plus a plain-English brief.

Three teacher-facing fields are scanned:
  - period `teacher_notes`
  - each phase `description`
  - each `task_brief` in `tasks_in_class` / `homework` (rendered to teachers):
    must carry NO internal codes AND must begin with / contain a subheading
    anchor so the teacher can locate the exercise.

The numeric `task_index` join key inside the structured arrays is NOT scanned;
only the human-readable fields above are checked.

Accepts either a full saved-plan JSON ({"result": {"lesson_plan": ...}}) or a
bare LP JSON ({"lesson_plan": ...} or {"periods": ...}).

Usage:
    python lint_lp_teacher_prose.py <plan.json> [<plan2.json> ...]
Exit code 0 = clean; 1 = leaks found; 2 = bad input.
"""
import json
import re
import sys

# Each rule: (label, compiled pattern). Patterns target PROSE only.
RULES = [
    ("task-index reference",
     re.compile(r'\btasks?\s+\d+\b', re.I)),                 # "task 3", "Tasks 5 and 6"
    ("task-index ranges/lists",
     re.compile(r'\btasks?\s+\d+\s*(?:,|and|&|to|-|–)\s*\d+', re.I)),
    ("schema key task_index",
     re.compile(r'task_index')),
    ("internal item id",
     re.compile(r'\bQ-[A-Z]{2,4}-[A-Z]-\d+\b')),            # Q-RFC-A-1
    ("internal short id",
     re.compile(r'\b(?:A|WE|E|FW|HW)-\d+\b')),              # A-1, WE-3, E-9
    ("schema/planner key",
     re.compile(r'\b(?:spines_taught|tasks_in_class|tasks_anchored|'
                r'coverage_handoff|implied_lo|section_context|task_brief|'
                r'spine_code|question_bank|tasks_verbatim)\b')),
    ("rule reference",
     re.compile(r'\bRule\s+\d+[A-Z]?\b')),
    ("C-code",
     re.compile(r'\bC-\d+\.\d+\b')),
    ("internal question-type code",
     re.compile(r'\b(?:MCQ|SCR|ECR|EXTRACT_ANALYSIS|MATCH|FILL_IN|'
                r'TRUE_FALSE|ORAL_PROMPT|WRITING_TASK|PROJECT)\b')),
]

# task_brief is ALSO teacher-facing (it is rendered to teachers), even though it
# lives inside the structured arrays. It must obey Rule 9: no internal codes, and
# it must name the task by a subheading anchor. We scan it with the same RULES
# (minus the schema-key rule, which would false-positive on the literal field
# names) PLUS a required-anchor check.
_BRIEF_RULES = [r for r in RULES if r[0] != "schema/planner key"]

# Valid teacher-facing anchors = the secondary-stage textbook subheadings.
SUBHEADING_ANCHORS = [
    "Reflect and Respond", "Reading for Meaning", "Reading for Appreciation",
    "Check Your Understanding", "Critical Reflection", "Listen and Respond",
    "Speaking Activity", "Writing Task", "Vocabulary and Structures in Context",
    "Vocabulary in Context", "Learning Beyond the Text", "POINTS TO REMEMBER",
]

# A page locator: "p.184", "p. 184", "pp.181-182", "p.181–182".
PAGE_REF = re.compile(r'pp?\.?\s?\d+', re.I)


def scan_brief(text):
    """Scan a task_brief. Each brief must (a) carry no internal code/id, (b) name
    a subheading anchor, and (c) include a page locator so the teacher can find
    the exercise. Format expected: '<Anchor> (p.NN): <plain brief>'."""
    out = []
    if not text:
        return out
    for label, pat in _BRIEF_RULES:
        for m in pat.finditer(text):
            out.append((label, m.group(0)))
    if not any(a in text for a in SUBHEADING_ANCHORS):
        out.append(("missing subheading anchor", text[:60]))
    if not PAGE_REF.search(text):
        out.append(("missing page locator", text[:60]))
    return out


def iter_periods(doc):
    """Yield period dicts from any accepted shape."""
    node = doc
    if isinstance(node, dict) and "result" in node:
        node = node["result"]
    if isinstance(node, dict) and "lesson_plan" in node:
        node = node["lesson_plan"]
    if isinstance(node, dict) and "periods" in node:
        return node["periods"]
    if isinstance(node, list):
        return node
    return []


def scan_text(text):
    out = []
    if not text:
        return out
    for label, pat in RULES:
        for m in pat.finditer(text):
            out.append((label, m.group(0)))
    return out


def lint_file(path):
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] {path}: cannot parse JSON — {e}")
        return None  # signals bad input

    periods = iter_periods(doc)
    if not periods:
        print(f"[ERROR] {path}: no periods found (unexpected shape)")
        return None

    leaks = []
    for p in periods:
        n = p.get("period_number", "?")
        for label, frag in scan_text(p.get("teacher_notes", "")):
            leaks.append((n, "teacher_notes", label, frag))
        for i, ph in enumerate(p.get("phases", []), 1):
            for label, frag in scan_text(ph.get("description", "")):
                leaks.append((n, f"phase {i} ({ph.get('minutes','?')})",
                              label, frag))
        # task_brief is teacher-facing too — scan it in both buckets.
        for bucket in ("tasks_in_class", "homework"):
            for t in p.get(bucket, []):
                for label, frag in scan_brief(t.get("task_brief", "")):
                    leaks.append((n, f"{bucket} task_brief", label, frag))
    return leaks


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    bad_input = False
    total = 0
    for path in argv[1:]:
        result = lint_file(path)
        if result is None:
            bad_input = True
            continue
        if result:
            total += len(result)
            print(f"\n✗ {path} — {len(result)} leak(s):")
            for n, where, label, frag in result:
                print(f"    period {n} · {where} · {label}: {frag!r}")
        else:
            print(f"✓ {path} — clean (no internal references in teacher prose)")
    if bad_input:
        return 2
    if total:
        print(f"\nFAILED: {total} internal-reference leak(s) found. "
              f"Rewrite teacher prose to name tasks by subheading anchor + brief.")
        return 1
    print("\nPASSED: all teacher-facing prose is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
