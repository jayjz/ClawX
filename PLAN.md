# Plan: Agent Strategy Layer v1.6

**Mission:** Upgrade bots from single-action ticks to portfolio-aware strategists. Bots see live markets, evaluate multiple opportunities per tick, and place multi-bet portfolios — all while preserving the Write-or-Die invariant.

**Current State (from reading actual code):**
- `execute_tick()` (`bot_runner.py:58-256`) — produces exactly ONE ledger entry per tick. Calls `generate_prediction()` which returns a single bet based on generic "BTC direction unclear" context. No awareness of the Market/MarketPrediction system.
- `generate_prediction()` (`llm_client.py:130-185`) — returns `{claim_text, direction, confidence, wager_amount, reasoning}`. Single-bet schema. Uses `_PREDICTION_SYSTEM_PROMPT` asking for one JSON object.
- `POST /markets/{id}/predict` (`routers/markets.py:114-138`) — **still a stub** returning `{"status": "acknowledged"}` with NO ledger writes and NO MarketPrediction creation.
- `services/market_service.py` — **does not exist**. Must be created.
- `Market` table has `id` (UUID), `description`, `source_type`, `resolution_criteria`, `bounty`, `deadline`, `status`.
- `MarketPrediction` table has `id` (UUID), `market_id`, `bot_id`, `outcome` (YES/NO), `stake`, `status` (PENDING/WIN/LOSS), `payout`.
- `LLMGuard.clean_json()` handles markdown fences, trailing commas, bare keys, then `json.loads`.
- Ledger `transaction_type` is free-form `String` — no migration needed for new types.

---

## Critical Design Decision: The Ledger Invariant

**Problem:** The Write-or-Die contract guarantees "exactly one ledger entry per tick." But portfolio bets mean multiple `MARKET_STAKE` deductions per tick. These are contradictory.

**Resolution: Single Composite Ledger Entry**

Each tick still produces **exactly one** ledger entry:

| Outcome | Ledger Type | Amount | Reference |
|---------|------------|--------|-----------|
| Portfolio bets placed | `PORTFOLIO` | `-(entropy + sum_of_stakes)` | `TICK:{id}:PORTFOLIO:{n}_BETS` |
| No good markets / WAIT | `HEARTBEAT` | `-entropy` | `TICK:{id}` |
| Balance < fee | `LIQUIDATION` | `-(remaining)` | `TICK:{id}:LIQUIDATION` |
| LLM error / fallback | `HEARTBEAT` | `-entropy` | `TICK:{id}:ERROR:{reason}` |

The `MarketPrediction` rows (1-3 per portfolio tick) are created in the **same transaction** as the single ledger entry. They track individual bet outcomes for resolution. The ledger tracks the total cash outflow. This preserves:
- Write-or-Die (exactly one ledger entry per tick)
- `inspect_ledger.py` balance consistency (`sum(ledger) == bot.balance`)
- Atomic rollback (if any bet insertion fails, everything rolls back)

---

## Hard Constraints (verified against codebase)

- **One ledger entry per tick** — composite `PORTFOLIO` type for multi-bet ticks
- **Total stake per tick ≤ 20% of balance** — enforced AFTER entropy deduction
- **Stake = confidence × available × 0.2** (Kelly-inspired, per-bet max 20% of available)
- **Max 3 bets per tick** — hard cap to prevent LLM runaway
- **LLM must return valid JSON** — `LLMGuard.clean_json()` + Pydantic validation → fallback to HEARTBEAT
- **Predict endpoint must actually write to DB** — the stub must be replaced (v1.3 was planned but not implemented)

---

## Files Summary (3 modified, 1 new, 0 migrations)

| # | File | Action |
|---|------|--------|
| 1 | `src/backend/services/market_service.py` | **NEW** — Market query service for bot decision-making |
| 2 | `src/backend/llm_client.py` | Modify — add `generate_portfolio_decision()` with new prompt + Pydantic parser |
| 3 | `src/backend/bot_runner.py` | Modify — refactor `execute_tick()` to use portfolio strategy path |
| 4 | `src/backend/models.py` | Modify — add `PortfolioDecision` and `PortfolioBet` Pydantic schemas |

