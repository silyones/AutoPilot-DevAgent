"""LangGraph node functions for AutoPilot Dev.

Each function has the signature ``(state: GraphState) -> GraphState`` (or a
partial dict — LangGraph merges partial updates into the shared state).

Nodes marked **STUBBED** return realistic fake data that matches the Pydantic
schema shapes defined in ``backend/models/schemas.py``. They will be replaced
by real agent calls in Phase 5.

AgentStep format (matches ``backend/models/schemas.AgentStep``):
    {
        "agent": str,
        "action": str,
        "result": str,
        "timestamp": str  (ISO-8601)
    }
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from backend.models.schemas import PRStatus
from backend.utils.logger import get_logger
from graph.state import GraphState
from tools.github_tool import fetch_pr_data

logger = get_logger(__name__)


# ── Helper ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _step(agent: str, action: str, result: str) -> dict:
    """Build an AgentStep dict."""
    return {
        "agent": agent,
        "action": action,
        "result": result,
        "timestamp": _now_iso(),
    }


# ── Node 1: Fetch PR ──────────────────────────────────────────────────────────

def fetch_pr_node(state: GraphState) -> dict:
    """Fetch PR diff and metadata from GitHub and populate ``pr_data``."""
    pr_url: str = state["pr_url"]
    logger.info("[fetch_pr_node] Fetching PR: %s", pr_url)

    try:
        pr_data = fetch_pr_data(pr_url)
        result_summary = (
            f"Fetched PR #{pr_data['pr_number']} — "
            f"{len(pr_data['files_changed'])} file(s) changed"
        )
        logger.info("[fetch_pr_node] %s", result_summary)
        step = _step("GitHub Fetcher", f"fetch_pr_data({pr_url})", result_summary)
        error = None
    except Exception as exc:
        result_summary = f"Failed to fetch PR: {exc}"
        logger.error("[fetch_pr_node] %s", result_summary)
        step = _step("GitHub Fetcher", f"fetch_pr_data({pr_url})", result_summary)
        pr_data = {}
        error = str(exc)

    return {
        "pr_data": pr_data,
        "current_agent": "GitHub Fetcher",
        "agent_trace": [step],
        "error": error,
    }


# ── Node 2: Review ────────────────────────────────────────────────────────────

def review_node(state: GraphState) -> dict:
    """Run the Reviewer Agent.

    **STUBBED until Phase 5** — returns a realistic ReviewReport dict.
    """
    logger.info("[review_node] Running Reviewer Agent (STUBBED)")

    # STUB — will be replaced by real CrewAI / LangGraph agent call in Phase 5
    review_report: dict = {
        "findings": [
            {
                "severity": "high",
                "description": "Potential null pointer dereference when response is None",
                "file": "main.py",
                "line": 42,
                "category": "logic_bug",
            },
            {
                "severity": "medium",
                "description": "Missing input validation on user-supplied query parameter",
                "file": "api/routes.py",
                "line": 17,
                "category": "security",
            },
        ],
        "total_issues": 2,
        "has_bugs": True,
    }

    step = _step(
        "Reviewer Agent",
        "review_pr_diff",
        f"Found {review_report['total_issues']} issue(s); has_bugs={review_report['has_bugs']}",
    )
    logger.info("[review_node] Review complete — total_issues=%d", review_report["total_issues"])

    return {
        "review_report": review_report,
        "current_agent": "Reviewer Agent",
        "agent_trace": [step],
    }


# ── Node 3: Fix ───────────────────────────────────────────────────────────────

def fix_node(state: GraphState) -> dict:
    """Run the Fixer Agent.

    **STUBBED until Phase 5** — returns a realistic Patch list dict.
    Increments ``retry_count`` on every call (tracks retry loop iterations).
    """
    retry_count: int = state.get("retry_count", 0) + 1
    logger.info("[fix_node] Running Fixer Agent (STUBBED) — attempt %d", retry_count)

    # STUB — will be replaced by real agent call in Phase 5
    patches: list[dict] = [
        {
            "file": "main.py",
            "original": "result = response.data",
            "fixed": "result = response.data if response is not None else {}",
            "explanation": "Added None guard to prevent null pointer dereference on line 42.",
        },
        {
            "file": "api/routes.py",
            "original": "query = request.args.get('q')",
            "fixed": "query = request.args.get('q', '').strip()[:256]",
            "explanation": "Added stripping and length cap to sanitise user query input.",
        },
    ]

    step = _step(
        "Fixer Agent",
        f"generate_patches (attempt {retry_count})",
        f"Generated {len(patches)} patch(es) on retry attempt {retry_count}",
    )
    logger.info("[fix_node] Generated %d patch(es)", len(patches))

    return {
        "patches": patches,
        "retry_count": retry_count,
        "current_agent": "Fixer Agent",
        "agent_trace": [step],
    }


# ── Node 4: Test ──────────────────────────────────────────────────────────────

def test_node(state: GraphState) -> dict:
    """Run the Tester Agent.

    **STUBBED until Phase 5** — always returns PASS for now.
    """
    retry_count: int = state.get("retry_count", 0)
    logger.info("[test_node] Running Tester Agent (STUBBED) — after attempt %d", retry_count)

    # STUB — will be replaced by real agent call in Phase 5
    test_results: dict = {
        "passed": 14,
        "failed": 0,
        "new_tests_added": 2,
        "output": (
            "============================= test session starts ==============================\n"
            "collected 14 items\n\n"
            "tests/test_main.py ..........   [71%]\n"
            "tests/test_routes.py ....      [100%]\n\n"
            "============================== 14 passed in 1.23s =============================="
        ),
        "status": "PASS",
    }

    step = _step(
        "Tester Agent",
        "run_test_suite",
        f"Tests complete — passed={test_results['passed']} failed={test_results['failed']} status={test_results['status']}",
    )
    logger.info("[test_node] test_status=%s", test_results["status"])

    return {
        "test_results": test_results,
        "test_status": test_results["status"],
        "current_agent": "Tester Agent",
        "agent_trace": [step],
    }


# ── Node 5: Document ──────────────────────────────────────────────────────────

def document_node(state: GraphState) -> dict:
    """Run the Documenter Agent.

    **STUBBED until Phase 5** — returns realistic Documentation dict.
    """
    logger.info("[document_node] Running Documenter Agent (STUBBED)")

    pr_title: str = state.get("pr_data", {}).get("title", "PR")

    # STUB — will be replaced by real agent call in Phase 5
    documentation: dict = {
        "docstrings": (
            '"""Fetches PR data from GitHub and returns structured diff information.\n\n'
            "Args:\n    pr_url: Full GitHub pull request URL.\n\n"
            "Returns:\n    dict: PR metadata including diff, files changed, and author info.\n"
            '"""'
        ),
        "changelog": (
            f"## Changes in {pr_title}\n\n"
            "- Fixed null pointer dereference in response handler (main.py:42)\n"
            "- Added input validation and length cap on query parameter (api/routes.py:17)\n"
            "- Added 2 new unit tests covering edge cases\n"
        ),
        "summary": (
            f"This PR ({pr_title}) addresses 2 issues: a high-severity null pointer risk "
            "and a medium-severity missing input validation. Both are patched and covered by tests."
        ),
    }

    step = _step(
        "Documenter Agent",
        "generate_documentation",
        "Documentation generated: docstrings, changelog, and summary.",
    )
    logger.info("[document_node] Documentation complete")

    return {
        "documentation": documentation,
        "current_agent": "Documenter Agent",
        "agent_trace": [step],
    }


