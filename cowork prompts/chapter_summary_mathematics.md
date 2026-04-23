# Cowork Session — Mathematics: Chapter Summary Generation

## What this session does

Reads one or more Mathematics chapter PDFs (NCERT *Ganita Prakash* or its
grade-appropriate equivalent) and writes a structured chapter summary JSON
for each. The summary is the content reference used by:

- the Mathematics competency mapping session
- the runtime lesson plan generation (period bin-packing + item distribution)
- the runtime assessment generation (three-section architecture)

The Mathematics summary is **richer than the Science / Social-Sciences
summary** because the Mathematics pipeline has no separate effort-index
prompt — the four effort signals are computed here — and because the LP
and assessment generators read enumerated items (with icons) directly from
the summary.

This session uses Cowork's own context to read the PDF and write the
summary. No API call is made.

---

## Run Scope

Specify which chapters to process at the start of the session:

```
Single chapter  : process chapter 5 only
Multiple        : process chapters 1, 5, 6
All chapters    : process all chapters in the textbook folder
```

Tell Cowork the grade and chapter scope before starting. Subject is
fixed to `mathematics` for this prompt.

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Chapter PDFs | mnt/data/knowledge_commons/textbooks/mathematics/{grade}/ |
| Summary output | mnt/data/mirror/chapters/mathematics/{grade}/summaries/ |

Files are named: `Chapter NN - Title.pdf` (e.g. `Chapter 05 - Parallel and
Intersecting Lines.pdf`).
Output files are named: `ch_NN_summary.json` (e.g. `ch_05_summary.json`).

---

## Step 1 — Locate the PDF

Match each requested chapter number to the correct file in the textbook
folder. If a requested chapter's PDF is not found, log a warning and
skip that chapter — do not halt.

---

## Step 2 — Extract chapter title

Read the chapter title exactly as it appears in the PDF (typically the
opening page). Record it verbatim — do not paraphrase or normalise
casing. This title is written as the `chapter_title` field in the
output JSON.

---

## Step 3 — Identify scope boundary (sections and subsections)

Read the full chapter PDF. List every section (§N) and subsection
(§N.M) heading present, in the order they appear. This heading list is
the **scope boundary** for the summary.

No concept, activity, worked example, or exercise may appear in the
summary unless it is anchored to one of these headings. This rule is
absolute — it prevents content from outside this chapter appearing in
the summary even if the topic is familiar.

---

## Step 4 — Identify the three item classes

Read the chapter end-to-end and inventory these three item classes,
preserving the textbook's authored order within each class:

### 4a — Enumerated activities

Boxed or clearly labelled hands-on tasks that the student executes in
class: constructions (compass-and-straightedge or paper-folding), grid
or dot-paper explorations, measurement tasks, tile arrangements, board
games, sorting-by-property tasks, and the like. Named sequences such as
"Activity 1", "Activity 2" are activities. An activity may appear mid-
section (embedded) or at a section boundary.

For each activity record: an id (`A-1`, `A-2`, ...), the `source_section`
it sits in (e.g. `§5.3`), and a one-line `description` of what the
student does.

### 4b — Enumerated worked examples

Worked-out solved problems presented by the textbook — typically
labelled "Example 1", "Example 2", or shown with a worked solution in
the body. These are teacher-walkthrough items, not student exercises.

For each worked example record: an id (`WE-1`, `WE-2`, ...), the
`source_section`, and a one-line `description` of the problem solved.

### 4c — Enumerated exercises (with icon)

Every student exercise in the chapter body. Ganita Prakash marks each
exercise with one of three author-provided icons:

- **Figure it Out (FIO)** — computational / applicational practice.
- **Math Talk (MT)** — discussion / explain / justify / compare.
- **Try This (TT)** — non-routine / exploratory / extension.

The icon appears as a small graphic next to the exercise label. Read
the icon from the PDF and tag each exercise accordingly.

For each exercise record: an id (`E-1`, `E-2`, ...), the
`source_section`, the `icon` (exactly one of `"FIO"`, `"MT"`, `"TT"`),
and a one-line `description` of what the exercise asks.

**Exclude**: end-of-chapter summaries, key-point boxes, and body-text
thought prompts that are not labelled as exercises or activities.

---

## Step 5 — Write the prose summary

Write a `prose_summary` of 800 – 1200 words addressing every section and
subsection identified in Step 3, in the order they appear.

For each section write 2 – 4 sentences covering:

- What the section teaches.
- The key concepts, definitions, or properties it introduces.
- Any significant construction, theorem, or representation it uses.
- Whether the section contains a student activity — note existence
  only; full activity detail is already captured in `enumerated_activities`.

**Rules:**

- Use the textbook's own section and subsection headings as the
  organising structure. Do not rename, merge, or reorder them.
- Do not describe end-of-chapter exercises inside the prose summary;
  they live in `enumerated_exercises`.
- Do not introduce content from outside this chapter. If you find
  yourself writing about something the chapter does not cover, stop
  and delete it.
- Write in plain prose. No bullet points. No tables inside
  `prose_summary`.
- Output summary text only — no preamble, no word count statement.

---

## Step 6 — Compute representation_index

`representation_index` is a visual-density signal: the ratio of visual
elements in the chapter to the number of sections.

- Numerator: total count of figures, diagrams, worked constructions,
  tables, and in-chapter grid/dot/number-line illustrations.
- Denominator: total count of sections and subsections from Step 3.

Report as a float to one decimal place. Example: 18 visual elements
across 6 sections → `3.0`.

---

## Step 7 — Compute the four effort signals

