"""
ask_aruvi_agent.py — Ask Aruvi Q&A engine (Managed Agent version)

Replaces the direct Haiku call in ask_aruvi_qa.py with Anthropic's
Managed Agent API.  The agent already holds the KB file server-side,
so there is no need to send the full knowledge base in every request.

Usage pattern
─────────────
    from ask_aruvi_agent import ask as aruvi_ask

Returns exactly the same dict shape as ask_aruvi_qa.ask():
    {
        "response":      str,   # agent's answer text
        "input_tokens":  int,   # summed across all model spans
        "output_tokens": int,   # summed across all model spans
    }

Forwarding / out-of-scope detection and logging mirrors ask_aruvi_qa.py
exactly — same sentinel strings, same log_forwarded_query() call.

Status: ACTIVE (managed agent path)
Old path (ask_aruvi_qa.py) is immobilised in app.py but untouched on disk.
"""

import uuid
from datetime import datetime
from pathlib import Path

import anthropic

# ── Managed-agent credentials ─────────────────────────────────────────────────
AGENT_ID        = "agent_011Ca6z4gAUB897Nr3xfHNiT"
ENVIRONMENT_ID  = "env_01L8dPr1NDwDzkiDXWPpn8YE"
# FILE_ID is baked into the agent server-side; kept here for reference only.
_FILE_ID        = "file_011Ca71pJpRQAZz3d2sKTfqA"

# ── Forwarded-query log location (mirrors ask_aruvi_qa.py) ───────────────────
_PROJECT_ROOT            = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")
_FEEDBACK_FORWARDED_ROOT = _PROJECT_ROOT / "mirror/feedback/forwarded_queries"


# ── Forwarded-response detector (identical sentinel strings to ask_aruvi_qa) ──
def _is_forwarded_response(text: str) -> tuple[bool, str]:
    """
    Returns (True, "unmatched")    — in-scope but no KB answer
            (True, "out_of_scope") — entirely outside platform scope
            (False, "")            — normal answered response
    """
    if "forwarded to the Aruvi support team" in text:
        return (True, "unmatched")
    if "beyond the scope of Ask Aruvi" in text:
        return (True, "out_of_scope")
    return (False, "")


# ── Forwarded query logger (identical to ask_aruvi_qa.log_forwarded_query) ───
def _log_forwarded_query(
    query:      str,
    reason:     str,
    session_id: str,
    tab:        str,
    subject:    str,
    grade:      str,
) -> None:
    """Writes a JSON file for a forwarded / out-of-scope query."""
    now       = datetime.now()
    month_dir = _FEEDBACK_FORWARDED_ROOT / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    import json
    filename = f"query_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    record = {
        "type":       "forwarded_query",
        "timestamp":  now.isoformat(timespec="seconds"),
        "session_id": session_id,
        "query":      query,
        "reason":     reason,
        "tab":        tab,
        "subject":    subject,
        "grade":      grade,
        "source":     "managed_agent",   # distinguishes from old Haiku path
    }
    try:
        with open(month_dir / filename, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # logging failure must never surface to the teacher


# ── Main entry point ──────────────────────────────────────────────────────────
def ask(
    query:      str,
    category:   str = None,   # kept for API compatibility; not sent to agent
    session_id: str = "",
    tab:        str = "",
    subject:    str = "",
    grade:      str = "",
) -> dict:
    """
    Answers a teacher's question using the Managed Agent (KB held server-side).

    Flow:
        1. Create a fresh managed-agent session pinned to AGENT_ID + ENVIRONMENT_ID
        2. Send the teacher's query as a user.message event
        3. Stream events; collect agent.message text blocks and
           span.model_request_end token counts
        4. Detect forwarded / out-of-scope responses; log if needed
        5. Archive the session (fire-and-forget) to keep the account tidy
        6. Return {"response", "input_tokens", "output_tokens"}

    Args:
        query:      The teacher's question.
        category:   Kept for call-site compatibility (not used — agent holds KB).
        session_id: Caller's session identifier (for log correlation).
        tab:        UI tab context.
        subject:    Current subject context.
        grade:      Current grade context.
    """
    client = anthropic.Anthropic()

    # ── 1. Create a fresh session ─────────────────────────────────────────────
    session = client.beta.sessions.create(
        agent          = AGENT_ID,
        environment_id = ENVIRONMENT_ID,
        title          = f"ask_aruvi_{uuid.uuid4().hex[:8]}",
    )
    managed_session_id = session.id

    response_text  = ""
    input_tokens   = 0
    output_tokens  = 0

    try:
        # ── 2. Send the teacher's question ────────────────────────────────────
        client.beta.sessions.events.send(
            managed_session_id,
            events=[{
                "type":    "user.message",
                "content": [{"type": "text", "text": query}],
            }],
        )

        # ── 3. Stream events until session goes idle ──────────────────────────
        with client.beta.sessions.events.stream(managed_session_id) as stream:
            for event in stream:
                etype = getattr(event, "type", None)

                # Agent text response — collect all text blocks
                if etype == "agent.message":
                    for block in getattr(event, "content", []):
                        response_text += getattr(block, "text", "")

                # Token usage — accumulate across all model spans
                elif etype == "span.model_request_end":
                    usage = getattr(event, "model_usage", None)
                    if usage:
                        input_tokens  += getattr(usage, "input_tokens", 0)
                        output_tokens += getattr(usage, "output_tokens", 0)

                # Stop streaming once the session returns to idle
                elif etype == "session.status.idle":
                    break

                # Surface errors explicitly rather than silently returning empty
                elif etype == "session.status.terminated":
                    if not response_text:
                        response_text = (
                            "Ask Aruvi is momentarily unavailable. "
                            "Please try again in a few seconds."
                        )
                    break

    except Exception as exc:
        # Never crash the Streamlit app — return a safe fallback
        if not response_text:
            response_text = (
                "Ask Aruvi encountered an error. "
                "Please try again or contact support."
            )

    # ── 4. Detect and log forwarded / out-of-scope responses ─────────────────
    forwarded, reason = _is_forwarded_response(response_text)
    if forwarded:
        try:
            _log_forwarded_query(
                query      = query,
                reason     = reason,
                session_id = session_id,
                tab        = tab,
                subject    = subject,
                grade      = grade,
            )
        except Exception:
            pass  # logging failure must never surface to the teacher

    # ── 5. Archive session (fire-and-forget) ──────────────────────────────────
    try:
        client.beta.sessions.archive(managed_session_id)
    except Exception:
        pass  # tidy-up failure is non-fatal

    # ── 6. Return in the same shape as ask_aruvi_qa.ask() ────────────────────
    return {
        "response":      response_text.strip(),
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
    }
