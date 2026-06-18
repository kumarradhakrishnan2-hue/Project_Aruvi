Aruvi Project \- Memory

Aruvi is an AI-powered lesson planning and assessment tool designed for Indian K–12 teachers, built on Anthropic’s Claude API. It addresses two major gaps in the EdTech ecosystem: excessive teacher workload and weak curriculum alignment. Teachers often spend substantial time manually creating lesson plans and assessments with minimal support, leading to inefficiency. At the same time, most EdTech platforms either overlook or superficially align with the National Curriculum Framework (NCF). Aruvi tackles both issues by automating content creation while ensuring strict adherence to NCF/NCERT standards through structured, subject-specific “constitutions” that encode pedagogy and competencies. This enables teachers to save time while producing high-quality, curriculum-aligned educational materials.

The [memory.md](http://memory.md) file purpose is to document overtime significant learnings in order to render the project production and eventually the run operations efficient and time/cost effective.The learnings so far are documented below. Subsequent learnings shall be documented regularly.

1. Design process: 

The overall design process involved the Aruvi team (to be called “Team”) and AI engaging in interactive, sequential and iterative conversations. One observation was the inclination for AI to produce verbose and detailed document where simpler versions would do. Prohibitions were considerable even when not relevant. If the team pointed out any issue, it resulted in detailed incorporation in the document rather than subtle changes. The team also did not fully read these productions leading to exalted assumptions. So the learnings are (1) Advise AI to keep docs simple and small as much as needed but no more (2) The team must read every single word and see its relevance apart from correctness. 

2. Hallucination: The team’s general observation is the potential for AI to hallucinate if not firmly grounded in constitutional docs and source files.  Another source of hallucination was verbose and sometimes conflicting demands leading to self discovery by AI. It was also found that in generating summary of textbook chapters pdf to txt, unless firmly anchored in sections and sub sections, AI was hallucinating portions from its own training data. The need to keep the ask of AI simple, grounded and non-contradictory was an important learning.

3. Constitutions development-Competency mapping: The whole project arose from a promise to align the lesson plan and assessment in line with NCF competencies as expected by NCF. Since the textbook was the only resource being used for this purpose, there was an implicit assumption about holistic coverage of NCF competencies by the textbook.  This worked quite well for social sciences wherein each chapter offered rich texture to develop multiple competencies. But when the team tried to apply the same competency\_mapping.md logic to another subject i.e. science it failed as in science each chapter was aligned to develop a single core competency. The allocation logic to distribute time based on weighted competencies of each chapter failed as in science all chapters had equal core weight\! The issue of what should drive the Aruvi approach for science as opposed to competency based approach for social science led to an innovative approach: progression stages in science.  The mistake made was to assume subject potential of similar nature at inception rather than keeping the original object \- providing a useful tool to teachers who are hard pressed for time- in mind.    
     
4. Changes: Any changes we make in response to specific need, for example, a layout need for science alone, may end up negatively impacting the other parts of the project. At all stages, it is necessary for the team and AI to keep in mind that changes must be evaluated for its total impact.

5. Cost and time : Token cost per chapter has ballooned from AI's projection of Rs. 8 per run to Rs. 23 now! The time taken to complete a plan now is 5 minutes against original time of less than 2 minutes due largely to significant number of periods for each chapter being suggested by allocate tab. The learning is that one must keep in mind the cost and time implications as we develop the project further.

---

## Structured Learnings — Post April 2026 Run
*Format: Context → Observation → Root cause → Action taken → Carry-forward rule*

---

[Learning #6] — 2026-04-17 — Science PDF / Output Truncation

Context: Generating a lesson plan and assessment for Science Ch 02 (Acids, Bases & Neutralisation) with only 1 period scheduled.
Observation: The saved JSON had empty `lesson_plan: {}` and `assessment_items: []` despite the API call succeeding and charging ₹23.17.
Root cause: `max_tokens` was hardcoded at 16,000. The Science assessment constitution generates rich guide blocks (what_each_option_reveals, inclusivity, look_for per item) which can exceed 16,000 tokens even for a single-period chapter. The response was truncated mid-JSON, causing a JSONDecodeError that silently set the result to empty.
Action taken: Raised `max_tokens` from 16,000 → 32,000 in `app.py`. No beta header needed for claude-sonnet-4-6 as extended output is natively supported.
Carry-forward rule: If a Generate run returns empty lesson_plan or empty assessment_items, always check token_log.csv first — if output_tokens equals max_tokens, it is a truncation, not a generation failure. The fix is raising the ceiling, not re-running with different inputs.

---

[Learning #7] — 2026-04-17 — Directory Rename Cascade Risk

Context: The `mirror/chapters/science/` directory was renamed from `grade_vii` → `vii` to align with the Social Sciences convention.
Observation: The app.py `grade_to_folder()` function was updated correctly, but `config_resolver.py` line 114 still used `f"grade_{grade.lower()}"`. This means the mapping pipeline scripts (run_mapping.sh) pointed to a non-existent folder path.
Root cause: The rename was applied in one file but not propagated to all consumers of that path. config_resolver.py serves the mapping scripts; app.py serves the runtime app — they are separate consumers.
Action taken: Updated `config_resolver.py` to use `grade.lower()` (not `f"grade_{grade.lower()}"`).
Carry-forward rule: Any folder/path rename must be grepped across the entire codebase before declaring done. At minimum check: app.py, config_resolver.py, and any shell scripts. Use `grep -r "old_path_fragment"` before closing a rename task.

---

[Learning #8] — 2026-04-17 — SS Assessment Open Task Silently Dropped

Context: Social Sciences assessment PDF was missing the open task entirely. Science PDF showed it correctly.
Observation: The `TYPE_ORDER` list in the PDF generator used lowercase `"open_task"` but SS JSON items stored `question_type` as `"OPEN_TASK"` (uppercase). The grouping filter ran before any normalisation, so SS open tasks never matched and were silently skipped — no error, no warning.
Root cause: Case mismatch between the constant list and the data value. Science worked because its grouping function (`_group_science`) normalised case internally; SS grouping did not.
Action taken: Added `.lower()` normalisation in the SS grouping filter before comparing against TYPE_ORDER.
Carry-forward rule: When a question type or enum value is missing from PDF/HTML output with no error, always check for case mismatch first. Always normalise to lowercase before comparing against TYPE_ORDER or equivalent enum lists.

---

[Learning #9] — 2026-04-17 — SS Assessment LO Text Showing Wrong Field

Context: Social Sciences assessment HTML was displaying the competency description text (e.g. "Analyses the effect of various changes...") in the Learning Outcome row of each question, instead of the specific implied learning outcome for that question.
Observation: In `app.py`, `_normalise_assessment_sections` built the `implied_lo` field for SS question objects from `competency_text` (the canonical competency description), not from `item["implied_lo"]` (the per-question LO). Science correctly used `implied_lo_assessed` directly.
Root cause: When the SS path was originally written, `competency_text` was used as a proxy for LO. Once the assessment constitution began generating a distinct `implied_lo` per question, the proxy became wrong but was never updated.
Action taken: Changed the SS path in `_normalise_assessment_sections` to read `item.get("implied_lo", "")` directly, mirroring the Science approach.
Carry-forward rule: The `implied_lo` field on assessment items is the per-question learning outcome. The `competency_text` in the competency block is the NCF competency description — these are two different things. Never substitute one for the other in display code.

---

[Learning #10] — 2026-04-17 — Cowork Session Context Does Not Persist Automatically

Context: First session to set up CLAUDE.md, MEMORY.md, and TASK.md for the project.
Observation: A new Cowork session starts completely cold — no memory of prior sessions unless CLAUDE.md (and files it references) exists in the project folder and is read at session start. The `.claude/projects/.../memory/` folder existed but was empty.
Root cause: Cowork does not auto-populate memory. The CLAUDE.md instruction to also read MEMORY.md and TASK.md only works if those files exist in the project root.
Action taken: Created CLAUDE.md, MEMORY.md, and TASK.md in the project root. CLAUDE.md instructs the session to read all three at start.
Carry-forward rule: At the end of any session where significant work was done, update CLAUDE.md progress section and append new learnings to MEMORY.md. This is the only way context carries forward. Do not assume prior session knowledge.

---

[Learning #12] — 2026-05-30 — TWAU Lesson Plan Template: No Toggle Inheritance from Science

Context: TWAU (The World Around Us) chapters are heterogeneous — some lean science (How Things Work), some lean social/cultural (Family, Community), and many are blended within a single period.
Observation: Considered introducing the lesson view / time view toggle (used in Science) for TWAU. But the toggle assumes a chapter-level or strand-level uniformity that TWAU does not have — inquiry and cultural strands can coexist within the same period.
Root cause: TWAU's pedagogical nature is fundamentally different from Science. Strand classification cannot be done at chapter or period level cleanly.
Action taken: Decision to give TWAU its own lesson plan template with activity-type labels (e.g. Explore / Discuss / Create) rather than inheriting Science's view toggle. No toggle for TWAU. No strand-level routing.
Carry-forward rule: TWAU is a distinct subject with its own constitution and template. Do not map it onto Science or Social Sciences mental models. Any TWAU-specific UI or generation logic must be designed ground-up for its blended nature.

---

[Learning #11] — 2026-04-17 — Competency Mapping: Constitutions Must Be Read Before Coding

Context: Session running competency mapping for Social Sciences Class VII chapters 1–5.
Observation: The mapping was done correctly because the AI read the full constitution (competency_mapping constitution) before starting — applying Pass 1 (transformation inventory) and Pass 2 (architectural container matching) rigorously. The output was high quality with well-reasoned weight assignments and incidental vs. structural distinctions.
Root cause: N/A — this was a positive observation.
Action taken: N/A.
Carry-forward rule: For competency mapping, always run Pass 1 (C-code-blind transformation inventory) fully before attempting Pass 2 (matching to CG codes). Skipping Pass 1 leads to superficial pattern-matching against CG text rather than genuine architectural analysis of the chapter. The constitution's two-pass methodology is not optional.

---

[Learning #12] — 2026-04-17 — Science PDF: Generic Visual Stimulus Note Was Meaningless

Context: Science assessment PDF was showing the sentence "A visual stimulus is provided for this question." wherever `visual_stimulus != null`, instead of showing the actual stimulus content.
Observation: The sentence added no information to the teacher — the actual stimulus text was never rendered, just a placeholder note. Removing it was cleaner than trying to render the full stimulus inline.
Root cause: The PDF generator had a placeholder block that printed a generic note rather than rendering the `visual_stimulus` field content. This was likely an interim implementation that was never completed.
Action taken: Removed the entire visual stimulus note block from the Science assessment PDF generator. The field remains in the JSON for future use.
Carry-forward rule: If a PDF/HTML shows a generic meta-note about content ("A visual is provided") rather than the content itself, it is an incomplete implementation. Either render the actual content or remove the note entirely — a placeholder note in teacher output is worse than silence.

---

[Learning #13] — 2026-04-17 — Allocated but Unused Combined Mapping File Creates Confusion

Context: Task to "make Allocate tab use individual chapter files not the combined chapter_mappings_science_vii.json."
Observation: Investigation showed the combined file was never referenced anywhere in the codebase — the app already read individual ch_XX_mapping.json files. The task was a false alarm; no code change was needed.
Root cause: The combined file had been generated as a convenience artifact but was never wired into the app. Its presence in the mappings folder made it look like it might be in use.
Action taken: Verified via grep that no code references the combined file. Marked task as verified-closed in TASK.md.
Carry-forward rule: Before writing code to "switch" a data source, always grep for actual references to both the old and new source. The presence of a file in the right folder does not mean it is being used. Verify first, change only if needed.

---

[Learning #14] — 2026-04-17 — visual_stimulus: Prose Description vs Actual Table Data

Context: Science assessment Ch 02 open task had visual_stimulus populated, but the PDF rendered it as a block of italic text rather than a table.
Observation: The LLM had written a prose description of the table ("A data table is provided with columns: Scenario, Litmus result...") in visual_stimulus instead of the actual pipe-delimited table rows. The PDF renderer could not detect a table because there were no consistent pipe-separated rows.
Root cause: The original constitution rule said visual_stimulus "must describe any visual provided to the student" — the word "describe" invited prose. The rule did not distinguish between the actual data and a description of it.
Action taken: (1) Rewrote the constitution rule as four explicit sub-rules (VS-1 to VS-4) specifying that visual_stimulus must contain the actual pipe-delimited table data, not a description. Added correct and prohibited examples for both MCQ and OPEN_TASK. (2) Made the rule explicitly type-agnostic — applies to all question types. (3) Added _render_visual_stimulus() to assessment_pdf_generator.py: detects pipe-table vs plain text and renders accordingly. (4) Added renderVisualStimulus() to lpa_page.html with matching CSS; wired into both the OPEN_TASK branch and the standard question branch. (5) Added visual_stimulus passthrough in _normalise_assessment_sections() in app.py.
Carry-forward rule: visual_stimulus must always contain the actual table rows in pipe-delimited format (header row + data rows, one per line). A prose description of a table is not a visual stimulus — it is metadata. If a question says "the table below" or "use the table provided", the actual table must be in visual_stimulus. Constitution rules that say "describe" invite prose; rules that say "provide the actual data in pipe-delimited format" do not.

---

[Learning #15] — 2026-04-18 — Summary File Numbering Mismatch Causes Wrong Competency Mappings

Context: User reported that ch_05_mapping.json for Social Sciences VII ("New Beginnings: Cities and States") had different competencies than those found in a fresh re-run of the mapping task.
Observation: Full audit revealed ch_04_summary.txt contained "New Beginnings: Cities and States" content and ch_05_summary.txt contained "The Rise of Empires" content — but the previous mapping session had produced ch_04_mapping.json titled "The Age of Empires" (derived from ch_05_summary) and ch_05_mapping.json titled "New Beginnings: Cities and States" (derived from ch_04_summary). Competencies in both JSONs were derived from the wrong chapter's content. The other 10 chapters (ch01–03, ch06–12) were audited and found correct.
Root cause: The mapping cowork prompt had no instruction to verify that the chapter_title and chapter_number in the output JSON matched the actual content of the source summary file. The AI mapped content correctly from whichever summary it read — but there was no guard against processing the wrong summary for a given chapter number.
Action taken: (1) Re-mapped ch_04 correctly from ch_04_summary.txt: New Beginnings: Cities and States → C-2.1 W3, C-3.1 W2. (2) Re-mapped ch_05 correctly from ch_05_summary.txt: The Rise of Empires → C-2.1 W3, C-3.1 W2. (3) Added mandatory cross-verification Rule 9 to the mapping constitution: before writing JSON, quote actual named section headers from the target summary, confirm they are present, confirm chapter_number/title match. (4) Added the same verification step to the competency_mapping.md cowork prompt.
Carry-forward rule: Before writing a mapping JSON, always verify that the chapter_title matches the summary file's own opening heading, and that every competency justification references section headers verifiably present in THAT chapter's summary. A mismatch between summary content and JSON title is a silent error that the constitution must explicitly prohibit.

---

[Learning #17] — 2026-04-18 — Competency Mapping: Incidental Mention ≠ Architectural Engagement

Context: Competency mapping for Social Sciences VI Chapter 2 (Oceans and Continents).
Observation: A competency was incorrectly assigned because a concept central to that competency appeared by name within a structural element whose primary subject was something else entirely.
Root cause: The system applied Rule 6's named-structural-element test without first asking whether the competency's required cognitive operation was being performed on that concept as the primary object, or merely referenced in passing. The presence of a keyword in a named element is not sufficient — Rule 3 prohibits vocabulary matches regardless of whether a structural element exists.
Action taken: Competency removed. Rule 3 rejection applied retrospectively.
Carry-forward rule: A named structural element qualifies for a competency only if the cognitive operation that competency demands is performed on the primary subject of that element. If the competency's key concept appears only as incidental context within an element whose primary subject is something else, that is a vocabulary match and must be rejected under Rule 3 — regardless of whether a named structural element exists.

---

[Learning #16] — 2026-04-18 — Incidental Array Removed from Mapping Schema (Weight 1 Retained)

Context: User decision to discontinue the separate "incidental" array in mapping JSONs.
Observation: The schema previously had two arrays — "primary" (Weight 3 and Weight 2) and "incidental" (a separate bucket for lightly-touched competencies). The incidental array added noise without contributing to lesson plan generation, assessment design, or chapter_weight calculations.
Root cause: Original schema separated competencies into two named arrays. The separation was unnecessary and confusing.
Action taken: (1) The "incidental" array removed as a schema concept from all mapping JSONs. (2) competency_mapping.md cowork prompt schema updated accordingly. (3) All competencies — Weight 3, Weight 2, and Weight 1 — now appear in a single flat "competencies" array, distinguished only by their weight value.
Carry-forward rule: The mapping schema has a single flat "competencies" array. Weight 1 (Present) is a valid weight and entries with Weight 1 remain in the JSON. There is no separate "incidental" array. Only competencies that fail the constitution's weight tests entirely are absent from the JSON.

---

[Learning #18] — 2026-04-28 — Mathematics visual_stimulus: SVG Must Render as Graphic, Not Text

Context: Mathematics assessment items (Ch 05 Parallel and Intersecting Lines) emit `visual_stimulus` as inline `<svg>...</svg>` markup per the maths assessment constitution (Rule 7 — SVG is the PREFERRED format for lines, angles, polygons, number lines, fraction bars, coordinate diagrams). Both the HTML and PDF renderers were treating SVG as the "non-pipe-table" branch and dumping the raw `<svg>` markup as italic prose — meaning teachers saw a wall of escaped SVG source code instead of a figure.
Observation: The shared `_render_visual_stimulus()` (PDF) and `renderVisualStimulus()` (HTML) only had two branches — pipe-table or italic prose. SVG fell through to the prose branch.
Root cause: When the visual_stimulus rendering was first built (Learning #14, for Science pipe tables), the pipe-vs-prose split was the only distinction needed because Science / SS never emitted SVG. Mathematics was added later with SVG as a permitted format, but neither renderer was updated.
Action taken: (1) Added an SVG detection branch (string starts with `<svg` and contains `</svg>`) that takes priority over pipe-table detection in both renderers. (2) PDF: new `_render_svg_stimulus()` parses the SVG via svglib, scales to 70% of usable width with a 90mm height cap, centres in the same light-grey box used for tables/prose. Falls back to italic prose if svglib is unavailable or parse fails. (3) HTML: SVG injected inline (with sanitisation stripping `<script>` and `on*=` handlers), wrapped in a `.vs-svg` div with CSS that caps max-height at 320px and centres the figure. (4) Verified Science and Social Sciences PDFs regenerate identically — neither subject's `visual_stimulus` is ever SVG, so the new branch is a no-op for them.
Carry-forward rule: visual_stimulus rendering must branch on content type — SVG (Mathematics figures), pipe-table (any subject's tabular data), or prose (rare fallback). The renderer must never dump raw `<svg>` markup as visible text. Any new permitted format added to a constitution (e.g. LaTeX, Mermaid) requires a matching detection branch in both `_render_visual_stimulus()` (PDF) and `renderVisualStimulus()` (HTML) before that format ships in production. svglib is now a runtime dependency for the Streamlit app — must be present in any deployment environment.

---

[Learning #19] — 2026-04-28 — ReportLab Drawing Canvas Clipping at viewBox Edges

Context: First-pass implementation of `_render_svg_stimulus()` (Learning #18) showed Q-C-2 in math Ch 05 (parallel lines AB || CD with two transversals, labels A/B/C/D/E/F/G + angles 35°/95°) rendering only its top half — line AB with E and 35° were visible, but line CD, labels C/D/F/G, the 95° label, and the lower portions of both transversals were silently clipped. Other math SVGs (Q-A-1, Q-A-3, Q-A-5) rendered correctly. User report read as "no chart at all — just ABCDEFG35°95°".
Observation: The Q-C-2 SVG had viewBox `0 0 260 210` with line endpoints reaching y=200 (very close to the canvas edge) and text labels at y=152 and y=165. The other working SVGs had a comfortable margin between content and the viewBox edge.
Root cause: ReportLab's `Drawing` flowable clips its contents to the `width` × `height` bounding box. The first-pass code did `drawing.scale(scale, scale)` then set `drawing.width = orig_w * scale; drawing.height = orig_h * scale`. Mathematically this should fit, but anti-aliased stroke pixels and any glyph metrics that overrun the declared text y-coordinate fall outside the bounding box and disappear at render time. SVGs whose author used the entire viewBox right up to the edge were silently clipped; SVGs with internal padding rendered fine.
Action taken: Added overscan padding to `_render_svg_stimulus()`. Now the function: (1) translates the drawing by `(pad, pad)` BEFORE applying the scale transform, (2) applies the uniform scale, (3) sets `drawing.width = (orig_w + 2*pad) * scale` and similarly for height. With pad=6 source-units, every edge stroke and label gets a guaranteed margin inside the canvas. Verified Q-C-2 now renders all elements (lines AB, CD, both transversals, labels A through G, both angle labels). Q-A-3 (previously working) confirmed unchanged — no regression.
Carry-forward rule: When rendering an svglib `Drawing` inside a ReportLab story, never set `drawing.width`/`drawing.height` to exactly `orig * scale` — always add an overscan margin (~6 source-units of padding × scale) on every side, and apply a matching `drawing.translate(pad, pad)` before the scale transform. This is independent of the SVG's own viewBox correctness — even mathematically-sound SVGs lose pixels at the edges of the ReportLab canvas. Rule applies to any future renderer that embeds SVG into PDF via svglib.

---

[Learning #20] — 2026-04-29 to 2026-05-04 — Mathematics VII: Full Pipeline Completed

Context: Post SVG-fix session to complete Mathematics VII end-to-end.
Observation: All 8 chapter summaries (JSON format) and all 8 competency mappings generated and stored. Maths LP constitution updated to v3.1 (anchor_id priority widened to WE-N and A-N when exercise pool exhausted; phase descriptions capped at ~10 words). Assessment constitution updated to v3.2 (two-artefact design: freshly generated question + textbook exercise companion; structured teacher_guide replaces one-line form). A saved plan for Ch 02 confirmed the full pipeline works end-to-end.
Action taken: All mirror data complete. Framework files for mathematics preparatory and secondary stages added.
Carry-forward rule: Mathematics VII pipeline is fully operational. Any future Maths chapter generation is purely a run task — no constitution or pipeline changes needed unless a new chapter type surfaces an unhandled edge case.

---

[Learning #21] — 2026-05-04 to 2026-05-10 — English VII: Subject Architecture and Pipeline

Context: English is structurally different from all prior subjects. No per-chapter competency mapping in the conventional sense — instead a 6-spine progression (Reading for Comprehension → Listening → Speaking → Writing → Vocabulary/Grammar → Beyond-the-Text) drives both LP and assessment.
Observation: (1) English uses a TWO-AXIS structure: outer axis = main_sections (poem, prose, dialogue etc.), inner axis = 6-spine cells within each section. The LP walks sections in textbook order, then spines within each section. C-codes do NOT appear in the LP JSON — NCF compliance is implicit in the spine structure itself. (2) Competency mapping for English uses equal Weight 1 across all applicable C-codes, plus effort signals (spine_load, task_density, writing_demand, project_load) that combine into an effort_index — this drives the Allocate tab, same as Science/Maths. (3) The combined cowork prompt (`chapter_summary_competency_mapping_english.md`) generates both summary JSON and mapping JSON in a single pass. (4) English framework files (CG + pedagogy for middle/preparatory/secondary stages, spine_to_cg mappings) added to mirror/framework/english/. (5) Ch 01 (Learning Together) summary and mapping complete. Multiple saved plans generated and refined through several constitution iterations (LP v1.5, Assessment v3.0).
Root cause of iteration: English assessment initially modelled on Science/SS (per-competency question types). Revised to LP→Assessment handoff arc: LP generates one implied_lo per (section × spine) cell; assessment generates one original item per implied_lo grounded in section text. Simpler and more faithful to language pedagogy.
Action taken: English LP constitution v1.5 and Assessment constitution v3.0 finalised. Allocate page updated to handle English effort_index display (same visual as Science/Maths). app.py extended to load English summaries/mappings in JSON format (already in `_JSON_SUMMARY_SUBJECTS`). Multiple test HTML files generated during assessment renderer debugging (test_debug.html, test_fixed.html etc.) — these are scratch artefacts, can be deleted.
Carry-forward rule: English assessment must NOT use C-codes or per-competency question-type rules. The sole driver is (section × spine) implied_lo values handed off from the LP. Any English chapter generation follows: run combined summary+mapping prompt → generate LP → LP handoff feeds assessment. No separate mapping step.

---

[Learning #22] — 2026-05-10 — LP PDF v3 Wired In (lp_pdf_generator.py)

Context: The LP PDF generator was overhauled and the new file (`aruvi_streamlit/lp_pdf_generator.py`, v3) wired into app.py, replacing the old inline `generate_pdf_bytes_lp()` function for English and Mathematics.
Key improvements in v3: Unicode sanitiser (_clean_text strips diacritics), Aruvi logo in page header with graceful fallback, dynamic page numbers via two-pass pypdf overlay, section anchor shows first sentence only, "LO" label drawn inside LOBox, "Confidential" footer removed, chapter_weight shown alongside total periods.
Observation: app.py now imports `build_lp_pdf_bytes` from `lp_pdf_generator` for the Generate tab (both bot and manual paths) and My Plans tab. The old inline function remains in app.py for Science/SS (not yet migrated).
Carry-forward rule: lp_pdf_generator.py (v3) is the current LP PDF standard. When migrating Science/SS to this generator, the main difference to handle is the Science/SS LP JSON structure (progression-stage based) versus the English/Maths structure (section × spine). Keep the old inline function in app.py until Science/SS migration is tested.

---

[Learning #23] — 2026-05-11 — English Assessment PDF/HTML: Seven Layout Fixes

Context: Post-English-pipeline review of assessment PDF and HTML output for Ch 01.
Fixes applied to assessment_pdf_generator.py and lpa_page.html:

1. Section name (spine title) now appears centre-aligned above EVERY English question (not just the first in each spine section). The English build loop passes header_items for every question. Font increased from 7.5pt → 8.5pt. (Previously it only appeared on the first question of each spine group.)

2. "Guidance" section renamed → "Notes" (all subjects). A PageBreak is inserted before it so it always begins on a fresh page at the end of the document, never mid-content.

3. Learning Outcome row moved to below the Teacher Guide block (with a 4pt spacer gap). LO font increased from q_meta (6.5pt) → q_lo (7.5pt). Previously LO appeared above the prompt alongside the source section title.

4. Word box (Listening MATCH, PDF): Rebuilt _render_word_box() to render individual pill cells in a nested table row, matching the HTML's pill-style layout (.vs-wordbox-word chips). Previously it rendered a flat paragraph with spaces between words.

5+6. FILL_IN question (Vocab/Grammar): item_stem contains inline markdown tables (pipe syntax). Previously the raw markdown showed as text AND visual_stimulus (Part A table only) appeared below Part B. Fix: added _render_fill_in_stem() in PDF (splits text and pipe-table segments, renders each table inline) and renderMarkdownStemHtml() in HTML (same logic). visual_stimulus is now suppressed for FILL_IN in both renderers to prevent duplication. Rule: any FILL_IN item must store its tables inline in item_stem; visual_stimulus should be empty or omitted.

7. Teacher Guide Part A / Part B shown as one paragraph: fmtGuide() (HTML) and _eng_guide_paras() (PDF) now split on "Part A / Part B / Part C" label patterns in addition to numbered items and lettered sub-items. Both functions use regex to insert line breaks before these patterns when they appear run-together in a single string.

Carry-forward rules:
- Any new question type that uses inline markdown tables in item_stem must go through renderMarkdownStemHtml (HTML) and _render_fill_in_stem (PDF) — not the default plain-text path.
- visual_stimulus for FILL_IN must be left empty; put all tables in item_stem.
- Teacher guide strings with Part A/B splits must not rely on newlines — the fmtGuide/eng_guide_paras regex handles run-together strings automatically.
- The Notes section (formerly Guidance) always uses a PageBreak before it. Do not remove this — it ensures Notes never appears mid-document.

---

[Learning #26] — 2026-05-25 — English Assessment: Textbook Content Contamination in Poem Chapters

Context: Grade V Ch 01 (Papa's Spectacles — a short poem) assessment generated for the first time. Assessment items across all five spines (Reading, Oracy, Writing, Word Work, Beyond Text) were found to reproduce textbook exercise content verbatim or near-verbatim — ascending-order word groups, spelling near-miss sets, homophone pairs, the onion riddle — all lifted directly from question_bank[] entries in the chapter summary JSON.

Observation: The May 2026 English VII fix (commit 0f59c23) that banned tasks_verbatim[] / question_bank[] via prompt instruction alone worked for VII because VII Ch 01 is a prose chapter with a 1,989-character prose_summary. The model anchored to that rich content naturally. Grade V Ch 01 is a short poem — poem_text is only 407 characters and poem_appreciation_summary is 730 characters. For Word Work, Oracy, and Beyond Text spines, the section_context in the coverage_handoff describes skills (ascending-order logic, homophone discrimination, riddle solving) that have no foothold in the poem text itself. Facing thin legitimate content, the model reached for the ready-made question_bank[] content despite explicit prohibition.

Root cause: Two distinct problems:
(1) Poem text too thin to support skill-type spines — for Oracy/Word Work/Beyond Text, the LP taught textbook exercises completely detached from the poem. No amount of prompt instruction can make the model generate from poem_text when poem_text has no relevant content for those skills.
(2) Even for Reading and Writing where poem_text is sufficient, the model still copied textbook framing because question_bank[] was visible in context — the path of least resistance.
The core principle: you cannot reliably instruct a model to ignore data that is sitting in its context window.

Constitution fix: Four minimal edits to English Assessment Constitution (middle) v3.1:
- INPUTS §2: "ONLY" → "primary" + exception clause for skill-type spines with no poem foothold
- Rule 2a: removed "strictly", added pointer to INPUTS §2 exception
- Rule 3 REQUIRED: added sixth bullet for fresh skill-type exercise instances themed around the poem world
- Rule 3 PROHIBITED: added "or question_bank entries" to the recycled-wording prohibition
Constitution fix alone was insufficient — model still contaminated because forbidden fields remained visible.

Definitive fix (confirmed by test): Strip tasks_verbatim[] and question_bank[] from the summary JSON in memory before building the assessment prompt. Tested by temporarily stripping the summary file — output was clean across all five spines. The model generated original items: fresh homophone pairs, new word-ordering sets, new spelling examples, a new riddle, all themed around the poem's world.

Pending permanent fix: `generate_assessment_only()` in app.py must strip tasks_verbatim and question_bank from the summary dict before passing it as `_static_user_text`. ~10-line addition, no architectural change. Also applies to `build_english_prompts()` for the combined LPA path.

Carry-forward rules:
- Constitution prohibitions alone cannot override data the model can see. If a field must not influence output, strip it from the prompt — do not rely on instruction.
- Short poem chapters (single section, thin poem_text) are the highest-risk case. Prose chapters with rich prose_summary are naturally safer.
- The strip must happen in both assessment paths: generate_assessment_only() (deferred) and build_english_prompts() (combined LPA).
- After stripping, the model correctly falls back to: section_context (skill type) + implied_lo (cognitive demand) + poem_text/poem_appreciation_summary (thematic anchor) — which is exactly the intended design.

---

[Learning #24] — 2026-05-21 — SS Assessment: Competency-LO Coherence Constraint

Context: Audit of saved plans SS VIII Ch 03, Ch 04, Ch 05 examining LP→Assessment coherence.
Observation: The assessment was occasionally assigning an implied_lo to a question whose competency.c_code did not match the c_code of the period that generated that implied_lo in the LP handoff. For example, Ch 03 Q7 (filed under C-3.2) carried the implied_lo from P5 (C-4.1). Ch 04 Q9 (filed under C-2.1) carried the implied_lo from P4 (C-3.2). The violation is narrow and specific — most questions were clean. It occurs when the system fills a competency's weight-slot and reaches for an LO from a thematically adjacent period belonging to a different competency, rather than reframing the question to fit the competency's own periods' LOs.
Root cause: The SS assessment constitution (pre-v1.6) permitted cross-period LO synthesis (Rule 1) without any constraint requiring the implied_lo to be sourced from a period whose c_code matches the question's competency. The period_ref could legitimately span multiple competencies for content grounding — and this is correct and should remain permitted — but the implied_lo field was also being sourced from those cross-competency periods, which is wrong.
Important distinction: A cross-competency period appearing in period_ref as a content reference is NOT itself a violation. Q6 in Ch 04 (refs=[10,4]) is clean — P4 is cited because the question content genuinely draws on P4's section, but the implied_lo comes from P10 (C-2.1). Only the implied_lo field's sourcing matters for this constraint.
Action taken: Added COMPETENCY-LO COHERENCE CONSTRAINT to Rule 2 of SS Assessment Constitution v1.6. The constraint requires that implied_lo must come from a period whose c_code matches the question's competency.c_code. Cross-competency period_refs for content remain permitted. If no suitable implied_lo exists among the competency's own periods, the system must reframe the question — not borrow from another competency's period.
Carry-forward rule: When auditing SS assessment output, check that every item's implied_lo text matches one of the implied_los in the LP handoff periods assigned to that same c_code. A mismatch between implied_lo origin and competency.c_code is a constitution violation from v1.6 onward. Science, Mathematics, and English are not exposed to this issue — their architectures (stage-position, one-item-per-goal, and C-code-free respectively) do not create the competency slot-filling dynamic that produces this problem in SS.

---

[Learning #28] — 2026-05-28 — TWAU: Unit Information Belongs Only in unit_map.json, Not in Summary JSON

Context: TWAU chapter PDFs do not carry unit information. Unit names appear only in the Prelims PDF (table of contents). Question arose whether the chapter summary should source unit info from the Prelims PDF or unit_map.json.
Decision: Unit information serves a single purpose — chapter listing in the Allocate tab. It has no role in lesson plan generation, assessment, or competency mapping. unit_map.json (one static file per grade, already created for iii, iv, v) is the canonical source for unit info at the Allocate tab. The summary JSON does not carry a `unit` field.
Action taken: Removed `unit` field from step_1_chapter_summary.md: (1) deleted the "Also record the unit..." instruction from Step 1, (2) removed `"unit"` from the Step 6 schema example, (3) added `"unit"` to the explicit exclusion list ("No `unit` field").
Carry-forward rule: TWAU unit info lives exclusively in `mirror/chapters/the_world_around_us/{grade}/mappings/unit_map.json`. The Allocate tab reads from there. Nothing else in the pipeline reads or writes unit information. Do not re-introduce a `unit` field into summary or mapping JSONs.

---

[Learning #27] — 2026-05-28 — TWAU Grade III Consistency Check: Architecture Holds, Three Constitution Guards Added

Context: Grade III Unit 3 chapters (Ch 7 Water, Ch 8 Food, Ch 9 Staying Healthy and Happy) reviewed against the proposed TWAU Aruvi architecture developed from Grade IV/V sample chapters.
Observation: The full architecture (effort index for allocation, single-axis LP by sections, CG codes at period level, one assessment item per CG-strand per period, Option B activity rule) is consistent with Grade III content. No structural breaks found.
Three constitution-level guards identified:
(1) CG-3 natural flagging: Grade III has strong CG-3 content (safety, hygiene, stranger safety in Ch 9). Decision: trust the CG-mapping process to flag CG-3 naturally — no special constitution instruction needed. Revisit only if actual pilot runs under-assign CG-3 for Grade III chapters. [WATCH ITEM — check in first Grade III run]
(2) OPEN_TASK performance variant: When C&E/R&A content maps to physical behaviour (hygiene routines, safety role-play), the assessment item should be flagged as a performance_task subtype within OPEN_TASK, not a written creative task. Constitution should note this distinction for lower primary.
(3) IKS lower-primary anchor: The constitution's IKS guidance (indian_knowledge_element field) should include at least one lower-primary example (datun/neem tradition, matka/surahi water vessels, seasonal eating) so the LLM does not default exclusively to upper-primary IKS examples.
Root cause: Grade IV/V sample had no CG-3-dominant chapters and no physical-behaviour OPEN_TASKs, so these edge cases were not visible in the initial design.
Action taken: Guard (1) — deferred, watch item. Guard (2) and (3) — noted as constitution refinements; to be applied when TWAU constitution is authored (not an architecture change).
Carry-forward rule: TWAU architecture is grade-agnostic (III through V). Grade III's lower effort indices and coarser section grain are expected outputs of the formula, not anomalies. CG-3 watch item must be checked against first Grade III pilot run.

---

[Learning #25] — 2026-05-23 — Mathematics PDF: Superscript and Math Symbol Blanking

Context: Mathematics Ch 05 (Prime Time) PDF showed blanked-out content wherever superscript notation like 2⁴ × 5⁴ appeared. HTML rendered correctly; PDF was blank at those positions.
Observation: ReportLab's built-in Helvetica font only covers latin-1 (U+0000–U+00FF). Unicode superscript digits ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ (U+2074–U+2079) and math symbols ≤ ≥ ≠ → − ✓ are all outside this range. When passed to a Helvetica Paragraph, these characters render as blank space with no error. The issue affected: (a) LP phase descriptions (e.g. "10000 = 2⁴ × 5⁴"), (b) assessment question prompts, (c) exercise companion card descriptions.
Root cause: _clean_text() in lp_pdf_generator.py only substituted a small set of known out-of-range chars (₹ → Rs., dashes, quotes, ellipsis). All other out-of-range math/science symbols were silently dropped by Helvetica's glyph lookup.
Action taken: (1) Expanded _UNICODE_SUBS in lp_pdf_generator.py to cover all math/science symbols found in saved plans: → ← ↔ − × ÷ ≤ ≥ ≠ ≈ ∞ √ ∑ ∏ ∈ ∉ ∩ ∪ ✓ ✗ and all superscript/subscript digits. (2) Added _apply_superscripts() function that converts Unicode superscript chars (⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ) to ReportLab XML <super> tags, giving proper raised rendering in Paragraphs. (3) Exported _apply_superscripts from lp_pdf_generator and imported in assessment_pdf_generator. (4) Wired _apply_superscripts into: Maths question prompt text (q_text), exercise companion description, and period_card_maths time-breakdown phase descriptions.
Critical ordering rule: _apply_superscripts MUST run BEFORE _clean_text. Correct: _clean_text(_apply_superscripts(raw)). Wrong: _apply_superscripts(_clean_text(raw)). If _clean_text runs first, it maps ⁴→^4 as a plain-text fallback and _apply_superscripts never sees the superscript chars.
Carry-forward rule: Any new Mathematics (or other subject) content field that may contain Unicode superscripts must use the _clean_text(_apply_superscripts(raw)) pipeline for Paragraph text. Science/SS/English are not affected — their constitutions do not emit superscript digits. If a new subject constitution introduces superscripts, apply the same pattern. The _UNICODE_SUBS fallback (⁴→^4) is a last-resort for non-Paragraph contexts only (e.g. metadata strings, filenames).


---

[Learning #26] — 2026-06-06 — English Secondary (Grade IX): constitution fork + separate transcript file

Context: Extending Aruvi English to the secondary stage (Grade IX, secondary textbook). Read Ch 1 (How I Taught My Grandmother to Read — prose memoir + "Bharat Our Land" poem) and Ch 6 (Twin Melodies — a three-act play + two poems).

What was built: Forked SEPARATE secondary constitutions (not parameterized) at:
  - mirror/constitutions/lesson_plan/english/secondary/lesson_plan_constitution.txt (v1.0)
  - mirror/constitutions/assessment/english/secondary/assessment_constitution.txt (v1.0)
All deltas from the middle constitution are flagged inline as [SECONDARY DELTA].

Key structural decisions (carry forward):
1. NEW section_type `drama` — a multi-act play is one main_section. Reading-for-Comprehension is read ACROSS acts; read-aloud is ROLE-ASSIGNED reading (Rule 2A); summary uses `drama_summary` (act-by-act arc). The assessment/renderer pipeline needs a `drama` branch wherever section_type is switched on (lpa_page.html + assessment_pdf_generator.py) before shipping — NOT yet wired.
2. NEW assessment item type `EXTRACT_ANALYSIS` — verbatim extract in visual_stimulus + numbered analytical sub-questions in item_stem; classified OPEN; mirrors the textbook's dominant "Critical Reflection" mode. Renderer needs an EXTRACT_ANALYSIS branch (extract block + numbered sub-qs) before shipping.
3. Raised cognitive demand: secondary Reading items prefer EXTRACT_ANALYSIS/ECR over MCQ; rubrics deeper (Rule 11); permitted methods include debate, close-reading, media-scripting, reported-speech grammar, multilingual exploration.
4. Secondary framework assets ALREADY existed before this work: mirror/framework/english/secondary/ has cg_secondary_english.txt, pedagogy_secondary_english.txt, spine_to_cg.json, competency_descriptions_secondary.json. The secondary spine_to_cg.json already carries the correct secondary subheading names (Reading for Meaning, Check Your Understanding, Critical Reflection, Reflect and Respond, Reading for Appreciation, Vocabulary and Structures in Context, Listen and Respond, Speaking Activity, Writing Task, Learning Beyond the Text, POINTS TO REMEMBER).

CRITICAL — SEPARATE TRANSCRIPT FILE (differs from middle):
  - Middle: listening transcript lived INSIDE each chapter PDF; transcript_ref="p.NN" indexed the chapter PDF.
  - Secondary: transcripts are in a standalone appendix booklet knowledge_commons/textbooks/english/ix/transcript.pdf (20 physical pages, all 8 units). transcript_ref (e.g. "p. 270") is the PRINTED textbook page number, NOT a chapter-PDF page and NOT a physical page in transcript.pdf.
  - Page-offset mapping (verified): printed_page − 258 = physical_page in transcript.pdf, from printed 260 onward (physical 1 = printed 259, marker is "Appendix" header). Booklet organised by Unit 1…Unit 8 in textbook order. The printed page footer (book-title marker, e.g. "<Title> NNN", or "Appendix NNN") appears in page text → locate by text search, not by physical index.
  - Ch 1 listening: printed 259 (digital literacy) + 260 (four travellers). Ch 6 listening: printed 270 (yazh) + 271 (music-centre dialogue).

DESIGN DECISION (user, 2026-06-06) — bake transcript into summary:
  When the secondary step_1 (chapter summary) prompt is authored, it MUST resolve each listening cell at summary time: open transcript.pdf, find the page by printed marker, and write the shortened transcript body (150–250 words, all speakers preserved — same as middle prompt's transcript_text) directly into the summary JSON listening cell. The summary becomes self-contained; LP and Assessment generators read transcript_text from the summary and NEVER open the appendix PDF. transcript_ref stays as a provenance pointer only. Optional summary fields transcript_file + transcript_unit make the lookup unambiguous. Assessment constitution Rule 6 already updated to verify against summary transcript_text, with PDF as fallback only.

Open items for the secondary step_1 prompt (NOT yet written):
  a. Drop the middle prompt's assumption that "a closing poem usually carries only Reading + Vocabulary" — Ch 1's "Bharat Our Land" poem section exercises ALL six spines.
  b. Treat end-of-chapter "read and enjoy" enrichment poems (e.g. "Music" by Walter de la Mare at end of Ch 6) as beyond_text content of the preceding section, NOT as their own main_section.
  c. Tune effort_signals for secondary (drama sections are long/multi-act; analytical task density is higher).
  d. Add `drama` to the section-type detection and the drama_summary field.

Still TODO before secondary is production-ready: renderer branches for `drama` section_type and `EXTRACT_ANALYSIS` item type; secondary step_1 combined prompt; update CLAUDE.md §4/§5 to register the secondary stage; consider adding english to any stage-list configs.

[Learning #26 — correction, 2026-06-06] — Secondary LP: "textbook order" ≠ canonical spine order
Issue found: LP constitution Rule 3 Step 3 originally said "walk spines in textbook order (RFC → Listening → Speaking → Writing → VocGram → Beyond-text)" — self-contradictory at secondary. In the secondary textbook the on-page spine sequence is NOT the canonical key order: Vocabulary/Grammar follows the Reading cluster, and "Listen and Respond" appears LATE (after Vocab in Ch 1; after Speaking+Writing in Ch 6), and the two chapters disagree on where Listening falls. (This held in middle only because "Let us read/listen/speak/write/learn/do" matched the canonical order — a coincidence not true at secondary.)
Fix applied: LP Rule 1 and Rule 2 Step 3 now state two INDEPENDENT orders — (a) WALKING / period-assignment order = the literal on-page sequence recorded in the summary for that section; (b) ENUMERATION/emission order (coverage_handoff keys, assessment spine emission) = canonical fixed order. The generator must NOT re-sort walk order into the canonical list. "Adjacent spines" in a period means adjacent in the on-page sequence.
Carry-forward: the secondary step_1 prompt MUST record each section's spines in on-page order (the summary's spine object order is the source of truth for walk order). Assessment constitution Rule 1 emission order stays canonical and is correct as-is — do not change it.

[Learning #26 — addendum 2, 2026-06-06] — Secondary step_1 prompt forked + effort tiers recalibrated
Forked the middle combined prompt to: cowork prompts/english/secondary/step_1_chapter_summary_and_mapping.md (457 lines). Fixed all 8 gap points vs middle:
  1. secondary subheading table (Reading for Meaning / Check Your Understanding / Critical Reflection / Reflect and Respond / Reading for Appreciation; Listen and Respond; Speaking Activity; Writing Task; Vocabulary and Structures in Context / Vocabulary in Context; Learning Beyond the Text / POINTS TO REMEMBER) — replaces the middle "Let us …" table. Authoritative, matches secondary spine_to_cg.json.
  2. drama section type + drama_summary (250–450 word act-by-act arc); a multi-act play is ONE section, not per-act sections.
  3. Transcript BAKED at summary time: Step 6 resolves transcript.pdf (printed textbook page; offset printed−258=physical, but confirm by marker text), writes transcript_text (150–250w) + transcript_file + transcript_unit into the listening cell. LP/Assessment never open the appendix.
  4. Spines recorded in ON-PAGE order (LP walk-order source of truth); mapping/competency emission stays canonical order (Step 8).
  5. Dropped the "poem usually only Reading+Vocab" assumption — Bharat Our Land poem section exercises all 6 spines; template shows it.
  6. Enrichment "read and enjoy" poems (e.g. "Music" de la Mare) are beyond_text tasks, NEVER their own main_section.
  7. All paths → /secondary/, stage "secondary", grade ix.
  8. Recalibrated effort tiers (see below).

EFFORT-TIER RECALIBRATION (secondary-specific; middle tiers were broken here):
  Root cause: every secondary section exercises all 6 spines, so middle spine_load (avg-spines-per-section) pinned at constant 3 → non-discriminating; both Ch1 and Ch6 collapsed to identical effort_index 11.0 under middle tiers.
  New secondary tiers:
    spine_load (re-based on TOTAL spine-cells, not avg/section): ≤6→1, 7–12→2, ≥13→3.
    task_density (tightened): avg≤2.5→1, 2.6–4.5→2, ≥4.6→3.
    writing_demand UNCHANGED: 0–5→0, 6–15→1, 16+→2.
    project_load UNCHANGED: count of beyond_text cells.
    formula UNCHANGED: (spine_load×2)+(task_density×1.5)+(writing_demand×1.5)+(project_load×1).
  Calibration check (manual tally from chapter text, not a live run): Ch1 (prose+poem, 12 cells, ~28 tasks, ~7 write items, 2 beyond) → sl2/td1/wd1/pl2 = 9.0. Ch6 (drama+poem, 12 cells, ~35 tasks, ~9 write items, 2 beyond) → sl2/td2/wd1/pl2 = 10.5. Now they DIFFER (Ch6 heavier, as expected). These are reference values; the prompt recomputes per chapter, does not hardcode.

HOLD: User instructed NOT to run the prompt on chapters yet (2026-06-06). Task "Run prompt on Ch 1 + Ch 6" is ON HOLD pending explicit go-ahead. Do not generate ix summary/mapping JSON until told.

[Learning #26 — addendum 3, 2026-06-06] — task_density tiers reverted to middle; prompt slimmed
User decision: restore the MIDDLE task_density tiers (≤3.0→1, 3.1–6.0→2, ≥6.1→3); keep the recalibrated spine_load (total spine-cells: ≤6→1, 7–12→2, ≥13→3); writing_demand, project_load, and the effort formula stay as middle. So the only secondary-specific tier change is spine_load.
Effect on calibration reference: under restored density tiers, Ch1 and Ch6 BOTH read task_density 1 → effort_index 9.0 each (Ch6's 2.92 avg now falls in tier 1, not the previously-proposed tier 2). spine_load (re-based on cell count) remains the discriminating signal across chapters of different section counts. Prompt's Step 7 reference values updated to 9.0 / 9.0.
Also: slimmed the secondary step_1 prompt 457 → 331 lines (crisp pass; no step/field/delta/constraint removed). Step 8b mapping JSON template verified strict-valid.

[Learning #27] — 2026-06-06 — English secondary LP: Rule 9 teacher-prose leak + verification pass
Symptom: the generated ch_06 secondary LP (mirror/saved_plans/english/ix/ch_06_20260606_150100.json) leaked internal task indices into teacher-facing prose — "task 3", "Tasks 5 and 6", "Speaking task 1", "task 0" etc. in teacher_notes (and one homework note). This violates LP constitution Rule 9 (no task indices / internal refs in teacher-facing narrative). It was a GENERATION-TIME slip, not a constitution gap — Rule 9 already banned it; the model just didn't honor it on that run.
Fix applied to the saved plan: rewrote every offending teacher_notes/homework sentence to reference tasks by their teacher-facing anchor (spine subheading) + plain brief, matching the established rubric (maths Rule 10 uses book_ref; English Rule 9 uses <spine_section_name> + brief). The structured join-key arrays (tasks_in_class/homework/tasks_anchored) still carry task_index — those are NOT prose and were left untouched.
Durable fix — VERIFICATION PASS added:
  - New script: aruvi-scripts/lint_lp_teacher_prose.py. Scans only teacher_notes + phase descriptions (not the join-key arrays) for: task indices ("task N", ranges/lists), task_index key, internal item IDs (Q-RFC-A-1, A-1, WE-3…), schema/planner keys, "Rule N" refs, and C-codes. Accepts full saved-plan shape OR bare LP. Exit 0 clean / 1 leaks / 2 bad input. Tested: cleaned file PASSES, injected-leak copy FAILS catching all 7 categories.
  - LP constitution Rule 9 (secondary) updated: enumerates the banned forms explicitly, says they apply to BOTH phase description and teacher_notes, and mandates running the lint after every LP generation (run not complete until lint passes).
Carry-forward: run lint_lp_teacher_prose.py on every generated English LP (any stage — the script is stage-agnostic) before accepting/saving it. Consider adding the same lint hook for middle/preparatory LP constitutions, and an analogous teacher-prose lint for assessment item_stem/expected_elements if leaks ever appear there.

[Learning #27 — addendum, 2026-06-06] — task_brief is teacher-facing too; codes + missing anchors
Two further Rule-9 leak types found in the same ch_06 secondary LP, beyond the prose task-indices already fixed:
  (a) Internal question-type CODES (MCQ, ECR, …) appeared in task_brief AND in some phase descriptions (P4/P5/P10/P11). A teacher should see "multiple-choice"/"extended-answer", not "MCQ"/"ECR".
  (b) task_brief mostly lacked a subheading ANCHOR, so a teacher couldn't locate the exercise. Both tasks_in_class and homework briefs were affected (homework especially, as flagged).
Root cause of the miss: task_brief lives inside the structured arrays, so the original lint (and Rule 9 wording) treated those arrays as exempt "machine-readable fields". WRONG — task_brief is rendered to teachers; only the numeric task_index join key is exempt.
Fixes (durable):
  - lint_lp_teacher_prose.py EXTENDED: added an "internal question-type code" rule; now also scans task_brief in tasks_in_class + homework with (i) the code/id rules and (ii) a REQUIRED subheading-anchor check (SUBHEADING_ANCHORS = the secondary subheadings). Tested: fixed file PASSES (exit 0); injected code/anchor leaks FAIL.
  - LP constitution Rule 9 (secondary) REWRITTEN: explicitly names task_brief as the third teacher-facing field, bans question-type codes (with the plain-word substitutions), requires the anchor in task_brief, and clarifies that ONLY task_index is exempt. Verification-pass clause updated to say the lint covers all three fields incl. missing-anchor briefs.
  - ch_06 saved plan fully cleaned: 19 briefs anchored, codes removed from briefs + phase descriptions + one teacher_notes; coverage_handoff tasks_anchored briefs mirrored. Lint now exit 0.
Carry-forward: the lint is the gate for ALL three teacher-facing fields. When the secondary LP is regenerated (or any English LP), run lint_lp_teacher_prose.py and do not accept until exit 0. Same fix should be back-ported to middle/preparatory English LP constitutions + any LP-generation prompt when those are next touched.

[Learning #27 — addendum 2, 2026-06-06] — task_brief needs a PAGE locator, not just the subheading
User point: a brief like "Critical Reflection: six extended-answer questions…" names the exercise TYPE but not WHERE — a teacher still can't find it. The locator must be subheading anchor + page (e.g. "(p.184)").
Fixes:
  - ch_06 LP: back-filled a page ref into EVERY task_brief (in-class + homework + coverage_handoff mirror), sourced authoritatively from the summary's per-task page_ref; tasks with no page_ref in the summary (warm-up/oral/open prompts — Reflect-and-Respond openers p.169, pre-listen p.188, Anuradha writing prompt pp.190–191) got the chapter activity-page hint. 0 briefs now lack a page.
  - lint_lp_teacher_prose.py: added a PAGE_REF check to scan_brief — a task_brief must contain p.NN / pp.NN-NN as well as a subheading anchor. Tested: corrected file PASSES; a brief with the anchor but no page FAILS ("missing page locator").
  - LP constitution Rule 9 (secondary): task_brief format tightened to "<Subheading> (p.NN): <plain brief>"; page comes from summary page_ref, else section range; explicitly notes HOMEWORK is bound identically. Worked example uses Critical Reflection (p.184).
Net: a task_brief now must satisfy three things to pass the verification pass — no internal code/index, a subheading anchor, AND a page locator. Carry-forward: same three-part brief requirement applies when regenerating any English LP and should be back-ported to middle/preparatory constitutions.

[Learning #28 — 2026-06-12] — Secondary Science LP: coverage_handoff restored to dedicated appended array
Problem: the Secondary Science LP constitution structured its coverage handoff differently from every other LP. It embedded the handoff fields INSIDE each period object — competency{c_code, cg, competency_text}, implied_lo, and section_context per period — so the competency statement (and LO/context) repeated across every period of the same section. All other LPs (middle Science Amendment A4, Maths Rule 11, English Rule 10) emit a dedicated coverage_handoff as a sibling key appended after the lesson plan, deduplicated by their organizing unit.
Fix (constitution — mirror/constitutions/lesson_plan/science/secondary/lesson_plan_constitution.txt):
  - Rule 6 rewritten: one implied_lo + section_context PER SECTION (not per activity/period), emitted in the handoff; explicit prohibition against placing implied_lo/section_context/competency in any period object.
  - Amendment A3 period schema stripped to teaching mechanics only (period_number, duration, activity_title, section_anchor, pedagogical_approach, materials, visual_aids, time_bands, homework). Removed competency{}, implied_lo, section_context.
  - Added Rule 9 (Coverage Handoff — required companion output) + Amendment A4 (SCIENCE · SECONDARY): coverage_handoff is a top-level ARRAY, ONE entry per anchored section (Rule 1 spine = sections, unlike middle science's progression stages). Fields chosen to MATCH the existing middle-science assessment constitution's reader contract: section_number, section_label, total_sections, period_numbers[], period_duration_minutes, activity_summary, implied_lo, section_context, cg, c_code, co_central. Where a section spans >1 period, those periods collapse to one entry (period_numbers lists them) — fields not repeated per period.
  - Header OUTPUTS + Rule 7 competency-exemption note updated to point at the handoff.
Fix (renderer — aruvi_streamlit/lp_pdf_generator.py, _json_to_science_secondary_lp_data):
  - Reads top-level coverage_handoff; builds period_number -> implied_lo lookup from period_numbers[], and resolves the competency fallback c_codes from the handoff.
  - BACKWARD COMPATIBLE: older saved plans (e.g. mirror/saved_plans/science/ix/ch_08_*.json) embed implied_lo/competency per period and carry a DICT-shaped (empty) coverage_handoff. Adapter guards isinstance(handoff, list); when not a list, falls back to per-period implied_lo / per-period competency object. Verified both shapes resolve correctly.
Carry-forward: the primary competency source for the header table remains the chapter mapping JSON + framework descriptions file (unchanged); handoff c_codes are only a fallback. The existing grade-IX saved plan still renders via the legacy path — regenerate it to migrate to the new array shape. Downstream assessment for secondary science currently reuses the middle assessment constitution (no secondary assessment constitution exists yet); the handoff field names were deliberately aligned to it.

---

[Learning #29] — 2026-06-16 — Mathematics Secondary: Step 2 (competency mapping) authored; chapter skill found out of date for Mathematics generally

Context: Mathematics secondary already had a working step_1 chapter-summary prompt (JSON output, emitting three effort signals: conceptual_demand 1–3, reasoning_load 0–3, exec_load 0–2 — a 3-signal scheme, distinct from middle's 4-signal scheme (conceptual_demand, activity_count→activity_load, demo_count→demo_load, exec_load) and preparatory's 4-signal scheme (conceptual_demand, task_load, exploration_load, procedural_load)). Step 2 (competency mapping) and its mapping constitution did not exist for secondary.

What was built: `mirror/constitutions/competency_mapping/mathematics/secondary/mapping_constitution_mathematics.txt` (v1.0) and `cowork prompts/mathematics/secondary/step_2_competency_mapping.md`, modeled structurally on the preparatory constitution (Rules 1–4 and 6 identical pattern across all three Mathematics stages; only Rule 5 — the effort index — differs per stage, by design precedent). User then independently refined both files further during the session (added `co_central` field, narrowed adjunct cap to ≤2, added a breadth-vs-difficulty design principle, retuned the formula to `(CD×2)+(reasoning_load×2)+(exec_load×1.5)`).

Separate issue surfaced while wiring this in: the `chapter` skill's SKILL.md (lives in a read-only Cowork skills cache — cannot be edited from inside a session) treats Mathematics as a single flat, non-stage-routed subject, with a prompt path of `cowork prompts/mathematics/step_N_*.md`. This is wrong and predates this session — Mathematics has been stage-split (`{subject}/{stage}/...`) like English since at least the preparatory/secondary framework files were added (per Learning #20, "Framework files for mathematics preparatory and secondary stages added"). The skill text was simply never updated when that split happened.

Action taken: Full corrected SKILL.md text staged at `chapter_skill_updated.md` in the project root (not yet pasted into Settings > Capabilities — that step is manual and pending). The corrected version splits Mathematics into three quick-reference rows (preparatory/middle/secondary), fixes the prompt-path documentation to `{subject}/{stage}/`, adds all three Mathematics stage entries to the subject→prompt-file map, and adds an error guard for running the wrong stage's Mathematics prompt against a chapter.

Carry-forward rule: Any time a subject's folder structure becomes stage-split (adding `{stage}/` under `cowork prompts/{subject}/` or `mirror/constitutions/.../{subject}/`), the `chapter` skill's SKILL.md must be updated in the same change — it is not auto-derived from folder structure and will silently point at non-existent flat paths otherwise. Skill files cannot be edited from a Cowork session (read-only cache); stage replacement text must be drafted as a project file and the user must paste it via Settings > Capabilities. Mathematics secondary mirror data (chapter summaries + mappings) has not yet been generated — TASK.md's "Secondary Stage (IX)" table still shows Mathematics IX mirror at 0; running the pipeline is a separate, not-yet-executed step from authoring the prompts.

---

[Learning #30] — 2026-06-16 — chapter_skill_updated.md was incomplete: Science secondary and English secondary were both missing from the corrected draft

Context: while finalizing Learning #29's fix, the user asked "where is science secondary, english secondary in this? are you sure stages are properly covered?" — a direct, correct challenge. A full bash audit of the actual folder structure (`cowork prompts/`, `mirror/constitutions/competency_mapping/`, `mirror/framework/`) showed the first draft of `chapter_skill_updated.md` only fixed Mathematics and left two more pre-existing gaps unaddressed:
  - **Science** is stage-split on disk (`cowork prompts/science/middle/` AND `cowork prompts/science/secondary/`, each with step_1 + step_2, plus matching constitutions and framework folders) — but the draft skill still documented Science as flat/single-stage with no `{stage}/` segment in its path. Confirmed both stages use the IDENTICAL 4-signal effort-index formula and tiering tables (`conceptual_demand`, `activity_count`→`activity_load`, `demo_count`→`demo_load`, `exec_load`; `(CD×2)+(AL×2)+(DL×1.5)+(EL×2)`, range 2.0–19.0) — only the CG document, constitution, and source textbook folder differ between middle and secondary Science, unlike Mathematics where the formula itself changes per stage.
  - **English** is stage-split into all three stages (`preparatory/`, `middle/`, `secondary/`, each a single combined step_1_chapter_summary_and_mapping.md) — but the draft skill only documented preparatory and middle, omitting secondary's existence and path entirely.
  - **Social Sciences**, by contrast, really is flat and middle-only — no preparatory or secondary folder exists anywhere (prompts, constitutions, or framework). This matches TASK.md's note that Social Sciences IX/X is out of scope (no NCF-compliant secondary textbooks available). The flat treatment for Social Sciences was NOT a bug.
  - **TWAU** really is flat and preparatory-only — also not a bug.

Fix: rewrote `chapter_skill_updated.md` in full (not a patch) to: split Science into two quick-reference rows (middle/secondary) with shared-formula explanation in the Step 4 "Science note"; add English secondary as a third quick-reference row and to every relevant section (Step 1 plan-announcement example, Step 2 path map, Step 5 confirmation table); add explicit Step 0 constraints rejecting Science-for-preparatory and Social-Sciences-for-preparatory-or-secondary requests; add corresponding error guards. Re-verified via direct file reads of `cowork prompts/science/secondary/step_1_chapter_summary.md`, `step_2_effort_index.md`, and `cowork prompts/english/secondary/step_1_chapter_summary_and_mapping.md` (confirmed combined single-step pattern, same as English's other stages, with drama/transcript deltas that don't affect the skill's routing logic).

Carry-forward rule (sharpened from #29): when fixing a skill-documentation gap for ONE subject, always re-audit ALL subjects against the actual folder tree (`find` across `cowork prompts/`, `mirror/constitutions/`, `mirror/framework/`) before declaring the skill fixed — a gap found in one subject is a strong signal the same class of bug exists elsewhere and was never an isolated, subject-specific oversight. Do not trust the previous SKILL.md's structure as a checklist of "what subjects/stages exist" — it had already proven stale once (Mathematics) and was stale a second way (Science, English) in the same sitting.

---

[Learning #31] — 2026-06-18 — Mathematics Secondary Pipeline: First Live Chapter Run (Ch 7, Grade IX)

Context: First actual execution of the Mathematics secondary pipeline authored in Learning #29 — "Run chapter skill for chapter 7 mathematics grade IX." Since the `chapter` skill's SKILL.md paste-in was still pending (per #29/#30), the explicit prompt paths were used directly instead of invoking the Skill tool, exactly as TASK.md instructed.

What was run: Step 1 (`cowork prompts/mathematics/secondary/step_1_chapter_summary.md`) read the source PDF directly (`knowledge_commons/textbooks/mathematics/ix/chapter 07 - The Mathematics of Maybe-Introduction to Probability.pdf`) and wrote `mirror/chapters/mathematics/ix/summaries/ch_07_summary.json` — full section spine (7.1–7.4), 7 worked examples, 20 exercises (Q9–Q16 of the end-of-chapter set correctly excluded as starred), effort signals conceptual_demand=2, reasoning_load=1, exec_load=1. Step 2 (`step_2_competency_mapping.md`) read that summary plus the CG document and mapping constitution, and wrote `mirror/chapters/mathematics/ix/mappings/ch_07_mapping.json`: core_cg CG-6, core C-6.2 (probability applied to everyday likelihood), adjunct C-8.1 (representations — tables, tree diagrams, sample-to-population modelling), co_central false, effort_index 7.5 via `(2×2)+(1×2)+(1×1.5)`. Full verification checklist passed (CG validity, core/adjunct CG membership, counts, co_central consistency, dissolution_test content, effort signal match, formula arithmetic).

Observation: The pipeline as authored in #29 worked end-to-end on the first real chapter with no constitution ambiguity — the probability chapter mapped unambiguously to CG-6/C-6.2 with no competing core candidate (C-6.1, central tendency, simply doesn't appear in the chapter, so the single-core/no-co-central path was clean). Glob tool calls for locating the textbook PDF and prompt files intermittently returned "No files found" for paths that direct Read/Write calls on the same paths handled correctly — a session-specific Glob friction point, not a real path/data issue; subagent delegation resolved it without guessing paths.

Action taken: TASK.md's Secondary Stage (IX) table updated — Mathematics IX mirror now shows "1/8 ✅ (ch_07)" instead of "0 ❌", with a note identifying which chapter and its mapping result. Remaining 7 of 8 Mathematics IX chapters (1–6, 8) still need to be run.

Carry-forward rule: The Mathematics secondary pipeline (step_1 + step_2 + constitution) is now confirmed working in production, not just authored — future Mathematics IX chapter runs can proceed chapter-by-chapter via the explicit prompt paths with confidence the schema and formula are correct. The `chapter` skill SKILL.md paste-in (Settings > Capabilities) remains the one outstanding blocker to routing these requests through the skill instead of explicit paths — still pending as of this session.
