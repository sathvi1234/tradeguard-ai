"""Position manager - tracks open positions and exit rules."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.utils.logging import get_logger

logger = get_logger(__name__)


class PositionStatus(str, Enum):
    """Position status."""
    OPEN = "open"
    EXITING = "exiting"
    CLOSED = "closed"


@dataclass
class Position:
    """Options position."""
    position_id: str
    symbol: str
    option_type: str  # call or put
    strike: float
    expiration: str
    quantity: int
    entry_price: float
    entry_date: datetime
    
    current_price: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    exit_reason: Optional[str] = None
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    
    # Greeks and risk
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0
    
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.status == PositionStatus.CLOSED:
            return (self.exit_price or 0) - self.entry_price
        return self.current_price - self.entry_price
    
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.entry_price <= 0:
            return 0.0
        return self.unrealized_pnl() / self.entry_price
    
    def total_exposure(self) -> float:
        """Calculate total position exposure ($)."""
        return self.current_price * self.quantity * 100
    
    def max_loss(self) -> float:
        """Calculate maximum possible loss."""
        if self.option_type == "call":
            return self.entry_price * self.quantity * 100
        else:  # put
            return (self.strike - self.entry_price) * self.quantity * 100
    
    def days_to_expiration(self) -> float:
        """Calculate days until expiration."""
        expiration = datetime.strptime(self.expiration, "%Y-%m-%d")
        days = (expiration - datetime.utcnow()).days
        return max(0, days)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiration": self.expiration,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "entry_date": self.entry_date.isoformat(),
            "status": self.status.value,
            "unrealized_pnl": self.unrealized_pnl(),
            "unrealized_pnl_pct": self.unrealized_pnl_pct() * 100,
            "total_exposure": self.total_exposure(),
            "max_loss": self.max_loss(),
            "days_to_expiration": self.days_to_expiration(),
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "iv": self.iv,
        }


class PositionManager:
    """Manages open positions and exit rules."""
    
    def __init__(self):
        """Initialize position manager."""
        self.logger = logger
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
    
    def add_position(
        self,
        position_id: str,
        symbol: str,
        option_type: str,
        strike: float,
        expiration: str,
        quantity: int,
        entry_price: float,
    ) -> Position:
        """Add new position."""
        position = Position(
            position_id=position_id,
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            entry_price=entry_price,
            entry_date=datetime.utcnow(),
            current_price=entry_price,
        )
        
        self.positions[position_id] = position
        
        self.logger.info(
            "Position added",
            position_id=position_id,
            symbol=symbol,
            quantity=quantity,
        )
        
        return position
    
    def update_position_price(
        self,
        position_id: str,
        current_price: float,
    ) -> Optional[Position]:
        """Update current market price of position."""
        position = self.positions.get(position_id)
        
        if not position:
            return None
        
        old_price = position.current_price
        position.current_price = current_price
        
        pnl_pct = position.unrealized_pnl_pct() * 100
        
        self.logger.debug(
            "Position price updated",
            position_id=position_id,
            old_price=old_price,
            new_price=current_price,
            pnl_pct=pnl_pct,
        )
        
        return position
    
    def should_exit_position(
        self,
        position_id: str,
        max_loss_pct: float = 0.50,  # 50% loss
        take_profit_pct: float = 0.50,  # 50% profit
        days_to_exp_threshold: int = 7,  # Exit if 7 days to expiration
        critical_mode: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if position should be exited.
        
        Returns:
            Tuple of (should_exit, reason)
        """
        position = self.positions.get(position_id)
        
        if not position:
            return False, None
        
        # Critical mode - exit all positions
        if critical_mode:
            return True, "Critical drawdown mode"
        
        pnl_pct = position.unrealized_pnl_pct()
        
        # Maximum loss rule
        if pnl_pct <= -max_loss_pct:
            return True, f"Maximum loss reached: {pnl_pct:.1%}"
        
        # Take profit rule
        if pnl_pct >= take_profit_pct:
            return True, f"Take profit target reached: {pnl_pct:.1%}"
        
        # Expiration proximity rule
        dte = position.days_to_expiration()
        if dte <= days_to_exp_threshold:
            return True, f"Approaching expiration: {dte} days"
        
        return False, None
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str,
    ) -> Optional[Position]:
        """Close a position."""
        position = self.positions.get(position_id)
        
        if not position:
            return None
        
        position.status = PositionStatus.CLOSED
        position.exit_price = exit_price
        position.exit_date = datetime.utcnow()
        position.exit_reason = reason
        
        # Move to closed list
        del self.positions[position_id]
        self.closed_positions.append(position)
        
        realized_pnl = (exit_price - position.entry_price) * position.quantity * 100
        
        self.logger.info(
            "Position closed",
            position_id=position_id,
            symbol=position.symbol,
            realized_pnl=realized_pnl,
            reason=reason,
        )
        
        return position
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self.positions.get(position_id)
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())
    
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions."""
        return self.closed_positions
    
    def get_total_exposure(self) -> float:
        """Get total portfolio exposure from positions."""
        return sum(p.total_exposure() for p in self.positions.values())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L."""
        return sum(p.unrealized_pnl() for p in self.positions.values())