#!/usr/bin/env python3
"""
verify_integrity.py — Reflection test to prove models match expected schema.

Imports models from models.py (Single Source of Truth) and verifies that
all critical columns exist with correct types. This script catches the exact
class of bug that caused the original AttributeError.

Usage:
    cd src/backend && python verify_integrity.py

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
"""

import sys

# Import from the Single Source of Truth
from models import Base, Bot, Ledger, Post, Prediction, AuditLog, User


def check_column(model_cls, column_name: str, expected_type: str) -> bool:
    """Verify a column exists on a model and its type matches."""
    table = model_cls.__table__
    if column_name not in table.columns:
        print(f"  FAIL: {model_cls.__name__}.{column_name} — column NOT FOUND")
        return False

    col = table.columns[column_name]
    actual_type = type(col.type).__name__
    if actual_type != expected_type:
        print(
            f"  FAIL: {model_cls.__name__}.{column_name} — "
            f"expected {expected_type}, got {actual_type}"
        )
        return False

    print(f"  OK:   {model_cls.__name__}.{column_name} -> {actual_type}")
    return True


def main() -> int:
    passed = 0
    failed = 0

    print("=" * 60)
    print("ClawdXCraft Model Integrity Verification")
    print("=" * 60)

    # --- Bot ---
    print("\n[Bot] — Arena agent table")
    checks = [
        (Bot, "id", "Integer"),
        (Bot, "handle", "String"),
        (Bot, "persona_yaml", "Text"),
        (Bot, "hashed_api_key", "String"),
        (Bot, "api_secret", "String"),
        (Bot, "balance", "Float"),
        (Bot, "status", "String"),
        (Bot, "created_at", "DateTime"),
        (Bot, "last_action_at", "DateTime"),   # Invariant #1: entropy decay
        (Bot, "is_external", "Boolean"),
        (Bot, "owner_id", "Integer"),           # Phase 8: human ownership
        (Bot, "verification_token", "String"),
        (Bot, "is_verified", "Boolean"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- Ledger ---
    print("\n[Ledger] — Hash-chained financial ledger")
    checks = [
        (Ledger, "id", "Integer"),
        (Ledger, "bot_id", "Integer"),
        (Ledger, "amount", "Float"),
        (Ledger, "transaction_type", "String"),
        (Ledger, "reference_id", "String"),
        (Ledger, "previous_hash", "String"),
        (Ledger, "hash", "String"),
        (Ledger, "sequence", "Integer"),        # Invariant #4: strictly monotonic
        (Ledger, "timestamp", "DateTime"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- Prediction ---
    print("\n[Prediction] — Wagers")
    checks = [
        (Prediction, "id", "Integer"),
        (Prediction, "bot_id", "Integer"),
        (Prediction, "user_id", "Integer"),     # Phase 8: human betting
        (Prediction, "direction", "String"),
        (Prediction, "wager_amount", "Float"),
        (Prediction, "start_price", "Float"),
        (Prediction, "status", "String"),
        (Prediction, "reasoning", "Text"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- AuditLog ---
    print("\n[AuditLog] — Security audit trail")
    checks = [
        (AuditLog, "id", "Integer"),
        (AuditLog, "bot_id", "Integer"),
        (AuditLog, "user_id", "Integer"),       # Phase 8 extension
        (AuditLog, "action", "String"),
        (AuditLog, "metadata_json", "Text"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- Post ---
    print("\n[Post] — Legacy social (deprioritized)")
    checks = [
        (Post, "id", "Integer"),
        (Post, "bot_id", "Integer"),
        (Post, "content", "String"),
        (Post, "parent_id", "Integer"),
        (Post, "prediction_id", "Integer"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- User ---
    print("\n[User] — Human accounts (Phase 8)")
    checks = [
        (User, "id", "Integer"),
        (User, "username", "String"),
        (User, "password_hash", "String"),
        (User, "balance", "Float"),
    ]
    for model, col, typ in checks:
        if check_column(model, col, typ):
            passed += 1
        else:
            failed += 1

    # --- Cross-import verification ---
    print("\n[Import Chain] — Verifying database.py re-exports")
    try:
        from database import Bot as DBBot, Ledger as DBLedger, get_session, init_db
        assert DBBot is Bot, "database.Bot is not models.Bot — re-export broken"
        assert DBLedger is Ledger, "database.Ledger is not models.Ledger — re-export broken"
        assert callable(get_session), "get_session not callable"
        assert callable(init_db), "init_db not callable"
        print("  OK:   database.py re-exports point to models.py (same objects)")
        passed += 1
    except Exception as e:
        print(f"  FAIL: Import chain broken — {e}")
        failed += 1

    # --- Table registration ---
    print("\n[Metadata] — Tables registered in Base.metadata")
    registered = sorted(Base.metadata.tables.keys())
    print(f"  Tables: {', '.join(registered)}")
    expected_tables = {"bots", "ledger", "predictions", "audit_log", "posts", "users"}
    missing = expected_tables - set(registered)
    if missing:
        print(f"  FAIL: Missing tables: {missing}")
        failed += 1
    else:
        print("  OK:   All expected tables registered")
        passed += 1

    # --- Summary ---
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed > 0:
        print("STATUS: INTEGRITY CHECK FAILED")
        return 1
    else:
        print("STATUS: ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
