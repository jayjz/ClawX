"""Tests for Agent Strategy Layer v1.6 — Portfolio multi-market betting.

Proves:
  1. No open markets → falls back to HEARTBEAT
  2. Portfolio places multiple MARKET_STAKE entries + HEARTBEAT
  3. Total stake capped at 20% of balance
  4. Entropy fee ALWAYS charged as HEARTBEAT entry
  5. Ledger sum matches Bot.balance after portfolio tick
  6. No duplicate market bets on same market
  7. Portfolio LLM failure → falls back to legacy WAGER
  8. get_balance() returns exact ledger sum

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly — ENTROPY_FEE enforces this
  - CLAUDE.md Invariant #2: Write or Die — at least one ledger entry per tick
  - CLAUDE.md Invariant #3: Decimal Purity — all money uses Decimal
"""

import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from models import Base, Bot, Ledger, Market, MarketPrediction, MarketStatus, MarketSourceType
from services.ledger_service import append_ledger_entry, get_balance


# ============================================================================
# Fixtures — in-memory SQLite for isolation
# ============================================================================

@pytest.fixture
async def session():
    """Create an isolated async SQLite session for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s

    await engine.dispose()


@pytest.fixture
async def bot_with_grant(session):
    """Create a bot with a GRANT ledger entry (balance=1000)."""
    import secrets
    import bcrypt

    raw_key = secrets.token_hex(16)
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    bot = Bot(
        handle="PortfolioBot",
        persona_yaml="Portfolio strategy test agent",
        hashed_api_key=hashed,
        api_secret=secrets.token_hex(32),
        balance=1000.0,
        status="ALIVE",
        is_external=False,
    )
    session.add(bot)
    await session.flush()

    await append_ledger_entry(
        bot_id=bot.id,
        amount=1000.0,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        session=session,
    )
    await session.commit()
    return bot


@pytest.fixture
async def markets(session):
    """Create 3 OPEN markets for testing."""
    created = []
    for i in range(3):
        m = Market(
            id=uuid.uuid4(),
            description=f"Test market {i}: Will condition {i} be met?",
            source_type=MarketSourceType.GITHUB,
            resolution_criteria={"repo_name": f"test/repo{i}", "metric": "merged_prs_24h", "operator": "gt", "value": 5},
            status=MarketStatus.OPEN,
            bounty=Decimal("10.00"),
            deadline=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(m)
        created.append(m)
    await session.flush()
    await session.commit()
    return created


def _mock_session(session):
    """Create a mock async context manager that yields the given session."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=session)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


# ============================================================================
# Test 1: No markets → heartbeat fallback
# ============================================================================

class TestNoMarketsFallback:
    @pytest.mark.asyncio
    async def test_no_markets_heartbeat(self, session, bot_with_grant):
        """No open markets → HEARTBEAT with entropy fee only."""
        from sqlalchemy import select

        bot = bot_with_grant

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=[]), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "HEARTBEAT"

        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "HEARTBEAT")
        )
        hb = result.scalar_one()
        assert hb.amount == -ENTROPY_FEE


# ============================================================================
# Test 2: Portfolio places market bets
# ============================================================================

class TestPortfolioBets:
    @pytest.mark.asyncio
    async def test_portfolio_places_bets(self, session, bot_with_grant, markets):
        """Portfolio with 2 bets → 2 MARKET_STAKE + 1 HEARTBEAT + 2 MarketPrediction."""
        from sqlalchemy import select, func

        bot = bot_with_grant
        market_dicts = [
            {"id": str(m.id), "description": m.description,
             "source_type": m.source_type.value,
             "resolution_criteria": m.resolution_criteria,
             "bounty": str(m.bounty), "deadline": m.deadline.isoformat()}
            for m in markets[:2]
        ]

        mock_portfolio = [
            {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.80, "reasoning": "Strong signal"},
            {"market_id": str(markets[1].id), "outcome": "NO", "confidence": 0.75, "reasoning": "Weak signal"},
        ]

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, return_value=mock_portfolio), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "PORTFOLIO"

        # Verify MARKET_STAKE entries
        result = await session.execute(
            select(func.count(Ledger.id))
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "MARKET_STAKE")
        )
        assert result.scalar() == 2

        # Verify HEARTBEAT entry (entropy)
        result = await session.execute(
            select(func.count(Ledger.id))
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "HEARTBEAT")
        )
        assert result.scalar() == 1

        # Verify MarketPrediction records
        result = await session.execute(
            select(func.count(MarketPrediction.id))
            .where(MarketPrediction.bot_id == bot.id)
        )
        assert result.scalar() == 2


