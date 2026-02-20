import asyncio
import pytest
from decimal import Decimal
from sqlalchemy import select

from models import Bot, Ledger
from database import async_session_maker
from services.ledger_service import append_ledger_entry, get_balance

@pytest.mark.asyncio
async def test_concurrent_ticker_and_wager_desync(db_session):
    """
    PROVE THE VULNERABILITY:
    Simulate bot_runner (ticker) and gateway (wager) running concurrently.
    This test will FAIL if the dual-state risk exists (which it currently does).
    """
    # 1. Setup Genesis Bot
    bot = Bot(
        handle="race_bot",
        persona_yaml="test",
        balance=Decimal('100.00'),
        status="ALIVE"
    )
    db_session.add(bot)
    await db_session.commit()
    
    await append_ledger_entry(
        bot_id=bot.id,
        amount=Decimal('100.00'),
        transaction_type="GRANT",
        reference_id="GENESIS",
        session=db_session
    )
    await db_session.commit()

    # 2. Simulate bot_runner reading ledger balance
    async with async_session_maker() as ticker_session:
        ticker_balance = await get_balance(bot_id=bot.id, session=ticker_session)
        
        # 3. Simulate gateway (wager) reading bot.balance and deducting
        async with async_session_maker() as wager_session:
            result = await wager_session.execute(select(Bot).where(Bot.id == bot.id))
            wager_bot = result.scalar_one()
            
            wager_amount = Decimal('10.00')
            wager_bot.balance -= wager_amount
            
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-wager_amount,
                transaction_type="WAGER",
                reference_id="WAGER_1",
                session=wager_session
            )
            await wager_session.commit()
            
        # 4. bot_runner finishes its tick and overwrites bot.balance
        result = await ticker_session.execute(select(Bot).where(Bot.id == bot.id))
        ticker_bot = result.scalar_one()
        
        entropy_fee = Decimal('1.00')
        ticker_bot.balance = ticker_balance - entropy_fee
        
        await append_ledger_entry(
            bot_id=bot.id,
            amount=-entropy_fee,
            transaction_type="HEARTBEAT",
            reference_id="TICK_1",
            session=ticker_session
        )
        await ticker_session.commit()

    # 5. Verify the desync
    async with async_session_maker() as verify_session:
        result = await verify_session.execute(select(Bot).where(Bot.id == bot.id))
        final_bot = result.scalar_one()
        final_ledger_balance = await get_balance(bot_id=bot.id, session=verify_session)
        
        # The ledger should be 100 - 10 - 1 = 89
        assert final_ledger_balance == Decimal('89.00')
        
        # If the vulnerability exists, bot.balance will be 99.00 (100 - 1)
        # We assert they are equal, which will FAIL until the architecture is fixed.
        assert final_bot.balance == final_ledger_balance, f"DESYNC DETECTED: bot.balance={final_bot.balance}, ledger={final_ledger_balance}"

@pytest.mark.asyncio
async def test_derived_balance_with_row_lock(db_session):
    """
    TEST THE NEW ARCHITECTURE:
    Ensure that using SELECT FOR UPDATE prevents concurrent modifications
    from reading stale ledger state.
    """
    # Setup
    bot = Bot(
        handle="lock_bot",
        persona_yaml="test",
        balance=Decimal('100.00'),
        status="ALIVE"
    )
    db_session.add(bot)
    await db_session.commit()
    
    await append_ledger_entry(
        bot_id=bot.id,
        amount=Decimal('100.00'),
        transaction_type="GRANT",
        reference_id="GENESIS",
        session=db_session
    )
    await db_session.commit()

    async def run_wager():
        async with async_session_maker() as session:
            # SELECT FOR UPDATE on the bot row to lock it
            result = await session.execute(
                select(Bot).where(Bot.id == bot.id).with_for_update()
            )
            locked_bot = result.scalar_one()
            
            # Read derived balance while holding the lock
            current_balance = await get_balance(bot_id=bot.id, session=session)
            
            await asyncio.sleep(0.1) # Simulate work
            
            wager_amount = Decimal('10.00')
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-wager_amount,
                transaction_type="WAGER",
                reference_id="WAGER_LOCK",
                session=session
            )
            await session.commit()

    async def run_ticker():
        async with async_session_maker() as session:
            # SELECT FOR UPDATE on the bot row to lock it
            result = await session.execute(
                select(Bot).where(Bot.id == bot.id).with_for_update()
            )
            locked_bot = result.scalar_one()
            
            # Read derived balance while holding the lock
            current_balance = await get_balance(bot_id=bot.id, session=session)
            
            entropy_fee = Decimal('1.00')
            await append_ledger_entry(
                bot_id=bot.id,
                amount=-entropy_fee,
                transaction_type="HEARTBEAT",
                reference_id="TICK_LOCK",
                session=session
            )
            await session.commit()

    # Run concurrently
    await asyncio.gather(run_wager(), run_ticker())

    # Verify
    async with async_session_maker() as verify_session:
        final_ledger_balance = await get_balance(bot_id=bot.id, session=verify_session)
        assert final_ledger_balance == Decimal('89.00')
