"""OpenAI-compatible LLM provider adapter.

Handles OpenAI, xAI Grok, and local inference (Ollama/vLLM) through a
single adapter — all three expose the OpenAI chat completions API format.

Constitutional references:
  - CLAUDE.md Security Baseline: "No hardcoded secrets anywhere" —
    API keys come exclusively from environment variables.
  - lessons.md Rule #2: "Fail Fast on Missing Configuration" —
    raises ValueError if API key is missing for non-local providers.
  - lessons.md External API Rate Limits: "Never retry at fixed interval" —
    max_retries=1 to prevent thundering herd; exponential backoff is the
    caller's responsibility.
"""

import logging
import os

from openai import AsyncOpenAI

from services.llm.interface import LLMProvider

logger = logging.getLogger("llm.openai_compat")

# Provider-specific defaults — base_url + model
_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-3-mini-fast",
    },
    "local": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
}


class OpenAICompatibleProvider(LLMProvider):
    """Adapter for any OpenAI-compatible chat completions API."""

    def __init__(self, provider_name: str = "openai") -> None:
        defaults = _DEFAULTS.get(provider_name, _DEFAULTS["openai"])

        api_key = os.environ.get("LLM_API_KEY", "")
        if not api_key and provider_name != "local":
            raise ValueError(
                f"LLM_API_KEY environment variable required for provider '{provider_name}'. "
                f"See lessons.md Rule #2: Fail Fast on Missing Configuration."
            )

        self._default_model = os.environ.get("LLM_MODEL", defaults["model"])
        base_url = os.environ.get("LLM_BASE_URL", defaults["base_url"])

        self._client = AsyncOpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=30.0,
            max_retries=1,
        )
        logger.info(
            "LLM provider initialized: %s (base=%s, model=%s)",
            provider_name, base_url, self._default_model,
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str | None:
        try:
            kwargs: dict = {
                "model": model or self._default_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return None
