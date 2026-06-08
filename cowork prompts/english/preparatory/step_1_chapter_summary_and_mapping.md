# Cowork Session — English (Preparatory): Chapter Summary + Static Competency Mapping

Reads an English chapter PDF for the **Preparatory stage (Grades III–V)** and writes two files per chapter:
- summary JSON → `mirror/chapters/english/{grade}/summaries/ch_NN_summary.json`
- mapping JSON → `mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json`

Cowork reads PDFs and writes JSON directly. No API calls.

**Shape.** Each chapter has 1–3 `main_sections` (a distinct text or visual narrative — `poem`, `prose`, `narrative`, `dialogue`, `informational`, or `picture_narrative`). Within each section, the 5 prep-native spines are: **Oracy**, **Reading**, **Writing**, **Word Work**, **Beyond-the-Text**. Competency mapping is static-by-stage (looked up from `spine_to_cg.json`), filtered to spines actually present, all weights = 1.

Sibling of the middle/secondary prompt (`chapter_summary_competency_mapping_english.md`, 6-spine model). NCF treats prep and middle as distinct stages; the two prompts are intentionally separate. **Do not use this prompt for grade VI or above.**

## Paths

| Item | Path |
|---|---|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/english/{grade}/` |
| Spine→CG lookup | `mnt/data/mirror/framework/english/preparatory/spine_to_cg.json` |
| NCF CG (context) | `mnt/data/mirror/framework/english/preparatory/cg_preparatory_english.txt` |
| NCF Pedagogy (context) | `mnt/data/mirror/framework/english/preparatory/pedagogy_preparatory_english.txt` |
| Competency descriptions | `mnt/data/mirror/framework/english/preparatory/competency_descriptions_preparatory.json` |
| Summary output | `mnt/data/mirror/chapters/english/{grade}/summaries/ch_NN_summary.json` |
| Mapping output | `mnt/data/mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json` |

## Step 1 — Chapter metadata

Extract `chapter_title` verbatim from the opening page. Set `stage = "preparatory"`.

## Step 2 — Detect main_sections (1 to 3)

A new `main_section` begins when the textbook starts a distinct text or visual narrative — a fresh chapter-title-style heading, a new "Let us Read" / "Let us Recite", a shift from picture-only story to prose/poem, or a re-run of the spine cycle for a different text. Prep default is usually **1 section**, occasionally **2** (e.g. a picture story followed by a poem).

Per section: `section_id` (A/B/C in textbook order), `title`, `type`, `page_range`, `page_count` (integer = `last_page − first_page + 1` parsed from `page_range`, counting every textbook page the section occupies — body, picture spreads, and exercise apparatus together; the LP uses this to allocate periods proportionally across sections).

| `type` | When |
|---|---|
| `poem` | Poem under "Let us Recite" or similar |
| `prose` | Continuous prose narrative |
| `narrative` | Story-like prose that doesn't fit prose/poem cleanly |
| `dialogue` | Conversational text (named speakers) |
| `informational` | Factual/expository text |
| `picture_narrative` | Wordless or near-wordless visual story (e.g. Grade III "Picture Reading"). Body is the visual story, not prose. |

## Step 3 — Section text summary

| Section `type` | Required field(s) | Length | Content |
|---|---|---|---|
| `prose` / `narrative` / `dialogue` / `informational` | `prose_summary` | 100–250 words | Plot/argument arc, characters, setting, themes, tone. Plain prose. |
| `poem` | `poem_text` + `poem_appreciation_summary` | full verbatim / 60–120 words | `poem_text`: line and stanza breaks preserved. Appreciation covers theme, tone, central imagery, dominant device. |
| `picture_narrative` | `picture_story_summary` + `dialogue_text` (if any) | 100–150 words / verbatim | Describe the visual sequence — what the pictures show, the events, the theme. Do not invent prose. `dialogue_text`: speech-bubble lines verbatim with speaker labels. |

Mandatory for the section type. Stay strictly within the textbook — no outside knowledge. Very short texts get proportionally shorter summaries (40–80 words) but are never omitted. This summary is the source of truth for downstream LP teacher notes and assessment items.

## Step 4 — Identify present spines per section

Walk each main_section in textbook order. A spine may be fed by **multiple** textbook subheadings, and a spine may be **absent** (especially at prep, where poem sections often carry only Reading + Oracy + Vocab/Phonics). Do not invent absent spines.

| Spine | Default routing |
|---|---|
| `oracy` | Let us Speak · Let us Listen · Let us Think (when oral) · Let us Recite (when oral repetition) |
| `reading` | Picture Reading · Let us Read · Let us Recite (when silent/shared reading) · Let us Think (when written Q&A) |
| `writing` | Let us Write |
| `word_work` | Let us Learn (default) · Let us Speak (when phonics drill) |
| `beyond_text` | Let us Do · Let us Explore · Just for Fun · Do You Know |

Splits and overlaps:
- "Let us Think" → `reading` if written ("Answer. Write in the given space"); → `oracy` if oral ("Think and say", "Talk in pairs").
- "Let us Speak" → `oracy` for conversation; → `word_work` for phonics drills (sound blends, sight words, blend-and-decode).
- "Let us Recite" is typically the **display** of the poem itself (no tasks); tasks follow under Let us Think / Let us Speak / etc.
- For a `picture_narrative` section: the visual comprehension is `reading`; discussion tasks attached to it go under `oracy`.
- For multi-subheading spines, do not collapse to the first subheading only — pull all matching tasks and join their subheadings in `section_name` with ` + ` in textbook order.

## Step 5 — Capture tasks per (section, spine) cell

```json
{
  "section_name": "<textbook subheading(s); join multiple with ' + '>",
  "tasks_verbatim": [
    {
      "task_text": "<verbatim instruction + body; fold speech-bubble dialogue inline if the task references it>",
      "question_bank": [               // [] if the task is a single open prompt
        {
          "stem":     "<verbatim>",
          "type":     "MCQ" | "SCR" | "MATCH" | "FILL_IN" | "TRUE_FALSE" | "ORAL_PROMPT" | "WRITING_TASK" | "PROJECT",
          "options":  [...],           // MCQ only
          "table":    "header|cells\nrow|cells",   // when tabular
          "page_ref": "p.NN"
        }
      ],
      "visual_stimulus": [             // OPTIONAL — only when the task references images
        { "type": "picture" | "map" | "grid" | "photo" | "diagram" | "photo_series",
          "count": <int>, "brief_description": "<one line>", "page_ref": "p.NN" }
      ],
      "transcript_ref":  "p.NN",       // OPTIONAL — listening tasks only
      "transcript_text": "<...>"       // 80–120 words; segments represented, sequence intact, filler trimmed, speaker labels preserved
    }
  ]
}
```

Rules:
- One task per textbook instruction in textbook order. Sub-parts (a)/(b)/(c) of one parent roll up as sub-items of a single task — NOT separate tasks.
- **`type: "ECR"` is BANNED at preparatory.** Long-form writing is `WRITING_TASK` (rubric) or `SCR` (1–3 sentences).
- **Speech-bubble dialogue belongs inside `task_text`** when a task references it. Do not introduce a per-task `dialogue_text` field. (Section-level `dialogue_text` exists only for `picture_narrative` — see Step 3.)
- **Listening tasks live in `oracy`** with per-task `transcript_ref` + `transcript_text`. No separate listening spine at prep.
- Each `question_bank` entry belongs to exactly one task. Do not duplicate questions across tasks. The flat top-level `question_bank` shape on a spine is forbidden.
- A spine with no task objects is omitted entirely from its section's `spines` object.

## Step 6 — Effort signals

Compute AFTER `main_sections` is fully written, by literally counting array entries — do not estimate. Stored in the summary JSON under `effort_signals`; Step 7 copies them into the mapping JSON without recomputing.

**`spine_load` (1–3)** — average spines per section (max 5 at prep):
- avg ≤ 2.5 → 1  ·  avg 2.6–4.0 → 2  ·  avg ≥ 4.1 → 3

**`task_density` (1–3)** — average task objects per (section, spine) cell:
- avg ≤ 3.0 → 1  ·  avg 3.1–6.0 → 2  ·  avg ≥ 6.1 → 3

**`writing_demand` (0–2)** — total exercise-item count under the `writing` spine only. (Beyond_text is excluded at prep — it's dominated by puzzles, riddles, crafts, and `Do You Know` info boxes.) For each writing task, count `max(1, len(t.question_bank))` — open tasks ("write the poem as a story") count as 1, not 0. Formula:
```
sum(max(1, len(t.question_bank)) for cell in writing_cells for t in cell.tasks_verbatim)
```
Tier (prep-tuned): 0–3 → 0  ·  4–8 → 1  ·  9+ → 2.

**`project_load` (0–3)** — count of sections that have a `beyond_text` cell.

**`effort_index`:**
```
effort_index = (spine_load × 2) + (task_density × 1.5) + (writing_demand × 1.5) + (project_load × 1)
```
One decimal place. Do not clamp or round.

After computing, re-walk the JSON and confirm counts match actual array lengths. If they don't, the JSON wins — recompute the signals.

## Step 7 — Attach mapping (summary + separate mapping file)

**7a — In the summary JSON.** For each spine actually present in this chapter (union of `spines` keys across all `main_sections`), copy that spine's `competency_codes` from `spine_to_cg.json` verbatim into `competency_reporting.by_spine`. Do not emit entries for absent spines. Do not generate per-chapter tags.

**7b — Separate mapping JSON** at `mirror/chapters/english/{grade}/mappings/ch_NN_mapping.json`:

```json
{
  "stage": "preparatory",
  "subject": "english",
  "grade": "{grade}",
  "chapter_number": <int>,
  "chapter_title": "<verbatim>",
  "summary_path": "mirror/chapters/english/{grade}/summaries/ch_NN_summary.json",
  "primary": [ { "c_code": "C-1.1", "weight": 1 }, ... ],
  "incidental": [],
  "spine_load": <int>,
  "task_density": <int>,
  "writing_demand": <int>,
  "project_load": <int>,
  "effort_index": <float>,
  "chapter_weight": null
}
```

- `primary`: walk present spines in canonical order (`oracy`, `reading`, `writing`, `word_work`, `beyond_text`), emit one entry per unique `c_code` from each spine's `competency_codes`, de-duplicating across spines (first occurrence wins). All weights = 1. English uses `effort_index`, not weights, for period allocation.
- `spine_load`, `task_density`, `writing_demand`, `project_load`, `effort_index`: copy verbatim from the summary JSON's `effort_signals` block. Do not recompute.
- `chapter_weight`: always `null` for English.
- Two chapters share `primary` only when they share spine coverage.

UTF-8. Create `mappings/` if absent. Overwrite.

## Step 8 — Write summary JSON

Top-level shape:

```json
{
  "subject": "english",
  "stage": "preparatory",
  "grade": "{grade}",
  "chapter_number": <int>,
  "chapter_title": "<verbatim>",
  "main_sections": [ /* one entry per Step 2 section */ ],
  "competency_reporting": { "by_spine": { /* spines present → their c_codes (Step 7a) */ } },
  "effort_signals": { /* Step 6 values */ }
}
```

Each `main_section` carries:
- Common: `section_id`, `title`, `type`, `page_range`, `page_count`, `spines: { <spine>: { section_name, tasks_verbatim }, ... }`.
- `poem`: add `poem_text`, `poem_appreciation_summary`.
- `picture_narrative`: add `picture_story_summary`, `dialogue_text` (if any).
- Prose family: add `prose_summary`.

A spine with no tasks is omitted from `spines` entirely (do not emit empty cells). UTF-8. Overwrite.

For a full worked example, see the existing pilot files at `mirror/chapters/english/iii/summaries/ch_01_summary.json` (picture_narrative + poem) and `mirror/chapters/english/v/summaries/ch_01_summary.json` (single poem section with all 5 spines).

## Step 9 — Confirmation line

```
ch_NN — "<title>" — sections: <count> (<type breakdown>) — pages: A=<N> B=<N> [C=<N>] — spines_total: <N> — tasks: <total_tasks> — sub_items: <total_subitems> — visuals: <total_visuals> — project_load: <N> — effort_index: <value>
```

`pages: ...` echoes each section's `page_count` integer so the value the LP uses to allocate periods is visible at confirmation time.

Totals are sums over all (section, spine) cells:
- `tasks` = `sum(len(spine.tasks_verbatim))`
- `sub_items` = `sum(len(t.question_bank))` over all tasks
- `visuals` = `sum(len(t.visual_stimulus))` over tasks that have it

Example: `ch_01 — "Fun with Friends" — sections: 2 (1 picture_narrative + 1 poem) — pages: A=3 B=11 — spines_total: 7 — tasks: 9 — sub_items: 18 — visuals: 4 — project_load: 1 — effort_index: 6.5`

## Constraints

- No consulting LOs, Syllabus, Assessment Framework, or Position Papers. Pedagogy beyond `mirror/framework/english/preparatory/` is off-limits.
- Two output files per chapter (summary + mapping). Both must be present before moving to the next chapter. Process chapters in order. UTF-8. Overwrite.
