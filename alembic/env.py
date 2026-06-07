"""Alembic environment script.

This file is executed by Alembic when running migration commands.
It configures:
  - The database URL (from settings, not alembic.ini) using a sync driver
  - The target metadata (from db/models.py ORM definitions)
  - Both offline and online migration modes
"""

from __future__ import annotations

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Make sure the project root is on sys.path so imports resolve correctly ────
# (Alembic may be invoked from any directory)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Import application settings & models ─────────────────────────────────────
from backend.config import settings  # noqa: E402
import db.models  # noqa: F401, E402  — ensures all ORM models are registered
from db.database import Base  # noqa: E402

# ── Alembic Config object (gives access to alembic.ini values) ────────────────
config = context.config

# ── Override sqlalchemy.url with the value from .env ─────────────────────────
# Alembic requires a *sync* URL, so we strip the +asyncpg dialect if present.
_db_url: str = settings.database_url
if "+asyncpg" in _db_url:
    _db_url = _db_url.replace("+asyncpg", "", 1)
config.set_main_option("sqlalchemy.url", _db_url)

# ── Set up Python logging from alembic.ini [loggers] section ─────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata — Alembic uses this for --autogenerate ────────────────────
target_metadata = Base.metadata


# ── Offline migration (without a live DB connection) ─────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL without establishing a real DB connection,
    useful for producing a migration script to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migration (with a live DB connection) ──────────────────────────────
def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a real DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
