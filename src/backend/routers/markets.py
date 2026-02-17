"""
markets.py — API router for multi-modal data markets (v1.2).

Endpoints:
  GET  /active           — List OPEN markets
  POST /                 — Create a new market
  POST /{market_id}/predict — Stub: acknowledge a prediction (no ledger writes)
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import (
    GithubCriteria,
    Market,
    MarketCreate,
    MarketPredictRequest,
    MarketResponse,
    MarketSourceType,
    MarketStatus,
    NewsCriteria,
    ResearchCriteria,
    WeatherCriteria,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Map source_type → criteria validator
CRITERIA_VALIDATORS = {
    MarketSourceType.GITHUB: GithubCriteria,
    MarketSourceType.NEWS: NewsCriteria,
    MarketSourceType.WEATHER: WeatherCriteria,
    MarketSourceType.RESEARCH: ResearchCriteria,
}


def _market_to_response(m: Market) -> MarketResponse:
    return MarketResponse(
        id=str(m.id),
        description=m.description,
        source_type=m.source_type,
        resolution_criteria=m.resolution_criteria,
        status=m.status,
        outcome=m.outcome,
        bounty=m.bounty,
        deadline=m.deadline.isoformat() if m.deadline else "",
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


@router.get("/active", response_model=list[MarketResponse])
async def list_active_markets(
    session: AsyncSession = Depends(get_session),
) -> list[MarketResponse]:
    """Return all OPEN markets, ordered by deadline (soonest first)."""
    result = await session.execute(
        select(Market)
        .where(Market.status == MarketStatus.OPEN)
        .order_by(Market.deadline.asc())
    )
    markets = result.scalars().all()
    return [_market_to_response(m) for m in markets]


@router.post("/", response_model=MarketResponse, status_code=201)
async def create_market(
    payload: MarketCreate,
    session: AsyncSession = Depends(get_session),
) -> MarketResponse:
    """Create a new market. Validates resolution_criteria against source_type."""
    # Validate criteria per source type
    validator = CRITERIA_VALIDATORS.get(payload.source_type)
    if not validator:
        raise HTTPException(status_code=422, detail=f"Unknown source_type: {payload.source_type}")

    try:
        validator(**payload.resolution_criteria)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid resolution_criteria for {payload.source_type.value}: {e}",
        )

    # Parse deadline
    try:
        deadline = datetime.fromisoformat(payload.deadline)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid deadline format. Use ISO 8601.")

    market = Market(
        id=uuid.uuid4(),
        description=payload.description,
        source_type=payload.source_type,
        resolution_criteria=payload.resolution_criteria,
        bounty=payload.bounty,
        deadline=deadline,
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)

    logger.info("Market created: %s [%s]", market.id, market.source_type.value)
    return _market_to_response(market)


@router.post("/{market_id}/predict")
async def predict_on_market(
    market_id: str,
    payload: MarketPredictRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Stub: acknowledge a prediction on a market. No ledger writes yet."""
    try:
        mid = uuid.UUID(market_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid market_id format")

    result = await session.execute(select(Market).where(Market.id == mid))
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.status != MarketStatus.OPEN:
        raise HTTPException(status_code=409, detail=f"Market is {market.status.value}, not OPEN")

    logger.info(
        "Prediction stub: market=%s outcome=%s stake=%s",
        market_id, payload.outcome, payload.stake,
    )
    return {"status": "acknowledged", "market_id": market_id, "outcome": payload.outcome}
