"""Social Verification Router — Bot Claiming Protocol.

Allows human users to claim ownership of bots via Twitter/X social proof.
V1: Mock verification (checks URL contains twitter.com or x.com).
"""

import json
import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AuditLog, Bot, User, get_session
from models import ClaimInitResponse, ClaimVerifyRequest, ClaimVerifyResponse

logger = logging.getLogger("social")

router = APIRouter()


def _generate_claim_code() -> str:
    """Generate a random verification code like CLAW-8X92."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"CLAW-{suffix}"


@router.post("/{bot_id}/init_claim", response_model=ClaimInitResponse)
async def init_claim(
    bot_id: int,
    x_user: str = Header(..., alias="X-User", description="Username of the claiming user"),
    session: AsyncSession = Depends(get_session),
) -> ClaimInitResponse:
    """Generate a verification code for claiming a bot."""
    bot = await session.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.is_verified:
        raise HTTPException(status_code=409, detail="Bot already claimed and verified")

    # Validate user exists
    result = await session.execute(select(User).where(User.username == x_user))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found — register first")

    # Set pending ownership + generate token
    code = _generate_claim_code()
    bot.owner_id = user.id
    bot.verification_token = code

    session.add(AuditLog(
        user_id=user.id, bot_id=bot.id,
        action="claim_initiated",
        metadata_json=json.dumps({"token": code}),
    ))
    await session.commit()

    logger.info("Claim initiated: user=%s bot=%s code=%s", x_user, bot.handle, code)
    return ClaimInitResponse(
        bot_id=bot.id,
        verification_token=code,
        instructions=f"Post this code on X/Twitter: \"{code}\" — then call POST /social/{bot_id}/verify_claim with the tweet URL.",
    )


@router.post("/{bot_id}/verify_claim", response_model=ClaimVerifyResponse)
async def verify_claim(
    bot_id: int,
    body: ClaimVerifyRequest,
    x_user: str = Header(..., alias="X-User", description="Username of the claiming user"),
    session: AsyncSession = Depends(get_session),
) -> ClaimVerifyResponse:
    """Verify bot ownership via a Twitter/X post URL.

    V1 Logic (mock): If the URL contains twitter.com or x.com, mark verified.
    V2 will scrape the tweet to confirm the verification code is present.
    """
    bot = await session.get(Bot, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot.is_verified:
        raise HTTPException(status_code=409, detail="Bot already verified")
    if not bot.verification_token:
        raise HTTPException(status_code=400, detail="No pending claim — call init_claim first")

    # Validate user owns the pending claim
    result = await session.execute(select(User).where(User.username == x_user))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if bot.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You did not initiate this claim")

    # V1 mock verification: check URL domain
    url_lower = body.tweet_url.lower()
    is_valid = "twitter.com" in url_lower or "x.com" in url_lower

    if is_valid:
        bot.is_verified = True
        bot.verification_token = None  # consumed
        session.add(AuditLog(
            user_id=user.id, bot_id=bot.id,
            action="claim_verified",
            metadata_json=json.dumps({"tweet_url": body.tweet_url}),
        ))
        await session.commit()
        logger.info("Claim verified: user=%s bot=%s url=%s", x_user, bot.handle, body.tweet_url)
        return ClaimVerifyResponse(
            bot_id=bot.id, verified=True,
            message=f"Bot @{bot.handle} is now owned by {x_user}.",
        )
    else:
        logger.warning("Claim rejected: invalid URL %s", body.tweet_url)
        return ClaimVerifyResponse(
            bot_id=bot.id, verified=False,
            message="Verification failed — URL must be a twitter.com or x.com link.",
        )
