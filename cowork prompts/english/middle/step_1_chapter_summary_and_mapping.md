# Cowork Session — English (Middle): Chapter Summary + Static Competency Mapping

Reads an English chapter PDF for the **Middle stage (Grades VI–VIII)**
and writes two files per chapter: a structured summary JSON and a
mapping JSON. Cowork reads and writes directly. No API calls.

The summary follows the **two-axis** structure of a middle-stage
English NCERT chapter: an **outer axis** of 1–3 `main_sections` (each
a distinct text the student reads — `prose`, `poem`, `narrative`,
`dialogue`, or `informational`), and an **inner axis** of the 6 spines
within each section (Reading for Comprehension, Listening, Speaking,
Writing, Vocabulary/Grammar, Beyond-the-Text).

Competency mapping is **static at the stage level** — looked up from
`spine_to_cg.json` and **restricted to spines that are actually present
in the chapter**. **No per-chapter competency mapping is performed.**
**All English competencies carry weight 1.**

## Run scope

Subject is `english`. Stage is `middle`. Grades VI, VII, VIII.

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/english/{grade}/` |
| Static spine→CG | `mnt/data/mirror/framework/english/middle/spine_to_cg.json` |
| NCF CG (context) | `mnt/data/mirror/framework/english/middle/cg_middle_english.txt` |
| NCF Pedagogy (context) | `mnt/data/mirror/framework/english/middle/pedagogy_middle_english.txt` |
| Summary output | `mnt/data/mirror/chapters/english/{grade}/summaries/ch_NN_summary.json` |
| Mapping output | `mnt/data/mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json` |

## Step 1 — Chapter title and stage

Extract `chapter_title` verbatim from the opening page. Set `stage` to
`"middle"`.

## Step 2 — Detect main_sections (1 to 3)

A `main_section` is a distinct text the student reads. New main_section
starts when ANY of these holds: a new chapter-title-style heading
appears (often with a separate author byline); a clear shift between
prose and poem; or the textbook re-runs a spine cycle (a second
"Let us read" for a different text).

Stage default for middle: usually **2–3 sections** (a primary prose
text plus a second text or closing poem).

Per main_section capture: `section_id` ("A"/"B"/"C" in textbook
order), `title`, `type` (`prose | poem | narrative | dialogue |
informational`), `page_range`, `char_count` (text body, not exercises).

## Step 3 — Per main_section, write the text summary

| section `type` | Required field(s) | Length | Content |
|---|---|---|---|
| prose / narrative / dialogue / informational | `prose_summary` | 200–400 words | Plot/argument arc, characters/key entities, setting, themes, tone, pivotal passages. Plain prose, no bullets. |
| poem | `poem_text` AND `poem_appreciation_summary` | full verbatim / 80–150 words | `poem_text`: line breaks + stanza breaks preserved. `poem_appreciation_summary`: theme, tone, central imagery, dominant device. |

These fields are MANDATORY. Stay strictly within the textbook — no
outside knowledge. Very short texts get proportionally shorter
summaries (50–100 words) but are never omitted.

The text summary is the source of truth for downstream LP
`teacher_notes` and assessment item generation/verification.

## Step 4 — Per main_section, identify present spine sections

Walk each main_section in textbook order. A single spine MAY be fed
by MULTIPLE textbook subheadings — see the table. A spine MAY be
absent (e.g. a closing poem often carries only Reading + Vocabulary).
Do NOT invent missing spines.

| Spine | Middle textbook subheadings |
|---|---|
| `reading_for_comprehension` | Let us read · Let us discuss · Let us think and reflect |
| `listening` | Let us listen |
| `speaking` | Let us speak |
| `writing` | Let us write |
| `vocabulary_grammar` | Let us learn |
| `beyond_text` | Let us do · Let us explore |

## Step 5 — Per (section, spine) cell, capture tasks with nested sub-items

For each present (section, spine) cell:

- `section_name` — the textbook subheading(s) used. When the spine
  pulls from MULTIPLE subheadings (per Step 4 table), join them with
  ` + ` in textbook order, e.g. `"Let us read + Let us discuss + Let us think and reflect"`.
- `tasks_verbatim` — array of OBJECTS, one per in-class task
  instruction appearing under ANY of the spine's subheadings in this
  main_section, in textbook order. Sub-parts (a)/(b)/(c) of one parent
  task roll up into one entry — they become sub-items of that single
  task, NOT separate task objects. Each entry:
  ```json
  {
    "task_text": "<verbatim instruction + body of the task>",
    "question_bank": [          // sub-items belonging to THIS task;
                                // [] if the task is a single open
                                // prompt with no sub-items in the
                                // textbook
      {
        "stem":     "<verbatim question text>",
        "type":     "MCQ" | "SCR" | "ECR" | "MATCH" | "FILL_IN" |
                    "TRUE_FALSE" | "ORAL_PROMPT" | "WRITING_TASK" |
                    "PROJECT",
        "options":  [...],          // MCQ only
        "table":    "header|cells\nrow|cells",  // when the sub-item
                                                // contains tabular data
        "page_ref": "p.NN"
      }
    ]
  }
  ```

**Single source of truth.** Each question_bank entry belongs to
exactly ONE task. Do NOT duplicate questions across tasks. Do NOT
emit a flat top-level `question_bank` array on the spine — that field
no longer exists. The lesson plan refers to a task by its index in
this array, enacts the full unit in class (teacher-led activity via
`task_text` + in-class working through of `question_bank` sub-items),
and emits an `implied_lo` per anchored task in its coverage handoff.
The assessment generator reads those implied LOs and generates
original items grounded in the section's `prose_summary` or
`poem_text` — it does NOT lift from `question_bank`.

**Critical for `reading_for_comprehension` and other multi-subheading
spines**: do NOT collapse to just the first subheading's tasks. The
Reading-for-Comprehension spine in a middle-stage section MUST
contain tasks from "Let us read" AND "Let us discuss" AND "Let us
think and reflect" if all three are present in the PDF. Each parent
task from any of those subheadings becomes its own task object (with
its own nested `question_bank`). Same applies to Beyond-the-Text
where multiple subheadings appear.

## Step 6 — Listening cells: capture transcript

Each listening cell captures both `transcript_ref` and
`transcript_text`.

- `transcript_ref`: `"p.NN"` — from the TRANSCRIPTS section of the
  chapter PDF.
- `transcript_text`: shortened to **150–250 words**. All
  speakers/segments represented, sequence and resolution intact,
  filler trimmed, speaker labels preserved.

Per main_section: each listening cell carries its own `transcript_ref`
and `transcript_text` matching its own listening tasks.

## Step 7 — Effort signals

Compute AFTER the `main_sections` JSON is fully written, by literally
counting and inspecting array entries — do not estimate, do not
approximate. These four bounded signals (and the `effort_index` derived
from them) are stored in the summary JSON and are the single source of
truth for the mapping JSON (Step 8b does NOT recompute them).

**Step 7a — Compute the four signals:**

**`spine_load` (integer 1–3):** average spines per section.
Count the number of spine keys present in each `main_section.spines`
object, average across all sections, then tier:
- avg ≤ 3.0 → 1
- avg 3.1–5.0 → 2
- avg ≥ 5.1 → 3

**`task_density` (integer 1–3):** average task objects per spine-cell.
Sum `len(tasks_verbatim)` across every (section, spine) cell (each
entry is one task object), divide by total number of spine-cells, then
tier:
- avg ≤ 3.0 → 1
- avg 3.1–6.0 → 2
- avg ≥ 6.1 → 3

**`writing_demand` (integer 0–2):** total exercise-item count under
the `writing` and `beyond_text` spines only. For each task in those
spines, count `max(1, len(t.question_bank))` — i.e. a task with
sub-items contributes its sub-item count, and an **open task** (one
with zero sub-items, e.g. "write a paragraph", "make a poster") still
counts as **1 item**, not 0. Formula:
`sum(max(1, len(t.question_bank)) for cell in (writing + beyond_text spine cells) for t in cell.tasks_verbatim)`.
Then tier:
- 0–5 → 0
- 6–15 → 1
- 16+ → 2

Rationale: an open writing/project task represents real student work
even though the textbook doesn't enumerate sub-items. The earlier
sub-items-only count under-reported chapters whose writing or
beyond-text tasks were long-form prompts.

**`project_load` (integer 0–3):** count of cells where the spine key
is `beyond_text` (one cell = one unit, one per section that has it).

**Step 7b — Apply formula:**
```
effort_index = (spine_load × 2) + (task_density × 1.5)
             + (writing_demand × 1.5) + (project_load × 1)
