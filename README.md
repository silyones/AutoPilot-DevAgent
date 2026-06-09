# AutoPilot Dev

> **Autonomous GitHub PR Review & Bug-Fix System** — submit a pull request URL and receive an AI-driven review, automated fixes, test validation, and documentation.

[Python](https://python.org)
[FastAPI](https://fastapi.tiangolo.com)
[LangGraph](https://langchain-ai.github.io/langgraph/)
[Docker](https://docker.com)

---

## Overview

AutoPilot Dev is a multi-agent AI pipeline that accepts a GitHub Pull Request URL and runs an end-to-end review workflow:

1. Fetches the PR diff and metadata from GitHub
2. Reviews the code for bugs, security issues, and style problems
3. Generates targeted patches for identified issues
4. Validates fixes through a test simulation with automatic retries
5. Produces documentation and a structured `DevReport`

Progress streams to the browser in real time over WebSocket. Completed reports are stored in PostgreSQL and available through the REST API.

---

## Architecture

The system uses a **LangGraph StateGraph** to orchestrate CrewAI agents. Each graph node runs a specialist agent, and conditional edges route the pipeline based on shared state.

```
┌─────────────┐
│  fetch_pr   │  GitHub API → PR diff, metadata, file tree
└──────┬──────┘
       ▼
┌─────────────┐
│   review    │  Reviewer Agent → findings, severity, classification
└──────┬──────┘
       │  has_bugs?
       ├─── No ──────────────────────────────────────────────┐
       ▼                                                     │
┌─────────────┐                                              │
│     fix     │  Fixer Agent → patches                       │
└──────┬──────┘                                              │
       ▼                                                     │
┌─────────────┐                                              │
│    test     │  Tester Agent → pytest simulation            │
└──────┬──────┘                                              │
       │  tests pass?                                        │
       ├─── No (retry_count < max) ──────→ back to fix       │
       ├─── No (max retries hit) ────────→ NEEDS_HUMAN_REVIEW│
       ▼                                                     │
┌─────────────┐                                              │
│   document  │  Documenter Agent → PR summary                 │
└──────┬──────┘                                              │
       ▼                                                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 compile_report  →  DevReport                  │
└─────────────────────────────────────────────────────────────┘
```

When tests fail, the pipeline retries the fix-and-test cycle. On each retry, the Fixer agent receives its previous output and the test failure report to refine patches automatically.

---

## Tech Stack


| Technology               | Role                                                             |
| ------------------------ | ---------------------------------------------------------------- |
| **LangGraph**            | StateGraph orchestrator with conditional routing and retry logic |
| **CrewAI**               | Agent framework; each node runs a specialist `Agent` and `Task`  |
| **Groq (LLaMA 3.3 70B)** | LLM backend for all agents (`groq/llama-3.3-70b-versatile`)      |
| **GitHub API**           | Fetches PR diffs, file trees, and metadata via PyGithub          |
| **FastAPI**              | REST API (`POST /api/review`, `GET /api/reports`, `GET /health`) |
| **WebSocket**            | Streams per-agent progress events to the browser                 |
| **PostgreSQL**           | Persists `DevReport` records as JSONB                            |
| **Redis**                | Caches PR diffs (1 hour) and session state (2 hours)             |
| **LangSmith**            | Traces LLM calls in the `autopilot_dev` project                  |
| **Docker**               | Runs Postgres, Redis, API, and UI via `docker-compose`           |
| **Next.js + React**      | Web UI with Tailwind CSS, built as a static export               |


---

## Project Structure

```
AutoPilot_Dev/
├── docker-compose.yml        # Postgres, Redis, and API services
├── docker-entrypoint.sh      # Database migrations, then API startup
├── Dockerfile                # Multi-stage build: Next.js frontend + Python API
├── pytest.ini                # Pytest configuration and markers
├── requirements.txt
├── alembic.ini
│
├── frontend/
│   ├── package.json
│   ├── next.config.mjs       # Static export → out/
│   ├── app/
│   │   ├── layout.jsx        # Root layout
│   │   ├── page.jsx          # Main page (WebSocket + pipeline UI)
│   │   └── globals.css       # Theme styles
│   ├── components/           # UI components
│   ├── lib/                  # Pipeline constants and API helpers
│   └── out/                  # Production build output (generated in Docker)
│
├── api/
│   ├── main.py               # Serves UI, API routes, and health check
│   ├── routes.py             # Review, WebSocket, and report endpoints
│   └── websocket_manager.py  # WebSocket connection manager
│
├── graph/                    # LangGraph pipeline
├── agents/                   # CrewAI agent modules
├── tools/                    # GitHub and code analysis utilities
├── backend/                  # Config, tracing, schemas
├── db/                       # SQLAlchemy models and database setup
├── cache/                    # Redis client and session store
├── alembic/                  # Database migrations
└── tests/                    # Unit and integration tests
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

The full stack (PostgreSQL, Redis, FastAPI, and the web UI) runs inside Docker containers.

### Installation

```bash
git clone https://github.com/your-username/AutoPilot-Dev.git
cd AutoPilot-Dev

cp .env.example .env
```

Edit `.env` and set the required values:

- `GROQ_API_KEY`
- `GITHUB_TOKEN`
- `LANGCHAIN_API_KEY`
- `POSTGRES_PASSWORD`

### Start the Application

```bash
docker-compose up --build
```

To run in the background:

```bash
docker-compose up --build -d
```

On first startup, the API container applies database migrations automatically, then starts the server.

### Stop the Application

```bash
docker-compose down
```

---

## Services


| Container            | Description                | Port   |
| -------------------- | -------------------------- | ------ |
| `autopilot-api`      | FastAPI backend and web UI | `8000` |
| `autopilot-postgres` | PostgreSQL database        | `5433` |
| `autopilot-redis`    | Redis cache                | `6379` |


Inside Docker, the API connects to Postgres and Redis using internal service hostnames (`postgres`, `redis`). The `DATABASE_URL` and `REDIS_URL` values in `docker-compose.yml` configure these connections.

---

## Using the Web UI

1. Start the stack with `docker-compose up --build`
2. Open [http://localhost:8000](http://localhost:8000)
3. Enter a GitHub pull request URL (for example, `https://github.com/owner/repo/pull/1`)
4. Click **Analyse**
5. Monitor the live pipeline diagram and activity feed
6. When the run completes, review the DevReport below the pipeline
7. Use **Download Report as PDF** to save the report through the browser print dialog

### Additional Endpoints


| URL                                                          | Description       |
| ------------------------------------------------------------ | ----------------- |
| [http://localhost:8000/docs](http://localhost:8000/docs)     | API documentation |
| [http://localhost:8000/health](http://localhost:8000/health) | Health check      |


### UI Layout


| Section        | Contents                                                                            |
| -------------- | ----------------------------------------------------------------------------------- |
| Left panel     | PR URL input, Analyse button, status badge, duration                                |
| Right panel    | Live pipeline diagram and recent activity log                                       |
| Report section | Summary cards, findings, patches, documentation summary, agent timeline, PDF export |


The frontend is built with **Next.js 15**, **React 18**, and **Tailwind CSS 3** during the Docker image build and served by FastAPI at port `8000`.

---

## Database Access (pgAdmin)

To inspect stored reports with pgAdmin or another SQL client:


| Field    | Value                                  |
| -------- | -------------------------------------- |
| Host     | `localhost`                            |
| Port     | `5433`                                 |
| Database | `autopilot_dev`                        |
| Username | `postgres`                             |
| Password | Value of `POSTGRES_PASSWORD` in `.env` |


Reports are stored in the `dev_reports` table under `public` schema.

---

## Environment Variables


| Variable            | Description                                                          |
| ------------------- | -------------------------------------------------------------------- |
| `GROQ_API_KEY`      | Groq API key ([console.groq.com](https://console.groq.com))          |
| `GROQ_MODEL`        | Groq model name (default: `llama-3.3-70b-versatile`)                 |
| `GITHUB_TOKEN`      | GitHub personal access token                                         |
| `LANGCHAIN_API_KEY` | LangSmith API key for tracing                                        |
| `POSTGRES_USER`     | PostgreSQL username                                                  |
| `POSTGRES_PASSWORD` | PostgreSQL password                                                  |
| `POSTGRES_DB`       | PostgreSQL database name                                             |
| `DATABASE_URL`      | PostgreSQL connection string (used by external tools on port `5433`) |
| `REDIS_URL`         | Redis connection string                                              |


---

## API Usage

### Start a Review

```bash
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "https://github.com/tiangolo/fastapi/pull/1"}'
```

Response:

```json
{"success": true, "session_id": "a3f1c2d4-...", "data": null, "error": null}
```

### Stream Progress

Connect to the WebSocket endpoint for the returned session ID:

```
ws://localhost:8000/api/ws/{session_id}
```

The web UI handles this connection automatically when a review is started from the browser.

### Sample DevReport

```json
{
  "pr_url": "https://github.com/tiangolo/fastapi/pull/1",
  "status": "FIXED",
  "review": {
    "findings": [
      {
        "severity": "high",
        "description": "Missing input validation on path parameter",
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
    "summary": "This PR adds tests for FastAPI path parameter validation endpoints."
  },
  "agent_trace": [
    {"agent": "GitHub Fetcher", "action": "fetch_pr", "result": "Fetched PR", "timestamp": "2026-06-08T06:29:42Z"},
    {"agent": "Reviewer Agent", "action": "review_pr", "result": "Found 5 issues", "timestamp": "2026-06-08T06:29:43Z"},
    {"agent": "Fixer Agent", "action": "fix_bugs_attempt_1", "result": "Generated 10 patches", "timestamp": "2026-06-08T06:29:47Z"},
    {"agent": "Tester Agent", "action": "run_tests", "result": "Status: PASS", "timestamp": "2026-06-08T06:29:48Z"},
    {"agent": "Documenter Agent", "action": "write_documentation", "result": "Generated summary", "timestamp": "2026-06-08T06:30:00Z"}
  ],
  "retry_count": 1,
  "total_duration_seconds": 21.35,
  "created_at": "2026-06-08T06:30:00Z"
}
```

The UI displays the documentation **summary** field. Additional documentation fields may be stored in the database but are not shown in the interface.

---

## Running Tests

Tests can be run with Python installed on the host machine:

```bash
pip install -r requirements.txt

# Fast offline tests (no Groq API calls)
pytest tests/test_github_tool.py tests/test_api.py -v

# All tests, including graph integration (requires GROQ_API_KEY)
pytest tests/ -v

# Graph integration tests only
pytest tests/test_graph.py -v -m graph
```

Graph integration tests call the live Groq API and require a valid `GROQ_API_KEY`.

---

## Agentic AI


| Concept                       | Implementation                                                          |
| ----------------------------- | ----------------------------------------------------------------------- |
| **Conditional routing**       | `graph/workflow.py` routes based on `test_status` and `retry_count`     |
| **Stateful retry loop**       | Fix → test cycle repeats up to `MAX_FIX_RETRIES`                        |
| **Multi-agent orchestration** | Reviewer, Fixer, Tester, and Documenter agents coordinated by LangGraph |
| **Self-correcting fixes**     | Fixer receives prior patches and test failures on each retry            |
| **Live streaming**            | WebSocket pushes progress and completion events per agent step          |
| **Redis caching**             | PR diffs cached with a 1-hour TTL                                       |
| **LangSmith tracing**         | All LLM calls traced in the `autopilot_dev` project                     |
| **Async persistence**         | SQLAlchemy async engine with PostgreSQL                                 |
| **Rate-limit handling**       | Automatic backoff when Groq rate limits are hit                         |


---

## License

MIT