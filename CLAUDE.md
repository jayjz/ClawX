# CLAUDE.md – ClawX Project Constitution
**Single Source of Truth — Truth Engine Edition (v2.0 — Hard Pivot Executed)**
**Last major update: February 21, 2026**

## Current Project Reality (Post-Pivot v2.0)

We have **executed the hard pivot** from "enforcement prison" to **"accountability + observability layer"**.

**What exists today (v2.0 — observe mode default):**
- **Core Engine:** FastAPI + Async SQLAlchemy + Postgres (`Numeric` precision preserved).
- **The Heart (softened):** `run_ticker.py` daemon still advances time, but **entropy fees, liquidations, and deaths are phantom metrics only** when `ENFORCEMENT_MODE=observe` (default).
- **The Truth (enhanced):** Append-only hash-chained `ledger` table (immutable core) + new shadow `agent_metrics` table for rich narrative (phantom fees, idle streaks, decision density, token costs when wired).
- **The Senses:** `AsyncFeedIngestor` still pulls real-world data (GitHub, news, weather, etc.).
- **The Market:** Polymorphic `markets` + `market_predictions` unchanged — bets still possible in enforce mode.
- **The UI:** React "Agent Battle Arena" (CRT aesthetic, Kill Feed, Leaderboard, Graveyard) — **needs update** to visualize phantom fees, idle rates, token burn, /insights data.
- **The SDK:** `clawx/` package at root with `@observe` decorator, `MetricsCollector` (contextvars), fluent API for metrics emission.
- **Observability Surface:** `GET /insights/{agent_id}` returns aggregate + recent narrative JSON (idle_rate, phantom_entropy_fee, etc.).
- **Integrity:** Hash chain sacred. `inspect_ledger.py` still validates chain + balance reconciliation (now also sees phantom events in metrics shadow).
- **Stress Test:** 50-agent runs still stable; observe mode removes liquidation pressure.

## Strategic Mission (Post-Pivot)

**Mission:**  
Become the **Stripe + Datadog of autonomous AI agents** — make every agent legible, accountable, and economically transparent **without controlling how they think or work**.

**The New Loop (observe mode dominant):**
1. Instrument any agent (ClawWork, LangChain, CrewAI, custom) with `@clawx.observe`
2. Observe real costs (tokens when wired, phantom entropy, idle streaks)
3. Query `/insights` for cost truth, waste %, ROI trends, human load metrics
4. Decide: scale, guardrail, retire — humans stay in control

**ClawX × ClawWork complementarity (locked in):**
- ClawWork = productivity & capability layer ("Can it do valuable work?")
- ClawX = cost truth & observability layer ("Was the work worth the cost?")

## The Constitutional Invariants (v2.0 — Relaxed Physics)

1. **Ledger = Immutable Truth**  
   Hash chain (SHA256) must never break. Sequence monotonic per bot.  
   New: `agent_metrics` shadow table captures narrative without touching chain.

2. **Observability by Default**  
   `ENFORCEMENT_MODE=observe` → no balance changes, no deaths, phantom fees/deaths logged as metrics.  
   `enforce` mode still exists (original physics) but is opt-in.

3. **Decimal Purity**  
   All money uses `Decimal` + `Numeric(18,8)`. Float banned for finance.

4. **External Truth**  
   Markets resolved by verifiable data sources (unchanged).

5. **No Silent Drift**  
   Every observed tick emits metrics (even if phantom). No invisible waste.

## Current Technical Debt & Immediate Priorities (v2.0 → v2.1)

**P0 — Critical (do today/tomorrow):**
- Wire real LLM token tracking (TrackedProvider in factory.py → collector.set_token_cost)
- Alembic autogenerate + upgrade for `agent_metrics` table

**P1 — High value:**
- Hook human ROI metrics (intervention count, decisions avoided) via manual collector calls
- Frontend: embed `/insights` data into ArenaDashboard (idle heatmaps, token burn charts)

**P2 — Polish:**
- ClawWork handshake: `clawx.export_for_clawwork(agent_id)` → exact JSON schema
- Clean bot_runner.py (extract enforcement policy class — reduce if/else spam)

**Resolved Debt (pivot execution):**
- [x] Runtime punishments default off
- [x] README rewritten to new identity
- [x] SDK + /insights endpoint live
- [x] Tests for observe mode + metrics emission passing

## Security & Safety Baseline (Unchanged)
- No hardcoded secrets
- Async purity (httpx only)
- Pydantic strict validation

## Open-Source Posture (Updated)
**Code is still Law — but now Truth is Law too.**  
Anyone can run `docker compose up -d` with `ENFORCEMENT_MODE=observe` and observe agents without killing them.  
The ledger remains verifiable forever.

> "If your agent looks expensive here, it will look even worse in production."  
> — Post-pivot motto

— End of Constitution v2.0 —