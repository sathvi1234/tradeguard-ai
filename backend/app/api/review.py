"""Restricted LLM review APIs. Never execute. Risk Guardian is final."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.models.enums import TradingMode
from app.risk.review_pipeline import last_review_pipeline, run_review_pipeline
from app.risk.risk_guardian import RiskGuardian
from app.trading.audit_logger import AuditLogger

router = APIRouter(prefix="/api/v1/review", tags=["llm-review"])
_guardian = RiskGuardian()
_audit = AuditLogger()


class ReviewRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    proposed_size: float = Field(..., gt=0, le=100000)
    quantity: Optional[int] = Field(default=None, ge=0)
    portfolio_value: float = Field(100000.0, gt=0)
    current_drawdown: float = Field(0.0, ge=0, le=1)
    current_positions: int = Field(0, ge=0)
    ai_confidence: float = Field(0.8, ge=0, le=1)
    trading_mode: str = "normal"
    market_closed: bool = False
    integrity_state: Optional[str] = None
    skip_quote_age: bool = True


@router.get("/last")
async def get_last_review() -> dict:
    payload = last_review_pipeline() or {}
    return {
        "review": payload,
        "live_trading": False,
        "llm_is_final_authority": False,
        "risk_guardian_is_final_authority": True,
    }


@router.post("/run")
async def run_review(request: ReviewRequest) -> dict:
    mode = TradingMode.CRITICAL if request.trading_mode.lower() == "critical" else TradingMode.NORMAL
    rg_kwargs: Dict[str, Any] = {
        "portfolio_value": request.portfolio_value,
        "current_equity": request.portfolio_value,
        "current_drawdown": request.current_drawdown,
        "current_positions": request.current_positions,
        "max_loss": request.proposed_size,
        "potential_reward": request.proposed_size,
        "ai_confidence": request.ai_confidence,
        "contract_validity": {"is_liquid": True, "open_interest": 1000, "instrument": "equity"},
        "market_data_timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
        "trading_mode": mode,
        "skip_quote_age": False if request.integrity_state == "DATA_STALE" else request.skip_quote_age,
        "market_closed": request.market_closed,
        "integrity_state": request.integrity_state,
    }
    pipeline = await run_review_pipeline(
        guardian=_guardian,
        symbol=request.symbol.upper(),
        proposed_size=request.proposed_size,
        rg_kwargs=rg_kwargs,
        audit=_audit,
        quantity=request.quantity,
        proposal={
            "symbol": request.symbol.upper(),
            "proposed_size": request.proposed_size,
            "quantity": request.quantity,
        },
    )
    pipeline["dry_run"] = settings.dry_run
    pipeline["live_trading"] = False
    pipeline["can_execute"] = False
    pipeline["note"] = "Visualization / research only. This endpoint never submits orders."
    return pipeline
