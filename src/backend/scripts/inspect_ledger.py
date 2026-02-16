#!/usr/bin/env python3
"""
inspect_ledger.py — Forensic inspection of the ledger and bot balances.

No psql dependency. Pure Python + SQLAlchemy.

Checks:
  1. Hash chain integrity (each entry's previous_hash == prior entry's hash)
  2. Sequence monotonicity (strictly increasing, no gaps, no forks)
  3. Balance consistency (bot.balance == sum of ledger amounts for that bot)
  4. Lists all entries per bot with amounts and types

Constitutional references:
  - CLAUDE.md Invariant #4: Irreversible loss — ledger is append-only, monotonic
  - lessons.md: All economic state changes must be hash-chained

Usage:
    # Docker:
    docker compose exec backend python3 src/backend/scripts/inspect_ledger.py

    # Local:
    cd src/backend && DATABASE_URL=... python scripts/inspect_ledger.py

    # Single bot:
    ... inspect_ledger.py --bot-id 1
"""

import argparse
import asyncio
import hashlib
import sys
from decimal import Decimal
from pathlib import Path

_backend = str(Path(__file__).resolve().parents[1])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy import select
from database import async_session_maker
from models import Bot, Ledger


async def inspect(bot_id: int | None = None) -> bool:
    """Inspect ledger integrity. Returns True if all checks pass."""
    all_ok = True

    async with async_session_maker() as session:
        # Load bots
        stmt = select(Bot)
        if bot_id is not None:
            stmt = stmt.where(Bot.id == bot_id)
        result = await session.execute(stmt.order_by(Bot.id))
        bots = result.scalars().all()

        if not bots:
            print("[!] No bots found.")
            return True

        print(f"{'='*70}")
        print(f"LEDGER FORENSIC REPORT — {len(bots)} bot(s)")
        print(f"{'='*70}")

        for bot in bots:
            print(f"\n[Bot #{bot.id}] @{bot.handle} | status={bot.status} | DB balance={bot.balance:.4f}")

            # Load ledger entries ordered by sequence
            result = await session.execute(
                select(Ledger)
                .where(Ledger.bot_id == bot.id)
                .order_by(Ledger.sequence.asc())
            )
            entries = result.scalars().all()

            if not entries:
                print("  (no ledger entries)")
                if bot.balance != 0:
                    print(f"  [FAIL] Bot has balance {bot.balance} but NO ledger entries!")
                    all_ok = False
                continue

            # Walk the chain
            ledger_sum = Decimal('0')
            prev_hash = "0" * 64
            prev_seq = 0
            chain_ok = True
            seq_ok = True

            print(f"  {'seq':>4} {'type':<14} {'amount':>12} {'hash':>26}")
            print(f"  {'-'*4} {'-'*14} {'-'*12} {'-'*26}")

            for entry in entries:
                entry_amount = Decimal(str(entry.amount))
                ledger_sum += entry_amount

                # Sequence check: strictly monotonic, no gaps
                if entry.sequence != prev_seq + 1:
                    print(f"  [FAIL] Sequence gap: expected {prev_seq + 1}, got {entry.sequence}")
                    seq_ok = False
                    all_ok = False

                # Hash chain check
                if entry.previous_hash != prev_hash:
                    print(f"  [FAIL] Chain break at seq {entry.sequence}: "
                          f"previous_hash mismatch")
                    chain_ok = False
                    all_ok = False

                print(f"  {entry.sequence:>4} {entry.transaction_type:<14} "
                      f"{float(entry_amount):>+12.4f} {entry.hash[:26]}")

                prev_hash = entry.hash
                prev_seq = entry.sequence

            # Summary
            print(f"  {'':>4} {'TOTAL':<14} {float(ledger_sum):>+12.4f}")
            print()

            # Balance consistency — CRITICAL invariant (exact with Numeric/Decimal)
            db_balance = Decimal(str(bot.balance))
            if db_balance != ledger_sum:
                print(f"  [CRITICAL INTEGRITY FAILURE] Balance mismatch: "
                      f"DB={db_balance}, Ledger sum={ledger_sum}, "
                      f"drift={db_balance - ledger_sum}")
                all_ok = False
            else:
                print(f"  [OK] Balance consistent: {db_balance}")

            if chain_ok:
                print(f"  [OK] Hash chain intact ({len(entries)} entries)")
            if seq_ok:
                print(f"  [OK] Sequence monotonic (1..{prev_seq})")

    print(f"\n{'='*70}")
    if all_ok:
        print("RESULT: ALL CHECKS PASSED")
    else:
        print("RESULT: FAILURES DETECTED — see above")
    print(f"{'='*70}")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Inspect ledger integrity")
    parser.add_argument("--bot-id", type=int, default=None, help="Inspect single bot")
    args = parser.parse_args()
    ok = asyncio.run(inspect(args.bot_id))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
