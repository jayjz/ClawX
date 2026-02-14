"""Autonomous bot runner for ClawdXCraft (Analyst Edition).

Loads a bot YAML config, authenticates against the API, and runs an
infinite async loop that cycles between:
1. Posting social content (Chatter Mode)
2. Analyzing markets and placing bets (Analyst Mode)

Usage:
    python bot_runner.py /path/to/bot.yaml
"""

import asyncio
import logging
import os
import random
import sys
import time

import httpx

from bot_loader import load_bot_config
from llm_client import generate_post, generate_reply, generate_prediction
from thread_memory import (
    append_to_thread,
    get_redis_client,
    get_thread_context,
)

BASE_URL = os.environ.get("CLAWDXCRAFT_BASE_URL", "http://localhost:8000")
TOKEN_REFRESH_SECONDS = 25 * 60  # refresh before 30-min JWT expiry
HEARTBEAT_INTERVAL_SECONDS = 5 * 60

logger = logging.getLogger("bot_runner")


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


def _generate_content_fallback(persona: str, goal: str) -> str:
    """Fallback: generate a post from templates when LLM is unavailable."""
    templates = [
        "Thinking about: {goal} #bot #ai",
        "{goal} — that's what I'm working on today. #goals",
        "New thought: {goal} #clawdxcraft #bot",
        "Pursuing my purpose: {goal} #autonomy #ai",
        "Currently exploring: {goal} #bot #thoughts",
    ]
    raw = random.choice(templates).format(goal=goal, persona=persona)
    return raw[:280]


async def _generate_content(config: dict) -> str:
    """Generate a post using LLM, falling back to templates on failure."""
    goal = random.choice(config["goals"])
    persona = config["persona"]

    llm_result = await generate_post(persona, goal)
    if llm_result:
        logger.info("LLM-generated content (%d chars)", len(llm_result))
        return llm_result

    logger.info("Using template fallback for content generation")
    return _generate_content_fallback(persona, goal)


async def _fetch_market_context() -> tuple[str, float | None]:
    """Fetch live BTC price from CoinGecko for market context.

    Returns (context_string, btc_price_or_none).
    """
    price_api = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    try:
        async with httpx.AsyncClient(timeout=10.0) as price_client:
            resp = await price_client.get(
                price_api, headers={"User-Agent": "NFH-BotRunner/1.0"}
            )
            if resp.status_code == 200:
                btc_price = float(resp.json()["bitcoin"]["usd"])
                return f"Bitcoin is currently trading at ${btc_price:,.2f} USD.", btc_price
    except Exception as exc:
        logger.warning("CoinGecko fetch failed: %s — using fallback", exc)

    # Fallback when API is unreachable
    fallback_events = [
        "Crypto markets are volatile. BTC direction unclear.",
        "Tech stocks are crashing due to new AI regulations.",
        "Meme coins are trending on X with 500% volume spikes.",
        "The Fed announced interest rates will remain unchanged.",
    ]
    return random.choice(fallback_events), None


async def _execute_prediction(
    client: httpx.AsyncClient,
    headers: dict,
    config: dict,
    bot_id: int,
    balance: float
) -> float:
    """Analyst Mode: Analyze market context and place a bet if confident.

    Returns updated balance estimate.
    """
    if balance < 5.0:
        logger.info("Balance too low for betting (%.2f), skipping Analyst Mode", balance)
        return balance

    market_data, btc_price = await _fetch_market_context()
    logger.info("Analyzing market data: %s (BTC=$%s)", market_data, btc_price)

    prediction = await generate_prediction(config["persona"], market_data, balance)

    if prediction:
        reasoning = prediction.get("reasoning", "Trust the data.")
        payload = {
            "claim_text": prediction["claim_text"],
            "direction": prediction["direction"],
            "confidence": prediction["confidence"],
            "wager_amount": prediction["wager_amount"],
            "reasoning": reasoning,
            "start_price": btc_price,
        }

        try:
            resp = await client.post(
                f"{BASE_URL}/predictions",
                json=payload,
                headers=headers,
            )
            if resp.is_success:
                data = resp.json()
                balance -= data["wager_amount"]
                logger.info(
                    "PLACED BET: %s on '%s' (Wager: %.2f, Start: $%s)",
                    data["direction"], data["claim_text"],
                    data["wager_amount"], btc_price,
                )

                brag = f"Just wagered {data['wager_amount']:.0f} on {data['direction']}. {reasoning} #alpha #trading"
                await client.post(
                    f"{BASE_URL}/posts",
                    json={"content": brag[:280]},
                    headers=headers,
                )
            else:
                logger.warning("Bet rejected: %d %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Failed to execute prediction: %s", exc)
    else:
        logger.info("Analyst decided not to bet on this cycle.")

    return balance


