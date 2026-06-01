# Cowork Session — The World Around Us: Chapter Summary

Reads a TWAU (The World Around Us) chapter PDF and writes a structured
summary JSON. Cowork reads the PDF and writes the file directly. No API
call is made.

The summary is grounded content extraction ONLY: what the chapter contains,
what student tasks are present, and the chapter's effort profile.

## Run scope

Specify grade and chapter scope at the start of the session. Subject is
`The World Around Us`. Stage is `preparatory` (Grades III, IV, V).

```
Single chapter  : process chapter 7 only
Multiple        : process chapters 1, 4, 8
All chapters    : process all chapters for this grade
```

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | `mnt/data/` |
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/the_world_around_us/{grade}/` |
| Output | `mnt/data/mirror/chapters/the_world_around_us/{grade}/summaries/ch_NN_summary.json` |

`{grade}` is the lowercase Roman numeral folder: `iii`, `iv`, or `v`. All TWAU
folders use the subject token `the_world_around_us` (matching the app's
`subject_to_folder`).

## Step 1 — Title and sections

Extract the chapter title verbatim from the opening page. List every named
section heading in textbook reading order. This is the summary's single
structural axis — the lesson plan will later walk these sections in order.
Nothing below may reference a heading not in this list.

## Step 2 — Per-section capture

For each named section, in textbook order, record:

- `title` — the section heading exactly as in the textbook.
- `content_summary` — 2 to 4 sentences covering what the section teaches:
  key concepts, the natural phenomenon, the human-cultural practice, and any
  concrete examples. Indian Knowledge System (IKS) content — traditional
  practices, local vessels, seasonal knowledge, folk conservation — is
  captured **here, inside `content_summary`**, where the textbook places it.

- `tasks` — array of task objects for all student tasks in this section
  (see Step 3 for what counts and how to structure each object).
  Empty array `[]` if the section has none.

Anchor every sentence to what is actually in the chapter. Never supplement
from training knowledge or general subject knowledge.

## Step 3 — What counts as a student task

TWAU chapters present student tasks under several distinct banner formats.
All of the following count and must be captured:

COUNTS:
- `Activity N` boxes — always; each numbered activity is one task object.
- `Find out` boxes — always; the full inquiry prompt is one task object.
- `Draw` boxes — always; the drawing instruction is one task object.
- `Write` boxes — each discrete writing or filling task is one task object
  (a table to fill, a question with a blank line to answer).
- `Discuss` boxes — every bullet point inside a Discuss box is a separate
  task object.
- `Let us reflect` sub-items — each lettered sub-section (A. Write,
  B. Draw, C. Discuss, D. Activity) is counted per its banner type above;
  a Discuss sub-section with three bullets produces three task objects.
- Any other named banner or boxed prompt not listed above that directs
  the student to do, make, find, observe, record, or express something —
  count it and use the banner's own heading text as the `banner` value.
  New banner formats may appear in Grade IV and Grade V chapters.

DOES NOT COUNT:
- Rhetorical questions woven into running narrative prose with no banner.
- Teacher callout boxes (Note to the Teacher).
- Key-point or summary boxes.
- Poem or song text.

**Task object structure:**

```json
{
  "id": "T-1",
  "banner": "Activity",
  "task_text": "Tick and colour the activities that you see in your family",
  "page": 9
}
```

- `id`: sequential across the entire chapter, never reset per section
  (T-1, T-2 … T-N).
- `banner`: exactly one of — `Activity`, `Discuss`, `Write`, `Find out`,
  `Draw`, `Let us reflect — Write`, `Let us reflect — Draw`,
  `Let us reflect — Discuss`, `Let us reflect — Activity`.
- `task_text`: verbatim instruction text as it appears in the textbook.
  For a Discuss or Write bullet, copy the bullet text only, not the
  banner heading.
- `page`: page number where the task appears in the PDF.

## Step 4 — Chapter-level effort signals

Compute four signals for the whole chapter:

- `conceptual_demand` (integer 1–3): how abstract the chapter's reasoning
  is. 1 = concrete, immediate, tangible — observation, naming, comparison
  of familiar objects (typical Grade III); 2 = moderate abstraction —
  classification, material properties, simple cause-and-effect,
  community/regional context (typical Grade IV); 3 = multi-step reasoning
  or inference beyond direct observation — seasonal cycles, ecosystem
  interdependence, geological/astronomical/cultural-history abstraction
  (typical Grade V). Judge from the chapter's actual demand, not the grade
  alone — the grade ranges are guidance. (Scale aligned to the 1–3
  conceptual_demand used by all other subjects.)

- `task_load` (integer 0–3): discrete score derived from the total count
  of task objects across all sections (sum of all `tasks` array lengths):

  | Score | Total task count |
  |-------|-----------------|
  | 0     | Fewer than 10   |
  | 1     | 10–20           |
  | 2     | 21–30           |
  | 3     | More than 30    |

- `project_load` (integer 0/1/2): 0 = none; 1 = light (a multi-day
  observation, e.g. watch a plant grow over a week); 2 = substantial (an
  artefact-construction or sustained build project).

- `map_work` (integer 0/1/2): 0 = no maps; 1 = map reading; 2 = map
  drawing or regional comparison.

Effort index formula:
`effort_index = (conceptual_demand × 2) + (task_load × 2) + (project_load × 1.5) + map_work`

## Step 5 — Dual strand

Every TWAU chapter carries two intertwined, structurally primary strands.
Record both in a `dual_strand` object:

- `natural` — the natural phenomenon or life-science / earth-science concept.
- `human_cultural` — the human-cultural response to it: conservation
  practice, tradition, civic responsibility, or cultural diversity.

## Step 6 — Write summary JSON

```json
{
  "chapter_number": 7,
  "chapter_title": "Solids, Liquids and Gases",
  "grade": "iv",
  "sections": [
    {
      "title": "Section heading exactly as in textbook",
      "content_summary": "2-4 sentences: what the section teaches, key concepts, phenomena, examples.",
      "tasks": [
        {
          "id": "T-1",
          "banner": "Activity",
          "task_text": "Collect three objects from around you — one solid, one liquid, one gas — and describe each",
          "page": 52
        },
        {
          "id": "T-2",
          "banner": "Discuss",
          "task_text": "Which state of matter is air? How do you know?",
          "page": 53
        }
      ]
    }
  ],
  "conceptual_demand": 3,
  "task_load": 2,
  "project_load": 0,
  "map_work": 0,
  "effort_index": 10.0,
  "dual_strand": {
    "natural": "Properties and states of matter",
    "human_cultural": "Traditional and everyday uses of solids, liquids, gases"
  }
}
```

Rules:
- `grade` is the lowercase Roman numeral: `iii`, `iv`, or `v`.
- Every section appears in `sections` in textbook order.
- Task `id` values are sequential across the whole chapter (T-1, T-2 …
  T-N). The highest id number equals the total task count.
- `task_load` is the discrete score (0–3) derived from the total task
  count per the Step 4 table.
- `effort_index` is computed by the Step 4 formula (one decimal place).
- **No `unit` field. No `activity_count` field. No `dominant_cg_codes`
  field. No `chapter_weight` field. No `indian_knowledge_element` field.
  No C-codes anywhere in this file.**

## Step 7 — Confirmation line

After each chapter, print one line:

```
ch_07 — "Solids, Liquids and Gases" — sections: 5 — tasks: 24 — TL:2 CD:3 PL:0 MW:0 — EI:13.0
```

`tasks` is the raw total count of all task objects (sum of all `tasks`
array lengths across all sections). `TL` is the discrete task_load score.

Flag any chapter where `effort_index` = 0 as WARNING — the evidence base
was likely not located correctly in the PDF.

## Constraints

- No API calls. Cowork reads the PDF directly.
- Do not consult Learning Outcomes, Pedagogy, Syllabus, Assessment, or
  Position Papers.
- Anchor strictly to the chapter content; never supplement from training
  knowledge.
- Process chapters in the order specified. UTF-8. Overwrite if a summary
  already exists.
