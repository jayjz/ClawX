"""Tests for LLM provider factory routing and initialization.

Validates that all 6 provider types (mock, openai, grok, kimi, local, ollama)
route correctly through the factory and that API key requirements are enforced.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Path fixup for test runner
import sys
from pathlib import Path
_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)


class TestFactoryRouting:
    """Test that get_llm_provider() routes to the correct provider class."""

    def setup_method(self):
        from services.llm.factory import reset_llm_provider
        reset_llm_provider()

    def teardown_method(self):
        from services.llm.factory import reset_llm_provider
        reset_llm_provider()

    def test_mock_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LLM_PROVIDER", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "MockLLMProvider"

    def test_mock_explicit(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "MockLLMProvider"

    def test_openai_requires_api_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
            os.environ.pop("LLM_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            with pytest.raises(ValueError, match="LLM_API_KEY"):
                get_llm_provider()

    def test_openai_with_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_API_KEY": "sk-test"}):
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "OpenAICompatibleProvider"

    def test_grok_requires_api_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "grok"}, clear=False):
            os.environ.pop("LLM_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            with pytest.raises(ValueError, match="LLM_API_KEY"):
                get_llm_provider()

    def test_kimi_requires_api_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "kimi"}, clear=False):
            os.environ.pop("LLM_API_KEY", None)
            os.environ.pop("MOONSHOT_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            with pytest.raises(ValueError, match="LLM_API_KEY"):
                get_llm_provider()

    def test_kimi_with_moonshot_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "kimi", "MOONSHOT_API_KEY": "mk-test"}):
            os.environ.pop("LLM_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "OpenAICompatibleProvider"

    def test_kimi_with_llm_api_key_fallback(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "kimi", "LLM_API_KEY": "sk-fallback"}):
            os.environ.pop("MOONSHOT_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "OpenAICompatibleProvider"

    def test_local_no_key_required(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "local"}):
            os.environ.pop("LLM_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "OpenAICompatibleProvider"

    def test_ollama_no_key_required(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}):
            os.environ.pop("LLM_API_KEY", None)
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            provider = get_llm_provider()
            assert type(provider).__name__ == "OpenAICompatibleProvider"

    def test_unknown_provider_raises(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "nonexistent"}):
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
                get_llm_provider()

    def test_singleton_caching(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            p1 = get_llm_provider()
            p2 = get_llm_provider()
            assert p1 is p2

    def test_reset_clears_cache(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            from services.llm.factory import reset_llm_provider, get_llm_provider
            reset_llm_provider()
            p1 = get_llm_provider()
            reset_llm_provider()
            p2 = get_llm_provider()
            assert p1 is not p2


class TestProviderDefaults:
    """Test that provider defaults are correctly configured."""

    def test_kimi_defaults(self):
        from services.llm.openai_compatible import _DEFAULTS
        assert "kimi" in _DEFAULTS
        assert _DEFAULTS["kimi"]["base_url"] == "https://api.moonshot.cn/v1"
        assert _DEFAULTS["kimi"]["model"] == "kimi-k2.5"

    def test_ollama_defaults(self):
        from services.llm.openai_compatible import _DEFAULTS
        assert "ollama" in _DEFAULTS
        assert _DEFAULTS["ollama"]["base_url"] == "http://localhost:11434/v1"

    def test_all_providers_have_defaults(self):
        from services.llm.openai_compatible import _DEFAULTS
        expected = {"openai", "grok", "kimi", "local", "ollama"}
        assert expected.issubset(set(_DEFAULTS.keys()))


class TestMockPreserved:
    """Verify mock provider still works correctly (no regressions)."""

    @pytest.mark.asyncio
    async def test_mock_generates_text(self):
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[{"role": "user", "content": "hello"}]
        )
        assert result is not None
        assert "Mock response" in result

    @pytest.mark.asyncio
    async def test_mock_generates_json(self):
        import json
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[{"role": "user", "content": "predict"}],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert "claim_text" in parsed
        assert "direction" in parsed

    @pytest.mark.asyncio
    async def test_mock_research_mode(self):
        import json
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[{"role": "user", "content": "What is the Wikipedia page ID for..."}],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert "answer" in parsed
        assert "confidence" in parsed

    @pytest.mark.asyncio
    async def test_mock_portfolio_mode(self):
        import json
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[{"role": "user", "content": "Available Markets:\n- ID: 12345678-1234-1234-1234-123456789abc"}],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert "bets" in parsed
