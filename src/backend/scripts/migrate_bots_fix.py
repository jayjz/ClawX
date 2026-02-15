import asyncio
import os
import sys
from sqlalchemy import text

# Add backend to path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backend.database import async_session_maker

async def migrate():
    print(">> MIGRATING BOTS: Adding Physics Columns...")
    async with async_session_maker() as session:
        try:
            # 1. last_action_at (For Entropy)
            print("   - Adding 'last_action_at'...")
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS last_action_at TIMESTAMP WITH TIME ZONE"))
            
            # 2. api_secret (For Gateway Auth)
            print("   - Adding 'api_secret'...")
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS api_secret VARCHAR(64)"))
            # Add unique constraint if not exists (simplified)
            try:
                await session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_bots_api_secret ON bots (api_secret)"))
            except Exception:
                pass

            # 3. is_external (For Identity)
            print("   - Adding 'is_external'...")
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS is_external BOOLEAN DEFAULT FALSE"))

            await session.commit()
            print(">> MIGRATION COMPLETE. Bots are ready for Physics.")
            
        except Exception as e:
            print(f"!! MIGRATION FAILED: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(migrate())
