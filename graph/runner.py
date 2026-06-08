"""AutoPilot Dev — graph runner entry point.

``run_autopilot`` is the single public function that FastAPI, the CLI, and
tests call to execute the full LangGraph pipeline for a given PR URL.
"""

from __future__ import annotations

import time
import uuid

from backend.config import settings
from backend.utils.logger import get_logger
from graph.workflow import graph

logger = get_logger(__name__)


def run_autopilot(pr_url: str) -> dict:
    """Run the full AutoPilot Dev graph for a given PR URL.

    Parameters
    ----------
    pr_url:
        A GitHub pull request URL, e.g.
        ``https://github.com/owner/repo/pull/42``

    Returns
    -------
    dict
        The ``final_report`` field from the completed graph state —
        a ``DevReport``-shaped dict with status, review, patches,
        test results, documentation, and agent trace.
    """
    session_id = str(uuid.uuid4())
    logger.info("run_autopilot: starting session=%s pr_url=%s", session_id, pr_url)

    initial_state = {
        "pr_url": pr_url,
        "session_id": session_id,
        "pr_data": {},
        "review_report": {},
        "patches": [],
        "test_results": {},
        "documentation": {},
        "retry_count": 0,
        "max_retries": settings.max_fix_retries,
        "test_status": "PENDING",
        "current_agent": "",
        "error": None,
        "agent_trace": [],
        "final_report": {},
        "start_time": time.time(),
    }

    result = graph.invoke(initial_state)

    final_report = result.get("final_report", {})
    logger.info(
        "run_autopilot: complete session=%s status=%s duration=%.2fs",
        session_id,
        final_report.get("status", "UNKNOWN"),
        final_report.get("total_duration_seconds", 0.0),
    )
    return final_report
