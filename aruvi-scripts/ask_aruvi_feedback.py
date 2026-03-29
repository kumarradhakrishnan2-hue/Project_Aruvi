"""
ask_aruvi_feedback.py — Feedback writers for Ask Aruvi and general platform feedback.

All writes are silent-fail: logging errors must never surface to the teacher.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
PROJECT_ROOT      = Path("/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi")
FEEDBACK_ROOT     = PROJECT_ROOT / "mirror/feedback"
ASK_ARUVI_FB_ROOT = FEEDBACK_ROOT / "ask_aruvi"
GENERAL_FB_ROOT   = FEEDBACK_ROOT / "general"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_month_folder(root: Path) -> Path:
    """Returns root/YYYY-MM/, creating it if necessary."""
    folder = root / datetime.now().strftime("%Y-%m")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _write_record(folder: Path, record: dict) -> None:
    """Writes record as JSON to folder/feedback_{YYYYMMDD_HHMMSS}.json. Never raises."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"feedback_{timestamp}_{uuid.uuid4().hex[:6]}.json"
        with open(folder / filename, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Ask Aruvi thumbs feedback ─────────────────────────────────────────────────
def write_thumbs_feedback(
    session_id:        str,
    rating:            str,
    query:             str,
    response_excerpt:  str,
    category_selected: str,
    follow_up_text:    str = None,
) -> None:
    """
    Records a thumbs-up or thumbs-down rating on an Ask Aruvi response.

    Args:
        session_id:        Caller session identifier.
        rating:            "up" or "down".
        query:             The teacher's original question.
        response_excerpt:  First 200 characters of the Haiku response.
        category_selected: KB category the teacher had selected (e.g. "cat_a").
        follow_up_text:    Optional free-text follow-up (e.g. from a thumbs-down form).
    """
    record = {
        "type":               "ask_aruvi",
        "timestamp":          datetime.now().isoformat(timespec="seconds"),
        "session_id":         session_id,
        "category_selected":  category_selected,
        "query":              query,
        "response_excerpt":   response_excerpt,
        "rating":             rating,
        "follow_up_text":     follow_up_text,
    }
    folder = _get_month_folder(ASK_ARUVI_FB_ROOT)
    _write_record(folder, record)


# ── General platform feedback ─────────────────────────────────────────────────
def write_general_feedback(
    session_id:    str,
    feedback_text: str,
    tab:           str,
    subject:       str,
    grade:         str,
) -> None:
    """
    Records a general platform feedback submission.

    Args:
        session_id:    Caller session identifier.
        feedback_text: Free-text feedback from the teacher.
        tab:           UI tab where feedback was submitted (e.g. "Generate").
        subject:       Current subject context.
        grade:         Current grade context.
    """
    record = {
        "type":          "general",
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "session_id":    session_id,
        "tab":           tab,
        "subject":       subject,
        "grade":         grade,
        "feedback_text": feedback_text,
    }
    folder = _get_month_folder(GENERAL_FB_ROOT)
    _write_record(folder, record)