# ── Node 6: Compile Report ────────────────────────────────────────────────────

def compile_report_node(state: GraphState) -> dict:
    """Assemble the final DevReport from all agent outputs."""
    logger.info("[compile_report_node] Assembling final DevReport")

    duration: float = time.time() - state.get("start_time", time.time())
    retry_count: int = state.get("retry_count", 0)
    max_retries: int = state.get("max_retries", 3)
    test_results: dict = state.get("test_results", {})
    patches: list = state.get("patches", [])

    # ── Determine final status ─────────────────────────────────────────────────
    if state.get("final_report", {}).get("status") == PRStatus.NEEDS_HUMAN_REVIEW.value:
        # human_review_node already set this — preserve it
        status = PRStatus.NEEDS_HUMAN_REVIEW.value
    elif test_results.get("status") == "PASS" and patches:
        status = PRStatus.FIXED.value
    elif retry_count >= max_retries:
        status = PRStatus.NEEDS_HUMAN_REVIEW.value
    else:
        status = PRStatus.PASSED.value

    final_report: dict = {
        "pr_url": state.get("pr_url", ""),
        "status": status,
        "review": state.get("review_report"),
        "patches": patches,
        "test_results": test_results if test_results else None,
        "documentation": state.get("documentation"),
        "agent_trace": state.get("agent_trace", []),
        "retry_count": retry_count,
        "total_duration_seconds": round(duration, 3),
        "created_at": _now_iso(),
    }

    step = _step(
        "Report Compiler",
        "compile_dev_report",
        f"Final report assembled — status={status} duration={duration:.2f}s",
    )
    logger.info(
        "[compile_report_node] Report ready — status=%s duration=%.2fs",
        status,
        duration,
    )

    return {
        "final_report": final_report,
        "current_agent": "Report Compiler",
        "agent_trace": [step],
    }


# ── Node 7: Human Review ──────────────────────────────────────────────────────

def human_review_node(state: GraphState) -> dict:
    """Escalation node — triggered when max retries are exhausted.

    Marks the report as ``NEEDS_HUMAN_REVIEW`` and records the escalation
    in the agent trace before handing off to ``compile_report_node``.
    """
    retry_count: int = state.get("retry_count", 0)
    max_retries: int = state.get("max_retries", 3)

    logger.warning(
        "[human_review_node] Max retries reached (%d/%d). Escalating to human review.",
        retry_count,
        max_retries,
    )

    step = _step(
        "Escalation Handler",
        "escalate_to_human",
        (
            f"Automatic fix failed after {retry_count} attempt(s). "
            "Escalated to human review — manual intervention required."
        ),
    )

    # Seed final_report with NEEDS_HUMAN_REVIEW so compile_report_node preserves it
    partial_report: dict = {
        "pr_url": state.get("pr_url", ""),
        "status": PRStatus.NEEDS_HUMAN_REVIEW.value,
    }

    return {
        "final_report": partial_report,
        "current_agent": "Escalation Handler",
        "agent_trace": [step],
    }
