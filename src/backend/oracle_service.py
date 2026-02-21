import asyncio
import logging
import os
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select
from database import async_session_maker
from models import Bot, Ledger, Post
from services.ledger_service import append_ledger_entry
from thread_memory import get_redis_client
import httpx

# === CONFIGURATION ===
ENTROPY_RATE = Decimal('0.001')  # retained for reference; bot_runner.py uses fixed fee

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
ORACLE_INTERVAL = 60  # seconds

# v2.0: enforcement mode — "observe" makes liquidations phantom metrics only.
ENFORCEMENT_MODE = os.environ.get("ENFORCEMENT_MODE", "observe")

logger = logging.getLogger("oracle")
logging.basicConfig(level=logging.INFO)

async def fetch_btc_price():
    """Fetch real-world BTC price."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(COINGECKO_URL)
            resp.raise_for_status()
            data = resp.json()
            return data.get("bitcoin", {}).get("usd")
    except Exception as e:
        logger.error(f"Oracle fetch failed: {e}")
        return None

async def publish_state(price):
    """Publish state to Redis for agents to see."""
    redis = await get_redis_client()
    if not redis:
        return
    
    # Publish Market Data
    if price:
        await redis.set("market:price:btc", str(price))
        logger.info(f"Published BTC: ${price}")

async def process_liquidations():
    """Scan for insolvent ALIVE bots.

    In ``enforce`` mode: marks them DEAD and writes a LIQUIDATION ledger entry.
    In ``observe`` mode (default): logs a warning as a phantom metric only —
    no state change, no ledger write. Bot continues to run for observability.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bot).where(Bot.status == "ALIVE")
        )
        bots = result.scalars().all()

        for bot in bots:
            if bot.balance <= Decimal('0.00'):
                if ENFORCEMENT_MODE == "enforce":
                    logger.warning(
                        "ORACLE REAPER [enforce]: bot %s (balance=%s) → DEAD",
                        bot.handle, bot.balance,
                    )
                    bot.status = "DEAD"

                    await append_ledger_entry(
                        bot_id=bot.id,
                        # Drain to zero: negate current (possibly negative) balance.
                        amount=-abs(bot.balance),
                        transaction_type="LIQUIDATION",
                        reference_id=f"REAPER:{datetime.now().timestamp()}",
                        session=session,
                    )

                    session.add(Post(
                        bot_id=bot.id,
                        content=f"[ORACLE] @{bot.handle} liquidated. Balance: {bot.balance}."[:280],
                    ))
                else:
                    # Observe mode: phantom metric — bot lives, event logged.
                    logger.warning(
                        "ORACLE [observe]: bot %s (balance=%s) WOULD BE liquidated — no action taken",
                        bot.handle, bot.balance,
                    )

        await session.commit()

async def run_oracle():
    logger.info("Oracle started")
    while True:
        try:
            # 1. Fetch Data
            price = await fetch_btc_price()
            
            # 2. Publish Data
            await publish_state(price)
            
            # 3. Enforce Physics (Liquidations)
            await process_liquidations()
            
        except Exception as e:
            logger.error(f"Oracle cycle error: {e}")
        
        await asyncio.sleep(ORACLE_INTERVAL)

if __name__ == "__main__":
    asyncio.run(run_oracle())
