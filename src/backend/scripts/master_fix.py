import asyncio
import os
import sys
from sqlalchemy import text

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.backend.database import async_session_maker

async def fix_schema():
    print("🔧 STARTING MASTER SCHEMA REPAIR...")
    async with async_session_maker() as session:
        # 1. Fix BOTS Table (The Physics Columns)
        print("   -> Patching 'bots' table...")
        try:
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS last_action_at TIMESTAMP WITH TIME ZONE"))
            print("      - Added last_action_at")
        except Exception as e: print(f"      - last_action_at error: {e}")

        try:
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS api_secret VARCHAR(64)"))
            await session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_bots_api_secret ON bots (api_secret)"))
            print("      - Added api_secret")
        except Exception as e: print(f"      - api_secret error: {e}")

        try:
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE"))
            print("      - Added is_external")
        except Exception as e: print(f"      - is_external error: {e}")

        # 2. Fix LEDGER Table (The Sequence Physics)
        print("   -> Patching 'ledger' table...")
        try:
            await session.execute(text("ALTER TABLE ledger ADD COLUMN IF NOT EXISTS sequence INTEGER"))
            # Backfill sequence if null to prevent unique constraint fail
            await session.execute(text("UPDATE ledger SET sequence = id WHERE sequence IS NULL"))
            print("      - Added sequence column")
        except Exception as e: print(f"      - sequence error: {e}")

        try:
            # We wrap this in a block because it fails if data is dirty, but we try anyway
            await session.execute(text("ALTER TABLE ledger ADD CONSTRAINT uq_ledger_bot_sequence UNIQUE (bot_id, sequence)"))
            print("      - Added UNIQUE constraint")
        except Exception:
            print("      - UNIQUE constraint skipped (might already exist or data conflict)")

        # 3. Fix USERS Table (If missing)
        print("   -> Patching 'users' table...")
        try:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR UNIQUE NOT NULL,
                    password_hash VARCHAR NOT NULL,
                    balance FLOAT DEFAULT 1000.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            print("      - Verified users table")
        except Exception as e: print(f"      - users table error: {e}")

        await session.commit()
        print("✅ SCHEMA REPAIR COMPLETE.")

if __name__ == "__main__":
    asyncio.run(fix_schema())
