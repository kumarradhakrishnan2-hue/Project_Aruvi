"""
call_mapping_api.py
Assembles the mapping prompt, calls Claude API (claude-sonnet-4-6),
parses and validates the JSON output, and logs token usage.
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
# Prices in INR (approximate, update if API pricing changes)
INPUT_COST_PER_1K_INR  = 0.27   # ~$0.003 per 1K input tokens at ~90 INR/USD
OUTPUT_COST_PER_1K_INR = 1.35   # ~$0.015 per 1K output tokens


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


def build_system_prompt(constitution_text: str) -> str:
    return f"""You are the Aruvi chapter mapping engine. Your sole task is to map an NCERT chapter to NCF 2023 Curricular Goals and Competency codes, following the constitution below with complete precision.

{constitution_text}

You MUST respond with valid JSON only — no preamble, no explanation, no markdown fences. The JSON must conform exactly to the output schema provided in the user message."""


def build_user_prompt(chapter_data: dict, cg_data: dict, subject_group: str,
                      stage: str, grade: str, chapter_number: int) -> str:
    headings_text = "\n".join(f"  - {h}" for h in chapter_data["section_headings"])
    cg_text = json.dumps(cg_data["curricular_goals"], ensure_ascii=False, indent=2)

    return f"""## CHAPTER TO MAP

Subject Group : {subject_group}
Stage         : {stage}
Grade         : {grade}
Chapter Number: {chapter_number}

### Section Headings (from textbook — your chapter summary MUST address each one)
{headings_text}

### Full Chapter Text
{chapter_data["full_text"]}

---

## CURRICULAR GOALS AND C-CODES (your sole framework reference)

{cg_text}

---

## REQUIRED OUTPUT

Respond with this exact JSON structure and nothing else:

