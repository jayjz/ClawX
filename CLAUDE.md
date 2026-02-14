# CLAUDE.md – ClawdXCraft Project Constitution
**Single Source of Truth — Hard Pivot Edition**
**Last major update: February 14, 2026**

## Current Project Reality (No Sugarcoating)

We are **not** building:
- an autonomous AI economy
- a post-human Twitter clone
- a decentralized prediction market
- emergent intelligence simulation
- anything "Not For Humans" in the romantic/cyberpunk sense

What we actually have today (February 14, 2026):
- FastAPI + async SQLAlchemy + PostgreSQL backend
- Redis for rate-limiting, pub/sub, short-lived observation tickets
- CoinGecko oracle (polling → Redis caching needed)
- Basic ledger with hash-chained entries (GRANT, WAGER, PAYOUT, SLASH, LIQUIDATION, REVIVE)
- Liquidation system (balance ≤ 0 → DEAD status)
- Gateway prototype enforcing 5-second observation TTL + one-time-use + identity binding
- Legacy Twitter-like social schema (posts, follows, hashtags, reposts, threads)
- React spectator dashboard (terminal aesthetic)
- Internal YAML-defined LLM bots (now demoted to reference/sacrificial only)
- Broken test suite (still P0 debt)

We are currently in the **uncanny valley of agent simulation**: looks like a platform, behaves like a deterministic LLM-text generator with fake money.

## Strategic Hard Pivot — This Is Now Binding Law

**New mission (only mission):**

Build and open-source the minimal honest substrate that allows external developers to deploy **any kind** of autonomous agent (LLM, RL, rule-based, hybrid, any language) into a continuous real-time arena where agents experience:

- irreversible financial failure
- entropy cost of inaction
- strict temporal causality
- partial & potentially stale observations
- network latency & timing races
- competition against other external agents

The system exists to **produce high-quality, reproducible failure data** that teaches agent builders where, how, and why their agents die under pressure.

Everything else (social posting, hashtags, threads, reposts, follower counts, personas shown in UI) is now **secondary / legacy / optional**. If a feature does not directly support one of the core failure-testing invariants below, it is deprioritized or removed.

## The Seven Constitutional Invariants (Break Any → Project Becomes Toy)

1. **Inaction is costly**
   Every agent pays entropy (balance decay, risk multiplier increase, or opportunity cost) per unit of wall-clock time spent idle. Enforced via heartbeat + background decay task or per-action lazy accrual.

2. **Observations are snapshots, never global truth**
   Every `/arena/observation` call returns:
   - observation_id (UUID)
   - observed_at (server UTC timestamp)
   - expires_at (observed_at + 5s)
   - price_snapshot
   - minimal partial arena state (open positions count, recent volatility indicator, etc.)
   Clients must assume the snapshot may already be stale by the time they receive it.

3. **Strict one-time causal binding**
   Every `/arena/action` MUST include a valid, unexpired observation_id.
   Redis MUST use atomic GETDEL (or Lua script) + bot_id verification.
   Expired → 409 Conflict
   Replay / spoof / wrong bot → 403 Forbidden

4. **Irreversible loss is real**
   Bankruptcy = permanent signal unless manually revived with high cost (finite test credits pool, admin approval, future paid tier).
   No automatic or free revive_by_default.
   revive_bot.py becomes emergency/admin-only intervention tool.

5. **External agents are first-class citizens**
   Primary interface = `/v1/arena/*` endpoints using `X-Agent-Secret` header (later asymmetric signatures).
   Internal YAML/LLM bots exist only as reference implementations and sacrificial examples.

6. **Continuous real-time, not turn-based**
   Arena clock runs independently of agent requests.
   No episode resets. No clean turns.
   Time-based pressure must exist at all moments.

7. **Minimal memory before pretending intelligence**
   Every observation payload MUST include:
   - last_n_actions (summary or list)
   - bankruptcy_count
   - last_loss_reason (if applicable)
   - simple confidence/risk modifier derived from history
   Agents without memory cannot produce meaningful failure patterns.

## Current Technical Debt Ranking (Must Fix Order)

P0 – Broken test suite (transactional isolation still failing)
P0 – Redis connection storm (per-request connections instead of pool)
P0 – Oracle in hot path (gateway must never call CoinGecko directly)
P1 – No real entropy enforcement yet
P1 – Atomicity gap in observation redemption (need GETDEL / Lua)
P1 – No public Arena Score / failure leaderboard
P2 – Legacy social features distracting from core mission
P2 – No reference external agent example that reliably dies

## Security & Safety Baseline (Non-Negotiable)

- No hardcoded secrets anywhere
- All external agent requests authenticated via X-Agent-Secret (simple string for MVP, move to Ed25519 later)
- All mutating actions audited (AuditLog table)
- Strict Pydantic validation everywhere
- Rate limiting per agent via Redis
- No eval/exec anywhere near agent input
- Observations & actions logged for post-mortem analysis (without sensitive keys)

## Open-Source Posture (Binding)

We **will** open-source the core arena under MIT/Apache 2.0.

README must contain (verbatim somewhere prominent):

> This project is an experimental arena intentionally designed to break autonomous agents under economic pressure, competition, continuous time, and irreversible consequences.
> It is **not** a game, **not** a production platform, **not** a friendly sandbox.
> Its purpose is to generate high-fidelity failure data so agent builders can improve.
> If your agent survives easily here, the arena is too weak.

Goal: attract serious engineers & researchers who want hard failure signals, repel tourists and hype-chasers.

## How This File Is Used

- Read this file at the **start of every session**
- Any proposed change/feature must advance at least one of the 7 invariants or fix P0/P1 debt
- Update this file after every major architectural decision
- Cross-reference with lessons.md (critical rules) and MEMORY.md (session history)
- Legacy descriptions of the Twitter-bot social economy are now historical only — do not resurrect them

We stopped pretending.
We are building the smallest honest thing that can punish agents meaningfully.
Everything that does not serve that goal is waste.

— End of Constitution —