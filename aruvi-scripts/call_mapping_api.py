"""
call_mapping_api.py
Two-call pipeline for Aruvi chapter mapping.

Call 1 — Summarise:
  Input : full chapter text
  Output: chapter_title + chapter_summary (markdown with headings)

Call 2 — Map:
  Input : chapter_summary (NOT raw chapter text) + CG document
  Output: primary, incidental, chapter_weight, min_viable_periods

The final record merges both outputs with stage/subject/grade/chapter_number
added from context. The two-call split is invisible to downstream consumers.
"""
import sys
import os
import json
import csv
import re
import time
from datetime import datetime
from pathlib import Path
import anthropic


# ── Token cost constants (claude-sonnet-4-6) ──────────────────────────────
INPUT_COST_PER_1K_INR  = 0.27   # ~$0.003 per 1K input tokens at ~90 INR/USD
OUTPUT_COST_PER_1K_INR = 1.35   # ~$0.015 per 1K output tokens


def _make_client():
    """Create Anthropic client with proxy/SSL handling for Cowork environment."""
    import os as _os, httpx as _httpx
    for _v in ["ALL_PROXY", "all_proxy"]:
        _os.environ.pop(_v, None)
    _http_proxy = (_os.environ.get("HTTPS_PROXY") or _os.environ.get("HTTP_PROXY")
                   or _os.environ.get("https_proxy") or _os.environ.get("http_proxy"))
    _http_client = _httpx.Client(proxy=_http_proxy, verify=False) if _http_proxy \
                   else _httpx.Client(verify=False)
    return anthropic.Anthropic(http_client=_http_client)


def load_constitution(subject_group: str, skill_dir: str) -> str:
    """Load the correct constitution for the subject group."""
    constitution_map = {
        "social_sciences": "constitution_social_sciences.md",
        "languages":       "constitution_languages.md",
        "mathematics":     "constitution_mathematics.md",
        "science":         "constitution_science.md",
    }
    filename = constitution_map.get(subject_group)
    if not filename:
        raise ValueError(f"Unknown subject group: {subject_group}. "
                        f"Must be one of: {list(constitution_map.keys())}")
    constitution_path = Path(skill_dir) / "references" / filename
    if not constitution_path.exists():
        raise FileNotFoundError(f"Constitution file not found: {constitution_path}")
    return constitution_path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# CALL 1 — SUMMARISE
# ═══════════════════════════════════════════════════════════════════════════

def build_summary_system_prompt() -> str:
    return """You are a curriculum documentation specialist. Your task is to produce a structured content summary of an NCERT textbook chapter.

The summary must faithfully represent what the chapter teaches — its concepts, terms, narratives, phenomena, people, events, and principles — organised under the chapter's own headings and subheadings.

CRITICAL: This is a content summary only. Do not describe exercises, questions, activities, or student tasks. Summarise only what the chapter teaches, not what students are asked to do.

You MUST respond with valid JSON only — no preamble, no explanation, no markdown fences."""


def build_summary_user_prompt(chapter_data: dict, chapter_number: int,
                               subject_group: str, stage: str, grade: str) -> str:
    return f"""## CHAPTER TO SUMMARISE

Subject Group : {subject_group}
Stage         : {stage}
Grade         : {grade}
Chapter Number: {chapter_number}

### Full Chapter Text
{chapter_data["full_text"]}

---

## REQUIRED OUTPUT

Respond with this exact JSON structure and nothing else:

{{
  "chapter_title": "<exact chapter title as it appears in the textbook>",
  "chapter_summary": "<structured content summary. Follow the chapter's own heading and subheading structure exactly — use markdown heading markers (## for major headings, ### for subheadings). Under each heading write 2-3 sentences summarising the key concepts, terms, significant people, events, phenomena, or principles in that section. Cover every section. Content only — no exercises, no student activities, no task descriptions.>"
}}

CRITICAL CONSTRAINTS:
- chapter_summary MUST be at least 800 words — cover every section heading; use as many words as the chapter's structure requires
- Use ## and ### markers to mirror the textbook's heading structure
- Content only — no exercises, no student activities, no task descriptions
- Respond with JSON only — no text before or after"""


