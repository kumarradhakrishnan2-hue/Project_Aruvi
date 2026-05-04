# Cowork Session — English: Chapter Summary + Static Competency Mapping

Reads an English chapter PDF (preparatory / middle / secondary) and writes a
structured summary JSON. Cowork reads and writes directly. No API calls.

The summary follows the **two-axis** structure of an English NCERT chapter:

```
chapter
└── main_section A (prose | poem | narrative | dialogue)
    ├── spine: reading
    ├── spine: listening
    ├── spine: speaking
    ├── spine: writing
    ├── spine: vocabulary_grammar
    └── spine: beyond_text
└── main_section B (often a poem under "Reading for Appreciation" at IX)
    └── spines that this section actually carries (often only reading + vocabulary_grammar)
└── main_section C (occasional, at middle/secondary)
```

The competency mapping is **static at the stage level**, not per-chapter. The
prompt looks it up from `mirror/framework/english/{stage}/spine_to_cg.json`
and attaches the C-codes to each spine in the output. **No per-chapter
competency mapping is performed.**

## Run scope

Specify grade and chapter scope. Subject is `english`. `{stage}` derives
from grade: III–V → `preparatory`, VI–VIII → `middle`, IX–X → `secondary`.

## Paths

| Item | Path |
|------|------|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/English/{grade}/` |
| Static spine→CG | `mnt/data/mirror/framework/english/{stage}/spine_to_cg.json` |
| NCF CG (read for context) | `mnt/data/mirror/framework/english/{stage}/cg_{stage}_english.txt` |
| NCF Pedagogy (read for context) | `mnt/data/mirror/framework/english/{stage}/pedagogy_{stage}_english.txt` |
| Output | `mnt/data/mirror/chapters/english/{grade}/summaries/ch_NN_summary.json` |

## Step 1 — Chapter title and stage

Extract the chapter title verbatim from the opening page. Set
`stage` from the grade per the mapping above.

## Step 2 — Detect main sections (1 to 3)

A `main_section` is a distinct text the student reads in the chapter — a
prose narrative, a poem, a dialogue, or an informational piece. The
chapter spine sections (Reading / Listening / Speaking / etc.) wrap
around the main_section's text, providing comprehension, exercises and
output tasks tied to that text.

Detection signals — any ONE of these starts a new main_section:

1. A new chapter-title-style heading appears (centred, larger font,
   sometimes with a separate author byline like "Sudha Murty",
   "Maya Anthony", "Charles Swain", "Ruskin Bond").
2. The textbook explicitly introduces a new text under a heading
   like "Reading for Appreciation" (IX/X convention — typically a
   short poem that closes the chapter).
3. A clear shift from prose to poem (poem has line breaks, indentation,
   no paragraph flow), or vice versa.
4. The textbook re-runs a spine cycle (a second "Let us Read" or
   "Reading for Meaning" appears within the same chapter for a
   different text).

Stage-specific defaults to confirm against the PDF:

- **Preparatory (V)**: typically 1 main_section (the chapter's main text).
  Occasionally 2 if a separate riddle / story / fable appears under
  "Let us Explore" or "Just for Fun".
- **Middle (VII)**: typically 2 main_sections — a primary text + a
  secondary text or a related literary piece.
- **Secondary (IX)**: typically 2 main_sections — a primary prose +
  a poem under "Reading for Appreciation".

Assign `section_id` = "A", "B", "C" in textbook order. Capture each
section's `title`, `type` (`prose` | `poem` | `narrative` | `dialogue`
| `informational`), `page_range`, and `char_count` (rough character
count of the text body, not exercises).

## Step 3 — Per main_section, write the text summary

For each main_section, capture what the student actually reads. This is
the source of truth for downstream LP planning and assessment grounding.

By section type:

- **`prose` / `narrative` / `informational`**:
  Write a `prose_summary` of 200–400 words covering plot/argument,
  characters/key entities, setting, themes, tone, and any pivotal
  passages. Plain prose. No bullets. Stay strictly within the textbook —
  no outside knowledge, no interpretation beyond what the text states
  or clearly implies.

- **`poem`**:
  Capture the full poem text verbatim in a `poem_text` field (newline-
  separated lines, stanza breaks preserved). Then write a
  `poem_appreciation_summary` of 80–150 words covering theme, tone,
  central imagery, and the dominant literary device(s) the poet uses.
  No interpretation that the poem itself does not support.

- **`dialogue`**:
  Write a `prose_summary` of 200–400 words naming the speakers, the
  context of the exchange, and the key turning points or revelations.

The text summary fields are MANDATORY — no main_section may be emitted
without them. If a main_section is a very short text (a riddle, a
4-line verse), write a shorter summary proportional to the source
(e.g., 50–100 words), but still write it.

These fields are the source of truth referenced by:
- The LP generator when teacher_notes describe what the period covers.
- The assessment generator when verifying answers and grounding
  generated items.

## Step 4 — Per main_section, identify present spine sections

For each main_section, walk the textbook in order and identify which of
the six spines are present. Use the static lookup
`spine_to_cg.json.spines.<spine>.textbook_section_names[]` for matching:

| Spine | Stage V matches | Stage VII matches | Stage IX matches |
|---|---|---|---|
| `reading` | Let us Read, Let us Recite, Let us Think | Let us read, Let us discuss, Let us think | Reading for Meaning, Check Your Understanding, Critical Reflection, Reflect and Respond, Reading for Appreciation |
| `listening` | Let us Listen | Let us listen | Listen and Respond |
| `speaking` | Let us Speak | Let us speak | Speaking Activity |
| `writing` | Let us Write | Let us write | Writing Task |
| `vocabulary_grammar` | Let us Learn | Let us learn | Vocabulary and Structures in Context, Vocabulary in Context |
| `beyond_text` | Let us Do, Let us Explore, Just for Fun | Let us do, Let us explore | Learning Beyond the Text, POINTS TO REMEMBER |

A spine may legitimately be ABSENT from a main_section. A short poem
under "Reading for Appreciation" often only carries `reading` +
`vocabulary_grammar`. Do not invent missing spines.

## Step 5 — Per (section, spine) cell, capture tasks and question bank

For each present (section, spine) cell, capture:

- `section_name` — the textbook subheading verbatim (e.g. "Reading for
  Meaning", "Let us Speak").
- `tasks_verbatim` — every in-class task instruction listed under that
  subheading, lifted verbatim. Each task is one entry. Sub-parts
  (a), (b), (c) of one parent task roll up into one entry; sub-parts
  are captured in the entry's text.
- `question_bank` — the textbook's own exercise / question items in
  the cell. Each entry:
  ```json
  {
    "stem":       "<verbatim question text>",
    "type":       "MCQ" | "SCR" | "ECR" | "MATCH" | "FILL_IN" |
                  "TRUE_FALSE" | "ORAL_PROMPT" | "WRITING_TASK" |
                  "PROJECT",
    "options":    [...],         // MCQ only
    "table":      "pipe|table",  // when the question carries tabular
                                 // data the student must read or fill
    "page_ref":   "p.NN"
  }
  ```
## Step 6 — Listening cells: capture transcript reference

For every (section, spine=listening) cell, capture `transcript_ref` as
the page number of the textbook's transcript appendix (NCERT books
ship listening transcripts at the end of each chapter, typically under
a "TRANSCRIPTS" banner). Format: `"p.NN"`. Do NOT inline the transcript
text into the summary — the page reference is sufficient.

## Step 7 — Effort signals

Compute at the chapter level:

- `total_char_count` — sum of `char_count` across all main_sections'
  text bodies.
- `total_task_count` — total number of `tasks_verbatim` entries across
  all (section, spine) cells.
- `total_question_bank_count` — total entries across all `question_bank`
  arrays.
- `project_load` — count of `beyond_text` cells across all
  main_sections (one cell = one unit of project load).
- `main_section_count` — number of main_sections detected (typically
  1, 2, or 3).

These feed the allocation tab's effort index downstream.

## Step 8 — Attach static competency mapping

Read `mirror/framework/english/{stage}/spine_to_cg.json` and copy each
spine's `competency_codes` array verbatim into the summary's
`competency_reporting.by_spine` block. **Do NOT generate per-chapter
competency tags.** This block is decorative and informs reporting in
LP and assessment outputs.

## Step 9 — Write summary JSON

```json
{
  "subject": "english",
  "stage": "secondary",
  "grade": "ix",
  "chapter_number": 3,
  "chapter_title": "Winds of Change",

  "main_sections": [
    {
      "section_id": "A",
      "title": "Pankhas Across India",
      "type": "prose",
      "page_range": "p.69-80",
      "char_count": 25000,
      "prose_summary": "<200–400 word textbook-grounded summary of the prose: argument arc, key entities (states, materials, makers), themes (craft heritage, regional variation, change over time), tone, and any pivotal passages.>",
      "spines": {
        "reading": {
          "section_name": "Reading for Meaning",
          "char_count": 4800,
          "tasks_verbatim": ["..."],
          "question_bank": [
            {
              "stem": "Work in pairs to complete the table on pankha.",
              "type": "MATCH",
              "table": "State|Type of Fan|Material Used\nRajasthan|appliqué hand fan|...",
              "page_ref": "p.73"
            }
          ]
        },
        "listening": {
          "section_name": "Listen and Respond",
          "transcript_ref": "p.263",
          "tasks_verbatim": ["..."],
          "question_bank": [ /* ... */ ]
        },
        "speaking":           { "section_name": "Speaking Activity",                     "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "writing":            { "section_name": "Writing Task",                          "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "vocabulary_grammar": { "section_name": "Vocabulary and Structures in Context",  "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "beyond_text":        { "section_name": "Learning Beyond the Text",              "tasks_verbatim": ["..."], "question_bank": [/* ... */] }
      }
    },
    {
      "section_id": "B",
      "title": "Canvas of Soil",
      "type": "poem",
      "page_range": "p.79",
      "char_count": 600,
      "poem_text": "Palette of earth, rich and deep,\nWhere dreams of gardeners seep.\n...\n(full poem verbatim, line breaks and stanza breaks preserved)",
      "poem_appreciation_summary": "<80–150 word appreciation: theme (the gardener as artist), tone (celebratory, contemplative), central imagery (palette / brushstrokes / canvas — visual-art lexicon mapped onto a garden), dominant device (extended metaphor of garden-as-painting).>",
      "spines": {
        "reading":            { "section_name": "Reading for Appreciation", "tasks_verbatim": ["..."], "question_bank": [/* ... */] },
        "vocabulary_grammar": { "section_name": "Vocabulary in Context",    "tasks_verbatim": ["..."], "question_bank": [/* ... */] }
      }
    }
  ],

  "competency_reporting": {
    "by_spine": {
      "reading":            ["C-2.1", "C-2.2", "C-3.1", "C-4.1"],
      "listening":          ["C-3.1"],
      "speaking":           ["C-1.1", "C-3.2"],
      "writing":            ["C-1.2", "C-1.3", "C-1.4", "C-2.3"],
      "vocabulary_grammar": ["C-2.2"],
      "beyond_text":        ["C-4.2", "C-4.3", "C-4.4", "C-4.5"]
    }
  },

  "effort_signals": {
    "total_char_count": 37363,
    "total_task_count": 28,
    "total_question_bank_count": 14,
    "project_load": 2,
    "main_section_count": 2
  }
}
```

Rules:
- Every `main_sections[i].section_id` is "A", "B", or "C" — sequential.
- Every main_section MUST carry the text-summary fields per its `type`:
  - `type` ∈ {prose, narrative, dialogue, informational} → `prose_summary`
    (200–400 words; mandatory)
  - `type` = `poem` → BOTH `poem_text` (full verbatim text with line and
    stanza breaks) AND `poem_appreciation_summary` (80–150 words;
    mandatory)
  - Mixed-type sections: pick the dominant type and use its convention.
- Every spine in a section's `spines` object has at least one of:
  `tasks_verbatim` non-empty OR `question_bank` non-empty. A spine
  with neither must be omitted from the section.
- `competency_reporting.by_spine` is copied verbatim from
  `spine_to_cg.json.spines.<spine>.competency_codes`.
- No per-chapter competency assignments. No mapping JSON file is
  written by this prompt.
- UTF-8. Overwrite if the file exists.

## Step 10 — Confirmation line

```
ch_03 — "Winds of Change" — sections: 2 (1 prose + 1 poem) — spines_total: 8 — tasks: 28 — question_bank: 14 — project_load: 2
```

Format: `ch_NN — "<title>" — sections: <count> (<breakdown by type>) — spines_total: <sum across sections> — tasks: <total_task_count> — question_bank: <total_question_bank_count> — project_load: <count>`

## Constraints

- No API calls — Cowork reads PDFs and writes JSON directly.
- No consulting LOs, Pedagogy beyond what's in the mirror, Syllabus,
  Assessment Framework, or Position Papers.
- Do NOT perform per-chapter competency mapping. The mapping is static
  at the stage level (`spine_to_cg.json`) and only attached
  decoratively.
- Do NOT inline listening transcripts — only the page reference.
- Do NOT invent missing spines. A poem appendix with only Reading +
  Vocabulary is correctly captured with only those two spines.
- Process chapters in order. UTF-8. Overwrite.
