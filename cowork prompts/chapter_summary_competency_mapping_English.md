# Cowork Session — English: Chapter Summary + Static Competency Mapping

Reads an English chapter PDF and writes two files per chapter:
a structured summary JSON and a mapping JSON.
Cowork reads and writes directly. No API calls.

The summary follows the **two-axis** structure of an English NCERT
chapter: an **outer axis** of 1–3 `main_sections` (each a distinct
text the student reads — prose, poem, narrative, dialogue, or
informational), and an **inner axis** of the 6 spines within each
section (Reading, Listening, Speaking, Writing, Vocabulary/Grammar,
Beyond-the-Text).

Competency mapping is **static at the stage level** — looked up from
`spine_to_cg.json` and attached decoratively. **No per-chapter
competency mapping is performed.**

## Run scope

Subject is `english`. `{stage}` derives from grade: III–V →
`preparatory`, VI–VIII → `middle`, IX–X → `secondary`.

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/english/{grade}/` |
| Listening transcript appendix (secondary only) | `mnt/data/knowledge_commons/textbooks/english/ix/appendix.pdf` |
| Static spine→CG | `mnt/data/mirror/framework/english/{stage}/spine_to_cg.json` |
| NCF CG (context) | `mnt/data/mirror/framework/english/{stage}/cg_{stage}_english.txt` |
| NCF Pedagogy (context) | `mnt/data/mirror/framework/english/{stage}/pedagogy_{stage}_english.txt` |
| Summary output | `mnt/data/mirror/chapters/english/{grade}/summaries/ch_NN_summary.json` |
| Mapping output | `mnt/data/mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json` |

## Step 1 — Chapter title and stage

Extract `chapter_title` verbatim from the opening page. Set `stage`
from the grade per Run scope.

## Step 2 — Detect main_sections (1 to 3)

A `main_section` is a distinct text the student reads. New main_section
starts when ANY of these holds: a new chapter-title-style heading
appears (often with a separate author byline); the textbook introduces
a new text under "Reading for Appreciation"; a clear shift between
prose and poem; or the textbook re-runs a spine cycle (a second
"Let us read" / "Reading for Meaning" for a different text).

Stage defaults (verify against the PDF, do not assume):
- **Preparatory**: usually 1; occasionally 2 (a separate fable / riddle).
- **Middle**: usually 2–3 (primary text + secondary text/poem).
- **Secondary**: usually 2 (primary prose + closing poem under
  "Reading for Appreciation").

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

| Spine | Preparatory | Middle | Secondary |
|---|---|---|---|
| `reading` | Let us Read · Let us Recite · Let us Think | Let us read · Let us discuss · Let us think | Reading for Meaning · Check Your Understanding · Critical Reflection · Reflect and Respond · Reading for Appreciation |
| `listening` | Let us Listen | Let us listen | Listen and Respond |
| `speaking` | Let us Speak | Let us speak | Speaking Activity |
| `writing` | Let us Write | Let us write | Writing Task |
| `vocabulary_grammar` | Let us Learn | Let us learn | Vocabulary and Structures in Context · Vocabulary in Context |
| `beyond_text` | Let us Do · Let us Explore · Just for Fun | Let us do · Let us explore | Learning Beyond the Text · POINTS TO REMEMBER |

## Step 5 — Per (section, spine) cell, capture tasks and question bank

For each present (section, spine) cell:

- `section_name` — the textbook subheading(s) used. When the spine
  pulls from MULTIPLE subheadings (per Step 4 table), join them with
  ` + ` in textbook order, e.g. `"Let us read + Let us discuss + Let us think"`.
- `tasks_verbatim` — flat array of EVERY in-class task instruction
  appearing under ANY of the spine's subheadings in this main_section,
  lifted verbatim and in textbook order. Sub-parts (a)/(b)/(c) of one
  parent task roll up into one entry.
- `question_bank` — flat array of EVERY exercise/question item
  appearing under ANY of the spine's subheadings in this main_section.
  Each entry:
  ```json
  {
    "stem":     "<verbatim question text>",
    "type":     "MCQ" | "SCR" | "ECR" | "MATCH" | "FILL_IN" |
                "TRUE_FALSE" | "ORAL_PROMPT" | "WRITING_TASK" |
                "PROJECT",
    "options":  [...],         // MCQ only
    "table":    "header|cells\nrow|cells",  // when the question
                                            // contains tabular data
    "page_ref": "p.NN"
  }
  ```

**Critical for `reading` and other multi-subheading spines**: do NOT
collapse to just the first subheading's tasks. The Reading spine in a
middle-stage section MUST contain tasks from "Let us read" AND
"Let us discuss" AND "Let us think" if all three are present in the
PDF. Same applies to Vocabulary/Grammar at secondary (two
subheadings) and Beyond-the-Text where multiple subheadings appear.

## Step 6 — Listening cells: capture transcript

| Stage | What to capture | Why |
|---|---|---|
| Preparatory · Middle | `transcript_ref` only, format `"p.NN"` | Transcript lives inside the chapter PDF (under "TRANSCRIPTS" banner near the end). Downstream tools read the PDF directly. |
| Secondary | BOTH `transcript_ref` (format `"appendix p.NN"`) AND `transcript_text` (full verbatim text from `appendix.pdf`, speaker labels and newlines preserved) | The appendix is a separate file; downstream tools do not reopen it. |

Per main_section: each listening cell carries its own
`transcript_text` portion that matches its own listening tasks.

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

**`task_density` (integer 1–3):** average tasks per spine-cell.
Sum `len(tasks_verbatim)` across every (section, spine) cell, divide
by total number of spine-cells, then tier:
- avg ≤ 3.0 → 1
- avg 3.1–6.0 → 2
- avg ≥ 6.1 → 3

**`writing_demand` (integer 0–2):** total `question_bank` entries
across all `writing` and `beyond_text` spine-cells only, then tier:
- 0–5 → 0
- 6–15 → 1
- 16+ → 2

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

Read `mirror/framework/english/{stage}/spine_to_cg.json` and copy each
spine's `competency_codes` array verbatim into
`competency_reporting.by_spine`. **Do NOT generate per-chapter
competency tags.**

### 8b — Write chapter mapping JSON

After writing the summary JSON, also write a separate mapping file to:

`mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json`

This file is read by the Allocate tab to display chapters and compute
period allocation. It must follow the same structure as other subjects'
mapping files.

**How to populate each field:**

- `stage`, `subject` (`"english"`), `grade`, `chapter_number`,
  `chapter_title` — copy from the summary JSON.
- `summary_path` — relative path string:
  `"mirror/chapters/english/{grade}/summaries/ch_NN_summary.json"`
- `primary` — build from `spine_to_cg.json`. For each spine in
  `spines` (in order: `reading`, `listening`, `speaking`, `writing`,
  `vocabulary_grammar`, `beyond_text`), emit one entry per unique
  `c_code` in that spine's `competency_codes` array. De-duplicate
  across spines: if the same `c_code` appears in multiple spines, emit
  it only once (first occurrence wins). Each entry:
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

**Mapping JSON template** (Ch 01, middle stage, computed values shown):

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
`spine_to_cg.json` with de-duplication applied. It will be the same
for every middle-stage English chapter — only `effort_index` varies
per chapter.

UTF-8. Create `mappings/` directory if it does not exist. Overwrite if
the file already exists.

## Step 9 — Write summary JSON

```json
{
  "subject": "english",
  "stage": "secondary",
  "grade": "ix",
  "chapter_number": 3,
  "chapter_title": "Winds of Change",

  "main_sections": [
    {
      "section_id": "A",
      "title": "Pankhas Across India",
      "type": "prose",
      "page_range": "p.69-80",
      "char_count": 25000,
      "prose_summary": "<200–400 word textbook-grounded summary>",
      "spines": {
        "reading": {
          "section_name": "Reading for Meaning + Check Your Understanding + Critical Reflection",
          "tasks_verbatim": ["...", "...", "..."],
          "question_bank": [
            {
              "stem": "Work in pairs to complete the table on pankha.",
              "type": "MATCH",
              "table": "State|Type of Fan|Material Used\nRajasthan|appliqué hand fan|...",
              "page_ref": "p.73"
            }
          ]
        },
        "listening": {
          "section_name": "Listen and Respond",
          "transcript_ref": "appendix p.263",
          "transcript_text": "ROHAN: Priya, what should we get Grandma...\nPRIYA: I was thinking a hand pankha...",
          "tasks_verbatim": ["..."],
          "question_bank": [/* ... */]
        },
        "speaking":           { "section_name": "Speaking Activity",                    "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "writing":            { "section_name": "Writing Task",                         "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "vocabulary_grammar": { "section_name": "Vocabulary and Structures in Context", "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "beyond_text":        { "section_name": "Learning Beyond the Text",             "tasks_verbatim": ["..."], "question_bank": [/* ... */] }
      }
    },
    {
      "section_id": "B",
      "title": "Canvas of Soil",
      "type": "poem",
      "page_range": "p.79",
      "char_count": 600,
      "poem_text": "Palette of earth, rich and deep,\nWhere dreams of gardeners seep.\n...",
      "poem_appreciation_summary": "<80–150 word appreciation>",
      "spines": {
        "reading":            { "section_name": "Reading for Appreciation", "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "vocabulary_grammar": { "section_name": "Vocabulary in Context",    "tasks_verbatim": ["..."], "question_bank": [/* ... */] }
      }
    }
  ],

  "competency_reporting": {
    "by_spine": {
      "reading":            ["C-2.1", "C-2.2", "C-3.1", "C-4.1"],
      "listening":          ["C-3.1"],
      "speaking":           ["C-1.1", "C-3.2"],
      "writing":            ["C-1.2", "C-1.3", "C-1.4", "C-2.3"],
      "vocabulary_grammar": ["C-2.2"],
      "beyond_text":        ["C-4.2", "C-4.3", "C-4.4", "C-4.5"]
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

A spine with both `tasks_verbatim` empty AND `question_bank` empty
must be omitted from its section's `spines` object. UTF-8. Overwrite.

## Step 10 — Confirmation line

```
ch_NN — "<title>" — sections: <count> (<type breakdown>) — spines_total: <N> — tasks: <total_task_count> — question_bank: <total_question_bank_count> — project_load: <N> — effort_index: <value>
```

Example: `ch_03 — "Winds of Change" — sections: 2 (1 prose + 1 poem) — spines_total: 8 — tasks: 28 — question_bank: 14 — project_load: 2 — effort_index: 1.72`

## Constraints

- No API calls. Cowork reads PDFs and writes JSON directly.
- No consulting LOs, Syllabus, Assessment Framework, or Position
  Papers. Pedagogy beyond `mirror/framework/english/{stage}/` is
  off-limits.
- Competency mapping is static (Step 8b): `primary` codes come from
  `spine_to_cg.json` only — do NOT generate per-chapter competency tags.
- `effort_index` is computed from the four bounded signals in Step 8b
  — do NOT estimate, do NOT clamp, keep one decimal place.
- Listening transcripts: prep/middle = `transcript_ref` only;
  secondary = `transcript_ref` + `transcript_text` (per Step 6).
- Do NOT invent absent spines. Do NOT collapse a multi-subheading
  spine to the first subheading only (per Step 5).
- Two output files are written per chapter: summary JSON (Step 9) and
  mapping JSON (Step 8b). Both must be present before moving to the
  next chapter.
- Process chapters in order. UTF-8. Overwrite.
