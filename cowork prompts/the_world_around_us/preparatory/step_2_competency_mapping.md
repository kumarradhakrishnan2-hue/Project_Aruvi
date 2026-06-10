# Cowork Session — The World Around Us: Competency Mapping

Reads a TWAU chapter summary JSON and the CG reference, applies the TWAU
Competency Mapping Constitution (two-pass discipline), and writes the
competency mapping JSON for each chapter. Cowork reads all inputs and writes
the file directly. No API call is made.

Chapter summaries must already exist (run `step_1_chapter_summary.md` first).
C-codes are **discovered here** through the two-pass process — they are never
present in the summary JSON.

## Run scope

Specify grade and chapter scope at the start of the session. Subject is
`The World Around Us`. Stage is `preparatory` (Grades III, IV, V).

```
Single chapter  : map chapter 7 only
Multiple        : map chapters 1, 4, 8
All chapters    : map all chapters for this grade
```

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | `mnt/data/` |
| Chapter summary (input) | `mnt/data/mirror/chapters/the_world_around_us/{grade}/summaries/ch_NN_summary.json` |
| CG reference | `mnt/data/mirror/framework/the_world_around_us/preparatory/competency_descriptions_twau.json` |
| Constitution | `mnt/data/mirror/constitutions/competency_mapping/the_world_around_us/preparatory/mapping_constitution_twau.txt` |
| Mapping output (per chapter) | `mnt/data/mirror/chapters/the_world_around_us/{grade}/mappings/ch_NN_mapping.json` |

`{grade}` is the lowercase Roman numeral: `iii`, `iv`, or `v`. All TWAU folders
use the subject token `the_world_around_us` (matching the app's
`subject_to_folder`).

## Step 1 — Load inputs

For each chapter, load ONLY the two inputs Pass 1 is permitted to see:
1. **Resolve `chapter_title` first (mandatory).** Read the `chapter_title`
   field from `ch_NN_summary.json` and use it verbatim. (TWAU summaries are
   JSON — the title is a field, not a first-line heading.) If the field is
   absent or blank, log a warning and halt for that chapter.
2. Read `ch_NN_summary.json` — this is the sole chapter content reference.
   Do NOT read the chapter PDF.
3. Read the mapping constitution `mapping_constitution_twau.txt`.

**Do NOT open the CG reference (`competency_descriptions_twau.json` or
`cg_twau.txt`) here.** Rule 1 requires Pass 1 to be C-code-blind, and a model
cannot reliably ignore C-codes already sitting in its context. The CG
reference is loaded only at the start of Pass 2 (Step 2), after the
transformation inventory is complete.

If `ch_NN_summary.json` is absent, log a warning and skip that chapter. Do
not generate the summary here — run `step_1_chapter_summary.md` first.

## Step 2 — Apply the constitution

Apply the TWAU Competency Mapping Constitution exactly. It is the governing
document; all mapping decisions follow its rules without exception.

- **Pass 1 (Rule 1) — Transformation inventory, C-code-blind.** Read the
  summary section by section. For each named section, state what cognitive
  operation it requires the student to perform, and on what content object.
  Do NOT open the CG reference during Pass 1.
- **Pass 2 (Rule 2) — Architectural container and matching.** Only now open
  the CG reference `competency_descriptions_twau.json` (preferred over
  `cg_twau.txt`) — this is the first point at which C-codes enter the session.
  For each transformation statement,
  identify its architectural container (the named section or activity block),
  read the full C-code definition, and match only if the chapter's
  architecture compels the student to execute the operation the C-code
  defines. Verify each distinct demand in a multi-demand C-code independently.
  As you accept each match, record the **named sections** (from the Pass-1
  inventory) whose transformation supports that c_code — this is the c_code's
  `sections[]`. Include EVERY section whose content genuinely develops the
  competency, not only the single strongest one.
- **Rule 3 — Reject vocabulary-only matches** and incidental mentions inside
  sections whose primary subject is something else.
