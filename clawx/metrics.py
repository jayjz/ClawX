"""ClawX metrics model and collection.

Captures agent accountability metrics without enforcing economic punishment.
All fields are optional — collect what you have, skip what you don't.

Uses ``contextvars`` so a single MetricsCollector propagates through nested
async calls without any thread-local risk.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("clawx.metrics")

# Propagates MetricsCollector through async call stacks (no thread-local risk)
_current_metrics: contextvars.ContextVar[Optional["MetricsCollector"]] = (
    contextvars.ContextVar("_clawx_current_metrics", default=None)
)


@dataclass
class AgentMetrics:
    """Observability snapshot for one agent execution unit (tick, call, or span)."""

    agent_id: str
    tick_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # --- Cost accounting ---
    token_cost: float = 0.0           # Estimated USD cost of LLM calls this unit
    tokens_used: int = 0              # Total tokens consumed (input + output)
    input_tokens: int = 0             # LLM prompt / input tokens consumed
    output_tokens: int = 0            # LLM completion / output tokens consumed
    wasted_tokens_pct: float = 0.0    # % tokens on refusals / retries / noise

    # --- Time accounting ---
    idle_time_pct: float = 0.0        # % of recent ticks where agent was idle
    idle_streak: int = 0              # Consecutive idle ticks

    # --- Decision quality ---
    decision_density: float = 0.0     # Meaningful decisions made per tick (0–1)
    confidence_avg: float = 0.0       # Mean confidence across decisions placed

    # --- ROI ---
    roi_trend: float = 0.0            # Rolling 10-tick return on investment
    cost_per_output: float = 0.0      # Token cost / ledger entries produced
    cost_per_quality_point: float = 0.0  # Token cost / successful outcomes

    # --- Human load ---
    human_interventions: int = 0         # Admin/REVIVE actions touching this agent
    decisions_avoided: int = 0           # Automated decisions that replaced human work
    context_switches_prevented: int = 0  # Interruptions saved for human operators

    # --- Enforcement shadow (observe mode only) ---
    enforcement_mode: str = "observe"
    phantom_entropy_fee: float = 0.0      # Fee that WOULD have been charged
    would_have_been_liquidated: bool = False  # Bot WOULD have died in enforce mode

    # --- Outcome ---
    tick_outcome: str = "HEARTBEAT"
    balance_snapshot: float = 0.0

    # --- Arbitrary extension bag ---
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class MetricsCollector:
    """Builds and emits an AgentMetrics snapshot for one execution unit."""

    def __init__(
        self,
        agent_id: str,
        tick_id: str,
        enforcement_mode: str = "observe",
    ) -> None:
        self._start = time.monotonic()
        self._m = AgentMetrics(
            agent_id=agent_id,
            tick_id=tick_id,
            enforcement_mode=enforcement_mode,
        )

    # --- Fluent builder API ---

    def set_token_cost(self, cost: float, tokens: int = 0) -> "MetricsCollector":
        self._m.token_cost = cost
        self._m.tokens_used = tokens
        return self

    def set_input_tokens(self, n: int) -> "MetricsCollector":
        """Set prompt/input token count and update total."""
        self._m.input_tokens = n
        self._m.tokens_used = self._m.input_tokens + self._m.output_tokens
        return self

    def set_output_tokens(self, n: int) -> "MetricsCollector":
        """Set completion/output token count and update total."""
        self._m.output_tokens = n
        self._m.tokens_used = self._m.input_tokens + self._m.output_tokens
        return self

    def increment_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
    ) -> "MetricsCollector":
        """Accumulate token counts and USD cost across multiple LLM calls in one tick.

        Called by ``TrackedProvider`` after each ``generate()`` call — multiple
        calls per tick (research, portfolio, strategy) all add up here.
        """
        self._m.input_tokens += input_tokens
        self._m.output_tokens += output_tokens
        self._m.tokens_used = self._m.input_tokens + self._m.output_tokens
        self._m.token_cost += cost
        return self

    def set_wasted_tokens(self, pct: float) -> "MetricsCollector":
        self._m.wasted_tokens_pct = max(0.0, min(100.0, pct))
        return self

    def set_idle(self, idle_streak: int, idle_time_pct: float = 0.0) -> "MetricsCollector":
        self._m.idle_streak = idle_streak
        self._m.idle_time_pct = max(0.0, min(100.0, idle_time_pct))
        return self

    def set_decisions(
        self, density: float, confidence_avg: float = 0.0
    ) -> "MetricsCollector":
        self._m.decision_density = density
        self._m.confidence_avg = confidence_avg
        return self

    def set_roi(
        self,
        roi_trend: float = 0.0,
        cost_per_output: float = 0.0,
        cost_per_quality: float = 0.0,
    ) -> "MetricsCollector":
        self._m.roi_trend = roi_trend
        self._m.cost_per_output = cost_per_output
        self._m.cost_per_quality_point = cost_per_quality
        return self

    def record_phantom_enforcement(
        self, fee: float, would_liquidate: bool = False
    ) -> "MetricsCollector":
        """Record what enforcement WOULD have done (observe mode only)."""
        self._m.phantom_entropy_fee = fee
        self._m.would_have_been_liquidated = would_liquidate
        return self

    def set_outcome(self, outcome: str, balance: float) -> "MetricsCollector":
        self._m.tick_outcome = outcome
        self._m.balance_snapshot = balance
        return self

    def set_extra(self, **kwargs: Any) -> "MetricsCollector":
        self._m.extra.update(kwargs)
        return self

    def snapshot(self) -> AgentMetrics:
        return self._m

    def emit(self) -> AgentMetrics:
        """Finalise timing, log structured metrics, and return the snapshot."""
        elapsed = time.monotonic() - self._start
        self._m.extra["elapsed_s"] = round(elapsed, 3)
        logger.info(
            "METRICS agent=%s tick=%s mode=%s outcome=%s "
            "phantom_fee=%.4f would_liquidate=%s idle=%d density=%.2f",
            self._m.agent_id,
            self._m.tick_id[:8],
            self._m.enforcement_mode,
            self._m.tick_outcome,
            self._m.phantom_entropy_fee,
            self._m.would_have_been_liquidated,
            self._m.idle_streak,
            self._m.decision_density,
        )
        return self._m


# --- Context propagation helpers ---

def get_current_collector() -> Optional[MetricsCollector]:
    """Return the MetricsCollector active in the current async context, or None."""
    return _current_metrics.get()


def set_current_collector(collector: MetricsCollector) -> contextvars.Token:
    """Activate a collector in the current async context. Returns reset token."""
    return _current_metrics.set(collector)
