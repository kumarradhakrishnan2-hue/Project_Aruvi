# Cowork Session — Competency Mapping


## What this session does

Reads one or more chapter summaries from mirror and the NCF Curricular
Goals document, applies the subject-specific Competency Mapping
Constitution, and writes the competency mapping JSON for each chapter.

Chapter summaries must already exist in mirror before this session runs.
Run `prompt_chapter_summary.md` first if they are absent.

This session uses Cowork's own context. No API call is made.
No scripts from aruvi-scripts/ are invoked.

---

## Run Scope

Specify subject, grade, and chapter scope at the start of the session:

```
Single chapter  : map chapter 3 only
Multiple        : map chapters 1, 4, 8
All chapters    : map all chapters for this subject and grade
```

---

## Paths

| Item | Path |
|------|------|
| Project root (Cowork mount) | mnt/data/ |
| Chapter summaries | mnt/data/mirror/chapters/{subject}/{grade}/summaries/ch_NN_summary.txt |
| Curricular Goals | mnt/data/mirror/framework/{subject}/{stage}/cg_{stage}_{subject}.txt |
| Constitution | mnt/data/mirror/constitutions/competency_mapping/{subject}/mapping_constitution_{subject}.txt |
| Mapping output (per chapter) | mnt/data/mirror/chapters/{subject}/{grade}/mappings/ch_NN_mapping.json |


---

## Step 1 — Load inputs

For each chapter:
1. **Resolve `chapter_title` first (mandatory).** Read the first line
   of `ch_NN_summary.txt` — the title is written there as a plain text
   heading. Use that line verbatim as `chapter_title`. Do not infer
   the title from section headers or body content further into the file.
   If the first line is absent or blank, log a warning and halt for
   that chapter.
2. Read `ch_NN_summary.txt` from mirror — this is the sole chapter
   content reference. Do not read the chapter PDF.
3. Read `cg_{stage}_{subject}.txt` from mirror/framework/ — this is
   the Curricular Goals reference.
4. Read the mapping constitution for the subject from mirror.

If `ch_NN_summary.txt` is absent, log a warning and skip that chapter.
Do not attempt to generate the summary here — run
`prompt_chapter_summary.md` first.

---

## Step 2 — Apply the constitution

Apply the subject-specific Competency Mapping Constitution exactly.
The constitution is the governing document — all mapping decisions
must follow its rules without exception.

**Cross-verification (mandatory before writing JSON):**
Before writing any mapping JSON, confirm for each competency assigned:
1. Quote the exact named section header(s) from the summary that justify it.
2. Confirm those headers are present in the summary file for THIS chapter number.
3. Confirm `chapter_number` matches the `NN` in the summary filename and `chapter_title` matches the title on the first line of that summary file.

If any competency cannot be anchored in a named section verifiably present
in the target ch_NN_summary.txt, remove it from the mapping.

**Prohibited documents for all subjects:**
Learning Outcomes, Pedagogy documents, Syllabus documents, Assessment
Framework documents, Position Papers — constitutionally excluded.

---

## Step 3 — Write the mapping JSON

Write one JSON record per chapter to:
`mnt/data/mirror/chapters/{subject}/{grade}/mappings/ch_NN_mapping.json`

**Field sourcing rules — every field must be derived as specified below:**

| Field | Source | Rule |
|-------|--------|------|
| `stage` | Run scope declared at session start | Map grade to stage: III–V → `"foundational"`, VI–VIII → `"middle"`, IX–X → `"secondary"` |
| `subject` | Folder path | The `{subject}` segment of `mirror/chapters/{subject}/{grade}/summaries/` |
| `grade` | Folder path | The `{grade}` segment of `mirror/chapters/{subject}/{grade}/summaries/` |
| `chapter_number` | Summary filename | Parse `NN` from `ch_NN_summary.txt`; strip leading zero; write as integer |
| `chapter_title` | First line of `ch_NN_summary.txt` | Read the title heading from the top of the summary file; used verbatim |
| `summary_path` | Constructed | `mirror/chapters/{subject}/{grade}/summaries/ch_NN_summary.txt` using derived values |
| `cg` | CG document | CG label exactly as it appears in the CG document header (e.g. `CG-6`) |
| `c_code` | CG document | C-code label exactly as it appears in the CG document (e.g. `C-6.1`) |
| `weight` | Constitution Rules 4–6 | Apply weight rules from the constitution; do not assign weight by any other means |
| `justification` | Summary file (Step 2 cross-verification) | Must be anchored to named section headers present in `ch_NN_summary.txt` |
| `chapter_weight` | Calculated | Sum of all `weight` values across all `primary` entries |


## Step 4 — Print verification summary

After each chapter, print one confirmation line:

```
ch_01 | Geographical Diversity of India | primary: C-6.1 (W3), C-7.2 (W2) | chapter_weight: 9
```

If any chapter summary was missing, list all skipped chapters at the end.

---

## Constraints

- Do not read chapter PDFs. The chapter summary is the sole content input.
- Do not consult Learning Outcomes, Pedagogy, Syllabus, Assessment
  Framework, or Position Papers — constitutionally prohibited.
- Do not call the Claude API. Cowork reads all inputs directly.
- Do not invoke any scripts from aruvi-scripts/.
- Process chapters in the order specified.
- All files written in UTF-8 encoding.
- If a mapping file already exists for a chapter, overwrite it.