- **Rule 4 — Flattened weight.** Every matched C-code receives `weight: 1`.
  No Weight 3/2, no dissolution test, no sub-discipline rule. A chapter
  typically yields 3–5 matched C-codes at comparable depth.

This step produces a verified in-memory competency list of
`{cg, c_code, competency_text, weight, justification, sections}`.
`competency_text` is copied verbatim from `competency_descriptions_twau.json`.
Each `justification` must cite a named section or activity verifiably present
in THIS chapter's summary. `sections[]` lists the section titles (exactly as
they appear in the summary's `sections[].title`) that develop this c_code; the
lesson plan uses it to bind CG codes to periods. No file is written in this step.

**Prohibited documents:** Learning Outcomes, Pedagogy, Syllabus, Assessment
Framework, Position Papers — constitutionally excluded.

## Step 3 — Write the mapping JSON

Write one JSON record per chapter to:
`mnt/data/mirror/chapters/the_world_around_us/{grade}/mappings/ch_NN_mapping.json`

```json
{
  "chapter_number": 7,
  "chapter_title": "Solids, Liquids and Gases",
  "grade": "iv",
  "stage": "preparatory",
  "subject": "the_world_around_us",
  "effort_index": 12.0,
  "competencies": [
    {
      "cg": "CG-1",
      "c_code": "C-1.1",
      "competency_text": "exact text from competency_descriptions_twau.json",
      "weight": 1,
      "justification": "cites a named section/activity verifiably present in this chapter's summary",
      "sections": ["exact summary section title(s) whose content develops this c_code"]
    }
  ],
  "chapter_weight": 4
}
```

Field sourcing rules:

| Field | Source | Rule |
|-------|--------|------|
| `chapter_number` | Summary JSON | Integer, copied from the summary. |
| `chapter_title` | Summary JSON | Copied verbatim (Step 1.1). |
| `grade` | Run scope / folder | Lowercase Roman numeral `iii`/`iv`/`v`. |
| `stage` | Fixed | Always `"preparatory"` for Grades III–V. |
| `subject` | Fixed | Always `"the_world_around_us"`. |
| `effort_index` | Summary JSON | Copied verbatim from the summary. |
| `competencies` | Step 2 output | Transcribe verbatim; every `weight` is `1`. |
| `competencies[].sections` | Step 2 output | Section titles (verbatim from the summary's `sections[].title`) that develop this c_code; lists every supporting section, not just the strongest. |
| `chapter_weight` | Calculated | Count of entries in `competencies` (= sum of weights, since all are 1). |

**Post-write verification (mandatory).** Read the file back and confirm:
1. Every `cg`, `c_code`, `weight`, and `justification` matches the Step 2
   competency list.
2. `chapter_title` exactly matches the summary JSON's `chapter_title`
   (Learning #15 guard).
3. `chapter_weight` equals the number of competencies.
4. `effort_index` equals the summary's `effort_index`.
5. Every entry in each competency's `sections[]` matches a `sections[].title`
   in the summary verbatim, and every summary section is covered by at least
   one competency's `sections[]` OR is a section the lesson plan will fall back
   on (a section legitimately developing no mapped competency).

If any discrepancy is found, overwrite with the correct values before moving
to the next chapter.

## Step 4 — Print verification summary

After each chapter, print one confirmation line:

```
ch_07 | Solids, Liquids and Gases | C-codes: C-1.1, C-2.1, C-4.4, C-6.1 | chapter_weight: 4 | EI: 12.0
```

If any chapter summary was missing, list all skipped chapters at the end.

## Constraints

- Do not read chapter PDFs. The summary JSON is the sole content input.
- Do not consult Learning Outcomes, Pedagogy, Syllabus, Assessment
  Framework, or Position Papers — constitutionally prohibited.
- Do not call the Claude API. Cowork reads all inputs directly.
- Process chapters in the order specified.
- All files written in UTF-8. Overwrite if a mapping file already exists.
