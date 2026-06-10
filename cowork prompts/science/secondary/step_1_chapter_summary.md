# Cowork Session — Chapter Summary Generation (Science · Secondary Stage)

## What this session does

Reads one or more secondary-stage Science chapter PDFs (Grade IX / X) and writes a
grounded chapter summary for each. The summary is the content reference used by the
competency mapping (effort index) session and by the runtime lesson plan and assessment
generation.

This session uses Cowork's own context to read the PDF and write the summary. No API call
is made.

---

## Run Scope

Specify which chapters to process at the start of the session:

```
Single chapter  : process chapter 8 only
Multiple        : process chapters 2, 8
All chapters    : process all chapters in the textbook folder
```

Tell Cowork the subject, grade, and chapter scope before starting.

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Chapter PDFs | mnt/data/knowledge_commons/textbooks/science/{grade}/ |
| Summary output | mnt/data/mirror/chapters/science/{grade}/summaries/ |

Files are named: `Chapter NN - Title.pdf`
Output files are named: `ch_NN_summary.txt`

---

## Step 1 — Locate the PDF

Match chapter number to the correct file in the textbook folder.

---

## Step 2 — Extract chapter title

Read the chapter title exactly as it appears in the PDF (typically on the opening page of
the chapter). Record it verbatim — do not paraphrase or normalise casing. This title is
written as the first line of the output file in the format:

```
Chapter NN: <Title>
```

followed by a blank line, before the summary text begins.

---

## Step 3 — Identify the scope boundary

Read the full chapter PDF. List, in the order they appear, every heading that structures
the chapter's instructional content. The heading list is the scope boundary for the
summary: no concept, phenomenon, process, person, event, formula, or example may appear in
the summary unless it is anchored to one of these headings. This rule is absolute — it
prevents content from outside this chapter (e.g. from a neighbouring chapter that shares
vocabulary) appearing in the summary even if the topic is familiar.

**Two kinds of heading belong in the scope boundary:**

1. **Numbered headings and subsections** — e.g. `8.1`, `8.2`, `8.2.1`, `2.2.1`, `2.3.1`.
2. **Named content-blocks** — bold-titled blocks that introduce a distinct concept,
   organelle, model, or process but carry no section number. These are part of the
   instructional spine and MUST be listed and covered. Examples:
   - In *Cell*: `Nucleus — House of coded instructions`, `Ribosomes — The protein
     factories`, `Endoplasmic Reticulum (ER)`, `Golgi apparatus`, `Lysosomes`,
     `Mitochondria — The powerhouse of the cell`, `Plastids`, `Vacuoles`.
   - In *Journey Inside the Atom*: `A. Rutherford's model of an atom`,
     `B. Limitations of Rutherford's model`, `C. Discovery of the proton`.

   Distinguish a named content-block (introduces chapter content → include) from a
   pedagogical sidebar box (recurring furniture → exclude; see below).

**Exclude these recurring pedagogical sidebar boxes** — they are NOT section
headings, MUST NOT appear in the heading list, and MUST NOT structure the summary:
`Think It Over`, `Pause and Ponder`, `Threads of Curiosity`, `Ready to Go Beyond`,
`Think as a Scientist`, `What if ...`, `Next Level Up`, `Meet a Scientist`, `At a Glance`,
`Revise, Reflect, Refine`, `The Journey Beyond`, `The Quest Continues ...`.
(`Revise, Reflect, Refine` is the secondary end-of-chapter exercise section — it is excluded
under the same rule that excludes exercises, see Step 4.)

**Controlled exception — real-world / India-contribution boxes.** Two named
boxes carry substantive NCF content (curricular goals CG-5 linkages, CG-6 India's
contribution, CG-7 frontiers) rather than motivational framing:
`India's Scientific Contributions` and `Bridging Science and Society`. Capture their
substantive content — but ONLY in the single dedicated closing paragraph described in
Step 4, never woven into the heading-anchored body. Do not capture `Meet a Scientist`
biographies under this exception.

---

## Step 4 — Write the summary

Write the summary addressing every heading identified in Step 3 — both numbered headings
and named content-blocks — in the order they appear.

For each heading or named content-block write 3–4 sentences covering:
- What the section teaches
- The key concepts or terms it introduces
- Any significant phenomena, processes, formulae, or examples it uses
- Whether the section contains a student activity — note existence only, do not elaborate
  activity steps

**Length is content-driven, not capped.** Give every heading and named content-block its
3–4 sentences; do not compress several organelles or model-blocks into a single clause to
hit a word target, and do not pad to reach one. A typical chapter has roughly 16–20 heading
units and lands at approximately **1200–1800 words**; a heading-dense chapter may run
longer. Coverage of every unit takes precedence over any word figure.

**One closing CG-5/6/7 paragraph (optional, only if such content exists).**
After the heading-anchored body, if the chapter contained an `India's Scientific
Contributions` or `Bridging Science and Society` box, add ONE final short paragraph (2–4
sentences) recording its substantive real-world / Indian-contribution / frontier content.
Begin it plainly (e.g. "The chapter also connects this science to …"). If neither box is
present, omit this paragraph entirely.

**Rules:**
- Use the textbook's own headings and named content-blocks as the organising structure. Do
  not rename, merge, or reorder them.
- Do not describe exercises, end-of-chapter questions (`Revise, Reflect, Refine`), or
  exploratory projects (`The Journey Beyond`).
- Do not introduce content from outside this chapter. If you find yourself writing about
  something the chapter does not cover, stop and delete it.
- Write in plain prose. No bullet points. No tables.
- Output summary text only. No preamble. No word count statement.

---

## Step 5 — Save the output

Save to: `mnt/data/mirror/chapters/science/{grade}/summaries/ch_NN_summary.txt`
(NN = zero-padded chapter number, e.g. `ch_08_summary.txt`)

---

## Step 6 — Verification

After writing each summary, print one line to confirm:

```
ch_08_summary.txt — written — "Journey Inside the Atom" — 1542 words — units: 8.1, 8.2, 8.2.1, 8.2.2, A, B, C, 8.2.3, 8.3, 8.3.1, 8.4, 8.5, 8.6, 8.7, 8.7.1, 8.8, 8.9, 8.9.1, 8.9.2 — CG5/6/7 closing para: yes
```

List both numbered headings and named content-blocks under `units:`. If any chapter PDF is
not found, log a warning and skip — do not halt.

---

## Constraints

- Do not call the Claude API. Cowork reads the PDF directly.
- Do not generate competency mappings or effort index values.
- Do not modify any existing mapping JSON.
- Process chapters in the order specified.
- All files written in UTF-8 encoding.
- If a summary file already exists for a chapter, overwrite it.