```
Do NOT clamp or round. Keep one decimal place.

**Step 7c — Verify:** Re-walk the JSON and confirm that the counts used
to derive each signal match the actual array lengths. If they don't, the
JSON wins — recompute the signals. A mismatch is a defect, not a
rounding artefact.

All five values (`spine_load`, `task_density`, `writing_demand`,
`project_load`, `effort_index`) are written into the summary JSON under
`effort_signals` (see Step 9 template).

## Step 8 — Attach static competency mapping AND write mapping JSON

### 8a — Attach to summary JSON

Read `mirror/framework/english/middle/spine_to_cg.json`. For each
spine that is **actually present in this chapter** (i.e. appears as a
key under any `main_section.spines`), copy that spine's
`competency_codes` array verbatim into
`competency_reporting.by_spine`. **Do NOT emit entries for spines that
are absent from the chapter.** **Do NOT generate per-chapter
competency tags.**

To compute "spines present in this chapter", take the union of
`spines` keys across every `main_section` in the summary. A spine that
has no task objects in any section is, by Step 9, omitted from
`main_sections[*].spines` — and therefore must also be absent here.

### 8b — Write chapter mapping JSON

After writing the summary JSON, also write a separate mapping file to:

`mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json`

This file is read by the Allocate tab to display chapters and compute
period allocation. It must follow the same structure as other subjects'
mapping files.

**How to populate each field:**

- `stage` (`"middle"`), `subject` (`"english"`), `grade`,
  `chapter_number`, `chapter_title` — copy from the summary JSON.
- `summary_path` — relative path string:
  `"mirror/chapters/english/{grade}/summaries/ch_NN_summary.json"`
- `primary` — build from `spine_to_cg.json`, **restricted to spines
  that are actually present in this chapter** (same union rule as Step
  8a — a spine appears here only if it appears as a key under at
  least one `main_section.spines`). Walk the present spines in the
  canonical order `reading_for_comprehension`, `listening`, `speaking`,
  `writing`, `vocabulary_grammar`, `beyond_text` (skipping any absent
  spine), and emit one entry per unique `c_code` in that spine's
  `competency_codes` array. De-duplicate across spines: if the same
  `c_code` appears in multiple spines, emit it only once (first
  occurrence wins). Each entry:
  ```json
  {
    "c_code": "C-1.1",
    "weight": 1
  }
  ```
  All English competencies carry `"weight": 1` — English uses
  `effort_index` (not competency weights) for period allocation.
- `incidental` — leave as empty array `[]`.
- `spine_load`, `task_density`, `writing_demand`, `project_load`,
  `effort_index` — **copy directly from the summary JSON's
  `effort_signals` block**. Do NOT recompute. The summary JSON is the
  single source of truth for all five values.
- `chapter_weight` — set to `null` (English uses `effort_index` for
  allocation, not `chapter_weight`).

**Mapping JSON template** (Ch 01, middle stage, all 6 spines present):

```json
{
  "stage": "middle",
  "subject": "english",
  "grade": "vii",
  "chapter_number": 1,
  "chapter_title": "Learning Together",
  "summary_path": "mirror/chapters/english/vii/summaries/ch_01_summary.json",
  "primary": [
    { "c_code": "C-1.1", "weight": 1 },
    { "c_code": "C-2.1", "weight": 1 },
    { "c_code": "C-2.2", "weight": 1 },
    { "c_code": "C-1.2", "weight": 1 },
    { "c_code": "C-1.3", "weight": 1 },
    { "c_code": "C-2.3", "weight": 1 },
    { "c_code": "C-1.4", "weight": 1 },
    { "c_code": "C-1.5", "weight": 1 },
    { "c_code": "C-3.2", "weight": 1 },
    { "c_code": "C-3.1", "weight": 1 },
    { "c_code": "C-5.1", "weight": 1 },
    { "c_code": "C-5.2", "weight": 1 },
    { "c_code": "C-5.3", "weight": 1 },
    { "c_code": "C-4.2", "weight": 1 }
  ],
  "incidental": [],
  "spine_load": 3,
  "task_density": 2,
  "writing_demand": 1,
  "project_load": 3,
  "effort_index": 13.5,
  "chapter_weight": null
}
```

The `primary` list above is derived from the middle-stage
`spine_to_cg.json` with de-duplication applied **and restricted to
spines present in this chapter**. If a chapter omits a spine (for
example a closing poem section that has no `listening` or `writing`
tasks anywhere in the chapter), the c-codes contributed solely by
that spine must NOT appear in `primary`. Two chapters with the same
spine coverage will share the same `primary` list; chapters with
different spine coverage will differ.

UTF-8. Create `mappings/` directory if it does not exist. Overwrite if
the file already exists.

## Step 9 — Write summary JSON

```json
{
  "subject": "english",
  "stage": "middle",
  "grade": "vii",
  "chapter_number": 1,
  "chapter_title": "Learning Together",

  "main_sections": [
    {
      "section_id": "A",
      "title": "A Day in School",
      "type": "prose",
      "page_range": "p.1-12",
      "char_count": 18000,
      "prose_summary": "<200–400 word textbook-grounded summary>",
      "spines": {
        "reading_for_comprehension": {
          "section_name": "Let us read + Let us discuss + Let us think and reflect",
          "tasks_verbatim": [
            {
              "task_text": "Work in pairs to discuss the following questions about the passage.",
              "question_bank": [
                { "stem": "What did the narrator notice on the first day?", "type": "SCR", "page_ref": "p.5" },
                { "stem": "Why is teamwork important according to the author?", "type": "SCR", "page_ref": "p.6" }
              ]
            },
            { "task_text": "<next reading-for-comprehension task verbatim>", "question_bank": [] }
          ]
        },
        "listening": {
          "section_name": "Let us listen",
          "transcript_ref": "p.39",
          "transcript_text": "Speaker 1 (Teacher): School taught me that learning never stops...\nSpeaker 2 (Student): My favourite part is meeting friends every day...\n[150–250 words — shortened, all speakers represented]",
          "tasks_verbatim": [
            { "task_text": "<task instruction>", "question_bank": [/* sub-items */] }
          ]
        },
        "speaking":           { "section_name": "Let us speak", "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] },
        "writing":            { "section_name": "Let us write", "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] },
        "vocabulary_grammar": { "section_name": "Let us learn", "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] },
        "beyond_text":        { "section_name": "Let us do + Let us explore", "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] }
      }
    },
    {
      "section_id": "B",
      "title": "The Morning Bell",
      "type": "poem",
      "page_range": "p.13",
      "char_count": 600,
      "poem_text": "The morning bell rings clear and loud,\nWaking the lanes, waking the crowd.\n...",
      "poem_appreciation_summary": "<80–150 word appreciation>",
      "spines": {
        "reading_for_comprehension": { "section_name": "Let us read + Let us discuss", "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] },
        "vocabulary_grammar":        { "section_name": "Let us learn",                 "tasks_verbatim": [{ "task_text": "...", "question_bank": [/* ... */] }] }
      }
    }
  ],

  "competency_reporting": {
    "by_spine": {
      "reading_for_comprehension": ["C-1.1", "C-2.1", "C-2.2"],
      "listening":                 ["C-1.1", "C-1.2"],
      "speaking":                  ["C-1.2", "C-1.3", "C-2.3"],
      "writing":                   ["C-1.4", "C-1.5", "C-2.3", "C-3.2"],
      "vocabulary_grammar":        ["C-3.1", "C-5.1", "C-5.2", "C-5.3"],
      "beyond_text":               ["C-2.1", "C-4.2"]
    }
  },

  "effort_signals": {
    "spine_load": 3,
    "task_density": 2,
    "writing_demand": 1,
    "project_load": 3,
    "effort_index": 13.5
  }
}
```

A spine with `tasks_verbatim` empty (no task objects, no nested
sub-items) must be omitted from its section's `spines` object. UTF-8.
Overwrite.

## Step 10 — Confirmation line

```
ch_NN — "<title>" — sections: <count> (<type breakdown>) — spines_total: <N> — tasks: <total_task_object_count> — sub_items: <total_subitem_count> — project_load: <N> — effort_index: <value>
```

Where:
- `total_task_object_count` = sum of `len(spine.tasks_verbatim)` across all (section, spine) cells.
- `total_subitem_count` = sum of `len(t.question_bank) for cell in all cells for t in cell.tasks_verbatim`.

Example: `ch_01 — "Learning Together" — sections: 2 (1 prose + 1 poem) — spines_total: 8 — tasks: 24 — sub_items: 32 — project_load: 1 — effort_index: 13.5`

## Constraints

- No API calls. Cowork reads PDFs and writes JSON directly.
- No consulting LOs, Syllabus, Assessment Framework, or Position
  Papers. Pedagogy beyond `mirror/framework/english/middle/` is
  off-limits.
- Competency mapping is static-by-stage (Step 8b): `primary` codes
  come from `spine_to_cg.json` only — do NOT generate per-chapter
  competency tags. But `primary` is **filtered to the spines actually
  present in this chapter** — c-codes contributed only by spines that
  the chapter does not exercise must be dropped.
- `effort_index` is computed from the four bounded signals in Step 7
  — do NOT estimate, do NOT clamp, keep one decimal place.
- `writing_demand` uses the `max(1, …)` rule — open tasks count as 1
  item, not 0.
- Listening transcripts: capture `transcript_ref` + `transcript_text`,
  shortened to 150–250 words (per Step 6).
- Do NOT invent absent spines. Do NOT collapse a multi-subheading
  spine to the first subheading only (per Step 5).
- Each `tasks_verbatim` entry MUST be an OBJECT
  `{ task_text, question_bank }`. Each `question_bank` entry MUST be
  nested inside its parent task object. The legacy flat top-level
  `question_bank` shape on a spine is FORBIDDEN.
- Two output files are written per chapter: summary JSON (Step 9) and
  mapping JSON (Step 8b). Both must be present before moving to the
  next chapter.
- Process chapters in order. UTF-8. Overwrite.
