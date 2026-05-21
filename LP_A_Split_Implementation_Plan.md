# Aruvi — LP / Assessment Split: Implementation Plan for Claude Code

**Date:** 2026-05-21  
**Scope:** Two-stage generation — LP first, Assessment on demand (deferred or inline at inception)  
**File primarily changed:** `aruvi_streamlit/app.py`  
**Constitution already changed:** `mirror/constitutions/lesson_plan/science/lesson_plan_constitution.txt` (v2.1) and `mirror/constitutions/assessment/science/assessment_constitution.txt` (v1.2) — `coverage_handoff` rename done. No further constitution changes needed.

---

## Design summary (carry this into every sub-task)

- **Default:** Generate button produces LP only. No assessment generated or charged.
- **Opt-in at inception:** A confirmation dialog (shown when Generate is clicked) lets the teacher also opt in for Assessment in the same run.
- **Deferred assessment:** If teacher skips assessment at inception, the My Plans row shows a **"Generate Assessment"** button instead of "PDF ⬇" in the Assessment column. Clicking it invokes `generate_assessment_only()` directly — no further confirmation, no parameter re-entry. The tracking window shows the inputs being consumed.
- **After deferred assessment completes:** The saved plan is updated on disk (`assessment_items` populated, `plan_status` set to `"full_lpa"`), and the My Plans row switches to **"PDF ⬇"** (download) in the Assessment column.
- **Saved plan schema:** A new field `plan_status` (`"lp_only"` | `"full_lpa"`) is added to every saved plan. All existing saved plans are treated as `"full_lpa"` at read time (backwards-compatible default).
- **Caching:** The LP-only run's prompt caching structure is unchanged — constitutions in system, pedagogy in static user block, summary + mapping in variable block. The Assessment-only run has its own cache structure (see §4).
- **My Plans display:** Assessment column shows "PDF ⬇" if `plan_status == "full_lpa"`, else "Generate Assessment" button.

---

## §1 — `save_plan()` schema change

**File:** `app.py` lines 461–499  
**What to change:** Add `plan_status` field to the saved payload.

```python
# BEFORE (line ~490 area):
"result": {
    "lesson_plan":      result.get("lesson_plan", {}),
    "coverage_handoff": result.get("coverage_handoff", {}),
    "assessment_items": result.get("assessment_items", []),
    "input_tokens":     result.get("input_tokens", 0),
    "output_tokens":    result.get("output_tokens", 0),
    "cost_inr":         result.get("cost_inr", 0),
},

# AFTER:
"plan_status": result.get("plan_status", "full_lpa"),  # new top-level field
"result": {
    "lesson_plan":      result.get("lesson_plan", {}),
    "coverage_handoff": result.get("coverage_handoff", {}),
    "assessment_items": result.get("assessment_items", []),
    "input_tokens":     result.get("input_tokens", 0),
    "output_tokens":    result.get("output_tokens", 0),
    "cost_inr":         result.get("cost_inr", 0),
    # assessment run tokens stored separately so LP and A costs are auditable
    "assess_input_tokens":  result.get("assess_input_tokens", 0),
    "assess_output_tokens": result.get("assess_output_tokens", 0),
    "assess_cost_inr":      result.get("assess_cost_inr", 0.0),
},
```

`plan_status` is a **top-level** key (not inside `result`) so it can be read cheaply from the My Plans list without unpacking the full result dict.

**Backwards compatibility:** When loading saved plans, wherever `plan_status` is read, default to `"full_lpa"` if the key is absent. This covers all existing saved plans.

---

## §2 — `generate_lpa()` split into two functions

**File:** `app.py` — rename and add function, starting around line 730.

### 2a — Rename `generate_lpa` → `generate_lp_only()`