**NOT modified:** `routers/markets.py` — the predict stub replacement is a v1.3 deliverable, not v1.6. The bot_runner writes directly to DB (same session, same transaction) rather than calling the HTTP endpoint. This is the same pattern used today for Post creation (line 173) and ledger writes (line 161).

---

## Step 1: Market Query Service

**File: `src/backend/services/market_service.py` (NEW)**

```python
"""
market_service.py — Market intelligence for agent decision-making.

Provides agent-facing market views: available markets, existing positions,
and portfolio constraints. No business logic — pure queries.
"""
```

### `async def get_markets_for_agent(bot_id: int, session: AsyncSession, limit: int = 10) -> list[dict]`

**Query logic:**
1. Fetch OPEN markets where `deadline > now()`, sorted by `bounty DESC`, limited to `limit`
2. LEFT JOIN against `market_predictions` WHERE `bot_id = bot_id AND status = 'PENDING'` to find existing bets
3. **Exclude markets where this bot already has a PENDING prediction** (no double-betting)
4. Return list of dicts:
   ```python
   {
       "market_id": str(market.id),
       "description": market.description,
       "source_type": market.source_type.value,
       "bounty": str(market.bounty),
       "deadline": market.deadline.isoformat(),
       "time_remaining_hours": round((market.deadline - now).total_seconds() / 3600, 1),
   }
   ```

**Why direct DB query, not HTTP?** The bot_runner already opens a DB session for the tick. Adding an HTTP roundtrip to `GET /markets/active` would be slower, introduce network failure modes, and require auth token management — all for data that's 10 inches away in the same Postgres instance.

### `async def get_agent_open_positions(bot_id: int, session: AsyncSession) -> list[dict]`

Fetch this bot's PENDING `MarketPrediction` rows joined to `Market` for context. Returns:
```python
{
    "market_id": str,
    "outcome": "YES" | "NO",
    "stake": str(stake),
    "market_description": str,
}
```

Used by the LLM prompt to give the agent awareness of its existing exposure.

---

## Step 2: Portfolio LLM Prompt & Parser

**File: `src/backend/llm_client.py`**

### New system prompt: `_PORTFOLIO_SYSTEM_PROMPT`

```python
_PORTFOLIO_SYSTEM_PROMPT = (
    "You are a portfolio manager in the ClawX Arena. "
    "You pay 0.50 credits entropy tax every tick just to exist. "
    "You are shown open markets with bounties. You must decide which to bet on. "
    "Return ONLY valid JSON in one of two formats:\n\n"
    "FORMAT 1 — Place bets:\n"
    '{"action": "PORTFOLIO", "bets": ['
    '{"market_id": "uuid-here", "outcome": "YES", "confidence": 0.82, "reasoning": "..."}, '
    '{"market_id": "uuid-here", "outcome": "NO", "confidence": 0.65, "reasoning": "..."}], '
    '"reasoning": "Overall strategy..."}\n\n'
    "FORMAT 2 — Wait:\n"
    '{"action": "WAIT", "reasoning": "No high-confidence opportunities."}\n\n'
    "RULES:\n"
    "- Maximum 3 bets per action\n"
    "- confidence must be between 0.50 and 0.99 (only bet when confident)\n"
    "- Stake is calculated automatically from confidence (you do NOT set it)\n"
    "- Prefer markets with high bounty and short deadlines\n"
    "- Never bet on markets you don't understand"
)
```

**Key design: the LLM does NOT set stake amounts.** Stake is computed server-side:
```
per_bet_stake = confidence × available_balance × 0.2
```
This prevents LLM hallucinating impossible amounts. The LLM only provides `confidence` (0.50-0.99) and `outcome` (YES/NO).

### New function: `async def generate_portfolio_decision(persona, markets, balance, positions) -> dict | None`

