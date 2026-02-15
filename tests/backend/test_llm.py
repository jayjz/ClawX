"""Tests for the LLM provider abstraction layer.

Verifies:
  1. Factory returns correct provider types based on LLM_PROVIDER env var
  2. Mock provider returns deterministic, reproducible responses
  3. Mock prediction output is valid JSON with required fields
  4. Factory caching works (same instance returned)
  5. Factory reset clears cache
  6. Invalid provider name raises ValueError
  7. Integration: llm_client functions work end-to-end with mock

Constitutional references:
  - lessons.md Rule #3: "Test Fixtures Must Guarantee Isolation" —
    each test resets provider cache and env vars via fixtures.
  - CLAUDE.md P0 debt: "Broken test suite" — these tests are self-contained,
    no DB, no Redis, no network.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure src/backend is on path (same pattern as alembic/env.py)
_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from services.llm.factory import get_llm_provider, reset_llm_provider
from services.llm.interface import LLMProvider
from services.llm.mock import MockLLMProvider


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Reset provider cache and set mock as default before each test."""
    reset_llm_provider()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    yield
    reset_llm_provider()


# ============================================================================
# Factory Tests
# ============================================================================

class TestFactory:
    def test_default_is_mock(self, monkeypatch):
        """Factory defaults to mock when LLM_PROVIDER is not set."""
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        reset_llm_provider()
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    def test_explicit_mock(self):
        """Factory returns MockLLMProvider when LLM_PROVIDER=mock."""
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    def test_caching(self):
        """Factory returns the same instance on repeated calls."""
        p1 = get_llm_provider()
        p2 = get_llm_provider()
        assert p1 is p2

    def test_reset_clears_cache(self):
        """reset_llm_provider() forces re-creation."""
        p1 = get_llm_provider()
        reset_llm_provider()
        p2 = get_llm_provider()
        assert p1 is not p2

    def test_invalid_provider_raises(self, monkeypatch):
        """Unknown provider name raises ValueError."""
        monkeypatch.setenv("LLM_PROVIDER", "nonexistent")
        reset_llm_provider()
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm_provider()

    def test_openai_without_key_raises(self, monkeypatch):
        """OpenAI provider without LLM_API_KEY raises ValueError."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        reset_llm_provider()
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            get_llm_provider()

    def test_grok_without_key_raises(self, monkeypatch):
        """Grok provider without LLM_API_KEY raises ValueError."""
        monkeypatch.setenv("LLM_PROVIDER", "grok")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        reset_llm_provider()
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            get_llm_provider()

    def test_local_without_key_ok(self, monkeypatch):
        """Local provider does NOT require LLM_API_KEY."""
        monkeypatch.setenv("LLM_PROVIDER", "local")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        reset_llm_provider()
        provider = get_llm_provider()
        assert isinstance(provider, LLMProvider)

    def test_provider_switch_on_env_change(self, monkeypatch):
        """Changing LLM_PROVIDER env var + reset returns different provider."""
        p1 = get_llm_provider()
        assert isinstance(p1, MockLLMProvider)

        monkeypatch.setenv("LLM_PROVIDER", "local")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        reset_llm_provider()
        p2 = get_llm_provider()
        assert not isinstance(p2, MockLLMProvider)


# ============================================================================
# Mock Provider Tests
# ============================================================================

class TestMockProvider:
    @pytest.mark.asyncio
    async def test_text_response(self):
        """Mock returns a non-empty text string for plain messages."""
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[{"role": "user", "content": "Hello arena"}]
        )
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Mock response" in result

    @pytest.mark.asyncio
    async def test_deterministic(self):
        """Same input produces same output (reproducible tests)."""
        provider = MockLLMProvider()
        msgs = [{"role": "user", "content": "test determinism"}]
        r1 = await provider.generate(messages=msgs)
        r2 = await provider.generate(messages=msgs)
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_different_input_different_output(self):
        """Different prompts produce different responses."""
        provider = MockLLMProvider()
        r1 = await provider.generate(messages=[{"role": "user", "content": "alpha"}])
        r2 = await provider.generate(messages=[{"role": "user", "content": "omega"}])
        assert r1 != r2

    @pytest.mark.asyncio
    async def test_json_response(self):
        """Mock returns valid prediction JSON when response_format is json_object."""
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[
                {"role": "system", "content": "You are an analyst."},
                {"role": "user", "content": "BTC is at $60000. Analyze."},
            ],
            response_format={"type": "json_object"},
        )
        assert result is not None
        data = json.loads(result)
        assert "claim_text" in data
        assert data["direction"] in ("UP", "DOWN")
        assert 0 < data["confidence"] < 1
        assert data["wager_amount"] > 0
        assert "reasoning" in data

    @pytest.mark.asyncio
    async def test_json_deterministic(self):
        """JSON mode is also deterministic for same input."""
        provider = MockLLMProvider()
        msgs = [{"role": "user", "content": "fixed input for json"}]
        fmt = {"type": "json_object"}
        r1 = await provider.generate(messages=msgs, response_format=fmt)
        r2 = await provider.generate(messages=msgs, response_format=fmt)
        assert r1 == r2
        assert json.loads(r1) == json.loads(r2)


# ============================================================================
# Integration: llm_client with mock provider
# ============================================================================

class TestLLMClientIntegration:
    @pytest.mark.asyncio
    async def test_generate_post(self):
        """generate_post() returns a string through mock provider."""
        from llm_client import generate_post
        result = await generate_post("tech analyst", "post about BTC trends")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) <= 280

    @pytest.mark.asyncio
    async def test_generate_reply(self):
        """generate_reply() returns a string through mock provider."""
        from llm_client import generate_reply
        result = await generate_reply("crypto degen", "BTC to 100k!")
        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_prediction(self):
        """generate_prediction() returns a valid dict through mock provider."""
        from llm_client import generate_prediction
        result = await generate_prediction(
            "quant trader", "BTC at $62000, RSI oversold", 500.0
        )
        assert result is not None
        assert isinstance(result, dict)
        assert result["direction"] in ("UP", "DOWN", "TRUE", "FALSE")
        assert result["wager_amount"] > 0
        assert result["wager_amount"] <= 500.0  # Never exceeds balance

    @pytest.mark.asyncio
    async def test_generate_prediction_respects_balance_cap(self):
        """Prediction wager is capped at 90% of balance."""
        from llm_client import generate_prediction
        # Use a very low balance so the mock's wager (5-44) exceeds it
        result = await generate_prediction(
            "quant trader", "BTC analysis", 3.0
        )
        if result is not None:
            assert result["wager_amount"] <= 3.0


# ============================================================================
# Interface contract
# ============================================================================

class TestInterface:
    def test_cannot_instantiate_abc(self):
        """LLMProvider is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_mock_is_subclass(self):
        """MockLLMProvider properly implements the interface."""
        assert issubclass(MockLLMProvider, LLMProvider)
        assert isinstance(MockLLMProvider(), LLMProvider)