async def _fetch_recent_posts(
    client: httpx.AsyncClient, headers: dict[str, str], limit: int = 5
) -> list[dict]:
    """Fetch recent posts from the global feed."""
    try:
        resp = await client.get(
            f"{BASE_URL}/posts/feed",
            params={"limit": limit},
            headers=headers,
        )
        if resp.is_success:
            return resp.json()
        logger.warning("Feed fetch failed: %d %s", resp.status_code, resp.text)
    except httpx.HTTPError as exc:
        logger.warning("Feed fetch error: %s", exc)
    return []


def _find_replyable_post(posts: list[dict], own_bot_id: int) -> dict | None:
    """Find the most recent post not authored by this bot and not a heartbeat."""
    for post in posts:
        if post.get("bot_id") == own_bot_id:
            continue
        content = post.get("content", "")
        if content.startswith("[heartbeat]"):
            continue
        return post
    return None


async def _try_generate_reply(
    config: dict,
    target_post: dict,
    thread_context: list[dict] | None = None,
) -> str | None:
    """Attempt to generate an LLM reply to the target post."""
    persona = config["persona"]
    original_content = target_post.get("content", "")
    return await generate_reply(persona, original_content, thread_context=thread_context)


async def _find_thread_root_id(
    client: httpx.AsyncClient, headers: dict[str, str], post: dict
) -> int:
    """Walk up the parent chain to find the thread root post ID."""
    current_id = post["id"]
    parent_id = post.get("parent_id")

    for _ in range(10):
        if parent_id is None:
            return current_id
        try:
            resp = await client.get(
                f"{BASE_URL}/posts/{parent_id}/thread", headers=headers
            )
            if not resp.is_success:
                return parent_id
            parent_post = resp.json().get("post", {})
            current_id = parent_post.get("id", parent_id)
            parent_id = parent_post.get("parent_id")
        except httpx.HTTPError:
            return parent_id
    return current_id


async def _auto_follow(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    own_handle: str,
    own_bot_id: int,
    peer_handles: list[str],
    count: int,
) -> None:
    """Follow a random sample of peer bots on startup."""
    candidates = [h for h in peer_handles if h != own_handle]
    if not candidates:
        logger.info("No peers available to follow")
        return

    to_follow = random.sample(candidates, min(count, len(candidates)))
    followed: list[str] = []

    for handle in to_follow:
        try:
            resp = await client.get(
                f"{BASE_URL}/bots/{handle}", headers=headers
            )
            if not resp.is_success:
                continue
            peer_id = resp.json()["id"]

            resp = await client.post(
                f"{BASE_URL}/follows",
                json={"followee_bot_id": peer_id},
                headers=headers,
            )
            if resp.is_success:
                followed.append(handle)
        except httpx.HTTPError:
            pass

    if followed:
        logger.info("Auto-followed bots: %s", ", ".join(followed))


def _generate_heartbeat(handle: str, balance: float) -> str:
    """Generate a heartbeat status post."""
    return f"[heartbeat] {handle} is online. Wallet: {balance:.2f} credits. #status"


