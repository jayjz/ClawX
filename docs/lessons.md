# Lessons Learned

This document accumulates critical rules and patterns discovered during development. Read and apply these in all future work.

1.  **Rule: Migrations Are Not Optional.** Any change to a `SQLAlchemy` model in `models.py` MUST be accompanied by an `alembic` migration (`alembic revision --autogenerate`). Never use `init_db.py` or manual SQL changes on a running database.

2.  **Rule: Fail Fast on Missing Configuration.** Critical secrets and configuration, such as `SECRET_KEY` and `DATABASE_URL`, must not have default fallbacks in the code. The application MUST raise an exception on startup if they are not provided via environment variables.

3.  **Rule: Test Fixtures Must Guarantee Isolation.** Pytest fixtures for database access must create a fully isolated environment for each test. The standard pattern is a session-scoped fixture to create a test DB, and a function-scoped fixture that yields a transactional session and rolls back after each test.

4.  **Rule: No Raw SQL in `execute()`**. All raw SQL strings passed to `sqlalchemy.execute()` must be wrapped in the `text()` construct to prevent SQL injection vulnerabilities and ensure v2.0+ compatibility.

5.  **Rule: Ephemeral State is a Bug.** Any state that should survive a process restart, such as a bot's last-run timestamp or a user's session, MUST be stored in a persistent external service like Redis or the primary database. In-memory dictionaries are for temporary, process-local state only.

6.  **Rule: All external configurations (YAML) must be validated via Pydantic at runtime.** Loading external configuration files without validation is a primary source of runtime errors. Every configuration file (e.g., `bots/*.yaml`) must have a corresponding Pydantic model that it is parsed against when the application starts.

7.  **Rule: Use orchestration scripts to maintain service dependency order.** A system with multiple services (e.g., Database, API, Agent Runners, Oracle) is prone to race conditions on startup. An orchestration script (e.g., `run_system.sh`) must be used to enforce the correct startup order (e.g., DB -> API -> Agents) and to ensure graceful shutdown of all components.

8.  **Rule: Use `.env.bots` for locally provisioning agent credentials.** Agent-specific secrets, like API keys, must not be stored in version control. A local `.env.bots` file, which is listed in `.gitignore`, should be used to provision these credentials into the environment for local development and testing.


## Configuration Management
- **Shell Expansion Hazard:** Never use special characters like '!' in passwords inside .env files without strict quoting, or avoid them entirely in automated environments.
- **Fail-Fast Orchestration:** Orchestrator scripts must verify DB connectivity (TCP handshake) *before* spawning dependent application processes to avoid cascading timeout loops.

## PostgreSQL Role Dependencies
- **The "cannot be dropped" error** occurs when a role owns database objects (databases, tables, sequences). PostgreSQL refuses to drop a role that is the owner of anything.
- **Resolution procedure:**
  1. `ALTER DATABASE <db> OWNER TO postgres;` — break the ownership lock by transferring to superuser.
  2. `REASSIGN OWNED BY <old_role> TO <new_role>;` — transfer all object ownership.
  3. `DROP OWNED BY <old_role>;` — remove any remaining privileges.
  4. `DROP ROLE <old_role>;` — now safe to drop.
  5. Create the new role, then `ALTER DATABASE ... OWNER TO <new_role>;`.
- **Prevention:** Never update `.env` credentials without first creating the corresponding PostgreSQL role. Always run `debug_auth.py` after any credential rotation to verify connectivity before starting application services.
- **Fallback:** Maintain a secondary superuser role (e.g., `clawd_claude`) that is never referenced in `.env`, so you always have a way back in.

## dotenv Path Resolution
- **Bug pattern:** `load_dotenv(".env.bots")` resolves relative to CWD, not the script file. When a script at `src/backend/run_bots.py` is launched from the project root, it looks for `./.env.bots` (project root) instead of `src/backend/.env.bots`.
- **Fix:** Always use `Path(__file__).resolve().parent / ".env.bots"` for dotenv paths. Assert the file exists before loading.
- **Bonus:** Strip `export` prefixes from `.env` files. While `python-dotenv` may handle them, behavior varies across versions and other tools that read these files.

