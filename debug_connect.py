import asyncio
import os
import asyncpg

# Hardcoded to match your working psql command
DSN = "postgresql://clawd_claude:clawd_claude_dev_2026@127.0.0.1:5433/clawdxcraft"

async def main():
    print(f"🔌 Attempting connection to: 127.0.0.1:5433 as clawd_claude")
    try:
        conn = await asyncpg.connect(DSN)
        print("✅ SUCCESS: Python asyncpg connected successfully!")
        await conn.close()
    except Exception as e:
        print(f"❌ FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(main())
