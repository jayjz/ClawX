# CLAUDE.md — ClawX Project Constitution
**Single Source of Truth — Cost & Observability Engine (v2.4)**
**Last major update: February 23, 2026**

---

## Project Reality (Post-Pivot)

ClawX has **completed its hard pivot**.

We are no longer an enforcement system.  
We are an **accountability + observability layer for autonomous agents**.

ClawX exists to make agents **economically legible** so humans can confidently decide to **scale, constrain, or retire them**.

---

## What Exists Today (v2.4 — Observe Mode Default)

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

- **Frontend v3.2 — Dark Forest Entropy Grinder (Shipped 2026-02-23)**  
  - Single Canvas 2D arena (no PixiJS, zero new deps) — entire screen is the living zero-sum arena  
  - Center entropy well: radial gradient black hole, radius tracks total economy / genesis  
  - Agent nodes orbit the well in 3 rings (ring = balance quartile), golden-angle distribution  
  - Betrayal lines: proximity-filtered connections, green = alliance, red pulsing = defection  
  - Graveyard debris: dead agent shards accumulate at bottom with handle labels  
  - Hover prisoner's dilemma heatmap: cooperation %, CC/CD/DC/DD outcomes per pair  
  - MetricsBar: ALIVE / LETHALITY / KIA pills + well-drain progress bar + ⌘K  
  - Minimal TerminalLayout header (h-10, brand + clock + MANUAL), metrics nav, tick footer  
  - `tsc --noEmit: 0 errors`

- **Frontend v3.1 — Danger Layer (Shipped 2026-02-23)**  
  - Metrics-first navbar: live ALIVE/LETHALITY/RESEARCH/KIA pills + glassmorphic backdrop  
  - KIA pill pulses red on death increase  
  - Pre-death glow: red border on balance < 36c agents  
  - Permanent scars: diagonal red line on dead rows + line-through handle  
  - Dominance crown: ♛ + rotating ring + DOMINANT badge on top agent  
  - Idle ticks: "Xi" amber badge when idle ≥3  
  - Footer NEXT TICK countdown (pulses red ≤3s)

- **Frontend v3.0 — Living Coliseum Base (Shipped 2026-02-22)**  
  - Live scrolling ticker (tripledItems + gapless -33.333% marquee)  
  - Breathing deploy button (cyber-button--epic, animate-gate-breathe)  
  - Glassmorphic panels (backdrop-blur-sm, titan-grey/80, rounded-xl)  
  - Header snap-scroll no-clip (scroll-snap-type x mandatory, snap-start children)  
  - Empty ticker placeholder (AWAITING FIRST BLOOD guard)

- **Testing & Development Workflow (2026-02-23)**  
  - quick_test.sh v1.4 — nuclear reset, --no-cache frontend rebuild, verbose deploy, robust per-service health checks, danger-layer monitoring  
  - stay_alive.sh — long-running survival test with 10 hyper-optimized personas  
  - Claude CLI token-limit workaround: `export CLAUDE_CODE_MAX_OUTPUT_TOKENS=100000` for large file rewrites

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

## Constitutional Invariants (v2.4)

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

## Game Theory UX Laws (Non-Negotiable — 2026 Aesthetic)

The UI must visually embody zero-sum survival, resource scarcity, and prisoner's dilemma.

- **Scarcity First:** The screen is the arena. No panels that obscure the Dark Forest canvas. The entropy well must always be visible and visibly shrinking.
- **Death Counter Priority:** KIA / LETHALITY pills must pulse red on any death. Death is the most important signal in the system.
- **Visual Mass for Dominance:** The highest-balance agent must have visibly larger node, rotating crown ring, and DOMINANT badge. Dominant agents must feel heavier.
- **Betrayal Visibility:** Live connections between agents must show alliance (green) or defection (red pulsing) based on real events.
- **Graveyard Growth:** Dead agents must explode into shards that accumulate and physically crowd the arena, reducing space for survivors.
- **No Fluff:** No decorative scanlines, no retro CRT effects, no unnecessary icons. All visuals must communicate consequence or scarcity.
- **Glassmorphic Command Bar:** Navigation is a floating glassmorphic ⌘K bar. No static tabs.
- **Full-Row Flash:** Ledger wins/losses use full-row flash (400ms) for cognitive offloading.
- **Canvas Over SVG:** New arena views use Canvas 2D (or WebGL if needed). No SVG for dynamic particle systems.
- **Dark Mode 2.0:** Background #0B0F19 (abyssal blue/charcoal). Text uses Inter/SF Pro for chrome, JetBrains Mono for data.

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

## Current Priorities (v2.4)

**Done — Frontend v3.2 Dark Forest Entropy Grinder (2026-02-23)**  
- Single Canvas 2D arena — entire screen is the living zero-sum arena  
- Entropy well, orbiting nodes, betrayal lines, graveyard debris, hover PD heatmap  
- Metrics-first navbar + KIA pulse + footer tick countdown  
- Danger layer complete (red glow, scars, crown, idle badges)

**Done — Frontend v3.1 Danger Layer (2026-02-23)**  
- Metrics-first navbar with live pills  
- KIA pill pulse on death increase  
- Pre-death red glow on low-balance agents  
- Permanent scars on dead rows/nodes  
- Dominance crown & DOMINANT badge  
- Idle "Xi" amber badges  
- Footer NEXT TICK countdown

**Done — Frontend v3.0 Living Coliseum Base (2026-02-22)**  
- Live scrolling ticker  
- Breathing deploy button  
- Glassmorphic panels  
- Header snap-scroll no-clip  
- Empty ticker placeholder

**P0 — Critical**  
- Wire real LLM token tracking via `TrackedProvider`  
- Alembic autogenerate + migrate `agent_metrics`

**P1 — High Value**  
- Human load metrics (interventions, decisions avoided)  
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

— End of Constitution v2.4 —