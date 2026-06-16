---
name: chapter
description: "Run the Aruvi chapter pipeline for any subject and grade — generates the chapter summary and competency mapping (or effort index) in the correct serialized order. Covers science (middle/secondary), social_sciences (middle only), mathematics (preparatory/middle/secondary), english (preparatory/middle/secondary), and the_world_around_us (preparatory only)."
---

# Chapter Pipeline Skill

This skill runs the Aruvi chapter data pipeline — producing the chapter summary and competency
mapping (or effort index) for a given chapter, subject, and grade. These are the mirror files
the Streamlit app reads at runtime (chapter summaries + mapping JSONs); this skill never touches
the app itself.

## Quick reference — what exists today

| Subject | Stages on disk | Steps | Output format |
|---|---|---|---|
| Mathematics | preparatory, middle, secondary | Step 1 (summary) → Step 2 (competency mapping) | `.json` |
| English | preparatory, middle, secondary | Step 1+2 combined (single prompt) | `.json` |
| Science | middle, secondary | Step 1 (summary) → Step 2 (effort index) | `.txt` summary, `.json` mapping |
| Social Sciences | middle only | Step 1 (summary) → Step 2 (competency mapping) | `.txt` summary, `.json` mapping |
| The World Around Us (TWAU) | preparatory only | Step 1 (summary) → Step 2 (competency mapping) | `.txt` summary, `.json` mapping |

### Stage coverage is NOT uniform across subjects

Do not assume every subject has all three stages, and do not assume a subject with only one
stage folder is "flat" by design choice rather than by actual curriculum scope. The real picture,
confirmed against the folder tree on disk:

- **Mathematics** and **English** are genuinely stage-split across all three stages
  (preparatory/middle/secondary) — each stage has its own prompt file(s) and constitution.
- **Science** is stage-split, but only into **two** stages — middle and secondary. There is no
  preparatory Science; TWAU is the preparatory-stage subject instead (Grades III–V). Both Science
  stages share the IDENTICAL 4-signal effort-index formula and tiering tables — only the CG
  document, constitution, and source textbook differ between them.
- **Social Sciences** has a `middle/` stage folder, but only middle actually exists — there is no
  preparatory or secondary content anywhere on disk (no NCF-compliant secondary Social Sciences
  textbooks exist). This is a genuine curriculum-scope limit, not a missing build.
- **TWAU** has a `preparatory/` stage folder, and only preparatory exists, by design — TWAU
  covers Grades III–V and is superseded by Science/Social Sciences from Grade VI onward.

When a user's request implies a stage/subject combination that does not exist (e.g. "Science
grade iv" or "Social Sciences grade ix"), do not guess or substitute — stop and tell the user
the combination is out of scope, per the Step 0 constraints below.

---

## Step 0 — Confirm scope before doing anything

Before reading any file, confirm with the user (or infer unambiguously from their message):
1. Subject
2. Grade (and therefore stage — preparatory III–V, middle VI–VIII, secondary IX–X)
3. Chapter number(s) — single, multiple, or "all"
4. Which step(s) — summary only, mapping only, or both in sequence

**Constraint — Science requested for a preparatory grade (III–V).** Science has no preparatory
stage. Reject with: "Science does not have a preparatory stage — Grades III–V are covered by The
World Around Us (TWAU) instead. Did you mean to run TWAU for this grade, or Science for a middle
(VI–VIII) or secondary (IX–X) grade?"

**Constraint — Social Sciences requested for a preparatory or secondary grade.** Social Sciences
only has middle-stage content (VI–VIII). Reject with: "Social Sciences only has middle-stage
content (Grades VI–VIII) — there is no preparatory or secondary Social Sciences in Aruvi yet (no
NCF-compliant secondary textbooks exist for this subject). Did you mean a middle grade?"

**Constraint — TWAU requested for grade VI or above.** TWAU is preparatory-only (III–V). Reject
with: "TWAU only covers Grades III–V. From Grade VI onward, use Science and/or Social Sciences
instead."

---

## Step 1 — Announce the plan

State the resolved subject, stage, grade, chapter scope, and which step(s) will run, before
reading any files. Examples:

- "Running Mathematics preparatory, Grade IV, Chapter 3 — Step 1 (chapter summary) then Step 2
  (competency mapping)."
- "Running Mathematics middle, Grade VII, Chapter 5 — Step 1 then Step 2."
- "Running Mathematics secondary, Grade IX, Chapter 3 — Step 1 then Step 2."
- "Running Science middle, Grade VII, Chapter 2 — Step 1 (chapter summary) then Step 2 (effort
  index)."
- "Running Science secondary, Grade IX, Chapter 8 — Step 1 then Step 2 (effort index)."
- "Running Social Sciences middle, Grade VIII, Chapter 8 — Step 1 then Step 2 (competency
  mapping)."
- "Running English preparatory, Grade V, Chapter 2 — Step 1+2 combined (single prompt)."
- "Running English middle, Grade VII, Chapter 4 — Step 1+2 combined."
- "Running English secondary, Grade IX, Chapter 4 — Step 1+2 combined."
- "Running TWAU, Grade III, Chapter 7 — Step 1 then Step 2 (competency mapping)."

---

## Step 2 — Locate and run the correct prompt file

**Path pattern.** `{subject}/{stage}/` applies to mathematics, english, AND science — all three
are stage-routed on disk. Social_sciences and the_world_around_us currently have only one stage
folder each (`middle/` and `preparatory/` respectively), reflecting genuine curriculum scope, not
an unfinished split.

### Subject → prompt file map

