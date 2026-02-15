"""Tests for the Contract of Behavior with Entropy Fee enforcement.

Proves:
  1. execute_tick ALWAYS produces exactly one ledger entry
  2. HEARTBEAT costs ENTROPY_FEE (not free)
  3. WAGER costs ENTROPY_FEE + wager amount
  4. Bot with balance < ENTROPY_FEE gets LIQUIDATION entry and status DEAD
  5. Error path still charges ENTROPY_FEE
  6. Wager capped at 10% of (balance - fee)
  7. Multiple ticks chain correctly
  8. bot.balance is updated atomically with ledger

Constitutional references:
  - CLAUDE.md Invariant #1: Inaction is costly — ENTROPY_FEE enforces this
  - CLAUDE.md Invariant #4: Irreversible loss (hash-chained)
  - lessons.md Rule #3: Test isolation (in-memory SQLite)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from models import Base, Bot, Ledger
from services.ledger_service import append_ledger_entry


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
        handle="TickTestBot",
        persona_yaml="Test agent for tick contract",
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
async def poor_bot(session):
    """Create a bot with balance below ENTROPY_FEE."""
    import secrets
    import bcrypt

    raw_key = secrets.token_hex(16)
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    bot = Bot(
        handle="PoorBot",
        persona_yaml="Broke agent",
        hashed_api_key=hashed,
        api_secret=secrets.token_hex(32),
        balance=0.10,  # Below ENTROPY_FEE (0.50)
        status="ALIVE",
        is_external=False,
    )
    session.add(bot)
    await session.flush()

    await append_ledger_entry(
        bot_id=bot.id,
        amount=0.10,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        session=session,
    )
    await session.commit()
    return bot


def _mock_session(session):
    """Create a mock async context manager that yields the given session."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=session)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


# ============================================================================
# Test: Entropy Fee on HEARTBEAT
# ============================================================================

class TestEntropyFee:
    @pytest.mark.asyncio
    async def test_heartbeat_costs_entropy_fee(self, session, bot_with_grant):
        """HEARTBEAT amount must be -ENTROPY_FEE, not zero."""
        from sqlalchemy import select

        bot = bot_with_grant

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "HEARTBEAT"

        # Verify the HEARTBEAT entry has negative amount
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "HEARTBEAT")
        )
        hb = result.scalar_one()
        assert hb.amount == -ENTROPY_FEE
        assert hb.amount < 0, "HEARTBEAT must cost money"

    @pytest.mark.asyncio
    async def test_wager_includes_entropy_fee(self, session, bot_with_grant):
        """WAGER amount must be -(ENTROPY_FEE + wager), not just -wager."""
        from sqlalchemy import select

        bot = bot_with_grant
        mock_prediction = {
            "claim_text": "BTC up",
            "direction": "UP",
            "confidence": 0.8,
            "wager_amount": 50.0,
            "reasoning": "Test",
        }

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=mock_prediction), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "WAGER"

        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "WAGER")
        )
        wager_entry = result.scalar_one()
        # Amount must include both fee and wager
        assert wager_entry.amount < -ENTROPY_FEE, \
            f"WAGER amount {wager_entry.amount} must be more negative than -{ENTROPY_FEE}"

    @pytest.mark.asyncio
    async def test_balance_updated_atomically(self, session, bot_with_grant):
        """bot.balance must decrease by exactly the ledger amount after tick."""
        from sqlalchemy import select

        bot = bot_with_grant
        original_balance = bot.balance

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        # Re-read bot
        result = await session.execute(select(Bot).where(Bot.id == bot.id))
        updated_bot = result.scalar_one()

        assert abs(updated_bot.balance - (original_balance - ENTROPY_FEE)) < 0.0001


# ============================================================================
# Test: Liquidation
# ============================================================================

class TestLiquidation:
    @pytest.mark.asyncio
    async def test_insufficient_balance_triggers_liquidation(self, session, poor_bot):
        """Bot with balance < ENTROPY_FEE gets LIQUIDATION and status DEAD."""
        from sqlalchemy import select

        bot = poor_bot

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "PoorBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "LIQUIDATION"

        # Verify bot is DEAD
        result = await session.execute(select(Bot).where(Bot.id == bot.id))
        updated_bot = result.scalar_one()
        assert updated_bot.status == "DEAD"
        assert updated_bot.balance == 0.0

        # Verify LIQUIDATION ledger entry
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "LIQUIDATION")
        )
        liq = result.scalar_one()
        assert liq.amount == 0.0
        assert "LIQUIDATION" in liq.reference_id


