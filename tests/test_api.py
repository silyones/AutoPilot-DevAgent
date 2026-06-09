"""FastAPI endpoint tests using TestClient (no live server required).

These tests exercise the HTTP layer without making any real agent calls.
The LangGraph pipeline is stubbed so tests run in milliseconds.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Import tracing first (mirrors api/main.py) so env vars are set before LangGraph loads
import backend.tracing  # noqa: F401

from api.main import app

client = TestClient(app)


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "AutoPilot Dev"


# ── POST /api/review ──────────────────────────────────────────────────────────

class TestPostReview:
    def test_valid_pr_url_returns_200_with_session_id(self):
        with patch("api.routes.run_autopilot", return_value={}):
            resp = client.post(
                "/api/review",
                json={"pr_url": "https://github.com/tiangolo/fastapi/pull/1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "session_id" in data
        assert data["session_id"] is not None

    def test_session_id_is_valid_uuid(self):
        import uuid
        with patch("api.routes.run_autopilot", return_value={}):
            resp = client.post(
                "/api/review",
                json={"pr_url": "https://github.com/tiangolo/fastapi/pull/1"},
            )
        session_id = resp.json()["session_id"]
        # Should not raise
        uuid.UUID(session_id)

    def test_empty_pr_url_returns_422(self):
        resp = client.post("/api/review", json={"pr_url": ""})
        # Pydantic min-length or field validation kicks in
        # FastAPI returns 422 for invalid input
        assert resp.status_code in (400, 422)

    def test_missing_pr_url_field_returns_422(self):
        resp = client.post("/api/review", json={})
        assert resp.status_code == 422

    def test_malformed_json_returns_422(self):
        resp = client.post(
            "/api/review",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ── GET /api/reports ──────────────────────────────────────────────────────────

def _make_db_override(rows=None, single_row="__unset__"):
    """Return a get_db dependency override that produces a fake AsyncSession.

    SQLAlchemy's Result object methods (scalars, all, scalar_one_or_none) are
    **synchronous** — only session.execute() is awaited.  We therefore use a
    regular MagicMock for the Result and AsyncMock only for execute().
    """
    from unittest.mock import MagicMock
    from db.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _fake_db():
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        if rows is not None:
            result.scalars.return_value.all.return_value = rows
        if single_row != "__unset__":
            # Use a plain function so it's not an AsyncMock (scalar_one_or_none is sync)
            result.scalar_one_or_none.return_value = single_row
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        yield session

    return get_db, _fake_db



class TestGetReports:
    def test_returns_200(self):
        get_db, override = _make_db_override(rows=[])
        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/reports")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_returns_list(self):
        get_db, override = _make_db_override(rows=[])
        app.dependency_overrides[get_db] = override
        try:
            resp = client.get("/api/reports")
        finally:
            app.dependency_overrides.clear()
        assert isinstance(resp.json(), list)

    def test_invalid_report_id_returns_400(self):
        resp = client.get("/api/reports/not-a-uuid")
        assert resp.status_code == 400

    def test_nonexistent_report_uuid_returns_404(self):
        import uuid
        get_db, override = _make_db_override(single_row=None)
        fake_id = str(uuid.uuid4())
        app.dependency_overrides[get_db] = override
        try:
            resp = client.get(f"/api/reports/{fake_id}")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 404
