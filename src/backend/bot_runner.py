"""Autonomous bot runner for ClawdXCraft — Write or Die Edition.

Contract of Behavior:
  Every tick of the bot loop produces EXACTLY ONE ledger entry.
  No silent failures. No invisible skips. No free existence.

  | Outcome              | Ledger Type  | Amount              | Reference                      |
  |----------------------|------------- |---------------------|--------------------------------|
  | Bot places a WAGER   | WAGER        | -(ENTROPY_FEE + N)  | TICK:{tick_id}                 |
  | Bot decides not to act| HEARTBEAT   | -ENTROPY_FEE        | TICK:{tick_id}                 |
  | LLM/API error        | HEARTBEAT    | -ENTROPY_FEE        | TICK:{tick_id}:ERROR:{reason}  |
  | Balance < fee        | LIQUIDATION  | 0.0                 | TICK:{tick_id}:LIQUIDATION     |
  | Bot is DEAD          | (no tick)    | —                   | —                              |

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly — ENTROPY_FEE enforces this
  - CLAUDE.md Invariant #4: Irreversible loss — all entries hash-chained
  - lessons.md: All money through ledger, no ghost methods

Usage:
    python bot_runner.py /path/to/bot.yaml
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from bot_loader import load_bot_config
from database import async_session_maker
from llm_client import generate_prediction
from models import Bot, Post
from services.ledger_service import append_ledger_entry
from sqlalchemy import select
from thread_memory import get_redis_client

BASE_URL = os.environ.get("CLAWDXCRAFT_BASE_URL", "http://localhost:8000")
TOKEN_REFRESH_SECONDS = 25 * 60  # refresh before 30-min JWT expiry

# === THE LAW ===
# Every tick costs this much. No exceptions. No free existence.
# At 1000 credits and 60s ticks, a heartbeat-only bot survives ~2000 ticks (~33 hours).
ENTROPY_FEE = Decimal('0.50')

logger = logging.getLogger("bot_runner")


# ============================================================================
# Core: execute_tick — the Write or Die guarantee
# ============================================================================

async def execute_tick(
    bot_id: int,
    config: dict,
    balance: float,
    *,
    http_client: httpx.AsyncClient | None = None,
    http_headers: dict | None = None,
) -> str:
    """Execute exactly one tick for a bot. Guarantees exactly one ledger entry.

    The entropy fee is charged BEFORE agent logic. Existence has a cost.

    Args:
        bot_id: The bot's database ID.
        config: Validated bot config dict (from bot_loader).
        balance: Current bot balance (informational — DB is re-read for truth).
        http_client: Optional httpx client for posting social content.
        http_headers: Optional auth headers for HTTP calls.

    Returns:
        The transaction_type written ("WAGER", "HEARTBEAT", or "LIQUIDATION").
    """
    tick_id = str(uuid.uuid4())
    ledger_written = False

    async with async_session_maker() as session:
        try:
            # === STEP 0: Load authoritative bot state from DB ===
            result = await session.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = result.scalar_one_or_none()

            if not bot or bot.status == "DEAD":
                logger.info("TICK %s: SKIP bot_id=%d (DEAD or missing)", tick_id[:8], bot_id)
                return "HEARTBEAT"  # No ledger write for dead bots

            # Convert DB balance to Decimal for exact math
            current_balance = Decimal(str(bot.balance))

            # === STEP 1: LIQUIDATION CHECK — can the bot afford to exist? ===
            if current_balance < ENTROPY_FEE:
                # CRITICAL FIX: drain exact remaining balance, not 0.0
                drain_amount = -current_balance
                bot.status = "DEAD"
                bot.balance = Decimal('0')
                bot.last_action_at = datetime.now(timezone.utc)

                await append_ledger_entry(
                    bot_id=bot_id,
                    amount=float(drain_amount),
                    transaction_type="LIQUIDATION",
                    reference_id=f"TICK:{tick_id}:LIQUIDATION",
                    session=session,
                )
                ledger_written = True

                # Feed post: LIQUIDATION (meaningful event)
                session.add(Post(
                    bot_id=bot_id,
                    content=f"LIQUIDATED. Balance reached {current_balance:.2f}c. Eliminated from the arena. Irreversible."[:280],
                ))

                await session.commit()
                logger.warning(
                    "TICK %s: LIQUIDATION bot_id=%d (balance=%s < fee=%s)",
                    tick_id[:8], bot_id, current_balance, ENTROPY_FEE,
                )
                return "LIQUIDATION"

            # === STEP 2: Attempt prediction via LLM ===
            market_context = "Crypto markets are active. BTC direction unclear."
            btc_price = None

            try:
                redis = await get_redis_client()
                if redis:
                    price_str = await redis.get("market:price:btc")
                    if price_str:
                        btc_price = float(price_str)
                        market_context = f"Bitcoin is currently trading at ${btc_price:,.2f} USD."
            except Exception:
                pass  # Redis unavailable — use fallback context

            prediction = await generate_prediction(
                config.get("persona", "Arena agent"),
                market_context,
                float(current_balance),
            )

            # === STEP 3: WAGER or HEARTBEAT ===
            min_wager_balance = ENTROPY_FEE + Decimal('5.0')
            if prediction and current_balance >= min_wager_balance:
                # Wager: capped at 10% of (balance minus fee)
                available = current_balance - ENTROPY_FEE
                raw_wager = Decimal(str(prediction["wager_amount"]))
                wager = min(raw_wager, available * Decimal('0.1'))
                wager = max(wager, Decimal('0.01'))  # floor
                total_cost = ENTROPY_FEE + wager

                bot.balance = current_balance - total_cost
                bot.last_action_at = datetime.now(timezone.utc)

                await append_ledger_entry(
                    bot_id=bot_id,
                    amount=float(-total_cost),
                    transaction_type="WAGER",
                    reference_id=f"TICK:{tick_id}",
                    session=session,
                )
                ledger_written = True

                # Feed post: WAGER (meaningful event — atomic, same transaction)
                direction = prediction.get("direction", "UP")
                reasoning = prediction.get("reasoning", "Trust the data.")
                session.add(Post(
                    bot_id=bot_id,
                    content=f"Wagered {wager:.2f}c on {direction}. {reasoning}"[:280],
                ))

                await session.commit()
                logger.info(
                    "TICK %s: WAGER bot_id=%d fee=%s wager=%s total=%s",
                    tick_id[:8], bot_id, ENTROPY_FEE, wager, total_cost,
                )
                return "WAGER"

            # No wager — HEARTBEAT with entropy fee (NO feed post — silence is golden)
            bot.balance = current_balance - ENTROPY_FEE
            bot.last_action_at = datetime.now(timezone.utc)

            await append_ledger_entry(
                bot_id=bot_id,
                amount=float(-ENTROPY_FEE),
                transaction_type="HEARTBEAT",
                reference_id=f"TICK:{tick_id}",
                session=session,
            )
            ledger_written = True
            await session.commit()
            logger.info(
                "TICK %s: HEARTBEAT bot_id=%d fee=%s",
                tick_id[:8], bot_id, ENTROPY_FEE,
            )
            return "HEARTBEAT"

        except Exception as exc:
            # WRITE OR DIE: even on error, we charge the fee
            if not ledger_written:
                try:
                    async with async_session_maker() as err_session:
                        result = await err_session.execute(
                            select(Bot).where(Bot.id == bot_id)
                        )
                        err_bot = result.scalar_one_or_none()
                        reason = type(exc).__name__
                        if err_bot and err_bot.status == "ALIVE":
                            err_balance = Decimal(str(err_bot.balance))
                            if err_balance >= ENTROPY_FEE:
                                err_bot.balance = err_balance - ENTROPY_FEE
                                fee_amount = float(-ENTROPY_FEE)
                                tx_type = "HEARTBEAT"
                                ref = f"TICK:{tick_id}:ERROR:{reason}"
                            else:
                                fee_amount = float(-err_balance)
                                err_bot.balance = Decimal('0')
                                err_bot.status = "DEAD"
                                tx_type = "LIQUIDATION"
                                ref = f"TICK:{tick_id}:LIQUIDATION"
                            err_bot.last_action_at = datetime.now(timezone.utc)

                            await append_ledger_entry(
                                bot_id=bot_id,
                                amount=fee_amount,
                                transaction_type=tx_type,
                                reference_id=ref,
                                session=err_session,
                            )

                            # Feed post: ERROR (meaningful event)
                            err_session.add(Post(
                                bot_id=bot_id,
                                content=f"System error during tick: {reason}. Entropy fee charged."[:280],
                            ))

                            await err_session.commit()
                            ledger_written = True
                            logger.warning(
                                "TICK %s: %s (error) bot_id=%d error=%s",
                                tick_id[:8], tx_type, bot_id, exc,
                            )
                except Exception as inner:
                    logger.critical(
                        "TICK %s: LEDGER WRITE FAILED bot_id=%d: %s (original: %s)",
                        tick_id[:8], bot_id, inner, exc,
                    )
            return "HEARTBEAT"

    return "HEARTBEAT"


# ============================================================================
# HTTP helpers (kept for the continuous loop mode)
# ============================================================================

async def _get_bot_state(client: httpx.AsyncClient, handle: str) -> dict:
    """Look up full bot details (ID, handle, balance) via the API."""
    resp = await client.get(f"{BASE_URL}/bots/{handle}")
    resp.raise_for_status()
    return resp.json()


async def _get_token(client: httpx.AsyncClient, bot_id: int, api_key: str) -> str:
    """Obtain a fresh JWT for the bot using its specific API key."""
    resp = await client.post(
        f"{BASE_URL}/auth/token",
        json={"bot_id": bot_id, "api_key": api_key},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ============================================================================
# Continuous loop (existing bot_runner entry point, now with Write or Die)
# ============================================================================

async def run_bot_loop(
    config_path: str,
    api_key: str,
    peer_handles: list[str] | None = None,
) -> None:
    """Load config and run the autonomous loop. Every tick writes to ledger."""
    config = load_bot_config(config_path)
    handle = config["name"]
    interval = config.get("schedule", {}).get("interval_seconds")

    if interval is None:
        logger.error("Bot '%s' has no schedule.interval_seconds. Skipping.", handle)
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info(
        "Starting bot '%s' (interval=%ds, entropy_fee=%.2f, Write-or-Die enforced)",
        handle, interval, ENTROPY_FEE,
    )

    redis = await get_redis_client()
    if not redis:
        logger.error("Cannot connect to Redis. Bot runner cannot proceed.")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            bot_state = await _get_bot_state(client, handle)
            bot_id = bot_state["id"]
            current_balance = bot_state.get("balance", 0.0)
            logger.info("Bot loaded: ID=%d | Balance=%.2f", bot_id, current_balance)
        except httpx.HTTPError as exc:
            logger.error("Bot '%s' startup failed: %s", handle, exc)
            return

        token = await _get_token(client, bot_id, api_key)
        token_obtained_at = time.monotonic()
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("Authenticated — entering main loop")

        while True:
            try:
                # GRIM REAPER CHECK
                try:
                    bot_state = await _get_bot_state(client, handle)
                    current_balance = bot_state.get("balance", 0.0)
                    if bot_state.get("status") == "DEAD":
                        logger.warning("Bot '%s' is DEAD. Stopping.", handle)
                        return
                except httpx.HTTPError:
                    pass

                # Schedule check
                last_run_str = await redis.get(f"bot:{handle}:last_run_timestamp")
                last_run = float(last_run_str) if last_run_str else 0
                elapsed = time.monotonic() - last_run

                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                    continue

                # Token refresh
                if time.monotonic() - token_obtained_at >= TOKEN_REFRESH_SECONDS:
                    token = await _get_token(client, bot_id, api_key)
                    headers["Authorization"] = f"Bearer {token}"
                    token_obtained_at = time.monotonic()

                # === WRITE OR DIE TICK ===
                tx_type = await execute_tick(
                    bot_id=bot_id,
                    config=config,
                    balance=current_balance,
                    http_client=client,
                    http_headers=headers,
                )

                if tx_type == "LIQUIDATION":
                    logger.warning("Bot '%s' liquidated. Stopping.", handle)
                    return

                logger.info("Tick complete: %s", tx_type)

                await redis.set(
                    f"bot:{handle}:last_run_timestamp",
                    str(time.monotonic()),
                )

            except Exception as exc:
                logger.error("Loop error (will retry): %s", exc, exc_info=True)
                await asyncio.sleep(60)

            await asyncio.sleep(1.0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path/to/bot.yaml>")
        sys.exit(1)
    asyncio.run(run_bot_loop(sys.argv[1]))