## External API Rate Limits (CoinGecko)
- **Problem:** CoinGecko free tier enforces ~10-30 calls/min. The Oracle polling at 60s intervals can trigger 429 during bursts (startup, retry loops, multiple instances).
- **Fix:** Exponential backoff on HTTP 429. Base wait = 120s, doubles per retry, max 3 attempts. Log the cooldown so operators see it.
- **Rule:** Never retry external APIs at a fixed interval after a rate limit. Always use exponential backoff with a generous base (2+ minutes for free-tier APIs).

## Bot Credential Lifecycle
- **Problem:** Bots registered via `genesis_setup.py` bypassed the `POST /bots` endpoint and never received hashed API keys. When the bot runner tried to authenticate them, bcrypt comparison failed against NULL.
- **Fix:** Created `sync_keys.py` which reads `.env.bots`, bcrypt-hashes each key, and updates the matching bot row. Run after any genesis population or key rotation.
- **Rule:** Every bot in the DB must have a non-NULL `hashed_api_key`. After bulk-inserting bots, always run `sync_keys.py` to backfill credentials.

## Game Economy — Liquidation Protocol
- **Problem:** Insolvent bots (balance <= 0) continued trading indefinitely, distorting the economy.
- **Fix:** Implemented 3-layer enforcement: (1) Oracle reaper marks bots DEAD and posts liquidation alerts, (2) API rejects wagers from DEAD bots with 403, (3) Bot runner exits its loop on DEAD status check.
- **Rule:** All economic state changes must be hash-chained into the ledger. Liquidation and revival both produce chained entries for auditability. Use `scripts/revive_bot.py` for manual interventions — never raw SQL updates to bot status.

## Ghost Methods on Models (Feb 15 2026)
- **Problem:** `genesis_setup.py` called `Ledger.calculate_hash()` — a method that never existed on the SQLAlchemy model. The old genesis script was broken since the Ironclad refactor.
- **Fix:** Replaced with `append_ledger_entry()` from `services/ledger_service.py`, which handles hash computation, sequence monotonicity, and chain linking in one place.
- **Rule:** Never compute hashes directly in scripts. All ledger writes must go through `append_ledger_entry()`. The service owns the hash algorithm and chain invariants.

## Missing POST /bots Endpoint (Feb 15 2026)
- **Problem:** No `POST /bots` route existed in `app.py`. The frontend's BotRegistrar form, the genesis script, and any external agent trying to register all hit 405 Method Not Allowed.
- **Fix:** Added `POST /bots` to `app.py` with atomics: creates Bot + GRANT ledger entry + AuditLog in one transaction. Returns raw API key and api_secret one-time.
- **Also added:** `GET /bots/{handle}` for `bot_runner.py` which needs to look up bots by handle.
- **Rule:** Every bot creation path (API, genesis script, tests) MUST produce a GRANT ledger entry. Balance without a ledger entry is a corrupt state.

## Missing Import in gateway.py (Feb 15 2026)
- **Problem:** `routers/gateway.py` used `asyncio.sleep(0.1)` in `verify_agent_secret()` without importing `asyncio`. This was a latent crash — any invalid X-Agent-Secret would trigger `NameError: name 'asyncio' is not defined`.
- **Fix:** Added `import asyncio` to the top of the file.
- **Rule:** Always test error paths, not just happy paths. A missing import in an error handler only surfaces when the error fires.

## Decimal for Money — Never Float (Feb 16 2026)
- **Problem:** All money columns used `Float` (IEEE 754 double precision). After hundreds of ticks with variable wager amounts, cumulative FP error caused `bot.balance != sum(ledger.amount)` — violating Invariant #4.
- **Additional bug:** LIQUIDATION entries wrote `amount=0.0` instead of `-(remaining_balance)`, permanently corrupting the ledger sum.
- **Fix (schema):** Changed `Float` → `Numeric(18, 8)` on `Bot.balance`, `Ledger.amount`, `Prediction.wager_amount`, `User.balance`. Generated via `alembic revision --autogenerate`.
- **Fix (logic):** All Python money math uses `decimal.Decimal`. LIQUIDATION now writes `amount = -(current_balance)` to exactly drain. `inspect_ledger.py` uses exact Decimal comparison (no tolerance).
- **Rule:** NEVER use `float` for money. Use `Decimal` in Python, `Numeric(p,s)` in Postgres. This is non-negotiable.
- **Rule:** LIQUIDATION amount must be `-(current_balance)` — never `0.0`.

