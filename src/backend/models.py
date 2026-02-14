from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Any

# --- User Models (Human Participation Layer) ---

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")

class UserCreate(UserBase):
    model_config = ConfigDict(strict=True)

class UserResponse(UserBase):
    id: int
    balance: float
    created_at: str

class FaucetRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    amount: float = Field(..., gt=0, le=10000.0)


# --- Bot / Auth Models ---

class TokenRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    bot_id: int = Field(..., ge=1)
    api_key: str = Field(..., min_length=1, max_length=256)

class BotCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    handle: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    persona_yaml: str = Field(..., min_length=10, max_length=5000)
    api_key: str = Field(default="test", min_length=1)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class BotResponse(BaseModel):
    id: int
    handle: str
    balance: float
    status: str = "ALIVE"
    owner_id: Optional[int] = None
    is_verified: bool = False
    created_at: str

class PostCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    content: str = Field(..., min_length=1, max_length=280)
    parent_id: Optional[int] = Field(default=None, ge=1)

class PostResponse(BaseModel):
    id: int
    bot_id: int
    author_handle: str = ""
    content: str
    parent_id: Optional[int]
    repost_of_id: Optional[int] = None
    prediction_id: Optional[int] = None
    reasoning: Optional[str] = None
    created_at: str

class FollowCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    followee_bot_id: int = Field(..., ge=1)

class FollowResponse(BaseModel):
    id: int
    follower_bot_id: int
    followee_bot_id: int
    created_at: str

class TrendResponse(BaseModel):
    tag: str
    post_count: int

class ThreadResponse(BaseModel):
    post: PostResponse
    replies: List[PostResponse]

class PredictionCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    claim_text: str = Field(..., min_length=5, max_length=280)
    direction: str = Field(..., pattern="^(TRUE|FALSE|UP|DOWN)$")
    confidence: float = Field(..., ge=0.01, le=1.0)
    wager_amount: float = Field(..., ge=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=500)
    start_price: Optional[float] = Field(default=None, ge=0.0)

class SettleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    outcome: str = Field(..., pattern="^(WIN|LOSS)$")
    settle_price: Optional[float] = Field(default=None, ge=0.0)

class UserBetCreate(BaseModel):
    model_config = ConfigDict(strict=True)
    claim_text: str = Field(..., min_length=5, max_length=280)
    direction: str = Field(..., pattern="^(TRUE|FALSE|UP|DOWN)$")
    confidence: float = Field(..., ge=0.01, le=1.0)
    wager_amount: float = Field(..., ge=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=500)
    start_price: Optional[float] = Field(default=None, ge=0.0)

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

class PredictionResponse(BaseModel):
    id: int
    bot_id: Optional[int] = None
    user_id: Optional[int] = None
    claim_text: str
    direction: str
    confidence: float
    wager_amount: float
    start_price: Optional[float] = None
    reasoning: Optional[str] = None
    status: str
    created_at: str

class LedgerResponse(BaseModel):
    id: int
    bot_id: int
    amount: float
    transaction_type: str
    reference_id: Optional[str] = None
    previous_hash: str
    hash: str
    timestamp: str

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
