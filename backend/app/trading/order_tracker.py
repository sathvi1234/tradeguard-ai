"""Order tracker - monitors submitted orders."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OrderStatus:
    """Status of an order."""
    order_id: str
    alpaca_order_id: Optional[str]
    symbol: str
    side: str  # buy or sell
    quantity: int
    limit_price: float
    status: str  # submitted, filled, partial, canceled, rejected
    submitted_at: datetime
    filled_at: Optional[datetime] = None
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    updates: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "alpaca_order_id": self.alpaca_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "updates": len(self.updates),
        }


class OrderTracker:
    """Tracks submitted orders and their status."""
    
    def __init__(self):
        """Initialize order tracker."""
        self.logger = logger
        self.tracked_orders: Dict[str, OrderStatus] = {}
    
    def track_order(
        self,
        order_id: str,
        alpaca_order_id: Optional[str],
        symbol: str,
        side: str,
        quantity: int,
        limit_price: float,
    ) -> OrderStatus:
        """
        Start tracking an order.
        
        Args:
            order_id: Internal order ID
            alpaca_order_id: Alpaca order ID (None for dry run)
            symbol: Option symbol
            side: buy or sell
            quantity: Quantity ordered
            limit_price: Limit price
            
        Returns:
            OrderStatus
        """
        status = OrderStatus(
            order_id=order_id,
            alpaca_order_id=alpaca_order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            status="submitted",
            submitted_at=datetime.utcnow(),
        )
        
        self.tracked_orders[order_id] = status
        
        self.logger.info(
            "Order tracking started",
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
        )
        
        return status
    
    def update_order_status(
        self,
        order_id: str,
        status: str,
        filled_quantity: int = 0,
        filled_price: Optional[float] = None,
    ) -> Optional[OrderStatus]:
        """
        Update order status.
        
        Args:
            order_id: Order ID to update
            status: New status
            filled_quantity: Filled quantity
            filled_price: Filled price
            
        Returns:
            Updated OrderStatus or None
        """
        order = self.tracked_orders.get(order_id)
        
        if not order:
            self.logger.warning(f"Order not tracked: {order_id}")
            return None
        
        old_status = order.status
        order.status = status
        
        if status == "filled" and filled_price:
            order.filled_at = datetime.utcnow()
            order.filled_quantity = filled_quantity or order.quantity
            order.filled_price = filled_price
        
        # Record update
        order.updates.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_status": old_status,
            "new_status": status,
            "filled_quantity": filled_quantity,
            "filled_price": filled_price,
        })
        
        self.logger.info(
            "Order status updated",
            order_id=order_id,
            old_status=old_status,
            new_status=status,
        )
        
        return order
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status."""
        return self.tracked_orders.get(order_id)
    
    def get_open_orders(self) -> List[OrderStatus]:
        """Get all open orders."""
        return [
            order for order in self.tracked_orders.values()
            if order.status in ["submitted", "partial"]
        ]
    
    def get_all_tracked_orders(self) -> List[OrderStatus]:
        """Get all tracked orders."""
        return list(self.tracked_orders.values())