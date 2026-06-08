"""LangGraph session-state persistence via Redis.

During the fix → test → fix retry loop, the graph state can be snapshotted
here so that a crash or restart can resume from where it left off rather than
re-running every earlier agent.

Key schema
----------
    session:{session_id}:state    TTL 7200s (2 hours)
"""

from __future__ import annotations

from cache.redis_client import cache_delete, cache_get, cache_set
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SESSION_TTL = 7200  # 2 hours


def save_session_state(session_id: str, state: dict, ttl: int = _SESSION_TTL) -> None:
    """Snapshot the current LangGraph graph state for *session_id*.

    Called after each node completes so that a resume is always possible.

    Parameters
    ----------
    session_id:
        The UUID that identifies this pipeline run.
    state:
        The full ``GraphState`` dict as returned by the last node.
    ttl:
        Redis TTL in seconds (default 7200 = 2 hours).
    """
    key = f"session:{session_id}:state"
    logger.debug("save_session_state: session_id=%s", session_id)
    cache_set(key, state, ttl_seconds=ttl)


def get_session_state(session_id: str) -> dict | None:
    """Retrieve the last saved graph state for *session_id*.

    Returns ``None`` if no snapshot exists or it has expired.
    """
    key = f"session:{session_id}:state"
    state = cache_get(key)
    if state is not None:
        logger.debug("get_session_state: HIT  session_id=%s", session_id)
    else:
        logger.debug("get_session_state: MISS session_id=%s", session_id)
    return state


def delete_session_state(session_id: str) -> None:
    """Remove the saved state for *session_id* (called on pipeline completion)."""
    key = f"session:{session_id}:state"
    logger.debug("delete_session_state: session_id=%s", session_id)
    cache_delete(key)
