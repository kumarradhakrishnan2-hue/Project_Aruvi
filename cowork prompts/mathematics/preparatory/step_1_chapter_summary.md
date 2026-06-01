# Cowork Session — Mathematics (Preparatory): Chapter Summary

Reads a Maths Mela chapter PDF for the **Preparatory stage (Grades III–V)**
and writes a structured summary JSON. Cowork reads the PDF and writes the
file directly. No API calls.

**Why this is separate from the middle prompt.** Middle maths (Ganita
Prakash) is built on numbered sections (§5.3), `Example N` worked examples,
and `Figure it Out` exercise banks. Maths Mela has none of these. Its
chapters are **named conceptual sections in textbook order**, moving
concrete → pictorial → symbolic, with student tasks sitting under intent
banners (*Let us Do / Think / Explore / Discuss / Play / Solve / Find /
Make*). So the spine here is **section flow** — the chapter's own sections,
walked in order — exactly like TWAU and Science prep, not the English
fixed-spine model. **Do not use this prompt for Grade VI or above.**

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
- `section_goal` — one OR two values, in textbook order, from:
  `recall` (count, name, identify, read a number/shape) ·
  `reason` (compare, explain why, spot a pattern, estimate) ·
  `apply` (compute, construct, convert, solve a problem). Two values only
  when the prose names two acts in sequence (e.g. *introduces … then
  applies*). Default is one.
- `tasks` — array of the student tasks in this section (Step 3). `[]` if none.

## Step 3 — Tasks (one per textbook instruction, in order)

```json
{
  "id":        "T-N",
  "banner":    "<verbatim banner, e.g. 'Let us Do'>",
  "intent":    "explore" | "reason" | "practice" | "play" | "solve",
  "book_ref":  "<banner + Q-number if numbered + page, e.g. 'Let us Do Q4, p.67'>",
  "description": "<verbatim instruction, ≤ 25 words; (a)/(b)/(c) sub-parts folded in>"
}
```

`intent` is read from the banner's purpose, not its name (the same banner
can serve different intents in different chapters):

| Banner | Usual intent |
|---|---|
| Let us Do (concept entry) · Let us Make · Let us Explore | `explore` |
| Let us Think · Let us Discuss · Let us Find · "Who am I" | `reason` |
| Let us Do (consolidation) · numbered practice lists | `practice` |
| Let us Play · games · puzzles (Magical Count, Number Hunt, Show and Tell) | `play` |
| Let us Solve · word problems | `solve` |

Rules: one task per instruction; sub-parts roll into one task. Unnumbered
prompts omit `Q<n>`. Never invent placeholder labels. `play` tasks are
captured but flagged — the prelims note most need not be assessed.

## Step 4 — Effort signals (count, do not estimate)

- `conceptual_demand` (1–3): 1 = recall/practice dominates (>60%);
  2 = reasoning/multi-step dominates or even; 3 = open-ended/estimation ≥30%.
- `activity_count` (int): hands-on / material-based tasks (`explore`, `play`, `make`).
- `demo_count` (int): teacher-demonstrated only (Teacher's Note walkthroughs). Usually 0.
- `exec_load` (0–2): multi-step computation/construction weight —
  0 = single-step; 1 = 30–60%; 2 = >60%.

## Step 5 — Write summary JSON

```json
{
  "stage": "preparatory",
  "subject": "mathematics",
  "grade": "{grade}",
  "chapter_number": <int>,
  "chapter_title": "<verbatim>",
  "sections": [
    { "ref": "S1", "title": "...", "section_goal": ["recall"],
      "prose_summary": "...",
      "tasks": [ { "id": "T-1", "banner": "...", "intent": "...", "book_ref": "...", "description": "..." } ] }
  ],
  "conceptual_demand": 2,
  "activity_count": 6,
  "demo_count": 0,
  "exec_load": 1
}
```

Rules: every `section_goal` is an array of length 1 or 2 (length 2 in
textbook order). Every task's section appears in `sections`. Every task
has a non-empty `book_ref`. `tasks` may be `[]` but `sections` may not.

## Step 6 — Confirmation line

Goal tally counts each section by its **first-listed** goal (totals equal
section count); append `· dual:N` if any section carries two goals.

```
ch_NN — "<title>" — sections: <N> — tasks: <T> — goals: recall×_ reason×_ apply×_ · dual:N — CD:_ AC:_ DC:_ EL:_
```

## Constraints

No API calls. No consulting LOs, Pedagogy, Syllabus, Assessment, or
Position Papers. Stay strictly within the chapter PDF. Process chapters in
order. UTF-8. Overwrite.

Step 2 (competency mapping) is unchanged: run the existing
`step_2_competency_mapping.md` against `cg_preparatory_mathematics.txt`.
Mapping stays **dynamic** (core CG + core/adjunct competencies + effort
index) — there is no static spine→CG lookup for maths, because core
linkages arise only from the per-chapter mapping pass.