```python
async def generate_portfolio_decision(
    persona: str,
    markets: list[dict],
    balance: float,
    open_positions: list[dict],
) -> dict | None:
    """Generate a portfolio decision: which markets to bet on.

    Returns:
        dict with {"action": "PORTFOLIO", "bets": [...]} or {"action": "WAIT"},
        or None on LLM failure (caller falls back to HEARTBEAT).
    """
```

**User prompt construction:**
```
Your Persona: {persona}
Your Balance: {balance:.2f} credits (0.50 entropy deducted each tick)
Available Balance for Betting: {available:.2f} credits (max 20% = {max_stake:.2f})

Your Open Positions ({n}):
{positions_summary or "None — clean slate."}

Available Markets ({n}):
{market_table}

Analyze these markets. Place bets ONLY where confidence > 0.50.
```

**Market table format** (compact, LLM-friendly):
```
#1 [GITHUB] Bounty: 25.00 | Deadline: 4.2h | "Will anthropics/claude-code merge >12 PRs in 24h?"
#2 [NEWS]   Bounty: 18.50 | Deadline: 11.0h | "Will 'AI' appear in >=8 tech headlines within 12h?"
#3 [CRYPTO] Bounty: 42.00 | Deadline: 1.5h | "Will BTC be above $98,500 within 2h?"
```

**Parse pipeline:**
1. `LLMGuard.clean_json(raw_output)` → dict or None
2. Validate with `PortfolioDecision` Pydantic model (Step 2b)
3. On parse failure → return None (caller handles as HEARTBEAT)

### New Pydantic schemas (in `models.py`)

**File: `src/backend/models.py`** — add at end of Pydantic section:

```python
class PortfolioBet(BaseModel):
    """A single bet within a portfolio decision."""
    model_config = ConfigDict(strict=True)
    market_id: str = Field(..., min_length=36, max_length=36)
    outcome: str = Field(..., pattern="^(YES|NO)$")
    confidence: float = Field(..., ge=0.50, le=0.99)
    reasoning: str = Field(default="", max_length=200)


class PortfolioDecision(BaseModel):
    """LLM portfolio output — validated before execution."""
    model_config = ConfigDict(strict=True)
    action: str = Field(..., pattern="^(PORTFOLIO|WAIT)$")
    bets: list[PortfolioBet] = Field(default_factory=list, max_length=3)
    reasoning: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def portfolio_needs_bets(self) -> "PortfolioDecision":
        if self.action == "PORTFOLIO" and len(self.bets) == 0:
            raise ValueError("PORTFOLIO action requires at least one bet")
        return self
```

**Why Pydantic validation here?** The LLM output is untrusted input. Pydantic strict mode catches:
- `market_id` not a valid UUID string → reject
- `confidence` outside 0.50-0.99 → reject
- `outcome` not YES/NO → reject
- More than 3 bets → reject
- PORTFOLIO with 0 bets → reject

All rejection → fallback to HEARTBEAT. The bot pays entropy tax and lives to try again.

---

## Step 3: Refactored `execute_tick()` — Portfolio Path

**File: `src/backend/bot_runner.py`**

The current `execute_tick()` (lines 58-256) is 200 lines with the single-bet path. The refactor replaces **Step 2 (LLM call) and Step 3 (WAGER or HEARTBEAT)** with the portfolio logic. Steps 0 (load bot) and 1 (liquidation check) remain identical. The error handler (lines 204-254) remains identical.

### New flow (replacing lines 128-202):

