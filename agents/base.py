"""Shared LLM factory for all AutoPilot Dev agents.

CrewAI 1.x uses its own ``crewai.LLM`` wrapper (backed by LiteLLM) rather
than a raw LangChain chat model. The model identifier for Groq follows the
LiteLLM convention: ``"groq/<model_name>"``.

Problem: CrewAI 1.14.x injects a ``cache_breakpoint`` key into each message
dict for Anthropic-style prompt caching. Groq rejects any message that
carries this unknown property. LiteLLM's ``drop_params`` flag only strips
top-level completion params — it does not clean message-level extra keys.

Fix: We monkey-patch ``litellm.completion`` (and its async sibling) to strip
``cache_breakpoint`` from every message dict before forwarding the call.
This is applied once at module load and is transparent to all callers.

All agents must call ``get_crewai_llm()`` — values always come from settings.
"""

from __future__ import annotations

import litellm
from crewai import LLM

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Monkey-patch LiteLLM to strip cache_breakpoint from messages ──────────────
_BANNED_MSG_KEYS = {"cache_breakpoint"}
_original_completion = litellm.completion
_original_acompletion = litellm.acompletion


def _scrub_messages(kwargs: dict) -> dict:
    """Remove Groq-incompatible keys from every message dict in *kwargs*."""
    messages = kwargs.get("messages")
    if isinstance(messages, list):
        cleaned = []
        for msg in messages:
            if isinstance(msg, dict):
                msg = {k: v for k, v in msg.items() if k not in _BANNED_MSG_KEYS}
            cleaned.append(msg)
        kwargs = {**kwargs, "messages": cleaned}
    return kwargs


def _patched_completion(*args, **kwargs):
    kwargs = _scrub_messages(kwargs)
    return _original_completion(*args, **kwargs)


async def _patched_acompletion(*args, **kwargs):
    kwargs = _scrub_messages(kwargs)
    return await _original_acompletion(*args, **kwargs)


litellm.completion = _patched_completion
litellm.acompletion = _patched_acompletion
logger.debug(
    "LiteLLM patched: cache_breakpoint will be stripped from messages "
    "for Groq compatibility."
)


def get_crewai_llm() -> LLM:
    """Return a CrewAI-compatible LLM instance configured from settings.

    Model  : ``settings.groq_model``   (e.g. ``llama-3.3-70b-versatile``)
    API key: ``settings.groq_api_key`` (read from env — never hardcoded)
    """
    model_id = f"groq/{settings.groq_model}"
    logger.debug("Initialising CrewAI LLM — model=%s", model_id)
    return LLM(
        model=model_id,
        api_key=settings.groq_api_key,
        temperature=0.1,
    )


def kickoff_with_retry(crew, max_retries: int = 4, default_wait: float = 20.0):
    """Invoke crew.kickoff() with automatic retry on Groq rate-limit errors.

    Groq's free tier has a 12,000 TPM limit.  When we hit it the API returns a
    RateLimitError that includes "Please try again in Xs" in the message body.
    We parse that hint and sleep accordingly before retrying.

    Parameters
    ----------
    crew:
        A constructed ``crewai.Crew`` instance ready to run.
    max_retries:
        Maximum number of retry attempts after the first failure.
    default_wait:
        Seconds to wait when the error message contains no retry hint.
    """
    import re
    import time

    attempt = 0
    while True:
        try:
            return crew.kickoff()
        except Exception as exc:
            err = str(exc)
            is_rate_limit = (
                "rate_limit" in err.lower()
                or "ratelimit" in err.lower()
                or "429" in err
            )
            if not is_rate_limit or attempt >= max_retries:
                raise

            attempt += 1
            # Parse "Please try again in 8.94s" from the Groq error body
            match = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", err, re.IGNORECASE)
            wait = float(match.group(1)) + 2.0 if match else default_wait

            logger.warning(
                "Groq rate limit hit (attempt %d/%d). Waiting %.1fs before retry...",
                attempt,
                max_retries,
                wait,
            )
            time.sleep(wait)




# ── Shared JSON parser used by all agents ─────────────────────────────────────

def _escape_control_chars_in_strings(s: str) -> str:
    """Escape literal control characters that appear inside JSON string values.

    LLMs sometimes emit multi-line strings with real newline/tab/carriage-return
    characters instead of JSON escape sequences (\\n, \\t, \\r).  This makes
    the output invalid JSON.  This function walks the raw text with a simple
    state machine and escapes those control characters *only while inside a
    quoted string*, leaving the structural JSON characters untouched.
    """
    result: list[str] = []
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and in_string:
            # Already-escaped sequence — copy both characters verbatim
            result.append(ch)
            i += 1
            if i < len(s):
                result.append(s[i])
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string:
            if ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            elif ord(ch) < 0x20:
                # Other ASCII control characters → unicode escape
                result.append(f"\\u{ord(ch):04x}")
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def parse_agent_json(raw: str, context: str = "") -> dict:
    """Strip markdown fences, sanitize, and parse JSON from an LLM response.

    Three-layer strategy, most to least strict:
    1. Strip fences + escape control chars -> json.loads
    2. Pass the result through json_repair.repair_json (handles unescaped
       quotes, Python docstrings with triple-quotes, trailing commas, etc.)
    3. Raise ValueError with a diagnostic log.

    Parameters
    ----------
    raw:
        The raw string returned by ``crew.kickoff()``.
    context:
        Label for error messages (e.g. ``"documenter"``).

    Raises
    ------
    ValueError
        If all repair attempts fail.
    """
    import json
    import re

    from json_repair import repair_json  # noqa: PLC0415

    # ── Layer 0: strip markdown fences ────────────────────────────────────────
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip(",")

    # ── Layer 1: escape control characters, try strict parse ──────────────────
    sanitized = _escape_control_chars_in_strings(clean)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError as exc1:
        logger.debug(
            "parse_agent_json [%s] strict parse failed (%s) — trying json-repair",
            context or "agent",
            exc1,
        )

    # ── Layer 2: json-repair (handles unescaped quotes, etc.) ─────────────────
    try:
        repaired = repair_json(clean, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        # repair_json sometimes returns a list or primitive — wrap if needed
        if isinstance(repaired, list) and len(repaired) == 1 and isinstance(repaired[0], dict):
            return repaired[0]
        # Last-ditch: parse the repaired string
        repaired_str = repair_json(clean)
        return json.loads(repaired_str)
    except Exception as exc2:
        logger.error(
            "parse_agent_json [%s] json-repair also failed — raw (first 800 chars):\n"
            "%.800s\nlayer1_error: %s\nlayer2_error: %s",
            context or "agent",
            raw,
            exc1,
            exc2,
        )
        raise ValueError(
            f"Agent ({context}) returned un-parseable JSON. "
            f"Layer1: {exc1} | Layer2: {exc2}"
        ) from exc2
