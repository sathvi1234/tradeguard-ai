"""Autonomous trading API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.trading.autonomous_engine import AutonomousTradingEngine
from app.risk.risk_guardian import RiskGuardian
from app.risk.drawdown_guardian import DrawdownGuardian
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/autonomous", tags=["autonomous"])

# Global autonomous engine instance
autonomous_engine = AutonomousTradingEngine(dry_run=True)  # Always paper trading


class AutoStartRequest(BaseModel):
    """Request to start autonomous trading."""
    dry_run: bool = Field(default=True, description="Simulate orders without live trading")


class CycleRequest(BaseModel):
    symbol: Optional[str] = None
    dry_run: bool = True


class CycleResponse(BaseModel):
    """Response from running a cycle."""
    model_config = {"extra": "allow"}
    cycle_id: Optional[str] = None
    cycle_number: int
    timestamp: str
    status: str
    mode: Optional[str] = None
    drawdown: Optional[str] = None
    decision: Optional[dict] = None
    order: Optional[dict] = None
    errors: list = Field(default_factory=list)
    message: Optional[str] = None
    halt_reason: Optional[str] = None


class StatusResponse(BaseModel):
    """Status response. Extra cycle fields are allowed so the debate UI can use real data."""
    model_config = {"extra": "allow"}
    running: bool
    dry_run: bool
    cycle_count: int
    last_cycle: Optional[str] = None
    current_mode: Optional[str] = None
    current_drawdown: Optional[float] = None
    positions_open: int
    portfolio: Optional[dict] = None
    last_decision: Optional[dict] = None
    last_order: Optional[str] = None
    last_rejection_reasons: list = Field(default_factory=list)
    last_red_team: Optional[dict] = None
    last_debate: Optional[dict] = None
    last_market_intelligence: Optional[dict] = None
    last_strategy_brain: Optional[list] = None
    last_cycle_status: Optional[str] = None
    last_cycle_message: Optional[str] = None
    last_halt_reason: Optional[str] = None
    last_bodyguard: Optional[dict] = None
    drawdown_guardian: Optional[dict] = None
    risk_limits: Optional[dict] = None


@router.post("/start")
async def start_autonomous_trading(request: AutoStartRequest = None) -> dict:
    """
    Start autonomous trading engine.
    
    Returns:
        Status confirmation
    """
    try:
        if request is None:
            request = AutoStartRequest()
        if request.dry_run is False:
            raise HTTPException(status_code=400, detail="DRY_RUN must remain true")
        autonomous_engine.dry_run = True
        autonomous_engine.order_executor.dry_run = True

        if autonomous_engine.running:
            raise HTTPException(
                status_code=409,
                detail="Autonomous engine already running"
            )
        
        success = await autonomous_engine.start()
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize autonomous engine"
            )
        
        logger.info("Autonomous trading started")
        
        return {
            "status": "started",
            "running": autonomous_engine.running,
            "dry_run": autonomous_engine.dry_run,
            "message": "Autonomous trading engine started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start autonomous trading: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to start autonomous trading"
        )


@router.post("/stop")
async def stop_autonomous_trading() -> dict:
    """Stop autonomous trading engine."""
    try:
        if not autonomous_engine.running:
            raise HTTPException(
                status_code=409,
                detail="Autonomous engine not running"
            )
        
        await autonomous_engine.stop()
        
        logger.info("Autonomous trading stopped")
        
        return {
            "status": "stopped",
            "running": autonomous_engine.running,
            "message": "Autonomous trading engine stopped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop autonomous trading: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to stop autonomous trading"
        )


@router.get("/status", response_model=StatusResponse)
async def get_autonomous_status() -> dict:
    """Get current autonomous trading status."""
    try:
        payload = autonomous_engine.get_status()
        payload["risk_limits"] = {
            "max_portfolio_drawdown": RiskGuardian.MAX_PORTFOLIO_DRAWDOWN,
            "max_daily_loss": RiskGuardian.MAX_DAILY_LOSS,
            "max_position_size": RiskGuardian.MAX_POSITION_SIZE,
            "max_portfolio_exposure": RiskGuardian.MAX_PORTFOLIO_EXPOSURE,
            "max_positions": RiskGuardian.MAX_POSITIONS,
            "min_confidence_score": RiskGuardian.MIN_CONFIDENCE_SCORE,
            "min_risk_reward_ratio": RiskGuardian.MIN_RISK_REWARD_RATIO,
            "min_contract_liquidity": RiskGuardian.MIN_CONTRACT_LIQUIDITY,
            "max_quote_age_seconds": RiskGuardian.MAX_QUOTE_AGE_SECONDS,
            "normal_to_protection_drawdown": DrawdownGuardian.NORMAL_TO_PROTECTION_DRAWDOWN,
            "protection_to_critical_drawdown": DrawdownGuardian.PROTECTION_TO_CRITICAL_DRAWDOWN,
        }
        return payload
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get autonomous status"
        )


@router.post("/run-cycle", response_model=CycleResponse)
async def run_autonomous_cycle(request: Optional[CycleRequest] = None) -> dict:
    """
    Run a complete autonomous trading cycle.
    
    Returns:
        Cycle result
    """
    try:
        if request and request.dry_run is False:
            raise HTTPException(status_code=400, detail="DRY_RUN must remain true")
        if not autonomous_engine.running:
            started = await autonomous_engine.start()
            if not started:
                raise HTTPException(status_code=500, detail="Failed to initialize autonomous engine")
        
        symbol = request.symbol.strip().upper() if request and request.symbol else None
        result = await autonomous_engine.run_cycle(symbol)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run cycle: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to run autonomous cycle"
        )