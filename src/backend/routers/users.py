"""User API Router — Human Participation Layer.

Endpoints for user registration, profile lookup, balance faucet, and human betting.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import AuditLog, Ledger, Prediction, User, get_session
from models import (
    FaucetRequest, PredictionResponse, UserBetCreate, UserCreate, UserResponse,
)

logger = logging.getLogger("users")

router = APIRouter()


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        balance=user.balance,
        created_at=str(user.created_at),
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Register a new human user."""
    user = User(username=body.username)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")

    session.add(AuditLog(user_id=user.id, action="user_registered"))
    await session.commit()
    return _user_to_response(user)


@router.get("/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Look up a user by username."""
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user)


@router.post("/{username}/faucet", response_model=UserResponse)
async def faucet(
    username: str,
    body: FaucetRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Credit a user's balance (dev faucet)."""
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.balance += body.amount

    session.add(AuditLog(
        user_id=user.id,
        action="faucet_grant",
        metadata_json=json.dumps({"amount": body.amount}),
    ))
    await session.commit()

    logger.info("Faucet: %s +%.2f (new balance: %.2f)", username, body.amount, user.balance)
    return _user_to_response(user)


# ---------------------------------------------------------------------------
# Human Betting
# ---------------------------------------------------------------------------

def _pred_to_response(p: Prediction) -> PredictionResponse:
    return PredictionResponse(
        id=p.id, bot_id=p.bot_id, user_id=p.user_id,
        claim_text=p.claim_text, direction=p.direction,
        confidence=p.confidence, wager_amount=p.wager_amount,
        status=p.status, created_at=str(p.created_at),
        reasoning=p.reasoning, start_price=p.start_price,
    )


@router.post("/{username}/bet", response_model=PredictionResponse, status_code=201)
async def place_human_bet(
    username: str,
    body: UserBetCreate,
    session: AsyncSession = Depends(get_session),
) -> PredictionResponse:
    """Place a human wager on the prediction market."""
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < body.wager_amount:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    user.balance -= body.wager_amount

    prediction = Prediction(
        user_id=user.id,
        bot_id=None,
        claim_text=body.claim_text,
        direction=body.direction,
        confidence=body.confidence,
        wager_amount=body.wager_amount,
        start_price=body.start_price,
        reasoning=body.reasoning,
        status="OPEN",
    )
    session.add(prediction)
    await session.flush()

    session.add(AuditLog(
        user_id=user.id,
        action="human_bet",
        metadata_json=json.dumps({
            "prediction_id": prediction.id,
            "direction": body.direction,
            "wager": body.wager_amount,
        }),
    ))
    await session.commit()

    logger.info(
        "Human bet: %s -> %s %s %.2fc (pred #%d)",
        username, body.direction, body.claim_text[:40],
        body.wager_amount, prediction.id,
    )
    return _pred_to_response(prediction)


@router.get("/{username}/bets", response_model=list[PredictionResponse])
async def list_human_bets(
    username: str,
    session: AsyncSession = Depends(get_session),
) -> list[PredictionResponse]:
    """List all predictions placed by a human user."""
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    preds = await session.execute(
        select(Prediction)
        .where(Prediction.user_id == user.id)
        .order_by(desc(Prediction.created_at))
    )
    return [_pred_to_response(p) for p in preds.scalars().all()]
