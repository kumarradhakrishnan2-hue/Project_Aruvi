# Cowork Session — Mathematics (Preparatory): Competency Mapping

Reads the prep section-flow summary JSON and writes a mapping JSON per
chapter, governed by the Mathematics Mapping Constitution. Mapping is
**dynamic** — core linkages arise from this pass, not a static lookup.

Summary MUST exist first (run `step_1_chapter_summary.md` in this folder).
**Grades III–V only.**

## Run scope

Specify grade and chapter scope. Subject fixed to `mathematics`,
`stage = preparatory`. `{grade}` is `iii`, `iv`, or `v`.

## Paths

| Item | Path |
|------|------|
| Summary (input) | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |
| CG document | `mnt/data/mirror/framework/mathematics/preparatory/cg_preparatory_mathematics.txt` |
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/mathematics/mapping_constitution_mathematics.txt` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json` |

## Procedure

For each chapter:

1. Load summary, the preparatory CG document, and the constitution. If the
   summary or any effort signal is missing, warn and skip.
2. Apply constitution Rules 1–6 exactly against the **preparatory** CGs
   (CG-1…CG-5). Read the chapter's organising purpose from the summary's
   `sections` (their `title`, `prose_summary`, `section_goal`) and `tasks`
   — there is no worked-example tier at prep, so justify core/adjunct from
   sections and tasks.
3. Copy the four effort signals verbatim from the summary
   (`conceptual_demand`, `activity_count`, `demo_count`, `exec_load`;
   `demo_count` is usually 0). Compute `effort_index` with the Maths
   weights from Rule 5.
4. Write mapping JSON per the constitution schema, with `stage: "preparatory"`.
5. Verify the written file:
   - `core_cg` is a valid CG-N in the **preparatory** CG document
   - every `core_competencies.c_code` lies inside `core_cg`
   - every `adjunct_competencies.c_code` lies outside `core_cg`
   - |core| ≤ 2, |adjunct| ≤ 3
   - `dissolution_test` names an operation associated with `core_cg`
   - `effort_index` matches the formula; signals match the summary
6. Confirmation line:
   `ch_06 | core_cg: CG-1 | core: C-1.1, C-1.3 | adjunct: C-4.1 | EI: 12.5`

At session end, list skipped chapters.

## Constraints

No PDF reads. Obey the constitution's prohibited-documents rule (CG is the
sole external input). Process chapters in order. UTF-8. Overwrite.
