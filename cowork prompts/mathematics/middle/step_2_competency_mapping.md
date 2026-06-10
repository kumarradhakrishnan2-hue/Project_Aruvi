# Cowork Session — Mathematics: Competency Mapping

Reads the chapter summary JSON and writes a mapping JSON per chapter,
governed by the Mathematics Mapping Constitution. **Middle stage, Grades
VI–VIII only** (preparatory uses the prompt in `../preparatory/`).

Summary MUST exist first (run `step_1_chapter_summary.md` in this folder).

## Run scope

Specify grade and chapter scope. Subject fixed to `mathematics`,
`stage = middle`.

## Paths

| Item | Path |
|------|------|
| Summary (input) | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |
| CG document | `mnt/data/mirror/framework/mathematics/middle/cg_middle_mathematics.txt` |
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/mathematics/middle/mapping_constitution_mathematics.txt` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json` |

## Procedure

For each chapter:

1. Load summary, CG document, constitution. If summary or any effort
   signal is missing, warn and skip.
2. Apply constitution Rules 1–6 exactly. Copy the raw signals
   (`conceptual_demand`, `activity_count`, `demo_count`, `exec_load`)
   verbatim from the summary. Per Rule 5, derive the discrete tiers
   `activity_load` (0–3) and `demo_load` (0–2) from the raw counts using
   the range tables, then compute `effort_index` with the harmonised
   formula `(CD×2) + (activity_load×2) + (demo_load×1.5) + (exec_load×2)`.
   Store both the raw counts and the derived tiers in the mapping JSON.

   **Justification writing rule:** Write each justification as natural prose that a
   teacher can read and immediately understand — as if explaining to a colleague
   why this competency fits. Draw on the actual topic names, activity descriptions,
   and learning contexts from the summary. For example: "The chapter's core work
   is on constructing and interpreting data displays — students collect information
   from their surroundings, organise it into bar graphs and pictographs, and draw
   conclusions from what they've made." Never use internal codes like S1, S2, T-7
   etc.; instead describe the section topic or activity directly in plain language.
3. Write mapping JSON per schema.
4. Verify the written file:
   - `core_cg` is a valid CG-N from the CG document
   - every `core_competencies.c_code` lies inside `core_cg`
   - every `adjunct_competencies.c_code` lies outside `core_cg`
   - |core| ≤ 2, |adjunct| ≤ 3
   - `dissolution_test` names an operation associated with `core_cg`
   - `activity_load` and `demo_load` are correctly tiered from the raw counts
   - `effort_index` matches the harmonised formula
   - raw signals (`conceptual_demand`, `activity_count`, `demo_count`,
     `exec_load`) match the summary
5. Confirmation line:
   `ch_05 | core_cg: CG-3 | core: C-3.2, C-3.4 | adjunct: C-6.1, C-9.2 | EI: 11.5`

At session end, list skipped chapters.

## Constraints

No PDF reads. Obey constitution's prohibited-documents rule. Process
chapters in order. UTF-8. Overwrite.
