#!/usr/bin/env python3
"""Standalone A/B harness — generate an Aruvi lesson plan + assessment as raw
JSON via the OpenAI API (or Claude, for a baseline), using the SAME
constitutions / pedagogy / summary / mapping the Streamlit app feeds the model.

It reproduces app.py's GENERIC prompt assembly verbatim (Science, Social
Sciences, Mathematics, The World Around Us). English uses a different builder
in app.py and is intentionally rejected here. Anthropic content-blocks are
flattened to plain strings — the only thing dropped is the cache_control tags,
which do not change the text the model sees, so the comparison is honest.

No HTML. Output is the raw JSON the model returns, written to disk, plus a quick
validity report (does it parse? do the top-level keys match what the renderer
expects?) so you can see mode-1 (invalid JSON) vs mode-2 (valid but wrong shape)
failures at a glance.

Usage:
  export OPENAI_API_KEY=sk-...
  pip install openai            # SDK is not currently installed
  python3 gpt_lpa_test.py --subject science --grade vii --chapter 2 \
          --periods 5 --minutes 40 --model gpt-4o

  # Baseline from Claude on the identical flattened prompt:
  python3 gpt_lpa_test.py --subject science --grade vii --chapter 2 \
          --provider anthropic --model claude-sonnet-4-6
"""

import argparse
import json
import sys
from pathlib import Path

# Repo root = parent of this script's folder (aruvi-scripts/ sits at the root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIRROR = PROJECT_ROOT / "mirror"

# Load .env (same file the app uses) so OPENAI_API_KEY / ANTHROPIC_API_KEY are
# picked up automatically — no need to re-export each session.
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

_STAGES = {
    "iii": "preparatory", "iv": "preparatory", "v": "preparatory",
    "vi": "middle", "vii": "middle", "viii": "middle",
    "ix": "secondary", "x": "secondary",
}
_GRADE_DISPLAY = {
    "iii": "Grade III", "iv": "Grade IV", "v": "Grade V", "vi": "Grade VI",
    "vii": "Grade VII", "viii": "Grade VIII", "ix": "Grade IX", "x": "Grade X",
}
_SUBJECT_DISPLAY = {
    "science": "Science", "social_sciences": "Social Science",
    "mathematics": "Mathematics", "the_world_around_us": "The World Around Us",
}
_JSON_SUMMARY_SUBJECTS = {"mathematics", "the_world_around_us"}  # english excluded here
_EXPECTED_TOP_KEYS = {
    "grade", "subject", "chapter_number", "chapter_title",
    "period_schedule", "lesson_plan", "coverage_handoff", "assessment_items",
}


def _require(path: Path, label: str) -> str:
    """Read a required mirror file; hard-fail loudly if it is missing so we
    never send the model a prompt with a [FILE NOT FOUND] hole in it."""
    if not path.exists():
        sys.exit(f"ERROR: missing {label}: {path}")
    return path.read_text(encoding="utf-8")


def resolve_paths(subject: str, grade: str, chapter: int, stage: str) -> dict:
    """Mirror of app.resolve_paths — stage-routed constitution, flat fallback."""
    nn = f"{chapter:02d}"
    lp_staged = MIRROR / f"constitutions/lesson_plan/{subject}/{stage}/lesson_plan_constitution.txt"
    lp_flat   = MIRROR / f"constitutions/lesson_plan/{subject}/lesson_plan_constitution.txt"
    ac_staged = MIRROR / f"constitutions/assessment/{subject}/{stage}/assessment_constitution.txt"
    ac_flat   = MIRROR / f"constitutions/assessment/{subject}/assessment_constitution.txt"
    summary_ext = "json" if subject in _JSON_SUMMARY_SUBJECTS else "txt"
    return {
        "lp_constitution":  lp_staged if lp_staged.exists() else lp_flat,
        "assessment_const": ac_staged if ac_staged.exists() else ac_flat,
        "pedagogy":         MIRROR / f"framework/{subject}/{stage}/pedagogy_{stage}_{subject}.txt",
        "chapter_summary":  MIRROR / f"chapters/{subject}/{grade}/summaries/ch_{nn}_summary.{summary_ext}",
        "chapter_mapping":  MIRROR / f"chapters/{subject}/{grade}/mappings/ch_{nn}_mapping.json",
    }


def format_period_schedule(rows) -> str:
    """rows: list of (duration_minutes, count). Reproduces app.format_period_schedule."""
    lines = []
    total_periods = 0
    total_minutes = 0
    for i, (dur, cnt) in enumerate(rows):
        total_periods += cnt
        total_minutes += dur * cnt
        lines.append(
            f"  Row {i+1}: {dur} minutes × {cnt} period{'s' if cnt != 1 else ''} = {dur*cnt} minutes"
        )
    h, m = divmod(total_minutes, 60)
    time_str = f"{h}h {m}min" if h > 0 else f"{m} minutes"
    return "Period schedule:\n" + "\n".join(lines) + f"\nTotal: {total_periods} periods · {time_str}"


