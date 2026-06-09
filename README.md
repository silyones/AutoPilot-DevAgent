# AutoPilot Dev

> **Autonomous GitHub PR Review & Bug-Fix System** — paste a PR URL, get a fully-reviewed, auto-fixed, tested, and documented codebase in seconds.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)

---

## What It Does

AutoPilot Dev is a **fully autonomous multi-agent AI pipeline** that takes a GitHub Pull Request URL as input and, without any human interaction, fetches the PR diff, runs a deep code review using AI agents, generates targeted bug fixes, executes test validation in a stateful retry loop (fix → test → fix until all tests pass), and produces professional documentation — all delivered in real time via a WebSocket-powered live activity feed. The complete `DevReport` is persisted to PostgreSQL and served via a REST API.

---

## Architecture

AutoPilot Dev uses a **LangGraph StateGraph** as the orchestration backbone. The graph is a directed state machine where each node is a CrewAI agent crew, and edges are conditionally routed based on the graph's shared state.

```
┌─────────────┐
│  fetch_pr   │  — GitHub API → PR diff, metadata, file tree
└──────┬──────┘
       ▼
┌─────────────┐
│   review    │  — Reviewer Agent → findings, severity, bug classification
└──────┬──────┘
       │  has_bugs?
       ├─── No ──────────────────────────────────────────────┐
       ▼                                                      │
┌─────────────┐                                              │
│     fix     │  — Fixer Agent → patches, self-aware retries │
└──────┬──────┘                                              │
       ▼                                                      │
┌─────────────┐                                              │
│    test     │  — Tester Agent → pytest simulation          │
└──────┬──────┘                                              │
       │  tests pass?                                         │
       ├─── No (retry_count < max) ──────→ back to fix       │
       ├─── No (max retries hit) ────────→ NEEDS_HUMAN_REVIEW │
       ▼                                                      │
┌─────────────┐                                              │
│   document  │  — Documenter Agent → docstrings, changelog  │
└──────┬──────┘                                              │
       ▼                                                      ▼
┌──────────────────────────────────────────────────────────────┐
│                 compile_report  →  DevReport                  │
└──────────────────────────────────────────────────────────────┘
```

**The fix → test retry loop is the key innovation.** On each retry, the Fixer agent receives its own previous attempt's output and the test failure report — enabling self-correction without human intervention.

---

## Tech Stack

| Technology | Role |
|---|---|
| **LangGraph** | StateGraph orchestrator — routes agents, manages shared state, drives the retry loop |
| **CrewAI** | Agent framework — each node wraps a `Crew` with a specialist `Agent` and `Task` |
| **Groq (LLaMA 3.3 70B)** | LLM backend — powers all 4 agents via the `groq/llama-3.3-70b-versatile` model |
| **GitHub API** | PR data source — fetches diffs, file trees, metadata via PyGithub |
| **FastAPI** | REST API server — `POST /api/review`, `GET /api/reports`, `GET /health` |
| **WebSocket** | Live streaming — pushes per-agent progress events to the browser in real time |
| **PostgreSQL** | Persistence — stores complete `DevReport` records as JSONB via SQLAlchemy async |
| **Redis** | Caching — PR diffs cached 1 hour (6000× speedup on repeat runs), session state 2 hours |
| **LangSmith** | Observability — traces every LLM call across all agents in the `autopilot_dev` project |
| **Docker** | Infrastructure — `docker-compose up` starts Postgres + Redis + API in one command |

---

## Project Structure

