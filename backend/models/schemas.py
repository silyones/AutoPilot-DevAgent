"""Pydantic v2 schemas for AutoPilot Dev.

All models use Pydantic v2 syntax (model_config instead of class Config).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PRStatus(str, Enum):
    PASSED = "PASSED"
    FIXED = "FIXED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"


# ── Review models ─────────────────────────────────────────────────────────────


class Finding(BaseModel):
    """A single issue discovered during PR review."""

    severity: Severity
    description: str
    file: str
    line: int | None = None
    category: str  # e.g. "logic_bug", "security", "style"


class ReviewReport(BaseModel):
    """Aggregated output from the code-review agent."""

    findings: List[Finding]
    total_issues: int
    has_bugs: bool


# ── Fix / patch models ────────────────────────────────────────────────────────


class Patch(BaseModel):
    """A single file-level fix proposed by the fix agent."""

    file: str
    original: str
    fixed: str
    explanation: str


# ── Test models ───────────────────────────────────────────────────────────────


class TestReport(BaseModel):
    """Results from running the test suite after a fix attempt."""

    passed: int
    failed: int
    new_tests_added: int
    output: str
    status: str  # "PASS" | "FAIL" | "TIMEOUT"


# ── Documentation models ──────────────────────────────────────────────────────


class Documentation(BaseModel):
    """Generated docs produced by the documentation agent."""

    docstrings: str
    changelog: str
    summary: str


# ── Agent trace ───────────────────────────────────────────────────────────────


class AgentStep(BaseModel):
    """A single recorded step in the multi-agent execution trace."""

    agent: str
    action: str
    result: str
    timestamp: datetime


# ── Top-level report ──────────────────────────────────────────────────────────


class DevReport(BaseModel):
    """Complete output of one AutoPilot Dev run for a given PR."""

    pr_url: str
    status: PRStatus
    review: ReviewReport | None = None
    patches: List[Patch] = []
    test_results: TestReport | None = None
    documentation: Documentation | None = None
    agent_trace: List[AgentStep] = []
    retry_count: int = 0
    total_duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── API request / response ────────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """Incoming request payload to trigger a PR review."""

    pr_url: str


class ReviewResponse(BaseModel):
    """Top-level API response envelope."""

    success: bool
    session_id: str | None = None
    data: DevReport | None = None
    error: str | None = None
