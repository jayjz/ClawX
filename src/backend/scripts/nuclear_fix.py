import asyncio
import os
import sys
from sqlalchemy import text

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.backend.database import async_session_maker

async def run_patch(name, sql_commands):
    print(f"🔧 PATCHING: {name}")
    for sql in sql_commands:
        # NEW SESSION FOR EVERY COMMAND
        # This prevents "Current transaction is aborted" errors from cascading
        async with async_session_maker() as session:
            try:
                await session.execute(text(sql))
                await session.commit()
                print(f"   [SUCCESS] Executed: {sql[:60]}...")
            except Exception as e:
                # We expect errors if columns exist, so we just log and move on
                print(f"   [SKIP] Ignored: {e}")

async def main():
    # 1. BOTS TABLE PATCHES
    await run_patch("Bots Table Physics", [
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS last_action_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS api_secret VARCHAR(64)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_bots_api_secret ON bots (api_secret)",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE"
    ])

    # 2. LEDGER TABLE PATCHES
    await run_patch("Ledger Sequence Physics", [
        "ALTER TABLE ledger ADD COLUMN IF NOT EXISTS sequence INTEGER",
        "UPDATE ledger SET sequence = id WHERE sequence IS NULL",
        "ALTER TABLE ledger ADD CONSTRAINT uq_ledger_bot_sequence UNIQUE (bot_id, sequence)"
    ])

    # 3. USERS TABLE RESTORATION
    await run_patch("Users Table Restoration", [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR UNIQUE NOT NULL,
            password_hash VARCHAR NOT NULL,
            balance FLOAT DEFAULT 1000.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """
    ])
    
    print("\n✅ NUCLEAR FIX COMPLETE. Database should be compliant.")

if __name__ == "__main__":
    asyncio.run(main())
