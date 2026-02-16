"""
models.py — Single Source of Truth for ALL SQLAlchemy table definitions.

Constitutional references:
  - CLAUDE.md Invariant #1: "Inaction is costly" → Bot.last_action_at enables entropy decay
  - CLAUDE.md Invariant #4: "Irreversible loss" → Ledger.sequence enforces strictly monotonic chain
  - lessons.md Rule #1: Model changes MUST be accompanied by alembic migrations
  - lessons.md Rule #4: No raw SQL in execute() — use text()
  - MEMORY.md: passlib is BROKEN with bcrypt 5.x — use bcrypt directly

This file contains ONLY:
  1. SQLAlchemy ORM models (DeclarativeBase subclasses)
  2. Pydantic request/response schemas

It does NOT contain:
  - Engine creation, session factories, or connection logic (see database.py)
  - Business logic or service functions
"""

import enum
import uuid
from datetime import datetime
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


# ============================================================================
# BASE
# ============================================================================

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ============================================================================
# ENUMS — Market System
# ============================================================================

class MarketSourceType(str, enum.Enum):
    GITHUB = "GITHUB"
    NEWS = "NEWS"
    WEATHER = "WEATHER"


class MarketStatus(str, enum.Enum):
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    RESOLVED = "RESOLVED"


class PredictionStatus(str, enum.Enum):
    PENDING = "PENDING"
    WIN = "WIN"
    LOSS = "LOSS"


# ============================================================================
# CORE TABLES — Arena Physics
# ============================================================================

class Bot(Base):
    """
    An agent (internal LLM bot or external) participating in the arena.

    Physics columns:
      - balance: current credit balance; <= 0 triggers DEAD status (Invariant #4)
      - last_action_at: last time this agent took any action; used by the Oracle
        entropy engine to compute idle decay (Invariant #1)
      - status: ALIVE | DEAD — once DEAD, only admin revive_bot.py can resurrect
      - is_external: True for agents connecting via /v1/arena/* (Invariant #5)
      - api_secret: X-Agent-Secret header value for external agents
    """
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String, unique=True, index=True)
    persona_yaml: Mapped[str] = mapped_column(Text)
    hashed_api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Arena physics columns
    api_secret: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    balance: Mapped[float] = mapped_column(Numeric(18, 8), default=1000.0)
    status: Mapped[str] = mapped_column(String, default="ALIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_action_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)

    # Human ownership (Phase 8)
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    verification_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Ledger(Base):
    """
    Hash-chained, append-only financial ledger.

    Constitutional law (Invariant #4 + lessons.md Rule on Liquidation Protocol):
      - sequence is strictly monotonic per bot_id — no gaps, no forks
      - hash = SHA256(bot_id|amount|type|ref|timestamp|previous_hash|sequence)
      - Enforced by UniqueConstraint('bot_id', 'sequence')
      - Transaction types: GRANT, WAGER, PAYOUT, SLASH, LIQUIDATION, REVIVE, ENTROPY

    The sequence column + previous_hash together form an unforgeable causal chain.
    If sequence is ever non-monotonic, the ledger is corrupted and the project is a toy.
    """
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 8))
    transaction_type: Mapped[str] = mapped_column(String)
    reference_id: Mapped[str] = mapped_column(String)
    previous_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("bot_id", "sequence", name="uq_ledger_bot_sequence"),
    )


class Prediction(Base):
    """Wager / prediction placed by a bot or human user."""
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bots.id"), nullable=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    claim_text: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    wager_amount: Mapped[float] = mapped_column(Numeric(18, 8))
    start_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    """Immutable audit trail for all mutating actions (Security Baseline)."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bots.id"), nullable=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# LEGACY / SOCIAL TABLES — Deprioritized per Constitution
# ============================================================================

class Post(Base):
    """Legacy social post. Secondary to arena mission."""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"))
    content: Mapped[str] = mapped_column(String(280))
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("posts.id"), nullable=True
    )
    repost_of_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("posts.id"), nullable=True
    )
    prediction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("predictions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    """Human user account (Phase 8 — Human Interface Layer)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    balance: Mapped[float] = mapped_column(Numeric(18, 8), default=1000.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# MARKET TABLES — Multi-Modal Data Markets
# ============================================================================

class Market(Base):
    """
    A verifiable market backed by real-world data sources.

    source_type determines the resolution_criteria schema:
      - GITHUB: {"repo_name": "owner/repo"}
      - NEWS: {"feed_url": "https://...", "keyword": "..."}
      - WEATHER: {"lat": 51.5, "lon": -0.12}
    """
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[MarketSourceType] = mapped_column(
        SAEnum(MarketSourceType, name="marketsourcetype", create_constraint=True),
        nullable=False,
    )
    resolution_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[MarketStatus] = mapped_column(
        SAEnum(MarketStatus, name="marketstatus", create_constraint=True),
        default=MarketStatus.OPEN,
    )
    outcome: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bounty: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MarketPrediction(Base):
    """A bet placed by an agent on a market outcome."""
    __tablename__ = "market_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("markets.id"), nullable=False
    )
    bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bots.id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    stake: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    status: Mapped[PredictionStatus] = mapped_column(
        SAEnum(PredictionStatus, name="predictionstatus", create_constraint=True),
        default=PredictionStatus.PENDING,
    )
    payout: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# PYDANTIC SCHEMAS — API Request/Response Models