The existing function is restructured to:
- Accept a new parameter: `include_assessment: bool = False`
- When `include_assessment=False`: remove `assessment_items` from the output schema instruction in `_variable_user_text` and remove the assessment constitution from the system prompt.
- When `include_assessment=True`: behave exactly as today (full LPA run — constitutions + assessment items in one pass).
- Set `plan_status` in the returned result dict: `"full_lpa"` if assessment was included, `"lp_only"` otherwise.
- `assessment_items` in the returned dict is `[]` when LP-only.

**Specific change in the output schema instruction** (`_variable_user_text`, lines ~810–827):

```python
# LP-only output schema (include_assessment=False):
_output_schema = f"""{{
  "grade": "{grade}",
  "subject": "{subject}",
  "chapter_number": {chapter["chapter_number"]},
  "chapter_title": "{chapter.get('chapter_title', '')}",
  "period_schedule": <derived from teacher period schedule above>,
  "lesson_plan": {{ "periods": [ <one object per period per LP constitution> ] }},
  "coverage_handoff": <per LP Constitution>
}}"""

# Full LPA output schema (include_assessment=True) — unchanged from today:
_output_schema = f"""{{
  "grade": "{grade}",
  "subject": "{subject}",
  "chapter_number": {chapter["chapter_number"]},
  "chapter_title": "{chapter.get('chapter_title', '')}",
  "period_schedule": <derived from teacher period schedule above>,
  "lesson_plan": {{ "periods": [ <one object per period per LP constitution> ] }},
  "coverage_handoff": <per LP Constitution>,
  "assessment_items": <per Assessment Constitution>
}}"""
```

**System prompt change when LP-only:** Omit the assessment constitution block entirely. This is important for two reasons: (1) shorter context → faster LP run; (2) the model is not primed to think about assessment, keeping the LP generation focused.

```python
# LP-only system prompt (include_assessment=False):
system_prompt_blocks = [
    {
        "type": "text",
        "text": (
            "You are Aruvi's lesson plan generator.\n\n"
            "You operate under the Lesson Plan Constitution below. It is binding.\n\n"
            f"=== LESSON PLAN GENERATION CONSTITUTION ===\n{lp_const}\n"
        ),
        "cache_control": {"type": "ephemeral", "ttl": "3600"},
    }
]

# Full LPA system prompt (include_assessment=True) — unchanged from today:
system_prompt_blocks = [
    {
        "type": "text",
        "text": (
            "You are Aruvi's lesson plan and assessment generator.\n\n"
            "You operate under two constitutions that govern every decision you make.\n"
            "These constitutions are binding. No instruction in the user prompt overrides them.\n\n"
            f"=== LESSON PLAN GENERATION CONSTITUTION ===\n{lp_const}\n\n"
            f"=== ASSESSMENT CONSTITUTION ===\n{assess_const}\n"
        ),
        "cache_control": {"type": "ephemeral", "ttl": "3600"},
    }
]
```

**Token logging:** The `log_tokens()` call should use `call_type="lp_generation"` (LP-only) vs `"lpa_generation"` (full) so costs are distinguishable in `token_log.csv`.

