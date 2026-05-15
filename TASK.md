**Tasks**

This document tracks two kinds of tasks under Project Aruvi: long term tasks towards completion and launch of the project and short term tasks that arise from time to time.  The purpose of the document is for Cowork to be able to track progress, remind outstanding tasks and correct any deviation from optimized paths. 

**Long term tasks**

Aruvi aims to deliver AI powered lesson plans and assessments for NCERT curriculum driven textbooks for English, Science, maths and social sciences for class III to X.  The planned approach to completion is as under:

1. For class VII, execute for Social sciences, science, maths and English in that order.  
2. Once it is done, extend for each subject in the above order to other classes within the middle stage i.e class VI and VIII   
3. Once step 2 is completed, move to the preparatory stage (III to V) beginning with class IV and repeating steps 1 & 2\.  
4. After step 3 is completed, finally move to the secondary stage (IX,X) and repeat the above steps.

Each subject for a grade involves the following steps:

1. Read the textbook chapters (a representative sample if not all of them) to understand the cognitive transformation pathway and potential.  
     
2. To develop an approach to a subject means the following: (1) a logic to allocate an annual calendar among various chapters of the textbook (example: competency weights for social science versus effort index for science) (2) an approach to deliver lesson plan that covers the main sections/sub sections of the textbook: an organizing principle here is necessary (transformation inventory aligned with NCF competency for social science versus progression stage based approach) (3) An approach to organize assessment (Implied learning outcome for both social science and science arising from the lesson plan). Here, a new subject attempt shall be made to apply one of already developed approaches to reduce system level complexity.  
     
3. Write a constitution (mapping, lesson plan & assessment) for the subject that will implement the logic developed in step 2, if different from the existing approach.  
     
4. Write a prompt (subject.md file) to write underlying chapter wise JSONs for the subject that incorporates the constitution and invokes the pre-written chapter summary.  
     
5. Run relevant prompts (example: chapter\_summary.md) to generate chapter summary in the right folder.  
     
6. Run one chapter summary prompt for one chapter, run the underlying subject md prompt to generate mapping JSON or equivalent and then (a) test the output on the allocate tab, (b) check the lesson plan  (‘c) check assessment . In checking them, ensure that allocate proportions are in line with the plan, the lesson plan organizing logic reflects the plan and so is the case with assessment. In the case of assessment, ensure that the different question types align with organizing principles (example: the types of permitted questions based on competency weights) and also carry its necessary within question elements like guide, inclusivity etc. as per the assessment constitution.  
     
7. Inspect the PDF output for lesson plan and assessment. Ensure that organizing elements (example: learning outcomes, progression stage etc.) that needs explicit mention in the pdf are indeed done so.  
     
8. Once step 7 is through, expand the chapter basket to cover all chapters for that subject under the grade in question to complete the task. Note that in step 6, point (a) will require all chapters to be processed as chapter summary and mapping JSON.

---

## Cowork Prompts Required — by Subject Group

The table below maps each subject to the cowork prompts that must be run (in order) to produce the artifacts needed for the **Allocate tab** and **LP + Assessment generation**.

| Subject | Step | Cowork Prompt | Output Artifact | Purpose |
|---|---|---|---|---|
| **Social Sciences** | 1 | `chapter_summary.md` | `mirror/chapters/social_sciences/{grade}/summaries/ch_XX_summary.txt` | Chapter summary — feeds LP + Assessment generation |
| **Social Sciences** | 2 | `competency_mapping_social_science.md` | `mirror/chapters/social_sciences/{grade}/mappings/ch_XX_mapping.json` | Competency weights — feeds Allocate tab |
| **Science** | 1 | `chapter_summary.md` | `mirror/chapters/science/{grade}/summaries/ch_XX_summary.txt` | Chapter summary — feeds LP + Assessment generation |
| **Science** | 2 | `effort_index_science.md` | `mirror/chapters/science/{grade}/mappings/ch_XX_mapping.json` | Effort index (central/co-central competency) — feeds Allocate tab |
| **Mathematics** | 1 | `chapter_summary_mathematics.md` | `mirror/chapters/mathematics/{grade}/summaries/ch_XX_summary.json` | Chapter summary in JSON format — feeds LP + Assessment generation |
| **Mathematics** | 2 | `competency_mapping_mathematics.md` | `mirror/chapters/mathematics/{grade}/mappings/ch_XX_mapping.json` | Competency weights — feeds Allocate tab |
| **English** | Static (one-time) | *(manual / pre-built)* | `mirror/framework/english/{stage}/spine_to_cg.json` | Spine-to-CG mapping — static JSON; must exist before any English LP or Assessment can be generated. One file per stage (middle / preparatory / secondary). |
| **English** | 1+2 (combined) | `chapter_summary_competency_mapping_english.md` | `mirror/chapters/english/{grade}/summaries/ch_XX_summary.json` + `mirror/chapters/english/{grade}/mappings/ch_XX_mapping.json` | Summary + effort index in a single pass — feeds LP, Assessment, and Allocate tab |


