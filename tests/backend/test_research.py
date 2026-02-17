"""Tests for v1.7 Proof-of-Retrieval — RESEARCH market instant resolution.

Proves:
  1. Correct answer → market RESOLVED, RESEARCH_PAYOUT in ledger
  2. Wrong answer → market stays OPEN, prediction = LOSS
  3. Already RESOLVED market → "CLOSED" result
  4. generate_research_answer returns valid JSON
  5. Mock LLM research mode returns deterministic answer
  6. execute_tick with RESEARCH market → attempts research
  7. Max 1 research attempt per tick enforced
  8. Entropy fee still charged after research attempt

Constitutional references:
  - CLAUDE.md Invariant #2: Write or Die — every research attempt produces ledger entries
  - CLAUDE.md Invariant #3: Decimal Purity — bounty and stake use Decimal
  - CLAUDE.md Invariant #4: External Truth — SHA256 hash verification
"""

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from models import (
    Base, Bot, Ledger, Market, MarketPrediction,
    MarketSourceType, MarketStatus, PredictionStatus,
)
from services.ledger_service import append_ledger_entry, get_balance
from services.market_service import submit_research_answer


# ============================================================================
# Fixtures
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
    """Create a bot with 1000c GRANT."""
    import secrets
    import bcrypt

    raw_key = secrets.token_hex(16)
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    bot = Bot(
        handle="ResearchBot",
        persona_yaml="Knowledge retrieval test agent",
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
async def research_market(session):
    """Create an OPEN RESEARCH market with known answer hash."""
    answer = "12345"
    answer_hash = hashlib.sha256(answer.encode()).hexdigest()

    market = Market(
        id=uuid.uuid4(),
        description="RESEARCH: What is the Wikipedia page ID for the article titled 'Test Article'?",
        source_type=MarketSourceType.RESEARCH,
        resolution_criteria={
            "answer_hash": answer_hash,
            "match_type": "exact_string",
        },
        bounty=Decimal("15.00"),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    session.add(market)
    await session.flush()
    await session.commit()
    return market, answer


def _mock_session(session):
    """Create a mock async context manager that yields the given session."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=session)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


# ============================================================================
# Test 1: Correct answer resolves market and pays bounty
# ============================================================================

class TestCorrectAnswer:
    @pytest.mark.asyncio
    async def test_correct_answer_resolves_and_pays(self, session, bot_with_grant, research_market):
        """Correct SHA256 match → RESOLVED, WIN, RESEARCH_PAYOUT in ledger."""
        from sqlalchemy import select

        bot = bot_with_grant
        market, correct_answer = research_market

        pred, result = await submit_research_answer(
            bot_id=bot.id,
            market_id=str(market.id),
            answer=correct_answer,
            stake=Decimal("1.00"),
            tick_id="test-tick-1",
            session=session,
        )
        await session.commit()

        assert result == "CORRECT"
        assert pred is not None
        assert pred.status == PredictionStatus.WIN
        assert pred.payout == Decimal("16.00")  # 15 bounty + 1 stake

        # Market should be RESOLVED
        res = await session.execute(select(Market).where(Market.id == market.id))
        updated_market = res.scalar_one()
        assert updated_market.status == MarketStatus.RESOLVED

        # Ledger should have MARKET_STAKE (-1) and RESEARCH_PAYOUT (+16)
        res = await session.execute(
            select(Ledger).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_PAYOUT",
            )
        )
        payout_entry = res.scalar_one()
        assert Decimal(str(payout_entry.amount)) == Decimal("16.00")

        # Net balance: 1000 - 1 + 16 = 1015
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("1015")


# ============================================================================
# Test 2: Wrong answer → LOSS, market stays OPEN
# ============================================================================

class TestWrongAnswer:
    @pytest.mark.asyncio
    async def test_wrong_answer_loss_market_open(self, session, bot_with_grant, research_market):
        """Wrong hash → WRONG, prediction LOSS, market stays OPEN."""
        from sqlalchemy import select

        bot = bot_with_grant
        market, _ = research_market

        pred, result = await submit_research_answer(
            bot_id=bot.id,
            market_id=str(market.id),
            answer="99999",  # wrong answer
            stake=Decimal("1.00"),
            tick_id="test-tick-2",
            session=session,
        )
        await session.commit()

        assert result == "WRONG"
        assert pred is not None
        assert pred.status == PredictionStatus.LOSS

        # Market should still be OPEN
        res = await session.execute(select(Market).where(Market.id == market.id))
        updated_market = res.scalar_one()
        assert updated_market.status == MarketStatus.OPEN

        # Balance: 1000 - 1 = 999 (stake lost)
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("999")


# ============================================================================
# Test 3: Already RESOLVED market → "CLOSED"
# ============================================================================

class TestAlreadyResolved:
    @pytest.mark.asyncio
    async def test_resolved_market_returns_closed(self, session, bot_with_grant, research_market):
        """Submitting to an already RESOLVED market returns CLOSED, no prediction."""
        bot = bot_with_grant
        market, correct_answer = research_market

        # First: resolve it
        pred1, result1 = await submit_research_answer(
            bot_id=bot.id,
            market_id=str(market.id),
            answer=correct_answer,
            stake=Decimal("1.00"),
            tick_id="test-tick-3a",
            session=session,
        )
        await session.commit()
        assert result1 == "CORRECT"

        # Second: try again on resolved market
        pred2, result2 = await submit_research_answer(
            bot_id=bot.id,
            market_id=str(market.id),
            answer=correct_answer,
            stake=Decimal("1.00"),
            tick_id="test-tick-3b",
            session=session,
        )
        assert result2 == "CLOSED"
        assert pred2 is None


# ============================================================================
# Test 4: generate_research_answer returns valid JSON
# ============================================================================

class TestResearchLLMClient:
    @pytest.mark.asyncio
    async def test_generate_research_answer_valid(self):
        """generate_research_answer returns {answer, confidence} dict."""
        import json
        from llm_client import generate_research_answer

        with patch("llm_client.get_llm_provider") as mock_prov:
            mock_prov.return_value.generate = AsyncMock(return_value=json.dumps({
                "answer": "42",
                "confidence": 0.85,
            }))

            result = await generate_research_answer(
                persona="Test agent",
                question="What is the answer?",
                balance=1000.0,
            )

        assert result is not None
        assert result["answer"] == "42"
        assert result["confidence"] == 0.85


# ============================================================================
# Test 5: Mock LLM research mode
# ============================================================================

class TestMockLLMResearch:
    @pytest.mark.asyncio
    async def test_mock_research_response(self):
        """MockLLMProvider detects research prompts and returns answer + confidence."""
        from services.llm.mock import MockLLMProvider

        provider = MockLLMProvider()
        response = await provider.generate(
            messages=[
                {"role": "system", "content": "Knowledge retrieval agent"},
                {"role": "user", "content": "Research Question: What is the Wikipedia page ID for 'Test'?"},
            ],
            response_format={"type": "json_object"},
        )

        import json
        parsed = json.loads(response)
        assert "answer" in parsed
        assert "confidence" in parsed
        assert isinstance(parsed["confidence"], float)
        assert parsed["confidence"] > 0


# ============================================================================
# Test 6: execute_tick with RESEARCH market attempts research
# ============================================================================

class TestTickResearch:
    @pytest.mark.asyncio
    async def test_tick_attempts_research(self, session, bot_with_grant, research_market):
        """execute_tick sees a RESEARCH market and calls submit_research_answer."""
        from sqlalchemy import select, func

        bot = bot_with_grant
        market, correct_answer = research_market

        market_dicts = [{
            "id": str(market.id),
            "description": market.description,
            "source_type": "RESEARCH",
            "resolution_criteria": market.resolution_criteria,
            "bounty": str(market.bounty),
            "deadline": market.deadline.isoformat(),
        }]

        mock_answer = {"answer": correct_answer, "confidence": 0.90}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_research_with_tool", new_callable=AsyncMock, return_value=mock_answer), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "RESEARCH"

        # Should have MARKET_STAKE + RESEARCH_PAYOUT + HEARTBEAT entries
        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_PAYOUT",
            )
        )
        assert result.scalar() == 1

        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "HEARTBEAT",
            )
        )
        assert result.scalar() == 1


# ============================================================================
# Test 7: Max 1 research attempt per tick
# ============================================================================

class TestMaxOneResearch:
    @pytest.mark.asyncio
    async def test_max_one_research_per_tick(self, session, bot_with_grant):
        """Two RESEARCH markets in same tick → only 1 attempt made."""
        from sqlalchemy import select, func

        bot = bot_with_grant

        # Create 2 research markets
        markets_data = []
        for i in range(2):
            answer = str(10000 + i)
            ahash = hashlib.sha256(answer.encode()).hexdigest()
            m = Market(
                id=uuid.uuid4(),
                description=f"RESEARCH: What is the page ID for 'Article {i}'?",
                source_type=MarketSourceType.RESEARCH,
                resolution_criteria={"answer_hash": ahash, "match_type": "exact_string"},
                bounty=Decimal("15.00"),
                deadline=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            session.add(m)
            markets_data.append({
                "id": str(m.id),
                "description": m.description,
                "source_type": "RESEARCH",
                "resolution_criteria": m.resolution_criteria,
                "bounty": str(m.bounty),
                "deadline": m.deadline.isoformat(),
            })
        await session.flush()
        await session.commit()

        # Mock: only first answer is correct
        call_count = 0

        async def mock_gen_research(persona, question, balance):
            nonlocal call_count
            call_count += 1
            return {"answer": "10000", "confidence": 0.80}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=markets_data), \
             patch("bot_runner.generate_research_with_tool", side_effect=mock_gen_research), \
             patch("bot_runner.generate_portfolio_decision", new_callable=AsyncMock, return_value=[]), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        # Only 1 research LLM call should have been made
        assert call_count == 1

        # Only 1 MARKET_STAKE entry (the research attempt, portfolio returned empty)
        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "MARKET_STAKE",
            )
        )
        assert result.scalar() == 1


# ============================================================================
# Test 8: Entropy fee charged after research
# ============================================================================

class TestEntropyAfterResearch:
    @pytest.mark.asyncio
    async def test_entropy_fee_charged_after_research(self, session, bot_with_grant, research_market):
        """After research attempt, HEARTBEAT entropy fee is still charged."""
        from sqlalchemy import select

        bot = bot_with_grant
        market, correct_answer = research_market

        market_dicts = [{
            "id": str(market.id),
            "description": market.description,
            "source_type": "RESEARCH",
            "resolution_criteria": market.resolution_criteria,
            "bounty": str(market.bounty),
            "deadline": market.deadline.isoformat(),
        }]

        mock_answer = {"answer": correct_answer, "confidence": 0.90}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_research_with_tool", new_callable=AsyncMock, return_value=mock_answer), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        result = await session.execute(
            select(Ledger).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "HEARTBEAT",
            )
        )
        hb = result.scalar_one()
        assert Decimal(str(hb.amount)) == -ENTROPY_FEE

        # Final balance: 1000 - 1 (stake) + 16 (payout) - 0.50 (entropy) = 1014.50
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("1014.5")
