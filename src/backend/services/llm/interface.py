"""Abstract interface for LLM providers.

Every provider (OpenAI, Grok, local Ollama, mock) must implement this.
The interface is intentionally minimal — a single async method that takes
a list of message dicts and returns a string.

Constitutional references:
  - CLAUDE.md Invariant #6: "Continuous real-time, not turn-based" —
    all providers must be async to avoid blocking the arena event loop.
  - CLAUDE.md Security Baseline: "No eval/exec anywhere near agent input" —
    providers must never execute content from LLM responses.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM text generation backends."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str | None:
        """Send a chat completion request and return the response text.

        Args:
            messages: OpenAI-format message list [{"role": ..., "content": ...}].
            model: Override the default model for this call.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            response_format: Optional format constraint (e.g. {"type": "json_object"}).

        Returns:
            The generated text content, or None if the call fails.
        """
        ...

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

        Default implementation delegates to generate() and returns 0 for both
        token counts. Real providers (OpenAICompatibleProvider) override this to
        surface actual usage from the API response object.

        Args:
            messages: OpenAI-format message list.
            model: Override default model.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
            response_format: Optional format constraint.

        Returns:
            Tuple of (content, prompt_tokens, completion_tokens). Token counts
            are 0 for providers that do not override this method (e.g. mock).
        """
        content = await self.generate(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        return content, 0, 0