def build_prompt(subject_disp, grade_disp, chapter_no, chapter_title,
                 lp_const, assess_const, pedagogy, summary, mapping_raw,
                 period_sched, include_assessment):
    """Verbatim reproduction of app.py's generic system/user assembly,
    flattened to two plain strings (system, user)."""
    if include_assessment:
        system_text = (
            "You are Aruvi's lesson plan and assessment generator.\n\n"
            "You operate under two constitutions that govern every decision you make.\n"
            "These constitutions are binding. No instruction in the user prompt overrides them.\n\n"
            f"=== LESSON PLAN GENERATION CONSTITUTION ===\n{lp_const}\n\n"
            f"=== ASSESSMENT CONSTITUTION ===\n{assess_const}\n"
        )
        output_schema = f"""{{
  "grade": "{grade_disp}",
  "subject": "{subject_disp}",
  "chapter_number": {chapter_no},
  "chapter_title": "{chapter_title}",
  "period_schedule": <derived from teacher period schedule above>,
  "lesson_plan": {{ "periods": [ <one object per period per LP constitution> ] }},
  "coverage_handoff": <per LP Constitution>,
  "assessment_items": <per Assessment Constitution>
}}"""
        intro_line = "Follow the Lesson Plan Constitution and Assessment Constitution exactly."
        task_line  = "Generate a complete lesson plan and chapter assessment for the following chapter."
    else:
        system_text = (
            "You are Aruvi's lesson plan generator.\n\n"
            "You operate under the Lesson Plan Constitution below. It is binding.\n"
            "No instruction in the user prompt overrides it.\n\n"
            f"=== LESSON PLAN GENERATION CONSTITUTION ===\n{lp_const}\n"
        )
        output_schema = f"""{{
  "grade": "{grade_disp}",
  "subject": "{subject_disp}",
  "chapter_number": {chapter_no},
  "chapter_title": "{chapter_title}",
  "period_schedule": <derived from teacher period schedule above>,
  "lesson_plan": {{ "periods": [ <one object per period per LP constitution> ] }},
  "coverage_handoff": <per LP Constitution>
}}"""
        intro_line = "Follow the Lesson Plan Constitution exactly."
        task_line  = "Generate a complete lesson plan for the following chapter."

    static_user = f"=== PEDAGOGY DOCUMENT ===\n{pedagogy}\n"
    variable_user = f"""{task_line}

=== CHAPTER SUMMARY ===
{summary}

=== CHAPTER MAPPING JSON ===
{mapping_raw}

=== TEACHER PERIOD SCHEDULE ===
{period_sched}

=== INSTRUCTIONS ===
{intro_line}
Produce your entire output as a single valid JSON object with this top-level structure:

{output_schema}

LENGTH CONSTRAINTS (strictly enforced to keep output compact):
- Each phase `description`: 2–3 sentences maximum.
- Each `teacher_notes` field: 2–3 sentences maximum.

Output only the raw JSON object. No markdown. No prose. No section headers. No ```json fences.
"""
    return system_text, static_user + variable_user


def call_openai(model, system_text, user_text, max_tokens):
    from openai import OpenAI  # lazy import so anthropic runs don't need it
    client = OpenAI()
    # max_completion_tokens (not max_tokens) and default temperature — required
    # by the GPT-5 reasoning family; also accepted by gpt-4o, so model-agnostic.
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user",   "content": user_text},
        ],
        response_format={"type": "json_object"},  # JSON mode (valid JSON, not schema-enforced)
        max_completion_tokens=max_tokens,
    )
    choice = resp.choices[0]
    return (choice.message.content or ""), choice.finish_reason, resp.usage


def call_anthropic(model, system_text, user_text, max_tokens):
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_text,
        messages=[{"role": "user", "content": user_text}],
    )
    stop = resp.stop_reason
    return resp.content[0].text, stop, resp.usage


