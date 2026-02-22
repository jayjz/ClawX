"""Tests for v2.2 Progressive Entropy — Ruthless Arena.

Validates:
  - Idle streak counting from ledger entries
  - Progressive fee calculation (base + penalty tiers + cap)
  - LLM strategy prompt and mock response
  - RESEARCH bounty increase to 25.00c
  - Research deadline shortened to 5 minutes
"""

import json
import os
import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

# Path fixup for test runner
import sys
from pathlib import Path
_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)


class TestCalculateEntropyFee:
    """Test the progressive entropy fee calculation."""

    def test_zero_idle_returns_base(self):
        from bot_runner import calculate_entropy_fee, ENTROPY_BASE
        assert calculate_entropy_fee(0) == ENTROPY_BASE
        assert calculate_entropy_fee(0) == Decimal('2.00')

    def test_under_interval_returns_base(self):
        from bot_runner import calculate_entropy_fee, ENTROPY_BASE
        for i in range(1, 5):
            assert calculate_entropy_fee(i) == ENTROPY_BASE

    def test_one_penalty_tier(self):
        from bot_runner import calculate_entropy_fee
        # base 2.00 + 1 tier * 0.50 = 2.50
        assert calculate_entropy_fee(5) == Decimal('2.50')
        assert calculate_entropy_fee(6) == Decimal('2.50')
        assert calculate_entropy_fee(9) == Decimal('2.50')

    def test_two_penalty_tiers(self):
        from bot_runner import calculate_entropy_fee
        # base 2.00 + 2 tiers * 0.50 = 3.00
        assert calculate_entropy_fee(10) == Decimal('3.00')
        assert calculate_entropy_fee(14) == Decimal('3.00')

    def test_three_penalty_tiers(self):
        from bot_runner import calculate_entropy_fee
        # base 2.00 + 3 tiers * 0.50 = 3.50
        assert calculate_entropy_fee(15) == Decimal('3.50')

    def test_fee_capped_at_max(self):
        from bot_runner import calculate_entropy_fee, MAX_ENTROPY_FEE
        # 100 idle ticks = 20 tiers * 0.50 = 10.00 + 2.00 = 12.00 -> capped at 5.00
        assert calculate_entropy_fee(100) == MAX_ENTROPY_FEE
        assert calculate_entropy_fee(100) == Decimal('5.00')

    def test_large_idle_still_capped(self):
        from bot_runner import calculate_entropy_fee, MAX_ENTROPY_FEE
        assert calculate_entropy_fee(1000) == MAX_ENTROPY_FEE


class TestResearchBountyAndDeadline:
    """Test that RESEARCH market parameters were updated for v2.1."""

    def test_research_bounty_is_25(self):
        from services.market_maker import RESEARCH_BOUNTY
        assert RESEARCH_BOUNTY == Decimal('25.00')

    def test_research_deadline_is_5_minutes(self):
        from services.market_maker import RESEARCH_DEADLINE_MINUTES
        assert RESEARCH_DEADLINE_MINUTES == 5


class TestMockStrategyResponse:
    """Test the mock LLM strategy response."""

    @pytest.mark.asyncio
    async def test_mock_returns_research_when_available(self):
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[
                {"role": "system", "content": "strategy"},
                {"role": "user", "content": (
                    "Idle Streak: 5 ticks\n"
                    "Available RESEARCH markets: 3\n"
                    "Available PORTFOLIO markets: 2\n"
                )},
            ],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "RESEARCH"
        assert "research" in parsed["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_mock_returns_portfolio_when_no_research(self):
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        result = await provider.generate(
            messages=[
                {"role": "system", "content": "strategy"},
                {"role": "user", "content": (
                    "Idle Streak: 5 ticks\n"
                    "Available RESEARCH markets: 0\n"
                    "Available PORTFOLIO markets: 5\n"
                )},
            ],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "PORTFOLIO"

    @pytest.mark.asyncio
    async def test_mock_strategy_valid_actions_only(self):
        from services.llm.mock import MockLLMProvider
        provider = MockLLMProvider()
        # Test with no markets — should return WAGER or WAIT
        result = await provider.generate(
            messages=[
                {"role": "system", "content": "strategy"},
                {"role": "user", "content": (
                    "Idle Streak: 10 ticks\n"
                    "Available RESEARCH markets: 0\n"
                    "Available PORTFOLIO markets: 0\n"
                )},
            ],
            response_format={"type": "json_object"},
        )
        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] in ("RESEARCH", "PORTFOLIO", "WAGER", "WAIT")


class TestTickStrategyFunction:
    """Test the generate_tick_strategy() LLM client function."""

    @pytest.mark.asyncio
    async def test_strategy_returns_valid_action(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            from services.llm.factory import reset_llm_provider
            reset_llm_provider()
            from llm_client import generate_tick_strategy
            result = await generate_tick_strategy(
                persona="Test bot",
                balance=500.0,
                idle_streak=10,
                entropy_fee=1.0,
                research_markets=2,
                portfolio_markets=3,
            )
            assert result is not None
            assert result["action"] in ("RESEARCH", "PORTFOLIO", "WAGER", "WAIT")
            assert "reasoning" in result
            reset_llm_provider()

    @pytest.mark.asyncio
    async def test_strategy_returns_none_on_failure(self):
        """If LLM provider fails, strategy returns None (fallback to priority chain)."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            from services.llm.factory import reset_llm_provider
            reset_llm_provider()
            from llm_client import generate_tick_strategy

            # Patch the provider to return None (simulate failure)
            with patch("llm_client.get_llm_provider") as mock_provider:
                provider_instance = AsyncMock()
                provider_instance.generate.return_value = None
                mock_provider.return_value = provider_instance

                result = await generate_tick_strategy(
                    persona="Test bot",
                    balance=500.0,
                    idle_streak=5,
                    entropy_fee=0.75,
                    research_markets=1,
                    portfolio_markets=0,
                )
                assert result is None
            reset_llm_provider()


class TestProgressiveConstants:
    """Test that v2.1 constants are correctly defined."""

    def test_entropy_base(self):
        from bot_runner import ENTROPY_BASE
        assert ENTROPY_BASE == Decimal('2.00')

    def test_entropy_idle_penalty(self):
        from bot_runner import ENTROPY_IDLE_PENALTY
        assert ENTROPY_IDLE_PENALTY == Decimal('0.50')

    def test_idle_penalty_interval(self):
        from bot_runner import IDLE_PENALTY_INTERVAL
        assert IDLE_PENALTY_INTERVAL == 5

    def test_max_entropy_fee(self):
        from bot_runner import MAX_ENTROPY_FEE
        assert MAX_ENTROPY_FEE == Decimal('5.00')

    def test_backward_compat_alias(self):
        from bot_runner import ENTROPY_FEE, ENTROPY_BASE
        assert ENTROPY_FEE == ENTROPY_BASE
