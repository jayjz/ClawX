import asyncio
import hashlib
from sqlalchemy import select, desc
from database import Ledger, async_session_maker

async def check_ledger_integrity():
    print("--- 🔍 NFH Ledger Integrity Audit ---")
    async with async_session_maker() as session:
        result = await session.execute(
            select(Ledger).order_by(desc(Ledger.timestamp)).limit(10)
        )
        entries = result.scalars().all()
        
        if not entries:
            print("[!] Ledger is empty. No transactions to verify.")
            return

        for e in entries:
            expected = Ledger.calculate_hash(
                e.previous_hash, e.bot_id, e.amount, 
                e.transaction_type, e.reference_id, str(e.timestamp)
            )
            status = "✅ VALID" if expected == e.hash else "❌ CORRUPT"
            print(f"ID: {e.id} | Bot: {e.bot_id} | {e.transaction_type} | {status}")
            if status == "❌ CORRUPT":
                print(f"   - Stored: {e.hash[:16]}...")
                print(f"   - Calc:   {expected[:16]}...")

if __name__ == "__main__":
    asyncio.run(check_ledger_integrity())
