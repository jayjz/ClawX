"""
WebSocket stream endpoint  —  GET /ws/stream

Subscribes to the arena:stream Redis Pub/Sub channel and fans out
every tick delta to all connected clients.

Each client gets its own pubsub() object (dedicated Redis connection).
The forward task is cancelled cleanly when the WebSocket closes.

Auth:  JWT required via ?token= query param  OR  Authorization: Bearer header.
       Rejected connections receive WS close code 4001 (Unauthorized) and are
       never admitted to the Redis broadcast.
       NOTE: ws.accept() is called before the close frame so that the browser
       receives a proper WS close frame (close before accept → HTTP 403, no code).

Payload forwarded verbatim from ws_publisher:
  {"t": unix_ts, "e": "W|H|L|R", "b": bot_id, "a": amount?}
"""

import asyncio
import contextlib
import logging
import os

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from redis_pool import get_redis
from utils.jwt import decode_access_token

logger  = logging.getLogger("ws")
router  = APIRouter(tags=["stream"])
CHANNEL = "arena:stream"

WS_CLOSE_UNAUTHORIZED = 4001   # application-defined: unauthorized

# Auth is required only in enforce mode running in a non-development environment.
# In observe mode or when ENV=development, unauthenticated clients are admitted
# as anonymous viewers (bot_id=0) so the frontend doesn't spam "WS rejected" logs.
_WS_AUTH_REQUIRED = (
    os.environ.get("ENFORCEMENT_MODE", "observe") == "enforce"
    and os.environ.get("ENV", "production") != "development"
)


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket) -> None:
    """Fan-out WebSocket endpoint — JWT-authenticated.

    Auth flow:
      1. Extract JWT from ?token= query param or Authorization: Bearer header.
      2. Call ws.accept() so a proper WS close frame (not HTTP 403) can be sent.
      3. Validate token with decode_access_token().
      4. On failure: ws.close(code=4001) and return — no Redis subscription opened.
      5. On success: subscribe to Redis pub/sub and fan-out events.

    Architecture:
      bot_runner (ticker process)
          └─ publish_tick_event() → Redis PUBLISH arena:stream
                                         ↓
      FastAPI (app process)
          └─ pubsub.listen() → asyncio task → ws.send_text()

    One pubsub connection per WebSocket client. Cancelled on disconnect.
    """
    # ── Extract token: ?token= query param or Authorization: Bearer header ─────
    token: str = ws.query_params.get("token", "")
    if not token:
        raw_auth = ws.headers.get("authorization", "")
        if raw_auth.startswith("Bearer "):
            token = raw_auth.removeprefix("Bearer ")

    # Accept before sending a WS close frame.
    # Closing before accept() causes uvicorn to send HTTP 403 with no WS code.
    await ws.accept()

    bot_id: int = 0  # default: anonymous viewer
    if not token:
        if _WS_AUTH_REQUIRED:
            logger.warning("WS rejected (no token): %s", ws.client)
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        logger.debug("WS anonymous connection (observe/dev mode): %s", ws.client)
    else:
        try:
            bot_id = decode_access_token(token)
        except HTTPException:
            logger.warning("WS rejected (invalid token): %s", ws.client)
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return

    # ── Authenticated (or permitted anonymous) — open Redis subscription ──────
    logger.info("WS connected: %s (bot_id=%d)", ws.client, bot_id)

    redis  = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)

    async def _forward() -> None:
        """Forward Redis pub/sub messages to the WebSocket until cancelled."""
        async for msg in pubsub.listen():
            if msg.get("type") == "message":
                try:
                    await ws.send_text(msg["data"])
                except Exception:
                    return  # WebSocket gone — let the task exit

    fwd = asyncio.create_task(_forward())
    try:
        # Block here; exits on client disconnect (receive() raises or returns disconnect frame)
        while True:
            raw = await ws.receive()
            if raw.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        fwd.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await fwd
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        logger.info("WS disconnected: %s (bot_id=%d)", ws.client, bot_id)
