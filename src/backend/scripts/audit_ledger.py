import asyncio
import os
import sys
from sqlalchemy import select, func

# Path hack to import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.backend.database import async_session_maker, Bot, Ledger

async def audit():
    print("🔍 STARTING LEDGER AUDIT...")
    async with async_session_maker() as session:
        # Get all bots
        bots = (await session.execute(select(Bot))).scalars().all()
        
        discrepancies = 0
        
        for bot in bots:
            # Sum ledger
            result = await session.execute(
                select(func.sum(Ledger.amount)).where(Ledger.bot_id == bot.id)
            )
            ledger_sum = result.scalar() or 0.0
            
            # Compare
            # Use a small epsilon for float math
            if abs(bot.balance - ledger_sum) > 0.0001:
                print(f"❌ INTEGRITY FAILURE: Bot @{bot.handle} (ID {bot.id})")
                print(f"   DB Balance:     {bot.balance}")
                print(f"   Ledger Proof:   {ledger_sum}")
                print(f"   Drift:          {bot.balance - ledger_sum}")
                discrepancies += 1
            else:
                print(f"✅ Bot @{bot.handle}: Verified ({ledger_sum}c)")
                
        if discrepancies > 0:
            print(f"\n🚨 AUDIT FAILED: {discrepancies} corrupt balances found.")
            sys.exit(1)
        else:
            print("\n✨ SYSTEM INTEGRITY VERIFIED. The math holds.")

if __name__ == "__main__":
    asyncio.run(audit())
