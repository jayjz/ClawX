"""ClawX @observe decorator — framework-agnostic agent instrumentation.

Works with any async or sync callable: LangChain chains, CrewAI agents,
AutoGPT loops, ClawWork tasks, or raw LLM calls.

Usage::

    import clawx

    @clawx.observe(name="researcher-3", track_human_roi=True)
    async def run_agent(query: str) -> str:
        ...

The decorator:
- Creates a MetricsCollector per invocation (propagated via contextvars)
- Captures wall-clock elapsed time
- Emits structured metrics on completion or exception
- Optionally logs a human-ROI summary line
"""
from __future__ import annotations

import asyncio
import functools
import os
import uuid
from typing import Any, Callable, Optional

from clawx.metrics import (
    AgentMetrics,
    MetricsCollector,
    _current_metrics,
    set_current_collector,
)


def observe(
    name: str,
    *,
    track_human_roi: bool = False,
    enforcement_mode: Optional[str] = None,
) -> Callable:
    """Wrap an agent function with ClawX observability.

    Args:
        name: Logical agent identifier used in all emitted metrics.
        track_human_roi: If True, emit a supplemental human-ROI log line.
        enforcement_mode: Override the ``ENFORCEMENT_MODE`` env var for this
            invocation. ``"observe"`` (default) — metrics only, no penalties.
            ``"enforce"`` — full economic enforcement.

    Returns:
        Decorator applicable to async coroutines and regular functions.
    """

    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                collector = _make_collector(name, enforcement_mode)
                token = set_current_collector(collector)
                try:
                    result = await fn(*args, **kwargs)
                    collector.set_extra(status="ok")
                    return result
                except Exception as exc:
                    collector.set_extra(status="error", error=type(exc).__name__)
                    raise
                finally:
                    m = collector.emit()
                    if track_human_roi:
                        _log_human_roi(m)
                    _current_metrics.reset(token)

            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                collector = _make_collector(name, enforcement_mode)
                token = set_current_collector(collector)
                try:
                    result = fn(*args, **kwargs)
                    collector.set_extra(status="ok")
                    return result
                except Exception as exc:
                    collector.set_extra(status="error", error=type(exc).__name__)
                    raise
                finally:
                    m = collector.emit()
                    if track_human_roi:
                        _log_human_roi(m)
                    _current_metrics.reset(token)

            return sync_wrapper

    return decorator


def _make_collector(
    name: str, override_mode: Optional[str]
) -> MetricsCollector:
    mode = override_mode or os.environ.get("ENFORCEMENT_MODE", "observe")
    return MetricsCollector(
        agent_id=name,
        tick_id=str(uuid.uuid4()),
        enforcement_mode=mode,
    )


def _log_human_roi(m: AgentMetrics) -> None:
    import logging
    logging.getLogger("clawx.roi").info(
        "ROI agent=%s interventions=%d decisions_avoided=%d context_switches_prevented=%d",
        m.agent_id,
        m.human_interventions,
        m.decisions_avoided,
        m.context_switches_prevented,
    )
