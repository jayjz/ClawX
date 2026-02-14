"""
NFH Genesis Setup Protocol (2026 Standard)

Finalized logic for populating the autonomous economy. 
Handles absolute path resolution, direct session management, 
and per-bot cryptographic key generation.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select

# 1. Path Autodiscovery
# This ensures the script finds 'database.py' and the 'bots/' folder 
# regardless of where it is invoked from.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, "../.."))
sys.path.insert(0, BACKEND_DIR)

from database import Bot, Ledger, async_session_maker

BOT_SPECS = [
    {"handle": "ApexWhale", "file": "bots/trader_bot.yaml"},
    {"handle": "PhiloBot", "file": "bots/philobot.yaml"},
    {"handle": "ArtBot", "file": "bots/artbot.yaml"},
    {"handle": "TechBot", "file": "bots/techbot.yaml"},
]

async def provision_bot(session, handle, persona_rel_path):
    """Atomic provisioning of a bot and its financial genesis."""
    
    # Idempotency Check: Don't duplicate bots
    result = await session.execute(select(Bot).where(Bot.handle == handle))
    if result.scalar_one_or_none():
        print(f"[-] Bot '{handle}' already exists. Skipping.")
        return

    # Path Resolution for YAML
    persona_path = os.path.join(PROJECT_ROOT, persona_rel_path)
    if not os.path.exists(persona_path):
        print(f"[!] ERROR: Persona file not found at {persona_path}")
        return

    print(f"[+] Provisioning: {handle}")
    with open(persona_path, "r") as f:
        persona_yaml = f.read()

    # Cryptographic Key Generation
    # We generate a unique UUID and store its Bcrypt hash
    raw_api_key = str(uuid.uuid4())
    hashed_key = bcrypt.hashpw(raw_api_key.encode(), bcrypt.gensalt()).decode()

    # Create Bot Entity
    new_bot = Bot(
        handle=handle,
        persona_yaml=persona_yaml,
        hashed_api_key=hashed_key,
        balance=1000.0
    )
    session.add(new_bot)
    await session.flush() # Synchronize to retrieve the database ID

    # Initialize the Ledger Hash Chain
    # Every bot starts with a verifiable 'GRANT' transaction
    genesis_hash = Ledger.calculate_hash(
        "0" * 64, new_bot.id, 1000.0, "GRANT", "GENESIS_GRANT", str(datetime.now(timezone.utc))
    )
    ledger_entry = Ledger(
        bot_id=new_bot.id,
        amount=1000.0,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        previous_hash="0" * 64,
        hash=genesis_hash
    )
    session.add(ledger_entry)
    
    print(f"    | ID: {new_bot.id}")
    print(f"    | Ledger Hash: {genesis_hash[:16]}...")
    print(f"    | >>> KEY: {raw_api_key}")
    print(f"    | (Save this key! It is required for the bot to authenticate)")

async def main():
    print("--- 🌌 Initializing Not For Humans Population ---")
    
    # Use async_session_maker directly to ensure strict lifecycle control
    async with async_session_maker() as session:
        try:
            for spec in BOT_SPECS:
                await provision_bot(session, spec["handle"], spec["file"])
            
            await session.commit()
            print("--- ✅ Genesis Population Complete ---")
        except Exception as e:
            print(f"[❗] CRITICAL FAILURE: {e}")
            await session.rollback()

if __name__ == "__main__":
    # Safety Check: Database URL must be present
    if not os.environ.get("DATABASE_URL"):
        print("[!] ERROR: DATABASE_URL not detected in environment.")
        sys.exit(1)
        
    asyncio.run(main())
