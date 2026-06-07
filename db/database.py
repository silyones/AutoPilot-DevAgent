"""SQLAlchemy async engine, session factory, and dependency helper.

Exports
-------
engine       — AsyncEngine connected to DATABASE_URL
SessionLocal — async session factory (AsyncSession)
Base         — declarative base shared by all ORM models
get_db()     — FastAPI dependency that yields an AsyncSession
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from backend.config import settings

# ── Convert the sync postgresql:// URL to the async postgresql+asyncpg:// form ──
_raw_url: str = settings.database_url
if _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql+asyncpg://"):
    _async_url = _raw_url
else:
    _async_url = _raw_url  # pass through and let SQLAlchemy raise if wrong

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    _async_url,
    echo=(settings.env == "development"),  # SQL logging only in dev
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Declarative base (shared by all ORM models) ───────────────────────────────
Base = declarative_base()


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and guarantee it is closed afterward.

    Usage in a FastAPI route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
