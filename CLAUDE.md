# Aruvi — Project Context for Cowork Sessions

This file is the standing briefing for every Cowork session on this project. It is updated automatically whenever meaningful progress is made. Last updated: 2026-05-10

---

## 1\. What is Aruvi and the market gap it fills

Aruvi is an AI-powered lesson planning and assessment tool designed for Indian K–12 teachers, built on Anthropic’s Claude API. It addresses two major gaps in the EdTech ecosystem: excessive teacher workload and weak curriculum alignment. Teachers often spend substantial time manually creating lesson plans and assessments with minimal support, leading to inefficiency. At the same time, most EdTech platforms either overlook or superficially align with the National Curriculum Framework (NCF). Aruvi tackles both issues by automating content creation while ensuring strict adherence to NCF/NCERT standards through structured, subject-specific “constitutions” that encode pedagogy and competencies. This enables teachers to save time while producing high-quality, curriculum-aligned educational materials.

The online tool is expected to provide an AI powered lesson plan and assessment along with allocation tool for entire subject across chapters for classes 3 to 8 for English, Science, Social Science and Mathematics. The [claude.md](http://claude.md) file is additionally expected to track progress along this vector keeping in mind that each subject will have to bed down its organizing logic followed by developing its Lesson plan and assessment. 

---

## 2\. Ideal Customer Profile (ICP)

**Primary: Individual teachers** Self-motivated teachers (CBSE, grades III–X) who want AI-assisted planning without needing school-level buy-in. They are the early adopters and the feedback loop.

**Secondary: CBSE private schools** Mid-to-large CBSE schools looking to reduce teacher prep time, improve lesson quality, and demonstrate curriculum compliance. School-level adoption drives volume and recurring revenue.

Both segments share the same core need: high-quality, NCF-aligned lesson plans and assessments generated in minutes, not hours.

---

## 3\. What final delivery looks like

### Near-term: hosted SaaS web app

The Streamlit app evolves into a production-grade, cloud-hosted multi-tenant SaaS. Each school or teacher gets their own account with saved plans, history, and profile. The local file system is replaced by a shared cloud backend.

### Scale architecture (target state)

- **Vector store for retrieval**: Chapter summaries, curricular goals, and pedagogy content move from flat `.txt` files into a vector store (e.g. Pinecone, Chroma, or pgvector). This enables semantic retrieval at scale across all subjects and grades without loading entire files into context.  
- **Centralised caching to cut API costs**: Competency mappings and chapter summaries are pre-computed once and cached centrally. Repeated requests for the same chapter never hit the Anthropic API again. This is critical for unit economics at scale.  
- **Cloud storage**: Mirror data (summaries, mappings, saved plans, feedback) moves from local folders to a cloud object store or database, enabling multi-user concurrent access.

### What does NOT change at scale

The constitution-based generation approach is the IP — the subject constitutions, the competency mapping framework, and the pedagogical rules stay as the core engine regardless of infrastructure.

---

## 4\. Progress so far

### What's built and working

- **Competency mapping pipeline**: Fully working for Science VII, Social Sciences VII, and Mathematics VII. Science VI and Social Sciences VI partially underway (ch\_02 done). English uses a combined chapter\_summary + competency mapping prompt (`chapter_summary_competency_mapping_english.md`).
- **Chapter summaries**: Generated and cached for Science VII, Social Sciences VII, Mathematics VII (all chapters), and English VII (ch\_01). Science VI and Social Sciences VI partially done (ch\_02).
- **Summary format**: Science and Social Sciences use `.txt` format; Mathematics and English use `.json` format. `app.py` resolves this via `_JSON_SUMMARY_SUBJECTS = {"mathematics", "english"}`.
- **Lesson plan generation**: Working via the Streamlit app (`aruvi_streamlit/app.py`) for Science, Social Sciences, Mathematics, and English (middle stage). Each subject has its own lesson plan constitution.
- **Assessment generation**: Working alongside lesson plans for Science, Social Sciences, Mathematics, and English. Each subject has its own assessment constitution.
- **Ask Aruvi helpline**: A Q\&A assistant within the app. The managed-agent path (`ask_aruvi_agent.py`) is fully built and wired with `USE_MANAGED_AGENT` flag in `app.py`, but currently set to `False` (original Haiku path still active). Switch to `True` to activate managed agent.
- **Feedback system**: Thumbs up/down and free-text feedback captured and stored in `mirror/feedback/` (monthly subfolders, per-interaction JSON files).
- **Token/cost logging**: Every API call logged to `knowledge_commons/evaluation_mappings/token_log.csv` with cost in INR.
- **Dynamic config**: `config_resolver.py` resolves all paths from `aruvi_config.json` dynamically — no hardcoded paths in the scripts.
- **LP PDF v2**: `aruvi_lp_v2.py` is a redesigned lesson plan PDF generator (improved period pills, competency table, learning outcome styling). Lives in `aruvi-scripts/` — not yet wired into `app.py` as the default.
- **SVG visual stimulus**: Both HTML and PDF assessment renderers support SVG figures (for Mathematics geometry questions), pipe-delimited tables (Science/SS), and prose fallback. svglib is a runtime dependency.

### Constitutions in place

- Competency mapping: Social Sciences, Science, Mathematics, Languages (English uses combined chapter_summary + competency_mapping prompt)
- Lesson plan: Social Sciences, Science, Mathematics, English  
- Assessment: Social Sciences, Science, Mathematics, English

### Mirror coverage (pre-computed data)

- Science VII: summaries \+ mappings (all 12 chapters)  
- Social Sciences VII: summaries \+ mappings (all 12 chapters)  
- Mathematics VII: summaries \+ mappings (all 8 chapters — `.json` format)  
- English VII: summaries \+ mappings (ch\_01 only — in progress; uses `.json` format)  
- Science VI: summaries \+ mappings (ch\_02 only — in progress)  
- Social Sciences VI: summaries \+ mappings (ch\_02 only — in progress)  
- Framework text (CG \+ pedagogy): Science middle, Social Sciences middle, Mathematics middle/preparatory/secondary, English middle/preparatory/secondary

---
## 5\. Steps involved

For subjects: Social sciences

Step 1 - Generate chapter summary by running the `chapter_summary.md` cowork prompt

Step 2 - Map competencies by running `competency_mapping_social_science.md` cowork prompt, which populates the chapter mapping JSON with competencies and their weights. The allocate tab uses the weights to allocate time across chapters.

For subjects: Science

Step 1 - Generate chapter summary by running the `chapter_summary.md` cowork prompt

Step 2 - Map central & co-central competency and effort index by running `effort_index_science.md`. The allocate tab uses the effort index to allocate time across chapters.

For subjects: Mathematics

Step 1 - Generate chapter summary by running `chapter_summary_mathematics.md` cowork prompt (produces `.json` format, not `.txt`)

Step 2 - Map competencies by running `competency_mapping_mathematics.md` cowork prompt

For subjects: English

Step 1 & 2 combined - Run `chapter_summary_competency_mapping_english.md` which generates both the summary JSON and mapping JSON in a single pass.

For Subjects: All

Step 3 (run)
3.1 Allocate tab - static data
3.2 Generate tab - run specific chapters based on custom time period - output lesson plan + assessment in HTML and PDF format
3.3 My plans tab - static data that reproduces generate tab's lesson plan on saved basis.


## 6\. Main challenges

### Token cost and economics, time taken

API costs are non-trivial at scale. Run costs per chapter is as high as Rs. 23 against original expectation of Rs. 8\.  The mitigation strategy is aggressive caching (map once, reuse forever) — the mirror architecture exists for this reason. At SaaS scale, the vector store \+ centralised cache is the path to acceptable unit economics.

The lesson plan and assessment generation is taking about 5 minutes. We need to continously explore ways to reduce the time.

---

## 7\. Key architectural decisions (carry forward to every session)

- **DYNAMIC project root**: `aruvi_config.json` uses `"project_root": "DYNAMIC"` — `config_resolver.py` derives the root from the config file's own location. Never hardcode paths in scripts.  
- **Known issue**: `aruvi_streamlit/app.py` still has hardcoded `PROJECT_ROOT = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")`. This must be fixed before any cloud deployment or multi-machine use. Also `ask_aruvi_agent.py` line `_PROJECT_ROOT` has the same hardcoded path.
- **Managed agent toggle**: `app.py` has `USE_MANAGED_AGENT = False` flag at the top. Set to `True` to switch Ask Aruvi from direct Haiku calls to the managed agent (credentials in `ask_aruvi_agent.py`). Old `ask_aruvi_qa.py` is immobilised but intact on disk.
- **Summary format split**: Mathematics and English chapter summaries are `.json` (not `.txt`). The `_JSON_SUMMARY_SUBJECTS` set in `app.py` controls which subjects use JSON loading. Any new subject using JSON format must be added to this set.
- **LP PDF v2 pending wiring**: `aruvi-scripts/aruvi_lp_v2.py` is a redesigned PDF generator ready for integration but not yet the default in `app.py`. When wiring in, replace the `generate_pdf_bytes_lp()` call.
- **visual\_stimulus rendering branches**: Renderers (`assessment_pdf_generator.py` + `lpa_page.html`) must handle three content types — SVG (Mathematics), pipe-table (Science/SS tabular data), prose (fallback). Any new format permitted in a constitution needs a matching detection branch in both renderers before shipping.  
- **Mirror-first reads**: At runtime, scripts read pre-extracted `.txt` files from `mirror/framework/` — never the source PDFs. PDFs are source-of-truth for humans, mirror is source-of-truth for the app.  
- **Constitution location**: `mirror/constitutions/{type}/{subject}/` — not inside skill folders. Constitution files are plain `.txt` extracted from DOCX sources.  
- **Saved plans**: Written to `mirror/saved_plans/{subject}/{grade}/` as timestamped JSON on explicit user save action.

---

## 8\. Folder map (quick reference)

Project Aruvi/

├── CLAUDE.md                          ← this file

├── MEMORY.md                          ← accumulated learnings across sessions

├── TASK.md                            ← long-term and short-term task tracker

├── aruvi\_config.json                  ← central config, DYNAMIC root

├── aruvi-scripts/                     ← mapping \+ extraction scripts

│   └── aruvi\_lp\_v2.py                ← ⚠️ redesigned LP PDF (not yet wired in)

├── aruvi\_streamlit/                   ← Streamlit web app

│   ├── app.py                         ← ⚠️ hardcoded path; USE\_MANAGED\_AGENT flag

│   ├── ask\_aruvi\_agent.py             ← managed-agent Ask Aruvi (inactive, flag=False)

│   ├── assessment\_pdf\_generator.py   ← handles SVG / pipe-table / prose stimuli

│   └── lp\_pdf\_generator.py

├── knowledge\_commons/

│   ├── constitutions/                 ← source DOCX constitutions (all subjects)

│   ├── framework/                     ← source PDFs (CG, pedagogy) incl. english, maths

│   ├── textbooks/                     ← source chapter PDFs incl. english, maths

│   └── evaluation\_mappings/           ← token\_log.csv, ask\_aruvi.csv

├── mirror/                            ← all pre-computed / cached data

│   ├── chapters/{subject}/{grade}/

│   │   ├── summaries/                 ← ch\_XX\_summary.txt (sci/ss) or .json (maths/english)

│   │   └── mappings/                  ← ch\_XX\_mapping.json

│   ├── constitutions/                 ← runtime .txt constitutions (all 4 subjects × LP/assess/mapping)

│   ├── framework/                     ← runtime CG \+ pedagogy .txt (english, maths added)

│   ├── saved\_plans/                   ← user-saved lesson plans (english, maths folders added)

│   ├── feedback/                      ← ask\_aruvi, general, forwarded

│   ├── debug/                         ← raw LLM output dumps for debugging

│   └── ask\_aruvi/                     ← qa\_knowledge\_base.json

├── Aruvi skills/                      ← Cowork skills for this project

└── cowork prompts/                    ← standing prompts for common tasks

    ├── chapter\_summary.md             ← Science / Social Sciences

    ├── chapter\_summary\_mathematics.md ← Mathematics (JSON output)

    ├── chapter\_summary\_competency\_mapping\_english.md ← English (combined, JSON)

    ├── competency\_mapping\_social\_science.md

    ├── competency\_mapping\_mathematics.md

    └── effort\_index\_science.md

## 9\. Must read files
Once you finish reading Claude.MD, also read MEMORY.md and TASK.md to update status, track progress, check deviations from the path and update learnings.