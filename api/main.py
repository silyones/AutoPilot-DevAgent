"""FastAPI application entry point for AutoPilot Dev.

Run the full stack with Docker::

    docker-compose up --build

Then open http://localhost:8000 for the UI.
Swagger UI: http://localhost:8000/docs
ReDoc     : http://localhost:8000/redoc
"""

from __future__ import annotations

from pathlib import Path

# ── LangSmith tracing — must be imported before api.routes (which loads LangGraph) ──
# backend.tracing sets LANGCHAIN_* env vars at module load time.
# backend.tracing itself only imports os + backend.config — no langchain — so
# the env vars are in place before LangGraph/LangChain reads them.
import backend.tracing  # noqa: F401  (side-effect import — sets env vars)



from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


from api.routes import router
from backend.config import settings
from backend.utils.logger import get_logger

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logger = get_logger(__name__)

app = FastAPI(
    title="AutoPilot Dev API",
    description=(
        "Autonomous GitHub PR Review & Bug Fix System powered by "
        "LangGraph + CrewAI + Groq."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins during local development so any frontend host works.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api")


# ── Frontend (single-page UI served from the API container) ───────────────────
@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Serve the AutoPilot Dev UI at the root URL."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"Frontend not found: {index_path}")
    return FileResponse(index_path)


# ── Health probe ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Liveness probe — returns 200 if the service is up."""
    return {"status": "ok", "service": "AutoPilot Dev"}


# ── Startup / shutdown hooks ──────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "AutoPilot Dev API starting on %s:%s (env=%s)",
        settings.fastapi_host,
        settings.fastapi_port,
        settings.env,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("AutoPilot Dev API shutting down.")
