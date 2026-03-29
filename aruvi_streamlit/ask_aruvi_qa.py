"""
ask_aruvi_qa.py — Ask Aruvi Q&A engine

Loads the platform Q&A knowledge base, calls claude-haiku to answer
teacher questions, and logs any forwarded queries to disk.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

import anthropic

# ── Constants ─────────────────────────────────────────────────────────────────
PROJECT_ROOT            = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")
QA_KB_PATH              = PROJECT_ROOT / "mirror/ask_aruvi/qa_knowledge_base.json"
FEEDBACK_FORWARDED_ROOT = PROJECT_ROOT / "mirror/feedback/forwarded_queries"
HAIKU_MODEL             = "claude-haiku-4-5-20251001"

_VALID_CATEGORIES       = {"cat_a", "cat_b", "cat_c", "cat_d", "cat_e"}


# ── Knowledge base loader ─────────────────────────────────────────────────────
def load_knowledge_base(category: str = None) -> str:
    """
    Reads qa_knowledge_base.json and returns Q&A pairs as a formatted string.

    Format per pair:
        Q: <question>
        A: <answer>

    If category is None or invalid: returns all pairs from all categories.
    If category is a valid key (cat_a … cat_e): returns only that category's pairs.
    """
    with open(QA_KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)

    categories = kb.get("categories", {})

    # Decide which categories to include
    if category and category in _VALID_CATEGORIES and category in categories:
        cats_to_use = {category: categories[category]}
    else:
        cats_to_use = categories

    lines = []
    for cat_data in cats_to_use.values():
        for pair in cat_data.get("pairs", []):
            q = pair.get("q", "").strip()
            a = pair.get("a", "").strip()
            if q and a:
                lines.append(f"Q: {q}\nA: {a}\n")

    return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────────────────
def build_system_prompt() -> str:
    """Returns the fixed system prompt for Ask Aruvi."""
    return (
        "You are Ask Aruvi, a help assistant for the Aruvi platform. "
        "Answer only from the Q&A knowledge base provided. "
        "Respond in 80 words or fewer. Be direct. Do not restate the question. "
        "When synthesising across multiple answers, compress into a single "
        "response — do not present each answer sequentially. "
        "Respond in the same language the teacher uses. "
        "If the question is within platform scope but cannot be confidently "
        "answered from the knowledge base, respond with exactly: "
        "'I do not have a specific answer for this. Your query will be "
        "forwarded to the Aruvi support team for a revert.' "
        "If the question is outside platform scope entirely, respond with exactly: "
        "'Ask Aruvi is a tool to help users with questions on the platform. "
        "This question is beyond the scope of Ask Aruvi.'"
    )


# ── Forwarded-response detector ───────────────────────────────────────────────
def is_forwarded_response(response_text: str) -> tuple[bool, str]:
    """
    Detects whether the model's response is a forwarding/out-of-scope reply.

    Returns:
        (True,  "unmatched")    — question in scope but unanswerable
        (True,  "out_of_scope") — question outside platform scope
        (False, "")             — normal answered response
    """
    if "forwarded to the Aruvi support team" in response_text:
        return (True, "unmatched")
    if "beyond the scope of Ask Aruvi" in response_text:
        return (True, "out_of_scope")
    return (False, "")


# ── Forwarded query logger ────────────────────────────────────────────────────
def log_forwarded_query(
    query:      str,
    reason:     str,
    session_id: str,
    tab:        str,
    subject:    str,
    grade:      str,
) -> None:
    """
    Writes a JSON file for a forwarded / out-of-scope query.

    Files land in:
        FEEDBACK_FORWARDED_ROOT / YYYY-MM / query_{timestamp}.json
    """
    now       = datetime.now()
    month_dir = FEEDBACK_FORWARDED_ROOT / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    timestamp = now.isoformat(timespec="seconds")
    filename  = f"query_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}.json"

    record = {
        "type":       "forwarded_query",
        "timestamp":  timestamp,
        "session_id": session_id,
        "query":      query,
        "reason":     reason,
        "tab":        tab,
        "subject":    subject,
        "grade":      grade,
    }

    with open(month_dir / filename, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


# ── Main entry point ──────────────────────────────────────────────────────────
def ask(
    query:      str,
    category:   str = None,
    session_id: str = "",
    tab:        str = "",
    subject:    str = "",
    grade:      str = "",
) -> dict:
    """
    Answers a teacher's question using the Ask Aruvi knowledge base.

    Steps:
        1. Load knowledge base (filtered by category if provided)
        2. Build system prompt
        3. Call claude-haiku-4-5-20251001 (max_tokens=300)
        4. Detect forwarded / out-of-scope responses and log them
        5. Return a dict with keys: "response", "input_tokens", "output_tokens"

    Args:
        query:      The teacher's question.
        category:   Optional KB category key (cat_a … cat_e) for scoped lookup.
        session_id: Caller's session identifier (for log correlation).
        tab:        UI tab context (e.g. "Generate", "My Plans").
        subject:    Current subject context.
        grade:      Current grade context.

    Returns:
        dict with keys:
            "response"      — the model's answer text
            "input_tokens"  — tokens consumed on the input side
            "output_tokens" — tokens consumed on the output side
    """
    kb_text       = load_knowledge_base(category)
    system_prompt = build_system_prompt()
    user_content  = kb_text + "\n\nTeacher's question: " + query

    client   = anthropic.Anthropic()
    response = client.messages.create(
        model      = HAIKU_MODEL,
        max_tokens = 300,
        system     = system_prompt,
        messages   = [{"role": "user", "content": user_content}],
    )

    response_text  = response.content[0].text
    input_tokens   = response.usage.input_tokens
    output_tokens  = response.usage.output_tokens

    forwarded, reason = is_forwarded_response(response_text)
    if forwarded:
        try:
            log_forwarded_query(
                query      = query,
                reason     = reason,
                session_id = session_id,
                tab        = tab,
                subject    = subject,
                grade      = grade,
            )
        except Exception:
            pass  # logging failure must never surface to the teacher

    return {
        "response":      response_text,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
    }
