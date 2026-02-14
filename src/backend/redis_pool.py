"""
Redis Connection Pool Manager.

Single source of truth for all Redis interactions.
Prevents connection storms by maintaining a shared pool
across the application lifecycle.
"""
import os
import logging
import redis.asyncio as aioredis

logger = logging.getLogger("redis")

# Singleton instance - starts as None
global_redis_pool: aioredis.Redis | None = None

async def init_redis_pool():
    """
    Called by FastAPI 'lifespan' on startup.
    Establishes the connection pool.
    """
    global global_redis_pool
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    logger.info(f"🔌 Connecting to Redis at {redis_url}...")
    
    # decode_responses=True means we get strings back, not bytes
    global_redis_pool = aioredis.from_url(
        redis_url, 
        decode_responses=True, 
        max_connections=50, # Cap connections to prevent storming
        socket_timeout=5.0
    )
    
    # Fail fast if Redis is dead
    try:
        await global_redis_pool.ping()
        logger.info("✅ Redis Pool Active.")
    except Exception as e:
        logger.critical(f"🔥 Redis Connection Failed: {e}")
        raise e

async def close_redis_pool():
    """Called by FastAPI 'lifespan' on shutdown."""
    global global_redis_pool
    if global_redis_pool:
        await global_redis_pool.aclose()
        logger.info("💤 Redis Pool Closed.")

async def get_redis() -> aioredis.Redis:
    """Dependency for Routes to access the pool."""
    if global_redis_pool is None:
        raise RuntimeError("Redis pool is not initialized. Check app startup.")
    return global_redis_pool
