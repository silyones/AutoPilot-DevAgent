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
import backend.tracing  # noqa: F401  (side-effect import — sets env vars)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from backend.config import settings
from backend.utils.logger import get_logger

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "out"

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Liveness probe — returns 200 if the service is up."""
    return {"status": "ok", "service": "AutoPilot Dev"}


def _frontend_index() -> Path:
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend not built. Rebuild with: docker-compose up --build",
        )
    return index_path


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Serve the Next.js-built React UI."""
    return FileResponse(_frontend_index())


if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=FRONTEND_DIST / "_next"), name="next_static")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "AutoPilot Dev API starting on %s:%s (env=%s)",
        settings.fastapi_host,
        settings.fastapi_port,
        settings.env,
    )
    if not (FRONTEND_DIST / "index.html").is_file():
        logger.warning(
            "Frontend dist missing at %s — rebuild with: docker-compose up --build",
            FRONTEND_DIST,
        )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("AutoPilot Dev API shutting down.")