# ============================================================================
# Test: Error path still charges fee
# ============================================================================

class TestErrorPath:
    @pytest.mark.asyncio
    async def test_error_still_charges_fee(self, session, bot_with_grant):
        """LLM exception still produces a ledger entry with negative amount."""
        from sqlalchemy import select, func

        bot = bot_with_grant

        result = await session.execute(
            select(func.count(Ledger.id)).where(Ledger.bot_id == bot.id)
        )
        before = result.scalar()

        # First call raises, second call (error path) succeeds
        call_count = [0]
        def mock_maker():
            call_count[0] += 1
            return _mock_session(session)

        with patch("bot_runner.async_session_maker", side_effect=mock_maker), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, side_effect=RuntimeError("LLM exploded")), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "HEARTBEAT"

        result = await session.execute(
            select(func.count(Ledger.id)).where(Ledger.bot_id == bot.id)
        )
        after = result.scalar()
        assert after == before + 1

        # The error entry should have a negative amount (fee charged)
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id)
            .order_by(Ledger.sequence.desc())
            .limit(1)
        )
        error_entry = result.scalar_one()
        assert error_entry.amount < 0, "Error path must still charge entropy fee"
        assert "ERROR" in error_entry.reference_id


# ============================================================================
# Test: Wager cap
# ============================================================================

class TestWagerCap:
    @pytest.mark.asyncio
    async def test_wager_capped_at_10_percent_of_available(self, session, bot_with_grant):
        """Wager portion is capped at 10% of (balance - fee)."""
        from sqlalchemy import select

        bot = bot_with_grant  # balance = 1000

        mock_prediction = {
            "claim_text": "BTC moon",
            "direction": "UP",
            "confidence": 0.99,
            "wager_amount": 999.0,  # LLM wants nearly everything
            "reasoning": "YOLO",
        }

        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=mock_prediction), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick, ENTROPY_FEE
            tx_type = await execute_tick(
                bot_id=bot.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot.balance,
            )

        assert tx_type == "WAGER"

        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id, Ledger.transaction_type == "WAGER")
        )
        wager_entry = result.scalar_one()

        # Original balance was 1000. 10% of (1000 - 0.50) = 99.95.
        # Total = 99.95 + 0.50 = 100.45
        original_balance = 1000.0
        max_total = (original_balance - ENTROPY_FEE) * 0.1 + ENTROPY_FEE
        assert abs(wager_entry.amount) <= max_total + 0.01


# ============================================================================
# Test: Reference ID and chain integrity
# ============================================================================

class TestChainIntegrity:
    @pytest.mark.asyncio
    async def test_tick_reference_contains_tick_id(self, session, bot_with_grant):
        """Every ledger entry reference_id starts with 'TICK:'."""
        with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
             patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
             patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
            from bot_runner import execute_tick
            await execute_tick(
                bot_id=bot_with_grant.id,
                config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                balance=bot_with_grant.balance,
            )

        from sqlalchemy import select
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot_with_grant.id)
            .order_by(Ledger.sequence.desc())
            .limit(1)
        )
        latest = result.scalar_one()
        assert latest.reference_id.startswith("TICK:")

    @pytest.mark.asyncio
    async def test_multiple_ticks_chain_correctly(self, session, bot_with_grant):
        """Running 3 ticks produces 3 new entries with valid chain links."""
        from sqlalchemy import select

        bot = bot_with_grant

        for _ in range(3):
            with patch("bot_runner.async_session_maker", return_value=_mock_session(session)), \
                 patch("bot_runner.generate_prediction", new_callable=AsyncMock, return_value=None), \
                 patch("bot_runner.get_redis_client", new_callable=AsyncMock, return_value=None):
                from bot_runner import execute_tick
                await execute_tick(
                    bot_id=bot.id,
                    config={"persona": "test", "name": "TickTestBot", "goals": ["survive"]},
                    balance=bot.balance,
                )

        # Verify chain: 1 GRANT + 3 HEARTBEATs = 4 entries
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id)
            .order_by(Ledger.sequence.asc())
        )
        entries = result.scalars().all()
        assert len(entries) == 4

        # Verify chain links
        prev_hash = "0" * 64
        for i, entry in enumerate(entries):
            assert entry.sequence == i + 1
            assert entry.previous_hash == prev_hash
            prev_hash = entry.hash

        # Verify all HEARTBEAT entries have negative amounts
        for entry in entries[1:]:  # skip GRANT
            assert entry.amount < 0, f"Entry seq={entry.sequence} has non-negative amount {entry.amount}"