### 7a — conceptual_demand (integer 1 – 3)

Based on the mix of questions in `enumerated_exercises`:

- **1** = recall, direct-formula-application, or familiar-context
  questions dominate (> 60 %).
- **2** = reasoning, multi-step application, or comparison across
  familiar contexts dominates — OR demand is evenly spread.
- **3** = unfamiliar-context transfer, proof-style reasoning,
  multi-step construction, or open-ended problem-posing questions
  constitute 30 % or more of the exercises.

### 7b — activity_count (integer)

Count `enumerated_activities` that are **student-executed**:
hands-on tasks the student performs. Exclude items that are purely
teacher-demonstrated or discussion-only.

### 7c — demo_count (integer)

Count items that are **teacher-demonstrated only** — a construction
or manipulation the teacher performs while the class observes. In
Mathematics this count is typically low (0 – 2 per chapter); most
activities are student-executed.

### 7d — exec_load (integer 0 – 2)

Weight of multi-step computation or multi-step construction in the
exercise set:

- **0** = exercise set is predominantly written reasoning or single-step.
- **1** = multi-step calculation or multi-step construction is
  30 – 60 % of exercises.
- **2** = > 60 %.

---

## Step 8 — Write the summary JSON

Assemble and write the output JSON to:

`mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json`

(NN = zero-padded chapter number, e.g. `ch_05_summary.json`.)

### Schema

```json
{
  "stage":          "middle",
  "subject":        "mathematics",
  "grade":          "vii",
  "chapter_number": 5,
  "chapter_title":  "Parallel and Intersecting Lines",

  "sections": ["§5.1", "§5.2", "§5.3", "§5.4", "§5.5"],

  "prose_summary": "<800–1200 word section-by-section prose>",

  "enumerated_activities": [
    {
      "id":             "A-1",
      "source_section": "§5.2",
      "description":    "Fold a paper strip to produce two parallel creases and measure the angles formed by a transversal."
    }
  ],

  "enumerated_worked_examples": [
    {
      "id":             "WE-1",
      "source_section": "§5.3",
      "description":    "Find the angles marked x and y when two parallel lines are cut by a transversal."
    }
  ],

  "enumerated_exercises": [
    {
      "id":             "E-1",
      "source_section": "§5.3",
      "icon":           "FIO",
      "description":    "Compute the missing angle in each of the given figures."
    },
    {
      "id":             "E-2",
      "source_section": "§5.3",
      "icon":           "MT",
      "description":    "Explain why alternate interior angles are equal when two lines are parallel."
    },
    {
      "id":             "E-3",
      "source_section": "§5.4",
      "icon":           "TT",
      "description":    "Can you construct a parallelogram given only the lengths of its diagonals? Justify."
    }
  ],

  "representation_index": 3.0,

  "conceptual_demand": 2,
  "activity_count":    5,
  "demo_count":        1,
  "exec_load":         1
}
```

### Field rules

| Field | Source | Rule |
|-------|--------|------|
| `stage` | Grade mapping | III–V → `"foundational"`; VI–VIII → `"middle"`; IX–X → `"secondary"` |
| `subject` | Fixed | Always `"mathematics"` for this prompt |
| `grade` | Run scope | Lowercase Roman numeral (`"vi"`, `"vii"`, `"viii"`) |
| `chapter_number` | Filename | Integer, no leading zero |
| `chapter_title` | PDF title page | Verbatim from the chapter opening |
| `sections` | Step 3 | All § headings in textbook order |
| `prose_summary` | Step 5 | 800 – 1200 words |
| `enumerated_activities` | Step 4a | All items; may be `[]` |
| `enumerated_worked_examples` | Step 4b | All items; may be `[]` |
| `enumerated_exercises` | Step 4c | All items with icon; MUST NOT be `[]` for a normal chapter |
| `representation_index` | Step 6 | Float, one decimal place |
| `conceptual_demand` | Step 7a | Integer 1 – 3 |
| `activity_count` | Step 7b | Integer ≥ 0 |
| `demo_count` | Step 7c | Integer ≥ 0 |
| `exec_load` | Step 7d | Integer 0 – 2 |

Every enumerated item MUST point to a `source_section` that appears in
the `sections` list. No item may be orphaned.

Icons on exercises MUST be exactly one of `"FIO"`, `"MT"`, `"TT"` —
case-sensitive. The system MUST NOT invent or adapt icon labels.

---

## Step 9 — Verification summary

After writing each summary, print one confirmation line:

```
ch_05_summary.json — written — "Parallel and Intersecting Lines" — 1 042 words — sections: 5.1, 5.2, 5.3, 5.4, 5.5 — activities: 5 — worked_examples: 3 — exercises: 14 (FIO:8, MT:4, TT:2) — CD:2 AC:5 DC:1 EL:1 RI:3.0
```

Flag any chapter where `enumerated_exercises` is empty as **WARNING** —
the three-icon evidence base was likely not located correctly in the
PDF.

If any chapter PDF is not found, log a warning and skip — do not halt.

---

## Constraints

- Do not call the Claude API. Cowork reads the PDF directly.
- Do not generate competency mappings or the composite effort_index —
  those are produced by `competency_mapping_mathematics.md`.
- Do not modify any existing mapping JSON.
- Do not consult Learning Outcomes, Pedagogy documents, Syllabus
  documents, Assessment Framework documents, or Position Papers —
  none of these informs the summary.
- Process chapters in the order specified.
- All files written in UTF-8 encoding.
- If a summary file already exists for a chapter, overwrite it.
