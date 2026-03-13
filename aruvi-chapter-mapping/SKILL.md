---
name: aruvi-chapter-mapping
description: >
  Runs the Aruvi build_chapter_mapping pipeline for one or more NCERT chapters.
  Given only a subject group and grade, automatically resolves all paths from
  aruvi_config.json and calls Claude API (claude-sonnet-4-6) with the correct
  Competency Mapping Constitution to produce Chapter Mapping JSON records.

  USE THIS SKILL whenever the user asks to:
  - Map a chapter or set of chapters to NCF competencies for Aruvi
  - Run build_chapter_mapping for any subject/grade combination
  - Generate or update chapter_mappings_{subject}_{grade}.json
  - Run pilot chapters before bulk mapping
  - Add a new subject or grade to the Aruvi platform (Phase B of build guide)
  - Check what chapters are available for a subject/grade (dry run)

  Works for all four subject groups: social_sciences, languages, mathematics, science.
  Works for all grades vi through x. Two arguments (subject + grade) are all that
  is needed — everything else resolves automatically from aruvi_config.json.
---

# Aruvi Chapter Mapping Skill

## Project Structure (Mac-side)

The project lives at `/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi/`.
GitHub: https://github.com/kumarradhakrishnan2-hue/project-aruvi

```
Project Aruvi/
├── .env                          ← ANTHROPIC_API_KEY (never commit)
├── .gitignore                    ← protects .env, .DS_Store, __pycache__
├── aruvi_config.json             ← project_root = "DYNAMIC"
├── run_mapping.sh                ← stable entry point (use this)
├── aruvi-scripts/                ← canonical patched scripts
│   ├── run_mapping.py
│   ├── call_mapping_api.py       ← patched: verify=False + socks proxy fix
│   ├── config_resolver.py        ← patched: DYNAMIC root + mirror constitution
│   ├── extract_chapter.py
│   ├── extract_cg.py
│   └── run_wrapper.py
├── knowledge_commons/
│   ├── constitutions/competency_mapping/{subject}/   ← DOCX source files
│   ├── framework/{subject}/{stage}/curricular_goals.pdf
│   ├── framework/{subject}/{stage}/pedagogy.pdf
│   ├── evaluation_mappings/chapter_mappings_{subject}_{grade}.json
│   ├── evaluation_mappings/token_log.csv
│   └── textbooks/{subject}/{grade}/Chapter NN - Title.pdf
└── mirror/
    ├── constitutions/competency_mapping/{subject}/   ← ACTIVE: .txt constitutions
    │   └── mapping_constitution_{subject}.txt
    └── framework/{subject}/{stage}/                  ← extracted CG text
```

## How to Run in Cowork

The entry point is `run_mapping.sh` at the project root (mounted as `mnt/data/`).
The script self-locates using `$(dirname "$(realpath "$0")")` — no hardcoded paths.

```bash
# Pilot: one chapter at a time (always start here)
bash run_mapping.sh --subject social_sciences --grade vii --chapters 1

# Multiple specific chapters
bash run_mapping.sh --subject social_sciences --grade vii --chapters 1 4 8

# Bulk: all chapters
bash run_mapping.sh --subject social_sciences --grade vii --all

# Any other subject/grade — same command, just change subject and grade:
bash run_mapping.sh --subject mathematics --grade ix --chapters 1
bash run_mapping.sh --subject science --grade viii --all

# Dry run (no API call — verify paths before spending tokens)
bash run_mapping.sh --subject social_sciences --grade vii --dry-run
```

The script sources `.env` automatically, unsets the socks proxy, and delegates
to `aruvi-scripts/run_mapping.py`. Constitution files are read from `mirror/`
at runtime — no skill dir or references/ folder is involved.

## Cowork Session Setup

On every new Cowork session, `mnt/data/` maps to the Mac project folder.
All scripts in `aruvi-scripts/` and `run_mapping.sh` persist there permanently.
The `.env` file with the API key also lives there and persists.

No setup is needed at the start of a new session — just run the command above.

The `--skill-dir` flag is deprecated and no longer needed. Constitutions are
read from `mirror/constitutions/competency_mapping/` via config — no skill dir required.

## What the Skill Produces

One JSON record per chapter appended to
`knowledge_commons/evaluation_mappings/chapter_mappings_{subject}_{grade}.json`:

```json
{
  "stage": "middle",
  "subject": "social_sciences",
  "grade": "vii",
  "chapter_number": 1,
  "chapter_title": "Geographical Diversity of India",
  "chapter_summary": "600-900 word structured summary mirroring every textbook heading...",
  "primary": [
    { "cg": "CG-3", "c_code": "C-4.1", "weight": 3,
      "justification": "The chapter's core structural activity requires..." }
  ],
  "incidental": [ { "cg": "CG-6", "c_code": "C-6.2" } ],
  "chapter_weight": 9
}
```

