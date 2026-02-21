"""ClawX — Autonomous Agent Accountability Layer.

ClawX makes autonomous agents legible, accountable, and economically
transparent — without controlling how they think or work.

Think of it as Stripe + Datadog for AI agents: cost truth, observability,
and audit trails — without dictating agent logic or runtime behaviour.

Works with any framework: LangChain, CrewAI, AutoGPT, ClawWork, raw LLM
calls, or any custom loop. Zero control-plane dependencies.

Quick start::

    import clawx

    @clawx.observe(name="researcher-3", track_human_roi=True)
    async def run_agent(query: str) -> str:
        # your agent logic here — ClawX records cost, idle time, decisions
        ...

ClawX × ClawWork::

    ClawWork = productivity + capability  (task orchestration, tool use)
    ClawX    = cost truth + observability (audit, spend, ROI tracking)

    They compose: wrap ClawWork tasks with @clawx.observe to surface
    economic data the productivity layer doesn't track.
    Export via ``GET /insights/{agent_id}`` for clean JSON handshake.
"""

from clawx.decorators import observe
from clawx.metrics import (
    AgentMetrics,
    MetricsCollector,
    get_current_collector,
    set_current_collector,
)

__version__ = "2.0.0"
__all__ = [
    "observe",
    "AgentMetrics",
    "MetricsCollector",
    "get_current_collector",
    "set_current_collector",
]
