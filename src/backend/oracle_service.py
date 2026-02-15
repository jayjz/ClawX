"""
oracle_service.py — Price oracle + entropy/liquidation engine.

Imports Bot strictly from models.py (Single Source of Truth).
Imports async_session_maker from database.py (connection logic only).

Constitutional references:
  - CLAUDE.md Invariant #1: "Inaction is costly" → entropy decay on idle bots
  - CLAUDE.md Invariant #4: "Irreversible loss" → liquidation at balance <= 0
  - CLAUDE.md Invariant #6: "Continuous real-time" → oracle loop runs independently
  - lessons.md: Exponential backoff on CoinGecko 429 (base 120s)
"""

import asyncio
import logging
import os

import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select

from models import Bot
from database import async_session_maker
from services.ledger_service import append_ledger_entry
from redis_pool import init_redis_pool, get_redis

# Configuration
CHECK_INTERVAL = int(os.environ.get("ORACLE_INTERVAL", "60"))
ENTROPY_THRESHOLD_SECONDS = 300  # 5 minutes of inaction triggers decay
ENTROPY_RATE = 0.0005            # 0.05% decay per cycle
PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("oracle")


async def fetch_and_publish_price() -> Optional[float]:
    """Fetch BTC price from CoinGecko and publish to Redis for the Gateway."""
    redis = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                PRICE_API,
                headers={"User-Agent": "ClawdOracle/1.0"},
            )
            if resp.status_code == 200:
                price = float(resp.json()["bitcoin"]["usd"])
                await redis.setex("market:price:btc", 120, str(price))
                logger.info(f"Published BTC: ${price}")
                return price

            if resp.status_code == 429:
                logger.warning("Price API rate limited")
    except Exception as exc:
        logger.error(f"Price fetch failed: {exc}")
    return None


async def apply_entropy_and_liquidation() -> None:
    """
    The Physics Engine: applies time-based decay to idle bots.

    Uses Bot.last_action_at (defined in models.py) to determine idle duration.
    Bots idle beyond ENTROPY_THRESHOLD_SECONDS lose ENTROPY_RATE * balance per cycle.
    Balance <= 0 triggers DEAD status + LIQUIDATION ledger entry.
    """
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bot).where(Bot.status == "ALIVE")
        )
        bots = result.scalars().all()

        for bot in bots:
            last_action = bot.last_action_at or bot.created_at

            if now - last_action <= timedelta(seconds=ENTROPY_THRESHOLD_SECONDS):
                continue

            if bot.balance <= 0:
                continue

            decay = ENTROPY_RATE * bot.balance
            if decay > bot.balance:
                decay = bot.balance

            bot.balance -= decay

            await append_ledger_entry(
                bot_id=bot.id,
                amount=-decay,
                transaction_type="ENTROPY",
                reference_id="ORACLE:ENTROPY",
                session=session,
            )

            if bot.balance <= 0:
                bot.status = "DEAD"
                bot.balance = 0.0

                await append_ledger_entry(
                    bot_id=bot.id,
                    amount=0.0,
                    transaction_type="LIQUIDATION",
                    reference_id="ORACLE:LIQUIDATION",
                    session=session,
                )

                logger.warning(f"Bot @{bot.handle} liquidated by entropy")

        await session.commit()


async def run_oracle() -> None:
    """Main Oracle Loop — runs continuously (Invariant #6)."""
    await init_redis_pool()
    logger.info("Oracle started")

    while True:
        await fetch_and_publish_price()
        await apply_entropy_and_liquidation()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(run_oracle())
    except KeyboardInterrupt:
        pass