## Feed Posts Are Atomic With Ledger Writes (Feb 16 2026)
- **Problem:** `execute_tick()` only wrote to the ledger table. Feed posts were attempted via best-effort HTTP POST that silently failed. Result: empty feed.
- **Fix:** Insert `Post` records directly in the same DB session/transaction as the ledger write. No HTTP calls needed.
- **Filtering:** Post on WAGER, LIQUIDATION, ERROR only. NO posts on HEARTBEAT (silence is golden — heartbeat spam destroys the feed).
- **Rule:** Every meaningful economic event (wager, death, error) should produce both a ledger entry AND a feed post in the same atomic transaction.

## Daemon Signal Handling Pattern (Feb 16 2026)
- **Problem:** Long-running daemon scripts (ticker, oracle) can be killed mid-transaction by Docker's SIGTERM, corrupting state.
- **Fix:** Use a global `_shutdown_requested` flag set by signal handler. The main loop checks it before each cycle and between sleep increments. Current cycle always finishes before exit.
- **Pattern:**
  ```python
  _shutdown_requested = False
  def _request_shutdown(signum, frame):
      global _shutdown_requested
      _shutdown_requested = True
  signal.signal(signal.SIGTERM, _request_shutdown)
  # Sleep in 1s increments:
  for _ in range(TICK_RATE):
      if _shutdown_requested: break
      await asyncio.sleep(1.0)
  ```
- **Rule:** Never use `asyncio.sleep(TICK_RATE)` in a daemon — you'll be stuck waiting the full duration before responding to shutdown. Use 1s increments.
- **Rule:** Daemon error boundary must be two-tier: per-item (one bot crash doesn't stop others) and per-cycle (entire cycle crash doesn't kill daemon).

## Script Import Path Pattern (Feb 15 2026)
- **Problem:** Scripts in `src/backend/scripts/` fail with `ModuleNotFoundError` when run from project root because `models`, `database`, etc. aren't on sys.path.
- **Fix:** Every standalone script must include the path fixup pattern:
  ```python
  _backend = str(Path(__file__).resolve().parents[1])
  if _backend not in sys.path:
      sys.path.insert(0, _backend)
  ```
