# Cowork Session — Mathematics: Chapter Summary (Secondary Stage)

Reads a secondary-stage Mathematics chapter PDF (Grade IX) and writes a
structured summary JSON. Cowork reads the PDF and writes the file directly.
No API call is made.

The summary is the content reference for the competency-mapping (effort
index) session and for the lesson-plan and assessment generation that
follow.

## Run scope

Tell Cowork the grade and chapter scope before starting:

```
Single chapter  : process chapter 2 only
Multiple        : process chapters 2, 5, 7
All chapters    : process every chapter in the textbook folder
```

Subject is `mathematics`, stage is `secondary`.

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/mathematics/{grade}/` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |

Output file name: `ch_NN_summary.json` (NN = zero-padded chapter number,
e.g. `ch_02_summary.json`).

## Step 1 — Title and section spine

Read the full chapter PDF. Record the chapter title exactly as printed on
the opening page — verbatim, no paraphrase, no casing change.

List every numbered section and subsection heading in the order they
appear (e.g. `2.1`, `2.2`, `2.3`, `2.3.1`). This ordered list is the
summary's scope boundary: nothing in the summary may reference a heading
not on this list, and no content from outside this chapter may appear.

## Step 2 — Enumerate examples and exercises

Two item classes are enumerated. The unit of enumeration is each discrete
item, not the banner that groups them.

- **Worked examples** → `{ "id": "WE-N", "source_section", "book_ref", "description" }`
  Each item printed as `Example N` (a solved instance shown in the text).

- **Exercises** → `{ "id": "E-N", "source_section", "book_ref", "description" }`
  Every numbered question a student is asked to do: the questions under a
  section's practice-exercise banner, and the questions in the
  end-of-chapter exercise set. Each numbered question is one `E-N`.

`book_ref` is the locator a teacher with the book in hand would use:
banner + question number (when the item is numbered) + page. Examples:
`"Example 4, p.19"`, `"Exercise 2.2 Q3, p.21"`, `"End of Chapter Q7, p.37"`.
If an item carries no number, omit the number and use the banner and page
alone. Do not invent placeholder numbers.

Sub-parts `(i), (ii), (iii)` of one numbered question roll up into a single
`E-N`; capture the sub-parts inside `description`.

**Do NOT enumerate:**
- Items or whole sections marked with an asterisk (*). These are the
  textbook's own enrichment / higher-order material and are excluded from
  the summary entirely.
- Sidebar boxes (shaded callouts that sit beside the main flow and carry a
  named fact, story, or caution rather than a section's core teaching).
  These are excluded entirely — they are not sections, not examples, and
  not exercises.

## Step 3 — Capture "Think and Reflect" prompts inline

"Think and Reflect" prompts are the chapter's reflective extensions of the
section they sit in. They are not exercises and are not enumerated as
items, but they shape how a section is taught, so they are recorded.

For each section that contains one or more such prompts, record a single
`think_reflect` string on that section: one sentence naming what the prompt
asks the student to consider. Where a section has several prompts, give one
combined sentence. A section with none omits the field.

## Step 4 — Prose summary

Write the summary in textbook-section order, one paragraph per section,
covering for each section: what it teaches, the key concepts or terms it
introduces, and any significant definition, result, or representation it
develops.

Open each section's paragraph with the dominant act of that section
(defines / introduces / explains / derives / proves / justifies / solves /
computes / constructs / represents). Name the act plainly; this is what the
mapping and lesson-plan steps read to infer what the section develops. If a
section genuinely carries two dominant acts in sequence, name both in order.

Plain prose. No bullet points. No tables. Cover every section on the spine
from Step 1; do not pad and do not compress a section away to save length.
Length follows content.

## Step 5 — Three effort signals

Record three signals as integers. Each measures a different, independent
axis. Keep them independent — do not let one raise or lower another.

- **`conceptual_demand` (1–3) — ABSTRACTION ONLY.** How far the chapter's
  objects sit from concrete, manipulable experience, and how much new
  formal vocabulary or notation the student must hold.
  - 1 = concrete objects, little new abstract apparatus
  - 2 = moderate abstraction or notation load
  - 3 = highly abstract objects or dense new formal apparatus

  The amount of proving or justifying MUST NOT move this score. A chapter
  can be highly abstract yet ask for little justification, or ask for heavy
  justification about fairly concrete objects. Abstraction only.

- **`reasoning_load` (0–3) — PROOF / JUSTIFICATION VOLUME.** How much of the
  chapter is spent justifying, deriving, proving, arguing across cases, or
  asking the student to explain why a result holds (including reflective
  prompts that ask for justification).
  - 0 = procedural or definitional only; no justification asked
  - 1 = occasional "explain why"; reasoning is incidental
  - 2 = reasoning is a recurring expectation across sections
  - 3 = formal proof or sustained deductive argument is the chapter's spine

- **`exec_load` (0–2) — PROCEDURAL VOLUME.** Weight of multi-step
  computation, construction, or graphing the student carries out.
  - 0 = single-step or no procedural work
  - 1 = procedural work present but not dominant
  - 2 = multi-step procedure, construction, or graphing dominates

## Step 6 — Write the summary JSON

```json
{
  "stage": "secondary",
  "subject": "mathematics",
  "grade": "ix",
  "chapter_number": 2,
  "chapter_title": "Introduction to Linear Polynomials",
  "sections": [
    { "ref": "2.1", "title": "...", "think_reflect": "..." },
    { "ref": "2.2", "title": "..." }
  ],
  "prose_summary": "<one paragraph per section, section order>",
  "enumerated_worked_examples": [
    { "id": "WE-1", "source_section": "2.1", "book_ref": "Example 1, p.16", "description": "..." }
  ],
  "enumerated_exercises": [
    { "id": "E-1", "source_section": "2.1", "book_ref": "Exercise 2.1 Q1, p.18", "description": "..." }
  ],
  "conceptual_demand": 2,
  "reasoning_load": 2,
  "exec_load": 2
}
```

Rules:
- Every section on the Step 1 spine appears once in `sections`, in order.
- `think_reflect` appears only on sections that carry such a prompt.
- Every enumerated item's `source_section` is a `ref` present in `sections`.
- Every enumerated item carries a non-empty `book_ref`.
- No `section_goal` field. No asterisked items. No sidebar-box items.
- `enumerated_exercises` is non-empty for a normal chapter.

## Step 7 — Confirmation line

After writing each summary, print one line:

```
ch_02 — "Introduction to Linear Polynomials" — sections: 6 — worked_examples: 16 — exercises: 28 — think_reflect: 9 — CD:2 RL:2 EL:2
```

If a chapter PDF is not found, log a warning and skip — do not halt.

## Constraints

- No API calls. Cowork reads the PDF directly.
- Do not generate mappings, learning outcomes, or effort-index values
  beyond the three raw signals above.
- Process chapters in the order specified.
- UTF-8. If a summary already exists for a chapter, overwrite it.
