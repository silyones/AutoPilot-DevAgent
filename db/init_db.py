"""Database initialisation script.

Run directly to create all tables and apply pending Alembic migrations:

    python -m db.init_db          # from project root

Or execute the file directly:

    python db/init_db.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys

from sqlalchemy import text

from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def _create_tables_async() -> None:
    """Create all tables using SQLAlchemy metadata (async engine)."""
    # Import here so that ORM models register themselves on Base before we call
    # create_all — order matters.
    from db.database import Base, engine  # noqa: PLC0415
    import db.models  # noqa: F401, PLC0415  — registers DevReportORM on Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Verify the table exists
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public';")
        )
        tables = [row[0] for row in result.fetchall()]
        logger.info("Tables present in public schema: %s", tables)

    await engine.dispose()


def _run_alembic_migrations() -> None:
    """Run `alembic upgrade head` as a subprocess."""
    logger.info("Running Alembic migrations (alembic upgrade head)…")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logger.info("Alembic stdout:\n%s", result.stdout.strip())
    if result.stderr:
        logger.warning("Alembic stderr:\n%s", result.stderr.strip())
    if result.returncode != 0:
        logger.error(
            "Alembic migration failed with exit code %d", result.returncode
        )
        sys.exit(result.returncode)
    logger.info("Alembic migrations applied successfully.")


def main() -> None:
    """Entry-point: create tables then run Alembic migrations."""
    logger.info("Initialising AutoPilot Dev database…")

    # 1. Create tables via SQLAlchemy metadata
    asyncio.run(_create_tables_async())

    # 2. Apply any pending Alembic migrations
    _run_alembic_migrations()

    print("✅ Database tables created successfully")


if __name__ == "__main__":
    main()