def _validate_summary(result: dict, chapter_data: dict) -> list:
    """Validate Call 1 output. Returns list of error strings."""
    errors = []
    for field in ["chapter_title", "chapter_summary"]:
        if field not in result:
            errors.append(f"Missing field: {field}")

    if "chapter_summary" in result:
        wc = len(result["chapter_summary"].split())
        if wc < 800:
            errors.append(f"chapter_summary too short: {wc} words (minimum 800)")
        else:
            print(f"    chapter_summary: {wc} words")

        if "section_headings" in chapter_data:
            # Known PDF artefact and sidebar patterns — never real content headings
            ARTEFACT_PATTERNS = {
                "retpahc", "do you know", "let's explore", "think about it",
                "let us", "activity", "exercise", "summary", "keywords",
                "glossary", "prelims", "let's recall", "let's discuss",
            }
            summary_lower = result["chapter_summary"].lower()
            headings = chapter_data["section_headings"][:8]
            uncovered = []
            for h in headings[1:]:
                h_lower = h.lower()
                if any(pat in h_lower for pat in ARTEFACT_PATTERNS):
                    continue
                if len(h.split()) <= 2:
                    continue
                key_words = [w.lower() for w in h.split() if len(w) > 4]
                if key_words and not any(w in summary_lower for w in key_words):
                    uncovered.append(h)
            if len(uncovered) > 2:
                errors.append(f"chapter_summary may not cover these headings: {uncovered[:3]}")

    return errors


