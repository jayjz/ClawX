import uuid
import time
import json
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, Bot, Prediction, AuditLog
from models import MarketObservation, AgentAction, ActionResponse
from redis_pool import get_redis

router = APIRouter()
logger = logging.getLogger("gateway")

OBSERVATION_TTL = 5 # Strict 5s window

async def verify_agent_secret(
    x_agent_secret: str = Header(..., alias="X-Agent-Secret"),
    session: AsyncSession = Depends(get_session)
) -> Bot:
    """
    Middleware: Authenticate External Agent.
    Enforces the 'DEAD' status lockout (Invariant 4).
    """
    stmt = select(Bot).where(Bot.api_secret == x_agent_secret)
    result = await session.execute(stmt)
    bot = result.scalar_one_or_none()
    
    if not bot:
        # Anti-timing attack delay
        await asyncio.sleep(0.1)
        raise HTTPException(status_code=401, detail="Invalid Agent Secret")
    
    if bot.status == "DEAD":
        raise HTTPException(status_code=403, detail="Agent is DEAD. Liquidation in effect.")
        
    return bot

@router.get("/arena/observation", response_model=MarketObservation)
async def get_arena_observation(
    bot: Bot = Depends(verify_agent_secret),
    redis = Depends(get_redis)
):
    """
    Invariant 2: Observations are snapshots.
    Returns a ticket (observation_id) valid for exactly 5 seconds.
    """
    # 1. Read Truth (from Redis, 0ms latency)
    price_str = await redis.get("market:price:btc")
    if not price_str:
        raise HTTPException(status_code=503, detail="Arena Oracle Offline (No Price Feed)")
    
    price = float(price_str)
    now_ts = time.time()
    
    # 2. Issue Ticket
    obs_id = str(uuid.uuid4())
    ticket = {
        "bot_id": bot.id,
        "price": price,
        "ts": now_ts
    }
    
    # 3. Store Ticket (Atomic Expiry)
    # The key will self-destruct in 5 seconds.
    await redis.setex(f"ticket:{obs_id}", OBSERVATION_TTL, json.dumps(ticket))
    
    # Invariant 7 Stub: Memory would be injected here in future versions
    return MarketObservation(
        observation_id=obs_id,
        server_time=now_ts,
        valid_until=now_ts + OBSERVATION_TTL,
        price_snapshot=price,
        open_positions=0 # Optimization: Fetch from Redis counter later
    )

@router.post("/arena/action")
async def post_arena_action(
    action: AgentAction,
    bot: Bot = Depends(verify_agent_secret),
    session: AsyncSession = Depends(get_session),
    redis = Depends(get_redis)
):
    """
    Invariant 3: Strict One-Time Causal Binding.
    Uses 'GETDEL' to ensure an observation cannot be reused or replayed.
    """
    ticket_key = f"ticket:{action.observation_id}"
    
    # --- ATOMICITY CHECK ---
    # GETDEL is atomic. If two requests hit this line at the same nanosecond,
    # only ONE gets the payload. The other gets None.
    raw_ticket = await redis.execute_command("GETDEL", ticket_key)
    
    if not raw_ticket:
        raise HTTPException(
            status_code=409, 
            detail="Temporal Conflict: Observation expired or already used."
        )
    
    ticket = json.loads(raw_ticket)
    
    # Security: Verify ownership
    if ticket["bot_id"] != bot.id:
        raise HTTPException(status_code=403, detail="Observation belongs to another agent")
        
    # --- EXECUTION ---
    if action.action_type == "PREDICT":
        if not action.direction or not action.wager_amount:
             raise HTTPException(status_code=400, detail="Missing direction/wager")
             
        if bot.balance < action.wager_amount:
            raise HTTPException(status_code=402, detail="Insufficient Funds")
            
        bot.balance -= action.wager_amount
        
        pred = Prediction(
            bot_id=bot.id,
            claim_text=f"Arena Action: {action.direction}",
            direction=action.direction,
            confidence=1.0,
            wager_amount=action.wager_amount,
            start_price=ticket["price"],
            status="OPEN",
            reasoning=action.reasoning
        )
        session.add(pred)
        session.add(AuditLog(bot_id=bot.id, action="ARENA_PREDICT"))
        
    elif action.action_type == "WAIT":
        session.add(AuditLog(bot_id=bot.id, action="ARENA_WAIT"))
    
    # Heartbeat update (for Entropy Tax later)
    bot.last_action_at = datetime.now(timezone.utc)
    await session.commit()
    
    return {
        "status": "ACCEPTED", 
        "new_balance": bot.balance,
        "action_id": str(uuid.uuid4())
    }
