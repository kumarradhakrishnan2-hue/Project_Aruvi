# Cowork Session — Mathematics: Competency Mapping + Effort Index

## What this session does

Reads one or more Mathematics chapter summary JSONs from mirror, the NCF
Mathematics Curricular Goals document, and the Mathematics Competency
Mapping Constitution, and writes one mapping JSON per chapter.

Two tasks are combined in this single session, per the Mathematics
pipeline:

1. **Competency mapping** — three-pass procedure (CG-blind summary
   reading → core CG and core competencies within it →
   cross-CG adjunct scan) per the Mathematics Mapping Constitution.
2. **Effort index composite** — copy the four effort signals from the
   summary JSON and compute the composite using Mathematics weights.

Chapter summary JSONs MUST already exist in mirror before this session
runs. Run `chapter_summary_mathematics.md` first if they are absent.

This session uses Cowork's own context. No API call is made.
No scripts from aruvi-scripts/ are invoked.

---

## Run Scope

Specify grade and chapter scope at the start of the session. Subject is
fixed to `mathematics` for this prompt.

```
Single chapter  : map chapter 5 only
Multiple        : map chapters 1, 5, 6
All chapters    : map all chapters for this grade
```

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Chapter summary (input) | mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json |
| Curricular Goals (input) | mnt/data/mirror/framework/mathematics/{stage}/cg_{stage}_mathematics.txt |
| Competency descriptions (input, optional) | mnt/data/mirror/framework/mathematics/{stage}/competency_descriptions_{stage}.json |
| Mapping constitution (input) | mnt/data/mirror/constitutions/competency_mapping/mathematics/mapping_constitution_mathematics.txt |
| Mapping output (per chapter) | mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json |

The `{stage}` value in CG and competency-description filenames maps from
grade: III–V → `foundational`; VI–VIII → `middle`; IX–X → `secondary`.

---

## Step 1 — Load inputs

For each chapter:

1. Read `ch_NN_summary.json` — this is the sole chapter content
   reference. Do NOT read the chapter PDF.
2. Read `cg_{stage}_mathematics.txt` from `mirror/framework/mathematics/` —
   the Curricular Goals reference (CG-1 through CG-9 with their C-codes).
3. Read the Mathematics mapping constitution from mirror.

If `ch_NN_summary.json` is absent, log a warning and skip that
chapter. Do not attempt to generate the summary here — run
`chapter_summary_mathematics.md` first.

The summary JSON MUST contain the four effort signals
(`conceptual_demand`, `activity_count`, `demo_count`, `exec_load`). If
any signal is missing, log a warning and skip.

---

## Step 2 — Apply the mapping constitution (three passes)

Apply the Mathematics Competency Mapping Constitution exactly. The
constitution is the governing document — all mapping decisions MUST
follow its rules without exception.

### 2a — Pass 1: Chapter summary reading (CG-blind)

Read the summary JSON in full: `prose_summary`, `enumerated_activities`,
`enumerated_worked_examples`, and `enumerated_exercises` (with icons).
At this pass, do NOT open the CG document. Do NOT pattern-match C-codes
against the text.

### 2b — Pass 2: Core CG identification and core competency selection

Open `cg_{stage}_mathematics.txt`. Read only CG-level headings and
descriptions. Select the single CG whose description best matches the
chapter's organising purpose.

All NINE CGs are eligible as `core_cg`. Both content CGs (CG-1 Number
Sense, CG-2 Algebra, CG-3 Geometry, CG-4 Measurement, CG-5 Data
Handling) and process CGs (CG-6 Reasoning, CG-7 Creativity, CG-8
Computational Thinking, CG-9 History) may legitimately land as
`core_cg`. A chapter whose central organising purpose is puzzle-solving
may land CG-7; a chapter built around systematic counting may land
CG-8.

Lock the selected CG as `core_cg`. No further CG-level comparison.

Open only the C-codes under the locked `core_cg`. Select up to TWO
`core_competencies` whose definitions the chapter substantively
addresses. A second competency requires justification from a distinct
strand of the chapter — not as a vehicle for or sub-step of the first.
If no second competency independently qualifies, stop at one.

For each core competency record:

- `c_code`
- `justification` — one to two sentences citing the section(s) or
  enumerated item(s) of the summary that substantively address this
  competency.

### 2c — Pass 3: Adjunct competency scan (cross-CG)

Scan C-codes across all CGs OTHER THAN `core_cg`. Select up to THREE
`adjunct_competencies` whose definitions the chapter substantively
engages but which are not the chapter's central organising purpose.

Adjunct selection criterion: the chapter MUST contain at least one
named section, enumerated activity, enumerated worked example, or
enumerated exercise that requires the student to perform the specific
cognitive operation the adjunct competency defines. Shared vocabulary,
passing mention, or incidental appearance is INSUFFICIENT.

If fewer than three adjunct competencies qualify under the criterion,
stop at the number that qualify. Do NOT pad the list.

For each adjunct competency record:

- `c_code`
- `justification` — one to two sentences citing the section(s) or
  enumerated item(s) of the summary that substantively engage this
  competency.

### 2d — Dissolution test

Write the dissolution test sentence in the form:

> "This chapter builds the student's ability to [verb] [object] by
> [cognitive mechanism]."

The sentence MUST name the operation associated with `core_cg` and its
`core_competencies`. Adjunct competencies MUST NOT drive the
dissolution test.