**Notes:**
- Social Sciences and Science summaries are `.txt`; Mathematics and English summaries are `.json`.
- The `spine_to_cg.json` files for English are static — they do not need to be regenerated per chapter or per grade; they are stage-level constants (middle, preparatory, secondary). Verify they are present in `mirror/framework/english/` before starting any new English grade.
- All mapping JSONs feed the Allocate tab's chapter-weight / effort-index display. The Allocate tab will be blank or incorrect for any chapter whose mapping JSON is missing.
- LP and Assessment generation requires both the summary file AND the mapping JSON to be present for the target chapter.

---

**Short term tasks**

1\. [PARTIALLY DONE] Managed Agent integration for Ask Aruvi: `ask_aruvi_agent.py` is written and wired into `app.py` behind a `USE_MANAGED_AGENT` flag (currently `False`). Credentials used: `AGENT_ID = "agent_011Ca6z4gAUB897Nr3xfHNiT"`, `ENVIRONMENT_ID = "env_01L8dPr1NDwDzkiDXWPpn8YE"`. Outstanding: test the managed agent path end-to-end, then flip `USE_MANAGED_AGENT = True` in `app.py` to activate.

2\. [DONE — May 2026] LP PDF v3 (`aruvi_streamlit/lp_pdf_generator.py`) wired into app.py for English and Mathematics. Science/SS LP PDF migration to v3 still pending.

3\. [DONE — May 2026] Fix hardcoded `PROJECT_ROOT` in `app.py` and `ask_aruvi_agent.py`. Both now use `Path(__file__).parent.parent` for dynamic resolution. The `load_dotenv` call in `app.py` was also fixed and `Path` import moved to the top of the file.

4\. [DONE — May 2026] Scratch test HTML files (test_debug.html, test_fixed.html, test_minimal.html, test_trycatch.html, test_assess_only.html, test_assessment.html, test_assessment_full.html, test_debug2.html) confirmed deleted — no longer present in the project.

5\. [IN PROGRESS] Complete English VII: Ch 02–05 done (summary + mapping). Ch 06–N — run combined summary+mapping prompt for remaining chapters, then full generate+test cycle. Note: English VI and English VIII each have only 5 chapters — both grades are now COMPLETE for summaries + mappings.

**Progress snapshot — as of 2026-05-15**

- Mathematics VII: COMPLETE (all 8 chapters — summaries, mappings, LP + assessment tested)
- English VII: Ch 01 complete (summary, mapping, LP, assessment tested). Ch 02–05 complete (summary + mapping, 2026-05-12). Ch 06–N pending. Assessment PDF/HTML layout fixes applied (2026-05-11): section name per-question, Notes to last page, LO below guide, word box pills, FILL_IN markdown tables, Part A/B guide splitting.
- English VIII: Ch 01 complete (summary + mapping, 2026-05-15) — 3 sections (1 prose + 1 poem + 1 dialogue); effort_index 14.5. LP + assessment testing pending. Ch 02 complete (summary + mapping, 2026-05-15) — 3 sections (1 prose + 1 poem + 1 informational: A Tale of Valour, Somebody's Mother, Verghese Kurien); effort_index 15.0. Ch 03 complete (summary + mapping, 2026-05-15) — 3 sections; effort_index pending. Ch 04 complete (summary + mapping, 2026-05-15) — 3 sections (1 prose: The Cherry Tree + 1 poem: Harvest Hymn + 1 narrative: Waiting for the Rain); effort_index 16.0. Ch 05 complete (summary + mapping, 2026-05-15) — 3 sections (1 narrative: Feathered Friend by Arthur C. Clarke + 1 poem: Magnifying Glass by Walter de la Mare + 1 informational: Bibha Chowdhuri); effort_index 12.0. Ch 06–N pending.
- English VI: Ch 01–05 complete (summary + mapping). Ch 05 done 2026-05-15 — 4 sections (Kalakritiyon ka Bharat, The Kites, Ila Sachani, National War Memorial); effort_index 11.0. Ch 06 pending.
- Science VII: Complete (all 12 chapters)
- Social Sciences VII: Complete (all 12 chapters)
- Science VI / Social Sciences VI: ch_02 only — paused

