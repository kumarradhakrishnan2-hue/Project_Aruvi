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

