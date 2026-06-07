"""LangGraph state definition for AutoPilot Dev.

GraphState is the single shared dictionary that flows through every node
in the StateGraph. All fields are typed so LangGraph can validate transitions.

The ``agent_trace`` field uses ``Annotated[List[dict], operator.add]`` which
tells LangGraph to *merge* (append) values rather than overwrite them — each
node safely appends its own AgentStep without seeing the full list.
"""

from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict


class GraphState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    pr_url: str
    session_id: str

    # ── PR data fetched from GitHub ────────────────────────────────────────────
    pr_data: dict  # raw output of fetch_pr_data()

    # ── Agent outputs (stored as dicts matching Pydantic schema shapes) ────────
    review_report: dict   # ReviewReport
    patches: List[dict]   # List[Patch]
    test_results: dict    # TestReport
    documentation: dict   # Documentation

    # ── Control flow ───────────────────────────────────────────────────────────
    retry_count: int
    max_retries: int
    test_status: str      # "PASS" | "FAIL" | "TIMEOUT" | "PENDING"
    current_agent: str    # name of the currently active agent (for WebSocket)
    error: Optional[str]

    # ── Audit trail (append-only — LangGraph merges with operator.add) ─────────
    agent_trace: Annotated[List[dict], operator.add]

    # ── Final output ───────────────────────────────────────────────────────────
    final_report: dict    # DevReport as dict
    start_time: float     # time.time() at graph entry — used for duration calc
