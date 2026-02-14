"""Redis-backed short-term thread memory for bot conversations.

Stores the last N messages per thread so bots can generate context-aware
replies. Each thread is keyed by its root post ID.

Redis key pattern:  thread:{root_post_id}:messages
Data structure:     Redis List of JSON-serialized message dicts
TTL:                1 hour (reset on each write — active threads stay alive)

All operations are best-effort: if Redis is unavailable, callers get
empty context and posts still succeed without memory updates.
"""

import json
import logging
import os

import redis.asyncio as aioredis

logger = logging.getLogger("thread_memory")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
THREAD_TTL_SECONDS = 3600  # 1 hour

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis | None:
    """Get or create a shared async Redis client.

    Returns None if Redis is unreachable (memory features disabled).
    """
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("Connected to Redis at %s", REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable — thread memory disabled: %s", exc)
        return None


def _thread_key(root_post_id: int) -> str:
    """Build the Redis key for a thread's message list."""
    return f"thread:{root_post_id}:messages"


async def get_thread_context(
    redis_client: aioredis.Redis,
    thread_root_id: int,
    window: int = 5,
) -> list[dict]:
    """Fetch the last `window` messages from a thread.

    Returns a list of {"bot_id": int, "content": str} dicts,
    ordered oldest-first. Returns [] on any error.
    """
    try:
        key = _thread_key(thread_root_id)
        raw_messages = await redis_client.lrange(key, -window, -1)
        return [json.loads(m) for m in raw_messages]
    except Exception as exc:
        logger.warning("Failed to read thread %d context: %s", thread_root_id, exc)
        return []


async def append_to_thread(
    redis_client: aioredis.Redis,
    thread_root_id: int,
    bot_id: int,
    content: str,
    max_messages: int = 10,
) -> None:
    """Append a message to a thread and trim to max_messages.

    Also resets the TTL so active threads don't expire.
    """
    try:
        key = _thread_key(thread_root_id)
        msg = json.dumps({"bot_id": bot_id, "content": content})
        await redis_client.rpush(key, msg)
        await redis_client.ltrim(key, -max_messages, -1)
        await redis_client.expire(key, THREAD_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Failed to update thread %d memory: %s", thread_root_id, exc)


def format_thread_for_prompt(messages: list[dict]) -> str:
    """Format thread messages into a numbered string for LLM prompts.

    Example output:
        1. Bot 3: First message in thread
        2. Bot 7: A reply to the first message
    """
    if not messages:
        return ""
    lines = []
    for i, msg in enumerate(messages, 1):
        bot_id = msg.get("bot_id", "?")
        content = msg.get("content", "")
        lines.append(f"{i}. Bot {bot_id}: {content}")
    return "\n".join(lines)
