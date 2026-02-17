"""Tests for v1.8/v1.8.1 Tool-Enabled Research — Wikipedia lookup for RESEARCH markets.

Proves:
  1. wikipedia_lookup returns valid pageid for known title
  2. wikipedia_lookup returns None for nonexistent title
  3. generate_research_with_tool uses tool when LLM confidence < 0.7
  4. generate_research_with_tool skips tool when LLM confidence >= 0.7
  5. Tool failure falls back to LLM answer
  6. execute_tick with tool-enabled research produces correct payout
  7. used_tool flag appears in response
  8. Title extraction regex works for various formats
  9. (v1.8.1) tool_fee_charged flag tracking
  10. (v1.8.1) wikipedia_lookup retry on 429/timeout
  11. (v1.8.1) execute_tick writes RESEARCH_LOOKUP_FEE on tool use

Constitutional references:
  - CLAUDE.md Invariant #2: Write or Die — tool use doesn't change ledger invariants
  - CLAUDE.md Invariant #3: Decimal Purity — payouts still use Decimal
  - CLAUDE.md: Additive only — existing v1.7 tests unaffected
"""

import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from models import (
    Base, Bot, Ledger, Market, MarketPrediction,
    MarketSourceType, MarketStatus, PredictionStatus,
)
from services.ledger_service import append_ledger_entry, get_balance


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
        handle="ToolResearchBot",
        persona_yaml="Tool-enabled research test agent",
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
    answer = "67890"
    answer_hash = hashlib.sha256(answer.encode()).hexdigest()

    market = Market(
        id=uuid.uuid4(),
        description="RESEARCH: What is the Wikipedia page ID for the article titled 'Python (programming language)'?",
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
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=session)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


# ============================================================================
# Test 1: wikipedia_lookup returns valid pageid for known title
# ============================================================================

class TestWikipediaLookupSuccess:
    @pytest.mark.asyncio
    async def test_lookup_returns_pageid(self):
        """wikipedia_lookup with a mocked response returns title + pageid."""
        from services.feed_ingestor import AsyncFeedIngestor

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Python (programming language)",
            "pageid": 23862,
            "extract": "Python is a programming language...",
        }

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Python (programming language)")

        assert result is not None
        assert result["pageid"] == 23862
        assert result["title"] == "Python (programming language)"


# ============================================================================
# Test 2: wikipedia_lookup returns None for nonexistent title
# ============================================================================

class TestWikipediaLookupNotFound:
    @pytest.mark.asyncio
    async def test_lookup_returns_none_on_404(self):
        """wikipedia_lookup returns None when article not found (404)."""
        from services.feed_ingestor import AsyncFeedIngestor

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Nonexistent Article XYZ123")

        assert result is None


# ============================================================================
# Test 3: generate_research_with_tool uses tool when LLM confidence < 0.7
# ============================================================================

class TestToolUsedOnLowConfidence:
    @pytest.mark.asyncio
    async def test_tool_called_when_llm_unsure(self):
        """LLM confidence 0.3 → tool called → pageid returned with confidence 0.95."""
        from llm_client import generate_research_with_tool

        # Mock LLM returning low confidence
        mock_llm_result = {"answer": "99999", "confidence": 0.3, "used_tool": False}

        # Mock Wikipedia lookup returning correct pageid
        mock_lookup = {"title": "Python (programming language)", "pageid": 67890, "extract": "..."}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_ingestor_cls:
            mock_ingestor = AsyncMock()
            mock_ingestor.wikipedia_lookup = AsyncMock(return_value=mock_lookup)
            mock_ingestor_cls.return_value = mock_ingestor

            result = await generate_research_with_tool(
                persona="Test agent",
                question="RESEARCH: What is the Wikipedia page ID for the article titled 'Python (programming language)'?",
                balance=1000.0,
            )

        assert result is not None
        assert result["answer"] == "67890"
        assert result["confidence"] == 0.95
        assert result["used_tool"] is True
        mock_ingestor.wikipedia_lookup.assert_called_once_with("Python (programming language)")


# ============================================================================
# Test 4: generate_research_with_tool skips tool when LLM confidence >= 0.7
# ============================================================================

class TestToolSkippedOnHighConfidence:
    @pytest.mark.asyncio
    async def test_tool_not_called_when_llm_confident(self):
        """LLM confidence 0.85 → tool NOT called → LLM answer used directly."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "42", "confidence": 0.85, "used_tool": False}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_ingestor_cls:
            mock_ingestor = AsyncMock()
            mock_ingestor_cls.return_value = mock_ingestor

            result = await generate_research_with_tool(
                persona="Test agent",
                question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=1000.0,
            )

        assert result is not None
        assert result["answer"] == "42"
        assert result["confidence"] == 0.85
        assert result["used_tool"] is False
        # Tool should NOT have been called
        mock_ingestor.wikipedia_lookup.assert_not_called()


# ============================================================================
# Test 5: Tool failure falls back to LLM answer
# ============================================================================

class TestToolFailureFallback:
    @pytest.mark.asyncio
    async def test_tool_failure_uses_llm_answer(self):
        """Tool returns None → falls back to LLM's low-confidence answer."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "99999", "confidence": 0.4, "used_tool": False}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_ingestor_cls:
            mock_ingestor = AsyncMock()
            mock_ingestor.wikipedia_lookup = AsyncMock(return_value=None)
            mock_ingestor_cls.return_value = mock_ingestor

            result = await generate_research_with_tool(
                persona="Test agent",
                question="RESEARCH: What is the Wikipedia page ID for the article titled 'Unknown'?",
                balance=1000.0,
            )

        assert result is not None
        assert result["answer"] == "99999"
        assert result["confidence"] == 0.4
        assert result["used_tool"] is False


