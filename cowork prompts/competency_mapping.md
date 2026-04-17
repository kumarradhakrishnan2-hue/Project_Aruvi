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
1. Read `ch_NN_summary.txt` from mirror — this is the sole chapter
   content reference. Do not read the chapter PDF.
2. Read `cg_{stage}_{subject}.txt` from mirror/framework/ — this is
   the Curricular Goals reference. 
3. Read the mapping constitution for the subject from mirror.

If `ch_NN_summary.txt` is absent, log a warning and skip that chapter.
Do not attempt to generate the summary here — run
`prompt_chapter_summary.md` first.

---

## Step 2 — Apply the constitution

Apply the subject-specific Competency Mapping Constitution exactly.
The constitution is the governing document — all mapping decisions
must follow its rules without exception.



**Prohibited documents for all subjects:**
Learning Outcomes, Pedagogy documents, Syllabus documents, Assessment
Framework documents, Position Papers — constitutionally excluded.

---

## Step 3 — Write the mapping JSON

Write one JSON record per chapter to:
`mnt/data/mirror/chapters/{subject}/{grade}/mappings/ch_NN_mapping.json`

```json
{
  "stage": "middle",
  "subject": "social_sciences",
  "grade": "vii",
  "chapter_number": 1,
  "chapter_title": "Geographical Diversity of India",
  "summary_path": "mirror/chapters/social_sciences/grade_vii/summaries/ch_01_summary.txt",
  "primary": [
    {
      "cg": "CG-6",
      "c_code": "C-6.1",
      "weight": 3,
      "justification": "..."
    }
  ],
  "incidental": [ { "cg": "CG-2", "c_code": "C-2.1" } ],
  "chapter_weight": 9
}
```


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
