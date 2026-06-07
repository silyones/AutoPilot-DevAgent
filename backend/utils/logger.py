"""Structured logger factory for AutoPilot Dev.

Usage:
    from backend.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Starting review agent", extra={"pr_url": pr_url})
"""

import logging
import sys
from functools import lru_cache


class _JsonFormatter(logging.Formatter):
    """Simple structured-ish formatter that emits key=value pairs."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        base = super().format(record)
        # Append any extra fields (e.g. pr_url, session_id) passed via `extra`
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            }
        }
        if extras:
            kv = " ".join(f"{k}={v!r}" for k, v in extras.items())
            return f"{base} | {kv}"
        return base


def _build_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    formatter = _JsonFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


@lru_cache(maxsize=None)
def get_logger(name: str) -> logging.Logger:
    """Return (and cache) a configured logger for *name*.

    The log level is read once from ``settings.LOG_LEVEL`` at first call.
    Subsequent calls for the same *name* return the cached instance.
    """
    # Import here to avoid circular imports at module load time
    from backend.config import settings  # noqa: PLC0415

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_build_handler())
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    return logger