{{
  "stage": "{stage}",
  "subject": "{subject_group}",
  "grade": "{grade}",
  "chapter_number": {chapter_number},
  "chapter_title": "<exact chapter title as it appears in the textbook>",
  "chapter_summary": "<600–900 word structured summary. MUST follow the chapter's own heading structure — one paragraph per major heading/subheading. Include: key concepts and terms, significant people/events/phenomena, and where relevant the textbook's own suggested activities or examples. This is the content backbone for lesson plan generation — it must be faithful to what the chapter actually contains, section by section.>",
  "min_viable_periods": <integer: minimum periods to teach this chapter at all>,
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
- chapter_summary MUST be 600–900 words and MUST follow the textbook's heading structure.
- chapter_weight MUST equal the arithmetic sum of all primary weight scores.
- Only use C-codes that appear in the Curricular Goals list provided above.
- Respond with JSON only — no text before or after."""


def validate_output(record: dict, chapter_data: dict) -> list[str]:
    """Validate the mapping output. Returns list of error strings (empty = valid)."""
    errors = []

    required_fields = ["stage", "subject", "grade", "chapter_number", "chapter_title",
                       "chapter_summary", "min_viable_periods", "primary", "incidental",
                       "chapter_weight"]
    for field in required_fields:
        if field not in record:
            errors.append(f"Missing required field: {field}")

    if "chapter_summary" in record:
        word_count = len(record["chapter_summary"].split())
        if word_count < 500:
            errors.append(f"chapter_summary too short: {word_count} words (minimum 500)")
        elif word_count > 1000:
            errors.append(f"chapter_summary too long: {word_count} words (maximum 1000)")

    if "primary" in record and "chapter_weight" in record:
        computed_weight = sum(p.get("weight", 0) for p in record["primary"])
        if computed_weight != record["chapter_weight"]:
            errors.append(
                f"chapter_weight mismatch: stated {record['chapter_weight']}, "
                f"computed {computed_weight}"
            )

    if "primary" in record:
        if len(record["primary"]) == 0:
            errors.append("No primary competencies — every valid NCERT chapter must have at least one")
        for p in record["primary"]:
            if p.get("weight") not in [1, 2, 3]:
                errors.append(f"Invalid weight {p.get('weight')} for {p.get('c_code')}")

    # Check heading coverage: summary should mention key headings
    if "chapter_summary" in record and "section_headings" in chapter_data:
        summary_lower = record["chapter_summary"].lower()
        headings = chapter_data["section_headings"][:8]  # check first 8 headings
        uncovered = []
        for h in headings[1:]:  # skip title
            key_words = [w.lower() for w in h.split() if len(w) > 4]
            if key_words and not any(w in summary_lower for w in key_words):
                uncovered.append(h)
        if len(uncovered) > 2:
            errors.append(
                f"chapter_summary may not cover these headings: {uncovered[:3]}"
            )

    return errors


def log_tokens(log_path: str, subject: str, grade: str, chapter_number: int,
               chapter_title: str, input_tokens: int, output_tokens: int):
    """Append one row to the token log CSV."""
    cost_inr = (
        (input_tokens  / 1000) * INPUT_COST_PER_1K_INR +
        (output_tokens / 1000) * OUTPUT_COST_PER_1K_INR
    )
    row = {
        "timestamp":      datetime.now().isoformat(),
        "call_type":      "chapter_mapping",
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


def call_mapping_api(chapter_data: dict, cg_data: dict, subject_group: str,
                     stage: str, grade: str, chapter_number: int,
                     skill_dir: str, token_log_path: str,
                     max_retries: int = 2) -> dict:
    """
    Call Claude API to generate chapter mapping.
    Returns the parsed and validated mapping record.
    """
    constitution = load_constitution(subject_group, skill_dir)
    system_prompt = build_system_prompt(constitution)
    user_prompt   = build_user_prompt(chapter_data, cg_data, subject_group,
                                       stage, grade, chapter_number)

    # Strip socks proxy — httpx can't use socks5h; fall back to HTTP_PROXY.
    # Also disable SSL verification: the local proxy does TLS inspection
    # with a self-signed cert the VM doesn't trust.
    import os as _os, httpx as _httpx
    for _v in ["ALL_PROXY", "all_proxy"]:
        _os.environ.pop(_v, None)
    _http_proxy = (_os.environ.get("HTTPS_PROXY") or _os.environ.get("HTTP_PROXY")
                   or _os.environ.get("https_proxy") or _os.environ.get("http_proxy"))
    _http_client = _httpx.Client(proxy=_http_proxy, verify=False) if _http_proxy \
                   else _httpx.Client(verify=False)
    client = anthropic.Anthropic(http_client=_http_client)  # reads ANTHROPIC_API_KEY from env

    for attempt in range(1, max_retries + 1):
        print(f"  API call attempt {attempt}/{max_retries}...")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            input_tokens  = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            raw_text = response.content[0].text.strip()

            # Strip markdown fences if model added them despite instructions
            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

            record = json.loads(raw_text)

            # Validate
            errors = validate_output(record, chapter_data)
            if errors and attempt < max_retries:
                print(f"  Validation issues (attempt {attempt}): {errors}")
                print("  Retrying with repair prompt...")
                repair_note = "REPAIR REQUIRED: " + "; ".join(errors)
                user_prompt = user_prompt + f"\n\n{repair_note}\nPlease fix and return corrected JSON only."
                continue

            # Log tokens (even if there are minor validation warnings)
            cost = log_tokens(
                token_log_path, subject_group, grade, chapter_number,
                record.get("chapter_title", "unknown"), input_tokens, output_tokens
            )

            if errors:
                print(f"  ⚠ Validation warnings (logged): {errors}")
            else:
                print(f"  ✓ Mapping valid")

            print(f"  Tokens: {input_tokens} in + {output_tokens} out = "
                  f"{input_tokens+output_tokens} total | Cost: ₹{cost:.4f}")

            return record

        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Failed to parse JSON after {max_retries} attempts") from e
        except Exception as e:
            print(f"  API error (attempt {attempt}): {e}")
            if attempt == max_retries:
                raise
            time.sleep(2)

    raise RuntimeError("Mapping failed after all retries")


if __name__ == "__main__":
    # Quick test: python call_mapping_api.py <chapter_json> <cg_json> <subject> <stage> <grade> <chapter_num> <skill_dir> <token_log>
    if len(sys.argv) < 9:
        print("Usage: call_mapping_api.py <chapter_json> <cg_json> <subject_group> "
              "<stage> <grade> <chapter_number> <skill_dir> <token_log_path>")
        sys.exit(1)

    chapter_data   = json.loads(Path(sys.argv[1]).read_text())
    cg_data        = json.loads(Path(sys.argv[2]).read_text())
    subject_group  = sys.argv[3]
    stage          = sys.argv[4]
    grade          = sys.argv[5]
    chapter_number = int(sys.argv[6])
    skill_dir      = sys.argv[7]
    token_log_path = sys.argv[8]

    result = call_mapping_api(chapter_data, cg_data, subject_group, stage,
                               chapter_number, skill_dir, token_log_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
