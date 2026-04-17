# Aruvi — Project Context for Cowork Sessions

This file is the standing briefing for every Cowork session on this project. It is updated automatically whenever meaningful progress is made. Last updated: 2026-04-15

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

- **Competency mapping pipeline**: Fully working for Science VII and Social Sciences VII. Scripts extract chapter content from PDFs, call Claude to map each chapter against curricular goals and competency frameworks, and store results in structured JSON (`mirror/chapters/{subject}/{grade}/mappings/`).  
- **Chapter summaries**: Generated and cached for Science VII and Social Sciences VII (`mirror/chapters/{subject}/{grade}/summaries/`).  
- **Lesson plan generation**: Working via the Streamlit app (`aruvi_streamlit/app.py`) for Science and Social Sciences, middle stage. Generates NCF-aligned lesson plans per chapter with period-level detail.  
- **Assessment generation**: Working alongside lesson plans — generates assessments aligned to the same competency mappings.  
- **Ask Aruvi helpline**: A Q\&A assistant within the app backed by a curated knowledge base (`mirror/ask_aruvi/qa_knowledge_base.json`). Feedback logged per interaction.  
- **Feedback system**: Thumbs up/down and free-text feedback captured and stored in `mirror/feedback/` (monthly subfolders, per-interaction JSON files).  
- **Token/cost logging**: Every API call logged to `knowledge_commons/evaluation_mappings/token_log.csv` with cost in INR.  
- **Dynamic config**: `config_resolver.py` resolves all paths from `aruvi_config.json` dynamically — no hardcoded paths in the scripts.

### Constitutions in place

- Competency mapping: Social Sciences, Science, Mathematics, Languages  
- Lesson plan: Social Sciences, Science  
- Assessment: Social Sciences, Science

### Mirror coverage (pre-computed data)

- Science VII: summaries \+ mappings (all 12 chapters)  
- Social Sciences VII: summaries \+ mappings (all 12 chapters)  
- Framework text (CG \+ pedagogy): Science middle, Social Sciences middle

---
## 5\. Steps involved

For subjects: Social sciences

Step 1 -  generate Chapter summary by running the chapter_summary.md cowork prompt

Step 2 - map competencies by running the competency_mapping.md cowork prompt which populates the chapter mapping JSON with competencies and their weights. The allocate tab uses the weights to allocate time across the various chapters. 


For subjects: science

Step 1 - generate Chapter summary by running the chapter_summary.md cowork prompt

Step 2 - Map central & co-central competency and efforts index by running the effort_index_science.md. The allocate tab uses the efforts index to allocate time across various chapters. 

For Subjects: All

Step 3 (run)
3.1 Allocate tab - static data
3.1 Generate tab - run specific chapters based on custom time period- output lesson plan, assessment both in html and pdf format
3.2- My plans tab- static data that reproduces generate tab's lesson plan on saved basis.


## 6\. Main challenges

### Token cost and economics, time taken

API costs are non-trivial at scale. Run costs per chapter is as high as Rs. 23 against original expectation of Rs. 8\.  The mitigation strategy is aggressive caching (map once, reuse forever) — the mirror architecture exists for this reason. At SaaS scale, the vector store \+ centralised cache is the path to acceptable unit economics.

The lesson plan and assessment generation is taking about 5 minutes. We need to continously explore ways to reduce the time.

---

## 7\. Key architectural decisions (carry forward to every session)

- **DYNAMIC project root**: `aruvi_config.json` uses `"project_root": "DYNAMIC"` — `config_resolver.py` derives the root from the config file's own location. Never hardcode paths in scripts.  
- **Known issue**: `aruvi_streamlit/app.py` still has hardcoded `PROJECT_ROOT = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")`. This must be fixed before any cloud deployment or multi-machine use.  
- **Mirror-first reads**: At runtime, scripts read pre-extracted `.txt` files from `mirror/framework/` — never the source PDFs. PDFs are source-of-truth for humans, mirror is source-of-truth for the app.  
- **Constitution location**: `mirror/constitutions/{type}/{subject}/` — not inside skill folders. Constitution files are plain `.txt` extracted from DOCX sources.  
- **Saved plans**: Written to `mirror/saved_plans/{subject}/{grade}/` as timestamped JSON on explicit user save action.

---

## 8\. Folder map (quick reference)

Project Aruvi/

├── CLAUDE.md                          ← this file

├── aruvi\_config.json                  ← central config, DYNAMIC root

├── aruvi-scripts/                     ← mapping \+ extraction scripts

├── aruvi\_streamlit/                   ← Streamlit web app

│   └── app.py                         ← ⚠️ hardcoded path, needs fixing

├── knowledge\_commons/

│   ├── constitutions/                 ← source DOCX constitutions

│   ├── framework/                     ← source PDFs (CG, pedagogy)

│   ├── textbooks/                     ← source chapter PDFs

│   └── evaluation\_mappings/           ← token\_log.csv, ask\_aruvi.csv

├── mirror/                            ← all pre-computed / cached data

│   ├── chapters/{subject}/{grade}/

│   │   ├── summaries/                 ← ch\_XX\_summary.txt

│   │   └── mappings/                  ← ch\_XX\_mapping.json

│   ├── constitutions/                 ← runtime .txt constitutions

│   ├── framework/                     ← runtime CG \+ pedagogy .txt

│   ├── saved\_plans/                   ← user-saved lesson plans

│   ├── feedback/                      ← ask\_aruvi, general, forwarded

│   └── ask\_aruvi/                     ← qa\_knowledge\_base.json

├── Aruvi skills/                      ← Cowork skills for this project

└── cowork prompts/                    ← standing prompts for common tasks  

## 9\. Must read files
Once you finish reading Claude.MD, also read MEMORY.md and TASK.md to update status, track progress, check deviations from the path and update learnings.