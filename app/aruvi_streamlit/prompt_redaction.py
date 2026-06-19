"""Prompt-envelope redactors for the assessment generator.

Closes two leaks that drive Rule 2(b) originality violations:

  Leak A — chapter summary JSON carries tasks_verbatim[] and question_bank[]
           arrays for every spine. The assessment prompt forbids the model
           from reading them, but they sit in the user message regardless.
  Leak B — coverage_handoff carries tasks_anchored[] entries whose
           task_brief strings summarise textbook task structure (e.g.
           "six phrasal verbs with 'move' — match meanings"), driving
           structural echo in generated items.

Both helpers are pure: they return new objects and never mutate input.
"""

from __future__ import annotations

import json
from typing import Any

_FORBIDDEN_SUMMARY_KEYS = frozenset({"tasks_verbatim", "question_bank"})

_HANDOFF_CONTRIB_KEEP = frozenset({
    "section_id",
    "section_title",
    "section_type",
    "implied_lo",
    "section_context",
})


def _redact_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _redact_obj(v)
            for k, v in obj.items()
            if k not in _FORBIDDEN_SUMMARY_KEYS
        }
    if isinstance(obj, list):
        return [_redact_obj(v) for v in obj]
    return obj


def redact_summary_for_assessment(summary_text: str, is_json: bool) -> str:
    """Strip tasks_verbatim[] and question_bank[] from a chapter summary.

    For JSON summaries (English / Mathematics / TWAU) the strip is structural
    and lossless for everything else. For .txt summaries (Science / Social
    Sciences) the prose contains no such arrays, so the text is returned
    unchanged.
    """
    if not is_json:
        return summary_text
    try:
        parsed = json.loads(summary_text)
    except json.JSONDecodeError:
        return summary_text
    redacted = _redact_obj(parsed)
    return json.dumps(redacted, ensure_ascii=False, indent=2)


def redact_coverage_handoff(handoff: dict) -> dict:
    """Drop tasks_anchored[] from every section_contribution.

    Keeps only the fields the Assessment Constitution legitimately needs:
    section_id, section_title, section_type, implied_lo, section_context.
    """
    if not isinstance(handoff, dict):
        return handoff
    out: dict = {}
    for spine, payload in handoff.items():
        if not isinstance(payload, dict):
            out[spine] = payload
            continue
        contribs = payload.get("section_contributions", [])
        new_contribs = []
        for c in contribs:
            if isinstance(c, dict):
                new_contribs.append(
                    {k: c[k] for k in _HANDOFF_CONTRIB_KEEP if k in c}
                )
            else:
                new_contribs.append(c)
        new_payload = {k: v for k, v in payload.items() if k != "section_contributions"}
        new_payload["section_contributions"] = new_contribs
        out[spine] = new_payload
    return out
