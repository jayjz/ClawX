"""LLM provider factory.

Reads LLM_PROVIDER env var and returns the appropriate provider instance.
Defaults to "mock" for safe test/CI operation — no API keys needed.

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

# Module-level singleton to avoid re-creating clients per call
_cached_provider: LLMProvider | None = None
_cached_provider_name: str | None = None


def get_llm_provider() -> LLMProvider:
    """Return a configured LLM provider based on LLM_PROVIDER env var.

    Supported values:
        "mock"   — Deterministic responses, no network (default)
        "openai" — OpenAI API (requires LLM_API_KEY)
        "grok"   — xAI Grok API (requires LLM_API_KEY)
        "local"  — Local Ollama/vLLM (no API key needed)

    The provider is cached as a module-level singleton. To force re-creation
    (e.g. after env var change in tests), call reset_llm_provider().
    """
    global _cached_provider, _cached_provider_name

    provider_name = os.environ.get("LLM_PROVIDER", "mock").lower()

    # Return cached if provider hasn't changed
    if _cached_provider is not None and _cached_provider_name == provider_name:
        return _cached_provider

    if provider_name == "mock":
        from services.llm.mock import MockLLMProvider
        _cached_provider = MockLLMProvider()
    elif provider_name in ("openai", "grok", "local"):
        from services.llm.openai_compatible import OpenAICompatibleProvider
        _cached_provider = OpenAICompatibleProvider(provider_name)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider_name}'. "
            f"Valid options: mock, openai, grok, local"
        )

    _cached_provider_name = provider_name
    logger.info("LLM provider selected: %s", provider_name)
    return _cached_provider


def reset_llm_provider() -> None:
    """Clear the cached provider. Used in tests to switch providers mid-run."""
    global _cached_provider, _cached_provider_name
    _cached_provider = None
    _cached_provider_name = None
