# Cowork Session — Mathematics: Chapter Summary

Reads a Mathematics chapter PDF (foundational / middle / secondary) and
writes a structured summary JSON. Cowork reads and writes directly.

## Run scope

Specify grade and chapter scope. Subject is `mathematics`. `{stage}`
derives from grade: III–V → `foundational`, VI–VIII → `middle`,
IX–X → `secondary`.

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/mathematics/{grade}/` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |

## Step 1 — Title and sections

Extract the chapter title verbatim from the opening page. List every
section (section N) and subsection (section N.M) heading in textbook order. This is
the summary's scope boundary — nothing below may reference a heading
not in this list.

## Step 2 — Inventory three item classes

Recognise by stage conventions. **Labeled headers / banners locate the
regions where exercises live — they are not the unit of count. The unit
of enumeration is each discrete question inside a region: every numbered,
lettered, or bulleted item, and every stand-alone question-marked prompt
under the banner.** An exercise box with 8 numbered questions produces
`E-1` … `E-8`, not a single `E-1`.

| Stage | Activities | Worked examples | Exercise regions (locators) |
|-------|-----------|-----------------|------------------------------|
| Foundational | *Let Us Do*, boxed action prompts | walkthroughs in prose | *Let Us Think*, *Pastime Mathematics*, numbered question lists |
| Middle | `Activity N`, boxed hands-on tasks | `Example N` | *Figure it Out*, *Math Talk*, *Try This* — every numbered question under each banner |
| Secondary | `Activity:`, boxed constructions | `Example N`, `Theorem N` (with proof) | `Exercise Set N.M`, `End-of-Chapter Exercises`, `Think and Reflect`, starred items — every numbered question inside |

Beyond the banners above, **any numbered / lettered question list
directed at the student** also counts as exercises, even if it sits
outside a named region.

**Sub-parts `(a), (b), (c)` of one parent question** roll up into one
`E-N`; the sub-parts are captured inside `description`. This prevents
granularity explosion.

Record:
- **Activities** → `{ id: "A-N", source_section, book_ref, description }`
- **Worked examples** → `{ id: "WE-N", source_section, book_ref, description }`
- **Exercises** → `{ id: "E-N", source_section, book_ref, description }`

`book_ref` is the textbook's own locator for the item — the label a
teacher with the book in hand would use to find it. Format: banner +
question number (where applicable) + page number.    Examples:

- Activity → `"Activity 1, p.105"`
- Worked example → `"Example 1, section 5.8 p.121"`
- Exercise (numbered) → `"Figure it Out Q1, section 5.1 p.107"`
- Exercise (unnumbered) → `"Figure it Out, section 5.1 p.107"`

The question number rule applies to all banners and stages: if the question carries a number, include `Q<n>`; if it does not, omit `Q<n>` entirely. Do NOT invent placeholder labels such as `Q (inline)`, `Q (standalone)`, `Q (unnumbered)`, or similar — the banner name alone suffices.

`book_ref` is what downstream LP and assessment outputs render to the
teacher; the internal `id` is a join key only and never appears in
teacher-facing prose.

**Exclude**: thought-prompts woven into explanatory prose without a
banner or a numbered list, teacher callouts, end-of-chapter summaries,
key-point / takeaway boxes.

## Step 3 — Prose summary

800–1200 words, textbook-section order. Per section: what it teaches,
key concepts, any significant construction/theorem, whether it contains
a student activity. Plain prose. No bullets.

Write one paragraph per section. The opening clause of each paragraph
should name the dominant act of that section (defines / identifies /
explains / justifies / proves / solves / computes / applies) — this
is what the next step reads for tagging.

If the section genuinely contains **two** dominant acts in textbook
order, name both in the opening clause: *"defines … then proves …"*.
Two acts are permitted only when the section's prose clearly progresses
through them in sequence; do NOT split a single arc into two acts to
inflate goal count.

## Step 4 — Tag each section with `section_goal`

Controlled vocabulary (one OR two values per section, in textbook order):

| Tag | Meaning |
|-----|---------|
| `recall` | recognise, identify, list, name, define, state a concept |
| `reason` | explain, justify, prove, compare approaches, derive |
| `apply` | solve, compute, construct, use a procedure in context |

**Source of truth for tagging is the prose paragraph you wrote for
that section in Step 3, not the PDF.** Re-read the paragraph, identify
the dominant act(s), pick the matching tag(s). If the paragraph does
not clearly signal a dominant act, fix the paragraph first — do not
guess from the PDF.

**One vs two goals.** Default is exactly one goal per section. Emit
two goals only when the Step 3 paragraph names two dominant acts in
sequence (e.g., *"defines … then proves …"*). When two goals are
emitted, list them in textbook order — the order they unfold in the
section's prose.

Two goals MUST NOT be used to:
- Cover ambiguity ("it kind of defines and kind of explains"). Pick one.
- Inflate goal count for downstream period budgeting.
- Bridge a section that simply contains an activity inside an
  exposition. A worked numerical example inside an introduction is not
  a separate `reason` act.



## Step 5 — Four effort signals

- `conceptual_demand` (1–3): 1 = recall/direct dominates (>60%);
  2 = reasoning/multi-step dominates or even; 3 = proof/open-ended ≥30%.
- `activity_count` (int): student-executed activities only.
- `demo_count` (int): teacher-demonstrated only.
- `exec_load` (0–2): multi-step computation/construction weight —
  0 = single-step; 1 = 30–60%; 2 = >60%.

## Step 6 — Write summary JSON

```json
{
  "stage": "middle",
  "subject": "mathematics",
  "grade": "vii",
  "chapter_number": 5,
  "chapter_title": "Parallel and Intersecting Lines",
  "sections": [
    { "ref": "section 5.1", "title": "...", "section_goal": ["recall", "reason"] },
    { "ref": "section 5.2", "title": "...", "section_goal": ["recall"] }
  ],
  "prose_summary": "<800–1200 words>",
  "enumerated_activities":      [ { "id": "A-1",  "source_section": "section 5.1", "book_ref": "Activity 1, p.105",                  "description": "..." } ],
  "enumerated_worked_examples": [ { "id": "WE-1", "source_section": "section 5.8", "book_ref": "Example 1, section 5.8 p.121",              "description": "..." } ],
  "enumerated_exercises":       [ { "id": "E-1",  "source_section": "section 5.1", "book_ref": "Figure it Out Q1, section 5.1 p.107",      "description": "..." } ],
  "conceptual_demand": 2,
  "activity_count": 5,
  "demo_count": 1,
  "exec_load": 1
}
```

Rules:
- Every section has `section_goal` as an array of length 1 or 2.
- When length is 2, values are in textbook order (first = dominant act).
- Every enumerated item's `source_section` appears in `sections`.
- Every enumerated item carries a non-empty `book_ref` (teacher-facing locator).
- No `icon`, no `cognitive_load` fields.
- `enumerated_exercises` MUST NOT be `[]` for a normal chapter.

## Step 7 — Confirmation line

Goal tally counts each section by its **first-listed** `section_goal`
(so totals always equal the section count). If any section carries a
two-goal array, append `· dual:N` where N is the count of two-goal
sections.

```
ch_05 — "Parallel and Intersecting Lines" — sections: 9 — activities: 6 — worked_examples: 4 — exercises: 14 — goals: recall×4 reason×3 apply×2 · dual:1 — CD:2 AC:6 DC:0 EL:1
```

## Constraints

No API calls. No consulting LOs, Pedagogy, Syllabus, Assessment, or
Position Papers. Process chapters in order. UTF-8. Overwrite.
