---
name: chapter
description: >
  Run the Aruvi chapter pipeline for any subject and grade — generates the chapter summary and
  competency mapping (or effort index) in the correct serialized order.
  USE THIS SKILL whenever the user says things like: "run chapter skill for chapter 5 maths grade vii",
  "process chapter 3 science class vi", "generate chapter summary for social sciences chapter 8 grade viii",
  "do chapter 2 english grade v", "run chapter 7 twau grade iii", "process the world around us chapter 4
  grade iv", "run the chapter pipeline", or any instruction that mentions a chapter number, subject, and
  grade together with intent to generate mirror data. Also trigger when the user says "run step 1" or
  "run step 2" for a chapter in the context of this project. Subjects include: science, social_sciences,
  mathematics, english, and the_world_around_us (TWAU — preparatory stage only, Grades III–V).
---

# Chapter Pipeline Skill

This skill runs the Aruvi chapter data pipeline — producing the chapter summary and competency
mapping (or effort index) for a given chapter, subject, and grade. These are the mirror files
that the Allocate tab and the LP + Assessment generator depend on.

---

## Quick reference — what runs for each subject

| Subject | Step 1 | Step 2 |
|---|---|---|
| **Science** | Chapter summary (`.txt`) | Effort index computation → `ch_NN_mapping.json` |
| **Social Sciences** | Chapter summary (`.txt`) | Competency mapping → `ch_NN_mapping.json` |
| **Mathematics** | Chapter summary (`.json`) | Competency mapping → `ch_NN_mapping.json` |
| **The World Around Us (TWAU)** | Chapter summary (`.json`) | Competency mapping → `ch_NN_mapping.json` |
| **English – Middle (VI–VIII)** | *(combined)* Chapter summary + mapping in one pass | — |
| **English – Preparatory (III–V)** | *(combined)* Chapter summary + mapping in one pass | — |

English is a single-step subject. All others (including TWAU) are two-step: Step 1 must fully
complete before Step 2 begins.

---

## Step 0 — Parse the request

Extract from the user's instruction:

- **subject** — one of: `science`, `social_sciences`, `mathematics`, `english`, `the_world_around_us`
  (accept "twau", "the world around us", "TWAU" → normalise to `the_world_around_us`)
- **grade** — roman numeral or arabic (e.g. "vii", "7", "grade 7", "class vii") → normalise to
  lowercase roman: `iii`, `iv`, `v`, `vi`, `vii`, `viii`, `ix`, `x`
- **chapter(s)** — single number, list, or "all"
- **stage** — derived from grade:
  - III–V → `preparatory`
  - VI–VIII → `middle`
  - IX–X → `secondary`

**TWAU constraint:** The World Around Us is only available for the preparatory stage (Grades III, IV, V).
If the user requests TWAU for grade VI or higher, reject with: "TWAU is a preparatory-stage subject
(Grades III–V only). Did you mean a different subject?"

If any of subject, grade, or chapter scope is missing or ambiguous, ask for clarification before
proceeding. Do not guess.

**Grade → Roman numeral mapping:**
3→iii, 4→iv, 5→v, 6→vi, 7→vii, 8→viii, 9→ix, 10→x

---

## Step 1 — Announce the plan

Before running anything, print a brief plan so the user can confirm:

```
Subject : Mathematics
Grade   : VII (middle stage)
Chapters: 5
Pipeline: Step 1 — Chapter summary (JSON) → Step 2 — Competency mapping
Prompt files:
  Step 1: cowork prompts/mathematics/step_1_chapter_summary.md
  Step 2: cowork prompts/mathematics/step_2_competency_mapping.md
```

For English:
```
Subject : English
Grade   : VII (middle stage)
Chapters: 3
Pipeline: Single step — Chapter summary + mapping (combined)
Prompt file:
  Step 1: cowork prompts/english/middle/step_1_chapter_summary_and_mapping.md
```

For The World Around Us (TWAU):
```
Subject : The World Around Us (TWAU)
Grade   : IV (preparatory stage)
Chapters: 7
Pipeline: Step 1 — Chapter summary (JSON) → Step 2 — Competency mapping
Prompt files:
  Step 1: cowork prompts/the_world_around_us/step_1_chapter_summary.md
  Step 2: cowork prompts/the_world_around_us/step_2_competency_mapping.md
```

