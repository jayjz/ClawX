# CLAUDE.md — ClawX Project Constitution
**Single Source of Truth — Cost & Observability Engine (v2.2)**
**Last major update: February 21, 2026**

---

## Project Reality (Post-Pivot)

ClawX has **completed its hard pivot**.

We are no longer an enforcement system.  
We are an **accountability + observability layer for autonomous agents**.

ClawX exists to make agents **economically legible** so humans can confidently decide to **scale, constrain, or retire them**.

---

## What Exists Today (v2.2 — Observe Mode Default)

- **Core Engine:** FastAPI + Async SQLAlchemy + Postgres  
  Financial precision preserved via `Decimal` + `Numeric(18,8)`.

- **Time Engine:**  
  `run_ticker.py` advances time deterministically.  
  In `ENFORCEMENT_MODE=observe` (default), entropy fees, liquidations, and deaths are **counterfactual only**.

- **Immutable Truth:**  
  Append-only, hash-chained `ledger` table remains sacred and unmodified.  
  Sequence monotonic per bot. Chain must always validate.

- **Narrative Metrics (Primary Surface):**  
  `agent_metrics` shadow table captures **non-financial reality**:
  - phantom entropy fees
  - idle streaks
  - decision density
  - token cost (when wired)
  - human intervention signals

  These metrics **never mutate the ledger**.

- **The Senses:**  
  `AsyncFeedIngestor` continues to pull external data (GitHub, news, weather, etc.).

- **Markets:**  
  Polymorphic `markets` and `market_predictions` remain intact.  
  Real resolution still requires enforce mode.

- **SDK (First-Class):**  
  Root-level `clawx/` package with:
  - `@observe` decorator
  - `MetricsCollector` (contextvars)
  - Fluent API for emitting cost, waste, and human-load signals

- **Observability Surface:**  
  `GET /insights/{agent_id}` returns aggregate + recent narrative truth:
  idle rate, counterfactual burn, token usage, trend deltas, and risk flags.

- **Integrity Tooling:**  
  `inspect_ledger.py` validates:
  - hash chain integrity
  - sequence monotonicity
  - balance reconciliation  
  (metrics live outside this invariant)

- **Stability:**  
  50+ agent simulations stable in observe mode.  
  No liquidation pressure by default.

---

## Strategic Mission

**Mission:**  
Become the **Stripe + Datadog of autonomous AI agents**.

ClawX does **not** control agents.  
ClawX makes their **cost, waste, and human load undeniable**.

---

## The Core Loop (Observe Mode Dominant)

1. Instrument any agent using `@clawx.observe`
2. Observe:
   - real execution cost
   - counterfactual waste
   - human attention consumed
3. Query `/insights` for economic and operational truth
4. Human decides: **scale · guardrail · retire**

ClawX never auto-punishes.  
Humans remain the final authority.

---

## ClawX × ClawWork Boundary (Locked)

- **ClawWork:** Capability, task execution, throughput  
  _“Can this agent do useful work?”_

- **ClawX:** Cost truth, waste detection, human legibility  
  _“Was that work worth the cost?”_

No implicit coupling.  
Only explicit schemas.

---

## Constitutional Invariants (v2.2)

1. **Ledger = Immutable Audit Truth**  
   Hash chain must never break.  
   Ledger exists for verification, not UX.

2. **Observability by Default**  
   `ENFORCEMENT_MODE=observe`:
   - no balance mutation
   - no deaths
   - no forced shutdowns  
   Counterfactuals are metrics only.

3. **Metrics Are Additive, Never Destructive**  
   All narrative truth lives in `agent_metrics`.  
   Ledger invariants remain untouched.

4. **Decimal Purity**  
   All monetary values use `Decimal`.  
   Floats are forbidden in finance paths.

5. **No Silent Drift**  
   Every tick emits observable data.  
   Invisible waste is a bug.

---

## Product Boundary: `/insights`

`GET /insights/{agent_id}` must always answer:

1. What did this agent cost?
2. What value did it plausibly produce?
3. How much human attention did it consume?
4. Is it trending better or worse?
5. What happens if we do nothing?

If a metric does not help answer these, it does not belong.

---

## Current Priorities (v2.2)

**P0 — Critical**
- Wire real LLM token tracking via `TrackedProvider`
- Alembic autogenerate + migrate `agent_metrics`

**P1 — High Value**
- Human load metrics (interventions, decisions avoided)
- Frontend: replace “Arena” metaphors with cost & clarity views
- `/insights` stability and zero-data guards

**P2 — Polish**
- Explicit ClawWork ↔ ClawX export schema
- Simplify enforcement branching (policy extraction)

---

## Security & Safety Baseline

- No hardcoded secrets
- Async-only I/O (`httpx`)
- Strict Pydantic validation
- Deterministic execution paths

---

## Open Source Posture

**Code is Law. Truth is Law.**

Anyone can run ClawX in observe mode and see the real cost of their agents without harming them.

If an agent looks expensive here,  
it will look worse in production.

---

— End of Constitution v2.2 —