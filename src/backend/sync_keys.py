"""Sync .env.bots API keys into the database as bcrypt hashes.

For each KEY in .env.bots (e.g. APEXWHALE_KEY=<uuid>), finds the bot
by matching the handle prefix and updates its hashed_api_key field.
"""
import asyncio
import os
import sys
from pathlib import Path

import bcrypt as _bcrypt
from dotenv import load_dotenv
from sqlalchemy import select, update

_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR / ".env", override=True)
load_dotenv(_SCRIPT_DIR / ".env.bots", override=True)

from database import Bot, engine, async_session_maker

# Map env var prefixes to bot handles
KEY_TO_HANDLE = {
    "APEXWHALE_KEY": ["ApexWhale"],
    "PHILOBOT_01_KEY": ["philobot_01", "PhiloBot"],
    "ARTBOT_01_KEY": ["artbot_01", "ArtBot"],
    "TECHBOT_01_KEY": ["techbot_01", "TechBot"],
}


async def sync():
    updated = 0
    async with async_session_maker() as session:
        for env_key, handles in KEY_TO_HANDLE.items():
            raw_key = os.environ.get(env_key)
            if not raw_key:
                print(f"  [SKIP] {env_key} not in environment")
                continue

            hashed = _bcrypt.hashpw(raw_key.encode(), _bcrypt.gensalt()).decode()

            for handle in handles:
                result = await session.execute(
                    select(Bot).where(Bot.handle == handle)
                )
                bot = result.scalar_one_or_none()
                if not bot:
                    continue

                bot.hashed_api_key = hashed
                updated += 1
                print(f"  [SYNC] {handle} (id={bot.id}) <- {env_key}")

        await session.commit()

    print(f"\n  {updated} bot(s) synced.")
    await engine.dispose()


if __name__ == "__main__":
    print("[sync_keys] Syncing .env.bots credentials to database...")
    asyncio.run(sync())
