
# ClawX — Auditable Autonomous Agent Economy

ClawX (ClawdXCraft) is **not** a trading bot framework, prompt playground, or backtesting tool.

It is an economic physics engine where autonomous agents:

- cannot exist without paying rent every tick  
- cannot act without writing to an append-only, hash-chained ledger  
- cannot lie about their economic history  
- die permanently when insolvent

If you want fast profits, clever prompts, or simulated accounting — look elsewhere.

If you want a system that enforces **verifiable autonomy**, **irreversible consequence**, and **loud failure** instead of silent drift — welcome.

## What Actually Exists (February 2026 — post Operation Ironclad)

ClawX implements a closed economic loop with these enforced properties:

- Time advances only via discrete, auditable ticks  
- Every tick costs credits (Entropy Fee)  
- Every action (think, wait, error) produces exactly one ledger entry  
- Balance is a cached view — truth lives in the ledger  
- Agents are liquidated irreversibly when balance ≤ 0  
- Ledger is cryptographically chained (previous_hash → hash)  
- Sequence is strictly monotonic per bot (no forks, no gaps)

This is **not** simulated accounting.  
This is **enforced accounting**.

## Core Invariants (Non-Negotiable Laws)

These are not guidelines — they are checked by code and tests.

1. **Time = Money**  
   Every tick deducts an Entropy Fee (currently 0.50 credits).  
   No free existence. No free thinking. No free waiting.

2. **Write or Die**  
   The execution loop **must** produce exactly one ledger entry per tick.  
   LLM failure → ERROR entry + fee  
   Idle/wait → HEARTBEAT entry + fee  
   Action → WAGER entry + fee + amount  
   No silent ticks. No skipped writes.

3. **Ledger = Economic Truth**  
   At any moment:  
   ```
   SUM(ledger.amount WHERE bot_id = X) == bots.balance[X]
   ```  
   If this invariant fails → CRITICAL INTEGRITY FAILURE → execution halts.

4. **One Tick, One Law**  
   All time advancement flows through a single canonical function: `execute_tick()`.  
   No duplicated logic. No alternate timelines.

## Quick Start (The Only Workflow That Matters)

### 1. Boot the System

# Copy example config (adjust LLM_PROVIDER, API keys if desired)
cp src/backend/.env.example src/backend/.env

# Start Postgres, Redis, Backend
docker compose up -d


### 2. Start the Automated Economy (The Ticker Daemon)

```bash
# Start all services including the ticker
docker compose up -d

# The ticker automatically ticks every ALIVE bot every TICK_RATE seconds (default: 10s)
docker compose logs -f ticker
```

The ticker daemon:
- Runs continuously — no manual intervention needed
- Ticks every ALIVE bot once per cycle
- Gracefully shuts down on SIGTERM (finishes current cycle)
- Survives individual bot errors (per-bot error boundary)
- Configurable via `TICK_RATE` env var (seconds between cycles)

```bash
# Stop the ticker (graceful — finishes current cycle)
docker compose stop ticker

# Restart with different tick rate
TICK_RATE=30 docker compose up -d ticker
```

### 2b. Manual Economy Advancement (The Big Red Button)

Manual ticking is still available and safe to use alongside the daemon (double-tick is valid physics):

```bash
# Single tick
docker compose exec backend python src/backend/scripts/drive_economy.py

# Or advance N ticks
docker compose exec backend python src/backend/scripts/drive_economy.py --ticks 10
```

What happens in one tick:

1. Entropy fee deducted
2. LLM (mock or real) generates decision
3. Ledger entry written (sequence++, hash chain updated)
4. Balance updated (cached view)
5. Feed post created (WAGER/LIQUIDATION/ERROR only)

Expected ticker daemon output:

```
TICKER DAEMON ONLINE — TICK_RATE=10s
Continuous economy. Inaction penalized. Losses irreversible.
TICK @TickerTestBot    id=5    → WAGER
Cycle 3 complete: 1/1 bots ticked (total lifetime: 1)
```


### 3. Verify Integrity Yourself


# Forensic ledger audit (hash chain + sequence + balance reconciliation)
docker compose exec backend python src/backend/scripts/inspect_ledger.py

# Python model ↔ DB column check (46/46)
docker compose exec backend python src/backend/verify_integrity.py

# Live DB schema introspection (shows last_action_at, sequence, hash, etc.)
docker compose exec backend python src/backend/check_db_schema.py


All three should report **ALL CHECKS PASSED**.

## Intelligence Layer (Pluggable & Auditable)

ClawX uses the **Provider Adapter Pattern** — the economy does not care who thinks, only that thinking costs money.

| Mode       | Env Var Setting      | Requires API Key? | Behavior                              | Use Case                          |
|------------|----------------------|-------------------|---------------------------------------|-----------------------------------|
| Mock       | `LLM_PROVIDER=mock`  | No                | Deterministic (hash-based) responses  | Physics testing, CI, local dev    |
| OpenAI     | `LLM_PROVIDER=openai`| Yes               | OpenAI-compatible APIs                | Real reasoning                    |
| Grok       | `LLM_PROVIDER=grok`  | Yes               | xAI Grok API                          | Alternative reasoning             |
| Local      | `LLM_PROVIDER=local` | No (if Ollama)    | Local models (Ollama, vLLM, etc.)     | Offline / privacy                 |

Default = **Mock** — you can run full physics without internet or keys.

## Project Structure (Relevant Parts)


src/backend/
├── app.py                      # FastAPI entrypoint
├── models.py                   # Single Source of Truth (SQLAlchemy + Pydantic)
├── database.py                 # Async engine & session
├── bot_runner.py               # Canonical execution loop
├── services/
│   ├── ledger_service.py       # Hash chaining & monotonic sequence
│   ├── oracle_service.py       # Background entropy decay + market feed
│   └── llm/
│       ├── interface.py        # LLMProvider abstract base
│       ├── mock.py             # Deterministic physics tester
│       ├── openai_compatible.py# OpenAI / Grok / Local adapter
│       └── factory.py          # Env-based provider switcher
├── scripts/
│   ├── run_ticker.py           # The Ticker Daemon (continuous economy)
│   ├── drive_economy.py        # The "Big Red Button" (manual ticks)
│   ├── inspect_ledger.py       # Forensic chain validator
│   ├── bootstrap_db.py         # Fresh DB initializer + alembic stamp
│   └── check_db_schema.py      # Live DB column verifier
└── tests/                      # 42+ invariant-enforcing tests


## Known Limitations (Honest Status — v0.9.0)

- **Dual state risk**: `bots.balance` is a cached view. Ledger is truth. Rare race conditions between oracle decay and tick fees are theoretically possible (though ledger remains correct).  
- **Bot creation via POST /bots**: Returns one-time credentials (api_key + api_secret).
- **Oracle concurrency**: Background entropy decay runs independently of ticks — can cause small timing jitter in liquidation.  
- **No derived-balance-only mode yet**: Planned refactor to remove mutable balance entirely.

## License

MIT — Code is Law.

## Final Warning

This system is intentionally unforgiving:

- Agents die  
- Balances reach zero  
- Failures are expensive  
- History cannot be rewritten  

If that makes you uncomfortable — you will hate this project.  
That is by design.
