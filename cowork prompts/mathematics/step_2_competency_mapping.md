# Cowork Session — Mathematics: Competency Mapping

Reads the chapter summary JSON and writes a mapping JSON per chapter,
governed by the Mathematics Mapping Constitution. Works across all stages.

Summary MUST exist first (run `chapter_summary_mathematics.md`).

## Run scope

Specify grade and chapter scope. Subject fixed to `mathematics`.
`{stage}` derives from grade.

## Paths

| Item | Path |
|------|------|
| Summary (input) | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |
| CG document | `mnt/data/mirror/framework/mathematics/{stage}/cg_{stage}_mathematics.txt` |
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/mathematics/mapping_constitution_mathematics.txt` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json` |

## Procedure

For each chapter:

1. Load summary, CG document, constitution. If summary or any effort
   signal is missing, warn and skip.
2. Apply constitution Rules 1–6 exactly. Copy the four effort signals
   verbatim. Compute `effort_index` using Maths weights.
3. Write mapping JSON per schema.
4. Verify the written file:
   - `core_cg` is a valid CG-N from the CG document
   - every `core_competencies.c_code` lies inside `core_cg`
   - every `adjunct_competencies.c_code` lies outside `core_cg`
   - |core| ≤ 2, |adjunct| ≤ 3
   - `dissolution_test` names an operation associated with `core_cg`
   - `effort_index` matches the formula
   - signals match the summary
5. Confirmation line:
   `ch_05 | core_cg: CG-3 | core: C-3.2, C-3.4 | adjunct: C-6.1, C-9.2 | EI: 13.5`

At session end, list skipped chapters.

## Constraints

No PDF reads. Obey constitution's prohibited-documents rule. Process
chapters in order. UTF-8. Overwrite.
