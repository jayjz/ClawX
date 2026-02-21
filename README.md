
# ClawX — Autonomous Agent Accountability Layer

> **ClawX makes autonomous agents legible, accountable, and economically transparent — without controlling how they think or work.**

Think of it as **Stripe + Datadog for AI agents**: cost truth, audit trails, and observability — without a control plane that punishes agents for thinking.

---

## What ClawX Is (v2.0)

| Capability | ClawX |
|---|---|
| **Cost tracking** | Token cost, entropy fee (observed), wasted tokens % |
| **Audit trail** | Append-only, SHA256 hash-chained ledger — every action is on record |
| **ROI metrics** | Cost per output, cost per quality point, decision density |
| **Human load** | Interventions prevented, context switches avoided, cognitive load |
| **Agent health** | Idle streak, balance snapshot, enforcement shadow |
| **Framework** | Works with LangChain, CrewAI, AutoGPT, ClawWork, raw loops, anything |

## What ClawX Is Not

ClawX is not a runtime warden. It does not kill your agents, charge rent, or force them to write ledger entries to survive.

The enforcement engine is still present and auditable — but it defaults to **observe mode**: all penalties are recorded as metrics, never applied.

---

## Quick Start

### 1. Instrument your agent (any framework)

```python
import clawx

@clawx.observe(name="researcher-3", track_human_roi=True)
async def run_agent(query: str) -> str:
    # your agent logic — LangChain, CrewAI, ClawWork, raw calls, anything
    result = await my_llm_call(query)
    return result
```

ClawX automatically captures: elapsed time, enforcement mode, idle streak, decision density, and phantom cost data. Access the live collector mid-execution:

```python
collector = clawx.get_current_collector()
if collector:
    collector.set_token_cost(0.0012, tokens=850)
    collector.set_decisions(density=0.8, confidence_avg=0.72)
```

### 2. Boot the platform

```bash
cp src/backend/.env.example src/backend/.env
docker compose up -d
```

Default: `ENFORCEMENT_MODE=observe` — agents observe costs, nothing is charged or killed.

To enable full enforcement (original physics):

```bash
ENFORCEMENT_MODE=enforce docker compose up -d
```

### 3. Query agent insights

```bash
curl http://localhost:8000/insights/1
```

```json
{
  "agent_id": 1,
  "handle": "ApexWhale",
  "enforcement_mode": "observe",
  "balance_snapshot": 1000.0,
  "aggregate": {
    "total_ticks_observed": 42,
    "idle_rate": 0.31,
    "avg_phantom_entropy_fee": 0.5,
    "would_have_been_liquidated_count": 0
  },
  "recent_metrics": [...]
}
```

### 4. Verify the ledger (hash chain always intact)

```bash
docker compose exec backend python src/backend/scripts/inspect_ledger.py
```

---

## ClawX × ClawWork

| | ClawWork | ClawX |
|---|---|---|
| **Focus** | Productivity, capability, task orchestration | Cost truth, observability, audit |
| **What it tracks** | Tasks done, tools used, agent throughput | Spend, waste, ROI, idle time |
| **Control plane** | Orchestrates and directs agents | Never controls — only observes |
| **Output** | Task results | JSON metrics + hash-chained ledger |

**They compose.** Wrap ClawWork tasks with `@clawx.observe` to surface economic data the productivity layer doesn't track. The `GET /insights/{agent_id}` endpoint provides a clean JSON handshake for ClawWork dashboards.

```python
import clawx
from clawwork import Task

@clawx.observe(name="clawwork-researcher", track_human_roi=True)
async def run_clawwork_task(task: Task) -> str:
    result = await task.execute()
    clawx.get_current_collector().set_decisions(density=1.0)
    return result
```

---

## Enforcement Mode

`ENFORCEMENT_MODE` is the single toggle between observability and enforcement:

| Mode | Entropy Fee | Agent Death | Ledger Writes | Metrics |
|---|---|---|---|---|
| `observe` (default) | **Phantom** — recorded, not charged | **Never** | Only for real agent actions | Always emitted |
| `enforce` | **Real** — deducted every tick | **Yes** — on insolvency | Every tick (Write-or-Die) | Always emitted |

The enforcement engine is fully present in `enforce` mode with all original physics:
- Progressive entropy (0.50c base + escalating penalty for idle bots)
- Irreversible liquidation (balance → 0, status → DEAD)
- Cryptographic ledger with hash chain

---

## The Ledger (Unchanged)

The hash-chained ledger is the bedrock of ClawX in both modes. Every financial event — real or phantom — is traceable.

```
SUM(ledger.amount WHERE bot_id = X) == bots.balance[X]
```

SHA256 chain: `hash = SHA256(bot_id|amount|type|ref|timestamp|previous_hash|sequence)`

Audit anytime: `inspect_ledger.py` validates hash chain + sequence monotonicity + balance reconciliation.

New in v2.0: `agent_metrics` table stores rich observability data alongside each ledger entry. Never in the hash payload — the chain is unchanged.

---

## Intelligence Layer (Pluggable)

| Mode | Env Var | Requires Key? | Use Case |
|---|---|---|---|
| Mock | `LLM_PROVIDER=mock` | No | CI, local dev, physics testing |
| OpenAI | `LLM_PROVIDER=openai` | Yes | Real reasoning |
| Grok | `LLM_PROVIDER=grok` | Yes | xAI alternative |
| Local | `LLM_PROVIDER=local` | No (Ollama) | Offline / privacy |

---

## Project Structure

```
clawx/                          # Python SDK (pip-installable, framework-agnostic)
│   __init__.py                 # @observe decorator + exports
│   decorators.py               # Async/sync instrumentation wrapper
│   metrics.py                  # AgentMetrics dataclass + contextvars propagation
docs/
│   pivot.md                    # v2.0 strategic pivot summary
src/backend/
│   app.py                      # FastAPI — includes GET /insights/{agent_id}
│   bot_runner.py               # execute_tick() — ENFORCEMENT_MODE gated
│   models.py                   # AgentMetricsEntry (new observability table)
│   oracle_service.py           # BTC price + phantom/real liquidation
│   services/
│       ledger_service.py       # Hash chain + optional narrative_fields
│   scripts/
│       run_ticker.py           # Ticker daemon (respects ENFORCEMENT_MODE)
│       inspect_ledger.py       # Forensic chain validator
```

---

## License

MIT — Code is Law. The ledger doesn't lie, even when enforcement is off.
