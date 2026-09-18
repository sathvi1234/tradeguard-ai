"""DrawdownGuardian - Tracks equity and manages trading modes."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

from app.models import TradingMode
from app.utils.logging import get_logger, log_risk_event

logger = get_logger(__name__)


@dataclass
class DrawdownGuardianState:
    """Current drawdown state."""
    starting_equity: float
    peak_equity: float
    current_equity: float
    total_pnl: float
    daily_pnl: float
    drawdown_percentage: float
    current_mode: TradingMode
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "starting_equity": self.starting_equity,
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "total_pnl": self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "drawdown_percentage": self.drawdown_percentage,
            "current_mode": self.current_mode.value,
        }


@dataclass
class ModeTransition:
    """Record of a mode transition."""
    previous_mode: TradingMode
    new_mode: TradingMode
    equity: float
    drawdown: float
    reason: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "previous_mode": self.previous_mode.value,
            "new_mode": self.new_mode.value,
            "equity": self.equity,
            "drawdown": self.drawdown,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class DrawdownGuardian:
    """
    Mathematically-driven drawdown tracking and mode management.
    
    Modes:
    - NORMAL: Normal trading
    - PROTECTION: Reduced position sizes, higher confidence required
    - CRITICAL: All new trades blocked
    
    Mode transitions are calculated, not overridable by LLM.
    """
    
    # Mode transition thresholds
    NORMAL_TO_PROTECTION_DRAWDOWN = 0.10  # 10% drawdown triggers PROTECTION
    PROTECTION_TO_CRITICAL_DRAWDOWN = 0.15  # 15% drawdown triggers CRITICAL
    
    def __init__(self):
        """Initialize DrawdownGuardian."""
        self.logger = logger
        self.state: Optional[DrawdownGuardianState] = None
        self.transitions: List[ModeTransition] = []
    
    def initialize(self, starting_equity: float) -> DrawdownGuardianState:
        """
        Initialize drawdown tracking with starting equity.
        
        Args:
            starting_equity: Starting portfolio equity
            
        Returns:
            Initial DrawdownGuardianState
        """
        self.state = DrawdownGuardianState(
            starting_equity=starting_equity,
            peak_equity=starting_equity,
            current_equity=starting_equity,
            total_pnl=0.0,
            daily_pnl=0.0,
            drawdown_percentage=0.0,
            current_mode=TradingMode.NORMAL
        )
        
        logger.info(
            "DrawdownGuardian initialized",
            starting_equity=starting_equity
        )
        
        return self.state
    
    async def update(
        self,
        current_equity: float,
        daily_pnl: float
    ) -> DrawdownGuardianState:
        """
        Update equity state and check for mode transitions.
        
        Args:
            current_equity: Current portfolio equity
            daily_pnl: Daily profit/loss
            
        Returns:
            Updated DrawdownGuardianState
        """
        if not self.state:
            raise RuntimeError("DrawdownGuardian not initialized")
        
        timestamp = datetime.utcnow()
        
        # Update equity values
        self.state.current_equity = current_equity
        self.state.daily_pnl = daily_pnl
        self.state.total_pnl = current_equity - self.state.starting_equity
        
        # Update peak equity
        if current_equity > self.state.peak_equity:
            self.state.peak_equity = current_equity
        
        # Calculate drawdown
        if self.state.peak_equity > 0:
            self.state.drawdown_percentage = (
                (self.state.peak_equity - current_equity) / self.state.peak_equity
            )
        else:
            self.state.drawdown_percentage = 0.0
        
        # Check for mode transition
        new_mode = self._calculate_mode(
            self.state.drawdown_percentage,
            self.state.current_mode
        )
        
        if new_mode != self.state.current_mode:
            # Record transition
            reason = self._get_transition_reason(
                self.state.current_mode,
                new_mode,
                self.state.drawdown_percentage
            )
            
            transition = ModeTransition(
                previous_mode=self.state.current_mode,
                new_mode=new_mode,
                equity=current_equity,
                drawdown=self.state.drawdown_percentage,
                reason=reason,
                timestamp=timestamp
            )
            
            self.transitions.append(transition)
            self.state.current_mode = new_mode
            
            # Log transition
            self._log_transition(transition)
        
        return self.state
    
    def _calculate_mode(
        self,
        drawdown_pct: float,
        current_mode: TradingMode
    ) -> TradingMode:
        """
        Calculate trading mode based on drawdown.
        
        This is purely mathematical - no LLM override.
        
        Args:
            drawdown_pct: Current drawdown percentage
            current_mode: Current trading mode
            
        Returns:
            New trading mode
        """
        # Check for mode escalation
        if drawdown_pct >= self.PROTECTION_TO_CRITICAL_DRAWDOWN:
            return TradingMode.CRITICAL
        elif drawdown_pct >= self.NORMAL_TO_PROTECTION_DRAWDOWN:
            return TradingMode.PROTECTION
        else:
            return TradingMode.NORMAL
    
    def _get_transition_reason(
        self,
        previous_mode: TradingMode,
        new_mode: TradingMode,
        drawdown_pct: float
    ) -> str:
        """Build reason string for mode transition."""
        if previous_mode == TradingMode.NORMAL and new_mode == TradingMode.PROTECTION:
            return f"Drawdown reached {drawdown_pct:.2%} - entering PROTECTION mode"
        elif previous_mode == TradingMode.PROTECTION and new_mode == TradingMode.CRITICAL:
            return f"Drawdown reached {drawdown_pct:.2%} - entering CRITICAL mode"
        elif new_mode == TradingMode.NORMAL:
            return f"Drawdown reduced to {drawdown_pct:.2%} - returning to NORMAL mode"
        else:
            return f"Mode transition: {previous_mode.value} -> {new_mode.value}"
    
    def _log_transition(self, transition: ModeTransition) -> None:
        """Log mode transition as risk event."""
        severity = "high" if transition.new_mode == TradingMode.CRITICAL else "medium"
        
        log_risk_event(
            f"trading_mode_transition",
            severity,
            {
                "previous_mode": transition.previous_mode.value,
                "new_mode": transition.new_mode.value,
                "equity": transition.equity,
                "drawdown": transition.drawdown,
                "reason": transition.reason,
            }
        )
    
    def get_state(self) -> Optional[DrawdownGuardianState]:
        """Get current state."""
        return self.state
    
    def get_transitions(self) -> List[ModeTransition]:
        """Get all mode transitions."""
        return self.transitions
    
    def reset_daily_pnl(self) -> None:
        """Reset daily P&L (called at end of trading day)."""
        if self.state:
            self.state.daily_pnl = 0.0