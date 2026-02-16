#!/usr/bin/env python3
"""
drive_economy.py — The Big Red Button.

Advances the arena economy by exactly one tick for every ALIVE bot.
No HTTP dependency. Direct DB writes via append_ledger_entry().
Verifies ledger integrity after every run.

Contract of Behavior:
  - If no bots exist, creates a GenesisBot automatically
  - Every ALIVE bot gets exactly one tick (WAGER or HEARTBEAT)
  - After all ticks: runs inspect_ledger to verify hash chain
  - Prints summary: "Economy Advanced: N Transactions Committed. Hash Chain Verified."

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly (every tick is visible)
  - CLAUDE.md Invariant #4: Irreversible loss (all entries hash-chained)
  - lessons.md: All money through ledger, all scripts use path fixup

Usage:
    # Docker:
    docker compose exec backend python scripts/drive_economy.py

    # Local:
    cd src/backend && DATABASE_URL=... python scripts/drive_economy.py

    # Single bot:
    ... drive_economy.py --bot-id 1

    # Multiple ticks:
    ... drive_economy.py --ticks 5
"""

import argparse
import asyncio
import secrets
import sys
from decimal import Decimal
from pathlib import Path

# --- Path fixup: works from any CWD, Docker or local ---
_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import bcrypt
from sqlalchemy import select, func

from database import async_session_maker
from models import Bot, Ledger, AuditLog
from services.ledger_service import append_ledger_entry
from scripts.inspect_ledger import inspect


async def ensure_genesis_bot() -> bool:
    """Create a GenesisBot if no bots exist. Returns True if one was created."""
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(Bot.id)))
        count = result.scalar()

        if count > 0:
            return False

        raw_api_key = secrets.token_hex(16)
        hashed_key = bcrypt.hashpw(raw_api_key.encode(), bcrypt.gensalt()).decode()
        api_secret = secrets.token_hex(32)

        bot = Bot(
            handle="GenesisBot",
            persona_yaml="Sacrificial reference agent — exists to prove the system works.",
            hashed_api_key=hashed_key,
            api_secret=api_secret,
            balance=Decimal('1000.00'),
            status="ALIVE",
            is_external=False,
        )
        session.add(bot)
        await session.flush()

        await append_ledger_entry(
            bot_id=bot.id,
            amount=Decimal('1000.00'),
            transaction_type="GRANT",
            reference_id="GENESIS_GRANT",
            session=session,
        )

        session.add(AuditLog(bot_id=bot.id, action="GENESIS_BOT_CREATED"))
        await session.commit()

        print(f"[GENESIS] Created GenesisBot (id={bot.id})")
        print(f"  api_key:    {raw_api_key}")
        print(f"  api_secret: {api_secret}")
        print(f"  Save these credentials. They will NOT be shown again.\n")
        return True


async def drive_one_tick(bot_id: int | None = None) -> int:
    """Advance the economy by one tick. Returns number of transactions committed.

    If bot_id is provided, only that bot ticks. Otherwise all ALIVE bots tick.
    """
    # Import here to avoid circular issues at module level
    from bot_runner import execute_tick

    async with async_session_maker() as session:
        stmt = select(Bot).where(Bot.status == "ALIVE")
        if bot_id is not None:
            stmt = stmt.where(Bot.id == bot_id)
        result = await session.execute(stmt.order_by(Bot.id))
        bots = result.scalars().all()

    if not bots:
        print("[!] No ALIVE bots to tick.")
        return 0

    committed = 0
    for bot in bots:
        config = {
            "persona": bot.persona_yaml or "Arena agent",
            "name": bot.handle,
            "goals": ["Survive the arena"],
            "schedule": {"interval_seconds": 60},
        }

        tx_type = await execute_tick(
            bot_id=bot.id,
            config=config,
            balance=bot.balance,
        )

        # Re-read balance from DB (authoritative, not cached)
        async with async_session_maker() as post_session:
            result = await post_session.execute(select(Bot).where(Bot.id == bot.id))
            updated_bot = result.scalar_one_or_none()
            new_balance = updated_bot.balance if updated_bot else 0.0
            new_status = updated_bot.status if updated_bot else "UNKNOWN"

        print(f"  [{tx_type:>11}] @{bot.handle} (id={bot.id}, balance={new_balance:.2f}, status={new_status})")
        committed += 1

    return committed


async def main(bot_id: int | None = None, ticks: int = 1) -> bool:
    """Main entry point. Returns True if all checks pass."""
    print("=" * 60)
    print("DRIVE ECONOMY — Big Red Button")
    print("=" * 60)

    # Step 1: Ensure at least one bot exists
    created = await ensure_genesis_bot()

    # Step 2: Count ledger entries before
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(Ledger.id)))
        before_count = result.scalar()

    # Step 3: Run ticks
    total_committed = 0
    for tick_num in range(1, ticks + 1):
        if ticks > 1:
            print(f"\n--- Tick {tick_num}/{ticks} ---")
        committed = await drive_one_tick(bot_id)
        total_committed += committed

    # Step 4: Count ledger entries after
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(Ledger.id)))
        after_count = result.scalar()

    delta = after_count - before_count
    print(f"\nLedger entries: {before_count} -> {after_count} (delta={delta})")

    if delta != total_committed + (1 if created else 0):
        print(f"[WARN] Expected delta={total_committed + (1 if created else 0)}, got {delta}")

    # Step 5: Verify integrity
    print()
    ok = await inspect(bot_id)

    print()
    print("=" * 60)
    if ok:
        print(f"Economy Advanced: {total_committed} Transactions Committed. Hash Chain Verified.")
    else:
        print(f"Economy Advanced: {total_committed} Transactions Committed. INTEGRITY CHECK FAILED.")
    print("=" * 60)

    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drive the arena economy forward")
    parser.add_argument("--bot-id", type=int, default=None, help="Tick a single bot")
    parser.add_argument("--ticks", type=int, default=1, help="Number of ticks to run (default: 1)")
    args = parser.parse_args()

    ok = asyncio.run(main(args.bot_id, args.ticks))
    sys.exit(0 if ok else 1)
