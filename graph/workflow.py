"""LangGraph StateGraph assembly for AutoPilot Dev.

``build_graph()`` wires all nodes and edges into a compiled LangGraph graph.
The exported ``graph`` singleton is what FastAPI and the WebSocket handler
invoke to run a PR review session.

Graph topology
--------------

    fetch_pr
        │
        ▼
    review ──── (has_bugs=False) ──────────────────────────────► document
        │                                                             │
        └── (has_bugs=True) ──► fix ──► test ──(PASS)───────────────┘
                                  ▲        │
                                  │        └──(FAIL/TIMEOUT, retries left)
                                  │                  │
                                  └──────────────────┘
                                           │
                                     (retries exhausted)
                                           │
                                           ▼
                                     human_review
                                           │
                                           ▼
                                    compile_report
                                           │
                                           ▼
                                          END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.utils.logger import get_logger
from graph.edges import route_on_severity, route_on_test_result
from graph.nodes import (
    compile_report_node,
    document_node,
    fetch_pr_node,
    fix_node,
    human_review_node,
    review_node,
    test_node,
)
from graph.state import GraphState

logger = get_logger(__name__)


def build_graph():
    """Construct and compile the AutoPilot Dev StateGraph.

    Returns
    -------
    CompiledGraph
        A LangGraph compiled graph ready to be invoked with an initial state dict.
    """
    logger.info("Building AutoPilot Dev StateGraph…")

    workflow = StateGraph(GraphState)

    # ── Register all nodes ────────────────────────────────────────────────────
    workflow.add_node("fetch_pr", fetch_pr_node)
    workflow.add_node("review", review_node)
    workflow.add_node("fix", fix_node)
    workflow.add_node("test", test_node)
    workflow.add_node("document", document_node)
    workflow.add_node("compile_report", compile_report_node)
    workflow.add_node("human_review", human_review_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    workflow.set_entry_point("fetch_pr")

    # ── Linear edges ──────────────────────────────────────────────────────────
    workflow.add_edge("fetch_pr", "review")   # always review after fetch
    workflow.add_edge("fix", "test")           # always test after a fix attempt
    workflow.add_edge("document", "compile_report")       # docs → final report
    workflow.add_edge("human_review", "compile_report")   # escalation → final report
    workflow.add_edge("compile_report", END)              # report → done

    # ── Conditional: after review (has bugs?) ─────────────────────────────────
    workflow.add_conditional_edges(
        "review",
        route_on_severity,
        {
            "fix_node": "fix",           # bugs found → Fixer Agent
            "document_node": "document", # clean → skip to documentation
        },
    )

    # ── Conditional: after test (retry loop) ─────────────────────────────────
    workflow.add_conditional_edges(
        "test",
        route_on_test_result,
        {
            "document_node": "document",           # tests pass → document
            "fix_node": "fix",                     # tests fail, retries left → fix again ↺
            "human_review_node": "human_review",   # retries exhausted → escalate
        },
    )

    compiled = workflow.compile()
    logger.info("StateGraph compiled successfully.")
    return compiled


# ── Singleton — import this in FastAPI / WebSocket handler ────────────────────
graph = build_graph()
