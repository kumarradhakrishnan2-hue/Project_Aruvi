# Claude Code — Plan Mode Prompt: TWAU Pipeline Implementation

## Context

Project Aruvi is an AI-powered lesson plan and assessment tool for Indian K–12 teachers, built on the Anthropic Claude API. It generates NCF-aligned lesson plans and assessments for CBSE Grades III–VIII. The tool is a Streamlit app (`aruvi_streamlit/app.py`). Lesson plan and assessment generation is driven by pre-computed "mirror" data (chapter summaries and competency mappings) and subject-specific runtime constitutions.

The project root is resolved dynamically via `aruvi_config.json` and `config_resolver.py`. Key paths:
- Mirror data: `mirror/chapters/{subject}/{grade}/summaries/` and `.../mappings/`
- Runtime constitutions: `mirror/constitutions/{type}/{subject}/`
- Framework files: `mirror/framework/{subject}/`
- Cowork prompts: `cowork prompts/{subject}/`
- Streamlit app: `aruvi_streamlit/app.py`

Four subjects are fully operational: `social_sciences`, `science`, `mathematics`, `english`. The task is to implement a fifth subject: **The World Around Us (TWAU)** — the EVS/integrated studies subject for Grades III, IV, and V.

A full design report has been produced and is at:
`TWAU_Aruvi_Design_Report_v2.docx`

This prompt supersedes the report where there are conflicts, incorporating final decisions made after the report was written. Read this prompt in full before entering plan mode.

---

## What already exists for TWAU

The following files are already in place and must NOT be modified:

- `mirror/framework/The World Around US/cg_twau.txt` — full CG framework text
- `mirror/framework/The World Around US/pedagogy_twau.txt` — TWAU pedagogy principles
- `mirror/framework/The World Around US/competency_descriptions_twau.json` — structured JSON of all 7 CGs and 22 C-codes (preferred reference for mapping; cleaner than `cg_twau.txt`)
- `mirror/chapters/The World Around Us/iii/`, `.../iv/`, `.../v/` — folder structure with empty `summaries/` and `mappings/` subdirectories
- `knowledge_commons/textbooks/The World Around Us/iii/`, `.../iv/`, `.../v/` — source chapter PDFs
- `TWAU_Aruvi_Design_Report_v2.docx` — design reference

Note: the framework folder uses `The World Around US` (capital S); the chapters/textbooks folders use `The World Around Us` (lowercase s). Both exist and must be preserved as-is.

---

## Architecture decisions (authoritative — follow exactly)

### A. Two-step pipeline — mirrors Social Sciences exactly

**Step 1** produces the chapter summary JSON. It does NOT contain any C-codes or competency assignments. Its sole purpose is grounded content extraction: what is in the chapter, what activities are present, what is the effort profile.

**Step 2** produces the competency mapping JSON. It reads the summary JSON and the CG framework, applies the TWAU mapping constitution using a two-pass approach (Pass 1: C-code-blind transformation inventory; Pass 2: architectural container matching to C-codes). C-codes are discovered through this process — they are not pre-assigned in Step 1.

This is identical to how `social_sciences` works. Do NOT follow the English pattern (combined step). Do NOT put `dominant_cg_codes` or any C-code field in the summary JSON.

The HTML LP and PDF draw CG codes from the mapping file at runtime, exactly as Social Sciences does.

### B. Chapter summary JSON schema

The summary is JSON format (same as mathematics and english — `.json` not `.txt`). Schema:

```json
{
  "chapter_number": 7,
  "chapter_title": "Solids, Liquids and Gases",
  "grade": "iv",
  "unit": "Unit 4: Things Around Us",
  "sections": [
    {
      "title": "Section heading exactly as in textbook",
      "content_summary": "2-4 sentences covering what the section teaches, key concepts, phenomena, examples.",
      "named_activities": ["Activity name 1", "Activity name 2"]
    }
  ],
  "activity_count": 6,
  "conceptual_demand": 3,
  "project_load": 0,
  "map_work": 0,
  "effort_index": 15.0,
  "dual_strand": {
    "natural": "Properties and states of matter",
    "human_cultural": "Traditional and everyday uses of solids, liquids, gases"
  }
}
```

No `dominant_cg_codes` field. No `chapter_weight` field (that belongs in the mapping JSON). No `indian_knowledge_element` field (IKS content is captured naturally within `section.content_summary` — it does not need a dedicated field).

Effort index formula:
`effort_index = (conceptual_demand × 3) + activity_count + (project_load × 1.5) + map_work`

- `conceptual_demand`: integer 1–5 (1 = concrete/Grade III, 5 = abstract/Grade V)
- `activity_count`: count of named hands-on activities across all sections
- `project_load`: 0 (none), 1 (light multi-day observation), 2 (substantial artefact construction)
- `map_work`: 0 (none), 1 (map reading), 2 (map drawing or regional comparison)

### C. Competency mapping JSON schema

