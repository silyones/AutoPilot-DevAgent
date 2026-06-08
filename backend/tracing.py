"""LangSmith tracing setup for AutoPilot Dev.

This module MUST be imported — and ``setup_tracing()`` called — before any
LangChain or LangGraph import anywhere in the process.  The safest place is
the very first line of ``api/main.py``.

All values come from ``settings`` (which reads .env) — nothing is hardcoded.
"""

from __future__ import annotations

import os

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def setup_tracing() -> None:
    """Push LangSmith environment variables before LangChain initialises.

    LangChain reads these env vars once at import time, so they must be set
    before the first ``from langchain...`` or ``from langgraph...`` statement
    executes anywhere in the process.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    logger.info(
        "LangSmith tracing configured — project=%s endpoint=%s tracing=%s",
        settings.langchain_project,
        settings.langchain_endpoint,
        settings.langchain_tracing_v2,
    )


# Call immediately on import so any module that does
#   from backend.tracing import setup_tracing
# will have tracing active even before setup_tracing() is called explicitly.
setup_tracing()
