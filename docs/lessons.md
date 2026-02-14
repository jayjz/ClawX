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
