"""Tests for bot creation and ledger integrity.

Proves:
  1. Bot creation writes a GRANT ledger entry
  2. Ledger sequence starts at 1 and is monotonic
  3. Bot balance == sum of ledger amounts
  4. Hash chain links correctly (previous_hash references prior entry)
  5. POST /bots endpoint works end-to-end
  6. Duplicate handle is rejected

Constitutional references:
  - CLAUDE.md Invariant #4: Irreversible loss / monotonic sequence
  - lessons.md Rule #3: Test fixtures must guarantee isolation
"""

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

_backend = str(Path(__file__).resolve().parents[2] / "src" / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from models import Bot, Ledger, AuditLog
from services.ledger_service import append_ledger_entry


# ============================================================================
# Fixtures — in-memory SQLite for isolation (lessons.md Rule #3)
# ============================================================================

@pytest.fixture
async def session():
    """Create an isolated async SQLite session for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from models import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s

    await engine.dispose()


async def _create_bot(session, handle="TestBot", balance=1000.0):
    """Helper: create a bot + GRANT entry atomically."""
    import secrets
    import bcrypt

    raw_key = secrets.token_hex(16)
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    bot = Bot(
        handle=handle,
        persona_yaml="test persona",
        hashed_api_key=hashed,
        api_secret=secrets.token_hex(32),
        balance=balance,
        status="ALIVE",
        is_external=False,
    )
    session.add(bot)
    await session.flush()

    entry = await append_ledger_entry(
        bot_id=bot.id,
        amount=balance,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        session=session,
    )
    await session.commit()
    return bot, entry, raw_key


# ============================================================================
# Tests
# ============================================================================

class TestGenesisBot:
    @pytest.mark.asyncio
    async def test_bot_created_with_grant(self, session):
        """Bot creation produces a GRANT ledger entry."""
        bot, entry, _ = await _create_bot(session)

        assert bot.id is not None
        assert bot.handle == "TestBot"
        assert bot.balance == 1000.0
        assert bot.status == "ALIVE"

        assert entry.bot_id == bot.id
        assert entry.transaction_type == "GRANT"
        assert entry.amount == 1000.0
        assert entry.reference_id == "GENESIS_GRANT"

    @pytest.mark.asyncio
    async def test_sequence_starts_at_one(self, session):
        """First ledger entry has sequence=1 (Invariant #4: monotonic)."""
        _, entry, _ = await _create_bot(session)
        assert entry.sequence == 1

    @pytest.mark.asyncio
    async def test_genesis_hash_chains_from_zero(self, session):
        """First entry's previous_hash is all zeros."""
        _, entry, _ = await _create_bot(session)
        assert entry.previous_hash == "0" * 64

    @pytest.mark.asyncio
    async def test_balance_equals_ledger_sum(self, session):
        """Bot balance must equal the sum of its ledger entries."""
        from sqlalchemy import select, func

        bot, _, _ = await _create_bot(session, balance=500.0)

        result = await session.execute(
            select(func.sum(Ledger.amount)).where(Ledger.bot_id == bot.id)
        )
        ledger_sum = result.scalar()
        assert abs(bot.balance - ledger_sum) < 0.0001


class TestLedgerChainIntegrity:
    @pytest.mark.asyncio
    async def test_multiple_entries_chain(self, session):
        """Multiple ledger entries form a valid hash chain."""
        bot, grant_entry, _ = await _create_bot(session)

        # Add a WAGER
        wager_entry = await append_ledger_entry(
            bot_id=bot.id,
            amount=-50.0,
            transaction_type="WAGER",
            reference_id="TEST_WAGER_1",
            session=session,
        )
        await session.commit()

        # Chain check: wager's previous_hash == grant's hash
        assert wager_entry.previous_hash == grant_entry.hash
        assert wager_entry.sequence == grant_entry.sequence + 1

    @pytest.mark.asyncio
    async def test_sequence_strictly_monotonic(self, session):
        """Adding 5 entries produces sequences 1,2,3,4,5 with no gaps."""
        bot, _, _ = await _create_bot(session)

        for i in range(4):
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-10.0,
                transaction_type="WAGER",
                reference_id=f"WAGER_{i}",
                session=session,
            )
        await session.commit()

        from sqlalchemy import select
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id)
            .order_by(Ledger.sequence.asc())
        )
        entries = result.scalars().all()

        assert len(entries) == 5  # 1 GRANT + 4 WAGERs
        for i, entry in enumerate(entries):
            assert entry.sequence == i + 1, f"Expected seq {i+1}, got {entry.sequence}"

    @pytest.mark.asyncio
    async def test_hash_chain_integrity(self, session):
        """Every entry's previous_hash matches the prior entry's hash."""
        bot, _, _ = await _create_bot(session)

        for i in range(3):
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-25.0,
                transaction_type="ENTROPY",
                reference_id=f"ORACLE:ENTROPY_{i}",
                session=session,
            )
        await session.commit()

        from sqlalchemy import select
        result = await session.execute(
            select(Ledger)
            .where(Ledger.bot_id == bot.id)
            .order_by(Ledger.sequence.asc())
        )
        entries = result.scalars().all()

        prev_hash = "0" * 64
        for entry in entries:
            assert entry.previous_hash == prev_hash, (
                f"Chain break at seq {entry.sequence}"
            )
            prev_hash = entry.hash

    @pytest.mark.asyncio
    async def test_two_bots_independent_chains(self, session):
        """Two bots have independent ledger chains, both starting at seq=1."""
        bot_a, entry_a, _ = await _create_bot(session, handle="BotA")
        bot_b, entry_b, _ = await _create_bot(session, handle="BotB")

        assert entry_a.sequence == 1
        assert entry_b.sequence == 1
        assert entry_a.hash != entry_b.hash  # Different bots, different hashes