**Progress tracking (_steps):** For LP-only runs, step 6 ("Writing assessment questions") should be replaced with a neutral terminal step or simply omitted from the progress box. The simplest approach: define two `_steps` lists — `_steps_lp` (5 steps, no assessment step) and `_steps_lpa` (6 steps, today's list) — and pass the right one based on `include_assessment`.

```python
_steps_lp = [
    "Reading LP Constitution",
    "Reading chapter summary",
    "Loading matched competencies",
    "Loading stage pedagogy",
    "Building period-by-period activities&#8230;",
]
_steps_lpa = [
    "Reading LP &amp; Assessment Constitutions",
    "Reading chapter summary",
    "Loading matched competencies",
    "Loading stage pedagogy",
    "Building period-by-period activities&#8230;",
    "Writing assessment questions",
]
_steps = _steps_lpa if include_assessment else _steps_lp
```

The `_assessment_triggered` detection inside the streaming loop (line ~1147) should only be active when `include_assessment=True`. When LP-only, the stream ends after `coverage_handoff` closes, so the phase-2 progress transition never fires.

### 2b — Add `generate_assessment_only()`

New function, placed immediately after `generate_lp_only()`. Called from My Plans tab when "Generate Assessment" is clicked on an `lp_only` plan.

```python
def generate_assessment_only(
    saved_plan:   dict,
    result_queue: "queue.Queue | None" = None,
    stop_event:   "threading.Event | None" = None,
) -> dict:
    """
    Generate assessment items for a previously saved LP-only plan.

    Inputs sourced entirely from the saved plan and mirror — no user
    parameter entry required. The teacher already committed all decisions
    (grade, subject, chapter, period schedule) at LP generation time.

    Inputs to the assessment constitution:
      - coverage_handoff: saved_plan["result"]["coverage_handoff"]
      - chapter_summary:  read from mirror (same path logic as generate_lp_only)

    Returns a result dict with:
      assessment_items, assess_input_tokens, assess_output_tokens, assess_cost_inr
    """
```

**Implementation details:**

1. Extract metadata from `saved_plan`: `grade`, `subject`, `chapter_number`, `chapter_title`.
2. Resolve paths via `resolve_paths(grade, subject, chapter_number)`.
3. Read `coverage_handoff` from `saved_plan["result"]["coverage_handoff"]`.
4. Read `chapter_summary` from mirror (already pre-computed).
5. Read `assess_const` from `paths["assessment_const"]`.

**Prompt structure (caching-aware):**

```python
# System — assessment constitution only (cacheable across chapters of same subject)
system_prompt_blocks = [
    {
        "type": "text",
        "text": (
            "You are Aruvi's assessment generator.\n\n"
            "You operate under the Assessment Constitution below. It is binding.\n\n"
            f"=== ASSESSMENT CONSTITUTION ===\n{assess_const}\n"
        ),
        "cache_control": {"type": "ephemeral", "ttl": "3600"},
    }
]

# Static user — chapter summary (cacheable per chapter, changes only per chapter)
_static_user_text = f"=== CHAPTER SUMMARY ===\n{summary}\n"

# Variable user — coverage_handoff + output instruction (changes per run)
_variable_user_text = f"""Generate the chapter assessment using the inputs below.

=== COVERAGE HANDOFF ===
{json.dumps(coverage_handoff, ensure_ascii=False, indent=2)}

=== INSTRUCTIONS ===
Follow the Assessment Constitution exactly.
The coverage_handoff above is your sole structural input. Ground every question
in it. Do not re-derive stage structure from the chapter summary.

Produce your entire output as a single valid JSON object:
{{
  "assessment_items": <per Assessment Constitution>
}}

Output only the raw JSON object. No markdown. No prose. No ```json fences.
"""

user_message_blocks = [
    {
        "type": "text",
        "text": _static_user_text,
        "cache_control": {"type": "ephemeral", "ttl": "3600"},
    },
    {
        "type": "text",
        "text": _variable_user_text,
    },
]
```

**Why this caching structure:** The assessment constitution is stable per subject (cache hit across all chapters). The chapter summary is stable per chapter (cache hit if the same teacher re-runs assessment for the same chapter). The `coverage_handoff` is unique per run and goes in the variable block.

**Progress tracking for deferred assessment:** Use a 3-step tracking window (not the full 6-step LP window):

```python
_steps_assess = [
    "Reading Assessment Constitution",
    "Reading chapter summary",
    "Writing assessment questions&#8230;",
]
```

The tracking window header should read: **"Generating assessment…"** and show the inputs at the top:
- Grade · Subject · Chapter title · Periods (from `saved_plan["period_schedule_display"]`)

This satisfies the requirement: *"the tracking window should now show inputs being used for A."*

**Token logging:** `call_type="assessment_generation_deferred"` to distinguish from inline assessment.

**Return dict:**
```python
{
    "assessment_items":       [...],
    "assess_input_tokens":    N,
    "assess_output_tokens":   N,
    "assess_cost_inr":        X,
}
```

**After completion:** The caller (My Plans tab) must:
1. Update the saved plan JSON on disk: merge `assessment_items` into `saved_plan["result"]`, set `saved_plan["plan_status"] = "full_lpa"`, update `assess_*` token fields.
2. Update `st.session_state` so the My Plans row re-renders with the PDF button.

A helper function `update_saved_plan_with_assessment(filename, grade, subject, assess_result)` should be added near `save_plan()` to handle the disk write atomically.

---

## §3 — Generate tab UI changes

**File:** `app.py` — Generate tab section starting ~line 4369.

### 3a — Replace the Generate button with a two-step confirmation dialog

**Current flow:** Teacher clicks "Generate Lesson Plan & Assessment" → `lpa_generating = True` → rerun → generation starts.

**New flow:**

1. Button label changes to **"Generate Lesson Plan"** (primary button, same location).
2. On click: instead of immediately setting `lpa_generating = True`, set `st.session_state.show_gen_confirm = True` and rerun.
3. A confirmation dialog renders (using `st.container` with border styling, same pattern as the existing save-prompt box at line ~4700):

```
┌─────────────────────────────────────────────────┐
│  Ready to generate                              │
│                                                 │
│  Grade VII · Science · Ch 02 · 7 periods        │
│                                                 │
│  [ ] Include Assessment                         │
│      Assessment can also be generated later     │
│      from My Plans at no extra inconvenience.   │
│                                                 │
│           [Generate]      [Cancel]              │
└─────────────────────────────────────────────────┘
```

Use `st.checkbox("Include Assessment", key="gen_confirm_include_assess", value=False)` for the opt-in.

4. On **Generate** click inside the dialog:
   - Read `include_assessment = st.session_state.get("gen_confirm_include_assess", False)`
   - Set `st.session_state.lpa_generating = True`
   - Set `st.session_state.gen_include_assessment = include_assessment`
   - Set `st.session_state.show_gen_confirm = False`
   - Rerun.

5. On **Cancel**: set `show_gen_confirm = False`, rerun.

### 3b — Pass `include_assessment` into the generation thread

Around line 4562–4577, the `threading.Thread` call must pass the new parameter:

```python
_t = threading.Thread(
    target=generate_lp_only,   # renamed from generate_lpa
    kwargs=dict(
        grade              = st.session_state.grade,
        subject            = st.session_state.subject,
        chapter            = selected_ch,
        period_rows        = st.session_state.get("period_rows", [0]),
        session            = st.session_state,
        include_assessment = st.session_state.get("gen_include_assessment", False),
        result_queue       = _rq,
        stop_event         = _stop_ev,
    ),
    daemon=True,
)
```

### 3c — Post-generation button bar (lines ~4761–4810)

**Current:** 4 buttons — "Lesson plan ⬇", "Assessment ⬇", "Save to my plans", "Clear"

**New (LP-only result):**
- Column 1: "Lesson plan ⬇" — unchanged
- Column 2: ~~"Assessment ⬇"~~ → **absent** (or greyed out placeholder, not a download button)
- Column 3: "Save to my plans" — unchanged in behaviour, but now saves with `plan_status="lp_only"`
- Column 4: "Clear" — unchanged

**New (full LPA result):**
- All 4 buttons exactly as today. `plan_status="full_lpa"`.

Logic: check `result.get("plan_status", "full_lpa") == "lp_only"` to decide whether to render the Assessment download button.

The save-prompt popup (line ~4700) needs no change — it already fires after any generation and saves whatever is in `result`.

---

## §4 — My Plans tab UI changes

**File:** `app.py` — My Plans section starting ~line 5248.

### 4a — Saved plan status detection

When iterating `_visible` plans (line ~5445), read `plan_status`:

```python
_plan_status = _p.get("plan_status", "full_lpa")  # default full_lpa for old plans
_has_assessment = (_plan_status == "full_lpa")
```

### 4b — Assessment column rendering (line ~5506–5514)

**Current:** Always renders a `st.download_button("PDF ⬇", ...)` in the Assessment column.

**New:**

```python
with _rc[5]:
    if _has_assessment:
        # existing download button — unchanged
        st.download_button(
            label="PDF ⬇",
            data=_mp_assess_bytes if _mp_assess_bytes else b"",
            file_name=f"Aruvi_{_safe_t}_Assessment.pdf",
            mime="application/pdf",
            key=f"mp_assess_{_safe_fn}",
            type="primary",
        )
    else:
        # Deferred assessment button
        if st.button(
            "Generate Assessment",
            key=f"mp_gen_assess_{_safe_fn}",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state.mp_deferred_assess_plan = _p
            st.session_state.mp_deferred_assess_generating = True
            st.rerun()
```

### 4c — Deferred assessment generation block

Add a new block at the top of the My Plans workspace section (before the plan list renders), so it takes over the workspace when a deferred generation is running:

```python
if st.session_state.get("mp_deferred_assess_generating") and \
   st.session_state.get("mp_deferred_assess_plan") is not None:

    _dap = st.session_state.mp_deferred_assess_plan

    # Show inputs being used (satisfies the tracking window requirement)
    st.markdown(
        f'<div style="font-size:0.82rem;color:#5a5754;margin-bottom:0.5rem;">'
        f'Generating assessment for: <strong>{_dap["chapter_title"]}</strong> · '
        f'{_dap["grade"]} · {_dap["subject"]} · '
        f'{_dap.get("period_schedule_display","")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Launch background thread for generate_assessment_only()
    _existing_da_thread = st.session_state.get("mp_da_thread")
    if (_existing_da_thread is not None and _existing_da_thread.is_alive()
            and st.session_state.mp_da_result_queue is not None):
        _da_stop_ev = st.session_state.mp_da_stop_event
        _da_rq      = st.session_state.mp_da_result_queue
    else:
        _da_stop_ev = threading.Event()
        _da_rq      = queue.Queue()
        st.session_state.mp_da_stop_event   = _da_stop_ev
        st.session_state.mp_da_result_queue = _da_rq
        _da_t = threading.Thread(
            target=generate_assessment_only,
            kwargs=dict(
                saved_plan   = _dap,
                result_queue = _da_rq,
                stop_event   = _da_stop_ev,
            ),
            daemon=True,
        )
        add_script_run_ctx(_da_t)
        _da_t.start()
        st.session_state.mp_da_thread = _da_t

    # Poll with heartbeat (same pattern as Generate tab)
    _da_heartbeat = st.empty()
    _da_result = None
    while _da_result is None:
        try:
            _da_result = _da_rq.get(timeout=0.25)
        except queue.Empty:
            _da_heartbeat.markdown("")
    _da_heartbeat.empty()

    st.session_state.mp_da_thread       = None
    st.session_state.mp_da_stop_event   = None
    st.session_state.mp_da_result_queue = None

    if not _da_result.get("stopped") and _da_result.get("assessment_items"):
        # Write updated plan to disk
        update_saved_plan_with_assessment(
            filename     = _dap["filename"],
            grade        = _dap["grade"],
            subject      = _dap["subject"],
            assess_result = _da_result,
        )

    st.session_state.mp_deferred_assess_generating = False
    st.session_state.mp_deferred_assess_plan       = None
    st.rerun()
```

### 4d — `update_saved_plan_with_assessment()` helper

Add near `save_plan()` (~line 500):

```python
def update_saved_plan_with_assessment(
    filename:      str,
    grade:         str,
    subject:       str,
    assess_result: dict,
) -> None:
    """
    Merge completed assessment items into an existing lp_only saved plan.
    Overwrites the file in place. Idempotent — safe to call twice.
    """
    d    = _saved_plans_dir(grade, subject)
    path = d / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return  # file gone — silently skip

    payload["plan_status"] = "full_lpa"
    payload["result"]["assessment_items"]    = assess_result.get("assessment_items", [])
    payload["result"]["assess_input_tokens"] = assess_result.get("assess_input_tokens", 0)
    payload["result"]["assess_output_tokens"]= assess_result.get("assess_output_tokens", 0)
    payload["result"]["assess_cost_inr"]     = assess_result.get("assess_cost_inr", 0.0)

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

---

## §5 — Session state additions

Add these to the session state initialisation block (wherever `lpa_generating`, `lpa_result`, etc. are initialised — around line ~2541 area):

```python
# LP/A split
if "gen_include_assessment"          not in st.session_state: st.session_state.gen_include_assessment          = False
if "show_gen_confirm"                not in st.session_state: st.session_state.show_gen_confirm                = False
# Deferred assessment (My Plans)
if "mp_deferred_assess_generating"   not in st.session_state: st.session_state.mp_deferred_assess_generating   = False
if "mp_deferred_assess_plan"         not in st.session_state: st.session_state.mp_deferred_assess_plan         = None
if "mp_da_thread"                    not in st.session_state: st.session_state.mp_da_thread                    = None
if "mp_da_stop_event"                not in st.session_state: st.session_state.mp_da_stop_event                = None
if "mp_da_result_queue"              not in st.session_state: st.session_state.mp_da_result_queue              = None
```

---

## §6 — Token log changes

**File:** `knowledge_commons/evaluation_mappings/token_log.csv`  
**No schema change required.** The `call_type` column already distinguishes runs. New `call_type` values to use:
- `"lp_generation"` — LP-only run
- `"lpa_generation"` — LP + Assessment inline (unchanged, already in use)
- `"assessment_generation_deferred"` — Assessment-only deferred run

The deferred assessment `log_tokens()` call uses the same fields as today. The cost is logged separately so the teacher's total cost per chapter is the sum of both entries in the CSV.

---

## §7 — English subject path

**File:** `app.py` — `_build_lpa_prompts_english()` function (~line 519).

This function currently builds both LP and assessment prompts together and returns `(system_prompt_blocks, user_message_blocks)`. It needs the same split:

- Add `include_assessment: bool = False` parameter.
- When `False`: return system + user blocks that produce LP + `coverage_handoff` only (no `assessment_items` in output schema).
- When `True`: current behaviour unchanged.
- The call site in `generate_lp_only()` (the English dispatch branch, ~line 757) passes `include_assessment` through.

---

## §8 — Sequence of implementation steps for Claude Code

Follow this order strictly — each step is independently testable.

**Step 1 — Schema and helpers (no UI change)**
- Add `plan_status` to `save_plan()` payload.
- Add `update_saved_plan_with_assessment()` function.
- Add session state keys.
- Verify: run app, generate a plan, save it, inspect the JSON — confirm `plan_status: "full_lpa"` is present.

**Step 2 — Split `generate_lpa()` into `generate_lp_only()`**
- Rename function.
- Add `include_assessment` parameter (default `False`).
- Branch system prompt (LP-only vs full).
- Branch output schema instruction.
- Branch `_steps` list.
- Branch `call_type` in `log_tokens()`.
- Branch `plan_status` in returned result dict.
- Update the thread spawn in Generate tab to call `generate_lp_only` with `include_assessment=st.session_state.get("gen_include_assessment", False)`.
- Set `include_assessment=True` as the default for now (so the app behaves identically to today while you validate the refactor).
- Verify: full LPA run produces same output as before. LP-only run produces LP + coverage_handoff, no assessment_items, plan_status="lp_only".

**Step 3 — `generate_assessment_only()` function**
- Implement as specified in §2b.
- Unit test in isolation (call directly, pass a saved plan dict, confirm assessment_items are returned).
- Verify: deferred assessment for a Science chapter returns valid assessment_items grounded in the coverage_handoff.

**Step 4 — Generate tab confirmation dialog**
- Replace button handler with `show_gen_confirm = True`.
- Add the confirmation container with checkbox.
- Wire Generate / Cancel buttons.
- Verify: dialog appears, checkbox defaults to unchecked, Generate with checkbox off produces lp_only plan, Generate with checkbox on produces full_lpa plan.

**Step 5 — Generate tab post-generation button bar**
- Conditionally hide/show Assessment download button based on `plan_status`.
- Verify: LP-only result shows no Assessment download; full LPA shows it.

**Step 6 — My Plans tab Assessment column**
- Add `plan_status` detection.
- Render "Generate Assessment" button for lp_only plans.
- Wire button to `mp_deferred_assess_generating = True`.
- Verify: existing full_lpa plans show PDF ⬇; lp_only plans show Generate Assessment.

**Step 7 — Deferred assessment generation block in My Plans**
- Add the generation block at top of My Plans workspace.
- Wire thread spawn, heartbeat poll, result handling.
- Wire `update_saved_plan_with_assessment()` on success.
- Verify: clicking "Generate Assessment" in My Plans runs the generation, updates the JSON on disk, and re-renders the row with PDF ⬇.

**Step 8 — English path (`_build_lpa_prompts_english`)**
- Add `include_assessment` parameter and branch.
- Verify: English LP-only run produces LP + coverage_handoff, no assessment_items.

**Step 9 — Final integration test**
- Full flow: generate LP only → save → My Plans shows "Generate Assessment" → click → assessment generated → My Plans shows PDF ⬇ → download works.
- Full flow: generate LP + Assessment at inception → My Plans shows PDF ⬇ immediately.
- Old saved plans (no plan_status key): treated as full_lpa, PDF ⬇ shown in My Plans — no regression.

---

## §9 — Things NOT to change

- `_normalise_lo_handoff()` — untouched. Handles old and new saved plan shapes already.
- `_normalise_assessment_sections()` — untouched.
- `lpa_page.html` — untouched. The HTML viewer renders whatever lo_handoff / assessment_sections are passed to it; empty assessment_sections renders gracefully (or can be hidden — check existing behaviour).
- `lp_pdf_generator.py` — untouched.
- `assessment_pdf_generator.py` — untouched.
- Allocate tab — untouched.
- Ask Aruvi — untouched.
- All mirror data (summaries, mappings, constitutions) — untouched except the Science constitutions already amended.

---

## §10 — Edge cases to handle

| Scenario | Handling |
|---|---|
| Teacher clicks "Generate Assessment" in My Plans but `coverage_handoff` is empty in the saved plan | Show an inline error: "Assessment cannot be generated — this plan was saved before coverage handoff was introduced. Please regenerate the lesson plan." Do not attempt the API call. |
| Deferred assessment API call fails (JSON parse error) | Show error inline in My Plans workspace. Do not update the saved plan. `plan_status` remains `"lp_only"`. Teacher can retry. |
| Teacher stops deferred assessment mid-run | Same stop-event pattern as Generate tab. On stop: reset `mp_deferred_assess_generating = False`, do not update saved plan. Button reverts to "Generate Assessment". |
| Old saved plans (pre-split, no `plan_status`) | Read-time default: `plan_status = "full_lpa"`. These all have `assessment_items` populated, so PDF download works correctly. |
| LP-only plan viewed in My Plans detail view | `_normalise_assessment_sections()` returns empty list for empty `assessment_items`. The lpa_page.html assessment tab should show "Assessment not yet generated" or simply be empty — verify current graceful-empty behaviour and add a note if needed. |
