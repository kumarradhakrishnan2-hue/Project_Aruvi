---
name: aruvi-ss-chapter-eval
description: >
  Evaluates Aruvi Social Sciences chapter mapping JSONs against the competency
  mapping constitution. Runs a full RAG audit (Red/Orange/Green), presents
  findings, awaits Kumar's explicit consent before any change, then stamps the
  mapping JSON and writes a learning entry. Accumulated learnings from prior
  chapters are loaded into each evaluation to sharpen the audit over time.

  USE THIS SKILL whenever the user asks to: evaluate or audit a SS chapter
  mapping, run the chapter eval for SS any grade, check for red/orange flags,
  stamp an evaluated mapping, run eval on a batch of SS chapters, or apply
  rubberstamp to finalized mappings (e.g. SS Grade VII).

  Two modes: EVALUATE-AND-STAMP (new mappings — full audit, consent gate,
  amendments applied only on approval) and RUBBERSTAMP (finalized mappings —
  full audit still runs for learnings, but existing JSON stamped as-is unless
  Kumar explicitly approves a change). Always one chapter at a time.
---

# Aruvi · Social Sciences Chapter Mapping Evaluator

## Project Structure (Mac-side)

Project root: `/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi/`

Eval-relevant paths (all relative to project root):

```
mirror/
└── chapters/
    └── social_sciences/
        └── grade_{grade}/
            ├── mappings/
            │   └── ch_{NN}_mapping.json          ← INPUT + OUTPUT (eval_record appended)
            ├── summaries/
            │   └── ch_{NN}_summary.txt           ← READ-ONLY (chapter_summary reference)
            └── evaluation_learnings/
                └── ch_{NN}_eval_learning.json    ← OUTPUT (one file per chapter)
```

The evaluation framework document is bundled at:
`references/eval_framework_social_sciences.md`

The constitution snapshot is bundled at:
`references/constitution_social_sciences.md`

---

## How to Run in Cowork

### Single chapter
```bash
python run_eval.py --subject social_sciences --grade vii --chapter 1
```

### Batch (sequential, one at a time)
```bash
python run_eval.py --subject social_sciences --grade vii --chapters 1 2 3 4
```

### Dry run (verify paths, do not call API)
```bash
python run_eval.py --subject social_sciences --grade vii --chapter 1 --dry-run
```

The script:
1. Resolves all paths from `aruvi_config.json`
2. Loads the chapter mapping JSON
3. Loads any prior `ch_*_eval_learning.json` files for the same subject/grade
4. Calls the Claude API with the evaluation prompt
5. Presents findings to Kumar
6. **STOPS. Waits for Kumar's explicit instruction.**

After Kumar's instruction, run the stamp command:
```bash
python stamp_eval.py --subject social_sciences --grade vii --chapter 1 \
  --outcome "Accept" \
  --amendments '[]' \
  --red-flags '[]' \
  --orange-flags '["C-2.2"]'
```

Or with amendments accepted:
```bash
python stamp_eval.py --subject social_sciences --grade vii --chapter 1 \
  --outcome "Correct and accept" \
  --amendments '[{"field":"weight","c_code":"C-3.1","from":3,"to":2}]' \
  --red-flags '["C-3.1"]' \
  --orange-flags '[]'
```

`stamp_eval.py` writes the `eval_record` field to the mapping JSON and writes
`ch_{NN}_eval_learning.json` to the evaluation_learnings folder. It does
**not** call the Claude API.

---

## The Evaluation Prompt (what run_eval.py sends to the API)

Read `references/eval_prompt_template.md` for the full prompt. The script
constructs it as follows:

