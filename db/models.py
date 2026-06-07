"""SQLAlchemy ORM models for AutoPilot Dev.

Maps to the PostgreSQL database defined in DATABASE_URL.
The `dev_reports` table stores the full DevReport as JSONB so that
evolving schema fields don't require a migration for every field change.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Float, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID

from db.database import Base


class DevReportORM(Base):
    """Persistent record for a single AutoPilot Dev PR analysis run."""

    __tablename__ = "dev_reports"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )

    # ── PR metadata ───────────────────────────────────────────────────────────
    pr_url: str = Column(Text, nullable=False)
    status: str = Column(String(50), nullable=True)

    # ── JSONB blobs ───────────────────────────────────────────────────────────
    # Stores the full serialised DevReport (review, patches, test_results, docs)
    report: dict = Column(JSONB, nullable=True)
    # Stores the List[AgentStep] trace separately for easier querying
    agent_trace: list = Column(JSONB, nullable=True, default=list)

    # ── Run statistics ────────────────────────────────────────────────────────
    retry_count: int = Column(Integer, default=0, nullable=False)
    duration_seconds: float = Column(Float, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: datetime = Column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DevReportORM id={self.id!r} pr_url={self.pr_url!r} "
            f"status={self.status!r}>"
        )