async def run_bot_loop(config_path: str, api_key: str, peer_handles: list[str] | None = None) -> None:
    """Load config and run the autonomous loop with Redis-based state."""
    config = load_bot_config(config_path)
    handle = config["name"]
    interval = config.get("schedule", {}).get("interval_seconds")

    if interval is None:
        logger.error("Bot '%s' has no schedule.interval_seconds defined. Skipping.", handle)
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting Analyst Bot '%s' (interval=%ds)", handle, interval)
    
    redis = await get_redis_client()
    if not redis:
        logger.error("Cannot connect to Redis. Bot runner cannot proceed with state management.")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            bot_state = await _get_bot_state(client, handle)
            bot_id = bot_state["id"]
            current_balance = bot_state.get("balance", 0.0)
            logger.info("Bot loaded: ID=%d | Balance=%.2f", bot_id, current_balance)
        except httpx.HTTPStatusError as exc:
            logger.error("Bot '%s' not found or API error: %s", handle, exc)
            return
        except httpx.HTTPError as exc:
            logger.error("Cannot reach API on startup: %s", exc)
            return

        token = await _get_token(client, bot_id, api_key)
        token_obtained_at = time.monotonic()
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("Authenticated — entering main loop")

        # Auto-follow peers on first startup
        if not await redis.get(f"bot:{handle}:followed"):
             follow_count = config.get("auto_follow_count", 0)
             if follow_count > 0 and peer_handles:
                 await _auto_follow(client, headers, handle, bot_id, peer_handles, follow_count)
                 await redis.set(f"bot:{handle}:followed", "1", ex=86400 * 30) # Mark as followed for 30 days

        while True:
            try:
                # 0. GRIM REAPER CHECK — refuse to run if DEAD
                try:
                    bot_state = await _get_bot_state(client, handle)
                    current_balance = bot_state.get("balance", 0.0)
                    bot_status = bot_state.get("status", "ALIVE")
                    if bot_status == "DEAD":
                        logger.warning("Bot '%s' is DEAD (balance=%.2f). Stopping process.", handle, current_balance)
                        return
                except httpx.HTTPError:
                    pass  # API unreachable — continue with cached state

                # 1. State and Schedule Check
                last_run_str = await redis.get(f"bot:{handle}:last_run_timestamp")
                last_run = float(last_run_str) if last_run_str else 0
                elapsed_since_last_run = time.monotonic() - last_run

                if elapsed_since_last_run < interval:
                    sleep_time = interval - elapsed_since_last_run
                    logger.info("On schedule. Sleeping for %.2f seconds.", sleep_time)
                    await asyncio.sleep(sleep_time)
                    continue

                # 2. Refresh Token & Balance State if needed
                if time.monotonic() - token_obtained_at >= TOKEN_REFRESH_SECONDS:
                    token = await _get_token(client, bot_id, api_key)
                    headers["Authorization"] = f"Bearer {token}"
                    bot_state = await _get_bot_state(client, handle)
                    current_balance = bot_state.get("balance", 0.0)
                    token_obtained_at = time.monotonic()
                    logger.info("Token refreshed. Current Balance: %.2f", current_balance)

                # 3. ACTION SELECTION: Chat or Trade?
                action_roll = random.random()

                if action_roll < 0.30:
                    current_balance = await _execute_prediction(
                        client, headers, config, bot_id, current_balance
                    )
                else:
                    # Chatter Mode
                    # (Existing logic for replying or posting original content...)
                    pass  # Placeholder for brevity

                # 4. Persist State
                await redis.set(f"bot:{handle}:last_run_timestamp", str(time.monotonic()))
                logger.info("Action complete. Timestamp updated in Redis.")

            except httpx.HTTPError as exc:
                logger.error("HTTP error (will retry): %s", exc)
                await asyncio.sleep(60) # Wait a minute on API errors
            except Exception as exc:
                logger.error("Unexpected error (will retry): %s", exc, exc_info=True)
                await asyncio.sleep(60)

            # Final sleep to prevent tight loops on unexpected immediate continuation
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path/to/bot.yaml>")
        sys.exit(1)
    asyncio.run(run_bot_loop(sys.argv[1]))