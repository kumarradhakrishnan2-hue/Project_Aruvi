# Cowork Session — Science Grade VII: Effort Index Computation and Mapping File Load

## What this session does

The competency mapping for all 12 Grade VII Science chapters has been manually
verified and pre-authorised in a reference JSON. This session has one job:

1. Read each chapter PDF
2. Compute the four effort index signals per chapter
3. Write the chapter summary to mirror
4. Merge signals into the pre-authorised record and write the final mapping JSON

The competency fields (primary array, co_central, dissolution_test) are fixed.
Do not modify them.

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Pre-authorised reference JSON | mnt/data/mirror/chapters/science/grade_vii/mappings/grade_vii_science_mappings.json |
| Chapter PDFs | mnt/data/data/textbooks/science/grade_vii/ |
| Chapter summaries output | mnt/data/mirror/chapters/science/grade_vii/summaries/ |
| Mapping output (per chapter) | mnt/data/mirror/chapters/science/grade_vii/mappings/ |
| Consolidated output | mnt/data/mirror/chapters/science/grade_vii/mappings/chapter_mappings_science_vii.json |

---

## Step 1 — Load the pre-authorised reference

Read grade_vii_science_mappings.json. This contains 12 records. For each record
the competency fields are fixed. The effort index fields (conceptual_demand,
activity_count, demo_count, exec_load, effort_index) are set to 0 and must be
replaced with computed values.

---

## Step 2 — For each chapter (1 through 12), process the PDF

### 2a — Locate the PDF

Match chapter number to the file in data/textbooks/science/grade_vii/.
Files are named: Chapter NN - Title.pdf

### 2b — Identify the evidence base

Read the full chapter PDF. The evidence base comprises exactly four elements:

(a) Embedded student activities — boxed tasks labelled "Let us explore /
    investigate / construct / experiment" and equivalents. Classify each as
    student-executed or teacher-demonstrated.

(b) End-of-chapter exercises — the "Let Us Enhance Our Learning" section
    or equivalent.

(c) Embedded diagram tasks — questions placed beneath body-text figures
    requiring the student to read or reason from the diagram.

(d) Body-text thought prompts — italicised questions or "can you think of"
    invitations in the explanatory text.

Exclude: explanatory prose with no student task. Sidebar boxes with no student task.

### 2c — Compute the four signals

conceptual_demand (integer 1–3):
  1 = recall and familiar-context questions dominate the exercise (>60%)
  2 = causal explanation or application to familiar context dominates,
      or demand is evenly spread
  3 = unfamiliar-context transfer, multi-step causal chain reasoning, or
      investigative design questions constitute 30% or more of the exercise

activity_count (integer):
  Count student-executed physical activities only.
  Exclude teacher demonstrations and discussion-only tasks.

demo_count (integer):
  Count teacher-performed demonstrations only.

exec_load (integer 0–2):
  0 = exercise is predominantly written reasoning
  1 = multi-step calculation or diagram production is 30–60% of questions
  2 = >60%

effort_index (number):
  (conceptual_demand × 2) + (activity_count × 1) + (demo_count × 1.5) + (exec_load × 2)

### 2d — Write the chapter summary

Write a chapter summary of 600–900 words mirroring the textbook's section
headings in order. The summary describes what the chapter teaches — its concepts,
phenomena, and content organisation. It notes the existence of activities without
elaborating them. It does not describe exercises.

Save to: mnt/data/mirror/chapters/science/grade_vii/summaries/ch_NN_summary.txt
(NN = zero-padded chapter number, e.g. ch_02_summary.txt)

---

## Step 3 — Merge and write the final mapping JSON

For each chapter:
1. Take the pre-authorised record from grade_vii_science_mappings.json
2. Replace the five effort index fields with the computed values
3. Set summary_path to: mirror/chapters/science/grade_vii/summaries/ch_NN_summary.txt
4. Write the final record to:
   mnt/data/mirror/chapters/science/grade_vii/mappings/ch_NN_mapping.json

Do not modify any other field.

---

## Step 4 — Write the consolidated mappings file

After all 12 chapters are processed, write all 12 records as a JSON array to:
  mnt/data/mirror/chapters/science/grade_vii/mappings/chapter_mappings_science_vii.json

This is the file the Planning Tool reads for period allocation across the grade.

---

## Step 5 — Print verification summary

Print this table to console on completion:

Ch | Title (40 chars)                         | CD | AC | DC | EL | EI
---|------------------------------------------|----|----|----|----|---------
01 | The Ever-Evolving World of Science       |  x |  x |  x |  x |   x.x
...

CD = conceptual_demand, AC = activity_count, DC = demo_count,
EL = exec_load, EI = effort_index

Flag any chapter where effort_index = 0 as a WARNING — this likely means
the evidence base was not located correctly in the PDF.

---

## Constraints

- Do not call the Claude API. All competency mapping is pre-authorised.
- Do not modify primary, co_central, dissolution_test, or any non-effort-index field.
- Process chapters in order 1 through 12.
- If a chapter PDF is not found, log a warning and skip — do not halt.
- All files written in UTF-8 encoding.
