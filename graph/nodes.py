"""LangGraph node functions for AutoPilot Dev — Phase 5 (real agent calls).

Each node calls the real CrewAI agent and returns a partial dict that
LangGraph merges into the shared GraphState.

The ``agent_trace`` field uses ``Annotated[List[dict], operator.add]``, so
each node must return a *new list* containing only its own step — LangGraph
appends it automatically.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from agents.documenter import run_documenter
from agents.fixer import run_fixer
from agents.reviewer import run_reviewer
from agents.tester import run_tester
from backend.utils.logger import get_logger
from graph.state import GraphState
from tools.github_tool import fetch_pr_data

logger = get_logger(__name__)


# ── Helper ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _step(agent: str, action: str, result: str) -> dict:
    return {"agent": agent, "action": action, "result": result, "timestamp": _now_iso()}


# ── Node 1: Fetch PR ──────────────────────────────────────────────────────────

def fetch_pr_node(state: GraphState) -> dict:
    """Fetch PR diff and metadata from GitHub."""
    pr_url: str = state["pr_url"]
    logger.info("[fetch_pr_node] Fetching PR: %s", pr_url)

    try:
        pr_data = fetch_pr_data(pr_url)
        summary = (
            f"Fetched PR: {pr_data.get('title')} — "
            f"{len(pr_data.get('files_changed', []))} files changed"
        )
        error = None
    except Exception as exc:
        pr_data = {}
        summary = f"Failed to fetch PR: {exc}"
        error = str(exc)
        logger.error("[fetch_pr_node] %s", summary)

    return {
        "pr_data": pr_data,
        "current_agent": "GitHub Fetcher",
        "agent_trace": [_step("GitHub Fetcher", "fetch_pr", summary)],
        "error": error,
    }


# ── Node 2: Review ────────────────────────────────────────────────────────────

def review_node(state: GraphState) -> dict:
    """Run the Reviewer Agent against the fetched PR diff."""
    logger.info("[review_node] Running Reviewer Agent")

    review_report = run_reviewer(state["pr_data"])

    summary = (
        f"Found {review_report['total_issues']} issues. "
        f"Has bugs: {review_report['has_bugs']}"
    )
    logger.info("[review_node] %s", summary)

    return {
        "review_report": review_report,
        "current_agent": "Reviewer Agent",
        "agent_trace": [_step("Reviewer Agent", "review_pr", summary)],
    }


# ── Node 3: Fix ───────────────────────────────────────────────────────────────

def fix_node(state: GraphState) -> dict:
    """Run the Fixer Agent. Passes previous test error on retries."""
    retry_count: int = state.get("retry_count", 0)
    logger.info("[fix_node] Running Fixer Agent (attempt %d)", retry_count + 1)

    # On retries, pass the previous test output so the agent self-corrects
    previous_error = ""
    if retry_count > 0 and state.get("test_results"):
        previous_error = state["test_results"].get("output", "")

    fix_result = run_fixer(state["review_report"], state["pr_data"], previous_error)
    patches = fix_result.get("patches", [])
    new_retry_count = retry_count + 1

    summary = f"Generated {len(patches)} patches on attempt {new_retry_count}"
    logger.info("[fix_node] %s", summary)

    return {
        "patches": patches,
        "retry_count": new_retry_count,
        "current_agent": "Fixer Agent",
        "agent_trace": [
            _step("Fixer Agent", f"fix_bugs_attempt_{new_retry_count}", summary)
        ],
    }


# ── Node 4: Test ──────────────────────────────────────────────────────────────

def test_node(state: GraphState) -> dict:
    """Run the Tester Agent to evaluate patches."""
    logger.info("[test_node] Running Tester Agent")

    test_results = run_tester(state["patches"], state["pr_data"])
    test_status = test_results.get("status", "FAIL")

    summary = (
        f"Status: {test_results['status']} | "
        f"Passed: {test_results['passed']} | "
        f"Failed: {test_results['failed']}"
    )
    logger.info("[test_node] %s", summary)

    return {
        "test_results": test_results,
        "test_status": test_status,
        "current_agent": "Tester Agent",
        "agent_trace": [_step("Tester Agent", "run_tests", summary)],
    }


# ── Node 5: Document ──────────────────────────────────────────────────────────

def document_node(state: GraphState) -> dict:
    """Run the Documenter Agent."""
    logger.info("[document_node] Running Documenter Agent")

    documentation = run_documenter(
        state.get("patches", []),
        state["pr_data"],
        state.get("review_report", {}),
    )

    summary = "Generated docstrings, changelog, and summary"
    logger.info("[document_node] %s", summary)

    return {
        "documentation": documentation,
        "current_agent": "Documenter Agent",
        "agent_trace": [_step("Documenter Agent", "write_documentation", summary)],
    }


# ── Node 6: Compile Report ────────────────────────────────────────────────────

def compile_report_node(state: GraphState) -> dict:
    """Assemble the final DevReport from all agent outputs."""
    logger.info("[compile_report_node] Compiling final DevReport")

    duration = round(time.time() - state.get("start_time", time.time()), 2)
    retry_count: int = state.get("retry_count", 0)
    max_retries: int = state.get("max_retries", 3)
    test_status: str = state.get("test_status", "PENDING")
    patches: list = state.get("patches", [])

    # Preserve NEEDS_HUMAN_REVIEW if human_review_node already set it
    existing_status = state.get("final_report", {}).get("status", "")
    if existing_status == "NEEDS_HUMAN_REVIEW":
        status = "NEEDS_HUMAN_REVIEW"
    elif retry_count >= max_retries and test_status != "PASS":
        status = "NEEDS_HUMAN_REVIEW"
    elif patches and test_status == "PASS":
        status = "FIXED"
    else:
        status = "PASSED"

    final_report = {
        "pr_url": state.get("pr_url", ""),
        "status": status,
        "review": state.get("review_report"),
        "patches": patches,
        "test_results": state.get("test_results") or None,
        "documentation": state.get("documentation"),
        "agent_trace": state.get("agent_trace", []),
        "retry_count": retry_count,
        "total_duration_seconds": duration,
        "created_at": _now_iso(),
    }

    summary = f"Report compiled — status={status} duration={duration}s"
    logger.info("[compile_report_node] %s", summary)

    return {
        "final_report": final_report,
        "current_agent": "Report Compiler",
        "agent_trace": [_step("Report Compiler", "compile_dev_report", summary)],
    }


# ── Node 7: Human Review ──────────────────────────────────────────────────────

def human_review_node(state: GraphState) -> dict:
    """Escalation node — max retries exhausted."""
    retry_count: int = state.get("retry_count", 0)
    logger.warning(
        "[human_review_node] Max retries reached (%d). Escalating to human review.",
        retry_count,
    )

    summary = (
        f"Failed after {retry_count} attempt(s). Manual review required."
    )

    return {
        "final_report": {
            "pr_url": state.get("pr_url", ""),
            "status": "NEEDS_HUMAN_REVIEW",
        },
        "current_agent": "System",
        "agent_trace": [_step("System", "escalate_to_human", summary)],
    }
