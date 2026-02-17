"""
market_maker.py — Automated market generation for the arena.

v1.7: Generates RESEARCH markets from random Wikipedia articles.
The answer (pageid) is stored as a SHA256 hash in resolution_criteria,
never as plaintext — preventing cheat-by-inspection.

Constitutional references:
  - CLAUDE.md Invariant #4: "External Truth" — Wikipedia as verifiable source
  - CLAUDE.md Invariant #3: "Decimal Purity" — bounty uses Decimal
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Market, MarketSourceType, MarketStatus
from services.feed_ingestor import AsyncFeedIngestor

logger = logging.getLogger("market_maker")

RESEARCH_BOUNTY = Decimal('15.00')
RESEARCH_DEADLINE_MINUTES = 30


async def generate_research_market(session: AsyncSession) -> Market | None:
    """Generate one RESEARCH market from a random Wikipedia article.

    The question asks for the pageid. The answer_hash is SHA256(str(pageid)).
    Returns the created Market, or None if fetch/creation fails.
    Does NOT commit — caller manages transaction.
    """
    ingestor = AsyncFeedIngestor()
    summary = await ingestor.fetch_random_wikipedia_summary()

    if not summary or not summary.get("pageid"):
        logger.warning("Wikipedia fetch returned no usable data")
        return None

    answer = str(summary["pageid"])
    answer_hash = hashlib.sha256(answer.encode()).hexdigest()

    description = (
        f"RESEARCH: What is the Wikipedia page ID for the article "
        f"titled '{summary['title']}'?"
    )[:500]

    # Dedup: check if same question already OPEN
    existing = await session.execute(
        select(Market).where(
            Market.description == description,
            Market.status == MarketStatus.OPEN,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate research market skipped: %s", summary["title"])
        return None

    market = Market(
        id=uuid.uuid4(),
        description=description,
        source_type=MarketSourceType.RESEARCH,
        resolution_criteria={
            "answer_hash": answer_hash,
            "match_type": "exact_string",
        },
        bounty=RESEARCH_BOUNTY,
        deadline=datetime.now(timezone.utc) + timedelta(minutes=RESEARCH_DEADLINE_MINUTES),
    )
    session.add(market)

    logger.info(
        "Research market created: '%s' (hash=%s...)",
        summary["title"], answer_hash[:12],
    )
    return market


async def ensure_research_markets(
    session: AsyncSession,
    min_open: int = 3,
) -> int:
    """Ensure at least `min_open` RESEARCH markets are OPEN.

    Generates new markets from Wikipedia until the minimum is reached.
    Returns the number of markets created.
    """
    result = await session.execute(
        select(sa_func.count(Market.id)).where(
            Market.source_type == MarketSourceType.RESEARCH,
            Market.status == MarketStatus.OPEN,
        )
    )
    current_count = result.scalar() or 0

    created = 0
    attempts = 0
    max_attempts = min_open * 3  # guard against infinite loop on API failure

    while current_count + created < min_open and attempts < max_attempts:
        attempts += 1
        market = await generate_research_market(session)
        if market:
            created += 1

    if created > 0:
        await session.commit()
        logger.info(
            "Research markets: %d created, %d now open",
            created, current_count + created,
        )

    return created
