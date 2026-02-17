#!/usr/bin/env python3
"""
genesis_bot.py — Create a bot directly in the database with a GRANT ledger entry.

Works in both Docker and local environments. No HTTP dependency.
All money enters through the ledger (CLAUDE.md Invariant #4).

Usage:
    # Docker:
    docker compose exec backend python3 src/backend/scripts/genesis_bot.py --handle TestBot

    # Local (with venv):
    cd src/backend && DATABASE_URL=... python scripts/genesis_bot.py --handle TestBot

    # With custom balance:
    ... genesis_bot.py --handle WhaleBot --balance 5000

    # With api_secret for arena gateway:
    The script always generates and prints api_secret.
"""

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

# --- Path fixup: works from any CWD, Docker or local ---
_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from models import Bot, AuditLog
from services.ledger_service import append_ledger_entry


async def create_genesis_bot(
    handle: str,
    balance: float = 1000.0,
    persona: str = "Arena test agent — sacrificial reference implementation.",
) -> None:
    """Create a bot + GRANT entry atomically."""

    async with async_session_maker() as session:
        # Idempotency check
        result = await session.execute(select(Bot).where(Bot.handle == handle))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"[SKIP] Bot '{handle}' already exists (id={existing.id}, balance={existing.balance})")
            return

        # Credential generation
        raw_api_key = secrets.token_hex(16)
        hashed_key = bcrypt.hashpw(raw_api_key.encode(), bcrypt.gensalt()).decode()
        api_secret = secrets.token_hex(32)

        bot = Bot(
            handle=handle,
            persona_yaml=persona,
            hashed_api_key=hashed_key,
            api_secret=api_secret,
            balance=balance,
            status="ALIVE",
            is_external=False,
        )
        session.add(bot)
        await session.flush()

        # GRANT entry — all money enters through the chain (Invariant #4)
        entry = await append_ledger_entry(
            bot_id=bot.id,
            amount=balance,
            transaction_type="GRANT",
            reference_id="GENESIS_GRANT",
            session=session,
        )

        session.add(AuditLog(bot_id=bot.id, action="GENESIS_BOT_CREATED"))
        await session.commit()

        print(f"[OK] Bot created successfully")
        print(f"  id:         {bot.id}")
        print(f"  handle:     {bot.handle}")
        print(f"  balance:    {bot.balance}")
        print(f"  status:     {bot.status}")
        print(f"  api_key:    {raw_api_key}")
        print(f"  api_secret: {api_secret}")
        print(f"  ledger seq: {entry.sequence}")
        print(f"  ledger hash:{entry.hash[:24]}...")
        print()
        print("  Save these credentials. They will NOT be shown again.")


def main():
    parser = argparse.ArgumentParser(description="Create a genesis bot in the arena")
    parser.add_argument("handle", nargs="?", default=None, help="Unique bot handle (positional)")
    parser.add_argument("name", nargs="?", default=None, help="Display name (unused, for compat)")
    parser.add_argument("config", nargs="?", default=None, help="Path to persona YAML file")
    parser.add_argument("--handle", dest="handle_flag", default=None, help="Unique bot handle (flag)")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting balance (default: 1000)")
    parser.add_argument("--persona", default=None, help="Persona description")
    args = parser.parse_args()

    handle = args.handle_flag or args.handle
    if not handle:
        parser.error("handle is required (positional or --handle)")

    # Load persona from config file if provided
    persona = args.persona or "Arena test agent — sacrificial reference implementation."
    if args.config:
        import os
        config_path = args.config
        if not os.path.isabs(config_path):
            config_path = os.path.join("/app", config_path)
        if os.path.exists(config_path):
            with open(config_path) as f:
                persona = f.read()
        else:
            print(f"[!] Config file not found: {config_path}, using default persona")

    asyncio.run(create_genesis_bot(handle, args.balance, persona))


if __name__ == "__main__":
    main()