**Prohibited documents for Mathematics mapping** (per constitution Rule 6):
Learning Outcomes, Pedagogy documents, Syllabus documents, Assessment
Framework documents, Position Papers. The only external document the
mapping procedure consults is the Curricular Goals document.

---

## Step 3 — Compute the composite effort_index (Mathematics weights)

Copy the four effort signals verbatim from the summary JSON. Do NOT
re-adjudicate any signal. Compute the composite using the Mathematics
weights:

```
effort_index = (conceptual_demand × 2)
             + (activity_count    × 1.5)
             + (demo_count        × 1)
             + (exec_load         × 2)
```

Sum of weights = 6.5. This matches the Science composite's weight sum
so that effort indices are cross-subject-comparable in the Allocate
tab. The Mathematics redistribution (activity_count 1 → 1.5,
demo_count 1.5 → 1) reflects Mathematics's higher reliance on
student-executed practice and lower reliance on teacher demonstration
relative to Science.

Report `effort_index` as a number with one decimal place.

---

## Step 4 — Write the mapping JSON

Write one JSON record per chapter to:

`mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json`

### Schema

```json
{
    "stage":          "middle",
    "subject":        "mathematics",
    "grade":          "vii",
    "chapter_number": 5,
    "chapter_title":  "Parallel and Intersecting Lines",

    "core_cg": "CG-3",

    "core_competencies": [
        {
            "c_code":        "C-3.2",
            "justification": "The chapter's central activity develops properties of angles formed by intersecting and parallel lines, exercised through construction and reasoning tasks across §5.2–§5.4."
        },
        {
            "c_code":        "C-3.4",
            "justification": "A dedicated strand of the chapter builds compass-and-straightedge construction of parallel lines and perpendiculars, with graded construction exercises distinct from the angle-property progression."
        }
    ],

    "adjunct_competencies": [
        {
            "c_code":        "C-6.1",
            "justification": "Math Talk items in §5.3 and §5.4 require the student to justify angle equalities through deductive argument, engaging the reasoning competency."
        },
        {
            "c_code":        "C-9.2",
            "justification": "The chapter references Baudhayana's geometric constructions from the Sulba-Sutras, engaging the historical-contributions competency."
        }
    ],

    "dissolution_test": "This chapter builds the student's ability to identify, justify, and construct relationships between parallel and intersecting lines by applying angle properties at their intersections.",

    "conceptual_demand": 2,
    "activity_count":    5,
    "demo_count":        1,
    "exec_load":         1,
    "effort_index":      13.5
}
```

### Field sourcing rules

| Field | Source | Rule |
|-------|--------|------|
| `stage` | Grade mapping | III–V → `"foundational"`; VI–VIII → `"middle"`; IX–X → `"secondary"` |
| `subject` | Fixed | Always `"mathematics"` |
| `grade` | Run scope | Lowercase Roman numeral (`"vi"`, `"vii"`, `"viii"`) |
| `chapter_number` | Summary JSON | Copy verbatim |
| `chapter_title` | Summary JSON | Copy verbatim |
| `core_cg` | Pass 2 | String in form `"CG-N"` |
| `core_competencies` | Pass 2 | Array of 1 – 2 objects, each `{c_code, justification}` |
| `adjunct_competencies` | Pass 3 | Array of 0 – 3 objects, each `{c_code, justification}` |
| `dissolution_test` | Pass 2d | Single sentence |
| `conceptual_demand` | Summary JSON | Copy verbatim |
| `activity_count` | Summary JSON | Copy verbatim |
| `demo_count` | Summary JSON | Copy verbatim |
| `exec_load` | Summary JSON | Copy verbatim |
| `effort_index` | Step 3 | Computed float, one decimal place |

### Post-write verification (mandatory)

After writing the JSON file, read it back and confirm:

1. `core_cg` is exactly one of `CG-1` … `CG-9`.
2. Every `c_code` in `core_competencies` lies WITHIN `core_cg`.
3. Every `c_code` in `adjunct_competencies` lies OUTSIDE `core_cg`.
4. `|core_competencies| ≤ 2` and `|adjunct_competencies| ≤ 3`.
5. `dissolution_test` names an operation associated with `core_cg`.
6. `effort_index` equals
   `(CD × 2) + (AC × 1.5) + (DC × 1) + (EL × 2)` of the four signals.
7. The four signals match those in the summary JSON exactly.

If any check fails, overwrite the file with corrected values before
proceeding to the next chapter.

---

## Step 5 — Print verification summary

After each chapter, print one confirmation line:

```
ch_05 | Parallel and Intersecting Lines | core_cg: CG-3 | core: C-3.2, C-3.4 | adjunct: C-6.1, C-9.2 | CD:2 AC:5 DC:1 EL:1 EI:13.5
```

If any summary was missing, list all skipped chapters at the end.

---

## Constraints

- Do not read chapter PDFs. The chapter summary JSON is the sole
  content input.
- Do not consult Learning Outcomes, Pedagogy documents, Syllabus
  documents, Assessment Framework documents, or Position Papers —
  constitutionally prohibited (see Rule 6 of the constitution).
- Do not call the Claude API. Cowork reads all inputs directly.
- Do not invoke any scripts from aruvi-scripts/.
- Do not re-adjudicate the four effort signals — copy them verbatim
  from the summary.
- Process chapters in the order specified.
- All files written in UTF-8 encoding.
- If a mapping file already exists for a chapter, overwrite it.