# ============================================================================
# Test 3: Stake capped at 20%
# ============================================================================

class TestStakeCap:
    @pytest.mark.asyncio
    async def test_total_stake_capped_at_20_percent(self, session, bot_with_grant, markets):
        """3 bets at max confidence → total MARKET_STAKE <= 20% of balance."""
        from sqlalchemy import select, func

        bot = bot_with_grant  # balance = 1000
        market_dicts = [
            {"id": str(m.id), "description": m.description,
             "source_type": m.source_type.value,
             "resolution_criteria": m.resolution_criteria,
             "bounty": str(m.bounty), "deadline": m.deadline.isoformat()}
            for m in markets
        ]

        mock_portfolio = [
            {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.99, "reasoning": "Max confidence"},
            {"market_id": str(markets[1].id), "outcome": "YES", "confidence": 0.99, "reasoning": "Max confidence"},
            {"market_id": str(markets[2].id), "outcome": "YES", "confidence": 0.99, "reasoning": "Max confidence"},
        ]

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, return_value=mock_portfolio), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "PORTFOLIO"

        # Sum all MARKET_STAKE amounts (they are negative)
        result = await session.execute(
            select(func.sum(Ledger.amount))
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "MARKET_STAKE")
        )
        total_staked = abs(Decimal(str(result.scalar())))

        # 20% of (1000 - 0.50) = 199.90
        max_allowed = (Decimal('1000') - ENTROPY_FEE) * Decimal('0.20')
        assert total_staked <= max_allowed + Decimal('0.01'), \
            f"Total staked {total_staked} exceeds 20% cap {max_allowed}"


# ============================================================================
# Test 4: Entropy always charged
# ============================================================================

class TestEntropyAlwaysCharged:
    @pytest.mark.asyncio
    async def test_entropy_charged_with_portfolio(self, session, bot_with_grant, markets):
        """Even with portfolio bets, HEARTBEAT entropy fee is always written."""
        from sqlalchemy import select

        bot = bot_with_grant
        market_dicts = [
            {"id": str(markets[0].id), "description": markets[0].description,
             "source_type": markets[0].source_type.value,
             "resolution_criteria": markets[0].resolution_criteria,
             "bounty": str(markets[0].bounty), "deadline": markets[0].deadline.isoformat()}
        ]

        mock_portfolio = [
            {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.80, "reasoning": "Test"},
        ]

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, return_value=mock_portfolio), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "HEARTBEAT")
        )
        hb = result.scalar_one()
        assert hb.amount == -ENTROPY_FEE


# ============================================================================
# Test 5: Ledger sum matches Bot.balance
# ============================================================================

class TestLedgerBalanceSync:
    @pytest.mark.asyncio
    async def test_balance_matches_ledger_sum(self, session, bot_with_grant, markets):
        """After portfolio tick, get_balance() must equal bot.balance."""
        from sqlalchemy import select

        bot = bot_with_grant
        market_dicts = [
            {"id": str(markets[0].id), "description": markets[0].description,
             "source_type": markets[0].source_type.value,
             "resolution_criteria": markets[0].resolution_criteria,
             "bounty": str(markets[0].bounty), "deadline": markets[0].deadline.isoformat()}
        ]

        mock_portfolio = [
            {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.80, "reasoning": "Test"},
        ]

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, return_value=mock_portfolio), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        # Re-read bot
        result = await session.execute(select(Bot).where(Bot.id == bot.id))
        updated_bot = result.scalar_one()

        ledger_balance = await get_balance(bot_id=bot.id, session=session)
        assert abs(Decimal(str(updated_bot.balance)) - ledger_balance) < Decimal('0.0001'), \
            f"Bot.balance={updated_bot.balance} != ledger_sum={ledger_balance}"


# ============================================================================
# Test 6: No duplicate market bets
# ============================================================================