# ============================================================================
# Test 6: execute_tick with tool-enabled research produces correct payout
# ============================================================================

class TestTickToolResearchPayout:
    @pytest.mark.asyncio
    async def test_tick_tool_research_correct_payout(self, session, bot_with_grant, research_market):
        """Tool-assisted correct answer → RESEARCH_PAYOUT in ledger."""
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

        # Tool-enabled answer with correct pageid
        mock_answer = {"answer": correct_answer, "confidence": 0.95, "used_tool": True}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_research_with_tool", new_callable=AsyncMock, return_value=mock_answer), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ToolResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "RESEARCH"

        # Verify RESEARCH_PAYOUT in ledger
        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_PAYOUT",
            )
        )
        assert result.scalar() == 1

        # Final balance: 1000 - 1 (stake) + 16 (payout) - 0.50 (entropy) = 1014.50
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("1014.5")


# ============================================================================
# Test 7: used_tool flag appears in response
# ============================================================================

class TestUsedToolFlag:
    @pytest.mark.asyncio
    async def test_used_tool_true_when_tool_used(self):
        """generate_research_with_tool sets used_tool=True when lookup succeeds."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "wrong", "confidence": 0.2, "used_tool": False}
        mock_lookup = {"title": "Test", "pageid": 12345, "extract": "..."}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_ingestor_cls:
            mock_ingestor = AsyncMock()
            mock_ingestor.wikipedia_lookup = AsyncMock(return_value=mock_lookup)
            mock_ingestor_cls.return_value = mock_ingestor

            result = await generate_research_with_tool(
                persona="Test",
                question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=500.0,
            )

        assert result["used_tool"] is True
        assert result["answer"] == "12345"

    @pytest.mark.asyncio
    async def test_used_tool_false_when_llm_confident(self):
        """generate_research_with_tool sets used_tool=False when LLM is confident."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "42", "confidence": 0.9, "used_tool": False}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result):
            result = await generate_research_with_tool(
                persona="Test",
                question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=500.0,
            )

        assert result["used_tool"] is False


# ============================================================================
# Test 8: Title extraction regex works for various formats
# ============================================================================

class TestTitleExtraction:
    def test_single_quotes(self):
        from llm_client import _extract_article_title
        title = _extract_article_title(
            "RESEARCH: What is the Wikipedia page ID for the article titled 'Python (programming language)'?"
        )
        assert title == "Python (programming language)"

    def test_double_quotes(self):
        from llm_client import _extract_article_title
        title = _extract_article_title(
            'RESEARCH: What is the Wikipedia page ID for the article titled "Albert Einstein"?'
        )
        assert title == "Albert Einstein"

    def test_no_match(self):
        from llm_client import _extract_article_title
        title = _extract_article_title(
            "What is the capital of France?"
        )
        assert title is None

    def test_special_characters(self):
        from llm_client import _extract_article_title
        title = _extract_article_title(
            "RESEARCH: What is the Wikipedia page ID for the article titled 'C++'?"
        )
        assert title == "C++"


# ============================================================================
# v1.8.1 Tests: Tool Fee Charged Flag
# ============================================================================

class TestToolFeeChargedFlag:
    @pytest.mark.asyncio
    async def test_tool_fee_charged_true_on_tool_success(self):
        """Successful tool lookup → tool_fee_charged=True."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "wrong", "confidence": 0.2, "used_tool": False}
        mock_lookup = {"title": "Test", "pageid": 12345, "extract": "..."}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_cls:
            mock_inst = AsyncMock()
            mock_inst.wikipedia_lookup = AsyncMock(return_value=mock_lookup)
            mock_cls.return_value = mock_inst

            result = await generate_research_with_tool(
                persona="Test", question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=500.0,
            )

        assert result["tool_fee_charged"] is True
        assert result["used_tool"] is True

    @pytest.mark.asyncio
    async def test_tool_fee_charged_false_when_llm_confident(self):
        """LLM confidence >= 0.7 → tool not called → tool_fee_charged=False."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "42", "confidence": 0.9, "used_tool": False}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result):
            result = await generate_research_with_tool(
                persona="Test", question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=500.0,
            )

        assert result["tool_fee_charged"] is False

    @pytest.mark.asyncio
    async def test_tool_fee_charged_false_on_tool_failure(self):
        """Tool returns None → falls back to LLM → tool_fee_charged=False."""
        from llm_client import generate_research_with_tool

        mock_llm_result = {"answer": "99999", "confidence": 0.4, "used_tool": False}

        with patch("llm_client.generate_research_answer", new_callable=AsyncMock, return_value=mock_llm_result), \
             patch("services.feed_ingestor.AsyncFeedIngestor") as mock_cls:
            mock_inst = AsyncMock()
            mock_inst.wikipedia_lookup = AsyncMock(return_value=None)
            mock_cls.return_value = mock_inst

            result = await generate_research_with_tool(
                persona="Test", question="RESEARCH: What is the Wikipedia page ID for the article titled 'Test'?",
                balance=500.0,
            )

        assert result["tool_fee_charged"] is False
        assert result["used_tool"] is False