One token log row per call appended to `knowledge_commons/evaluation_mappings/token_log.csv`.

## How Path Resolution Works

`config_resolver.py` reads `aruvi_config.json` and derives all paths automatically.
When `project_root` is `"DYNAMIC"`, it derives root from the config file's location.

| What | Resolved to |
|------|-------------|
| Stage | Looked up from grade (e.g. vii → middle) |
| CG PDF | `knowledge_commons/framework/{subject}/{stage}/curricular_goals.pdf` |
| Chapter dir | `knowledge_commons/textbooks/{subject}/{grade}/` |
| Output JSON | `knowledge_commons/evaluation_mappings/chapter_mappings_{subject}_{grade}.json` |
| Token log | `knowledge_commons/evaluation_mappings/token_log.csv` |
| Constitution | `mirror/constitutions/competency_mapping/{subject}/mapping_constitution_{subject}.txt` |

## First-Time Setup for a New Subject/Grade

1. Extract the competency mapping constitution DOCX with pandoc and save to:
   `mirror/constitutions/competency_mapping/{subject_group}/mapping_constitution_{subject_group}.txt`
2. Place the Curricular Goals PDF (correct stage only — no mixed stages):
   `knowledge_commons/framework/{subject_group}/{stage}/curricular_goals.pdf`
3. Place chapter PDFs:
   `knowledge_commons/textbooks/{subject_group}/{grade}/Chapter 01 - Title.pdf`
4. Run `--dry-run` to confirm all paths resolve before spending tokens.
5. Run pilot chapters 1, 4, 8 — review each against review_checklist.md before proceeding.
6. Run `--all` only after pilot review passes.

## IMPORTANT: CG PDF Must Contain Only the Correct Stage

The Curricular Goals PDF must contain ONLY the stage matching the grade being mapped.
If the source PDF contains both Middle Stage and Secondary Stage CGs, delete the
irrelevant stage's pages before placing the file. Mixing stages produces incorrect
competency assignments.

## Phase B Pilot Workflow

Run one at a time for the first 3 chapters. Review output before proceeding.

```
Chapter 1 → review_checklist.md → Chapter 4 → review → Chapter 8 → expert review → --all
```

See `references/review_checklist.md` for the go/no-go criteria after each pilot run.

## Token Cost Reference

| Operation | Per chapter | Notes |
|-----------|-------------|-------|
| Build mapping (one-time) | ~Rs.4-8 | Actual: Rs.7.78 for Ch1 (16K tokens — full chapter text) |
| Runtime lesson plan | ~Rs.1.25-1.55 | Per teacher request |

Note: chapter mapping tokens are higher than lesson plan tokens because the full
chapter text is passed to the mapping prompt. This is correct and expected.

## Constitution Source Policy

Constitutions are read at runtime from the mirror layer — never bundled inside
this skill. `config_resolver.py` resolves the path automatically from config as:

```
mirror/constitutions/competency_mapping/{subject_group}/
    mapping_constitution_{subject_group}.txt
```

The source of truth is the DOCX file in:
```
knowledge_commons/constitutions/competency_mapping/{subject_group}/
    Aruvi_Competency_Mapping_Constitutions_{subject_group}_V*.docx
```

To update a constitution: edit the DOCX source, then re-extract with:
```bash
pandoc "knowledge_commons/constitutions/competency_mapping/{subject}/..." \
  --to plain --wrap=none \
  -o "mirror/constitutions/competency_mapping/{subject}/mapping_constitution_{subject}.txt"
```
The updated .txt will be picked up automatically on the next pipeline run.
No script changes, no repackaging required.

Active mirror constitution paths:
- `mirror/constitutions/competency_mapping/social_sciences/mapping_constitution_social_sciences.txt`
- `mirror/constitutions/competency_mapping/languages/mapping_constitution_languages.txt`
- `mirror/constitutions/competency_mapping/mathematics/mapping_constitution_mathematics.txt`
- `mirror/constitutions/competency_mapping/science/mapping_constitution_science.txt`

## Hard Constraints (Constitutional)

- Only chapter text + Curricular Goals are passed to the mapping prompt.
  All other documents (pedagogy, LOs, syllabus) are excluded — constitutional requirement.
- Constitution is passed as the system prompt, not user-turn context.
- Runs are additive — re-running a chapter overwrites its record by chapter_number.
- The `--dry-run` flag ALWAYS works without an API key — use it to verify setup.
- CG PDF must contain only the stage being mapped — never mix stages in one file.
