"""
market_maker.py — Automated market generation for the arena.

v1.7: RESEARCH markets from Wikipedia (pageid scavenger hunt).
v2.0: All 4 source types — RESEARCH · WEATHER · GITHUB · NEWS — with
      weighted random cycling.  Each generator is self-contained and
      fail-silent; the ensure_open_markets() orchestrator retries until
      the board is adequately stocked.

Constitutional references:
  - CLAUDE.md Invariant #4: "External Truth" — all data from verifiable APIs
  - CLAUDE.md Invariant #3: "Decimal Purity" — bounties use Decimal
"""

import hashlib
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Market, MarketSourceType, MarketStatus
from services.feed_ingestor import AsyncFeedIngestor

logger = logging.getLogger("market_maker")

# ── RESEARCH ──────────────────────────────────────────────────────────────────
RESEARCH_BOUNTY            = Decimal('25.00')
RESEARCH_DEADLINE_MINUTES  = 5

# ── WEATHER ───────────────────────────────────────────────────────────────────
WEATHER_BOUNTY             = Decimal('5.00')
WEATHER_DEADLINE_MINUTES   = 30

WEATHER_CITIES = [
    {"name": "London",     "lat":  51.51,  "lon":  -0.13},
    {"name": "New York",   "lat":  40.71,  "lon": -74.00},
    {"name": "Tokyo",      "lat":  35.68,  "lon": 139.69},
    {"name": "Sydney",     "lat": -33.87,  "lon": 151.21},
    {"name": "Berlin",     "lat":  52.52,  "lon":  13.40},
    {"name": "Singapore",  "lat":   1.35,  "lon": 103.82},
    {"name": "São Paulo",  "lat": -23.55,  "lon": -46.63},
    {"name": "Cairo",      "lat":  30.04,  "lon":  31.24},
]

# ── GITHUB ────────────────────────────────────────────────────────────────────
GITHUB_BOUNTY              = Decimal('8.00')
GITHUB_DEADLINE_MINUTES    = 60

# ── NEWS ──────────────────────────────────────────────────────────────────────
NEWS_BOUNTY                = Decimal('5.00')
NEWS_DEADLINE_MINUTES      = 20

_NEWS_RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
]

# ── Weighted source dispatch ──────────────────────────────────────────────────
# RESEARCH 40 % · WEATHER 25 % · GITHUB 20 % · NEWS 15 %
_MARKET_SOURCE_WEIGHTS: dict[MarketSourceType, int] = {
    MarketSourceType.RESEARCH: 40,
    MarketSourceType.WEATHER:  25,
    MarketSourceType.GITHUB:   20,
    MarketSourceType.NEWS:     15,
}


# ── RESEARCH market generator ─────────────────────────────────────────────────

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

    answer      = str(summary["pageid"])
    answer_hash = hashlib.sha256(answer.encode()).hexdigest()

    description = (
        f"RESEARCH: What is the Wikipedia page ID for the article "
        f"titled '{summary['title']}'?"
    )[:500]

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
            "match_type":  "exact_string",
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


# ── WEATHER market generator ──────────────────────────────────────────────────

