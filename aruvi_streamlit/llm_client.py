"""Single seam between Aruvi and the model provider SDK.

Aruvi is built and certified against Claude only. Rather than instantiate the
Anthropic SDK at each call site, every runtime model call routes through this
module. If a second model is ever deliberately certified, this is the one file
that changes — the app code never touches the provider SDK directly.

Pure passthrough today: stream() and create() return the genuine SDK objects
unchanged, so callers keep using `.text_stream`, `.get_final_message()`,
`.get_current_message_snapshot()`, `.content`, and `.usage` exactly as before.
"""

import os

import anthropic

# Certified model IDs. Aruvi is validated against these specific Claude
# versions — bump only after re-running the per-version regression cycle.
GENERATION_MODEL = "claude-sonnet-4-6"          # LP / assessment generation
HELPLINE_MODEL   = "claude-haiku-4-5-20251001"  # Ask Aruvi Q&A

# Anthropic prompt-caching beta header. Sent only when a call opts in via
# prompt_cache=True, preserving the prior per-call behaviour.
_PROMPT_CACHE_HEADERS = {"anthropic-beta": "prompt-caching-2024-07-31"}


def _client():
    """Construct the provider client. Reads ANTHROPIC_API_KEY from the env."""
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def stream(*, model, max_tokens, system, messages, prompt_cache=False):
    """Streaming completion. Returns the SDK stream context manager unchanged.

    Use as:  with llm_client.stream(...) as s:  for text in s.text_stream: ...
    """
    kwargs = {
        "model":      model,
        "max_tokens": max_tokens,
        "system":     system,
        "messages":   messages,
    }
    if prompt_cache:
        kwargs["extra_headers"] = _PROMPT_CACHE_HEADERS
    return _client().messages.stream(**kwargs)


def create(*, model, max_tokens, system, messages):
    """Non-streaming completion. Returns the SDK response object unchanged."""
    return _client().messages.create(
        model      = model,
        max_tokens = max_tokens,
        system     = system,
        messages   = messages,
    )
