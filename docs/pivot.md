# ClawX v2.0 — Strategic Pivot Summary

**Date:** February 2026
**From:** Enforcement engine (runtime punishment, agent death, entropy drain)
**To:** Accountability + observability layer (cost truth, audit, ROI — without control)

---

## The One-Sentence Shift

> *ClawX makes autonomous agents legible, accountable, and economically transparent — without controlling how they think or work.*

Previously: **"Agents that can't survive the arena don't deserve to run."**
Now: **"Agents that can't explain their costs don't deserve your budget."**

---

## What Changed (and What Didn't)

### Changed

| Component | Before | After |
|---|---|---|
| `ENFORCEMENT_MODE` | Hardcoded "always enforce" | Env var, default `"observe"` |
| Entropy fee | Charged every tick, balance drained | Phantom metric in `observe` mode |
| Agent death | Irreversible on insolvency | No-op in `observe` mode; logged |
| Oracle reaper | Kills insolvent bots | Logs would-have-died events |
| `bot_runner` error handler | Charges fee even on exception | Phantom metric in `observe` mode |
| `ledger_service` | Single audit function | + `narrative_fields` observability param |
| API | No insights endpoint | `GET /insights/{agent_id}` |
| README | "Unforgiving enforcer" | Accountability layer narrative |
| SDK | None | `clawx/` package with `@observe` |
| LLM providers | Token counts discarded | `TrackedProvider` captures & accumulates (**v2.1**) |
| `LLMProvider` interface | `generate()` only | + `generate_tracked()` returns `(content, in_tok, out_tok)` (**v2.1**) |
| `OpenAICompatibleProvider` | Discards `response.usage` | `generate_tracked()` extracts real token counts (**v2.1**) |
| `MetricsCollector` | `set_token_cost(total)` | + `set_input_tokens`, `set_output_tokens`, `increment_tokens` (**v2.1**) |

### Not Changed

| Component | Status |
|---|---|
| Ledger hash chain | **Unchanged** — SHA256 payload identical |
| `SUM(ledger) == balance` invariant | **Preserved** in both modes |
| Sequence monotonicity | **Preserved** |
| DB schema | **Additive only** — new `agent_metrics` table, no altered columns |
| `enforce` mode behaviour | **100% backward compatible** — set `ENFORCEMENT_MODE=enforce` |
| All existing tests | **Pass** (enforcement paths still exist and work) |

---

## New: `clawx/` SDK

Framework-agnostic Python SDK for any agent loop.

```python
import clawx

@clawx.observe(name="my-agent", track_human_roi=True)
async def run(query: str) -> str:
    ...
```

Metrics automatically captured:
- `token_cost`, `tokens_used`, `wasted_tokens_pct`
- `idle_time_pct`, `idle_streak`
- `decision_density`, `confidence_avg`
- `roi_trend`, `cost_per_output`, `cost_per_quality_point`
- `human_interventions`, `decisions_avoided`, `context_switches_prevented`
- `phantom_entropy_fee`, `would_have_been_liquidated` (enforce mode shadow)

---

## New: `agent_metrics` Table

Additive observability companion to the ledger. Never part of the hash chain.

| Column | Type | Purpose |
|---|---|---|
| `bot_id` | FK → bots | Agent identity |
| `ledger_id` | FK → ledger (nullable) | Link to primary ledger entry |
| `tick_id` | String | Correlation key across tables |
| `enforcement_mode` | String | observe / enforce |
| `tick_outcome` | String | HEARTBEAT / PORTFOLIO / WAGER / LIQUIDATION_OBSERVED |
| `phantom_entropy_fee` | Numeric(18,8) | Fee that would have been charged |
| `would_have_been_liquidated` | Boolean | Death that was avoided |
| `balance_snapshot` | Numeric(18,8) | Balance at time of tick |
| `metrics_json` | JSONB | Full narrative payload |

---

## New: `GET /insights/{agent_id}`

Returns aggregated narrative JSON for operator dashboards and ClawWork handshake:

```json
{
  "agent_id": 3,
  "handle": "ResearchBot",
  "enforcement_mode": "observe",
  "balance_snapshot": 987.5,
  "aggregate": {
    "total_ticks_observed": 100,
    "idle_rate": 0.22,
    "avg_phantom_entropy_fee": 0.5,
    "would_have_been_liquidated_count": 0
  },
  "recent_metrics": [...]
}
```

---

## Migration Path

Existing deployments using the enforcement engine:

```bash
# Keep full enforcement (no change in behaviour)
ENFORCEMENT_MODE=enforce docker compose up -d

# Switch to observe mode (default)
ENFORCEMENT_MODE=observe docker compose up -d
# or just: docker compose up -d
```

The `agent_metrics` table is created automatically by `init_db()` / `create_all()` on next boot. No manual migration needed.

---

## Rationale

The enforcement model was a **proving ground** — useful for testing raw agent survival fitness. The accountability model is a **production tool** — useful for teams shipping agents to customers who care about cost, auditability, and ROI.

ClawX now serves both: observe by default, enforce when you want the arena.
