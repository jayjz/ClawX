"""
database.py — Async engine, session factory, and DB lifecycle.

This file handles ONLY connection infrastructure:
  - Engine creation from DATABASE_URL
  - Session factory (async_session_maker)
  - FastAPI dependency (get_session)
  - Schema initialization (init_db)

All table definitions live in models.py (Single Source of Truth).
Re-exports from models.py are provided for backward compatibility so that
existing code doing `from database import Bot` continues to work.

References:
  - lessons.md Rule #2: Fail fast on missing config (DATABASE_URL has fallback
    only for local dev; production MUST set it explicitly)
  - MEMORY.md: DSN uses psyop_admin role on port 5432
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import everything from models — models.py is the Single Source of Truth.
# These re-exports exist so that `from database import Bot, Ledger, ...`
# continues to work across the codebase without a mass-migration of imports.
from models import (  # noqa: F401 — intentional re-exports
    Base,
    Bot,
    Ledger,
    Post,
    Prediction,
    AuditLog,
    User,
    MarketObservation,
    AgentAction,
    ActionResponse,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://psyop_admin:psyop_admin_2026@localhost:5432/clawdxcraft",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables defined in models.py (idempotent via create_all).

    WARNING (lessons.md Rule #1): This will NOT alter existing tables.
    Column additions require alembic migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional async session."""
    async with async_session_maker() as session:
        yield session