```
AutoPilot_Dev/
├── .env                      # API keys & config (never committed)
├── .env.example              # Template for .env
├── docker-compose.yml        # Postgres + Redis + API services
├── Dockerfile                # python:3.11-slim image
├── requirements.txt
├── alembic.ini
│
├── frontend/
│   └── index.html            # Single-file dark-theme UI (no dependencies)
│
├── api/                      # FastAPI application
│   ├── main.py               # App factory + CORS + startup hooks
│   ├── routes.py             # POST /review, WS /ws/{id}, GET /reports
│   └── websocket_manager.py  # ConnectionManager singleton
│
├── graph/                    # LangGraph pipeline
│   ├── state.py              # GraphState TypedDict
│   ├── nodes.py              # All node implementations (calls agents)
│   ├── workflow.py           # StateGraph topology + conditional edges
│   └── runner.py             # run_autopilot(pr_url) entry point
│
├── agents/                   # CrewAI agent modules
│   ├── base.py               # get_crewai_llm(), kickoff_with_retry(), parse_agent_json()
│   ├── reviewer.py           # Finds bugs, security issues, style problems
│   ├── fixer.py              # Generates targeted patches
│   ├── tester.py             # Simulates test suite execution
│   └── documenter.py         # Writes docstrings, changelog, summary
│
├── tools/                    # Pure utility functions
│   ├── github_tool.py        # fetch_pr_data() with Redis caching
│   └── code_analysis_tool.py # extract_functions(), detect_security_patterns()
│
├── backend/                  # Shared config & utilities
│   ├── config.py             # Pydantic Settings (reads .env)
│   ├── tracing.py            # LangSmith env var setup
│   ├── utils/logger.py       # Structured logging
│   └── models/schemas.py     # Pydantic v2 schemas (DevReport, Patch, etc.)
│
├── db/                       # Database layer
│   ├── database.py           # AsyncEngine, SessionLocal, get_db()
│   └── models.py             # DevReportORM (SQLAlchemy)
│
├── cache/                    # Redis caching layer
│   ├── redis_client.py       # cache_set/get/delete/exists
│   └── session_store.py      # save/get/delete_session_state
│
├── alembic/                  # DB migrations
│   └── versions/             # Migration scripts
│
└── tests/
    ├── test_github_tool.py   # parse_pr_url + detect_security_patterns
    ├── test_graph.py         # Full graph with mocked GitHub fetch
    └── test_api.py           # FastAPI endpoint tests (TestClient)
```

---

## Setup & Run

### Prerequisites
- **Python 3.11+**
- **Docker Desktop** (for Postgres + Redis)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/AutoPilot-Dev.git
cd AutoPilot-Dev

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in your GROQ_API_KEY, GITHUB_TOKEN, LANGCHAIN_API_KEY

# 5. Start Postgres + Redis
docker-compose up postgres redis -d

# 6. Run database migrations
alembic upgrade head

# 7. Start the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 8. Open the frontend
# Open frontend/index.html in your browser — no build step needed
```

### Full Docker Stack (all services in one command)

```bash
docker-compose up --build
```

Postgres, Redis, and the FastAPI server start together with health-checked ordering.

---

### Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (get from console.groq.com) |
| `GROQ_MODEL` | Model name (default: `llama-3.3-70b-versatile`) |
| `GITHUB_TOKEN` | GitHub personal access token |
| `LANGCHAIN_API_KEY` | LangSmith API key (for tracing) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `POSTGRES_USER` | Postgres username (used by Docker Compose) |
| `POSTGRES_PASSWORD` | Postgres password (used by Docker Compose) |
| `POSTGRES_DB` | Database name (used by Docker Compose) |

---

### Example API Call

```bash
# Start a review (returns immediately with session_id)
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "https://github.com/tiangolo/fastapi/pull/1"}'

# Response:
# {"success": true, "session_id": "a3f1c2d4-...", "data": null, "error": null}

