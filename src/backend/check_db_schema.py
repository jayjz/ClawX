#!/usr/bin/env python3
"""
check_db_schema.py — Live DB introspection script.

Works inside Docker container (PYTHONPATH=/app/src/backend) and locally.
Uses raw asyncpg via SQLAlchemy to query information_schema — no ORM needed.

References:
  - lessons.md Rule #4: All raw SQL wrapped in text()
  - MEMORY.md: Expected tables include bots, ledger, predictions, etc.
  - CLAUDE.md Invariant #4: ledger.sequence must exist (monotonic chain)
  - CLAUDE.md Invariant #1: bots.last_action_at must exist (entropy decay)

Usage:
    # Inside Docker container:
    docker compose exec backend python src/backend/check_db_schema.py

    # Or from src/backend directly:
    cd src/backend && python check_db_schema.py
"""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://psyop_admin:psyop_admin_2026@localhost:5432/clawdxcraft",
)


async def introspect():
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            # 1. List all tables
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            ))
            tables = [row[0] for row in result.fetchall()]
            print(f"\n{'='*60}")
            print(f"DATABASE: {DATABASE_URL.split('@')[-1]}")
            print(f"{'='*60}")
            print(f"\nTables ({len(tables)}):")
            for t in tables:
                print(f"  - {t}")

            if not tables:
                print("\n  [!] No tables found. Run init_db() or alembic upgrade head.")
                return

            # 2. Detail columns for critical tables
            critical_tables = ["bots", "ledger", "predictions", "users", "audit_log", "posts"]
            for table_name in critical_tables:
                if table_name not in tables:
                    print(f"\n[{table_name}] — NOT FOUND in database")
                    continue

                result = await conn.execute(text(
                    "SELECT column_name, data_type, is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name = :tbl ORDER BY ordinal_position"
                ), {"tbl": table_name})
                cols = result.fetchall()

                print(f"\n[{table_name}] — {len(cols)} columns:")
                for name, dtype, nullable, default in cols:
                    null_str = "NULL" if nullable == "YES" else "NOT NULL"
                    default_str = f" DEFAULT {default}" if default else ""
                    print(f"  {name:25s} {dtype:20s} {null_str}{default_str}")

            # 3. Check alembic version
            if "alembic_version" in tables:
                result = await conn.execute(text(
                    "SELECT version_num FROM alembic_version"
                ))
                rows = result.fetchall()
                if rows:
                    print(f"\n[alembic] Current revision: {rows[0][0]}")
                else:
                    print("\n[alembic] Table exists but no version stamped")
            else:
                print("\n[alembic] No alembic_version table — migrations not initialized")

            # 4. Constitutional invariant checks
            print(f"\n{'='*60}")
            print("CONSTITUTIONAL INVARIANT CHECKS")
            print(f"{'='*60}")

            bot_cols = []
            ledger_cols = []
            if "bots" in tables:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'bots'"
                ))
                bot_cols = [r[0] for r in result.fetchall()]

            if "ledger" in tables:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'ledger'"
                ))
                ledger_cols = [r[0] for r in result.fetchall()]

            checks = [
                ("Invariant #1", "bots.last_action_at", "last_action_at" in bot_cols),
                ("Invariant #1", "bots.status (ALIVE/DEAD)", "status" in bot_cols),
                ("Invariant #4", "ledger.sequence (monotonic)", "sequence" in ledger_cols),
                ("Invariant #4", "ledger.hash (chain)", "hash" in ledger_cols),
                ("Invariant #4", "ledger.previous_hash", "previous_hash" in ledger_cols),
                ("Invariant #5", "bots.api_secret (ext agents)", "api_secret" in bot_cols),
                ("Invariant #5", "bots.is_external", "is_external" in bot_cols),
            ]

            all_pass = True
            for inv, desc, ok in checks:
                status = "OK" if ok else "MISSING"
                if not ok:
                    all_pass = False
                print(f"  [{status:7s}] {inv}: {desc}")

            if all_pass:
                print("\n  All constitutional columns present.")
            else:
                print("\n  [!] Missing columns — run alembic upgrade head or init_db()")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(introspect())