# ============================================================================
# v1.8.1 Tests: Wikipedia Lookup Retry/Backoff
# ============================================================================

class TestWikipediaRetry:
    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """429 response triggers retry with backoff, succeeds on 2nd attempt."""
        from services.feed_ingestor import AsyncFeedIngestor

        resp_429 = MagicMock()
        resp_429.status_code = 429

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"title": "Test", "pageid": 111, "extract": "ok"}

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[resp_429, resp_ok])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Test", max_retries=3, base_backoff=0.01)

        assert result is not None
        assert result["pageid"] == 111
        mock_sleep.assert_called_once()  # slept once for 429

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Timeout triggers retry, succeeds on 2nd attempt."""
        from services.feed_ingestor import AsyncFeedIngestor

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"title": "Test", "pageid": 222, "extract": "ok"}

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[
                httpx.TimeoutException("timed out"),
                resp_ok,
            ])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Test", max_retries=3, base_backoff=0.01)

        assert result is not None
        assert result["pageid"] == 222

    @pytest.mark.asyncio
    async def test_exhausted_retries_returns_none(self):
        """All retries exhausted → returns None."""
        from services.feed_ingestor import AsyncFeedIngestor

        resp_429 = MagicMock()
        resp_429.status_code = 429

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_cls, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=resp_429)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Test", max_retries=2, base_backoff=0.01)

        assert result is None

    @pytest.mark.asyncio
    async def test_404_no_retry(self):
        """404 is definitive — no retry, immediate None."""
        from services.feed_ingestor import AsyncFeedIngestor

        resp_404 = MagicMock()
        resp_404.status_code = 404

        with patch("services.feed_ingestor.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=resp_404)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            ingestor = AsyncFeedIngestor()
            result = await ingestor.wikipedia_lookup("Nonexistent", max_retries=3, base_backoff=0.01)

        assert result is None
        assert mock_client.get.call_count == 1  # only 1 call, no retries


# ============================================================================
# v1.8.1 Tests: RESEARCH_LOOKUP_FEE Ledger Entry in execute_tick
# ============================================================================

class TestTickToolFee:
    @pytest.mark.asyncio
    async def test_tick_writes_lookup_fee_on_tool_use(self, session, bot_with_grant, research_market):
        """Tool-assisted research → RESEARCH_LOOKUP_FEE entry in ledger."""
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

        # Tool-enabled answer with correct pageid and tool_fee_charged=True
        mock_answer = {"answer": correct_answer, "confidence": 0.95, "used_tool": True, "tool_fee_charged": True}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_research_with_tool", new_callable=AsyncMock, return_value=mock_answer), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, TOOL_LOOKUP_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ToolResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "RESEARCH"

        # Verify RESEARCH_LOOKUP_FEE in ledger
        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_LOOKUP_FEE",
            )
        )
        assert result.scalar() == 1

        # Verify amount is -0.50
        result = await session.execute(
            select(Ledger).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_LOOKUP_FEE",
            )
        )
        fee_entry = result.scalar_one()
        assert Decimal(str(fee_entry.amount)) == -TOOL_LOOKUP_FEE

        # Final balance: 1000 - 1 (stake) - 0.50 (tool fee) + 16 (payout) - 0.50 (entropy) = 1014.00
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("1014.0")

    @pytest.mark.asyncio
    async def test_tick_no_lookup_fee_without_tool(self, session, bot_with_grant, research_market):
        """Research without tool → NO RESEARCH_LOOKUP_FEE entry."""
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

        # LLM-only answer — no tool used
        mock_answer = {"answer": correct_answer, "confidence": 0.85, "used_tool": False, "tool_fee_charged": False}

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_active_markets_for_agent", new_callable=AsyncMock, return_value=market_dicts), \
             patch("bot_runner.generate_research_with_tool", new_callable=AsyncMock, return_value=mock_answer), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "ToolResearchBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "RESEARCH"

        # No RESEARCH_LOOKUP_FEE
        result = await session.execute(
            select(func.count(Ledger.id)).where(
                Ledger.bot_id == bot.id,
                Ledger.transaction_type == "RESEARCH_LOOKUP_FEE",
            )
        )
        assert result.scalar() == 0

        # Final balance: 1000 - 1 + 16 - 0.50 = 1014.50 (no tool fee)
        balance = await get_balance(bot_id=bot.id, session=session)
        assert balance == Decimal("1014.5")
