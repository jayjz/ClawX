import asyncio
import os
import sys
from typing import AsyncGenerator

# 1. SETUP ENVIRONMENT FIRST (Before any app/database imports)
TEST_DB_NAME = "test_clawdxcraft"
BASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://clawd_claude:clawd_claude_dev_2026@localhost:5432/clawdxcraft")
TEST_DATABASE_URL = BASE_URL.replace("/clawdxcraft", f"/{TEST_DB_NAME}")
MAINTENANCE_URL = BASE_URL.replace("/clawdxcraft", "/postgres")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test_secret"
os.environ["BOT_API_KEY"] = "test_global_key"

# 2. Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/backend')))

# 3. NOW IMPORT LOCAL MODULES
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database import Base, get_session
from app import app

@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest-asyncio's default function-scoped loop with a session-scoped one."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Creates the test database and schema once per session."""
    # Connect to Maintenance DB to Create DB
    m_engine = create_async_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
    async with m_engine.connect() as conn:
        await conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid();"))
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await m_engine.dispose()

    # Connect to Test DB to Create Tables
    t_engine = create_async_engine(TEST_DATABASE_URL)
    async with t_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    await t_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional session that rolls back after every test."""
    engine = create_async_engine(TEST_DATABASE_URL)
    connection = await engine.connect()
    trans = await connection.begin()
    
    Session = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    
    await trans.rollback()
    await connection.close()
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Wired httpx client using the transactional session."""
    async def _get_session_override():
        yield db_session

    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def bot_and_token(db_session: AsyncSession):
    """Generates a real bot in the test DB for auth testing."""
    from utils.jwt import create_access_token
    import bcrypt
    from database import Bot

    api_key = "test_key"
    hashed = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
    
    bot = Bot(handle="test_trader", persona_yaml="persona: test", hashed_api_key=hashed)
    db_session.add(bot)
    await db_session.flush() 
    
    token = create_access_token(bot.id)
    return {"bot_id": bot.id, "api_key": api_key, "headers": {"Authorization": f"Bearer {token}"}}
