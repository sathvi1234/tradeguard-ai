"""Autonomous Trading Engine - orchestrates the complete trading cycle."""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.autonomous.debate_engine import DebateEngine
from app.autonomous.master_orchestrator import MasterOrchestrator
from app.risk import RiskGuardian, DrawdownGuardian
from app.trading.order_builder import OrderBuilder
from app.trading.order_validator import OrderValidator
from app.trading.order_executor import OrderExecutor
from app.trading.order_tracker import OrderTracker
from app.trading.position_manager import PositionManager
from app.trading.portfolio_monitor import PortfolioMonitor
from app.trading.audit_logger import AuditLogger
from app.services.post_trade_memory import PostTradeMemory
from app.alpaca.service import AlpacaService
from app.utils.logging import get_logger, log_risk_event

logger = get_logger(__name__)


class AutonomousTradingEngine:
    """Main autonomous trading engine."""
    
    def __init__(self, dry_run: bool = True):
        """
        Initialize autonomous trading engine.
        
        Args:
            dry_run: If True, simulate orders without live trading
        """
        self.logger = logger
        self.dry_run = dry_run
        self.running = False
        
        # Authoritative risk instances (shared with DebateEngine / Orchestrator)
        self.risk_guardian = RiskGuardian()
        self.drawdown_guardian = DrawdownGuardian()
        self.alpaca_service = AlpacaService()
        self.debate_engine = DebateEngine(
            risk_guardian=self.risk_guardian,
            drawdown_guardian=self.drawdown_guardian,
            alpaca_service=self.alpaca_service,
        )
        
        # Trading components
        self.order_builder = OrderBuilder()
        self.order_validator = OrderValidator()
        self.order_executor = OrderExecutor(dry_run=dry_run)
        self.order_tracker = OrderTracker()
        self.position_manager = PositionManager()
        self.portfolio_monitor = PortfolioMonitor()
        self.audit_logger = AuditLogger()
        self.trade_memory = PostTradeMemory()
        self.orchestrator = MasterOrchestrator(self)
        
        # State
        self.last_cycle: Optional[datetime] = None
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_order: Optional[str] = None
        self.last_rejection_reasons: list = []
        self.last_red_team: Optional[Dict[str, Any]] = None
        self.last_debate: Optional[Dict[str, Any]] = None
        self.last_bodyguard: Optional[Dict[str, Any]] = None
        self.last_market_intelligence: Optional[Dict[str, Any]] = None
        self.last_strategy_brain: Optional[list] = None
        self.last_cycle_status: Optional[str] = None
        self.last_cycle_message: Optional[str] = None
        self.last_halt_reason: Optional[str] = None
        self.last_risk_guardian: Optional[Dict[str, Any]] = None
        self.cycle_count = 0
        self.recent_orders: list = []
        self.simulated_equity_fills: list = []
    
    async def check_system_health(self) -> Tuple[bool, Optional[str]]:
        """
        Check system health before trading.
        
        Returns:
            Tuple of (is_healthy, error_message)
        """
        try:
            try:
                account = await self.alpaca_service.get_account()
                if not account:
                    return False, "Alpaca account unavailable"
            except Exception as e:
                return False, f"Alpaca connection failed: {str(e)}"
            
            if not account.get("paper_trading_allowed") or account.get("trading_blocked"):
                return False, "Paper trading not enabled"
            
            return True, None
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return False, str(e)
    
    async def initialize(self) -> bool:
        """
        Initialize the autonomous engine.
        
        Returns:
            True if successful
        """
        try:
            is_healthy, error = await self.check_system_health()
            if not is_healthy:
                logger.error(f"System health check failed: {error}")
                return False
            
            account = await self.alpaca_service.get_account()
            if not account:
                logger.error("Failed to get account information")
                return False
            
            account_value = float(account.get("portfolio_value", 0) or account.get("equity", 0) or 0)
            cash = float(account.get("cash", 0) or 0)
            buying_power = float(account.get("buying_power", 0) or 0)
            self.portfolio_monitor.initialize(account_value)
            self.portfolio_monitor.create_snapshot(
                account_value=account_value,
                cash=cash,
                buying_power=buying_power,
                positions_count=len(self.position_manager.get_open_positions()),
            )

            self.drawdown_guardian.initialize(account_value)
            
            logger.info(
                "Autonomous engine initialized",
                account_value=account_value,
                dry_run=self.dry_run,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def run_cycle(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Run a complete cycle via the Master Orchestrator."""
        if self.drawdown_guardian.state is None and self.portfolio_monitor.starting_balance:
            self.drawdown_guardian.initialize(self.portfolio_monitor.starting_balance)
        return await self.orchestrator.run_cycle(symbol)
    
    async def start(self) -> bool:
        """Start autonomous trading."""
        self.logger.info("Starting autonomous trading engine")
        
        if not await self.initialize():
            return False
        
        self.running = True
        log_risk_event("autonomous_engine_started", "low", {})
        return True
    
    async def stop(self) -> None:
        """Stop autonomous trading."""
        self.logger.info("Stopping autonomous trading engine")
        self.running = False
        log_risk_event("autonomous_engine_stopped", "low", {})
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        latest_snapshot = self.portfolio_monitor.get_latest_snapshot()
        
        return {
            "running": self.running,
            "dry_run": self.dry_run,
            "cycle_count": self.cycle_count,
            "last_cycle": self.last_cycle.isoformat() if self.last_cycle else None,
            "last_decision": self.last_decision,
            "last_order": self.last_order,
            "last_rejection_reasons": self.last_rejection_reasons,
            "last_red_team": self.last_red_team,
            "last_debate": self.last_debate,
            "last_market_intelligence": self.last_market_intelligence,
            "last_strategy_brain": self.last_strategy_brain,
            "last_cycle_status": self.last_cycle_status,
            "last_cycle_message": self.last_cycle_message,
            "last_halt_reason": self.last_halt_reason,
            "last_risk_guardian": self.last_risk_guardian,
            "last_bodyguard": self.last_bodyguard,
            "current_mode": self.drawdown_guardian.state.current_mode.value if self.drawdown_guardian.state else None,
            "current_drawdown": self.drawdown_guardian.state.drawdown_percentage if self.drawdown_guardian.state else 0,
            "positions_open": len(self.position_manager.get_open_positions()),
            "portfolio": latest_snapshot.to_dict() if latest_snapshot else None,
            "drawdown_guardian": {
                "state": self.drawdown_guardian.state.to_dict() if self.drawdown_guardian.state else None,
                "transitions": [t.to_dict() for t in self.drawdown_guardian.get_transitions()],
            },
            "simulated_equity_fills": list(self.simulated_equity_fills),
        }
