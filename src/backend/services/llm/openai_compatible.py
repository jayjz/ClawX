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
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5",
    },
    "local": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
}


class OpenAICompatibleProvider(LLMProvider):
    """Adapter for any OpenAI-compatible chat completions API."""

    def __init__(self, provider_name: str = "openai") -> None:
        defaults = _DEFAULTS.get(provider_name, _DEFAULTS["openai"])

        # Kimi uses MOONSHOT_API_KEY; all others use LLM_API_KEY
        if provider_name == "kimi":
            api_key = os.environ.get("MOONSHOT_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
        else:
            api_key = os.environ.get("LLM_API_KEY", "")

        if not api_key and provider_name not in ("local", "ollama"):
            raise ValueError(
                f"LLM_API_KEY environment variable required for provider '{provider_name}'. "
                f"See lessons.md Rule #2: Fail Fast on Missing Configuration."
            )

        self._provider_name = provider_name
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

    async def _create_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        max_tokens: int,
        temperature: float,
        response_format: dict | None,
    ):
        """Execute the chat completion request, handling the local-model fallback.

        Raises on unrecoverable failure — callers wrap in try/except.
        """
        kwargs: dict = {
            "model": model or self._default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            return await self._client.chat.completions.create(**kwargs)
        except Exception as fmt_exc:
            # Fallback: some local models don't support response_format.
            # Retry without it, injecting a JSON instruction into system prompt.
            if response_format and self._provider_name in ("local", "ollama"):
                logger.warning(
                    "response_format not supported by %s, retrying with prompt injection: %s",
                    self._provider_name, fmt_exc,
                )
                fallback_messages = list(messages)
                if fallback_messages and fallback_messages[0].get("role") == "system":
                    fallback_messages[0] = {
                        **fallback_messages[0],
                        "content": (
                            fallback_messages[0]["content"]
                            + "\n\nYou MUST respond with ONLY valid JSON. No markdown, no explanation."
                        ),
                    }
                kwargs.pop("response_format", None)
                kwargs["messages"] = fallback_messages
                return await self._client.chat.completions.create(**kwargs)
            raise

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
            response = await self._create_completion(
                messages, model, max_tokens, temperature, response_format
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return None

    async def generate_tracked(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> tuple[str | None, int, int]:
        """Like generate(), but also returns (content, prompt_tokens, completion_tokens).

        Extracts token counts from ``response.usage`` for real cost accounting.
        Returns (None, 0, 0) on any failure — never raises.
        """
        try:
            response = await self._create_completion(
                messages, model, max_tokens, temperature, response_format
            )
            content = response.choices[0].message.content
            usage = getattr(response, "usage", None)
            prompt_tokens: int = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens: int = getattr(usage, "completion_tokens", 0) or 0
            return content.strip() if content else None, prompt_tokens, completion_tokens
        except Exception as exc:
            logger.error("LLM generation (tracked) failed: %s", exc)
            return None, 0, 0