---

## Step 2 — Locate and read the prompt file(s)

All prompt files live under:
`mnt/data/cowork prompts/{subject}/` (for science, social_sciences, mathematics, the_world_around_us)
`mnt/data/cowork prompts/english/{stage}/` (for english)

### Subject → prompt file map

**Science:**
- Step 1: `mnt/data/cowork prompts/science/step_1_chapter_summary.md`
- Step 2: `mnt/data/cowork prompts/science/step_2_effort_index.md`

**Social Sciences:**
- Step 1: `mnt/data/cowork prompts/social_sciences/step_1_chapter_summary.md`
- Step 2: `mnt/data/cowork prompts/social_sciences/step_2_competency_mapping.md`

**Mathematics:**
- Step 1: `mnt/data/cowork prompts/mathematics/step_1_chapter_summary.md`
- Step 2: `mnt/data/cowork prompts/mathematics/step_2_competency_mapping.md`

**The World Around Us / TWAU (preparatory — grades III, IV, V):**
- Step 1: `mnt/data/cowork prompts/the_world_around_us/step_1_chapter_summary.md`
- Step 2: `mnt/data/cowork prompts/the_world_around_us/step_2_competency_mapping.md`

**English (middle — grades VI, VII, VIII):**
- Step 1 (only): `mnt/data/cowork prompts/english/middle/step_1_chapter_summary_and_mapping.md`

**English (preparatory — grades III, IV, V):**
- Step 1 (only): `mnt/data/cowork prompts/english/preparatory/step_1_chapter_summary_and_mapping.md`

Read the prompt file(s) now. The prompt file contains the full instructions for that step —
follow them exactly.

---

## Step 3 — Execute Step 1

Follow the instructions in the Step 1 prompt exactly for the requested chapter(s) and grade.

**Important serialization rule:** Step 1 must be fully complete — all requested chapters
written and verified — before Step 2 begins. Never interleave steps across chapters
(e.g. do not do ch_05 Step 1 + ch_05 Step 2, then ch_06 Step 1 + ch_06 Step 2).
Instead: finish all Step 1 files first, then proceed to Step 2.

Correct order for chapters 5 and 6:
```
ch_05 Step 1 ✓
ch_06 Step 1 ✓
  → then →
ch_05 Step 2 ✓
ch_06 Step 2 ✓
```

---

## Step 4 — Execute Step 2 (non-English subjects only)

After all Step 1 files are confirmed written, read the Step 2 prompt file and follow it exactly.

Step 2 reads from the summary files produced in Step 1 — it never reads the source PDF.

**TWAU note:** TWAU Step 2 reads the summary JSON (`.json`, same as Mathematics) and the CG
reference file at `mnt/data/mirror/framework/The World Around US/competency_descriptions_twau.json`.
The constitution is at `mnt/data/mirror/constitutions/competency_mapping/the_world_around_us/mapping_constitution_twau.txt`.
Note the capitalisation difference: framework folder is `The World Around US` (capital S);
chapter mirror folder is `The World Around Us` (lowercase s). Preserve both exactly.

---

## Step 5 — Final confirmation

After all steps complete, print a summary table:

```
Chapter | Title                        | Step 1        | Step 2
--------|------------------------------|---------------|------------------
ch_05   | Parallel and Intersecting... | summary ✓     | mapping ✓ EI:13.5
```

For English (single-step):
```
Chapter | Title          | Summary + Mapping
--------|----------------|------------------
ch_03   | The Great Game | ✓ effort_index: 14.5
```

For TWAU (two-step, same format as Science/Mathematics):
```
Chapter | Title              | Step 1        | Step 2
--------|--------------------|---------------|----------------------------------
ch_07   | Water              | summary ✓     | mapping ✓ EI:9.0 cw:4
```

---

## Common error guards

- **Summary file missing when Step 2 runs**: halt and report. Do not fabricate. Re-run Step 1.
- **Grade out of range for stage**: warn and ask — e.g. English preparatory prompt used for grade VI
  would be wrong; correct prompt is english/middle. TWAU requested for grade VI or above — reject;
  TWAU only exists for grades III, IV, V.
- **Chapter PDF not found**: log a warning for that chapter and skip — do not halt the whole run.
- **Existing file will be overwritten**: this is expected behaviour — all prompts overwrite silently.
