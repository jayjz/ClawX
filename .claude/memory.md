# memory.md: Persistent Context Across Prompts

- Project Name: ClawdXCraft (bot-focused X/Twitter clone).
- Stack: FastAPI backend, React frontend, PostgreSQL+Redis DB.
- Goals: Rush to MVP launch in 4-6 weeks, bot-to-bot interactions.
- Prior Outputs: Architecture diagram, API endpoints, DB schema.
- Current Phase: Phase 2 backend skeleton complete.
- Phase 2 delivers: app.py (3 endpoints + rate limit), models.py (Pydantic v2), database.py (async SQLAlchemy ORM).
- Auth is stub (token = bot_id string). Real JWT in Phase 3.
- PostgreSQL access resolved: dedicated role `clawd_claude` with password auth (no sudo/peer needed).
- DB `clawdxcraft` exists. Schema initialized via `init_db()`. Tables: `bots`, `posts`, `audit_log` — verified.
- DSN: `postgresql+asyncpg://clawd_claude:clawd_claude_dev_2026@localhost:5432/clawdxcraft` (in .env as DATABASE_URL).
- Standalone init script: `src/backend/init_db.py` (idempotent, safe to re-run).
- Phase 3 planned: Auth upgraded to real PyJWT (HS256), all 10 endpoints designed, tests stubbed.
- New tables planned: `follows` (UniqueConstraint), `hashtags` (tag+post_count). Post gets `repost_of_id`.
- New files: `utils/jwt.py`, `tests/backend/conftest.py`, `tests/backend/test_api.py`.
- Implementation order: jwt.py → database.py → models.py → app.py → tests.
- Next: Implement Phase 3.
