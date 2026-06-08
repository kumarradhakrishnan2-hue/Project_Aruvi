# Cowork Session — English (Secondary): Chapter Summary + Static Competency Mapping

Reads an English chapter PDF for the **Secondary stage (Grade IX; extensible
to X)** and writes two files per chapter — a summary JSON
and a mapping JSON. Cowork reads/writes directly. No API calls. Forked from
the Middle prompt; secondary-only differences flagged **[DELTA]**.

Two-axis structure: **outer axis** = 1–3 `main_sections` (each a distinct text:
`prose`, **`drama`**, `poem`, `narrative`, `dialogue`, `informational`);
**inner axis** = the 6 spines per section (Reading for Comprehension,
Listening, Speaking, Writing, Vocabulary/Grammar, Beyond-the-Text).

Competency mapping is **static at stage level** — from the secondary
`spine_to_cg.json`, restricted to spines present in the chapter, no per-chapter
tags, all weights 1.

## Run scope
Subject `english`, stage `secondary`, grade IX (`ix`).

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/english/{grade}/` |
| **[DELTA] Transcript appendix** | `mnt/data/knowledge_commons/textbooks/english/{grade}/transcript.pdf` |
| Static spine→CG | `mnt/data/mirror/framework/english/secondary/spine_to_cg.json` |
| NCF CG / Pedagogy (context) | `mnt/data/mirror/framework/english/secondary/{cg,pedagogy}_secondary_english.txt` |
| Summary out | `mnt/data/mirror/chapters/english/{grade}/summaries/ch_NN_summary.json` |
| Mapping out | `mnt/data/mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json` |

## Step 1 — Title and stage
Extract `chapter_title` verbatim from the unit-title heading. Set `stage` =
`"secondary"`.

## Step 2 — Detect main_sections (1–3)
A `main_section` is a distinct text that carries its own exercise apparatus.
A new section starts at a new titled text (own byline), a genre shift
(prose ↔ drama ↔ poem), or a re-run spine cycle for a different text. Capture
per section: `section_id` (A/B/C in textbook order), `title`, `type`,
`page_range`, `page_count` (integer — number of textbook pages this section
spans, INCLUDING its exercise apparatus; compute as
last_page − first_page + 1 from `page_range`). This is the teaching-load
signal the LP uses to allocate periods across sections, so it must reflect
the full footprint a teacher works through — the body text PLUS every
Reading / Vocabulary / Listening / Speaking / Writing / Beyond-text
subheading that belongs to this section.

**[DELTA — DRAMA]** A multi-act play (ACT I/II/III) is ONE section,
`type: "drama"` — acts are parts of one text, not separate sections.
**[DELTA — ENRICHMENT]** A "read and enjoy" piece under *Learning Beyond the
Text* with NO exercise apparatus (e.g. "Music" by de la Mare) is NOT a
section — capture it as a `beyond_text` task of the preceding section.

## Step 3 — Per section, write the text summary

| `type` | Required field(s) | Length | Content |
|---|---|---|---|
| prose / narrative / dialogue / informational | `prose_summary` | 200–400 w | Plot/argument arc, characters, setting, themes, tone, pivotal passages. Prose, no bullets. |
| **[DELTA] drama** | `drama_summary` | 250–450 w | **Act-by-act arc**: per act — setting, who is present, central exchange/conflict, how it advances. Name characters + the thematic conflict (e.g. tradition vs. modernity). Prose, no bullets. |
| poem | `poem_text` + `poem_appreciation_summary` | full verbatim / 80–150 w | `poem_text`: line/stanza breaks preserved. Appreciation: theme, tone, central imagery, dominant device. |

MANDATORY. Stay strictly within the textbook — no outside knowledge. Very
short texts get shorter summaries (50–100 w) but are never omitted. This text
is the source of truth for downstream LP `teacher_notes` and assessment
generation/verification.

## Step 4 — Per section, identify present spines

Walk each section in textbook order; a spine may be fed by multiple
subheadings; a spine may be absent (don't invent it).

**[DELTA — SECONDARY SUBHEADINGS]** (authoritative, matches `spine_to_cg.json`):

| Spine | Secondary textbook subheadings |
|---|---|
| `reading_for_comprehension` | Reflect and Respond · Reading for Meaning · Reading for Appreciation · Check Your Understanding · Critical Reflection |
| `listening` | Listen and Respond |
| `speaking` | Speaking Activity |
| `writing` | Writing Task |
| `vocabulary_grammar` | Vocabulary and Structures in Context · Vocabulary in Context |
| `beyond_text` | Learning Beyond the Text · POINTS TO REMEMBER |

In the Reading cluster: *Reflect and Respond* = pre-reading activation;
*Reading for Meaning* (prose/drama) / *Reading for Appreciation* (poem) = the
text; *Check Your Understanding* + *Critical Reflection* = comprehension/
analysis. All roll into `reading_for_comprehension`.

**[DELTA — ON-PAGE ORDER]** Record each section's `spines` object in the
literal on-page subheading order (typically Reading → Vocab/Grammar → … →
Listening late), NOT canonical order. This is the LP's spine-walk source of
truth; do not re-sort. (Mapping emission uses canonical order — Step 8.)

## Step 5 — Per (section, spine) cell, capture tasks

- `section_name` — the subheading(s) used, joined ` + ` in on-page order.
- `tasks_verbatim` — array of OBJECTS, one per in-class task under any of the
  spine's subheadings, in textbook order. Sub-parts (i)/(ii)/(a)/(b) of one
  parent roll into that task's `question_bank` (sub-items, NOT separate
  tasks). Entry shape:
  ```json
  {
    "task_text": "<verbatim instruction + body>",
    "question_bank": [          // sub-items of THIS task; [] for an open prompt
      { "stem": "<verbatim>",
        "type": "MCQ|SCR|ECR|EXTRACT_ANALYSIS|MATCH|FILL_IN|TRUE_FALSE|ORAL_PROMPT|WRITING_TASK|PROJECT",
        "options": [...],       // MCQ only
        "table": "header|cells\nrow|cells",  // when tabular
        "page_ref": "p.NN" }
    ]
  }
  ```

Single source of truth: each question_bank entry belongs to ONE task; no
duplication; no flat top-level question_bank. The LP enacts the full task in
class and emits an `implied_lo`; the assessment generator makes ORIGINAL items
from `prose_/drama_summary` / `poem_text` and never lifts from question_bank.

Multi-subheading spines: do NOT collapse to the first subheading. A section's
`reading_for_comprehension` MUST hold task objects from *Reflect and Respond*,
*Reading for Meaning/Appreciation*, *Check Your Understanding*, AND *Critical
Reflection* when present; same for `beyond_text` across its two subheadings.
**[DELTA — DRAMA]** A drama's Reading spine captures the Check-Your-
Understanding tasks after EACH act plus the end-of-play Critical Reflection.

## Step 6 — Listening: bake the transcript [DELTA]

Secondary transcripts live in a SEPARATE `transcript.pdf` appendix. Resolve
and bake them HERE so LP/Assessment never open the appendix. Per listening
cell capture:
- `transcript_ref` — `"p. NN"`, the PRINTED textbook page from the chapter's
  "(Transcript for teacher on page NN)" note. Provenance only.
- `transcript_file` — `"knowledge_commons/textbooks/english/{grade}/transcript.pdf"`.
- `transcript_unit` — e.g. `"Unit 6"`.
- `transcript_text` — the body, shortened to **150–250 w**, all speakers/
  segments represented, sequence + resolution intact, filler trimmed, speaker
  labels kept.

Locate it: each appendix page carries the textbook's own printed page-number
footer (it alternates between the book-title marker, e.g. `"<Title> NNN"`, and
`"Appendix NNN"`), ordered by Unit 1…8. Match the page whose printed footer
number equals `transcript_ref`. (For Grade IX the physical offset is
`printed − 258 = physical page`, but always confirm by the printed footer, not
the offset alone.)

## Step 7 — Effort signals

Compute AFTER `main_sections` is written, by counting array entries (no
estimation). Stored under `effort_signals`; single source of truth for the
mapping (Step 8b does NOT recompute).

**[DELTA — RECALIBRATED `spine_load`]** Re-based on TOTAL spine-cells, because
every secondary section runs all 6 spines (the middle avg-per-section measure
pinned at a constant and stopped discriminating). The other signals keep the
middle definitions.

- **`spine_load` (1–3)** = total spine-cells (sum over sections of #spine
  keys). Tier: ≤6→1, 7–12→2, ≥13→3.
- **`task_density` (1–3)** = avg task objects per spine-cell
  (Σ len(tasks_verbatim) ÷ #spine-cells). Tier: ≤3.0→1, 3.1–6.0→2, ≥6.1→3.
- **`writing_demand` (0–2)** = Σ over `writing`+`beyond_text` tasks of
  `max(1, len(question_bank))` (an open task counts as 1, not 0).
  Tier: 0–5→0, 6–15→1, 16+→2.
- **`project_load` (0–3)** = count of `beyond_text` cells.

Formula (one decimal, no clamp/round):
`effort_index = spine_load×2 + task_density×1.5 + writing_demand×1.5 + project_load×1`

Verify: re-walk the JSON; if a count ≠ an actual array length, the JSON wins —
recompute.

> Reference (recompute per chapter, don't hardcode): Ch 01 (prose+poem) ≈
> sl2/td1/wd1/pl2 → 9.0; Ch 06 (drama+poem) ≈ sl2/td1/wd1/pl2 → 9.0.

## Step 8 — Static competency mapping + mapping JSON

**8a — Attach to summary.** From the secondary `spine_to_cg.json`, for each
spine present in this chapter (a key under any `main_section.spines`), copy its
`competency_codes` verbatim into `competency_reporting.by_spine`. No entries
for absent spines; no per-chapter tags.

**8b — Write mapping JSON** to
`mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json` (read by the
Allocate tab):
- `stage`/`subject`/`grade`/`chapter_number`/`chapter_title` — from summary.
- `summary_path` — `"mirror/chapters/english/{grade}/summaries/ch_NN_summary.json"`.
- `primary` — from `spine_to_cg.json`, restricted to present spines. Walk
  present spines in **canonical order** (reading_for_comprehension, listening,
  speaking, writing, vocabulary_grammar, beyond_text), emit each unique
  `c_code` once (first occurrence wins), `{ "c_code": …, "weight": 1 }`.
  (Canonical emission here is independent of Step 4's on-page order.)
- `incidental` — `[]`.
- `spine_load`/`task_density`/`writing_demand`/`project_load`/`effort_index` —
  copy from the summary's `effort_signals`; do NOT recompute.
- `chapter_weight` — `null`.

Template (Ch 01, all 6 spines present):
```json
{
  "stage": "secondary",
  "subject": "english",
  "grade": "ix",
  "chapter_number": 1,
  "chapter_title": "How I Taught My Grandmother to Read",
  "summary_path": "mirror/chapters/english/ix/summaries/ch_01_summary.json",
  "primary": [
    { "c_code": "C-2.1", "weight": 1 },
    { "c_code": "C-2.2", "weight": 1 },
    { "c_code": "C-3.1", "weight": 1 },
    { "c_code": "C-4.1", "weight": 1 },
    { "c_code": "C-1.1", "weight": 1 },
    { "c_code": "C-3.2", "weight": 1 },
    { "c_code": "C-1.2", "weight": 1 },
    { "c_code": "C-1.3", "weight": 1 },
    { "c_code": "C-1.4", "weight": 1 },
    { "c_code": "C-2.3", "weight": 1 },
    { "c_code": "C-4.2", "weight": 1 },
    { "c_code": "C-4.3", "weight": 1 },
    { "c_code": "C-4.4", "weight": 1 },
    { "c_code": "C-4.5", "weight": 1 }
  ],
  "incidental": [],
  "spine_load": 2,
  "task_density": 1,
  "writing_demand": 1,
  "project_load": 2,
  "effort_index": 9.0,
  "chapter_weight": null
}
```
That `primary` is the secondary `spine_to_cg.json` de-duplicated in canonical
order with all 6 spines present; drop c-codes contributed only by an absent
spine. UTF-8. Create `mappings/` if absent; overwrite.

## Step 9 — Write summary JSON

```json
{
  "subject": "english",
  "stage": "secondary",
  "grade": "ix",
  "chapter_number": 1,
  "chapter_title": "How I Taught My Grandmother to Read",
  "main_sections": [
    {
      "section_id": "A",
      "title": "How I Taught My Grandmother to Read",
      "type": "prose",
      "page_range": "p.1-22",
      "page_count": 22,
      "prose_summary": "<200–400 w textbook-grounded summary>",
      "spines": {
        "reading_for_comprehension": {
          "section_name": "Reflect and Respond + Reading for Meaning + Check Your Understanding + Critical Reflection",
          "tasks_verbatim": [
            { "task_text": "Read the extracts below and answer the questions that follow.",
              "question_bank": [
                { "stem": "The phrase 'never seen her cry...' shows the grandmother was ____.", "type": "MCQ", "options": ["strong-willed","understanding","considerate","bold"], "page_ref": "p.10" }
              ] }
          ]
        },
        "vocabulary_grammar": { "section_name": "Vocabulary and Structures in Context", "tasks_verbatim": [] },
        "listening": {
          "section_name": "Listen and Respond",
          "transcript_ref": "p. 259",
          "transcript_file": "knowledge_commons/textbooks/english/ix/transcript.pdf",
          "transcript_unit": "Unit 1",
          "transcript_text": "<150–250 w, all segments, labels kept>",
          "tasks_verbatim": []
        },
        "speaking":    { "section_name": "Speaking Activity", "tasks_verbatim": [] },
        "writing":     { "section_name": "Writing Task", "tasks_verbatim": [] },
        "beyond_text": { "section_name": "Learning Beyond the Text", "tasks_verbatim": [] }
      }
    },
    {
      "section_id": "B",
      "title": "Bharat Our Land",
      "type": "poem",
      "page_range": "p.23-32",
      "page_count": 10,
      "poem_text": "The mighty Himavant is ours-\nthere's no equal anywhere on earth.\n...",
      "poem_appreciation_summary": "<80–150 w>",
      "spines": {
        "reading_for_comprehension": { "section_name": "Reflect and Respond + Reading for Appreciation + Check Your Understanding + Critical Reflection", "tasks_verbatim": [] },
        "vocabulary_grammar":        { "section_name": "Vocabulary in Context", "tasks_verbatim": [] },
        "listening":                 { "section_name": "Listen and Respond", "transcript_ref": "p. 260", "transcript_file": "knowledge_commons/textbooks/english/ix/transcript.pdf", "transcript_unit": "Unit 1", "transcript_text": "<150–250 w>", "tasks_verbatim": [] },
        "speaking":                  { "section_name": "Speaking Activity", "tasks_verbatim": [] },
        "writing":                   { "section_name": "Writing Task", "tasks_verbatim": [] },
        "beyond_text":               { "section_name": "Learning Beyond the Text", "tasks_verbatim": [] }
      }
    }
  ],
  "competency_reporting": {
    "by_spine": {
      "reading_for_comprehension": ["C-2.1", "C-2.2", "C-3.1", "C-4.1"],
      "listening":                 ["C-3.1"],
      "speaking":                  ["C-1.1", "C-3.2"],
      "writing":                   ["C-1.2", "C-1.3", "C-1.4", "C-2.3"],
      "vocabulary_grammar":        ["C-2.2"],
      "beyond_text":               ["C-4.2", "C-4.3", "C-4.4", "C-4.5"]
    }
  },
  "effort_signals": { "spine_load": 2, "task_density": 1, "writing_demand": 1, "project_load": 2, "effort_index": 9.0 }
}
```

Notes: record `spines` in ON-PAGE order (Step 4); each `tasks_verbatim` is
populated with real task objects (shown `[]` above only as placeholders). For
a `drama` section use `drama_summary` + `type:"drama"`; its Reading spine holds
per-act Check-Your-Understanding plus the end Critical Reflection. A spine with
no tasks is omitted from its section. UTF-8. Overwrite.

## Step 10 — Confirmation line
```
ch_NN — "<title>" — sections: <count> (<type breakdown>) — pages: A=<N> B=<N> [C=<N>] — spines_total: <N> — tasks: <task_objs> — sub_items: <subitems> — project_load: <N> — effort_index: <value>
```
`task_objs` = Σ len(spine.tasks_verbatim); `subitems` = Σ len(t.question_bank).
The `pages: ...` block echoes each section's `page_count` integer
(last_page − first_page + 1) so the value used by the LP's
proportional-period allocation is visible at confirmation time.
Example: `ch_06 — "Twin Melodies" — sections: 2 (1 drama + 1 poem) — pages: A=25, B=9 — spines_total: 12 — tasks: 35 — sub_items: 48 — project_load: 2 — effort_index: 9.0`

## Constraints
- No API calls; Cowork reads PDFs and writes JSON directly.
- No LOs/Syllabus/Assessment Framework/Position Papers; pedagogy beyond
  `mirror/framework/english/secondary/` is off-limits.
- [DELTA] Use the secondary subheading table (Step 4), not middle "Let us …".
- [DELTA] A multi-act play is one `drama` section with `drama_summary`;
  enrichment poems are `beyond_text` tasks, never their own section.
- [DELTA] Record `spines` in on-page order; mapping emission (Step 8) is
  canonical order.
- [DELTA] Bake the listening transcript into `transcript_text` from the
  separate appendix (Step 6); LP/Assessment must not need the appendix.
- [DELTA] `spine_load` uses the recalibrated total-spine-cells tiers (Step 7);
  the other signals and the formula are unchanged from middle.
- `effort_index` from the four signals — no estimate/clamp; one decimal.
  `writing_demand` uses the `max(1, …)` rule.
- Don't invent absent spines; don't collapse a multi-subheading spine.
- Each `tasks_verbatim` entry is an OBJECT `{ task_text, question_bank }`; the
  flat top-level `question_bank` is FORBIDDEN.
- Two files per chapter (summary + mapping), both present before moving on.
  Process chapters in order. UTF-8. Overwrite.
