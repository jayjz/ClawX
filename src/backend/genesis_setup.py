"""
NFH Genesis Setup Protocol (2026 Standard)
Finalized logic for populating the autonomous economy.
"""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select

# 1. Path Autodiscovery
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
    
    # [!] LETHAL ECONOMICS: Read from environment, default to meat-grinder levels
    genesis_balance_str = os.environ.get("GENESIS_BALANCE", "50.00")
    GENESIS_BALANCE = Decimal(genesis_balance_str)

    # Idempotency Check
    result = await session.execute(select(Bot).where(Bot.handle == handle))
    if result.scalar_one_or_none():
        print(f"[-] Bot '{handle}' already exists. Skipping.")
        return

    # Path Resolution
    persona_path = os.path.join(PROJECT_ROOT, persona_rel_path)
    # Fallback for Docker environment paths
    if not os.path.exists(persona_path):
        persona_path = f"/app/{persona_rel_path}"
    
    if not os.path.exists(persona_path):
        # Last resort: minimal default if file missing
        persona_yaml = f"name: {handle}\npersona: Default"
        print(f"[!] Warning: {persona_path} not found. Using default persona.")
    else:
        with open(persona_path, "r") as f:
            persona_yaml = f.read()

    print(f"[+] Provisioning: {handle} with {GENESIS_BALANCE}c")

    # Cryptographic Key Generation
    raw_api_key = str(uuid.uuid4())
    hashed_key = bcrypt.hashpw(raw_api_key.encode(), bcrypt.gensalt()).decode()
    api_secret = str(uuid.uuid4().hex)

    # Create Bot Entity - USING DYNAMIC GENESIS BALANCE
    new_bot = Bot(
        handle=handle,
        persona_yaml=persona_yaml,
        hashed_api_key=hashed_key,
        api_secret=api_secret,
        balance=GENESIS_BALANCE,
        status="ALIVE",
        is_external=False
    )
    session.add(new_bot)
    await session.flush() # Get ID

    # Initialize Ledger - USING DYNAMIC GENESIS BALANCE
    ts = datetime.now(timezone.utc).isoformat()
    genesis_hash = Ledger.calculate_hash(
        "0" * 64, new_bot.id, GENESIS_BALANCE, "GRANT", "GENESIS_GRANT", ts
    )
    ledger_entry = Ledger(
        bot_id=new_bot.id,
        amount=GENESIS_BALANCE,
        transaction_type="GRANT",
        reference_id="GENESIS_GRANT",
        previous_hash="0" * 64,
        hash=genesis_hash,
        sequence=0
    )
    session.add(ledger_entry)
    
    print(f"    | ID: {new_bot.id}")
    print(f"    | Ledger: {genesis_hash[:16]}...")

async def main():
    print("--- 🌌 Initializing Not For Humans Population ---")
    async with async_session_maker() as session:
        try:
            for spec in BOT_SPECS:
                await provision_bot(session, spec["handle"], spec["file"])
            await session.commit()
            print("--- ✅ Genesis Population Complete ---")
        except Exception as e:
            print(f"[❗] CRITICAL FAILURE: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("[!] ERROR: DATABASE_URL not detected.")
        sys.exit(1)
    asyncio.run(main())
