#!/usr/bin/env python3
"""
bootstrap_db.py — Initialize a fresh database from models.py and stamp alembic.

This script handles the "fresh Docker DB" case where:
  1. The postgres volume is empty (0 tables)
  2. Old alembic migrations reference dead tables (follows, hashtags, resolutions)
     that no longer exist in models.py
  3. Running `alembic upgrade head` would fail on a fresh DB

What it does:
  1. Creates all tables from models.py via Base.metadata.create_all (idempotent)
  2. Stamps alembic_version to HEAD so future migrations pick up from here

References:
  - lessons.md Rule #1: "Migrations Are Not Optional" — this is the ONE exception:
    bootstrapping a fresh DB. After this, all changes go through alembic.
  - MEMORY.md: "init_db.py is idempotent (uses create_all) but won't ALTER existing tables"

Usage:
    # Inside Docker:
    docker compose exec backend python src/backend/scripts/bootstrap_db.py

    # Locally:
    cd src/backend && python scripts/bootstrap_db.py
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Ensure src/backend is on path
_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://psyop_admin:psyop_admin_2026@localhost:5432/clawdxcraft",
)


async def bootstrap():
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Check if tables already exist
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"
        ))
        table_count = result.scalar()

        if table_count > 1:  # >1 because alembic_version might exist alone
            print(f"[!] Database already has {table_count} tables. Skipping create_all.")
            print("    Use alembic for schema changes from here.")
        else:
            print("[*] Fresh database detected. Creating all tables from models.py...")
            await conn.run_sync(Base.metadata.create_all)
            print("[+] Tables created successfully.")

        # Verify
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ))
        tables = [r[0] for r in result.fetchall()]
        print(f"[*] Tables now present: {', '.join(tables)}")

    await engine.dispose()

    # Stamp alembic to head
    print("[*] Stamping alembic version to HEAD...")
    project_root = Path(__file__).resolve().parents[3]  # /app
    alembic_ini = project_root / "alembic.ini"

    if alembic_ini.exists():
        result = subprocess.run(
            ["python", "-m", "alembic", "-c", str(alembic_ini), "stamp", "head"],
            cwd=str(project_root),
            env={**os.environ, "PYTHONPATH": _backend},
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("[+] Alembic stamped to HEAD.")
        else:
            print(f"[!] Alembic stamp failed: {result.stderr}")
            print("    You may need to run: alembic stamp head manually")
    else:
        print(f"[!] alembic.ini not found at {alembic_ini}")
        print("    Stamp manually: cd /app && alembic stamp head")


if __name__ == "__main__":
    asyncio.run(bootstrap())
