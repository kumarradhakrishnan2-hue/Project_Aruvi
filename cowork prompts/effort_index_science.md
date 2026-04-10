# Cowork Session — Science: Effort Index Computation

## What this session does

Reads one or more Science chapter PDFs, computes the four effort index
signals per chapter, and merges them into the pre-authorised mapping
record. Competency fields and chapter summaries are handled by separate
sessions and must not be touched here.

This session uses Cowork's own context to read the PDF and compute
signals. No API call is made.

---

## Run Scope

Specify which chapters to process at the start of the session:

```
Single chapter  : process chapter 9 only
Multiple        : process chapters 1, 4, 8
All chapters    : process all chapters for this grade
```

Tell Cowork the grade and chapter scope before starting.

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Pre-authorised reference JSON | mnt/data/mirror/chapters/science/{grade}/mappings/grade_{grade}_science_mappings.json |
| Chapter PDFs | mnt/data/knowledge_commons/textbooks/science/{grade}/ |
| Mapping output (per chapter) | mnt/data/mirror/chapters/science/{grade}/mappings/ch_NN_mapping.json |
| Consolidated output | mnt/data/mirror/chapters/science/{grade}/mappings/chapter_mappings_science_{grade}.json |

---

## Step 1 — Load the pre-authorised reference

Read `grade_{grade}_science_mappings.json`. Each record contains fixed
competency fields and effort index fields currently set to 0. Only the
five effort index fields will be replaced:
`conceptual_demand`, `activity_count`, `demo_count`, `exec_load`, `effort_index`

Do not modify any other field.

---

## Step 2 — For each chapter, process the PDF

### 2a — Locate the PDF

Match chapter number to the file in `knowledge_commons/textbooks/science/{grade}/`.
Files are named: `Chapter NN - Title.pdf`

### 2b — Identify the evidence base

Read the full chapter PDF. The evidence base comprises exactly four elements:

**(a) Embedded student activities** — boxed tasks labelled "Let us explore /
investigate / construct / experiment" and equivalents. Classify each as
student-executed or teacher-demonstrated.

**(b) End-of-chapter exercises** — the "Let Us Enhance Our Learning" section
or equivalent.

**(c) Embedded diagram tasks** — questions placed beneath body-text figures
requiring the student to read or reason from the diagram.

**(d) Body-text thought prompts** — italicised questions or "can you think of"
invitations in the explanatory text.

Exclude: explanatory prose with no student task. Sidebar boxes with no
student task.

### 2c — Compute the four signals

**conceptual_demand (integer 1–3):**
- 1 = recall and familiar-context questions dominate the exercise (>60%)
- 2 = causal explanation or application to familiar context dominates,
      or demand is evenly spread
- 3 = unfamiliar-context transfer, multi-step causal chain reasoning, or
      investigative design questions constitute 30% or more of the exercise

**activity_count (integer):**
Count student-executed physical activities only.
Exclude teacher demonstrations and discussion-only tasks.

**demo_count (integer):**
Count teacher-performed demonstrations only.

**exec_load (integer 0–2):**
- 0 = exercise is predominantly written reasoning
- 1 = multi-step calculation or diagram production is 30–60% of questions
- 2 = >60%

**effort_index (number):**
`(conceptual_demand × 2) + (activity_count × 1) + (demo_count × 1.5) + (exec_load × 2)`

---

## Step 3 — Merge and write the mapping JSON

For each chapter:
1. Take the pre-authorised record from the reference JSON
2. Replace the five effort index fields with computed values
3. Write the updated record to:
   `mnt/data/mirror/chapters/science/{grade}/mappings/ch_NN_mapping.json`

Do not modify any other field.

---

## Step 4 — Write the consolidated mappings file

After all specified chapters are processed, merge all per-chapter
mapping files into a single JSON array and write to:
`mnt/data/mirror/chapters/science/{grade}/mappings/chapter_mappings_science_{grade}.json`

---

## Step 5 — Print verification summary

```
Ch | Title (40 chars)                         | CD | AC | DC | EL | EI
---|------------------------------------------|----|----|----|----|---------
09 | Life Processes in Animals                |  x |  x |  x |  x |   x.x
```

CD = conceptual_demand, AC = activity_count, DC = demo_count,
EL = exec_load, EI = effort_index

Flag any chapter where effort_index = 0 as WARNING — evidence base
was likely not located correctly in the PDF.

---

## Constraints

- Do not call the Claude API. Cowork reads the PDF directly.
- Do not modify primary, co_central, dissolution_test, chapter_summary,
  or any non-effort-index field.
- Do not generate or overwrite chapter summaries.
- If a chapter PDF is not found, log a warning and skip — do not halt.
- All files written in UTF-8 encoding.