| Subject | Stage | Step 1 file | Step 2 file |
|---|---|---|---|
| Mathematics | preparatory | `cowork prompts/mathematics/preparatory/step_1_chapter_summary.md` | `cowork prompts/mathematics/preparatory/step_2_competency_mapping.md` |
| Mathematics | middle | `cowork prompts/mathematics/middle/step_1_chapter_summary.md` | `cowork prompts/mathematics/middle/step_2_competency_mapping.md` |
| Mathematics | secondary | `cowork prompts/mathematics/secondary/step_1_chapter_summary.md` | `cowork prompts/mathematics/secondary/step_2_competency_mapping.md` |
| Science | middle | `cowork prompts/science/middle/step_1_chapter_summary.md` | `cowork prompts/science/middle/step_2_effort_index.md` |
| Science | secondary | `cowork prompts/science/secondary/step_1_chapter_summary.md` | `cowork prompts/science/secondary/step_2_effort_index.md` |
| Social Sciences | middle | `cowork prompts/social_sciences/middle/step_1_chapter_summary.md` | `cowork prompts/social_sciences/middle/step_2_competency_mapping.md` |
| English | preparatory | `cowork prompts/english/preparatory/step_1_chapter_summary_and_mapping.md` (combined) | — |
| English | middle | `cowork prompts/english/middle/step_1_chapter_summary_and_mapping.md` (combined) | — |
| English | secondary | `cowork prompts/english/secondary/step_1_chapter_summary_and_mapping.md` (combined) | — |
| TWAU | preparatory | `cowork prompts/the_world_around_us/preparatory/step_1_chapter_summary.md` | `cowork prompts/the_world_around_us/preparatory/step_2_competency_mapping.md` |

Read the prompt file in full before acting — it governs paths, scope rules, and output schema for
that subject/stage. Do not improvise or reuse a different stage's or subject's rules from memory.

---

## Step 3 — Run Step 1 (chapter summary)

Follow the located Step 1 prompt file exactly: locate the source PDF, extract the chapter title,
identify the scope boundary (headings/sections), write the summary per that prompt's own rules,
and save to the path it specifies. Mathematics and English summaries are `.json`; Science and
Social Sciences and TWAU summaries are `.txt`.

---

## Step 4 — Run Step 2 (competency mapping / effort index), if applicable

English combines Step 1 and Step 2 into a single prompt — do not run a separate Step 2 for
English; the one prompt file produces both the summary JSON and the mapping JSON in one pass.

For all other subjects, follow the located Step 2 prompt file exactly — it specifies which
constitution to apply, the effort-index or competency-weight formula for that subject/stage, and
the output schema.

**Science note.** Unlike Mathematics (where each of the three stages has its own distinct effort
formula and signal set — Mathematics middle, preparatory, and secondary all differ), Science
middle and secondary share the IDENTICAL 4-signal formula:
`(conceptual_demand × 2) + (activity_load × 2) + (demo_load × 1.5) + (exec_load × 2)`, range
2.0–19.0. Only the CG document, constitution text, and source textbook folder differ between the
two Science stages — never assume the Science formula changes by stage the way Mathematics's does.

---

## Step 5 — Print a verification summary

After writing the output file(s), print a short confirmation table covering: chapter number,
title, key signal values, and the final mapping/effort score, per the verification format
specified in that subject/stage's own prompt file (formats differ slightly by subject — follow
the prompt's own Step 5/6, not a generic template).

Example (Science Secondary):

```
Ch | Title (40 chars)                         | CD | AC>AL | DC>DL | EL | EI
---|------------------------------------------|----|-------|-------|----|------
08 | Journey Inside the Atom                   |  3 |  0> 0 |  0> 0 |  1 |  8.0
```

---

## Common error guards

- **Science requested for a preparatory grade** — reject per Step 0; redirect to TWAU.
- **Social Sciences requested for a preparatory or secondary grade** — reject per Step 0; no such
  content exists.
- **TWAU requested for grade VI or above** — reject per Step 0; redirect to Science/Social
  Sciences.
- **Mathematics prompt used for the wrong stage** — e.g. running the middle Mathematics prompt
  against a Grade IX chapter. Always resolve stage from grade first (preparatory III–V, middle
  VI–VIII, secondary IX–X), then pick the matching `{stage}/` folder. Never reuse a different
  stage's prompt file even if it seems similar — Mathematics's effort-index signals differ by
  stage and a wrong-stage run produces an invalid schema.
- **Science prompt used for the wrong stage** — e.g. running the middle Science prompt against a
  Grade IX chapter, or vice versa. The formula is identical across stages, but the constitution,
  CG document, and source textbook are stage-specific — always use the matching `{stage}/` folder
  even though the math would happen to come out the same either way.
- **English Step 2 run separately** — there is no separate English Step 2 prompt; it does not
  exist as a file. Re-run the combined Step 1+2 prompt instead.
- **Summary file missing when Step 2 is requested** — Step 2 (or the combined English prompt)
  always depends on Step 1's output existing first. If the summary file is missing, run Step 1
  first, do not fabricate mapping content from the PDF directly.
- **Wrong output format assumed** — Mathematics and English are `.json` summaries; Science, Social
  Sciences, and TWAU are `.txt` summaries. All mapping outputs (every subject) are `.json`.

---

## Constraints

- Do not call the Claude API from inside this skill unless the located prompt file explicitly
  says to. Most Step 1/Step 2 prompts read the PDF directly using Cowork's own context.
- Do not modify any field outside what the specific step's prompt file authorizes.
- Do not generate or overwrite a chapter summary when only Step 2 was requested, and vice versa.
- If a chapter PDF is not found, log a warning and skip — do not halt the whole run.
- All files written in UTF-8 encoding.
