# Cowork Session — The World Around Us: Chapter Summary

Reads a TWAU (The World Around Us) chapter PDF and writes a structured
summary JSON. Cowork reads the PDF and writes the file directly. No API
call is made.

The summary is grounded content extraction ONLY: what the chapter contains,
what activities are present, and the chapter's effort profile. 

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
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/The World Around Us/{grade}/` |
| Output | `mnt/data/mirror/chapters/The World Around Us/{grade}/summaries/ch_NN_summary.json` |

`{grade}` is the lowercase Roman numeral folder: `iii`, `iv`, or `v`.
Note the folder spelling: textbooks and chapters use `The World Around Us`
(lowercase s). Preserve it exactly.

## Step 1 — Title and sections

Extract the chapter title verbatim from the opening page. List every named
section heading in textbook reading order. This is the summary's single
structural axis — the lesson plan will later walk these sections in order.
Nothing below may reference a heading not in this list.

Also record the unit the chapter belongs to: `Unit N: Unit Name` exactly as
printed in the textbook contents/unit divider.

## Step 2 — Per-section capture

For each named section, in textbook order, record:

- `title` — the section heading exactly as in the textbook.
- `content_summary` — 2 to 4 sentences covering what the section teaches:
  key concepts, the natural phenomenon, the human-cultural practice, and any
  concrete examples. Indian Knowledge System (IKS) content — traditional
  practices, local vessels, seasonal knowledge, folk conservation — is
  captured **here, inside `content_summary`**, where the textbook places it.
  
- `named_activities` — array of the names of hands-on activities in this
  section (see the definition in Step 3). Empty array `[]` if the section
  has none.

Anchor every sentence to what is actually in the chapter. Never supplement
from training knowledge or general subject knowledge.

## Step 3 — What counts as a "named hands-on activity"

Precise definition (this drives `activity_count`, so count consistently):

COUNTS — a discrete, named task that asks the student to DO something:
- imperative-verb headings: "Make a…", "Find out…", "Let us do…",
  "Let us observe…", "Collect…", "Draw…", "Try this…"
- boxed action prompts, observation tasks, field walks, experiments,
  art-integration / construction tasks, surveys, interviews.

DOES NOT COUNT:
- discussion questions, "Let us discuss / think / talk about" prose prompts
- comprehension or recall questions woven into body text
- end-of-chapter written exercises that are not a hands-on task
- teacher callouts, summaries, key-point boxes.

When in doubt, ask: does this require the student to physically observe,
make, collect, measure, or construct something? If yes, it counts.

## Step 4 — Chapter-level effort signals

Compute four signals for the whole chapter:

- `conceptual_demand` (integer 1–5): how abstract the chapter's reasoning is.
  1 = concrete, immediate, tangible (typical Grade III: water sources, food,
  hygiene); 3 = classification, material properties, community context
  (typical Grade IV); 5 = geological, astronomical, or cultural-history
  abstraction (typical Grade V). Judge from the chapter's actual demand, not
  the grade alone — the grade ranges are guidance.
- `activity_count` (integer): total named hands-on activities (Step 3
  definition) across all sections. Must equal the sum of the
  `named_activities` array lengths.
- `project_load` (integer 0/1/2): 0 = none; 1 = light (a multi-day
  observation, e.g. watch a plant grow over a week); 2 = substantial (an
  artefact-construction or sustained build project).
- `map_work` (integer 0/1/2): 0 = no maps; 1 = map reading; 2 = map drawing
  or regional comparison.

Effort index:
`effort_index = (conceptual_demand × 3) + activity_count + (project_load × 1.5) + map_work`

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
  "unit": "Unit 4: Things Around Us",
  "sections": [
    {
      "title": "Section heading exactly as in textbook",
      "content_summary": "2-4 sentences: what the section teaches, key concepts, phenomena, examples.",
      "named_activities": ["Activity name 1", "Activity name 2"]
    }
  ],
  "activity_count": 6,
  "conceptual_demand": 3,
  "project_load": 0,
  "map_work": 0,
  "effort_index": 15.0,
  "dual_strand": {
    "natural": "Properties and states of matter",
    "human_cultural": "Traditional and everyday uses of solids, liquids, gases"
  }
}
```

Rules:
- `grade` is the lowercase Roman numeral: `iii`, `iv`, or `v`.
- Every section appears in `sections` in textbook order.
- `activity_count` equals the total of all `named_activities` lengths.
- `effort_index` is computed by the Step 4 formula (one decimal place).
- **No `dominant_cg_codes` field. No `chapter_weight` field. No
  `indian_knowledge_element` field. No C-codes anywhere in this file.**

## Step 7 — Confirmation line

After each chapter, print one line:

```
ch_07 — "Solids, Liquids and Gases" — sections: 5 — activities: 6 — CD:3 PL:0 MW:0 — EI:15.0
```

Flag any chapter where `effort_index` = 0 as WARNING — the evidence base was
likely not located correctly in the PDF.

## Constraints

- No API calls. Cowork reads the PDF directly.
- Do not consult Learning Outcomes, Pedagogy, Syllabus, Assessment, or
  Position Papers.
- Anchor strictly to the chapter content; never supplement from training
  knowledge.
- Process chapters in the order specified. UTF-8. Overwrite if a summary
  already exists.