# Then connect WebSocket at: ws://localhost:8000/api/ws/{session_id}
# Or just open frontend/index.html
```

### Sample DevReport Output

```json
{
  "pr_url": "https://github.com/tiangolo/fastapi/pull/1",
  "status": "FIXED",
  "review": {
    "findings": [
      {
        "severity": "high",
        "description": "Missing input validation on path parameter — allows negative float values",
        "file": "tests/test_tutorial/test_path_params/test_tutorial004.py",
        "line": 12,
        "category": "logic_bug"
      }
    ],
    "total_issues": 5,
    "has_bugs": true
  },
  "patches": [
    {
      "file": "tests/test_tutorial/test_path_params/test_tutorial004.py",
      "original": "def get_path_param_gt(item_id: float = Path(..., gt=0)):",
      "fixed": "def get_path_param_gt(item_id: float = Path(..., gt=0, description='Must be greater than 0')):",
      "explanation": "Added description to improve API documentation clarity"
    }
  ],
  "test_results": {
    "passed": 18,
    "failed": 0,
    "new_tests_added": 2,
    "output": "18 passed in 0.43s",
    "status": "PASS"
  },
  "documentation": {
    "docstrings": "def get_path_param_gt(item_id: float):\n    \"\"\"Return item_id if it is greater than 0.\"\"\"\n    ...",
    "changelog": "## [Unreleased]\n### Fixed\n- Added input validation for path parameters",
    "summary": "This PR adds tests for FastAPI path parameter validation endpoints."
  },
  "agent_trace": [
    {"agent": "GitHub Fetcher", "action": "fetch_pr", "result": "Fetched PR: Add tests for path endpoints — 2 files changed", "timestamp": "2026-06-08T06:29:42Z"},
    {"agent": "Reviewer Agent", "action": "review_pr", "result": "Found 5 issues. Has bugs: True", "timestamp": "2026-06-08T06:29:43Z"},
    {"agent": "Fixer Agent", "action": "fix_bugs_attempt_1", "result": "Generated 10 patches on attempt 1", "timestamp": "2026-06-08T06:29:47Z"},
    {"agent": "Tester Agent", "action": "run_tests", "result": "Status: PASS | Passed: 18 | Failed: 0", "timestamp": "2026-06-08T06:29:48Z"},
    {"agent": "Documenter Agent", "action": "write_documentation", "result": "Generated docstrings, changelog, and summary", "timestamp": "2026-06-08T06:30:00Z"}
  ],
  "retry_count": 1,
  "total_duration_seconds": 21.35,
  "created_at": "2026-06-08T06:30:00Z"
}
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run only fast offline tests (skip graph integration tests)
pytest tests/test_github_tool.py tests/test_api.py -v

# Run graph tests (calls Groq — requires GROQ_API_KEY)
pytest tests/test_graph.py -v -m graph
```

---

## Agentic AI Concepts Demonstrated

| Concept | Implementation |
|---|---|
| **LangGraph StateGraph with conditional routing** | `graph/workflow.py` — nodes connected by `add_conditional_edges` that inspect `test_status` and `retry_count` |
| **Stateful retry loop** | fix → test → fix, up to `MAX_FIX_RETRIES` iterations; state is shared across the loop via `GraphState` |
| **Hierarchical multi-agent topology** | 4 specialist CrewAI agents (`Reviewer`, `Fixer`, `Tester`, `Documenter`) orchestrated by LangGraph as a manager |
| **CrewAI crew pattern inside LangGraph nodes** | Each node instantiates a `Crew(agents=[...], tasks=[...])` and calls `kickoff_with_retry()` |
| **Self-improving agent** | On each retry, the Fixer receives its previous patches and the test failure output — enabling targeted self-correction |
| **WebSocket live activity streaming** | `api/websocket_manager.py` — `ConnectionManager` pushes `progress` events per agent step, `complete` event on finish |
| **Redis caching for GitHub API** | `cache/redis_client.py` + `tools/github_tool.py` — PR diffs cached at `pr_diff:{owner}_{repo}_{number}` with 1-hour TTL |
| **LangSmith observability** | `backend/tracing.py` — sets `LANGCHAIN_TRACING_V2=true` before LangGraph loads; all LLM calls traced in `autopilot_dev` project |
| **Async FastAPI + asyncpg** | `db/database.py` — `create_async_engine` + `AsyncSession`; `run_autopilot` wrapped in `asyncio.to_thread` |
| **Rate-limit resilience** | `agents/base.py kickoff_with_retry()` — parses Groq's "retry in Xs" hint and backs off automatically |

---

## License

MIT
