import asyncio
import os
import sys
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.backend.database import async_session_maker

async def migrate():
    print(">> MIGRATING LEDGER: Adding Sequence Physics...")
    async with async_session_maker() as session:
        try:
            # 1. Add Column (Nullable first)
            print("   - Adding 'sequence' column...")
            await session.execute(text("ALTER TABLE ledger ADD COLUMN IF NOT EXISTS sequence INTEGER"))
            
            # 2. Backfill Sequence (This is tricky in SQL, simple approximation for Dev)
            # We assume ID order is close enough for existing data or we wipe.
            # For this 'Hard Pivot', we will wipe the ledger if it has data to ensure purity,
            # OR we attempt to sequence it. Let's sequence it.
            print("   - Backfilling sequence numbers...")
            # This requires a window function update which is complex in generic SQL.
            # Simplified: Reset sequence to id for simplicity in this pivot phase.
            await session.execute(text("UPDATE ledger SET sequence = id"))
            
            # 3. Add Unique Constraint (The Law)
            print("   - Applying UNIQUE constraint (bot_id, sequence)...")
            try:
                await session.execute(text("ALTER TABLE ledger ADD CONSTRAINT uq_ledger_bot_sequence UNIQUE (bot_id, sequence)"))
                print("     [OK] Constraint Applied.")
            except Exception as e:
                print(f"     [WARN] Constraint might already exist: {e}")

            await session.commit()
            print(">> MIGRATION COMPLETE. Ledger is now Linear.")
            
        except Exception as e:
            print(f"!! MIGRATION FAILED: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(migrate())
