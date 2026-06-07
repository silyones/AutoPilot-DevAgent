"""Conditional edge routing functions for the AutoPilot Dev StateGraph.

Each function receives the current GraphState and returns a string key
that LangGraph maps to the next node via ``add_conditional_edges``.
"""

from __future__ import annotations

from backend.utils.logger import get_logger
from graph.state import GraphState

logger = get_logger(__name__)


def route_on_severity(state: GraphState) -> str:
    """Route after ``review_node`` based on whether bugs were found.

    Returns
    -------
    ``"fix_node"``
        When ``review_report["has_bugs"]`` is ``True`` — send to Fixer Agent.
    ``"document_node"``
        When no bugs were found — skip fixing and go straight to documentation.
    """
    review = state.get("review_report", {})
    has_bugs: bool = review.get("has_bugs", False)

    if has_bugs:
        total = review.get("total_issues", 0)
        logger.info(
            "route_on_severity: bugs detected (total_issues=%d) → fix_node", total
        )
        return "fix_node"

    logger.info("route_on_severity: no bugs found → document_node")
    return "document_node"


def route_on_test_result(state: GraphState) -> str:
    """Route after ``test_node`` — implements the retry loop.

    Decision table
    --------------
    test_status == "PASS"                           → ``"document_node"``
    test_status in ("FAIL", "TIMEOUT")
        AND retry_count < max_retries               → ``"fix_node"``  (retry loop)
        AND retry_count >= max_retries              → ``"human_review_node"``

    Returns
    -------
    One of: ``"document_node"``, ``"fix_node"``, ``"human_review_node"``
    """
    test_status: str = state.get("test_status", "PENDING")
    retry_count: int = state.get("retry_count", 0)
    max_retries: int = state.get("max_retries", 3)

    if test_status == "PASS":
        logger.info("route_on_test_result: tests PASSED → document_node")
        return "document_node"

    if test_status in ("FAIL", "TIMEOUT"):
        if retry_count < max_retries:
            logger.info(
                "route_on_test_result: tests %s — retry %d/%d → fix_node",
                test_status,
                retry_count,
                max_retries,
            )
            return "fix_node"

        logger.warning(
            "route_on_test_result: tests %s — max retries (%d) reached → human_review_node",
            test_status,
            max_retries,
        )
        return "human_review_node"

    # Unexpected status — treat as failure and escalate
    logger.error(
        "route_on_test_result: unexpected test_status=%r with retry_count=%d/%d → human_review_node",
        test_status,
        retry_count,
        max_retries,
    )
    return "human_review_node"
