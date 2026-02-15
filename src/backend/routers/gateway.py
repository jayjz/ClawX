import asyncio
import uuid
import time
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, Bot, Prediction, AuditLog
from models import MarketObservation, AgentAction, ActionResponse
from redis_pool import get_redis
from services.ledger_service import append_ledger_entry

router = APIRouter()
logger = logging.getLogger("gateway")

OBSERVATION_TTL = 5 # Physics: 5s window
SYSTEM_HALT_THRESHOLD = 15 # Physics: If Oracle is silent >15s, Universe is broken

async def verify_agent_secret(
    x_agent_secret: str = Header(..., alias="X-Agent-Secret"),
    session: AsyncSession = Depends(get_session)
) -> Bot:
    stmt = select(Bot).where(Bot.api_secret == x_agent_secret)
    result = await session.execute(stmt)
    bot = result.scalar_one_or_none()
    
    if not bot:
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
    # --- CIRCUIT BREAKER (System Death) ---
    # We don't just check if the key exists. We check if it's FRESH.
    # The Oracle sets a 120s TTL. If the key is missing, Oracle is dead.
    price_str = await redis.get("market:price:btc")
    
    if not price_str:
        logger.critical("🚨 SYSTEM HALT: Oracle is silent. Rejecting observations.")
        raise HTTPException(status_code=503, detail="Arena Halted: Market Data Stale")
    
    price = float(price_str)
    now_ts = time.time()
    
    obs_id = str(uuid.uuid4())
    ticket = {"bot_id": bot.id, "price": price, "ts": now_ts}
    
    await redis.setex(f"ticket:{obs_id}", OBSERVATION_TTL, json.dumps(ticket))
    
    return MarketObservation(
        observation_id=obs_id,
        server_time=now_ts,
        valid_until=now_ts + OBSERVATION_TTL,
        price_snapshot=price,
        open_positions=0 
    )

@router.post("/arena/action")
async def post_arena_action(
    action: AgentAction,
    bot: Bot = Depends(verify_agent_secret),
    session: AsyncSession = Depends(get_session),
    redis = Depends(get_redis)
):
    # 1. Atomicity Check
    ticket_key = f"ticket:{action.observation_id}"
    raw_ticket = await redis.execute_command("GETDEL", ticket_key)
    
    if not raw_ticket:
        raise HTTPException(status_code=409, detail="Temporal Conflict: Expired or Replayed")
    
    ticket = json.loads(raw_ticket)
    if ticket["bot_id"] != bot.id:
        raise HTTPException(status_code=403, detail="Ticket belongs to another agent")
        
    # 2. Execution
    if action.action_type == "PREDICT":
        if not action.direction or not action.wager_amount:
             raise HTTPException(status_code=400, detail="Missing direction/wager")
             
        if bot.balance < action.wager_amount:
            raise HTTPException(status_code=402, detail="Insufficient Funds")
            
        # --- ATOMIC LEDGER TRANSACTION ---
        bot.balance -= action.wager_amount
        
        # LINK CAUSALITY: We record the observation_id in the ledger
        await append_ledger_entry(
            bot_id=bot.id,
            amount=-action.wager_amount,
            transaction_type="WAGER",
            reference_id=f"OBS:{action.observation_id}", # <--- THE FIX
            session=session
        )
        
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
    
    bot.last_action_at = datetime.now(timezone.utc)
    await session.commit()
    
    return {
        "status": "ACCEPTED", 
        "new_balance": bot.balance,
        "action_id": str(uuid.uuid4())
    }
