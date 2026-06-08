"""AutoPilot Dev API routes.

Endpoints
---------
POST /api/review
    Accepts a PR URL, starts the graph pipeline as a background task,
    and returns a session_id immediately.  The client connects to the
    WebSocket endpoint to receive live progress events.

WS   /api/ws/{session_id}
    Streams JSON events to the browser as the pipeline runs:
      {"type": "start",    "session_id": ..., "message": ...}
      {"type": "progress", "session_id": ..., "agent": ..., "message": ...}
      {"type": "complete", "session_id": ..., "report": {...}}
      {"type": "error",    "session_id": ..., "message": ...}

GET  /api/reports
    Returns all past DevReports ordered newest-first.

GET  /api/reports/{report_id}
    Returns a single report by UUID.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.websocket_manager import manager
from backend.models.schemas import ReviewRequest, ReviewResponse
from backend.utils.logger import get_logger
from db.database import SessionLocal, get_db
from db.models import DevReportORM
from graph.runner import run_autopilot

logger = get_logger(__name__)
router = APIRouter()


# ── POST /api/review ──────────────────────────────────────────────────────────

@router.post("/review", response_model=ReviewResponse, tags=["Reviews"])
async def start_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
) -> ReviewResponse:
    """Start an autonomous PR review pipeline.

    Returns immediately with a ``session_id``.  Connect to
    ``/api/ws/{session_id}`` to receive live progress events.
    """
    session_id = str(uuid.uuid4())
    logger.info("start_review: session_id=%s pr_url=%s", session_id, request.pr_url)
    background_tasks.add_task(run_review_task, request.pr_url, session_id)
    return ReviewResponse(success=True, session_id=session_id)


# ── Background task ───────────────────────────────────────────────────────────

async def run_review_task(pr_url: str, session_id: str) -> None:
    """Run the LangGraph pipeline in a thread and push WS events at each stage.

    The LangGraph graph (and all CrewAI agent calls) are synchronous, so we
    wrap them in ``asyncio.to_thread`` to avoid blocking the event loop.
    """
    logger.info("run_review_task: starting session_id=%s", session_id)

    # ── Start event ───────────────────────────────────────────────────────────
    await manager.send_update(session_id, {
        "type": "start",
        "session_id": session_id,
        "message": "AutoPilot Dev pipeline started. Fetching PR…",
    })

    try:
        # ── Run pipeline (sync → wrapped in thread) ────────────────────────────
        report: dict = await asyncio.to_thread(run_autopilot, pr_url)

        # ── Progress: surface agent trace steps to the client ─────────────────
        for step in report.get("agent_trace", []):
            await manager.send_update(session_id, {
                "type": "progress",
                "session_id": session_id,
                "agent": step.get("agent", ""),
                "action": step.get("action", ""),
                "message": step.get("result", ""),
                "timestamp": step.get("timestamp", ""),
            })

        # ── Complete event ─────────────────────────────────────────────────────
        await manager.send_update(session_id, {
            "type": "complete",
            "session_id": session_id,
            "report": report,
        })

        # ── Persist to PostgreSQL ──────────────────────────────────────────────
        await save_report_to_db(report, session_id)

    except Exception as exc:
        logger.error("run_review_task failed session_id=%s: %s", session_id, exc, exc_info=True)
        await manager.send_update(session_id, {
            "type": "error",
            "session_id": session_id,
            "message": str(exc),
        })


# ── WebSocket /api/ws/{session_id} ────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket connection for live pipeline progress updates."""
    await manager.connect(session_id, websocket)
    try:
        # Keep the connection alive by reading (client may send pings)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as exc:
        logger.warning("WS session_id=%s terminated with error: %s", session_id, exc)
        manager.disconnect(session_id)


# ── GET /api/reports ──────────────────────────────────────────────────────────

@router.get("/reports", tags=["Reports"])
async def get_reports(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return a paginated list of all past DevReports, newest first."""
    stmt = (
        select(DevReportORM)
        .order_by(DevReportORM.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_orm_to_dict(row) for row in rows]


# ── GET /api/reports/{report_id} ──────────────────────────────────────────────

@router.get("/reports/{report_id}", tags=["Reports"])
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return a single DevReport by UUID."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report_id — must be a UUID.")

    stmt = select(DevReportORM).where(DevReportORM.id == report_uuid)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")

    return _orm_to_dict(row)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def save_report_to_db(report: dict, session_id: str) -> None:
    """Persist a completed DevReport to the ``dev_reports`` table.

    Uses its own session (not injected via Depends) because it runs inside
    a background task that has no request context.
    """
    logger.info("save_report_to_db: session_id=%s status=%s", session_id, report.get("status"))
    try:
        async with SessionLocal() as db:
            record = DevReportORM(
                id=uuid.UUID(session_id),          # reuse session_id as PK
                pr_url=report.get("pr_url", ""),
                status=report.get("status", "UNKNOWN"),
                report=report,                      # full dict → JSONB
                agent_trace=report.get("agent_trace", []),
                retry_count=report.get("retry_count", 0),
                duration_seconds=report.get("total_duration_seconds"),
            )
            db.add(record)
            await db.commit()
            logger.info("save_report_to_db: saved id=%s", session_id)
    except Exception as exc:
        logger.error("save_report_to_db failed session_id=%s: %s", session_id, exc, exc_info=True)


def _orm_to_dict(row: DevReportORM) -> dict[str, Any]:
    """Serialise a DevReportORM row to a plain dict for JSON responses."""
    return {
        "id": str(row.id),
        "pr_url": row.pr_url,
        "status": row.status,
        "report": row.report,
        "agent_trace": row.agent_trace,
        "retry_count": row.retry_count,
        "duration_seconds": row.duration_seconds,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