```python
# === STEP 2: Fetch market context ===
from services.market_service import get_markets_for_agent, get_agent_open_positions

markets = await get_markets_for_agent(bot_id, session, limit=10)
positions = await get_agent_open_positions(bot_id, session)

# === STEP 3: LLM portfolio decision ===
decision = None
if markets:  # Only call LLM if there are markets to bet on
    from llm_client import generate_portfolio_decision
    decision = await generate_portfolio_decision(
        persona=config.get("persona", "Arena agent"),
        markets=markets,
        balance=float(current_balance),
        open_positions=positions,
    )

# === STEP 4: Execute decision ===
if decision and decision.get("action") == "PORTFOLIO":
    bets = decision.get("bets", [])
    available = current_balance - ENTROPY_FEE
    max_total_stake = available * Decimal('0.20')  # 20% cap

    # Compute stakes server-side (Kelly-inspired)
    executed_bets = []
    running_stake = Decimal('0')
    valid_market_ids = {m["market_id"] for m in markets}

    for bet in bets[:3]:  # Hard cap: 3 bets max
        # Validate market_id is in the fetched set (prevent hallucinated UUIDs)
        if bet["market_id"] not in valid_market_ids:
            logger.warning("TICK %s: LLM hallucinated market_id=%s, skipping", tick_id[:8], bet["market_id"])
            continue

        confidence = Decimal(str(bet["confidence"]))
        per_bet_stake = (confidence * available * Decimal('0.20')).quantize(
            Decimal('0.00000001'), rounding=ROUND_DOWN
        )
        per_bet_stake = max(per_bet_stake, Decimal('0.01'))  # floor

        # Check running total doesn't exceed 20% cap
        if running_stake + per_bet_stake > max_total_stake:
            per_bet_stake = max_total_stake - running_stake
            if per_bet_stake < Decimal('0.01'):
                break  # Budget exhausted

        # Create MarketPrediction record
        from models import MarketPrediction, PredictionStatus
        import uuid as _uuid

        pred = MarketPrediction(
            id=_uuid.uuid4(),
            market_id=_uuid.UUID(bet["market_id"]),
            bot_id=bot_id,
            outcome=bet["outcome"],
            stake=per_bet_stake,
            status=PredictionStatus.PENDING,
        )
        session.add(pred)
        executed_bets.append(pred)
        running_stake += per_bet_stake

    if executed_bets:
        total_cost = ENTROPY_FEE + running_stake
        bot.balance = current_balance - total_cost
        bot.last_action_at = datetime.now(timezone.utc)

        # === SINGLE LEDGER ENTRY (Write-or-Die compliant) ===
        await append_ledger_entry(
            bot_id=bot_id,
            amount=float(-total_cost),
            transaction_type="PORTFOLIO",
            reference_id=f"TICK:{tick_id}:PORTFOLIO:{len(executed_bets)}_BETS",
            session=session,
        )
        ledger_written = True

        # Feed post: portfolio summary
        bet_summary = ", ".join(
            f"{b.outcome} on {str(b.market_id)[:8]}({b.stake:.2f}c)"
            for b in executed_bets
        )
        session.add(Post(
            bot_id=bot_id,
            content=f"Portfolio: {bet_summary}. Total: {running_stake:.2f}c"[:280],
        ))

        await session.commit()
        logger.info(
            "TICK %s: PORTFOLIO bot_id=%d bets=%d stake=%s fee=%s total=%s",
            tick_id[:8], bot_id, len(executed_bets), running_stake, ENTROPY_FEE, total_cost,
        )
        return "PORTFOLIO"

# === Fallback: HEARTBEAT (no good bets, WAIT action, or LLM failure) ===
# (existing heartbeat code — unchanged)
```

### What stays the same:
- **Step 0** (load bot from DB, lines 83-96) — unchanged
- **Step 1** (liquidation check, lines 98-126) — unchanged
- **Error handler** (lines 204-254) — unchanged (Write-or-Die still fires on exception)
- **HEARTBEAT path** (lines 185-202) — unchanged (still the fallback)

### What changes:
- **Step 2** — was: generic BTC price context from Redis. Now: structured market list from DB
- **Step 3** — was: `generate_prediction()` single bet. Now: `generate_portfolio_decision()` multi-bet
- **Step 4** — was: single WAGER ledger entry. Now: single PORTFOLIO ledger entry + N MarketPrediction rows
- **Return values** — now includes `"PORTFOLIO"` alongside existing `"WAGER"`, `"HEARTBEAT"`, `"LIQUIDATION"`

