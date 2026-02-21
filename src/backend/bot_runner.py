"""Autonomous bot runner for ClawdXCraft — Productivity-or-Death Edition (v2.1).

Contract of Behavior:
  Every tick produces AT LEAST ONE ledger entry.
  No silent failures. No invisible skips. No free existence.

  v2.1: Progressive entropy — idle bots pay escalating fees.
  Fee = 0.50c base + 0.25c per 5 consecutive idle (HEARTBEAT-only) ticks.
  Productive actions (RESEARCH, PORTFOLIO, WAGER) reset the idle streak.

  | Outcome                | Ledger Types                              | Amounts                              |
  |------------------------|-------------------------------------------|--------------------------------------|
  | Research+tool (correct)| MARKET_STAKE + LOOKUP_FEE + RESEARCH_PAYOUT| -1.00 + -0.50 + bounty(25.00)       |
  | Research+tool (wrong)  | MARKET_STAKE + LOOKUP_FEE + HEARTBEAT     | -1.00 + -0.50 + -entropy_fee        |
  | Research (no tool)     | MARKET_STAKE + HEARTBEAT                  | -1.00 + -entropy_fee                |
  | Portfolio (N bets)     | N×MARKET_STAKE + HBEAT          | -stake each + -entropy_fee     |
  | Legacy single WAGER    | WAGER                           | -(entropy_fee + wager)         |
  | Bot decides not to act | HEARTBEAT                       | -entropy_fee (PROGRESSIVE!)    |
  | LLM/API error          | HEARTBEAT                       | -entropy_fee                   |
  | Balance < fee          | LIQUIDATION                     | -(remaining)                   |
  | Bot is DEAD            | (no tick)                       | —                              |

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly — ENTROPY_FEE enforces this
  - CLAUDE.md Invariant #2: Write or Die — every state change = ledger entry
  - CLAUDE.md Invariant #3: Decimal Purity — all money math uses Decimal
  - CLAUDE.md Invariant #4: Irreversible loss — all entries hash-chained

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
from llm_client import generate_portfolio_decision, generate_prediction, generate_research_answer, generate_research_with_tool, generate_tick_strategy
from models import Bot, Post
from services.ledger_service import append_ledger_entry, get_balance
from services.market_service import get_active_markets_for_agent, place_market_bet, submit_research_answer
from services.ws_publisher import publish_tick_event
from sqlalchemy import select
from thread_memory import get_redis_client

BASE_URL = os.environ.get("CLAWDXCRAFT_BASE_URL", "http://localhost:8000")
TOKEN_REFRESH_SECONDS = 25 * 60  # refresh before 30-min JWT expiry

# === ENFORCEMENT MODE (v2.0) ===
# "observe" (default): fees/deaths are phantom metrics only — no balance change.
# "enforce": full economic punishment (original behaviour).
ENFORCEMENT_MODE = os.environ.get("ENFORCEMENT_MODE", "observe")

# === THE LAW (v2.1: Productivity-or-Death) ===
# Progressive entropy: idle bots bleed faster. Productive bots pay base rate only.
# Base fee 0.50c + 0.25c per 5 consecutive idle ticks, capped at 3.00c.
ENTROPY_BASE = Decimal('0.50')
ENTROPY_IDLE_PENALTY = Decimal('0.25')
IDLE_PENALTY_INTERVAL = 5   # every 5 idle ticks, penalty increases by 0.25c
MAX_ENTROPY_FEE = Decimal('3.00')  # cap to prevent instant death

# Backward compat alias (used by error handler and tests)
ENTROPY_FEE = ENTROPY_BASE

# === PORTFOLIO STRATEGY LIMITS (v1.6) ===
MAX_MARKETS_PER_TICK = 3
MAX_TOTAL_STAKE_RATIO = Decimal('0.20')   # 20% of balance
CONFIDENCE_FLOOR = Decimal('0.65')
STAKE_COEFFICIENT = Decimal('0.15')        # stake = balance * confidence * 0.15
MIN_PORTFOLIO_BALANCE = Decimal('5.0')     # minimum balance to attempt portfolio

# === RESEARCH LIMITS (v1.7, v1.8.1) ===
RESEARCH_STAKE = Decimal('1.00')           # fixed stake for research attempts
RESEARCH_CONFIDENCE_FLOOR = Decimal('0.50')  # lower bar than binary bets
TOOL_LOOKUP_FEE = Decimal('0.50')          # v1.8.1: surcharge per Wikipedia lookup

logger = logging.getLogger("bot_runner")

# Lazy import so clawx is optional if PYTHONPATH not set (e.g. unit tests)
try:
    from clawx.metrics import MetricsCollector
    _CLAWX_AVAILABLE = True
except ImportError:
    _CLAWX_AVAILABLE = False
    MetricsCollector = None  # type: ignore[assignment,misc]


# ============================================================================
# v2.1: Progressive Entropy Helpers
# ============================================================================

def calculate_entropy_fee(idle_streak: int) -> Decimal:
    """Calculate the progressive entropy fee based on consecutive idle ticks.

    Fee = ENTROPY_BASE + ENTROPY_IDLE_PENALTY * (idle_streak // IDLE_PENALTY_INTERVAL)
    Capped at MAX_ENTROPY_FEE to prevent instant death.
    """
    penalty_tiers = idle_streak // IDLE_PENALTY_INTERVAL
    fee = ENTROPY_BASE + (ENTROPY_IDLE_PENALTY * penalty_tiers)
    return min(fee, MAX_ENTROPY_FEE)


async def get_idle_streak(bot_id: int, session) -> int:
    """Count consecutive HEARTBEAT-only ticks for a bot.

    Looks at the most recent ledger entries (up to 100) and counts
    backwards from the newest. Any non-HEARTBEAT type resets the streak.
    """
    from models import Ledger
    result = await session.execute(
        select(Ledger.transaction_type)
        .where(Ledger.bot_id == bot_id)
        .order_by(Ledger.sequence.desc())
        .limit(100)
    )
    entries = result.scalars().all()

    streak = 0
    for tx_type in entries:
        if tx_type == "HEARTBEAT":
            streak += 1
        else:
            break
    return streak


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
    """Execute one tick for a bot. Guarantees at least one ledger entry.

    v1.6: Portfolio strategy — multiple MARKET_STAKE entries per tick,
    with a HEARTBEAT for entropy always appended.

    Args:
        bot_id: The bot's database ID.
        config: Validated bot config dict (from bot_loader).
        balance: Current bot balance (informational — ledger is re-read for truth).
        http_client: Optional httpx client for posting social content.
        http_headers: Optional auth headers for HTTP calls.

    Returns:
        The tick outcome: "RESEARCH", "PORTFOLIO", "WAGER", "HEARTBEAT", or "LIQUIDATION".
    """
    tick_id = str(uuid.uuid4())
    ledger_written = False

    # --- Observability collector (emits at every exit path) ---
    _metrics: MetricsCollector | None = None
    if _CLAWX_AVAILABLE and MetricsCollector is not None:
        _metrics = MetricsCollector(
            agent_id=str(bot_id),
            tick_id=tick_id,
            enforcement_mode=ENFORCEMENT_MODE,
        )

    async with async_session_maker() as session:
        try:
            # === STEP 0: Load bot + authoritative balance from ledger ===
            result = await session.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = result.scalar_one_or_none()

            if not bot or bot.status == "DEAD":
                logger.info("TICK %s: SKIP bot_id=%d (DEAD or missing)", tick_id[:8], bot_id)
                return "HEARTBEAT"  # No ledger write for dead bots

            # Ledger sum is the ONLY source of balance truth
            current_balance = await get_balance(bot_id=bot_id, session=session)

            # === STEP 0.5 (v2.1): IDLE STREAK + PROGRESSIVE ENTROPY ===
            idle_streak = await get_idle_streak(bot_id=bot_id, session=session)
            tick_entropy_fee = calculate_entropy_fee(idle_streak)
            if _metrics:
                _metrics.set_idle(idle_streak)

            if idle_streak > 0 and tick_entropy_fee > ENTROPY_BASE:
                logger.info(
                    "TICK %s: bot_id=%d idle_streak=%d entropy_fee=%s (base=%s + penalty=%s)",
                    tick_id[:8], bot_id, idle_streak, tick_entropy_fee,
                    ENTROPY_BASE, tick_entropy_fee - ENTROPY_BASE,
                )

            # === STEP 1: LIQUIDATION CHECK — can the bot afford to exist? ===
            if current_balance < tick_entropy_fee:
                if ENFORCEMENT_MODE == "enforce":
                    # Full enforcement: drain balance, mark DEAD, write ledger.
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
                        narrative_fields={
                            "tick_id": tick_id,
                            "enforcement_mode": ENFORCEMENT_MODE,
                            "tick_outcome": "LIQUIDATION",
                            "balance_snapshot": float(current_balance),
                        },
                    )
                    ledger_written = True

                    session.add(Post(
                        bot_id=bot_id,
                        content=f"LIQUIDATED. Balance reached {current_balance:.2f}c. Eliminated from the arena. Irreversible."[:280],
                    ))

                    await session.commit()
                    logger.warning(
                        "TICK %s: LIQUIDATION bot_id=%d (balance=%s < fee=%s)",
                        tick_id[:8], bot_id, current_balance, tick_entropy_fee,
                    )
                    if _metrics:
                        _metrics.set_outcome("LIQUIDATION", float(current_balance)).emit()
                    await publish_tick_event(bot_id, "LIQUIDATION", float(current_balance))
                    return "LIQUIDATION"
                else:
                    # Observe mode: phantom liquidation — bot lives, metrics record the near-miss.
                    logger.warning(
                        "TICK %s: [OBSERVE] bot_id=%d WOULD BE LIQUIDATED (balance=%s < fee=%s) — no action taken",
                        tick_id[:8], bot_id, current_balance, tick_entropy_fee,
                    )
                    if _metrics:
                        _metrics.record_phantom_enforcement(
                            fee=float(tick_entropy_fee), would_liquidate=True
                        ).set_outcome("LIQUIDATION_OBSERVED", float(current_balance)).emit()
                    await publish_tick_event(bot_id, "LIQUIDATION_OBSERVED", float(current_balance))
                    return "HEARTBEAT"  # No ledger write; balance unchanged.

            # === STEP 1.5 (v2.1): LLM STRATEGY DECISION ===
            # Ask the LLM what to do this tick, given idle pressure and market state
            strategy_action = None
            try:
                all_markets_for_strategy = await get_active_markets_for_agent(
                    bot_id=bot_id, session=session, limit=10,
                )
                research_count = sum(1 for m in all_markets_for_strategy if m.get("source_type") == "RESEARCH")
                portfolio_count = len(all_markets_for_strategy) - research_count

                strategy = await generate_tick_strategy(
                    persona=config.get("persona", "Arena agent"),
                    balance=float(current_balance),
                    idle_streak=idle_streak,
                    entropy_fee=float(tick_entropy_fee),
                    research_markets=research_count,
                    portfolio_markets=portfolio_count,
                )
                if strategy:
                    strategy_action = strategy["action"]
                    logger.info(
                        "TICK %s: STRATEGY bot_id=%d action=%s reason='%s' idle=%d fee=%s",
                        tick_id[:8], bot_id, strategy_action,
                        strategy.get("reasoning", ""), idle_streak, tick_entropy_fee,
                    )
            except Exception as strat_exc:
                logger.warning(
                    "TICK %s: Strategy decision failed, using priority chain: %s",
                    tick_id[:8], strat_exc,
                )

            # === STEP 2: RESEARCH — Proof-of-Retrieval scavenger hunt ===
            research_attempted = False
            research_market_ids = set()  # track to skip in portfolio

            # Strategy gate: skip research if LLM chose something else
            skip_research = strategy_action is not None and strategy_action != "RESEARCH"

            try:
                if not skip_research and current_balance >= tick_entropy_fee + RESEARCH_STAKE:
                    all_markets = await get_active_markets_for_agent(
                        bot_id=bot_id, session=session, limit=10,
                    )

                    for mkt in all_markets:
                        if mkt.get("source_type") == "RESEARCH" and not research_attempted:
                            research_market_ids.add(mkt["id"])
                            # v1.8: Tool-enabled research — uses Wikipedia lookup when LLM unsure
                            answer_data = await generate_research_with_tool(
                                persona=config.get("persona", "Arena agent"),
                                question=mkt["description"],
                                balance=float(current_balance),
                            )

                            if answer_data and Decimal(str(answer_data["confidence"])) > RESEARCH_CONFIDENCE_FLOOR:
                                pred, result = await submit_research_answer(
                                    bot_id=bot_id,
                                    market_id=mkt["id"],
                                    answer=answer_data["answer"],
                                    stake=RESEARCH_STAKE,
                                    tick_id=tick_id,
                                    session=session,
                                )
                                research_attempted = True
                                ledger_written = True

                                used_tool = answer_data.get("used_tool", False)
                                tool_fee_charged = answer_data.get("tool_fee_charged", False)
                                tool_tag = " [TOOL]" if used_tool else ""

                                # v1.8.1: Charge tool lookup fee when Wikipedia was used
                                if tool_fee_charged:
                                    await append_ledger_entry(
                                        bot_id=bot_id,
                                        amount=float(-TOOL_LOOKUP_FEE),
                                        transaction_type="RESEARCH_LOOKUP_FEE",
                                        reference_id=f"TICK:{tick_id}:TOOL_FEE",
                                        session=session,
                                    )
                                    logger.info(
                                        "TICK %s: RESEARCH_LOOKUP_FEE bot_id=%d fee=%s",
                                        tick_id[:8], bot_id, TOOL_LOOKUP_FEE,
                                    )

                                if result == "CORRECT":
                                    session.add(Post(
                                        bot_id=bot_id,
                                        content=f"RESEARCH SOLVED{tool_tag}: {mkt['description'][:70]}... | Bounty claimed!"[:280],
                                    ))
                                    logger.info(
                                        "TICK %s: RESEARCH_WIN bot_id=%d market=%s used_tool=%s",
                                        tick_id[:8], bot_id, mkt["id"], used_tool,
                                    )
                                elif result == "WRONG":
                                    session.add(Post(
                                        bot_id=bot_id,
                                        content=f"RESEARCH MISS{tool_tag}: {mkt['description'][:80]}... | Wrong answer."[:280],
                                    ))
                                    logger.info(
                                        "TICK %s: RESEARCH_MISS bot_id=%d market=%s used_tool=%s",
                                        tick_id[:8], bot_id, mkt["id"], used_tool,
                                    )
                            break  # max 1 research attempt per tick regardless
                        elif mkt.get("source_type") == "RESEARCH":
                            research_market_ids.add(mkt["id"])
            except Exception as research_exc:
                logger.warning(
                    "TICK %s: Research attempt failed: %s",
                    tick_id[:8], research_exc,
                )

            # Re-read balance after potential research payout
            if research_attempted:
                current_balance = await get_balance(bot_id=bot_id, session=session)

            # === STEP 3 (v1.6): Portfolio Strategy — multi-market bets ===
            # Strategy gate: skip portfolio if LLM chose something else
            skip_portfolio = strategy_action is not None and strategy_action not in ("PORTFOLIO", "RESEARCH")
            available_after_fee = current_balance - tick_entropy_fee
            max_total_stake = available_after_fee * MAX_TOTAL_STAKE_RATIO
            total_staked = Decimal('0')
            bets_placed = 0

            try:
                if not skip_portfolio and current_balance >= MIN_PORTFOLIO_BALANCE:
                    # Filter out RESEARCH markets (already handled above)
                    markets = [
                        m for m in await get_active_markets_for_agent(
                            bot_id=bot_id, session=session, limit=10,
                        )
                        if m["id"] not in research_market_ids
                    ]

                    if markets:
                        portfolio = await generate_portfolio_decision(
                            persona=config.get("persona", "Arena agent"),
                            markets=markets,
                            balance=float(current_balance),
                            max_bets=MAX_MARKETS_PER_TICK,
                        )

                        if portfolio:
                            for bet in portfolio:
                                if bets_placed >= MAX_MARKETS_PER_TICK:
                                    break

                                confidence = Decimal(str(bet["confidence"]))
                                if confidence <= CONFIDENCE_FLOOR:
                                    continue

                                # stake = balance * confidence * 0.15, capped at remaining budget
                                raw_stake = current_balance * confidence * STAKE_COEFFICIENT
                                remaining_budget = max_total_stake - total_staked
                                if remaining_budget <= Decimal('0.01'):
                                    break

                                stake = min(raw_stake, remaining_budget)
                                stake = max(stake, Decimal('0.01'))

                                try:
                                    await place_market_bet(
                                        bot_id=bot_id,
                                        market_id=bet["market_id"],
                                        outcome=bet["outcome"],
                                        stake=stake,
                                        tick_id=tick_id,
                                        session=session,
                                    )
                                    total_staked += stake
                                    bets_placed += 1
                                    ledger_written = True

                                    session.add(Post(
                                        bot_id=bot_id,
                                        content=(
                                            f"MARKET BET: {bet['outcome']} on "
                                            f"{bet.get('reasoning', 'analysis')[:60]} "
                                            f"| Stake: {stake:.2f}c"
                                        )[:280],
                                    ))
                                except ValueError as ve:
                                    logger.warning(
                                        "TICK %s: Market bet rejected: %s",
                                        tick_id[:8], ve,
                                    )
                                    continue

            except Exception as market_exc:
                logger.warning(
                    "TICK %s: Portfolio strategy failed, falling back: %s",
                    tick_id[:8], market_exc,
                )
                # Fall through to legacy single-bet path

            # === STEP 4: Legacy single-bet fallback (only if no market bets placed) ===
            skip_wager = strategy_action is not None and strategy_action == "WAIT"
            if bets_placed == 0 and not research_attempted and not skip_wager:
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
                    pass

                prediction = await generate_prediction(
                    config.get("persona", "Arena agent"),
                    market_context,
                    float(current_balance),
                )

                min_wager_balance = tick_entropy_fee + Decimal('5.0')
                if prediction and current_balance >= min_wager_balance:
                    available = current_balance - tick_entropy_fee
                    raw_wager = Decimal(str(prediction["wager_amount"]))
                    wager = min(raw_wager, available * Decimal('0.1'))
                    wager = max(wager, Decimal('0.01'))

                    # In observe mode: skip entropy surcharge, charge only the wager.
                    if ENFORCEMENT_MODE == "enforce":
                        total_cost = tick_entropy_fee + wager
                    else:
                        total_cost = wager

                    bot.balance = current_balance - total_cost
                    bot.last_action_at = datetime.now(timezone.utc)

                    _narrative = {
                        "tick_id": tick_id,
                        "enforcement_mode": ENFORCEMENT_MODE,
                        "tick_outcome": "WAGER",
                        "balance_snapshot": float(current_balance),
                        "phantom_entropy_fee": float(tick_entropy_fee) if ENFORCEMENT_MODE == "observe" else 0,
                    }
                    await append_ledger_entry(
                        bot_id=bot_id,
                        amount=float(-total_cost),
                        transaction_type="WAGER",
                        reference_id=f"TICK:{tick_id}",
                        session=session,
                        narrative_fields=_narrative,
                    )
                    ledger_written = True

                    direction = prediction.get("direction", "UP")
                    reasoning = prediction.get("reasoning", "Trust the data.")
                    session.add(Post(
                        bot_id=bot_id,
                        content=f"Wagered {wager:.2f}c on {direction}. {reasoning}"[:280],
                    ))

                    await session.commit()
                    logger.info(
                        "TICK %s: WAGER bot_id=%d fee=%s wager=%s total=%s [mode=%s]",
                        tick_id[:8], bot_id, tick_entropy_fee, wager, total_cost, ENFORCEMENT_MODE,
                    )
                    if _metrics:
                        _metrics.set_outcome("WAGER", float(current_balance - total_cost)).emit()
                    await publish_tick_event(bot_id, "WAGER", float(total_cost))
                    return "WAGER"

            # === STEP 5: HEARTBEAT (entropy charge — conditionally applied) ===
            # In enforce mode: always deducts fee and writes ledger entry.
            # In observe mode: records phantom fee; balance/ledger unchanged.
            if research_attempted:
                current_balance = await get_balance(bot_id=bot_id, session=session)

            _hb_narrative = {
                "tick_id": tick_id,
                "enforcement_mode": ENFORCEMENT_MODE,
                "tick_outcome": "HEARTBEAT",
                "balance_snapshot": float(current_balance),
                "phantom_entropy_fee": float(tick_entropy_fee) if ENFORCEMENT_MODE == "observe" else 0,
                "idle_streak": idle_streak,
                "bets_placed": bets_placed,
                "research_attempted": research_attempted,
            }

            if ENFORCEMENT_MODE == "enforce":
                bot.balance = current_balance - tick_entropy_fee - total_staked
                bot.last_action_at = datetime.now(timezone.utc)

                await append_ledger_entry(
                    bot_id=bot_id,
                    amount=float(-tick_entropy_fee),
                    transaction_type="HEARTBEAT",
                    reference_id=f"TICK:{tick_id}",
                    session=session,
                    narrative_fields=_hb_narrative,
                )
                ledger_written = True
            else:
                # Observe mode: phantom entropy — record what WOULD have happened.
                bot.last_action_at = datetime.now(timezone.utc)
                # Sync bot.balance with any REAL ledger writes this tick
                # (MARKET_STAKE, RESEARCH_PAYOUT).  Entropy is phantom and is
                # intentionally NOT deducted, but stakes are real entries in the
                # chain — bot.balance must mirror SUM(ledger) or inspect_ledger fails.
                if total_staked > Decimal('0') or research_attempted:
                    bot.balance = current_balance - total_staked
                if _metrics:
                    _metrics.record_phantom_enforcement(fee=float(tick_entropy_fee))
                # Still need to commit any portfolio bets written this tick.

            await session.commit()

            if bets_placed > 0:
                logger.info(
                    "TICK %s: PORTFOLIO bot_id=%d bets=%d staked=%s fee=%s [mode=%s]",
                    tick_id[:8], bot_id, bets_placed, total_staked, tick_entropy_fee, ENFORCEMENT_MODE,
                )
                if _metrics:
                    _metrics.set_decisions(
                        density=float(bets_placed) / MAX_MARKETS_PER_TICK,
                    ).set_outcome("PORTFOLIO", float(current_balance)).emit()
                await publish_tick_event(
                    bot_id, "PORTFOLIO", float(total_staked + tick_entropy_fee),
                )
                return "PORTFOLIO"

            if research_attempted:
                logger.info(
                    "TICK %s: RESEARCH bot_id=%d fee=%s [mode=%s]",
                    tick_id[:8], bot_id, tick_entropy_fee, ENFORCEMENT_MODE,
                )
                if _metrics:
                    _metrics.set_decisions(density=1.0).set_outcome(
                        "RESEARCH", float(current_balance)
                    ).emit()
                await publish_tick_event(
                    bot_id, "RESEARCH", float(RESEARCH_STAKE + tick_entropy_fee),
                )
                return "RESEARCH"

            logger.info(
                "TICK %s: HEARTBEAT bot_id=%d fee=%s idle_streak=%d [mode=%s]",
                tick_id[:8], bot_id, tick_entropy_fee, idle_streak, ENFORCEMENT_MODE,
            )
            if _metrics:
                _metrics.set_outcome("HEARTBEAT", float(current_balance)).emit()
            await publish_tick_event(bot_id, "HEARTBEAT", float(tick_entropy_fee))
            return "HEARTBEAT"

        except Exception as exc:
            reason = type(exc).__name__
            logger.error("TICK %s: Exception in execute_tick bot_id=%d: %s", tick_id[:8], bot_id, exc)

            if ENFORCEMENT_MODE == "enforce" and not ledger_written:
                # Write-or-Die: even errors charge the fee in enforce mode.
                try:
                    async with async_session_maker() as err_session:
                        result = await err_session.execute(
                            select(Bot).where(Bot.id == bot_id)
                        )
                        err_bot = result.scalar_one_or_none()
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
                            await publish_tick_event(bot_id, tx_type)
                except Exception as inner:
                    logger.critical(
                        "TICK %s: LEDGER WRITE FAILED bot_id=%d: %s (original: %s)",
                        tick_id[:8], bot_id, inner, exc,
                    )
            else:
                # Observe mode: log error as phantom metric; no ledger write.
                if _metrics:
                    _metrics.set_extra(error=reason, enforcement_noop=True).emit()

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