```json
{
  "chapter_number": 7,
  "chapter_title": "Solids, Liquids and Gases",
  "grade": "iv",
  "stage": "foundational",
  "subject": "the_world_around_us",
  "effort_index": 15.0,
  "competencies": [
    {
      "cg": "CG-1",
      "c_code": "C-1.1",
      "competency_text": "exact text from competency_descriptions_twau.json",
      "weight": 1,
      "justification": "cites a named section/activity verifiably present in this chapter's summary"
    }
  ],
  "chapter_weight": 4
}
```

All competencies are Weight 1 — TWAU has a flattened weight structure (no dominant C-code, no Rule 4 equivalent). `chapter_weight` = count of active C-codes (since all are Weight 1, this equals the length of the competencies array). `effort_index` is copied from the summary JSON.

Grade-to-stage mapping: III → `"foundational"`, IV → `"foundational"`, V → `"foundational"`.

### D. Two-pass mapping constitution (TWAU-specific)

The mapping constitution for TWAU must implement the same two-pass discipline as Social Sciences:

**Pass 1 (C-code-blind):** Read the chapter summary section by section. For each named section, state: what cognitive transformation does this section require the student to perform, and on what content object? No C-codes are consulted during Pass 1. The CG document is prohibited until the inventory is complete.

**Pass 2 (architectural container matching):** Open the CG framework. For each transformation statement in the inventory, identify its architectural container (the named section or activity block), then match to a C-code only if the chapter's architecture compels the student to execute the specific operation the C-code defines.

**TWAU-specific departure from Social Sciences constitution:** No weight differentiation. All matched C-codes receive Weight 1. There is no Weight 3 / Weight 2 test. The two-pass discipline applies in full; only the weight assignment step is simplified.

