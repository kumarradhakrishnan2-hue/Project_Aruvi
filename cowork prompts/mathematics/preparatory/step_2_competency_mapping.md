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
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/mathematics/preparatory/mapping_constitution_mathematics.txt` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/mappings/ch_NN_mapping.json` |

## Procedure

For each chapter:

1. Load summary, the preparatory CG document, and the constitution. If the
   summary or any effort signal is missing, warn and skip.
2. Apply constitution Rules 1–6 exactly against the **preparatory** CGs
   (CG-1…CG-5). Read the chapter's organising purpose from the summary's
   `sections` (their `title`, `prose_summary`) and `tasks` (banner, intent, description)
   — justify core/adjunct from sections and tasks.

   **Justification writing rule:** Write each justification as natural prose a teacher can read immediately — as if explaining to a colleague why this competency fits. Name the actual topics, activities, and learning contexts from the summary (e.g. "the estimate-then-verify produce weighing activity" or "the Boxes of Sweet packing problem"). **Never cite section or task codes (S1, S2, T-7, etc.) — these are invisible to the reader. If you find yourself writing a code, replace it with thetopic name.**
   
3. Copy the four prep effort signals verbatim from the summary
   (`conceptual_demand`, `task_load`, `exploration_load`, `procedural_load`).
   Compute `effort_index` with the preparatory weights from Rule 5.
4. Write mapping JSON per the constitution schema, with `stage: "preparatory"`.
5. Verify the written file:
   - `core_cg` is a valid CG-N in the **preparatory** CG document
   - every `core_competencies.c_code` lies inside `core_cg`
   - every `adjunct_competencies.c_code` lies outside `core_cg`
   - |core| ≤ 2, |adjunct| ≤ 3
   - `dissolution_test` names an operation associated with `core_cg`
   - `effort_index` matches the formula; signals match the summary
   - **Justification validator (hard stop):** Scan every `justification` field in
     `core_competencies` and `adjunct_competencies` for internal reference codes.
     A violation is any token matching `S\d+`, `T-\d+`, or a standalone letter+digit
     like `S1`, `S2`, `T7` etc. If any violation is found, **do not write the file**.
     Rewrite the offending justification(s) using the section's `title` or `prose_summary`
     text in plain language, then repeat this validator check before writing.
6. Confirmation line:
   `ch_06 | core_cg: CG-1 | core: C-1.1, C-1.3 | adjunct: C-4.1 | EI: 11.0`

At session end, list skipped chapters.

## Constraints

No PDF reads. Obey the constitution's prohibited-documents rule (CG is the
sole external input). Process chapters in order. UTF-8. Overwrite.
