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
       ▼                                                     │
┌─────────────┐                                              │
│     fix     │  — Fixer Agent → patches, self-aware retries │
└──────┬──────┘                                              │
       ▼                                                     |
┌─────────────┐                                              │
│    test     │  — Tester Agent → pytest simulation          │
└──────┬──────┘                                              │
       │  tests pass?                                        │
       ├─── No (retry_count < max) ──────→ back to fix       │
       ├─── No (max retries hit) ────────→ NEEDS_HUMAN_REVIEW│
       ▼                                                     │
┌─────────────┐                                              │
│   document  │  — Documenter Agent → PR summary             │
└──────┬──────┘                                              │
       ▼                                                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 compile_report  →  DevReport                │
└─────────────────────────────────────────────────────────────┘
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
| **Docker** | Infrastructure — `docker-compose up --build` starts Postgres + Redis + API in one command |
| **Vite + React** | Professional SPA — `frontend/src/` with Tailwind, built to `frontend/dist/` |

---

## Project Structure

```
AutoPilot_Dev/
├── .env                      # API keys & config (never committed)
├── .env.example              # Template for .env
├── docker-compose.yml        # Postgres + Redis + API (Docker-only stack)
├── docker-entrypoint.sh      # Runs alembic migrations, then uvicorn
├── Dockerfile                # Multi-stage: Node (Vite build) + Python API
├── pytest.ini                # Pytest markers (graph integration tests)
├── requirements.txt
├── alembic.ini
│
├── frontend/
│   ├── package.json          # Vite + React + Tailwind dependencies
│   ├── vite.config.js        # Dev server + production build config
│   ├── index.html            # Vite entry HTML
│   ├── src/
│   │   ├── App.jsx           # Main application state + WebSocket logic
│   │   ├── main.jsx          # React entry point
│   │   ├── index.css         # Dark green + pink theme (Tailwind)
│   │   ├── components/       # Pipeline, report panels, control panel
│   │   ├── constants/        # Pipeline nodes, status styles
│   │   └── utils/            # API URL validation, WebSocket helpers
│   └── dist/                 # Production build (generated inside Docker)
│
├── api/                      # FastAPI application
│   ├── main.py               # Serves frontend/dist + /api/* + /health
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
- **Docker Desktop** only — Postgres, Redis, API, and the React UI all run in containers

### Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/your-username/AutoPilot-Dev.git
cd AutoPilot-Dev

# 2. Configure environment
cp .env.example .env
# Edit .env — set GROQ_API_KEY, GITHUB_TOKEN, LANGCHAIN_API_KEY, POSTGRES_PASSWORD

# 3. Start everything (builds Vite frontend + API image, runs migrations)
docker-compose up --build
```

Run in the background:

```bash
docker-compose up --build -d
```

### Docker containers

| Container | Purpose | Host port |
|-----------|---------|-----------|
| `autopilot-api` | FastAPI + React UI + auto-migrations | `8000` |
| `autopilot-postgres` | Report persistence (`dev_reports` table) | `5433` |
| `autopilot-redis` | PR diff caching | `6379` |

On startup, `autopilot-api` runs `alembic upgrade head` then `uvicorn`. The API container overrides `DATABASE_URL` and `REDIS_URL` to use Docker service names (`postgres`, `redis`) — not your local Postgres install.

Stop the stack:

```bash
docker-compose down
```

### Using the UI

1. Run `docker-compose up --build` and wait for `autopilot-api` to start
2. Open **http://localhost:8000** (this is the only URL for the UI)
3. Paste a GitHub PR URL (e.g. `https://github.com/owner/repo/pull/1`)
4. Click **Analyse**
5. Watch the live pipeline diagram and status badge update via WebSocket
6. When complete, scroll down for the DevReport (summary cards, findings table, patches, documentation summary, agent timeline)
7. Click **Download Report as PDF** to print/save via the browser

Other URLs:

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Open the UI at **http://localhost:8000** only. The Vite + React app is built inside the Docker image and served by FastAPI — no separate dev server, no local `npm` required.

### Frontend architecture

| Path | Role |
|------|------|
| `frontend/src/App.jsx` | Main app — WebSocket, pipeline state, review flow |
| `frontend/src/components/` | `ControlPanel`, `PipelineDiagram`, `ReportPanel`, etc. |
| `frontend/src/constants/pipeline.js` | Node definitions, status colours, badge styles |
| `frontend/src/utils/api.js` | PR URL validation, API base URL, WebSocket URL builder |
| `frontend/dist/` | Built inside Docker, served by FastAPI at `http://localhost:8000` |

Tech: **Vite 6 + React 18 + Tailwind CSS 3** — built during `docker-compose up --build`.

UI layout (unchanged):

- **Left column** — PR URL input, Analyse button, status badge, duration
- **Right column** — live pipeline diagram (waiting / running / done / failed) + last 5 activity lines
- **Report section** — summary cards, findings table, patches, documentation summary, agent timeline, PDF export

### pgAdmin / external DB tools

Connect to **Docker** Postgres (port `5433` avoids clashing with a local Postgres on `5432`):

| Field    | Value           |
|----------|-----------------|
| Host     | `localhost`     |
| Port     | `5433`          |
| Database | `autopilot_dev` |
| Username | `postgres`      |
| Password | value from `.env` `POSTGRES_PASSWORD` |

After at least one review, refresh **Schemas → public → Tables → `dev_reports`**.

### Running tests locally (optional)

Tests run on your machine with Python installed — they do not require Docker for the fast offline suite:

```bash
pip install -r requirements.txt
pytest tests/test_github_tool.py tests/test_api.py -v
```

---

### Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (get from console.groq.com) |
| `GROQ_MODEL` | Model name (default: `llama-3.3-70b-versatile`) |
| `GITHUB_TOKEN` | GitHub personal access token |
| `LANGCHAIN_API_KEY` | LangSmith API key (for tracing) |
| `POSTGRES_USER` | Postgres username (Docker `autopilot-postgres` container) |
| `POSTGRES_PASSWORD` | Postgres password (Docker `autopilot-postgres` container) |
| `POSTGRES_DB` | Database name (Docker `autopilot-postgres` container) |
| `DATABASE_URL` | Host-side DB URL for pgAdmin (`localhost:5433`); overridden inside the API container |
| `REDIS_URL` | Host-side Redis URL; overridden inside the API container to `redis://redis:6379` |

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
# Or open http://localhost:8000 and paste a PR URL in the UI
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
    "summary": "This PR adds tests for FastAPI path parameter validation endpoints and fixes missing input validation on path parameters."
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

> **Note:** The backend may still store `changelog` and `docstrings` in PostgreSQL JSONB. The UI displays only the **summary** under Documentation.

---

## Running Tests

```bash
# Fast offline tests (no Groq, no live server)
pytest tests/test_github_tool.py tests/test_api.py -v

# All tests including graph integration (calls Groq — requires GROQ_API_KEY)
pytest tests/ -v

# Graph tests only
pytest tests/test_graph.py -v -m graph
```

Pytest config lives in `pytest.ini` (no root `conftest.py`). The `graph` marker flags tests that call the live Groq API.

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
