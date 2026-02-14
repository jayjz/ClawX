"""
Redis Connection Pool Manager.
Single source of truth for all Redis interactions.
"""
import os
import logging
import redis.asyncio as aioredis

logger = logging.getLogger("redis")

global_redis_pool: aioredis.Redis | None = None

async def init_redis_pool():
    """Called on app startup."""
    global global_redis_pool
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    logger.info(f"🔌 Connecting to Redis at {redis_url}...")
    
    global_redis_pool = aioredis.from_url(
        redis_url, 
        decode_responses=True, 
        max_connections=50, 
        socket_timeout=5.0
    )
    try:
        await global_redis_pool.ping()
        logger.info("✅ Redis Pool Active.")
    except Exception as e:
        logger.critical(f"🔥 Redis Connection Failed: {e}")
        raise e

async def close_redis_pool():
    global global_redis_pool
    if global_redis_pool:
        await global_redis_pool.aclose()
        logger.info("💤 Redis Pool Closed.")

async def get_redis() -> aioredis.Redis:
    if global_redis_pool is None:
        raise RuntimeError("Redis pool not initialized.")
    return global_redis_pool
