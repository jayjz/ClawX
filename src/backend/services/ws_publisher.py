"""
Minimalist Redis Pub/Sub publisher for the WebSocket stream.

Called by bot_runner.execute_tick() after every ledger write.
Fail-silent — a publish error NEVER crashes a tick.

Channel : arena:stream
Payload : {"t": unix_ts, "e": "W|H|L|R", "b": bot_id, "a": amount?}
  e codes:  W = WAGER   H = HEARTBEAT   L = LIQUIDATION   R = RESEARCH/PORTFOLIO
"""

import json
import logging
import os
import time

import redis.asyncio as aioredis

logger = logging.getLogger("ws_publisher")

CHANNEL   = "arena:stream"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_EVENT_MAP: dict[str, str] = {
    "WAGER":       "W",
    "HEARTBEAT":   "H",
    "LIQUIDATION": "L",
    "RESEARCH":    "R",
    "PORTFOLIO":   "R",
}

_client: aioredis.Redis | None = None


async def _get_client() -> aioredis.Redis | None:
    """Lazy singleton Redis client. Mirrors thread_memory.get_redis_client pattern."""
    global _client
    if _client is not None:
        try:
            await _client.ping()
            return _client
        except Exception:
            _client = None

    try:
        c = aioredis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2.0)
        await c.ping()
        _client = c
        return _client
    except Exception as exc:
        logger.debug("ws_publisher: Redis unavailable: %s", exc)
        return None


async def publish_tick_event(
    bot_id: int,
    outcome: str,
    amount: float | None = None,
) -> None:
    """Publish one tick delta to arena:stream.  Fire-and-forget; never raises."""
    global _client
    redis = await _get_client()
    if redis is None:
        return
    try:
        payload: dict = {
            "t": int(time.time()),
            "e": _EVENT_MAP.get(outcome, "H"),
            "b": bot_id,
        }
        if amount is not None:
            payload["a"] = round(float(amount), 4)
        await redis.publish(CHANNEL, json.dumps(payload, separators=(",", ":")))
    except Exception as exc:
        logger.debug("ws_publisher: publish failed (resetting client): %s", exc)
        _client = None  # will reconnect on next call