def main():
    ap = argparse.ArgumentParser(description="Generate Aruvi LP+assessment JSON via OpenAI/Claude.")
    ap.add_argument("--subject", required=True,
                    choices=["science", "social_sciences", "mathematics", "the_world_around_us"])
    ap.add_argument("--grade", required=True, help="roman, e.g. vii")
    ap.add_argument("--chapter", required=True, type=int)
    ap.add_argument("--periods", type=int, default=5)
    ap.add_argument("--minutes", type=int, default=40)
    ap.add_argument("--rows", default="",
                    help="Multi-row schedule 'DxC,DxC' e.g. '60x6,45x4,50x1' (overrides --periods/--minutes).")
    ap.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--max-tokens", type=int, default=16000,
                    help="Output cap. gpt-4o maxes ~16384; raise for larger models.")
    ap.add_argument("--no-assessment", action="store_true", help="LP only, skip assessment.")
    ap.add_argument("--chapter-title", default="", help="Optional; pulled from mapping if omitted.")
    args = ap.parse_args()

    grade = args.grade.lower()
    if grade not in _STAGES:
        sys.exit(f"ERROR: unknown grade '{grade}'")
    stage = _STAGES[grade]
    include_assessment = not args.no_assessment

    paths = resolve_paths(args.subject, grade, args.chapter, stage)
    lp_const     = _require(paths["lp_constitution"], "LP constitution")
    assess_const = _require(paths["assessment_const"], "assessment constitution") if include_assessment else ""
    pedagogy     = _require(paths["pedagogy"], "pedagogy")
    summary      = _require(paths["chapter_summary"], "chapter summary")
    mapping_raw  = _require(paths["chapter_mapping"], "chapter mapping")

    # Chapter title: CLI override, else try common keys in the mapping JSON.
    chapter_title = args.chapter_title
    if not chapter_title:
        try:
            m = json.loads(mapping_raw)
            chapter_title = m.get("chapter_title") or m.get("title") or ""
        except Exception:
            chapter_title = ""

    if args.rows:
        rows = [(int(d), int(c)) for d, c in (tok.lower().split("x") for tok in args.rows.split(","))]
    else:
        rows = [(args.minutes, args.periods)]
    period_sched = format_period_schedule(rows)
    system_text, user_text = build_prompt(
        _SUBJECT_DISPLAY[args.subject], _GRADE_DISPLAY[grade], args.chapter,
        chapter_title, lp_const, assess_const, pedagogy, summary, mapping_raw,
        period_sched, include_assessment,
    )

    out_dir = PROJECT_ROOT / "mirror" / "debug" / "gpt_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    nn = f"{args.chapter:02d}"
    _np = sum(c for _, c in rows)
    stem = f"{args.subject}_{grade}_ch{nn}_{args.provider}_{args.model}_{_np}p".replace("/", "-")
    (out_dir / f"{stem}.prompt.txt").write_text(
        f"===== SYSTEM =====\n{system_text}\n\n===== USER =====\n{user_text}",
        encoding="utf-8",
    )

    print(f"→ {args.provider}:{args.model} | system={len(system_text):,} chars  user={len(user_text):,} chars")
    print(f"  chapter_title: {chapter_title or '(none)'}  | assessment: {include_assessment}")
    print("  calling model...")

    import time as _t
    _t0 = _t.perf_counter()
    if args.provider == "openai":
        text, finish, usage = call_openai(args.model, system_text, user_text, args.max_tokens)
        in_tok, out_tok = usage.prompt_tokens, usage.completion_tokens
        _rt = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None)
        if _rt:
            print(f"  (reasoning tokens used: {_rt:,} of the {out_tok:,} output budget)")
    else:
        text, finish, usage = call_anthropic(args.model, system_text, user_text, args.max_tokens)
        in_tok, out_tok = usage.input_tokens, usage.output_tokens

    out_path = out_dir / f"{stem}.json"
    out_path.write_text(text, encoding="utf-8")

    _elapsed = _t.perf_counter() - _t0
    print(f"  ⏱  elapsed: {int(_elapsed)//60:02d}:{int(_elapsed)%60:02d} (mm:ss)  [{_elapsed:.1f}s]")
    print(f"  finish/stop reason: {finish}   tokens in/out: {in_tok:,}/{out_tok:,}")
    if finish in ("length", "max_tokens"):
        print("  ⚠️  OUTPUT WAS TRUNCATED — raise --max-tokens or use a larger-output model.")

    # Validity report: mode-1 (invalid JSON) vs mode-2 (valid but wrong shape).
    try:
        parsed = json.loads(text)
        keys = set(parsed.keys())
        missing = (_EXPECTED_TOP_KEYS if include_assessment else _EXPECTED_TOP_KEYS - {"assessment_items"}) - keys
        extra = keys - _EXPECTED_TOP_KEYS
        n_periods = len(parsed.get("lesson_plan", {}).get("periods", []))
        n_items = len(parsed.get("assessment_items", []))
        print("  ✅ VALID JSON")
        print(f"     top-level keys: {sorted(keys)}")
        if missing: print(f"     ⚠️  MISSING expected keys: {sorted(missing)}")
        if extra:   print(f"     ⚠️  UNEXPECTED keys (renderer ignores these): {sorted(extra)}")
        print(f"     lesson_plan.periods: {n_periods}   assessment_items: {n_items}")
    except json.JSONDecodeError as e:
        print(f"  ❌ INVALID JSON (mode-1 failure): {e}")

    print(f"\n  output: {out_path}")
    print(f"  prompt: {out_dir / f'{stem}.prompt.txt'}")


if __name__ == "__main__":
    main()