**Reject:** any C-code match where the only connection is shared vocabulary (Learning #17 guard). Reject any match where a concept appears incidentally in a section whose primary subject is something else.

**Validate:** before writing the JSON, verify `chapter_title` matches the summary JSON's `chapter_title` exactly (Learning #15 guard).

### E. LP structure — single-axis (sections only)

The lesson plan is organized on a single axis: the textbook's named sections in reading order. Each period maps to one section (or part of a section for longer ones).

`dominant_mode` is **pedagogical approach metadata** on each period — not a structural axis. It does not drive the LP's organization. Values: `O&R` (Observe and Record), `HI` (Hands-on Investigation), `D&C` (Discussion and Connection), `C&E` (Create and Express), `R&A` (Reflect and Act). One dominant mode per period.

LP period JSON fields:
- `section_ref` — textbook section this period covers
- `dominant_mode` — one of the five values above
- `cg_codes` — array of C-codes active in this period (drawn from mapping JSON)
- `textbook_anchor` — named activity or section element from the textbook
- `implied_lo` — specific observable learning outcome for this period
- `teacher_facilitation_note` — brief note on facilitation approach

**No period caps.** Aruvi is suggestive — teachers decide actual period counts via the Allocate tab. The LP constitution must not impose a maximum number of periods per chapter.

**Activity rule (Option B):** One hands-on activity per period. Light discussion or reflection tasks may be paired only if they directly consolidate the main activity (same content, same outcome). The constitution enforces this — it does not impose a count cap.

**CG codes in HTML LP:** Must appear at period level, consistent with Social Sciences LP HTML rendering.

**No Rule 4 equivalent:** Social Sciences assigns proportionally greater emphasis to higher-weighted competencies. TWAU has no such rule — all C-codes at comparable depth. Section-level effort components drive period distribution, not C-code weights.

### F. Assessment architecture

**Quantity:** One assessment item per CG-strand per period. A period with `cg_codes: ["C-1.1", "C-4.4"]` generates two items, one anchored to each C-code.

**Question types:** Existing Aruvi taxonomy only — `MCQ`, `SCR`, `ECR`, `OPEN_TASK`. No new types.

Type guidance for TWAU:
- MCQ: CG-1 observation recognition, CG-5 map/directional, CG-4 conservation choices. Preferred for O&R and D&C periods.
- SCR: CG-2 cultural practices, CG-6 inquiry process steps. Preferred for HI periods.
- ECR: CG-3 wellbeing reasoning, CG-4 stewardship arguments. D&C periods with ethical/evaluative demand.
- OPEN_TASK: C&E and R&A dominant_mode periods. At Grade III, when content maps to a physical behaviour (hygiene routine, safety role-play), flag as `performance_task` subtype.

**`cognitive_demand` field:** Separate metadata field on every assessment item. Values: `Observe and Identify`, `Predict and Explain`, `Connect and Interpret`, `Evaluate and Choose`, `Design and Justify`. This is not a question type — it describes the cognitive demand the item makes.

**Teacher guide:** Same as all other Aruvi subjects (renamed "Notes" per Learning #23). No change to the guide pattern.

**Regional variation note:** When an assessment item asks for an example that is inherently region-specific (a crop, a festival, a water body, a food, a local practice), add a teacher note that regionally varied answers are acceptable. This is a constitution instruction applied conditionally — not a schema field on every item.

**Visual stimulus:** No new rendering branch. Existing pipe-table and SVG branches unchanged. TWAU assessment items are self-contained text-based questions.

### G. app.py changes

- Add `"the_world_around_us"` to `_JSON_SUMMARY_SUBJECTS` (JSON summary format).
- `grade_to_folder()` must handle grades `"iii"`, `"iv"`, `"v"` (lowercase Roman numerals, matching the existing folder structure).
- Add TWAU to the subject selector in the Generate tab and Allocate tab.
- Route TWAU through the JSON summary loading path.
- HTML LP renderer: display `cg_codes` at period level (same as SS); display `dominant_mode` as a period-level label; `dominant_mode` badge styling should be visually distinct from the CG code display.
- Assessment renderer: display `cognitive_demand` as metadata alongside `question_type` for each item.

---

## Deliverables

Plan and implement in this order:

1. **Cowork prompt: `cowork prompts/the_world_around_us/step_1_chapter_summary.md`**
   Reads one or more chapter PDFs from `knowledge_commons/textbooks/The World Around Us/{grade}/`. Writes summary JSON to `mirror/chapters/The World Around Us/{grade}/summaries/ch_NN_summary.json`. No C-codes. No API call (Cowork reads PDF directly). Follows the schema in §B above. Verification line after each chapter.

2. **Cowork prompt: `cowork prompts/the_world_around_us/step_2_competency_mapping.md`**
   Reads summary JSON + `mirror/framework/The World Around US/competency_descriptions_twau.json`. Applies two-pass mapping discipline (§D). Writes mapping JSON to `mirror/chapters/The World Around Us/{grade}/mappings/ch_NN_mapping.json`. Uses schema in §C. No C-codes in summary; C-codes discovered here. Verification line after each chapter.

3. **TWAU mapping constitution: `mirror/constitutions/competency_mapping/the_world_around_us/mapping_constitution_twau.txt`**
   Formal constitution document encoding the two-pass rules for TWAU, the flattened Weight 1 structure, the Learning #15 and #17 guards, and the prohibited-documents list. Model this on the Social Sciences mapping constitution — adapt Rules 1, 2, 3 (Pass 1/2/vocabulary-rejection) directly; replace Rules 4–8 (weight differentiation) with the simplified Weight 1 rule.

4. **TWAU LP constitution: `mirror/constitutions/lesson_plan/the_world_around_us/lp_constitution_twau.txt`**
   Single-axis LP (sections in reading order). Period fields per §E. dominant_mode as metadata. Option B activity rule. No period caps. CG codes at period level. Regional-variation constitution instruction. Grade III performance_task subtype guidance.

5. **TWAU assessment constitution: `mirror/constitutions/assessment/the_world_around_us/assessment_constitution_twau.txt`**
   One item per CG-strand per period. MCQ/SCR/ECR/OPEN_TASK taxonomy. `cognitive_demand` field on every item. Regional-variation note as conditional instruction. Teacher guide (Notes) consistent with existing subjects. Grade III performance_task subtype for behavioural OPEN_TASKs.

6. **app.py changes** per §G. Wire TWAU into the Generate and Allocate tabs. HTML LP renderer updates (cg_codes at period level, dominant_mode badge). Assessment renderer update (cognitive_demand display).

7. **Pilot run:** Generate a complete LP + assessment for one chapter (suggested: Grade IV Ch 7 — Solids, Liquids and Gases) using the new pipeline. Verify HTML and PDF output. Check CG codes appear at period level in HTML LP. Check cognitive_demand appears on assessment items. Check activity rule is observed (one hands-on per period). Check no regional-variation note appears on items that don't need it.

---

## Key learnings to carry forward (from MEMORY.md)

- **Learning #15:** Before writing mapping JSON, verify `chapter_title` in the JSON exactly matches the first-line title in the source summary. A mismatch is a silent error.
- **Learning #17:** A C-code match requires the cognitive operation the C-code demands to be performed on the primary subject of a named structural element — not incidental mention within a section whose primary subject is something else. Vocabulary matches must be rejected.
- **Learning #2:** Anchor all generation strictly to the chapter summary content. Do not supplement from training knowledge.
- **Learning #26:** If thin content sections cause assessment contamination from question_bank or tasks_verbatim fields, strip those fields before building the assessment prompt. Monitor on first pilot run — TWAU content is generally richer than Grade V English poems, so risk is lower, but watch for it.
- **CG-3 watch item:** Grade III chapters with safety/hygiene content (Ch 9 Staying Healthy and Happy) are CG-3 dominant. Trust the two-pass mapping to flag CG-3 naturally. Flag for manual review on first Grade III pilot run if CG-3 appears under-assigned.

---

## What this task does NOT include

- No changes to Science, Social Sciences, Mathematics, or English pipelines.
- No new visual_stimulus rendering branch.
- No `indian_knowledge_element` schema field anywhere.
- No competency weights above 1 for TWAU.
- No period caps.
- No combined Step 1+2 prompt (keep steps separate).
