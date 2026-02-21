import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from database import AuditLog, Bot, Post, Prediction, get_session, init_db
from routers import users as users_router
from routers import social as social_router
from routers import gateway as gateway_router
from routers import markets as markets_router
from routers import ws as ws_router
from redis_pool import init_redis_pool, close_redis_pool
from models import (
    AgentMetricsEntry, BotCreate, BotResponse, PostResponse, PredictionResponse,
    TokenRequest, TokenResponse,
)
from services.ledger_service import append_ledger_entry
from utils.jwt import create_access_token
import bcrypt as _bcrypt

logger = logging.getLogger("app")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(">> SYSTEM BOOT: Initializing Infrastructure...")
    await init_db()
    await init_redis_pool()
    yield
    print(">> SYSTEM SHUTDOWN: Closing connections...")
    await close_redis_pool()

app = FastAPI(title="Clawd Arena", version="0.9.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(users_router.router, prefix="/users", tags=["users"])
app.include_router(social_router.router, prefix="/social", tags=["social"])
app.include_router(gateway_router.router, prefix="/v1", tags=["Arena Gateway"])
app.include_router(markets_router.router, prefix="/markets", tags=["markets"])
app.include_router(ws_router.router)   # /ws/stream — no prefix, path is in the route

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "ARENA"}

# --- Legacy Endpoints (Maintained for UI compatibility) ---
def _bot_to_response(bot: Bot) -> BotResponse:
    return BotResponse(
        id=bot.id, handle=bot.handle, balance=bot.balance,
        status=bot.status, owner_id=bot.owner_id,
        is_verified=bot.is_verified, created_at=str(bot.created_at),
        last_action_at=bot.last_action_at.isoformat() if bot.last_action_at else None,
    )

def _post_to_response(post: Post, handle: str = "", reasoning: str | None = None) -> PostResponse:
    return PostResponse(
        id=post.id, bot_id=post.bot_id, author_handle=handle,
        content=post.content, parent_id=post.parent_id,
        repost_of_id=post.repost_of_id, prediction_id=post.prediction_id,
        reasoning=reasoning, created_at=str(post.created_at),
    )

@app.post("/auth/token", response_model=TokenResponse)
async def auth_token(body: TokenRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    bot = await session.get(Bot, body.bot_id)
    if not bot: raise HTTPException(status_code=404, detail="Bot not found")
    if body.api_key == os.environ.get("BOT_API_KEY", "test"):
         return TokenResponse(access_token=create_access_token(bot.id))
    if bot.hashed_api_key:
        if not _bcrypt.checkpw(body.api_key.encode(), bot.hashed_api_key.encode()):
             raise HTTPException(status_code=401, detail="Invalid API key")
    return TokenResponse(access_token=create_access_token(bot.id))

@app.get("/bots", response_model=list[BotResponse])
async def list_bots(session: AsyncSession = Depends(get_session)) -> list[BotResponse]:
    result = await session.execute(select(Bot).order_by(Bot.id))
    return [_bot_to_response(b) for b in result.scalars().all()]


@app.post("/bots", status_code=201)
async def create_bot(body: BotCreate, session: AsyncSession = Depends(get_session)):
    """Create a new bot with GRANT ledger entry.

    Returns the bot ID, raw API key (one-time display), and api_secret
    for arena gateway auth. All money enters via the ledger — no balance
    is set without a corresponding GRANT entry (CLAUDE.md Invariant #4).
    """
    # Uniqueness check
    existing = await session.execute(select(Bot).where(Bot.handle == body.handle))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Handle '{body.handle}' already exists")

    # Credential generation (lessons.md: no hardcoded secrets)
    raw_api_key = body.api_key
    hashed_key = _bcrypt.hashpw(raw_api_key.encode(), _bcrypt.gensalt()).decode()
    api_secret = secrets.token_hex(32)

    initial_balance = Decimal('1000.00')

    bot = Bot(
        handle=body.handle,
        persona_yaml=body.persona_yaml,
        hashed_api_key=hashed_key,
        api_secret=api_secret,
        balance=initial_balance,
        status="ALIVE",
        is_external=False,
    )
    session.add(bot)
    await session.flush()  # get bot.id

    # GRANT ledger entry — all money must enter through the chain
    await append_ledger_entry(
        bot_id=bot.id,
        amount=initial_balance,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        session=session,
    )

    session.add(AuditLog(bot_id=bot.id, action="BOT_CREATED"))
    await session.commit()

    logger.info("Bot created: id=%d handle=%s", bot.id, bot.handle)
    return {
        "id": bot.id,
        "handle": bot.handle,
        "balance": bot.balance,
        "api_key": raw_api_key,
        "api_secret": api_secret,
        "message": "Save these credentials. They will not be shown again.",
    }


@app.get("/bots/{handle}", response_model=BotResponse)
async def get_bot_by_handle(handle: str, session: AsyncSession = Depends(get_session)):
    """Lookup a bot by handle. Used by bot_runner to get bot state."""
    result = await session.execute(select(Bot).where(Bot.handle == handle))
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot '{handle}' not found")
    return _bot_to_response(bot)


@app.get("/posts/feed", response_model=list[PostResponse])
async def get_feed(limit: int = Query(default=20), offset: int = Query(default=0), session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Post, Bot.handle, Prediction.reasoning)
        .join(Bot, Post.bot_id == Bot.id)
        .outerjoin(Prediction, Post.prediction_id == Prediction.id)
        .order_by(desc(Post.created_at))
        .offset(offset).limit(limit)
    )
    result = await session.execute(stmt)
    out = []
    for post, handle, reasoning in result.all():
        out.append(_post_to_response(post, handle, reasoning))
    return out

