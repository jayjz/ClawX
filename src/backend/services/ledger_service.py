import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import Ledger

async def append_ledger_entry(
    *,
    bot_id: int,
    amount: float,
    transaction_type: str,
    reference_id: str,
    session: AsyncSession,
) -> Ledger:
    """
    Appends a new entry to the cryptographic ledger.
    Calculates the hash based on the previous entry to ensure chain integrity.
    """
    # 1. Get previous hash (The Chain)
    result = await session.execute(
        select(Ledger)
        .where(Ledger.bot_id == bot_id)
        .order_by(Ledger.id.desc())
        .limit(1)
    )
    last_entry: Optional[Ledger] = result.scalar_one_or_none()
    previous_hash = last_entry.hash if last_entry else "0" * 64
    
    timestamp = datetime.now(timezone.utc)

    # 2. Construct Payload
    payload = (
        f"{bot_id}|"
        f"{amount}|"
        f"{transaction_type}|"
        f"{reference_id}|"
        f"{timestamp.isoformat()}|"
        f"{previous_hash}"
    )

    # 3. Hash
    entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # 4. Commit
    entry = Ledger(
        bot_id=bot_id,
        amount=amount,
        transaction_type=transaction_type,
        reference_id=reference_id,
        previous_hash=previous_hash,
        hash=entry_hash,
        created_at=timestamp,
    )

    session.add(entry)
    return entry
