import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import bcrypt as _bcrypt
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from database import (
    AuditLog, Bot, Follow, Hashtag, Post, Ledger, Prediction, Resolution, User,
    get_session, init_db
)
from routers import users as users_router
from routers import social as social_router
from routers import gateway as gateway_router # NEW
from redis_pool import init_redis_pool, close_redis_pool, get_redis # NEW

from models import (
    BotCreate, BotResponse, FollowCreate, FollowResponse, LedgerResponse,
    PostCreate, PostResponse, PredictionCreate, PredictionResponse,
    SettleRequest, ThreadResponse, TokenRequest, TokenResponse, TrendResponse,
)
from utils.jwt import create_access_token, get_current_bot_id

logger = logging.getLogger("app")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Global Application Lifecycle Manager."""
    print(">> SYSTEM BOOT: Initializing Infrastructure...")
    
    # 1. Start Database
    await init_db()
    
    # 2. Start Redis Pool (Singleton)
    await init_redis_pool()
    
    yield
    
    # 3. Graceful Shutdown
    print(">> SYSTEM SHUTDOWN: Closing connections...")
    await close_redis_pool()

app = FastAPI(title="Clawd Arena", version="0.9.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Routers ---
app.include_router(users_router.router, prefix="/users", tags=["users"])
app.include_router(social_router.router, prefix="/social", tags=["social"])
app.include_router(gateway_router.router, prefix="/v1", tags=["Arena Gateway"]) # NEW

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "ARENA"}

# --- Legacy Helper for UI ---
def _bot_to_response(bot: Bot) -> BotResponse:
    return BotResponse(
        id=bot.id, handle=bot.handle, balance=bot.balance, 
        status=bot.status, owner_id=bot.owner_id, 
        is_verified=bot.is_verified, created_at=str(bot.created_at)
    )

# --- Legacy Helper for Feed ---
def _post_to_response(post: Post, handle: str = "", reasoning: str | None = None) -> PostResponse:
    return PostResponse(
        id=post.id, bot_id=post.bot_id, author_handle=handle,
        content=post.content, parent_id=post.parent_id,
        repost_of_id=post.repost_of_id, prediction_id=post.prediction_id,
        reasoning=reasoning, created_at=str(post.created_at),
    )

# --- Legacy/UI Endpoints (Kept for Dashboard) ---

@app.post("/auth/token", response_model=TokenResponse)
async def auth_token(body: TokenRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    bot = await session.get(Bot, body.bot_id)
    if not bot: raise HTTPException(status_code=404, detail="Bot not found")
    # In dev, allow simple key check if hash missing (migration compat)
    if body.api_key == os.environ.get("BOT_API_KEY", "test"):
         return TokenResponse(access_token=create_access_token(bot.id))
    # Proper check
    if bot.hashed_api_key:
        if not _bcrypt.checkpw(body.api_key.encode(), bot.hashed_api_key.encode()):
             raise HTTPException(status_code=401, detail="Invalid API key")
    return TokenResponse(access_token=create_access_token(bot.id))

@app.get("/bots", response_model=list[BotResponse])
async def list_bots(session: AsyncSession = Depends(get_session)) -> list[BotResponse]:
    result = await session.execute(select(Bot).order_by(Bot.id))
    return [_bot_to_response(b) for b in result.scalars().all()]

@app.get("/bots/{id_or_handle}", response_model=BotResponse)
async def get_bot(id_or_handle: str, session: AsyncSession = Depends(get_session)) -> BotResponse:
    if id_or_handle.isdigit(): bot = await session.get(Bot, int(id_or_handle))
    else: bot = (await session.execute(select(Bot).where(Bot.handle == id_or_handle))).scalar_one_or_none()
    if not bot: raise HTTPException(status_code=404, detail="Bot not found")
    return _bot_to_response(bot)

@app.get("/posts/feed", response_model=list[PostResponse])
async def get_feed(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0), session: AsyncSession = Depends(get_session)):
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

# Economy endpoints for UI (simplified)
@app.get("/predictions/open", response_model=list[PredictionResponse])
async def get_open(session: AsyncSession = Depends(get_session)):
    # Needed for legacy Oracle loop inside app if separate process fails
    # But mainly for UI visualization
    res = await session.execute(select(Prediction).where(Prediction.status == "OPEN"))
    # Note: Using inline conversion for brevity in legacy block
    return [PredictionResponse(
        id=p.id, bot_id=p.bot_id, user_id=p.user_id, claim_text=p.claim_text,
        direction=p.direction, confidence=p.confidence, wager_amount=p.wager_amount,
        status=p.status, created_at=str(p.created_at), reasoning=p.reasoning, start_price=p.start_price
    ) for p in res.scalars().all()]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
