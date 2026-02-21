"""
ledger_service.py — Append-only hash-chained ledger operations.

Imports Ledger strictly from models.py (Single Source of Truth).

Constitutional references:
  - CLAUDE.md Invariant #4: "Irreversible loss is real"
  - Ledger.sequence is strictly monotonic per bot_id — enforced by
    UniqueConstraint('bot_id', 'sequence') and this service's SELECT...ORDER BY
  - Hash chain: SHA256(bot_id|amount|type|ref|timestamp|previous_hash|sequence)
  - If sequence is ever non-monotonic, the ledger is corrupted.

v2.0 — Observability layer:
  ``narrative_fields`` is an optional dict of cost/ROI/waste data written to
  the companion ``agent_metrics`` table in the same transaction. It is NOT
  included in the SHA256 payload — the hash chain is unchanged.
"""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Ledger


async def append_ledger_entry(
    *,
    bot_id: int,
    amount: "float | Decimal",
    transaction_type: str,
    reference_id: str,
    session: AsyncSession,
    narrative_fields: Optional[dict[str, Any]] = None,
) -> Ledger:
    """
    Append a new entry to the cryptographic ledger for a given bot.

    Enforces linear ordering via strictly monotonic sequence number.
    The caller MUST hold a transactional session — this function does NOT commit.

    If ``narrative_fields`` is provided, a companion ``AgentMetricsEntry`` row
    is also added to the session (same transaction, NOT part of the hash chain).
    """
    # 1. Get the tip of the chain (last entry for this bot)
    result = await session.execute(
        select(Ledger)
        .where(Ledger.bot_id == bot_id)
        .order_by(Ledger.sequence.desc())
        .limit(1)
    )
    last_entry: Optional[Ledger] = result.scalar_one_or_none()

    # 2. Calculate next link in the chain
    previous_hash = last_entry.hash if last_entry else "0" * 64
    next_sequence = (last_entry.sequence + 1) if last_entry else 1

    timestamp = datetime.now(timezone.utc)

    # 3. Construct hash payload (deterministic ordering)
    payload = (
        f"{bot_id}|"
        f"{amount}|"
        f"{transaction_type}|"
        f"{reference_id}|"
        f"{timestamp.isoformat()}|"
        f"{previous_hash}|"
        f"{next_sequence}"
    )

    # 4. Hash
    entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # 5. Create entry
    entry = Ledger(
        bot_id=bot_id,
        amount=amount,
        transaction_type=transaction_type,
        reference_id=reference_id,
        previous_hash=previous_hash,
        hash=entry_hash,
        sequence=next_sequence,
        timestamp=timestamp,
    )

    session.add(entry)

    # --- Observability companion row (v2.0) ---
    # Written in the same transaction but NOT part of the hash chain.
    if narrative_fields is not None:
        from models import AgentMetricsEntry

        session.add(
            AgentMetricsEntry(
                bot_id=bot_id,
                tick_id=narrative_fields.get("tick_id", reference_id),
                enforcement_mode=narrative_fields.get("enforcement_mode", "observe"),
                tick_outcome=narrative_fields.get("tick_outcome", transaction_type),
                phantom_entropy_fee=Decimal(
                    str(narrative_fields.get("phantom_entropy_fee", 0))
                ),
                would_have_been_liquidated=bool(
                    narrative_fields.get("would_have_been_liquidated", False)
                ),
                balance_snapshot=Decimal(
                    str(narrative_fields.get("balance_snapshot", 0))
                ),
                metrics_json=narrative_fields,
            )
        )

    return entry


async def get_balance(*, bot_id: int, session: AsyncSession) -> Decimal:
    """Compute authoritative balance by summing all ledger entries for a bot.

    This is the ONLY source of balance truth. Bot.balance is a denormalized
    cache that MUST NOT be used for financial decisions.

    Returns Decimal('0') if no ledger entries exist.
    """
    result = await session.execute(
        select(sa_func.sum(Ledger.amount)).where(Ledger.bot_id == bot_id)
    )
    raw = result.scalar_one_or_none()
    if raw is None:
        return Decimal('0')
    return Decimal(str(raw))
