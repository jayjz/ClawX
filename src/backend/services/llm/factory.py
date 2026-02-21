"""LLM provider factory.

Reads LLM_PROVIDER env var and returns the appropriate provider instance.
Defaults to "mock" for safe test/CI operation — no API keys needed.

v2.0 — ClawX token tracking:
  When called inside an ``@observe`` context (i.e. ``get_current_collector()``
  is non-None), the factory wraps the base provider in ``TrackedProvider``.
  Outside ``@observe``, the raw base is returned — zero overhead.
  This preserves all existing ``type(provider).__name__`` test assertions
  because those tests run outside any ``@observe`` context.

Constitutional references:
  - CLAUDE.md P0 debt: "Broken test suite" — mock default means tests
    never fail due to missing LLM credentials.
  - lessons.md Rule #2: "Fail Fast on Missing Configuration" —
    real providers will raise immediately if API keys are absent.
  - MEMORY.md Docker rules: env vars set in docker-compose.yml.
"""

import logging
import os

from services.llm.interface import LLMProvider

logger = logging.getLogger("llm.factory")

# Module-level singleton — caches the BASE provider (expensive client).
# TrackedProvider is a lightweight wrapper created at call time when needed.
_cached_provider: LLMProvider | None = None
_cached_provider_name: str | None = None


def get_llm_provider() -> LLMProvider:
    """Return a configured LLM provider based on LLM_PROVIDER env var.

    Supported values:
        "mock"   — Deterministic responses, no network (default)
        "openai" — OpenAI API (requires LLM_API_KEY)
        "grok"   — xAI Grok API (requires LLM_API_KEY)
        "kimi"   — Moonshot Kimi K2.5 API (requires LLM_API_KEY)
        "local"  — Local Ollama/vLLM (no API key needed)
        "ollama" — Alias for local Ollama (no API key needed)

    The base provider is cached as a module-level singleton. When called inside
    a ClawX ``@observe`` context, the base is transparently wrapped in
    ``TrackedProvider`` so token counts flow into the active ``MetricsCollector``.
    Outside ``@observe``, the raw cached base is returned with zero overhead.

    To force re-creation (e.g. after env var change in tests), call
    ``reset_llm_provider()``.
    """
    global _cached_provider, _cached_provider_name

    provider_name = os.environ.get("LLM_PROVIDER", "mock").lower()

    # Build or reuse the cached base provider.
    if _cached_provider is None or _cached_provider_name != provider_name:
        if provider_name == "mock":
            from services.llm.mock import MockLLMProvider
            _cached_provider = MockLLMProvider()
        elif provider_name in ("openai", "grok", "kimi", "local", "ollama"):
            from services.llm.openai_compatible import OpenAICompatibleProvider
            _cached_provider = OpenAICompatibleProvider(provider_name)
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER='{provider_name}'. "
                f"Valid options: mock, openai, grok, kimi, local, ollama"
            )
        _cached_provider_name = provider_name
        logger.info("LLM provider selected: %s", provider_name)

    # --- ClawX token tracking (v2.0) ---
    # If we're inside an @observe context, wrap the base in TrackedProvider so
    # every generate() call automatically updates the active MetricsCollector.
    # Outside @observe, return the raw base — zero allocation, zero overhead.
    try:
        from clawx.metrics import get_current_collector
        if get_current_collector() is not None:
            from services.llm.tracked_provider import TrackedProvider
            return TrackedProvider(_cached_provider)
    except ImportError:
        pass  # clawx not on PYTHONPATH — continue without tracking

    return _cached_provider


def reset_llm_provider() -> None:
    """Clear the cached provider. Used in tests to switch providers mid-run."""
    global _cached_provider, _cached_provider_name
    _cached_provider = None
    _cached_provider_name = None
