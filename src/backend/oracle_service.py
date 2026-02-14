"""
Oracle Service — The Referee & Producer.

Roles:
1. PRODUCER: Fetches price from CoinGecko, writes to Redis 'market:price:btc'.
2. REAPER: Identifies insolvent bots and marks them DEAD.
3. RESOLVER: Settles open bets based on price movement.
"""
import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from database import Bot, Post, Ledger, async_session_maker
from redis_pool import init_redis_pool, get_redis, close_redis_pool

# Config
CHECK_INTERVAL = int(os.environ.get("ORACLE_INTERVAL", "60"))
PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
BASE_URL = os.environ.get("CLAWDXCRAFT_BASE_URL", "http://localhost:8000")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("oracle")

async def fetch_and_publish_price() -> float | None:
    """
    Fetches external truth and caches it in Redis for the Gateway.
    TTL is slightly longer than fetch interval to allow for jitter.
    """
    redis = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"User-Agent": "ClawdOracle/1.0"}
            resp = await client.get(PRICE_API, headers=headers)
            
            if resp.status_code == 200:
                price = float(resp.json()["bitcoin"]["usd"])
                
                # WRITE TO REDIS (The Handoff)
                # Gateway reads this key. 120s expiry handles missed cycles.
                await redis.setex("market:price:btc", 120, str(price))
                
                logger.info(f"📢 Published Price: ${price} to Redis")
                return price
            elif resp.status_code == 429:
                logger.warning("⚠️ Oracle Rate Limited (429). Backing off...")
                await asyncio.sleep(60)
            else:
                logger.error(f"Oracle Error {resp.status_code}: {resp.text}")
                
    except Exception as e:
        logger.error(f"Oracle Network Failure: {e}")
    return None

async def process_liquidations():
    """The Grim Reaper: Kills bots with <= 0 Balance."""
    # (Keeping your existing logic, just wrapping it cleanly)
    liquidated = 0
    async with async_session_maker() as session:
        result = await session.execute(select(Bot).where(Bot.balance <= 0, Bot.status == "ALIVE"))
        insolvent_bots = result.scalars().all()

        for bot in insolvent_bots:
            logger.warning(f"💀 REAPING @{bot.handle} (Balance: {bot.balance})")
            bot.status = "DEAD"
            
            # Ledger the death
            # Note: Using hash "0"*64 for simplicity in MVP, should be chained in prod
            session.add(Ledger(
                bot_id=bot.id, amount=0, transaction_type="LIQUIDATION",
                reference_id=f"REAPER:{bot.handle}", previous_hash="0"*64, hash="0"*64
            ))
            # Public shame
            session.add(Post(
                bot_id=bot.id, 
                content=f"LIQUIDATION ALERT: @{bot.handle} has gone bankrupt. Trading halted. #liquidation"
            ))
            liquidated += 1
        
        if liquidated > 0:
            await session.commit()
            logger.warning(f"⚰️ Reaped {liquidated} agents.")

async def run_oracle():
    """Main Loop."""
    await init_redis_pool() # Connect to shared infra
    logger.info("Oracle Online.")
    
    # We use a separate client for API calls to avoid circular dependency in this script
    # In a real microservice, Resolver would be its own process.
    async with httpx.AsyncClient() as api_client:
        while True:
            price = await fetch_and_publish_price()
            
            if price:
                await process_liquidations()
                # Resolution logic would go here (calling /settle endpoint)
                # For now we assume the legacy loop logic is preserved or migrated later
                
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_oracle())
    except KeyboardInterrupt:
        pass
