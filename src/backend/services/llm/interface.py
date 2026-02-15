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