def call_summary_api(chapter_data: dict, chapter_number: int,
                     subject_group: str, stage: str, grade: str,
                     token_log_path: str, max_retries: int = 2) -> dict:
    """
    Call 1: Summarise the chapter from full text.
    Returns dict with chapter_title and chapter_summary.

    Uses multi-turn messages for retries so the model sees its prior response
    and corrects specific fields — prevents it from dropping chapter_title on retry.
    """
    client = _make_client()
    system_prompt = build_summary_system_prompt()
    initial_user_prompt = build_summary_user_prompt(
        chapter_data, chapter_number, subject_group, stage, grade
    )

    last_result = None
    total_input_tokens = 0
    total_output_tokens = 0

    for attempt in range(1, max_retries + 1):
        print(f"    Summary call attempt {attempt}/{max_retries}...")

        # On retry: send a fresh single-turn message with just the prior summary
        # to avoid re-sending 43k+ chars of chapter text and hitting context limits.
        if attempt == 1:
            messages = [{"role": "user", "content": initial_user_prompt}]
        else:
            prior_summary = last_result.get("chapter_summary", "") if last_result else ""
            prior_title   = last_result.get("chapter_title", "") if last_result else ""
            retry_prompt = (
                f"You previously produced this chapter summary but it had validation issues.\n\n"
                f"Prior chapter_title: {prior_title}\n\n"
                f"Prior chapter_summary:\n{prior_summary}\n\n"
                f"Please return corrected JSON with BOTH fields (chapter_title AND chapter_summary).\n"
                f"Issues to fix: {'; '.join(retry_errors)}"
            )
            messages = [{"role": "user", "content": retry_prompt}]

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )

            input_tokens  = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_input_tokens  += input_tokens
            total_output_tokens += output_tokens

            raw_text = response.content[0].text.strip()
            clean_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
            clean_text = re.sub(r'\s*```$', '', clean_text)

            result = json.loads(clean_text)

            # If retry dropped any fields, recover them from the previous good parse
            if attempt > 1 and last_result is not None:
                for field in ["chapter_title", "chapter_summary"]:
                    if field not in result and field in last_result:
                        result[field] = last_result[field]

            errors = _validate_summary(result, chapter_data)
            if errors and attempt < max_retries:
                print(f"    Validation issues (attempt {attempt}): {errors}")
                retry_errors = errors
                last_result = result
                continue

            cost = _log_tokens(
                token_log_path, "summary_call", subject_group, grade,
                chapter_number, result.get("chapter_title", "unknown"),
                total_input_tokens, total_output_tokens
            )

            if errors:
                print(f"    Warning (logged): {errors}")
            else:
                wc = len(result.get("chapter_summary", "").split())
                print(f"    Summary valid: {wc} words")

            print(f"    Tokens: {total_input_tokens} in + {total_output_tokens} out = "
                  f"{total_input_tokens+total_output_tokens} total | Cost: Rs.{cost:.4f}")

            return result

        except json.JSONDecodeError as e:
            print(f"    JSON parse error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Summary call: failed to parse JSON after {max_retries} attempts") from e
            retry_errors = [f"Response was not valid JSON: {e}"]
        except Exception as e:
            print(f"    API error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise
            time.sleep(2)

    raise RuntimeError("Summary call failed after all retries")

# ═══════════════════════════════════════════════════════════════════════════
# CALL 2 — MAP
# ═══════════════════════════════════════════════════════════════════════════

def build_mapping_system_prompt(constitution_text: str) -> str:
    return f"""You are the Aruvi chapter mapping engine. Your sole task is to map an NCERT chapter to NCF 2023 Curricular Goals and Competency codes, following the constitution below with complete precision.

{constitution_text}

IMPORTANT: You are working from a content summary of the chapter — not the raw chapter text. The summary describes what the chapter teaches: its concepts, narrative, phenomena, and content organisation. It does not include exercises or student activities. Apply the constitution's rules to the content as summarised.

You MUST respond with valid JSON only — no preamble, no explanation, no markdown fences. The JSON must conform exactly to the output schema provided in the user message."""


def build_mapping_user_prompt(summary: str, chapter_title: str, cg_data: dict,
                               subject_group: str, stage: str, grade: str,
                               chapter_number: int) -> str:
    cg_text = json.dumps(cg_data["curricular_goals"], ensure_ascii=False, indent=2)

    return f"""## CHAPTER TO MAP

Subject Group : {subject_group}
Stage         : {stage}
Grade         : {grade}
Chapter Number: {chapter_number}
Chapter Title : {chapter_title}

### Chapter Content Summary
{summary}

---

## CURRICULAR GOALS AND C-CODES (your sole framework reference)

{cg_text}

---

## REQUIRED OUTPUT

Respond with this exact JSON structure and nothing else:

{{
  "min_viable_periods": <integer: minimum periods needed to teach this chapter at all>,
  "primary": [
    {{
      "cg": "<CG code e.g. CG-2>",
      "c_code": "<C-code e.g. C-2.1>",
      "weight": <3 | 2 | 1>,
      "justification": "<one sentence explaining the structural match per constitution rules>"
    }}
  ],
  "incidental": [
    {{ "cg": "<CG code>", "c_code": "<C-code>" }}
  ],
  "chapter_weight": <sum of all primary weight scores>
}}

CRITICAL CONSTRAINTS:
- Apply the constitution rules exactly. Weight 3 only if the competency structurally dissolves the chapter if removed.
- chapter_weight MUST equal the arithmetic sum of all primary weight scores.
- Only use C-codes that appear in the Curricular Goals list provided above.
- Respond with JSON only — no text before or after."""


def _validate_mapping(mapping: dict) -> list:
    """Validate Call 2 output. Returns list of error strings."""
    errors = []
    for field in ["min_viable_periods", "primary", "incidental", "chapter_weight"]:
        if field not in mapping:
            errors.append(f"Missing field: {field}")

    if "primary" in mapping and "chapter_weight" in mapping:
        computed = sum(p.get("weight", 0) for p in mapping["primary"])
        if computed != mapping["chapter_weight"]:
            errors.append(
                f"chapter_weight mismatch: stated {mapping['chapter_weight']}, "
                f"computed {computed}"
            )

    if "primary" in mapping:
        if len(mapping["primary"]) == 0:
            errors.append("No primary competencies — every valid NCERT chapter must have at least one")
        for p in mapping["primary"]:
            if p.get("weight") not in [1, 2, 3]:
                errors.append(f"Invalid weight {p.get('weight')} for {p.get('c_code')}")

    return errors


def call_mapping_api(chapter_data: dict, cg_data: dict, subject_group: str,
                     stage: str, grade: str, chapter_number: int,
                     skill_dir: str, token_log_path: str,
                     max_retries: int = 2) -> dict:
    """
    Full two-call pipeline. Orchestrates Call 1 (summarise) then Call 2 (map).
    Returns the merged, validated final record.
    """
    # ── Call 1: Summarise ────────────────────────────────────────────────────
    print("  [Call 1/2] Summarising chapter content...")
    summary_result = call_summary_api(
        chapter_data   = chapter_data,
        chapter_number = chapter_number,
        subject_group  = subject_group,
        stage          = stage,
        grade          = grade,
        token_log_path = token_log_path,
        max_retries    = max_retries
    )
    chapter_title   = summary_result["chapter_title"]
    chapter_summary = summary_result["chapter_summary"]

    # ── Call 2: Map ──────────────────────────────────────────────────────────
    print("  [Call 2/2] Mapping competencies from summary...")
    constitution  = load_constitution(subject_group, skill_dir)
    system_prompt = build_mapping_system_prompt(constitution)
    user_prompt   = build_mapping_user_prompt(
        summary        = chapter_summary,
        chapter_title  = chapter_title,
        cg_data        = cg_data,
        subject_group  = subject_group,
        stage          = stage,
        grade          = grade,
        chapter_number = chapter_number
    )

    client = _make_client()

    for attempt in range(1, max_retries + 1):
        print(f"    Mapping call attempt {attempt}/{max_retries}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            input_tokens  = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            raw_text = response.content[0].text.strip()
            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

            mapping = json.loads(raw_text)

            errors = _validate_mapping(mapping)
            if errors and attempt < max_retries:
                print(f"    Validation issues (attempt {attempt}): {errors}")
                repair_note = "REPAIR REQUIRED: " + "; ".join(errors)
                user_prompt = user_prompt + f"\n\n{repair_note}\nPlease fix and return corrected JSON only."
                continue

            cost = _log_tokens(
                token_log_path, "mapping_call", subject_group, grade,
                chapter_number, chapter_title, input_tokens, output_tokens
            )

            if errors:
                print(f"    Warning (logged): {errors}")
            else:
                print(f"    Mapping valid")

            print(f"    Tokens: {input_tokens} in + {output_tokens} out = "
                  f"{input_tokens+output_tokens} total | Cost: Rs.{cost:.4f}")

            # ── Merge into final record ──────────────────────────────────────
            record = {
                "stage":              stage,
                "subject":            subject_group,
                "grade":              grade,
                "chapter_number":     chapter_number,
                "chapter_title":      chapter_title,
                "chapter_summary":    chapter_summary,
                "min_viable_periods": mapping["min_viable_periods"],
                "primary":            mapping["primary"],
                "incidental":         mapping["incidental"],
                "chapter_weight":     mapping["chapter_weight"],
            }
            return record

        except json.JSONDecodeError as e:
            print(f"    JSON parse error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Mapping call: failed to parse JSON after {max_retries} attempts") from e
        except Exception as e:
            print(f"    API error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise
            time.sleep(2)

    raise RuntimeError("Mapping call failed after all retries")


# ═══════════════════════════════════════════════════════════════════════════
# TOKEN LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def _log_tokens(log_path: str, call_type: str, subject: str, grade: str,
                chapter_number: int, chapter_title: str,
                input_tokens: int, output_tokens: int) -> float:
    """Append one row to the token log CSV. Returns cost in INR."""
    cost_inr = (
        (input_tokens  / 1000) * INPUT_COST_PER_1K_INR +
        (output_tokens / 1000) * OUTPUT_COST_PER_1K_INR
    )
    row = {
        "timestamp":      datetime.now().isoformat(),
        "call_type":      call_type,
        "subject":        subject,
        "grade":          grade,
        "chapter_number": chapter_number,
        "chapter_title":  chapter_title,
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "total_tokens":   input_tokens + output_tokens,
        "cost_inr":       f"{cost_inr:.4f}"
    }
    log_path = Path(log_path)
    write_header = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return cost_inr
