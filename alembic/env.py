import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Path Management: Add 'src/backend' to sys.path so we can import 'database'
# This ensures Alembic can find your models even when run from the root.
parent_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(parent_dir / "src" / "backend"))

# 2. Config Setup: Load the .ini file and interpretation of logging
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Model Discovery: Import your metadata and URL from your application
# We use 'try/except' to handle cases where environment variables might be missing
try:
    from database import Base, DATABASE_URL
except ImportError as e:
    print(f"[!] Error: Could not find application modules. Check PYTHONPATH. {e}")
    sys.exit(1)

# Set the SQLAlchemy URL from our .env/database.py instead of alembic.ini
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (scripts-only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Sync-wrapper to run actual migrations on the connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live database).
    
    This uses an async engine to communicate with asyncpg.
    """
    # 4. Engine Configuration: Setup the async connectable
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # We must use run_sync because Alembic is internally synchronous
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

# 5. Execution Entrypoint
if context.is_offline_mode():
    run_migrations_offline()
else:
    # Use the existing loop if available (common in 2026 dev environments)
    try:
        asyncio.run(run_migrations_online())
    except RuntimeError:
        # Fallback if an event loop is already running
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_migrations_online())