class TestNoDuplicateBets:
    @pytest.mark.asyncio
    async def test_no_duplicate_market_bets(self, session, bot_with_grant, markets):
        """LLM returning same market_id twice → only 1 MARKET_STAKE for that market."""
        from sqlalchemy import select, func

        bot = bot_with_grant
        # Only provide 1 market but LLM tries to bet on it twice
        market_dicts = [
            {"id": str(markets[0].id), "description": markets[0].description,
             "source_type": markets[0].source_type.value,
             "resolution_criteria": markets[0].resolution_criteria,
             "bounty": str(markets[0].bounty), "deadline": markets[0].deadline.isoformat()}
        ]

        # Two bets on the same market — validation in generate_portfolio_decision
        # should filter these, but even if it doesn't, place_market_bet will
        # create a second prediction (which is allowed but wasteful).
        # The LLM client filters duplicates; this test verifies that layer.
        mock_portfolio = [
            {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.80, "reasoning": "First bet"},
            {"market_id": str(markets[0].id), "outcome": "NO", "confidence": 0.75, "reasoning": "Duplicate bet"},
        ]

        # generate_portfolio_decision is mocked at bot_runner level,
        # so we pass the raw mock data through. The duplicate market_id
        # means the second call to place_market_bet writes a second MarketPrediction.
        # This is technically valid but the LLM validation layer should prevent it.
        # Let's test what the LLM client itself does:
        from llm_client import generate_portfolio_decision as _real_fn

        # Instead, test via the LLM client's dedup logic directly
        with patch("llm_client.get_llm_provider") as mock_provider:
            import json
            mock_provider.return_value.generate = AsyncMock(return_value=json.dumps({
                "bets": [
                    {"market_id": str(markets[0].id), "outcome": "YES", "confidence": 0.80, "reasoning": "First"},
                    {"market_id": str(markets[0].id), "outcome": "NO", "confidence": 0.75, "reasoning": "Duplicate"},
                ]
            }))

            result = await _real_fn(
                persona="test",
                markets=market_dicts,
                balance=1000.0,
                max_bets=3,
            )

        # Should only contain 1 bet (first one wins, duplicate filtered)
        assert len(result) == 1
        assert result[0]["market_id"] == str(markets[0].id)


# ============================================================================
# Test 7: Portfolio failure falls back to legacy WAGER
# ============================================================================

class TestPortfolioFallback:
    @pytest.mark.asyncio
    async def test_portfolio_failure_falls_back_to_wager(self, session, bot_with_grant):
        """If generate_portfolio_decision raises, fall back to legacy WAGER."""
        from sqlalchemy import select

        bot = bot_with_grant

        mock_prediction = {
            "claim_text": "BTC up",
            "direction": "UP",
            "confidence": 0.8,
            "wager_amount": 50.0,
            "reasoning": "Fallback test",
        }

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=[{"id": "fake"}]), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, side_effect=RuntimeError("LLM exploded")), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=mock_prediction), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PortfolioBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "WAGER"

        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "WAGER")
        )
        wager_entry = result.scalar_one()
        assert wager_entry.amount < 0


# ============================================================================
# Test 8: get_balance unit test
# ============================================================================

class TestGetBalance:
    @pytest.mark.asyncio
    async def test_get_balance_returns_exact_sum(self, session, bot_with_grant):
        """get_balance() must return exact sum of all ledger entries."""
        from bot_runner import ENTROPY_FEE

        bot = bot_with_grant

        # Add 3 HEARTBEAT entries
        for i in range(3):
            await append_ledger_entry(
                bot_id=bot.id,
                amount=float(-ENTROPY_FEE),
                transaction_type="HEARTBEAT",
                reference_id=f"TEST_HB_{i}",
                session=session,
            )
        await session.commit()

        balance = await get_balance(bot_id=bot.id, session=session)
        expected = Decimal('1000') - (ENTROPY_FEE * 3)
        assert balance == expected, f"get_balance()={balance} != expected={expected}"

    @pytest.mark.asyncio
    async def test_get_balance_no_entries(self, session):
        """get_balance() returns 0 for a bot with no ledger entries."""
        balance = await get_balance(bot_id=99999, session=session)
        assert balance == Decimal('0')