async def generate_weather_market(session: AsyncSession) -> Market | None:
    """Generate a YES/NO market on whether a city's temperature exceeds a
    threshold at market close (Open-Meteo — no API key required).

    Threshold = round(current_temp) so the bet sits at the current boundary.
    Direction is randomised so the board has both "above" and "below" markets.
    Does NOT commit — caller manages transaction.
    """
    city     = random.choice(WEATHER_CITIES)
    ingestor = AsyncFeedIngestor()
    weather  = await ingestor.fetch_weather(city["lat"], city["lon"])

    if not weather or weather.get("temperature_c") is None:
        logger.warning("Weather fetch returned no usable data for %s", city["name"])
        return None

    current_temp = float(weather["temperature_c"])
    direction    = random.choice(["above", "below"])
    threshold    = round(current_temp)

    description = (
        f"WEATHER: Will the temperature in {city['name']} be {direction} "
        f"{threshold}°C when this market closes? "
        f"(Current reading: {current_temp:.1f}°C)"
    )[:500]

    existing = await session.execute(
        select(Market).where(
            Market.description == description,
            Market.status      == MarketStatus.OPEN,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate weather market skipped: %s", city["name"])
        return None

    market = Market(
        id=uuid.uuid4(),
        description=description,
        source_type=MarketSourceType.WEATHER,
        resolution_criteria={
            "city":             city["name"],
            "lat":              city["lat"],
            "lon":              city["lon"],
            "metric":           "temperature_c",
            "operator":         ">" if direction == "above" else "<",
            "threshold":        threshold,
            "current_reading":  current_temp,
        },
        bounty=WEATHER_BOUNTY,
        deadline=datetime.now(timezone.utc) + timedelta(minutes=WEATHER_DEADLINE_MINUTES),
    )
    session.add(market)
    logger.info(
        "Weather market created: %s %s %d°C (current: %.1f°C)",
        city["name"], direction, threshold, current_temp,
    )
    return market


# ── GITHUB market generator ───────────────────────────────────────────────────

async def generate_github_market(session: AsyncSession) -> Market | None:
    """Generate a YES/NO star-milestone market for a repo from GITHUB_WATCHLIST.

    Milestone = next 500-star multiple above the current star count, so the
    question is 'Will {repo} reach {milestone} stars by market close?'
    Does NOT commit — caller manages transaction.
    """
    watchlist_raw = os.getenv(
        "GITHUB_WATCHLIST", "anthropics/claude-code,langchain-ai/langchain"
    )
    repos = [r.strip() for r in watchlist_raw.split(",") if r.strip()]
    if not repos:
        logger.warning("GITHUB_WATCHLIST is empty — skipping GitHub market")
        return None

    repo     = random.choice(repos)
    ingestor = AsyncFeedIngestor()
    data     = await ingestor.fetch_github_stars(repo)

    if not data:
        logger.warning("GitHub stars fetch failed for %s", repo)
        return None

    current_stars = int(data["stars"])
    # Milestone: next 500-boundary above current (minimum +1 so it's always future)
    milestone = ((current_stars // 500) + 1) * 500

    description = (
        f"GITHUB: Will {repo} reach {milestone:,} GitHub stars by market close? "
        f"(Currently: {current_stars:,} ★)"
    )[:500]

    # Dedup: at most one OPEN GITHUB market per repo
    existing = await session.execute(
        select(Market).where(
            Market.source_type == MarketSourceType.GITHUB,
            Market.status      == MarketStatus.OPEN,
            Market.description.contains(repo),
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate GitHub market skipped: %s", repo)
        return None

    market = Market(
        id=uuid.uuid4(),
        description=description,
        source_type=MarketSourceType.GITHUB,
        resolution_criteria={
            "repo":                   repo,
            "metric":                 "stargazers_count",
            "operator":               ">=",
            "threshold":              milestone,
            "snapshot_at_creation":   current_stars,
        },
        bounty=GITHUB_BOUNTY,
        deadline=datetime.now(timezone.utc) + timedelta(minutes=GITHUB_DEADLINE_MINUTES),
    )
    session.add(market)
    logger.info(
        "GitHub market created: %s milestone=%d (current=%d)",
        repo, milestone, current_stars,
    )
    return market


# ── NEWS market generator ─────────────────────────────────────────────────────

async def generate_news_market(session: AsyncSession) -> Market | None:
    """Generate a YES/NO market on whether a keyword appears in tech headlines.

    Data source priority:
      1. NewsAPI.org (if NEWS_API_KEY env var is set — free tier, 100 req/day)
      2. RSS fallback: TechCrunch + BBC Technology feeds (no key required)

    Does NOT commit — caller manages transaction.
    """
    keywords_raw = os.getenv("NEWS_KEYWORDS", "AI,Crypto,Regulation")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    if not keywords:
        logger.warning("NEWS_KEYWORDS is empty — skipping news market")
        return None

    keyword  = random.choice(keywords)
    ingestor = AsyncFeedIngestor()
    headlines: list[str] = []

    # Try NewsAPI first
    api_key = os.getenv("NEWS_API_KEY", "").strip()
    if api_key:
        headlines = await ingestor.fetch_newsapi_headlines(keyword, api_key)

    # RSS fallback (always runs if NewsAPI returned nothing)
    if not headlines:
        rss_url = random.choice(_NEWS_RSS_FEEDS)
        items   = await ingestor.fetch_rss(rss_url)
        headlines = [
            i["title"] for i in items
            if keyword.lower() in i["title"].lower()
        ]

    matched = len(headlines)
    description = (
        f"NEWS: Will '{keyword}' appear in tech news headlines in the next "
        f"{NEWS_DEADLINE_MINUTES} minutes? "
        f"(Currently {matched} matching headline(s) found)"
    )[:500]

    # Dedup: at most one OPEN NEWS market per keyword
    existing = await session.execute(
        select(Market).where(
            Market.source_type == MarketSourceType.NEWS,
            Market.status      == MarketStatus.OPEN,
            Market.description.contains(f"'{keyword}'"),
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate news market skipped: keyword='%s'", keyword)
        return None

    market = Market(
        id=uuid.uuid4(),
        description=description,
        source_type=MarketSourceType.NEWS,
        resolution_criteria={
            "keyword":                      keyword,
            "match_type":                   "title_contains",
            "sources":                      (
                ["newsapi.org"] if api_key else _NEWS_RSS_FEEDS
            ),
            "snapshot_matches_at_creation": matched,
        },
        bounty=NEWS_BOUNTY,
        deadline=datetime.now(timezone.utc) + timedelta(minutes=NEWS_DEADLINE_MINUTES),
    )
    session.add(market)
    logger.info(
        "News market created: keyword='%s' (current_matches=%d, via=%s)",
        keyword, matched, "newsapi" if api_key else "rss",
    )
    return market


# ── Generator dispatch table ──────────────────────────────────────────────────

_GENERATORS = {
    MarketSourceType.RESEARCH: generate_research_market,
    MarketSourceType.WEATHER:  generate_weather_market,
    MarketSourceType.GITHUB:   generate_github_market,
    MarketSourceType.NEWS:     generate_news_market,
}


# ── Orchestrators ─────────────────────────────────────────────────────────────

async def ensure_open_markets(
    session: AsyncSession,
    min_open: int = 6,
) -> int:
    """Ensure at least `min_open` total OPEN markets exist across all sources.

    Source type is chosen by weighted random selection per cycle:
      RESEARCH 40 % · WEATHER 25 % · GITHUB 20 % · NEWS 15 %

    On API failure a generator returns None; the orchestrator retries with a
    different source (up to min_open * 3 attempts total).
    Returns the number of markets created.
    """
    result = await session.execute(
        select(sa_func.count(Market.id)).where(Market.status == MarketStatus.OPEN)
    )
    current_count = result.scalar() or 0

    _types   = list(_MARKET_SOURCE_WEIGHTS.keys())
    _weights = list(_MARKET_SOURCE_WEIGHTS.values())

    created     = 0
    attempts    = 0
    max_attempts = min_open * 3  # guard against infinite loop on API failures

    while current_count + created < min_open and attempts < max_attempts:
        attempts += 1
        source    = random.choices(_types, weights=_weights, k=1)[0]
        market    = await _GENERATORS[source](session)
        if market:
            created += 1

    if created > 0:
        await session.commit()
        logger.info(
            "Open markets: %d created across all sources (%d now open total)",
            created, current_count + created,
        )

    return created


async def ensure_research_markets(
    session: AsyncSession,
    min_open: int = 3,
) -> int:
    """Ensure at least `min_open` RESEARCH markets are OPEN.

    Retained for backward compatibility — called by run_ticker.py.
    Generates new markets from Wikipedia until the minimum is reached.
    Returns the number of markets created.
    """
    result = await session.execute(
        select(sa_func.count(Market.id)).where(
            Market.source_type == MarketSourceType.RESEARCH,
            Market.status      == MarketStatus.OPEN,
        )
    )
    current_count = result.scalar() or 0

    created      = 0
    attempts     = 0
    max_attempts = min_open * 3

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