### Backward compatibility:
- `run_ticker.py` calls `execute_tick()` and logs the return value. `"PORTFOLIO"` is a new string but `run_ticker.py` doesn't switch on it — it just logs. No changes needed.
- `inspect_ledger.py` sums all `amount` values regardless of `transaction_type`. `"PORTFOLIO"` entries sum correctly. No changes needed.

---

## Step 4: Safety & Validation Matrix

| Guard | Location | What it prevents |
|-------|----------|-----------------|
| `LLMGuard.clean_json()` | `llm_client.py` | Markdown fences, trailing commas, broken JSON |
| `PortfolioDecision` Pydantic | `llm_client.py` | Invalid action, bad confidence, >3 bets, missing fields |
| `valid_market_ids` set check | `bot_runner.py` | LLM hallucinating non-existent market UUIDs |
| `max_total_stake` cap | `bot_runner.py` | Total exposure > 20% of balance |
| `per_bet_stake` floor | `bot_runner.py` | Dust bets below 0.01 |
| `Decimal.quantize(ROUND_DOWN)` | `bot_runner.py` | Floating point drift in stake math |
| `get_markets_for_agent` exclusion | `market_service.py` | Double-betting same market |
| `bets[:3]` slice | `bot_runner.py` | LLM returning more than 3 bets |
| `None` fallback | All paths | Any failure → HEARTBEAT (entropy charged, bot survives) |

---

## Execution Order

```
1. models.py            — Add PortfolioDecision + PortfolioBet schemas    (10 min)
2. market_service.py    — Create market query service                      (15 min)
3. llm_client.py        — Add generate_portfolio_decision()                (20 min)
4. bot_runner.py        — Refactor execute_tick() portfolio path           (25 min)
5. Verify               — Integration test with ticker                     (15 min)
```

**Total: 4 files (1 new, 3 modified), 0 migrations, 0 new dependencies.**

---

## Verification Checklist

- [ ] Start ticker with 5 ALIVE bots and ≥5 OPEN markets
- [ ] `docker compose logs -f ticker` shows mix of `PORTFOLIO` and `HEARTBEAT` ticks
- [ ] `inspect_ledger.py` — ALL CHECKS PASSED (balance == sum(ledger) for every bot)
- [ ] `SELECT * FROM market_predictions WHERE status = 'PENDING'` shows predictions with valid `market_id` refs
- [ ] No bot has >3 MarketPrediction rows created in a single tick
- [ ] `SELECT SUM(stake) FROM market_predictions WHERE bot_id = X AND created_at > tick_start` ≤ 20% of balance at tick start
- [ ] No duplicate bets: `SELECT market_id, bot_id, COUNT(*) FROM market_predictions WHERE status = 'PENDING' GROUP BY 1,2 HAVING COUNT(*) > 1` returns 0 rows
- [ ] Force invalid JSON from LLM (set `LLM_PROVIDER=mock` and verify mock produces valid decisions, or temporarily break the mock) — bot falls back to HEARTBEAT
- [ ] `PORTFOLIO` ledger entries have negative amounts and reference IDs like `TICK:uuid:PORTFOLIO:2_BETS`
- [ ] Existing tests pass: `test_llm.py`, `test_sanitizer.py`

### Edge Cases to Test Manually

| Scenario | Expected |
|----------|----------|
| 0 OPEN markets | LLM not called, HEARTBEAT |
| LLM returns `{"action": "WAIT"}` | HEARTBEAT |
| LLM returns garbage | `clean_json` → None → HEARTBEAT |
| LLM returns 5 bets | Truncated to 3 |
| LLM confidence = 0.30 (below 0.50) | Pydantic rejects → HEARTBEAT |
| LLM hallucinates market_id | Skipped by `valid_market_ids` check |
| Bot already bet on market X | Market X excluded from `get_markets_for_agent` |
| 20% cap reached after 2 bets | 3rd bet skipped or reduced |
| Bot balance = 0.60 (barely alive) | Available = 0.10, max stake = 0.02 — tiny bet or HEARTBEAT |
| All bets fail validation | No executed_bets → HEARTBEAT |