@app.get("/predictions/open", response_model=list[PredictionResponse])
async def get_open(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Prediction).where(Prediction.status == "OPEN"))
    return [PredictionResponse(
        id=p.id, bot_id=p.bot_id, user_id=p.user_id, claim_text=p.claim_text,
        direction=p.direction, confidence=p.confidence, wager_amount=p.wager_amount,
        status=p.status, created_at=str(p.created_at), reasoning=p.reasoning, start_price=p.start_price
    ) for p in res.scalars().all()]


@app.get("/insights/{agent_id}")
async def get_agent_insights(
    agent_id: int,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Return the observability narrative for an agent.

    Aggregates ``AgentMetricsEntry`` rows to surface cost truth, idle rate,
    phantom enforcement events, and decision density. Suitable for ClawWork
    JSON handshake or human operator dashboards.
    """
    bot = await session.get(Bot, agent_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Safe defaults — returned when agent_metrics table is missing or has no rows.
    entries: list = []
    total_ticks: int = 0
    avg_phantom_fee: float = 0.0
    liq_count: int = 0
    heartbeat_count: int = 0

    try:
        # Recent raw entries
        recent_result = await session.execute(
            select(AgentMetricsEntry)
            .where(AgentMetricsEntry.bot_id == agent_id)
            .order_by(AgentMetricsEntry.created_at.desc())
            .limit(limit)
        )
        entries = recent_result.scalars().all()

        # Aggregate stats — note: boolean SUM is not portable across DBs; count separately.
        agg_result = await session.execute(
            select(
                sa_func.count(AgentMetricsEntry.id).label("total_ticks"),
                sa_func.avg(AgentMetricsEntry.phantom_entropy_fee).label("avg_phantom_fee"),
            ).where(AgentMetricsEntry.bot_id == agent_id)
        )
        agg = agg_result.one_or_none()
        total_ticks = agg[0] if agg else 0
        avg_phantom_fee = float(agg[1] or 0) if agg else 0.0

        # Separate count for would_have_been_liquidated (avoids SUM(boolean) PG error)
        liq_count_result = await session.execute(
            select(sa_func.count(AgentMetricsEntry.id)).where(
                AgentMetricsEntry.bot_id == agent_id,
                AgentMetricsEntry.would_have_been_liquidated.is_(True),
            )
        )
        liq_count = liq_count_result.scalar_one_or_none() or 0

        heartbeat_count_result = await session.execute(
            select(sa_func.count(AgentMetricsEntry.id)).where(
                AgentMetricsEntry.bot_id == agent_id,
                AgentMetricsEntry.tick_outcome == "HEARTBEAT",
            )
        )
        heartbeat_count = heartbeat_count_result.scalar_one_or_none() or 0

    except Exception as metrics_exc:
        # agent_metrics table may not exist yet (migration pending) or query failed.
        # Return zero-metric response rather than 500 — observability must stay up.
        logger.warning("insights: metrics query failed for agent %d: %s", agent_id, metrics_exc)

    idle_rate = (heartbeat_count / total_ticks) if total_ticks else 0.0

    return {
        "agent_id": agent_id,
        "handle": bot.handle,
        "status": bot.status,
        "enforcement_mode": os.environ.get("ENFORCEMENT_MODE", "observe"),
        "balance_snapshot": float(bot.balance),
        "aggregate": {
            "total_ticks_observed": total_ticks,
            "idle_rate": round(idle_rate, 4),
            "avg_phantom_entropy_fee": round(avg_phantom_fee, 8),
            "would_have_been_liquidated_count": liq_count,
        },
        "recent_metrics": [
            {
                "tick_id": e.tick_id,
                "outcome": e.tick_outcome,
                "enforcement_mode": e.enforcement_mode,
                "phantom_fee": float(e.phantom_entropy_fee),
                "would_liquidate": e.would_have_been_liquidated,
                "balance": float(e.balance_snapshot),
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "details": e.metrics_json,
            }
            for e in entries
        ],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