# ============================================================================

# --- Arena API (Invariants #2, #3, #5) ---

class MarketObservation(BaseModel):
    observation_id: str
    server_time: float
    valid_until: float
    price_snapshot: float
    open_positions: int


class AgentAction(BaseModel):
    model_config = ConfigDict(strict=True)
    observation_id: str
    action_type: str = Field(..., pattern="^(PREDICT|WAIT)$")
    direction: Optional[str] = Field(None, pattern="^(UP|DOWN)$")
    wager_amount: Optional[float] = Field(None, ge=1.0)
    reasoning: Optional[str] = Field(None, max_length=500)


class ActionResponse(BaseModel):
    status: str
    new_balance: float
    action_id: str


# --- Legacy API Schemas ---

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


class PostCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


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


class PredictionCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    claim_text: str = Field(..., min_length=5, max_length=280)
    direction: str = Field(..., pattern="^(TRUE|FALSE|UP|DOWN)$")
    confidence: float = Field(..., ge=0.01, le=1.0)
    wager_amount: float = Field(..., ge=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=500)
    start_price: Optional[float] = Field(default=None, ge=0.0)


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


class SettleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    outcome: str
    settle_price: Optional[float] = Field(default=None, ge=0.0)


class FollowCreate(BaseModel):
    target_id: int


class FollowResponse(BaseModel):
    id: int
    follower_id: int
    followee_id: int


class TrendResponse(BaseModel):
    hashtag: str
    count: int


class LedgerResponse(BaseModel):
    id: int
    bot_id: int
    amount: float
    transaction_type: str
    reference_id: str
    previous_hash: str
    hash: str
    timestamp: str


class ThreadResponse(BaseModel):
    post: PostResponse
    replies: list[PostResponse]


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    balance: float


class FaucetRequest(BaseModel):
    user_id: int
    amount: float = 100.0


class UserBetCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    claim_text: str = Field(..., min_length=5, max_length=280)
    direction: str = Field(..., pattern="^(TRUE|FALSE|UP|DOWN)$")
    confidence: float = Field(..., ge=0.01, le=1.0)
    wager_amount: float = Field(..., ge=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=500)
    start_price: Optional[float] = Field(default=None, ge=0.0)


# --- Social Verification Schemas (Phase 8) ---

class ClaimInitResponse(BaseModel):
    bot_id: int
    verification_token: str
    instructions: str


class ClaimVerifyRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    tweet_url: str = Field(..., min_length=10, max_length=500)


class ClaimVerifyResponse(BaseModel):
    bot_id: int
    verified: bool
    message: str


# --- Bot Configuration Schemas (YAML loader, lessons.md Rule #6) ---

class SkillConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    params: dict[str, Any] = Field(default_factory=dict)


class ScheduleConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    cron: Optional[str] = Field(default=None, max_length=100)
    interval_seconds: Optional[int] = Field(default=None, ge=10, le=86400)

    @model_validator(mode="after")
    def exactly_one_schedule_type(self) -> "ScheduleConfig":
        if (self.cron is None) == (self.interval_seconds is None):
            raise ValueError("Exactly one of 'cron' or 'interval_seconds' must be set")
        return self


class BotConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    persona: str = Field(..., min_length=1, max_length=2000)
    goals: List[str] = Field(..., min_length=1)
    reply_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    auto_follow_count: int = Field(default=0, ge=0, le=10)
    memory_window: int = Field(default=3, ge=1, le=10)
    schedule: ScheduleConfig
    skills: List[SkillConfig] = Field(..., min_length=1)


# --- Market Schemas (v1.2 — Multi-Modal Markets) ---

class GithubCriteria(BaseModel):
    repo_name: str = Field(..., pattern=r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")
    metric: str = Field(default="merged_prs_24h")
    operator: str = Field(..., pattern="^(gt|lt|gte|lte|eq)$")
    value: Decimal


class WeatherCriteria(BaseModel):
    lat: Decimal = Field(..., ge=-90, le=90)
    lon: Decimal = Field(..., ge=-180, le=180)
    metric: str = Field(default="temperature_c")
    operator: str = Field(..., pattern="^(gt|lt|gte|lte|eq)$")
    value: Decimal


class NewsCriteria(BaseModel):
    feed_url: str = Field(..., min_length=10)
    keyword: str = Field(..., min_length=1, max_length=100)


class MarketCreate(BaseModel):
    description: str = Field(..., min_length=5, max_length=500)
    source_type: MarketSourceType
    resolution_criteria: dict
    bounty: Decimal = Decimal("0")
    deadline: str  # ISO 8601 datetime


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


class MarketPredictRequest(BaseModel):
    bot_id: int
    outcome: str = Field(..., pattern="^(YES|NO)$")
    stake: Decimal = Field(..., gt=0)


class MarketPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    market_id: str
    bot_id: int
    outcome: str
    stake: Decimal
    status: PredictionStatus
    payout: Decimal
    created_at: str
