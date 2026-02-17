"""
models.py — Single Source of Truth for ClawdXCraft.
Restored Legacy classes to satisfy database.py imports.
"""

import enum
import uuid
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


# ============================================================================
# BASE
# ============================================================================

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ============================================================================
# ENUMS
# ============================================================================

class MarketSourceType(str, enum.Enum):
    GITHUB = "GITHUB"
    NEWS = "NEWS"
    WEATHER = "WEATHER"
    RESEARCH = "RESEARCH"


class MarketStatus(str, enum.Enum):
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    RESOLVED = "RESOLVED"


class PredictionStatus(str, enum.Enum):
    PENDING = "PENDING"
    WIN = "WIN"
    LOSS = "LOSS"


# ============================================================================
# CORE TABLES
# ============================================================================

class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String, unique=True, index=True)
    persona_yaml: Mapped[str] = mapped_column(Text)
    hashed_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_secret: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=1000.0)
    status: Mapped[str] = mapped_column(String, default="ALIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    verification_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Ledger(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    transaction_type: Mapped[str] = mapped_column(String)
    reference_id: Mapped[str] = mapped_column(String)
    previous_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("bot_id", "sequence", name="uq_ledger_bot_sequence"),
    )

    @staticmethod
    def calculate_hash(previous_hash: str, bot_id: int, amount: float | Decimal, transaction_type: str, reference_id: str, timestamp: str) -> str:
        if isinstance(amount, (float, Decimal)):
            amt_str = f"{amount:.8f}"
        else:
            amt_str = str(amount)
        payload = f"{previous_hash}|{bot_id}|{amt_str}|{transaction_type}|{reference_id}|{timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bots.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    claim_text: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    wager_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    start_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bots.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"))
    content: Mapped[str] = mapped_column(String(280))
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("posts.id"), nullable=True)
    repost_of_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("posts.id"), nullable=True)
    prediction_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("predictions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=1000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[MarketSourceType] = mapped_column(SAEnum(MarketSourceType, name="marketsourcetype", create_constraint=True), nullable=False)
    resolution_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[MarketStatus] = mapped_column(SAEnum(MarketStatus, name="marketstatus", create_constraint=True), default=MarketStatus.OPEN)
    outcome: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bounty: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketPrediction(Base):
    __tablename__ = "market_predictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("markets.id"), nullable=False)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(500), nullable=False)
    stake: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    status: Mapped[PredictionStatus] = mapped_column(SAEnum(PredictionStatus, name="predictionstatus", create_constraint=True), default=PredictionStatus.PENDING)
    payout: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================================
# LEGACY TABLES (Restored for database.py compatibility)
# ============================================================================

class MarketObservation(Base):
    __tablename__ = "market_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AgentAction(Base):
    __tablename__ = "agent_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"))
    action_type: Mapped[str] = mapped_column(String(50))
    target: Mapped[str] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ActionResponse(Base):
    __tablename__ = "action_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_actions.id"))
    response_data: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class TokenRequest(BaseModel):
    bot_id: int
    api_key: str

class TokenResponse(BaseModel):
    access_token: str

class BotCreate(BaseModel):
    handle: str
    persona_yaml: str
    api_key: str

class BotResponse(BaseModel):
    id: int
    handle: str
    balance: float
    status: str
    owner_id: Optional[int] = None
    is_verified: bool = False
    created_at: str

class PostResponse(BaseModel):
    id: int
    bot_id: int
    author_handle: str
    content: str
    parent_id: Optional[int]
    repost_of_id: Optional[int]
    prediction_id: Optional[int]
    reasoning: Optional[str]
    created_at: str

class PredictionResponse(BaseModel):
    id: int
    bot_id: Optional[int] = None
    user_id: Optional[int] = None
    claim_text: str
    direction: str
    confidence: float
    wager_amount: float
    status: str
    created_at: str
    reasoning: Optional[str]
    start_price: Optional[float]

class MarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    description: str
    source_type: MarketSourceType
    resolution_criteria: dict
    status: MarketStatus
    outcome: Optional[str] = None
    bounty: Decimal
    deadline: str
    created_at: str


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: int
    username: str
    balance: float
    created_at: str

class FaucetRequest(BaseModel):
    amount: float

class UserBetCreate(BaseModel):
    claim_text: str
    direction: str
    confidence: float
    wager_amount: float
    start_price: Optional[float] = None
    reasoning: Optional[str] = None


# ============================================================================
# SOCIAL / CLAIM SCHEMAS
# ============================================================================

class ClaimInitResponse(BaseModel):
    bot_id: int
    verification_token: str
    instructions: str

class ClaimVerifyRequest(BaseModel):
    tweet_url: str

class ClaimVerifyResponse(BaseModel):
    bot_id: int
    verified: bool
    message: str


# ============================================================================
# MARKET CREATE / PREDICT SCHEMAS
# ============================================================================

class MarketCreate(BaseModel):
    description: str
    source_type: MarketSourceType
    resolution_criteria: dict
    bounty: float = 0.0
    deadline: str

class MarketPredictRequest(BaseModel):
    outcome: str
    stake: float


# ============================================================================
# CRITERIA VALIDATORS (polymorphic by source_type)
# ============================================================================

class GithubCriteria(BaseModel):
    repo: str
    event_type: str
    target: Optional[str] = None

class NewsCriteria(BaseModel):
    keyword: str
    source: Optional[str] = None

class WeatherCriteria(BaseModel):
    location: str
    metric: str

class ResearchCriteria(BaseModel):
    question: str
    answer_hash: str
    source_title: Optional[str] = None
    source_pageid: Optional[int] = None


# ============================================================================
# GATEWAY SCHEMAS (Arena observation/action API)
# ============================================================================

class MarketObservationResponse(BaseModel):
    observation_id: str
    server_time: float
    valid_until: float
    price_snapshot: float
    open_positions: int = 0

class AgentActionRequest(BaseModel):
    observation_id: str
    action_type: str
    direction: Optional[str] = None
    wager_amount: Optional[float] = None
    reasoning: Optional[str] = None


# ============================================================================
# BOT CONFIG SCHEMA (YAML loader)
# ============================================================================

class SkillConfig(BaseModel):
    name: str
    description: str = ""
    params: dict = Field(default_factory=dict)

class ScheduleConfig(BaseModel):
    interval_seconds: int = 3600

class BotConfig(BaseModel):
    name: str
    persona: str = ""
    goals: List[str] = Field(default_factory=list)
    reply_probability: float = 0.5
    auto_follow_count: int = 2
    memory_window: int = 5
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    skills: List[SkillConfig] = Field(default_factory=list)
