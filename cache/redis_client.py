"""Redis client and low-level cache helpers for AutoPilot Dev.

All cache keys follow the convention documented here so they are
predictable and easy to inspect with redis-cli:

    pr_diff:{owner}_{repo}_{pr_number}     TTL 3600s  — PR diff/metadata
    session:{session_id}:state             TTL 7200s  — LangGraph state snapshot

The ``r`` singleton is created once at import time using ``REDIS_URL``
from settings (never hardcoded).  All string values are automatically
decoded (``decode_responses=True``).
"""

from __future__ import annotations

import json
from typing import Any

import redis

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Shared Redis client ───────────────────────────────────────────────────────
# Created lazily so import-time failures are surfaced at call time, not startup.
_r: redis.Redis | None = None


def _client() -> redis.Redis:
    """Return (and lazily create) the shared Redis client."""
    global _r  # noqa: PLW0603
    if _r is None:
        _r = redis.from_url(settings.redis_url, decode_responses=True)
        logger.debug("Redis client created — url=%s", settings.redis_url)
    return _r


# ── Core helpers ──────────────────────────────────────────────────────────────

def cache_set(key: str, value: dict[str, Any], ttl_seconds: int = 3600) -> None:
    """Serialise *value* to JSON and store it in Redis with a TTL.

    Parameters
    ----------
    key:
        Cache key string.
    value:
        JSON-serialisable dict to store.
    ttl_seconds:
        Expiry time in seconds (default 3600 = 1 hour).
    """
    try:
        _client().setex(key, ttl_seconds, json.dumps(value, default=str))
        logger.info("[Redis] SET %s  (TTL: %ds)", key, ttl_seconds)
    except redis.RedisError as exc:
        logger.warning("[Redis] SET failed for key=%s: %s", key, exc)


def cache_get(key: str) -> dict[str, Any] | None:
    """Retrieve and deserialise a cached dict from Redis.

    Returns ``None`` on a cache miss or if Redis is unavailable.
    """
    try:
        raw = _client().get(key)
    except redis.RedisError as exc:
        logger.warning("[Redis] GET failed for key=%s: %s", key, exc)
        return None

    if raw:
        logger.info("[Redis] HIT  %s", key)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("[Redis] JSON decode error for key=%s: %s", key, exc)
            return None

    logger.info("[Redis] MISS %s", key)
    return None


def cache_delete(key: str) -> None:
    """Delete a key from Redis (no-op if the key does not exist)."""
    try:
        _client().delete(key)
        logger.debug("[Redis] DEL %s", key)
    except redis.RedisError as exc:
        logger.warning("[Redis] DEL failed for key=%s: %s", key, exc)


def cache_exists(key: str) -> bool:
    """Return ``True`` if *key* exists in Redis, ``False`` otherwise."""
    try:
        return _client().exists(key) == 1
    except redis.RedisError as exc:
        logger.warning("[Redis] EXISTS failed for key=%s: %s", key, exc)
        return False
