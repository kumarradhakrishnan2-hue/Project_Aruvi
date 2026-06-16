# Cowork Session — Mathematics: Competency Mapping (Secondary Stage)

Reads the chapter summary JSON and writes a mapping JSON per chapter,
governed by the Mathematics Competency Mapping Constitution (Secondary).

The summary MUST exist first — run `step_1_chapter_summary.md` in this folder.

## Run scope

Tell Cowork the grade and chapter scope before starting. Subject is
`mathematics`, stage is `secondary`.

```
Single chapter  : process chapter 2 only
Multiple        : process chapters 2, 5, 7
All chapters    : process every chapter with a summary
```

## Paths

| Item | Path |
|------|------|
| Summary (input) | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |
| CG document | `mnt/data/mirror/framework/mathematics/secondary/cg_secondary_mathematics.txt` |
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/mathematics/secondary/mapping_constitution_mathematics.txt` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json` |

## Procedure

For each chapter:

1. Load the summary, the CG document, and the constitution. If the summary
   or any effort signal (`conceptual_demand`, `reasoning_load`, `exec_load`)
   is missing, warn and skip.

2. Apply the constitution's Rules 1–6 exactly.
   - Passes 1–3 select `core_cg`, up to two `core_competencies`, and up to
     three `adjunct_competencies`.
   - Set `co_central` to true when, and only when, two core competencies are
     selected.
   - Write the `dissolution_test` sentence (Rule 4).
   - Copy the three effort signals verbatim from the summary — they are
     already discrete tiers, so no tiering step is needed. Compute
     `effort_index = (conceptual_demand × 2) + (reasoning_load × 2) + (exec_load × 1.5)`,
     rounded to one decimal.

   **Justification writing rule:** write each justification as plain prose a
   teacher can read and immediately understand — as if explaining to a
   colleague why this competency fits — naming the actual section topics,
   results, derivations, worked examples, or exercises from the summary.
   Never use internal item codes (WE-3, E-7, and the like) in the
   justification text; describe the content directly.

3. Write the mapping JSON per the constitution's schema.

4. Verify the written file:
   - `core_cg` is a valid CG-N from the CG document
   - every `core_competencies.c_code` lies inside `core_cg`
   - every `adjunct_competencies.c_code` lies outside `core_cg`
   - core count ≤ 2, adjunct count ≤ 2
   - `co_central` is true if and only if two core competencies are present
   - `dissolution_test` names an operation associated with `core_cg`
   - the three effort signals match the summary
   - `effort_index` matches the formula

5. Confirmation line:
   `ch_02 | core_cg: CG-3 | core: C-3.2 | adjunct: C-4.5, C-8.1 | EI: 11.0`

At session end, list any skipped chapters.

## Constraints

No PDF reads. Obey the constitution's prohibited-documents rule (the CG
document is the sole external input). Process chapters in order. UTF-8.
Overwrite an existing mapping.
