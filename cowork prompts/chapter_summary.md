# Cowork Session — Chapter Summary Generation

## What this session does

Reads one or more chapter PDFs and writes a grounded chapter summary
for each. The summary is the content reference used by the competency
mapping session and by the runtime lesson plan and assessment generation.

This session uses Cowork's own context to read the PDF and write the
summary. No API call is made.

---

## Run Scope

Specify which chapters to process at the start of the session:

```
Single chapter  : process chapter 9 only
Multiple        : process chapters 1, 4, 8
All chapters    : process all chapters in the textbook folder
```

Tell Cowork the subject, grade, and chapter scope before starting.

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Chapter PDFs | mnt/data/knowledge_commons/textbooks/{subject}/{grade}/ |
| Summary output | mnt/data/mirror/chapters/{subject}/{grade}/summaries/ |

Files are named: `Chapter NN - Title.pdf`
Output files are named: `ch_NN_summary.txt`

---

## Step 1 — Locate the PDF

Match chapter number to the correct file in the textbook folder.

---

## Step 2 — Identify scope boundary

Read the full chapter PDF. List every section and subsection heading
present in the chapter, in the order they appear. This heading list is
the scope boundary for the summary.

No concept, phenomenon, process, person, event, formula, or example
may appear in the summary unless it is anchored to one of these headings.
This rule is absolute — it prevents content from outside this chapter
appearing in the summary even if the topic is familiar.

---

## Step 3 — Write the summary

Write a summary of 800–1200 words addressing every heading identified
in Step 2, in the order they appear.

For each heading write 2–4 sentences covering:
- What the section teaches
- The key concepts or terms it introduces
- Any significant phenomena, processes, or examples it uses
- Whether the section contains a student activity — note existence
  only, do not elaborate activity steps

**Rules:**
- Use the textbook's own section and subsection headings as the
  organising structure. Do not rename, merge, or reorder them.
- Do not describe exercises, end-of-chapter questions, or exploratory
  projects.
- Do not introduce content from outside this chapter. If you find
  yourself writing about something the chapter does not cover, stop
  and delete it.
- Write in plain prose. No bullet points. No tables.
- Output summary text only. No preamble. No word count statement.

---

## Step 4 — Save the output

Save to: `mnt/data/mirror/chapters/{subject}/{grade}/summaries/ch_NN_summary.txt`
(NN = zero-padded chapter number, e.g. `ch_09_summary.txt`)

---

## Step 5 — Verification

After writing each summary, print one line to confirm:

```
ch_09_summary.txt — written — 943 words — sections: 9.1, 9.1.1, 9.1.2, 9.2, 9.2.1, 9.2.2
```

If any chapter PDF is not found, log a warning and skip — do not halt.

---

## Constraints

- Do not call the Claude API. Cowork reads the PDF directly.
- Do not generate competency mappings or effort index values.
- Do not modify any existing mapping JSON.
- Process chapters in the order specified.
- All files written in UTF-8 encoding.
- If a summary file already exists for a chapter, overwrite it.
