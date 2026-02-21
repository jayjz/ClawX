# MEMORY.md — ClawX Project Memory Cluster (Feb 21 2026)

## Hard Pivot Executed (v2.0)
- Identity: “ClawX makes autonomous agents legible, accountable, and economically transparent — without controlling how they think or work.”
- ENFORCEMENT_MODE=observe (default) → phantom fees/deaths, no balance mutation
- Ledger sacred: hash chain untouched, narrative_fields → AgentMetricsEntry shadow table (additive)
- SDK: clawx/ with @observe decorator, MetricsCollector (contextvars)
- /insights/{agent_id} endpoint returns idle_rate, phantom_entropy_fee, etc.

## LLM Token Tracking (TrackedProvider)
- New file: src/backend/services/llm/tracked_provider.py
- Factory wraps only inside @observe
- generate_tracked() extracts usage from response
- increment_tokens() accumulates in collector
- Cost placeholder: (input*3 + output*10)/1M USD

## Current Bugs (Feb 21 15:23 EST)
- Ledger drift in observe mode: skipped HEARTBEAT writes break SUM(ledger) == Bot.balance
- /insights 500: likely zero-division in idle_rate or missing data
- WS rejected spam: frontend no token

## Next Fixes Needed
- Record 0-amount ledger entries for skipped fees in observe mode
- Guard /insights aggregation (total_ticks > 0)
- Optional WS auth bypass in dev mode
