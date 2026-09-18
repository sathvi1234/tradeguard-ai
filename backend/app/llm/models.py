"""Structured LLM advisory payloads."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.schemas import LLM_UNAVAILABLE


class LlmAdvisory(BaseModel):
    """Advisory-only LLM output. Cannot authorize a trade."""

    status: str = LLM_UNAVAILABLE
    provider: str = LLM_UNAVAILABLE
    model: Optional[str] = None
    advisory_only: bool = True
    summary: Optional[str] = None
    points: List[str] = Field(default_factory=list)
    cannot_override_risk: bool = True
    error: Optional[str] = None

    def to_agent_dict(self) -> dict:
        return self.model_dump()


class LLMReviewAction(str, Enum):
    VETO = "VETO"
    SHRINK = "SHRINK"
    NO_CHANGE = "NO_CHANGE"


class LLMReview(BaseModel):
    """Restricted reviewer output. Cannot approve, execute, or raise size."""

    action: str = Field(..., description="VETO, SHRINK, or NO_CHANGE")
    reason: str
    risk_flags: List[str] = Field(default_factory=list)
    suggested_reduction_pct: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    model: str = LLM_UNAVAILABLE
    timestamp: str
    advisory_only: bool = True
    can_approve: bool = False
    can_execute: bool = False
    can_increase_size: bool = False
    can_override_risk_guardian: bool = False
    fail_safe: bool = False
    status: str = "AVAILABLE"
