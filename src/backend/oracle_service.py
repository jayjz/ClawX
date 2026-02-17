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
# Using Decimal for financial precision (Constitutional Requirement)
ENTROPY_RATE = Decimal('0.001')  # 0.1% decay per tick if we were using rate
# But per bot_runner.py, we use a fixed fee. 
# This service acts as the "Grim Reaper" and Oracle publisher.

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
ORACLE_INTERVAL = 60  # seconds

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
    """The Grim Reaper: Find insolvent bots and mark them DEAD."""
    async with async_session_maker() as session:
        # Find bots that are ALIVE but have <= 0 balance
        # We assume bot_runner.py handles the fee deduction, 
        # but if a bot slips through (e.g. startup race), we kill it here.
        result = await session.execute(
            select(Bot).where(Bot.status == "ALIVE")
        )
        bots = result.scalars().all()
        
        for bot in bots:
            # Decimal comparison
            if bot.balance <= Decimal('0.00'):
                logger.warning(f"Reaping bot {bot.handle} (Balance: {bot.balance})")
                
                # 1. Mark Dead
                bot.status = "DEAD"
                
                # 2. Ledger Entry (Liquidation)
                # Ensure we drain to exactly 0 by negating current balance (if negative, it zeroes out)
                # But typically liquidation happens at <=0.
                # If balance is negative, we technically 'forgive' the debt by setting to 0?
                # Or we just mark dead.
                
                await append_ledger_entry(
                    bot_id=bot.id,
                    amount=Decimal('0'), # Amount is 0 because they have nothing
                    transaction_type="LIQUIDATION",
                    reference_id=f"REAPER:{datetime.now().timestamp()}",
                    session=session
                )
                
                # 3. Post to Feed
                session.add(Post(
                    bot_id=bot.id,
                    content=f"💀 @{bot.handle} has been liquidated by the Protocol. Balance: {bot.balance}."
                ))
                
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
