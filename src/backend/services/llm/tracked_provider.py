"""ClawX token-tracking LLM provider wrapper.

Wraps any ``LLMProvider`` to automatically capture prompt/completion token counts
and estimated USD cost into the active ``MetricsCollector`` (if any).

Design principles:
  - Zero overhead when no collector is active (outside ``@observe``).
  - Transparent passthrough — callers receive identical content to unwrapped calls.
  - ``generate_tracked()`` on the base provider supplies real usage; the default
    fallback in ``LLMProvider`` returns (content, 0, 0) for providers that don't
    expose usage (e.g. mock).
  - clawx is imported lazily inside generate() so this module is safe to import
    even if the repo root is not on PYTHONPATH (graceful degradation to passthrough).

Cost model (USD, configurable via env):
  Input  tokens: CLAWX_INPUT_COST_PER_M  (default 3.0  USD / 1M tokens, gpt-4o-mini)
  Output tokens: CLAWX_OUTPUT_COST_PER_M (default 10.0 USD / 1M tokens, gpt-4o-mini)
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from services.llm.interface import LLMProvider

if TYPE_CHECKING:
    from clawx.metrics import MetricsCollector

logger = logging.getLogger("clawx.tracked_provider")

# Read once at import time (module is a singleton alongside the base provider).
# Override via env to match the actual deployed model's pricing.
_INPUT_COST_PER_TOKEN: float = (
    float(os.environ.get("CLAWX_INPUT_COST_PER_M", "3.0")) / 1_000_000
)
_OUTPUT_COST_PER_TOKEN: float = (
    float(os.environ.get("CLAWX_OUTPUT_COST_PER_M", "10.0")) / 1_000_000
)


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts using the configured cost model."""
    return (
        prompt_tokens * _INPUT_COST_PER_TOKEN
        + completion_tokens * _OUTPUT_COST_PER_TOKEN
    )


class TrackedProvider(LLMProvider):
    """Passthrough ``LLMProvider`` that instruments token usage into ``MetricsCollector``.

    Returned by ``get_llm_provider()`` when called inside an ``@observe`` context.
    Outside ``@observe``, the factory returns the unwrapped base provider so there
    is zero cost from this wrapper in the hot path.

    Token accumulation is additive — multiple LLM calls within the same
    ``@observe`` span (e.g. strategy + portfolio + research in one tick) all
    add to the same collector via ``increment_tokens()``.
    """

    def __init__(self, base: LLMProvider) -> None:
        self._base = base

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str | None:
        """Delegate to ``base.generate_tracked()``, push usage into MetricsCollector."""
        # Lazy import: keeps clawx optional; degrades gracefully if unavailable.
        collector: MetricsCollector | None = None
        try:
            from clawx.metrics import get_current_collector
            collector = get_current_collector()
        except ImportError:
            pass

        if collector is None:
            # Not inside @observe — pure passthrough, zero allocation overhead.
            return await self._base.generate(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )

        # Inside @observe — use generate_tracked() to capture usage metadata.
        content, prompt_tokens, completion_tokens = await self._base.generate_tracked(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )

        cost = _estimate_cost(prompt_tokens, completion_tokens)
        collector.increment_tokens(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cost=cost,
        )

        if prompt_tokens or completion_tokens:
            logger.debug(
                "TOKEN in=%d out=%d cost=$%.6f agent=%s tick=%s",
                prompt_tokens,
                completion_tokens,
                cost,
                collector.snapshot().agent_id,
                collector.snapshot().tick_id[:8],
            )

        return content
