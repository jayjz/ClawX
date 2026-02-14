import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select

from database import Bot, async_session_maker
from services.ledger_service import append_ledger_entry
from redis_pool import init_redis_pool, get_redis

# Configuration
CHECK_INTERVAL = int(os.environ.get("ORACLE_INTERVAL", "60"))
ENTROPY_THRESHOLD_SECONDS = 300  # 5 Minutes of inaction triggers decay
ENTROPY_RATE = 0.0005            # 0.05% decay per cycle
PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("oracle")

async def fetch_and_publish_price() -> Optional[float]:
    """
    Fetches price and Publishes to Redis for the Gateway.
    """
    redis = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                PRICE_API,
                headers={"User-Agent": "ClawdOracle/1.0"},
            )
            if resp.status_code == 200:
                price = float(resp.json()["bitcoin"]["usd"])
                
                # Publish to Redis (The Heartbeat of the Gateway)
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
    The Physics Engine: Applies time-based decay to idle bots.
    """
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bot).where(Bot.status == "ALIVE")
        )
        bots = result.scalars().all()

        for bot in bots:
            # Default to created_at if never acted
            last_action = bot.last_action_at or bot.created_at
            
            # If active recently, skip entropy
            if now - last_action <= timedelta(seconds=ENTROPY_THRESHOLD_SECONDS):
                continue

            if bot.balance <= 0:
                continue

            # Calculate Decay
            decay = ENTROPY_RATE * bot.balance
            # Ensure we don't decay into negatives purely by math
            if decay > bot.balance: 
                decay = bot.balance
            
            bot.balance -= decay

            # Log Entropy via Ledger Service
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-decay,
                transaction_type="ENTROPY",
                reference_id="ORACLE:ENTROPY",
                session=session,
            )

            # Check Liquidation
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

                logger.warning(
                    f"💀 Bot @{bot.handle} liquidated by entropy"
                )

        await session.commit()

async def run_oracle() -> None:
    """Main Oracle Loop"""
    await init_redis_pool() # Initialize Shared Redis
    logger.info("Oracle started")
    
    while True:
        # 1. Producer Phase
        await fetch_and_publish_price()

        # 2. Reaper/Entropy Phase
        await apply_entropy_and_liquidation()
        
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_oracle())
    except KeyboardInterrupt:
        pass
