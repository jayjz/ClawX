"""
market_service.py — Market discovery and betting operations.

Provides agent-facing market queries and atomic bet placement
with ledger integration. Follows the same caller-manages-session
pattern as ledger_service.py.

Constitutional references:
  - CLAUDE.md Invariant #2: "Write or Die" — every stake produces a ledger entry
  - CLAUDE.md Invariant #3: "Decimal Purity" — all money math uses Decimal
  - CLAUDE.md Invariant #4: "External Truth" — markets resolved by verifiable data
"""

import hashlib
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Market, MarketPrediction, MarketSourceType, MarketStatus, PredictionStatus
from services.ledger_service import append_ledger_entry

logger = logging.getLogger("market_service")


async def get_active_markets_for_agent(
    *,
    bot_id: int,
    session: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """Return OPEN markets the bot has NOT already bet on, ordered by deadline.

    Returns list of dicts suitable for LLM context injection.
    The caller MUST hold a transactional session.
    """
    # Subquery: market IDs this bot already bet on
    already_bet = (
        select(MarketPrediction.market_id)
        .where(MarketPrediction.bot_id == bot_id)
        .scalar_subquery()
    )

    result = await session.execute(
        select(Market)
        .where(
            Market.status == MarketStatus.OPEN,
            Market.id.not_in(already_bet),
        )
        .order_by(Market.deadline.asc())
        .limit(limit)
    )
    markets = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "description": m.description,
            "source_type": m.source_type.value,
            "resolution_criteria": m.resolution_criteria,
            "bounty": str(m.bounty),
            "deadline": m.deadline.isoformat(),
        }
        for m in markets
    ]


async def place_market_bet(
    *,
    bot_id: int,
    market_id: str,
    outcome: str,
    stake: Decimal,
    tick_id: str,
    session: AsyncSession,
) -> MarketPrediction:
    """Place a bet on a market. Writes MarketPrediction + MARKET_STAKE ledger entry.

    Does NOT commit — caller manages the transaction.
    Does NOT update Bot.balance — caller must do that.

    Raises ValueError if market is not OPEN or stake <= 0.
    """
    mid = uuid.UUID(market_id)
    result = await session.execute(
        select(Market).where(Market.id == mid)
    )
    market = result.scalar_one_or_none()

    if not market:
        raise ValueError(f"Market {market_id} not found")
    if market.status != MarketStatus.OPEN:
        raise ValueError(f"Market {market_id} is {market.status.value}, not OPEN")
    if stake <= Decimal('0'):
        raise ValueError(f"Stake must be positive, got {stake}")

    # Create MarketPrediction record
    prediction = MarketPrediction(
        id=uuid.uuid4(),
        market_id=mid,
        bot_id=bot_id,
        outcome=outcome,
        stake=stake,
    )
    session.add(prediction)

    # Write MARKET_STAKE ledger entry (negative = money leaving bot)
    await append_ledger_entry(
        bot_id=bot_id,
        amount=Decimal(str(-stake)),
        transaction_type="MARKET_STAKE",
        reference_id=f"TICK:{tick_id}:MARKET:{market_id}",
        session=session,
    )

    logger.info(
        "Market bet placed: bot=%d market=%s outcome=%s stake=%s",
        bot_id, market_id, outcome, stake,
    )
    return prediction


# ---------------------------------------------------------------------------
# v1.7: Proof-of-Retrieval — RESEARCH market instant resolution
# ---------------------------------------------------------------------------

async def submit_research_answer(
    *,
    bot_id: int,
    market_id: str,
    answer: str,
    stake: Decimal,
    tick_id: str,
    session: AsyncSession,
) -> tuple[MarketPrediction | None, str]:
    """Submit a text answer to a RESEARCH market. Resolves instantly if correct.

    Returns (prediction, result) where result is "CORRECT", "WRONG", or "CLOSED".
    Does NOT commit — caller manages the transaction.
    Does NOT update Bot.balance — caller must do that.
    """
    mid = uuid.UUID(market_id)
    result = await session.execute(
        select(Market).where(Market.id == mid)
    )
    market = result.scalar_one_or_none()

    if not market:
        raise ValueError(f"Market {market_id} not found")
    if market.status != MarketStatus.OPEN:
        return (None, "CLOSED")
    if market.source_type != MarketSourceType.RESEARCH:
        raise ValueError(f"Market {market_id} is not RESEARCH type")
    if stake <= Decimal('0'):
        raise ValueError(f"Stake must be positive, got {stake}")

    clean_answer = answer.strip()

    # Create MarketPrediction with the text answer as outcome
    prediction = MarketPrediction(
        id=uuid.uuid4(),
        market_id=mid,
        bot_id=bot_id,
        outcome=clean_answer[:500],
        stake=stake,
    )
    session.add(prediction)

    # Write MARKET_STAKE ledger entry (negative = money leaving bot)
    await append_ledger_entry(
        bot_id=bot_id,
        amount=Decimal(str(-stake)),
        transaction_type="MARKET_STAKE",
        reference_id=f"TICK:{tick_id}:RESEARCH:{market_id}",
        session=session,
    )

    # === INSTANT RESOLUTION: SHA256 hash comparison ===
    expected_hash = market.resolution_criteria.get("answer_hash", "")
    user_hash = hashlib.sha256(clean_answer.encode()).hexdigest()

    if user_hash == expected_hash:
        # CORRECT — resolve market, pay bounty
        market.status = MarketStatus.RESOLVED
        market.outcome = clean_answer

        payout = market.bounty + prediction.stake
        prediction.status = PredictionStatus.WIN
        prediction.payout = payout

        await append_ledger_entry(
            bot_id=bot_id,
            amount=Decimal(str(payout)),
            transaction_type="RESEARCH_PAYOUT",
            reference_id=f"TICK:{tick_id}:RESEARCH_WIN:{market_id}",
            session=session,
        )

        logger.info(
            "RESEARCH SOLVED: bot=%d market=%s payout=%s",
            bot_id, market_id, payout,
        )
        return (prediction, "CORRECT")

    else:
        # WRONG — mark prediction as loss, market stays OPEN
        prediction.status = PredictionStatus.LOSS

        logger.info(
            "RESEARCH MISS: bot=%d market=%s answer='%s'",
            bot_id, market_id, clean_answer[:20],
        )
        return (prediction, "WRONG")
