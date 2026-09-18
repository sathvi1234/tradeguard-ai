"""Order executor - submits validated orders to Alpaca."""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import uuid

from app.trading.order_builder import OptionsOrder
from app.alpaca.service import AlpacaService
from app.utils.logging import get_logger, log_risk_event

logger = get_logger(__name__)


@dataclass
class ExecutedOrder:
    """Record of executed order."""
    order_id: str
    alpaca_order_id: Optional[str]
    symbol: str
    option_type: str
    strike: float
    expiration: str
    quantity: int
    side: str
    limit_price: float
    status: str  # submitted, filled, canceled, rejected
    timestamp: datetime
    filled_price: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "alpaca_order_id": self.alpaca_order_id,
            "symbol": self.symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiration": self.expiration,
            "quantity": self.quantity,
            "side": self.side,
            "limit_price": self.limit_price,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "filled_price": self.filled_price,
            "error_message": self.error_message,
        }


class OrderExecutor:
    """Submits validated orders to Alpaca."""
    
    def __init__(self, dry_run: bool = True):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate order submission without live trading
        """
        self.logger = logger
        self.alpaca_service = AlpacaService()
        self.dry_run = dry_run
        self.submitted_orders: Dict[str, ExecutedOrder] = {}
    
    async def execute_order(
        self,
        order: OptionsOrder,
        decision_id: str,
        dry_run: Optional[bool] = None,
    ) -> ExecutedOrder:
        """
        Execute order to Alpaca.
        
        Args:
            order: Order to execute
            decision_id: ID of decision that generated this order
            dry_run: Override instance dry_run setting
            
        Returns:
            ExecutedOrder with status
        """
        use_dry_run = dry_run if dry_run is not None else self.dry_run
        order_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        try:
            if use_dry_run:
                # Simulate successful order submission
                executed = ExecutedOrder(
                    order_id=order_id,
                    alpaca_order_id=f"sim-{order_id[:8]}",
                    symbol=order.symbol,
                    option_type=order.option_type,
                    strike=order.strike,
                    expiration=order.expiration,
                    quantity=order.quantity,
                    side=order.side.value,
                    limit_price=order.limit_price or 0,
                    status="filled",  # Simulate immediate fill
                    timestamp=timestamp,
                    filled_price=order.limit_price,
                )
                
                self.logger.info(
                    "DRY RUN: Order simulated (not submitted to Alpaca)",
                    order_id=order_id,
                    symbol=order.symbol,
                    quantity=order.quantity,
                )
                
            else:
                # LIVE TRADING: NOT IMPLEMENTED IN PAPER MODE
                # This is intentionally stubbed out - live trading never happens
                raise RuntimeError("SECURITY: Live trading is disabled")
            
            # Store order
            self.submitted_orders[order_id] = executed
            
            # Log success
            log_risk_event(
                "order_executed",
                "low",
                {
                    "order_id": order_id,
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "side": order.side.value,
                    "decision_id": decision_id,
                    "dry_run": use_dry_run,
                }
            )
            
            return executed
            
        except Exception as e:
            self.logger.error(
                "Order execution failed",
                order_id=order_id,
                symbol=order.symbol,
                error=str(e),
            )
            
            executed = ExecutedOrder(
                order_id=order_id,
                alpaca_order_id=None,
                symbol=order.symbol,
                option_type=order.option_type,
                strike=order.strike,
                expiration=order.expiration,
                quantity=order.quantity,
                side=order.side.value,
                limit_price=order.limit_price or 0,
                status="rejected",
                timestamp=timestamp,
                error_message=str(e),
            )
            
            self.submitted_orders[order_id] = executed
            
            log_risk_event(
                "order_execution_failed",
                "high",
                {
                    "order_id": order_id,
                    "symbol": order.symbol,
                    "error": str(e),
                }
            )
            
            return executed
    
    def get_order(self, order_id: str) -> Optional[ExecutedOrder]:
        """Get submitted order by ID."""
        return self.submitted_orders.get(order_id)
    
    def get_all_orders(self) -> list:
        """Get all submitted orders."""
        return list(self.submitted_orders.values())