**System prompt:** contents of `references/eval_framework_social_sciences.md`
(the full evaluation framework, Rules P1–P5, R2–R9, RAG legend, Section 5
correction format — this IS the evaluator's constitution)

**User prompt:** constructed from three components:
1. **Prior learnings block** — all `ch_*_eval_learning.json` files for this
   subject/grade loaded and formatted as a numbered list of prior findings
   with their pattern tags. If none exist yet, this block is omitted.
2. **Chapter mapping JSON** — the full `ch_{NN}_mapping.json` record
3. **Evaluation instruction** — see `references/eval_prompt_template.md`

**Model:** `claude-sonnet-4-6` (same as mapping pipeline)
**Max tokens:** 2000 (findings are concise — no per-chapter narrative reports)

---

## What the Evaluator Produces

The API call returns a structured finding, NOT a narrative report. Format:

```
PRE-CHECKS
P1: PASS  P2: PASS  P3: PASS  P4: PASS  P5: PASS

CHAPTER-LEVEL
Rule 8 (sub-discipline restriction): PASS — primary sub-discipline: Geography
Rule 9 (tie-break): NOT APPLICABLE

COMPETENCY FINDINGS
CG-6 | C-6.1 | W3 | R2+R3+R4 | GREEN
  Container: named correctly (Section 2 — River Systems)
  Transformation: analysis of drainage pattern formation — demonstrably demanded
  C-code correspondence: confirmed

CG-3 | C-3.1 | W2 | R2+R3+R5 | ORANGE
  Container: named but imprecisely (references "the chapter" not specific section)
  Transformation: stated weakly — "students learn about historical change"
  Flag: justification does not anchor to a named architectural section
  Suggested correction: name Section 4 — Medieval Trade Routes explicitly;
  restate transformation as "students construct causal sequence of trade
  network collapse from Section 4's timeline activity"

PATTERN TAGS (from this evaluation)
  justification_floats (C-3.1)

PRIOR LEARNING MATCH
  justification_floats: previously seen in Ch 3 (C-2.1). Same failure mode.
  Third occurrence would warrant constitution note.

SUMMARY
  Red flags: none
  Orange flags: C-3.1
  Structural errors: none
  Recommended action: Accept with optional justification sharpening on C-3.1
```

---

## Consent Gate — What Happens After Findings Are Presented

Kumar reads the findings and issues ONE of these instructions:

| Kumar's instruction | What stamp_eval.py does |
|---|---|
| "Accept as-is" / "Rubberstamp" | Stamps existing JSON unchanged. outcome = Accept |
| "Accept, fix the orange" | Applies the suggested justification correction to JSON. outcome = Correct and accept |
| "Accept, fix [specific C-code]" | Applies only that correction. outcome = Correct and accept |
| "Reject all changes, stamp" | Stamps existing JSON unchanged. outcome = Accept |
| "Re-run" | Do not stamp. Re-run mapping pipeline for this chapter first |

**Red flags always require an explicit Kumar decision.** The script never
auto-applies a red flag correction. Orange flag corrections are optional —
Kumar may accept the mapping as-is even with orange flags.

---

## The eval_record Field (written to ch_NN_mapping.json)

`stamp_eval.py` appends this field to the chapter's mapping JSON record:

```json
"eval_record": {
  "evaluated_on": "2026-03-30T14:22:00",
  "mode": "evaluate_and_stamp",
  "gross_violations_found": [],
  "amendments_applied": [],
  "outcome": "Accept",
  "constitution_version": "V1.1",
  "stamp": "EVAL_SS_VII_CH01_V1.1_20260330"
}
```

**Stamp format:** `EVAL_{SUBJECT_ABBREV}_{GRADE}_{CHAP}_V{CONST_VER}_{DATE}`

Subject abbreviations: SS · LA · MA · SC

Chapters with no `eval_record` field are unevaluated. This is the only
audit trail needed — Section 6 CSV log is not used.

---

## The Learning Entry (written to evaluation_learnings/)

`stamp_eval.py` writes `ch_{NN}_eval_learning.json`:

```json
{
  "chapter_number": 1,
  "chapter_title": "Geographical Diversity of India",
  "evaluated_on": "2026-03-30T14:22:00",
  "chapter_sub_discipline": "geography",
  "outcome": "Accept",
  "structural_errors": [],
  "red_flags": [],
  "orange_flags": [
    {
      "c_code": "C-3.1",
      "rule_cited": "R5",
      "failure_pattern": "justification_floats",
      "what_was_found": "justification references 'the chapter' not a named section",
      "corrected_to": null
    }
  ],
  "pattern_tags": ["justification_floats"],
  "prior_pattern_match": ["justification_floats seen in Ch 3 (C-2.1)"],
  "evaluator_note": ""
}
```

`corrected_to` is null if Kumar rejected the change, or contains the
corrected justification string if Kumar accepted it.

`evaluator_note` is populated by the evaluator when a pattern has appeared
3+ times — it contains a one-sentence note for future constitution review.

---

## Pattern Tag Vocabulary (controlled)

The evaluator MUST tag each finding using only these tags. No free-form tags.

| Tag | Meaning |
|---|---|
| `dissolution_test_misread` | W3 assigned to rhetorically prominent competency, not the load-bearing one |
| `surface_match_accepted` | Vocabulary shared between competency and chapter, but architectural demand not confirmed |
| `cross_subdiscipline_w3_violation` | W3 assigned to a C-code outside the chapter's primary sub-discipline cluster |
| `incidental_promoted_incorrectly` | Competency in incidental array has a structural element — should be primary |
| `primary_demoted_incorrectly` | Competency in primary array has no structural element — should be incidental |
| `justification_floats` | Transformation stated but not anchored to a named architectural section |
| `tie_break_not_applied` | Two W3 assignments present without tie-break resolution |
| `weight_arithmetic_error` | P1 pre-check failure — chapter_weight ≠ sum of primary weights |
| `cg_mismatch` | P5 pre-check failure — cg field does not match c_code's parent CG |
| `container_named_imprecisely` | Architectural container named but too broadly (e.g. "the chapter" vs section name) |

Multiple tags allowed per finding. Each tag must reference the specific C-code
it applies to in the learning entry.

---

## Mode Selection

The skill operates in the mode Kumar states at invocation time.

**EVALUATE-AND-STAMP** (default for new grades/subjects):
- Full RAG audit
- All red and orange flags presented
- Consent gate: Kumar approves or rejects each suggested change
- Approved changes written to mapping JSON
- Stamp applied

**RUBBERSTAMP** (for finalized mappings — e.g. SS Grade VII):
- Full RAG audit STILL RUNS (learnings are the point)
- Findings presented
- Kumar reviews and decides — but default expectation is rejection of changes
- Mapping JSON is NOT modified (unless Kumar explicitly instructs otherwise)
- Stamp applied to existing JSON as-is
- Learning entry written with full findings

To invoke rubberstamp mode, Kumar says "rubberstamp" or "stamp as-is after eval".

---

## Prior Learnings — How Accumulation Works

Before each evaluation, `run_eval.py` loads all `ch_*_eval_learning.json`
files for the same subject/grade from `evaluation_learnings/`.

These are injected into the user prompt as:

```
PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:
[1] Ch 1 · Geography · pattern_tags: [justification_floats (C-6.1)]
    Finding: justification referenced "the chapter" rather than named section.
    Outcome: Accept (change rejected).
[2] Ch 3 · History · pattern_tags: [dissolution_test_misread (C-1.2)]
    Finding: W3 assigned to most prominent theme; dissolution test showed
    the chapter would reorganise, not dissolve, without it.
    Outcome: Correct and accept — weight changed to 2.
```

The evaluator is instructed: "Check whether any pattern_tag from prior
learnings applies to the current chapter's mapping before completing your
analysis. If a pattern seen before appears again, note it explicitly."

When a pattern tag appears for the third time across the subject/grade,
the evaluator adds a one-sentence `evaluator_note` flagging it for
constitution review. This is the signal for Kumar to consider whether the
mapping constitution needs a clarification.

---

## Hard Constraints

- The evaluator reads `chapter_summary` from the mapping JSON as its sole content
  reference. It does NOT re-read the chapter PDF or the CG document independently.
- The CG document is consulted only to verify that a transformation named in a
  justification corresponds to what the C-code defines — not to scan for evidence.
- `stamp_eval.py` never calls the API. It is a pure write operation.
- `run_eval.py` never writes to any file. It is a pure read + display operation.
- No file is modified until Kumar gives explicit instruction after seeing findings.
- The `evaluation_learnings/` folder is in `mirror/` — machine-written, never
  edited by hand. The mapping JSON is also in `mirror/` but is amended by
  `stamp_eval.py` only, never by hand after stamping.

---

## Config Key Addition Required

Add to `aruvi_config.json`:

```json
"paths.mirror_eval_learnings_dir": "mirror/chapters/{subject}/grade_{grade}/evaluation_learnings/"
```

This follows the existing pattern for `paths.mirror_mappings_dir` and
`paths.mirror_summaries_dir`. `config_resolver.py` resolves it the same way.

---

## First-Time Setup for a New Subject/Grade

1. Confirm `ch_{NN}_mapping.json` files exist in `mirror/chapters/{subject}/grade_{grade}/mappings/`
2. Create the `evaluation_learnings/` folder (empty — `run_eval.py` creates it if missing)
3. Run `--dry-run` to verify all paths resolve
4. Run Chapter 1 first — no prior learnings yet, full eval
5. Review findings, stamp, confirm `ch_01_eval_learning.json` written
6. Proceed chapter by chapter — each subsequent chapter benefits from accumulated learnings

---

## Reference Files in This Skill

| File | Purpose | When to read |
|---|---|---|
| `references/eval_framework_social_sciences.md` | Full evaluation framework (P1-P5, R2-R9, RAG legend) — used as system prompt | Loaded by `run_eval.py` at runtime |
| `references/constitution_social_sciences.md` | Constitution snapshot (R1-R10) — for Cowork operator reference | When verifying a finding manually |
| `references/eval_prompt_template.md` | Full user prompt template with injection points | Read when constructing the API call |
