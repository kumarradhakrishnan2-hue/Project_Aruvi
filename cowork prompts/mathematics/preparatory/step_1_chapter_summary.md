# Cowork Session — Mathematics (Preparatory): Chapter Summary

Reads a Maths Mela chapter PDF for the **Preparatory stage (Grades III–V)**
and writes a structured summary JSON. Cowork reads the PDF and writes the
file directly. No API calls.


## Paths

| Item | Path |
|---|---|
| Chapter PDFs | `mnt/data/knowledge_commons/textbooks/mathematics/{grade}/` |
| Output | `mnt/data/mirror/chapters/mathematics/{grade}/summaries/ch_NN_summary.json` |

`{grade}` is the lowercase Roman numeral folder: `iii`, `iv`, `v`.

## Step 1 — Title and section list

Extract `chapter_title` verbatim from the opening page. Set
`stage = "preparatory"`. List every **named conceptual section** in
textbook reading order. A section is a distinct idea-block the chapter
develops (e.g. *counting beyond 200*, *place value with H-T-O*,
*comparing numbers*) — usually signalled by a heading, a new sub-theme,
or a fresh concept entry, **not** by a banner. This ordered list is the
summary's single structural axis; the lesson plan walks it in order.
Nothing below may reference a section not in this list.

Sections have no textbook numbers. Assign `ref` = `S1`, `S2`, … in order.

## Step 2 — Per-section capture

For each section, in order, record:

- `ref` — `S1`, `S2`, …
- `title` — short label for the idea-block (≤ 8 words). Use the textbook
  heading if one exists; otherwise name the idea from its content.
- `prose_summary` — 2–4 sentences: what the section teaches, the key
  concept, the concrete material or model used (matchsticks, Dienes
  blocks, number line, pan-balance, paper-folding), and where it sits on
  the concrete → pictorial → symbolic path. Anchor every sentence to the
  chapter. No outside content.
- `tasks` — array of the student tasks in this section (Step 3). `[]` if none.

## Step 3 — Tasks (one per textbook instruction, in order)

```json
{
  "id":        "T-N",
  "banner":    "<verbatim banner, e.g. 'Let us Do'>",
  "intent":    "explore" | "reason" | "practice" | "solve",
  "book_ref":  "<banner + Q-number if numbered + page, e.g. 'Let us Do Q4, p.67'>",
  "description": "<verbatim instruction, ≤ 25 words; (a)/(b)/(c) sub-parts folded in>"
}
```

`intent` is strictly **what the student is expected to do** — the
cognitive act — judged from the `description`, NOT from the banner name.
The same banner serves different intents in different places (e.g. *Let us
Do* opens a concept in one section and drills practice in another), so the
banner alone never fixes the intent. Choose exactly one of four:

| intent | The task asks the student to… |
|---|---|
| `explore` | handle material, fold/build, observe, enter a new idea by doing (matchsticks, Dienes blocks, paper-folding, firki) |
| `reason` | compare, estimate, explain why, spot/extend a pattern, deduce ("Who am I", "which is more and why") |
| `practice` | consolidate a known idea by repetition (drill lists, fill-in, mark on number line) |
| `solve` | work a routine or word problem to an answer (computation, unit conversion) |

There is **no `play` intent**. A game or puzzle is a *mode of delivery*,
not an expected act — so a game's true intent is whichever of the four it
actually exercises (a Number-Hunt is usually `practice` or `reason`). Tag
that underlying act like any other task; game-ness is not separately
recorded.

Banner is only a starting hint, overridden by the description: *Let us
Explore/Make* → often `explore`; *Let us Think/Discuss/Find* → often
`reason`; *Let us Solve* → `solve`; *Let us Do* → `explore` or `practice`
by the task; *Let us Play* / named games → tag the underlying act.

**Why `intent` matters (two downstream uses).** It is the load-bearing
field of the prep pipeline:

1. *Pedagogical method (LP).* Each intent maps to the NCF method whose
   described purpose matches it, applied **per task** (prep periods mix
   intents, so method is a task property, not a period property):
   `explore` → Play-way / Inquiry · `reason` → Inductive ·
   `solve` → Problem-solving · `practice` → meaningful practice. This
   default map honours prep frequency (Play-way & Inductive MORE_OFTEN,
   Deductive LESS_OFTEN); the LP may override it (it is a default, not a rule).
2. *Assessment axis.* Prep assessment is organised on the intent axis —
   the student's expected act — not recall/reason/apply, and never on the
   teaching method. One item per intent present in the chapter's enacted
   tasks. Game tasks carry a normal intent and are assessable like any
   other (the book's "games needn't be assessed" is soft guidance, not a
   hard exclusion).

Rules: one task per instruction; sub-parts roll into one task. Unnumbered
prompts omit `Q<n>`. Never invent placeholder labels.

## Step 4 — Effort signals (count from `tasks`, do not estimate)

Four prep-native signals. Counts are over all task objects in the chapter;
"share" means that count ÷ total tasks. These feed the **preparatory**
mapping constitution's effort-index formula — they are NOT the middle
signals (`activity_count`/`demo_count` have no meaning at prep maths).

- `conceptual_demand` (1–3): abstraction on the concrete→symbolic path.
  1 = concrete handling / counting / naming dominates; 2 = comparison,
  estimation, or place-value/unit reasoning dominates; 3 = multi-step
  conversion or pattern-generalisation is a substantial share (≥30%).
- `task_load` (0–3): discrete tier from total task count —
  <10 → 0 · 10–19 → 1 · 20–29 → 2 · ≥30 → 3.
- `exploration_load` (0–2): share of `explore` tasks (hands-on /
  manipulative / discovery). 0 = <20% · 1 = 20–50% · 2 = >50%.
  The prep-distinctive signal — concrete doing is the stage's core.
- `procedural_load` (0–2): share of `solve` + `practice` tasks
  (computation / conversion / drill). 0 = <20% · 1 = 20–50% · 2 = >50%.

## Step 5 — Write summary JSON

```json
{
  "stage": "preparatory",
  "subject": "mathematics",
  "grade": "{grade}",
  "chapter_number": <int>,
  "chapter_title": "<verbatim>",
  "sections": [
    { "ref": "S1", "title": "...",
      "prose_summary": "...",
      "tasks": [ { "id": "T-1", "banner": "...", "intent": "...", "book_ref": "...", "description": "..." } ] }
  ],
  "conceptual_demand": 2,
  "task_load": 1,
  "exploration_load": 2,
  "procedural_load": 1
}
```

Rules: every task's section appears in `sections`. Every task has a
non-empty `book_ref` and an `intent` (one of four). `tasks` may be `[]`
but `sections` may not. No `section_goal` field, no `play` intent.

## Step 6 — Confirmation line

Tally tasks by `intent`.

```
ch_NN — "<title>" — sections: <N> — tasks: <T> — intents: explore×_ reason×_ practice×_ solve×_ — CD:_ TL:_ EXP:_ PROC:_
```

## Constraints

No API calls. No consulting LOs, Pedagogy, Syllabus, Assessment, or
Position Papers. Stay strictly within the chapter PDF. Process chapters in
order. UTF-8. Overwrite.

Next: run `step_2_competency_mapping.md` in this folder, governed by the
**preparatory** mapping constitution
(`competency_mapping/mathematics/preparatory/mapping_constitution_mathematics.txt`).
Mapping stays **dynamic** (core CG + core/adjunct competencies + effort
index from the four signals above) — there is no static spine→CG lookup
for maths, because core linkages arise only from the per-chapter pass.
