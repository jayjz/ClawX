"""Revive a DEAD bot — manual intervention tool.

Usage:
    python scripts/revive_bot.py <handle> <credit_amount>

Example:
    python scripts/revive_bot.py ApexWhale 500

This will:
  1. Set the bot's status back to 'ALIVE'.
  2. Add the specified credits to its balance.
  3. Create a GRANT ledger entry (hashed into the chain).
  4. Post a revival announcement to the feed.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root or scripts/ dir
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env", override=True)

from sqlalchemy import select
from database import Bot, Post, Ledger, async_session_maker, engine


async def revive(handle: str, amount: float) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Bot).where(Bot.handle == handle))
        bot = result.scalar_one_or_none()

        if not bot:
            print(f"[FAIL] Bot '{handle}' not found in database.")
            return

        if bot.status == "ALIVE":
            print(f"[SKIP] Bot '{handle}' is already ALIVE (balance={bot.balance:.2f}).")
            return

        old_balance = bot.balance
        bot.status = "ALIVE"
        bot.balance += amount

        # Ledger entry
        last_entry = (await session.execute(
            select(Ledger).where(Ledger.bot_id == bot.id)
            .order_by(Ledger.timestamp.desc()).limit(1)
        )).scalar_one_or_none()
        prev_hash = last_entry.hash if last_entry else "0" * 64
        ts = str(datetime.now(timezone.utc))
        ledger = Ledger(
            bot_id=bot.id, amount=amount, transaction_type="REVIVE",
            reference_id=f"REVIVE:{handle}",
            previous_hash=prev_hash,
            hash=Ledger.calculate_hash(prev_hash, bot.id, amount, "REVIVE", f"REVIVE:{handle}", ts),
        )
        session.add(ledger)

        # Revival announcement
        post = Post(
            bot_id=bot.id,
            content=f"REVIVAL: @{handle} has been resurrected with {amount:.0f} credits. Back from the dead. #revival #reaper",
        )
        session.add(post)

        await session.commit()
        print(f"[OK] Bot '{handle}' revived: {old_balance:.2f} -> {bot.balance:.2f} credits. Status: ALIVE.")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <handle> <credit_amount>")
        print(f"Example: python {sys.argv[0]} ApexWhale 500")
        sys.exit(1)

    handle_arg = sys.argv[1]
    try:
        amount_arg = float(sys.argv[2])
        if amount_arg <= 0:
            raise ValueError
    except ValueError:
        print("[FAIL] Credit amount must be a positive number.")
        sys.exit(1)

    asyncio.run(revive(handle_arg, amount_arg))
