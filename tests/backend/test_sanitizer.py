"""Tests for LLM Output Sanitization Layer (LLMGuard)."""

import pytest

from src.backend.utils.sanitizer import LLMGuard


# ── clean_json ──────────────────────────────────────────────────────

class TestCleanJSON:
    """LLMGuard.clean_json should tolerate common LLM formatting issues."""

    def test_markdown_fenced_json_with_trailing_comma(self):
        raw = '```json\n{"action": "BUY",}\n```'
        result = LLMGuard.clean_json(raw)
        assert result is not None
        assert result == {"action": "BUY"}

    def test_plain_valid_json(self):
        raw = '{"direction": "UP", "confidence": 0.85}'
        result = LLMGuard.clean_json(raw)
        assert result == {"direction": "UP", "confidence": 0.85}

    def test_trailing_comma_in_array(self):
        raw = '{"tags": ["alpha", "beta",]}'
        result = LLMGuard.clean_json(raw)
        assert result == {"tags": ["alpha", "beta"]}

    def test_unquoted_keys(self):
        raw = '{action: "SELL", confidence: 0.7}'
        result = LLMGuard.clean_json(raw)
        assert result is not None
        assert result["action"] == "SELL"
        assert result["confidence"] == 0.7

    def test_empty_input_returns_none(self):
        assert LLMGuard.clean_json("") is None
        assert LLMGuard.clean_json("   ") is None

    def test_total_garbage_returns_none(self):
        assert LLMGuard.clean_json("I don't know what to say") is None

    def test_nested_code_fence(self):
        raw = '```JSON\n{"claim_text": "BTC > 100k", "wager_amount": 10.0,}\n```'
        result = LLMGuard.clean_json(raw)
        assert result is not None
        assert result["claim_text"] == "BTC > 100k"
        assert result["wager_amount"] == 10.0

    def test_non_dict_json_returns_none(self):
        raw = "[1, 2, 3]"
        assert LLMGuard.clean_json(raw) is None


# ── sanitize_thought ────────────────────────────────────────────────

class TestSanitizeThought:
    """LLMGuard.sanitize_thought should block refusals and truncate."""

    def test_refusal_blocked(self):
        raw = "As an AI language model, I cannot predict market movements."
        result = LLMGuard.sanitize_thought(raw)
        assert result is None

    def test_refusal_variant_sorry(self):
        raw = "Sorry, I can't provide financial advice."
        result = LLMGuard.sanitize_thought(raw)
        assert result is None

    def test_clean_text_passes(self):
        raw = "BTC looking bullish after the Fed meeting. Expecting a breakout."
        result = LLMGuard.sanitize_thought(raw)
        assert result == raw

    def test_truncation_at_280(self):
        raw = "A" * 500
        result = LLMGuard.sanitize_thought(raw)
        assert result is not None
        assert len(result) == 280
        assert result.endswith("\u2026")

    def test_empty_returns_none(self):
        assert LLMGuard.sanitize_thought("") is None
        assert LLMGuard.sanitize_thought("   ") is None

    def test_custom_max_length(self):
        raw = "Short but enforce limit"
        result = LLMGuard.sanitize_thought(raw, max_length=10)
        assert result is not None
        assert len(result) == 10


# ── is_refusal ──────────────────────────────────────────────────────

class TestIsRefusal:
    """Quick boolean refusal detection."""

    @pytest.mark.parametrize("text", [
        "As an AI, I cannot do that.",
        "I'm not able to provide predictions.",
        "Sorry but I cannot assist with that.",
        "I don't have real-time access to data.",
        "I am unable to make financial predictions.",
    ])
    def test_refusals_detected(self, text):
        assert LLMGuard.is_refusal(text) is True

    @pytest.mark.parametrize("text", [
        "BTC is pumping hard today!",
        "Bearish divergence on the 4H chart.",
        "",
    ])
    def test_non_refusals(self, text):
        assert LLMGuard.is_refusal(text) is False
