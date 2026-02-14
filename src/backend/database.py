from datetime import datetime, timezone
import hashlib
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("A DATABASE_URL environment variable is required.")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True)
    handle = Column(String(50), unique=True, index=True, nullable=False)
    persona_yaml = Column(Text, nullable=False)
    hashed_api_key = Column(String(128), nullable=True)
    balance = Column(Float, default=1000.0, nullable=False)
    status = Column(String(10), default="ALIVE", nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_token = Column(String(20), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    content = Column(String(280), nullable=False)
    parent_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    repost_of_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    # The Bridge: Link post to the prediction logic
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    claim_text = Column(String(500), nullable=False)
    direction = Column(String(10), nullable=False)
    confidence = Column(Float, nullable=False)
    wager_amount = Column(Float, nullable=False)
    start_price = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    status = Column(String(20), default="OPEN", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(20), nullable=False) # GRANT, WAGER, PAYOUT, SLASH
    reference_id = Column(String(100), nullable=True)
    previous_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False, unique=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def calculate_hash(prev_hash, bot_id, amount, t_type, ref_id, ts):
        data = f"{prev_hash}{bot_id}{amount}{t_type}{ref_id}{ts}"
        return hashlib.sha256(data.encode()).hexdigest()

class Hashtag(Base):
    __tablename__ = "hashtags"
    id = Column(Integer, primary_key=True)
    tag = Column(String(50), unique=True, index=True)
    post_count = Column(Integer, default=0)

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True)
    follower_bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    followee_bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Resolution(Base):
    __tablename__ = "resolutions"
    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    outcome = Column(String(10), nullable=False)
    proof_url = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    metadata_json = Column(Text, nullable=True) # JSON string
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
