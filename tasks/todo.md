## Surgical Backend Patch — Immortality + Genesis Crash (2026-02-22)

### Context
Agents were immortal because `ENTROPY_BASE` and starting balance were hardcoded.
`genesis_setup.py` had a duplicate insert block causing `ix_bots_handle` UniqueViolationError crash.

---

### Execution Checklist

- [x] **Step 1** — Write this todo.md (read lessons.md first → none existed, created)
- [x] **Step 2** — Fix `bot_runner.py` ENTROPY_BASE
  - Already done: line 66 reads `ENTROPY_BASE = Decimal(os.environ.get("ENTROPY_BASE", "15.00"))`
  - No change required
- [x] **Step 3** — Fix `genesis_setup.py`: remove duplicate insert block (lines 95–130)
  - Duplicate re-created same bot with hardcoded `Decimal('1000.0')` balance
  - UniqueViolationError on `ix_bots_handle` constraint — same handle inserted twice in one session
- [x] **Step 4** — Fix `genesis_bot.py`: bind `GENESIS_BALANCE = Decimal(os.environ.get("GENESIS_BALANCE", "50.00"))`
  - Add `from decimal import Decimal` import
  - Add module-level `GENESIS_BALANCE` constant
  - Function signature default + argparse default + call site all use `Decimal`
- [x] **Step 5** — Run `BATTLE_DURATION_MIN=5 ./stress_test.sh`
  - ✅ Zero IntegrityErrors — all 24 bots provisioned at 50c
  - ✅ Observe mode correct — phantom entropy, real research payouts
  - ✅ Viability: 79.2 VIABLE | 31 ticks | 69 research | 0 deaths
  - ✅ lessons.md updated with results

---

## Phase 1 — Architecture & Specs (Completed 2026-02-07)

- docs/architecture.md written and committed
- Core 5 tables defined
- 10 essential endpoints locked
- Security & auth baseline confirmed