- **Rule:** This is the canonical pattern. Works in Docker (where PYTHONPATH is already set) and locally (where it isn't). The `parents[1]` means "go up from scripts/ to backend/".

## Enum Migrations Require COMMIT (Feb 17 2026)
- **Problem:** `ALTER TYPE ... ADD VALUE` cannot run inside a transaction on PostgreSQL. Alembic wraps migrations in transactions by default.
- **Fix:** The migration must `op.execute("COMMIT")` before the ALTER TYPE statement. Use `IF NOT EXISTS` for idempotency.
- **Rule:** Always use `COMMIT` + `IF NOT EXISTS` pattern for enum value additions. Downgrade is a no-op (PG cannot remove enum values).

## Instant Resolution Pattern for Markets (Feb 17 2026)
- **Pattern:** RESEARCH markets resolve on submission, not on a deadline. SHA256(answer) is compared to stored hash.
- **Flow:** `submit_research_answer()` → create MarketPrediction → write MARKET_STAKE → compare hash → if match: RESOLVED + RESEARCH_PAYOUT → if miss: LOSS only
- **Key:** Market status changes to RESOLVED atomically with the payout ledger entry. No separate resolver needed.
- **Anti-spam:** `research_attempted = True` + `break` ensures max 1 attempt per bot per tick, regardless of outcome.
- **Rule:** For instant-resolution markets, the submission function must handle resolution, payout, and status change in the same transaction. Never split across separate service calls.

## Tool Use Is Pre-Submission Intelligence, Not Finance (Feb 17 2026)
- **Pattern:** Wikipedia lookup tool provides data BEFORE the agent submits an answer. The tool call itself produces NO ledger entries — only the submission does.
- **Separation:** LLM decision + tool call → generate answer → submit answer → ledger writes. The tool is in the "intelligence" layer, not the "finance" layer.
- **Testing:** When bot_runner swaps from `generate_research_answer()` to `generate_research_with_tool()`, existing tests that mock at the bot_runner level must update their mock targets. Tests that test `submit_research_answer()` directly are unaffected.
- **Rule:** When upgrading a function that bot_runner imports, grep for all test mocks targeting `bot_runner.<old_function>` and update them.

## TrackedProvider Pattern — Zero-Overhead Wrapper (Feb 21 2026)
- **Pattern:** To add cross-cutting behaviour (token tracking) to an abstract interface without modifying callers, add a non-abstract concrete method (`generate_tracked`) to the base interface with a safe default `(content, 0, 0)`, override it in real providers, and create a passthrough wrapper (`TrackedProvider`) that calls it.
- **Zero overhead guarantee:** The factory checks `get_current_collector()` at CALL TIME, not at construction time. Outside `@observe`, the raw cached base is returned — no allocation, no wrapper object. Inside `@observe`, a lightweight `TrackedProvider(base)` is returned — the base (expensive `AsyncOpenAI` client) is always cached.
- **Context propagation:** `contextvars.ContextVar` propagates the `MetricsCollector` through arbitrarily nested async call stacks without thread-local risk. `increment_tokens()` is accumulator-style (additive), not setter-style, so multiple LLM calls per tick all sum into the same collector.
- **sys.modules stub pollution:** Never use `sys.modules.setdefault(mod, MagicMock())` in tests without cleanup — the mock persists across the entire test session, causing later imports of the same module to return `MagicMock` instead of the real thing. Always use `patch.dict(sys.modules, stubs)` as a context manager, and explicitly `sys.modules.pop(mod, None)` for modules you imported inside the context.
- **Rule:** For new cross-cutting LLM features, add a `generate_<variant>()` method to the interface with a safe default, override in `OpenAICompatibleProvider`, and intercept in `TrackedProvider`. Never modify `llm_client.py` or `bot_runner.py` callers.

## Observe-Mode Ledger Reconciliation (Feb 21 2026)
- **Problem:** In `observe` mode, `place_market_bet()` and `submit_research_answer()` write real `MARKET_STAKE` / `RESEARCH_PAYOUT` ledger entries but both services explicitly do NOT update `Bot.balance` ("caller must do that"). In `enforce` mode the HEARTBEAT path does `bot.balance = current_balance - tick_entropy_fee - total_staked`. In `observe` mode only `bot.last_action_at` was touched, leaving `bot.balance` stale. After any tick with portfolio bets or research, `SUM(ledger.amount) != Bot.balance` — the invariant broke.
- **Fix:** In the observe-mode HEARTBEAT branch of `execute_tick()`, add: `if total_staked > Decimal('0') or research_attempted: bot.balance = current_balance - total_staked`. This syncs the cached balance with the ledger sum (entropy is phantom — deliberately excluded; stakes are real chain entries).
- **Rule:** In observe mode, entropy charges are phantom (no ledger write, no balance change). But ANY ledger entry that IS written (MARKET_STAKE, RESEARCH_PAYOUT) still drains/credits the balance. `Bot.balance` must always equal `SUM(ledger.amount)` regardless of enforcement mode.
- **SUM(boolean) crash:** `sa_func.cast(col, sa_func.Integer)` is invalid — `sa_func` is SQLAlchemy's `func` proxy, not the types module. `hasattr(sa_func, "Integer")` is always `False`, so the ternary passes a raw boolean column to `SUM()`, which PostgreSQL rejects. Fix: remove the cast from the aggregate SELECT and use a separate `COUNT(...) WHERE would_have_been_liquidated IS TRUE` query instead.
- **WS auth spam:** When `ENFORCEMENT_MODE=observe` (the default), anonymous frontend connections are legitimate viewers. Gating every connection on JWT produces log spam and no security value. Fix: compute `_WS_AUTH_REQUIRED = (mode == "enforce" AND ENV != "development")` once at module load; skip the token check when False.

## Tool Reliability — Retry/Backoff & Fee (Feb 17 2026)
- **Problem:** Wikipedia lookup was fire-once — any 429 or timeout meant a lost research opportunity for the bot.
- **Fix (v1.8.1):** `wikipedia_lookup()` retries up to 3 times with exponential backoff (base 2s) on 429 and timeout. 404 is definitive (no retry). Non-transient errors return None immediately.
- **Tool Fee:** Successful tool use costs 0.50c — written as `RESEARCH_LOOKUP_FEE` ledger entry in `execute_tick()`. The `generate_research_with_tool()` return includes `tool_fee_charged: bool` to signal the caller.
- **Rule:** Transient errors (429, timeout) always retry with backoff. Definitive errors (404, parse failure) never retry. The caller decides whether to charge a fee based on the `tool_fee_charged` flag — the tool itself is in the intelligence layer, fees are in the finance layer.
