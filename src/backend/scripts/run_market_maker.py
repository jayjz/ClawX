#!/usr/bin/env python3
"""
run_market_maker.py — Automated market generation daemon.

Periodically calls ensure_open_markets() to keep the arena supplied
with markets across all 4 source types: RESEARCH · WEATHER · GITHUB · NEWS.

Usage:
    docker compose up -d market-maker
    # or directly:
    python src/backend/scripts/run_market_maker.py
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Path fixup
_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from database import async_session_maker
from services.market_maker import ensure_open_markets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("market-maker-daemon")

INTERVAL = int(os.environ.get("MARKET_MAKER_INTERVAL", "300"))

_shutdown_requested = False


def _handle_signal(signum, frame):
    global _shutdown_requested
    logger.info("Shutdown signal received (sig=%d). Finishing current cycle...", signum)
    _shutdown_requested = True


async def run_daemon():
    cycle = 0
    while not _shutdown_requested:
        cycle += 1
        try:
            async with async_session_maker() as session:
                created = await ensure_open_markets(session, min_open=6)
                if created:
                    logger.info("Cycle %d: created %d markets across all sources", cycle, created)
                else:
                    logger.debug("Cycle %d: board sufficiently stocked", cycle)
        except Exception:
            logger.exception("Cycle %d FAILED — will retry next cycle", cycle)

        # Interruptible sleep
        for _ in range(INTERVAL):
            if _shutdown_requested:
                break
            await asyncio.sleep(1)

    logger.info("Market maker daemon stopped after %d cycles.", cycle)


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Market maker daemon starting (interval=%ds)", INTERVAL)
    asyncio.run(run_daemon())


if __name__ == "__main__":
    main()
