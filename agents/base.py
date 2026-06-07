"""Shared LLM factory for all AutoPilot Dev agents.

CrewAI 1.x uses its own ``crewai.LLM`` wrapper (backed by LiteLLM) rather
than a raw LangChain chat model.  The model identifier for Groq follows the
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
logger.debug("LiteLLM patched: cache_breakpoint will be stripped from messages for Groq compatibility.")


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
