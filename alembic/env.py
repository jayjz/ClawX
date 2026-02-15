"""
Alembic env.py — Migration runner for ClawdXCraft.

Path handling:
  - When run from project root (/app in Docker): adds src/backend to sys.path
  - When PYTHONPATH already includes src/backend: no-op (Docker compose sets this)
  - References lessons.md Rule #1: "Migrations Are Not Optional"
  - References lessons.md Rule #4: "No Raw SQL in execute()" — use text()
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Path Management
# Add src/backend to sys.path so `from models import Base` works.
# This handles both: running from project root AND inside Docker where
# PYTHONPATH=/app/src/backend is already set.
_backend_dir = str(Path(__file__).resolve().parents[1] / "src" / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# 2. Config Setup
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Model Discovery
# Import from models.py (Single Source of Truth) — NOT database.py.
# This avoids creating an engine at import time just to read metadata.
try:
    from models import Base
except ImportError as e:
    print(f"[!] Cannot import models. Check PYTHONPATH includes src/backend. {e}")
    sys.exit(1)

target_metadata = Base.metadata

# 4. Database URL
# Prefer DATABASE_URL env var (set by docker-compose or .env).
# Falls back to alembic.ini's sqlalchemy.url only if env var is missing.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Sync wrapper — Alembic internals are synchronous."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live async database."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# 5. Execution Entrypoint
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
