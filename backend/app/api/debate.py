"""Debate API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.autonomous.debate_engine import DebateEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/debate", tags=["debate"])

# Global debate engine instance
debate_engine = DebateEngine()


class DebateRequest(BaseModel):
    """Request to run a debate."""
    symbol: str = Field(..., description="Stock symbol")
    option_type: str = Field(default="call", description="'call' or 'put'")
    strike: Optional[float] = Field(default=None, description="Strike price")
    expiration: Optional[str] = Field(default=None, description="Expiration date (YYYY-MM-DD)")
    portfolio_value: float = Field(default=100000.0, description="Portfolio value in USD")
    current_equity: float = Field(default=100000.0, description="Current equity in USD")
    current_positions: int = Field(default=0, description="Number of open positions")
    current_drawdown: float = Field(default=0.0, description="Current drawdown percentage (0.0-1.0)")


class DebateResponse(BaseModel):
    """Response from a debate."""
    debate_id: str
    timestamp: str
    symbol: str
    completed: bool
    agent_outputs: dict
    agent_errors: dict
    final_decision: Optional[dict]
    risk_guardian_result: Optional[dict]


@router.post("/run", response_model=dict)
async def run_debate(request: DebateRequest) -> dict:
    """
    Run complete debate for a trading opportunity.
    
    Executes all agents in sequence:
    1. Market Scout
    2. Options Analyst
    3. Bull Agent
    4. Bear Agent
    5. Options Strategy Agent
    6. Risk Agent
    7. Decision Agent
    8. Risk Guardian (deterministic final gate)
    
    Returns:
        Debate result with debate_id for tracking
    """
    try:
        logger.info(f"Starting debate request for {request.symbol}")
        
        # Run debate
        result = await debate_engine.run_debate(
            symbol=request.symbol,
            option_type=request.option_type,
            strike=request.strike,
            expiration=request.expiration,
            portfolio_value=request.portfolio_value,
            current_equity=request.current_equity,
            current_positions=request.current_positions,
            current_drawdown=request.current_drawdown,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Debate request failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Debate execution failed: {str(e)}"
        )


@router.get("/{debate_id}", response_model=dict)
async def get_debate(debate_id: str) -> dict:
    """
    Get debate result by ID.
    
    Args:
        debate_id: Debate ID from run response
        
    Returns:
        Debate result with all agent outputs
    """
    try:
        result = debate_engine.get_debate(debate_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Debate not found: {debate_id}"
            )
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve debate {debate_id}", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve debate"
        )


@router.get("/", response_model=list)
async def list_debates(symbol: Optional[str] = Query(None, description="Filter by symbol")) -> list:
    """
    List all debates, optionally filtered by symbol.
    
    Args:
        symbol: Optional symbol filter
        
    Returns:
        List of debate results
    """
    try:
        debates = debate_engine.get_all_debates(symbol=symbol)
        return [d.to_dict() for d in debates]
        
    except Exception as e:
        logger.error(f"Failed to list debates", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to list debates"
        )