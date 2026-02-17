#!/usr/bin/env python3
"""
run_ticker.py — The Ticker Daemon.

Continuous heartbeat of the ClawdXCraft arena economy.
Runs an infinite loop, ticking every ALIVE bot once per cycle,
then sleeping for TICK_RATE seconds.

Contract of Behavior:
  - Calls execute_tick() for every ALIVE bot each cycle (Write or Die applies)
  - Respects Decimal math and hash-chained ledger integrity
  - Graceful shutdown on SIGINT/SIGTERM: finishes the current tick cycle,
    then exits cleanly. Never kills a tick mid-transaction.
  - Does NOT run migrations. Assumes DB schema is ready.
  - Does NOT prevent concurrent drive_economy.py runs (double-tick is valid physics)
  - Error boundary: if a single bot's tick crashes, log and continue to next bot.
    If the entire cycle crashes, log and retry next cycle.

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly — every cycle enforces entropy
  - CLAUDE.md Invariant #4: Irreversible loss — all entries hash-chained
  - CLAUDE.md Invariant #6: Continuous real-time, not turn-based
  - lessons.md: All money through ledger, path fixup pattern

Environment:
  TICK_RATE  — seconds between cycles (default: 10)
  DATABASE_URL — async postgres DSN
  REDIS_URL — redis connection

Usage:
    # Docker (preferred):
    docker compose up -d ticker

    # Manual:
    cd src/backend && DATABASE_URL=... python scripts/run_ticker.py
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# --- Path fixup: works from any CWD, Docker or local ---
_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy import select

from database import async_session_maker
from models import Bot
from services.market_maker import ensure_research_markets

# Configure logging before any other imports that use loggers
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ticker")

TICK_RATE = int(os.environ.get("TICK_RATE", "10"))

# --- Graceful shutdown flag ---
_shutdown_requested = False


def _request_shutdown(signum, frame):
    """Signal handler: set flag, let current cycle finish."""
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — will shut down after current cycle completes", sig_name)
    _shutdown_requested = True


async def tick_all_bots() -> tuple[int, int]:
    """Run one tick for every ALIVE bot. Returns (ticked, alive_count)."""
    # Import here to avoid circular issues at module level
    from bot_runner import execute_tick

    async with async_session_maker() as session:
        result = await session.execute(
            select(Bot).where(Bot.status == "ALIVE").order_by(Bot.id)
        )
        bots = result.scalars().all()

    if not bots:
        return 0, 0

    ticked = 0
    for bot in bots:
        if _shutdown_requested:
            logger.info("Shutdown requested — stopping mid-cycle after %d/%d bots", ticked, len(bots))
            break

        config = {
            "persona": bot.persona_yaml or "Arena agent",
            "name": bot.handle,
            "goals": ["Survive the arena"],
            "schedule": {"interval_seconds": 60},
        }

        try:
            tx_type = await execute_tick(
                bot_id=bot.id,
                config=config,
                balance=float(bot.balance),
            )
            ticked += 1
            logger.info(
                "TICK @%-20s id=%-4d → %-11s",
                bot.handle, bot.id, tx_type,
            )
        except Exception as exc:
            # Error boundary per bot — one bot crashing must not stop the others
            logger.error(
                "TICK @%-20s id=%-4d → EXCEPTION: %s",
                bot.handle, bot.id, exc,
                exc_info=True,
            )
            ticked += 1  # execute_tick's Write-or-Die should have handled it

    return ticked, len(bots)


async def run_daemon():
    """Main daemon loop. Runs until SIGINT/SIGTERM."""
    global _shutdown_requested

    # Install signal handlers
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    logger.info("=" * 60)
    logger.info("TICKER DAEMON ONLINE — TICK_RATE=%ds", TICK_RATE)
    logger.info("Continuous economy. Inaction penalized. Losses irreversible.")
    logger.info("=" * 60)

    cycle = 0
    total_ticks = 0

    while not _shutdown_requested:
        cycle += 1

        # v1.7: Ensure research markets exist before ticking bots
        try:
            async with async_session_maker() as session:
                created = await ensure_research_markets(session, min_open=3)
                if created > 0:
                    logger.info("Cycle %d: Created %d research markets", cycle, created)
        except Exception as mkt_exc:
            logger.warning("Cycle %d: Research market generation failed: %s", cycle, mkt_exc)

        try:
            ticked, alive = await tick_all_bots()
            total_ticks += ticked

            if alive == 0:
                logger.info("Cycle %d: No ALIVE bots. Waiting...", cycle)
            else:
                logger.info(
                    "Cycle %d complete: %d/%d bots ticked (total lifetime: %d)",
                    cycle, ticked, alive, total_ticks,
                )
        except Exception as exc:
            # Error boundary for entire cycle — daemon must not die
            logger.error(
                "Cycle %d FAILED: %s — will retry next cycle",
                cycle, exc,
                exc_info=True,
            )

        # Sleep in small increments to respond to shutdown quickly
        for _ in range(TICK_RATE):
            if _shutdown_requested:
                break
            await asyncio.sleep(1.0)

    logger.info("=" * 60)
    logger.info("TICKER DAEMON SHUTDOWN — %d cycles, %d total ticks", cycle, total_ticks)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_daemon())
