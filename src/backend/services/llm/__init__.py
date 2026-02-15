"""LLM provider abstraction layer.

Exposes a single entry point: get_llm_provider() via the factory.
All callers should use this instead of importing providers directly.
"""

from services.llm.factory import get_llm_provider
from services.llm.interface import LLMProvider

__all__ = ["get_llm_provider", "LLMProvider"]
