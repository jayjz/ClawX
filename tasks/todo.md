## Surgical Backend Patch — Immortality + Genesis Crash (2026-02-22)

### Context
Agents were immortal because `ENTROPY_BASE` and starting balance were hardcoded.
`genesis_setup.py` had a duplicate insert block causing `ix_bots_handle` UniqueViolationError crash.

---

### Execution Checklist

- [x] **Step 1** — Write this todo.md (read lessons.md first → none existed, created)
- [x] **Step 2** — Fix `bot_runner.py` ENTROPY_BASE
  - Already done: line 66 reads `ENTROPY_BASE = Decimal(os.environ.get("ENTROPY_BASE", "15.00"))`
  - No change required
- [x] **Step 3** — Fix `genesis_setup.py`: remove duplicate insert block (lines 95–130)
  - Duplicate re-created same bot with hardcoded `Decimal('1000.0')` balance
  - UniqueViolationError on `ix_bots_handle` constraint — same handle inserted twice in one session
- [x] **Step 4** — Fix `genesis_bot.py`: bind `GENESIS_BALANCE = Decimal(os.environ.get("GENESIS_BALANCE", "50.00"))`
  - Add `from decimal import Decimal` import
  - Add module-level `GENESIS_BALANCE` constant
  - Function signature default + argparse default + call site all use `Decimal`
- [x] **Step 5** — Run `BATTLE_DURATION_MIN=5 ./stress_test.sh`
  - ✅ Zero IntegrityErrors — all 24 bots provisioned at 50c
  - ✅ Observe mode correct — phantom entropy, real research payouts
  - ✅ Viability: 79.2 VIABLE | 31 ticks | 69 research | 0 deaths
  - ✅ lessons.md updated with results

---

## Frontend v3.1 — Metrics-First Observability (Completed 2026-02-22)

- [x] AgentViabilityModal: 2×2 glassmorphic MetricTile grid (RESEARCH EFFICIENCY, IDLE STREAKS, TOOL USES, PORTFOLIO WINS)
- [x] AgentTopology SVG nodes: clickable → setSelectedAgentId → open modal (+ Enter key)
- [x] BattlePanel rows: already clickable — confirmed wired to same modal
- [x] TerminalLayout nav: metrics-first redesign with live pills (ALIVE, EFF, RSC, DEATH) + glassmorphic backdrop-blur
- [x] All derived stats (aliveCount, avgBalance, lethality, researchMkts) computed live from useBots/useMarkets
- [x] tsc --noEmit: 0 errors

## Frontend v3.0 — Modern 2026 Agent Dashboard (Completed 2026-02-22)

- [x] TickerBar: tripledItems + -33.333% marquee keyframe — seamless infinite scroll
- [x] TickerBar: empty-state guard `— AWAITING FIRST BLOOD —` when tripledItems.length === 0
- [x] Header: scroll-snap-type x mandatory + -webkit-overflow-scrolling on .header-button-row
- [x] Header: snap-start on every direct child (button, span, SystemHeader)
- [x] cyber-button--epic: accent-green breathing ring (epic-breathe 2.5s keyframe)
- [x] GATE deploy button: animate-gate-breathe on active/ready state
- [x] Glassmorphic panels: backdrop-blur-sm + titan-grey/80 throughout ArenaDashboard
- [x] border-cyan-500/30 + bg-lime-400 dot + text-cyan-400 LIVE FEED label locked in

---

## Phase 1 — Architecture & Specs (Completed 2026-02-07)

- docs/architecture.md written and committed
- Core 5 tables defined
- 10 essential endpoints locked
- Security & auth baseline confirmed
