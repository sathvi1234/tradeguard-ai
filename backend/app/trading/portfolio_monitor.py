"""Portfolio monitor - tracks portfolio metrics and health."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio state."""
    timestamp: datetime
    account_value: float
    cash: float
    buying_power: float
    portfolio_value: float
    
    # Positions
    positions_count: int = 0
    position_exposure: float = 0.0
    
    # P&L metrics
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    
    # Risk metrics
    peak_equity: float = 0.0
    current_equity: float = 0.0
    drawdown_pct: float = 0.0
    
    # Historical data
    previous_close_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "account_value": self.account_value,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "portfolio_value": self.portfolio_value,
            "positions_count": self.positions_count,
            "position_exposure": self.position_exposure,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "drawdown_pct": self.drawdown_pct * 100,
        }


class PortfolioMonitor:
    """Monitors portfolio and tracks metrics."""
    
    def __init__(self):
        """Initialize portfolio monitor."""
        self.logger = logger
        self.snapshots: List[PortfolioSnapshot] = []
        self.starting_balance: Optional[float] = None
        self.peak_value: float = 0.0
    
    def initialize(self, starting_balance: float) -> None:
        """Initialize with starting balance."""
        self.starting_balance = starting_balance
        self.peak_value = starting_balance
        self.logger.info(f"Portfolio monitor initialized: ${starting_balance:,.2f}")
    
    def create_snapshot(
        self,
        account_value: float,
        cash: float,
        buying_power: float,
        positions_count: int = 0,
        position_exposure: float = 0.0,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
    ) -> PortfolioSnapshot:
        """
        Create portfolio snapshot.
        
        Args:
            account_value: Total account value
            cash: Available cash
            buying_power: Buying power
            positions_count: Number of open positions
            position_exposure: Total position exposure
            realized_pnl: Realized P&L
            unrealized_pnl: Unrealized P&L
            
        Returns:
            PortfolioSnapshot
        """
        portfolio_value = account_value - cash
        total_pnl = realized_pnl + unrealized_pnl
        
        # Update peak value
        if account_value > self.peak_value:
            self.peak_value = account_value
        
        # Calculate drawdown
        if self.peak_value > 0:
            drawdown = (self.peak_value - account_value) / self.peak_value
        else:
            drawdown = 0.0
        
        # Calculate daily P&L (from previous snapshot if exists)
        daily_pnl = 0.0
        if self.snapshots:
            daily_pnl = account_value - self.snapshots[-1].account_value
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            account_value=account_value,
            cash=cash,
            buying_power=buying_power,
            portfolio_value=portfolio_value,
            positions_count=positions_count,
            position_exposure=position_exposure,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            peak_equity=self.peak_value,
            current_equity=account_value,
            drawdown_pct=drawdown,
        )
        
        self.snapshots.append(snapshot)
        
        self.logger.info(
            "Portfolio snapshot",
            account_value=account_value,
            cash=cash,
            total_pnl=total_pnl,
            drawdown_pct=f"{drawdown:.1%}",
        )
        
        return snapshot
    
    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Get most recent snapshot."""
        return self.snapshots[-1] if self.snapshots else None
    
    def get_snapshots(
        self,
        limit: Optional[int] = None,
    ) -> List[PortfolioSnapshot]:
        """Get snapshots, optionally limited to most recent."""
        if limit:
            return self.snapshots[-limit:]
        return self.snapshots
    
    def get_portfolio_stats(self) -> Dict[str, Any]:
        """Get portfolio statistics."""
        if not self.snapshots:
            return {}
        
        latest = self.snapshots[-1]
        
        # Calculate average daily return
        if len(self.snapshots) > 1:
            days = len(self.snapshots)
            total_return = (latest.account_value - self.snapshots[0].account_value)
            avg_daily = total_return / days if days > 0 else 0
        else:
            avg_daily = 0
        
        return {
            "current_value": latest.account_value,
            "peak_value": latest.peak_equity,
            "starting_value": self.snapshots[0].account_value if self.snapshots else 0,
            "total_pnl": latest.total_pnl,
            "realized_pnl": latest.realized_pnl,
            "unrealized_pnl": latest.unrealized_pnl,
            "drawdown": latest.drawdown_pct,
            "daily_pnl": latest.daily_pnl,
            "avg_daily_pnl": avg_daily,
            "positions_count": latest.positions_count,
            "snapshots_count": len(self.snapshots),
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get portfolio health status."""
        latest = self.get_latest_snapshot()
        
        if not latest:
            return {
                "status": "no_data",
                "message": "No portfolio data available"
            }
        
        # Assess health based on metrics
        if latest.drawdown_pct >= 0.15:
            status = "critical"
            color = "red"
        elif latest.drawdown_pct >= 0.10:
            status = "warning"
            color = "orange"
        elif latest.drawdown_pct >= 0.05:
            status = "caution"
            color = "yellow"
        else:
            status = "healthy"
            color = "green"
        
        return {
            "status": status,
            "color": color,
            "drawdown": latest.drawdown_pct,
            "cash": latest.cash,
            "buying_power": latest.buying_power,
            "peak_equity": latest.peak_equity,
            "current_equity": latest.current_equity or latest.account_value,
            "open_positions": latest.positions_count,
            "exposure_pct": (latest.position_exposure / latest.account_value) if latest.account_value > 0 else 0.0,
            "exposure": (latest.position_exposure / latest.account_value) if latest.account_value > 0 else 0.0,
            "concentration": 0.0,
            "volatility": "Not enough data" if len(self.snapshots) < 3 else None,
        }