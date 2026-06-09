"""Integration tests for the LangGraph pipeline (graph/workflow.py).

The GitHub API call is mocked so these tests run fully offline and fast.
All 4 CrewAI agents run for real — they call Groq via the env-configured key.

Pytest marks:
    graph  — all tests in this file
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import pytest

from graph.workflow import graph
from graph.state import GraphState

# ── Shared fake PR data ───────────────────────────────────────────────────────

FAKE_PR: dict = {
    "pr_number": 999,
    "title": "Fix division by zero in arithmetic module",
    "description": "This PR fixes a critical divide-by-zero bug.",
    "author": "test-bot",
    "base_branch": "main",
    "head_branch": "fix/divide-by-zero",
    "diff": "def divide(a, b):\n-    return a / b\n+    if b == 0:\n+        raise ValueError('Division by zero')\n+    return a / b",
    "files_changed": [
        {
            "filename": "math_utils.py",
            "status": "modified",
            "additions": 3,
            "deletions": 1,
            "patch": "-    return a / b\n+    if b == 0:\n+        raise ValueError('Division by zero')\n+    return a / b",
        }
    ],
    "pr_url": "https://github.com/test/repo/pull/999",
}


def _initial_state(pr_url: str = "https://github.com/test/repo/pull/999") -> dict:
    """Build a minimal valid initial GraphState dict."""
    return {
        "pr_url": pr_url,
        "session_id": str(uuid.uuid4()),
        "pr_data": {},
        "review_report": {},
        "patches": [],
        "test_results": {},
        "documentation": {},
        "retry_count": 0,
        "max_retries": 3,
        "test_status": "PENDING",
        "current_agent": "",
        "error": None,
        "agent_trace": [],
        "final_report": {},
        "start_time": time.time(),
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.graph
class TestGraphPipeline:
    """Full graph invocation tests with mocked GitHub fetch."""

    def test_final_report_has_required_keys(self):
        """Graph must produce a final_report with all expected top-level keys."""
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state())

        report = result.get("final_report", {})
        for key in ("pr_url", "status", "review", "agent_trace"):
            assert key in report, f"Missing key in final_report: {key!r}"

    def test_status_is_valid_enum_value(self):
        """Status must be one of the recognised pipeline outcomes."""
        valid_statuses = {"PASSED", "FIXED", "NEEDS_HUMAN_REVIEW"}
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state())

        status = result["final_report"].get("status")
        assert status in valid_statuses, f"Unexpected status: {status!r}"

    def test_agent_trace_is_non_empty(self):
        """At minimum the Fetcher and Reviewer steps must be in the trace."""
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state())

        trace = result["final_report"].get("agent_trace", [])
        assert len(trace) >= 2

    def test_pr_url_preserved_in_report(self):
        """The pr_url passed in must be echoed in the final report."""
        pr_url = "https://github.com/test/repo/pull/999"
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state(pr_url))

        assert result["final_report"]["pr_url"] == pr_url

    def test_duration_is_positive(self):
        """total_duration_seconds should be a positive number."""
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state())

        duration = result["final_report"].get("total_duration_seconds", 0)
        assert duration > 0

    def test_review_report_has_findings(self):
        """The review field must contain a findings list (may be empty)."""
        with patch("graph.nodes.fetch_pr_data", return_value=FAKE_PR):
            result = graph.invoke(_initial_state())

        review = result["final_report"].get("review", {})
        assert "findings" in review
        assert isinstance(review["findings"], list)

    def test_fetch_error_sets_error_field(self):
        """If GitHub fetch raises, the graph should record the error gracefully."""
        with patch("graph.nodes.fetch_pr_data", side_effect=RuntimeError("GitHub 403")):
            result = graph.invoke(_initial_state())

        # The graph should not crash — it should record the error
        assert result is not None
        # error field should be populated or final_report should exist
        assert "final_report" in result or result.get("error") is not None
