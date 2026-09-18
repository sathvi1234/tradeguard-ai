"""Order builder for constructing Alpaca options orders."""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from app.utils.logging import get_logger

logger = get_logger(__name__)


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class OptionsOrder:
    """Options order specification."""
    symbol: str
    option_type: str  # call or put
    strike: float
    expiration: str  # YYYY-MM-DD
    quantity: int
    side: OrderSide
    limit_price: Optional[float] = None
    order_type: OrderType = OrderType.LIMIT
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiration": self.expiration,
            "quantity": self.quantity,
            "side": self.side.value,
            "limit_price": self.limit_price,
            "order_type": self.order_type.value,
        }


class OrderBuilder:
    """Build Alpaca options orders from debate decisions."""
    
    def __init__(self):
        """Initialize order builder."""
        self.logger = logger
    
    def build_buy_call(
        self,
        symbol: str,
        strike: float,
        expiration: str,
        quantity: int,
        bid_price: float,
        ask_price: float,
    ) -> OptionsOrder:
        """
        Build a BUY_CALL order.
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiration: Expiration date (YYYY-MM-DD)
            quantity: Number of contracts
            bid_price: Current bid price
            ask_price: Current ask price
            
        Returns:
            OptionsOrder
        """
        # Use ask price as limit for buy orders (avoid slippage above ask)
        limit_price = ask_price + (ask_price * 0.01)  # 1% above ask for safety
        
        order = OptionsOrder(
            symbol=symbol,
            option_type="call",
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            side=OrderSide.BUY,
            limit_price=limit_price,
            order_type=OrderType.LIMIT,
        )
        
        self.logger.info(
            "Built BUY_CALL order",
            symbol=symbol,
            strike=strike,
            quantity=quantity,
            limit_price=limit_price,
        )
        
        return order
    
    def build_buy_put(
        self,
        symbol: str,
        strike: float,
        expiration: str,
        quantity: int,
        bid_price: float,
        ask_price: float,
    ) -> OptionsOrder:
        """
        Build a BUY_PUT order.
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiration: Expiration date (YYYY-MM-DD)
            quantity: Number of contracts
            bid_price: Current bid price
            ask_price: Current ask price
            
        Returns:
            OptionsOrder
        """
        # Use ask price as limit for buy orders
        limit_price = ask_price + (ask_price * 0.01)  # 1% above ask for safety
        
        order = OptionsOrder(
            symbol=symbol,
            option_type="put",
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            side=OrderSide.BUY,
            limit_price=limit_price,
            order_type=OrderType.LIMIT,
        )
        
        self.logger.info(
            "Built BUY_PUT order",
            symbol=symbol,
            strike=strike,
            quantity=quantity,
            limit_price=limit_price,
        )
        
        return order
    
    def build_sell_call(
        self,
        symbol: str,
        strike: float,
        expiration: str,
        quantity: int,
        bid_price: float,
        ask_price: float,
    ) -> OptionsOrder:
        """
        Build a SELL_CALL order (exit).
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiration: Expiration date (YYYY-MM-DD)
            quantity: Number of contracts
            bid_price: Current bid price
            ask_price: Current ask price
            
        Returns:
            OptionsOrder
        """
        # Use bid price as limit for sell orders
        limit_price = bid_price - (bid_price * 0.01)  # 1% below bid for safety
        
        order = OptionsOrder(
            symbol=symbol,
            option_type="call",
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            side=OrderSide.SELL,
            limit_price=limit_price,
            order_type=OrderType.LIMIT,
        )
        
        self.logger.info(
            "Built SELL_CALL order (exit)",
            symbol=symbol,
            strike=strike,
            quantity=quantity,
            limit_price=limit_price,
        )
        
        return order
    
    def build_sell_put(
        self,
        symbol: str,
        strike: float,
        expiration: str,
        quantity: int,
        bid_price: float,
        ask_price: float,
    ) -> OptionsOrder:
        """
        Build a SELL_PUT order (exit).
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiration: Expiration date (YYYY-MM-DD)
            quantity: Number of contracts
            bid_price: Current bid price
            ask_price: Current ask price
            
        Returns:
            OptionsOrder
        """
        # Use bid price as limit for sell orders
        limit_price = bid_price - (bid_price * 0.01)  # 1% below bid for safety
        
        order = OptionsOrder(
            symbol=symbol,
            option_type="put",
            strike=strike,
            expiration=expiration,
            quantity=quantity,
            side=OrderSide.SELL,
            limit_price=limit_price,
            order_type=OrderType.LIMIT,
        )
        
        self.logger.info(
            "Built SELL_PUT order (exit)",
            symbol=symbol,
            strike=strike,
            quantity=quantity,
            limit_price=limit_price,
        )
        
        return order
    
    def calculate_quantity(
        self,
        proposed_size: float,
        option_price: float,
        multiplier: int = 100,
    ) -> int:
        """
        Calculate quantity of contracts.
        
        Args:
            proposed_size: Size in USD
            option_price: Price per contract
            multiplier: Contracts multiplier (standard is 100)
            
        Returns:
            Quantity of contracts
        """
        if option_price <= 0:
            return 0
        
        # Each contract controls 100 shares
        total_notional = option_price * multiplier
        
        # Calculate contracts (round down for safety)
        if total_notional > 0:
            quantity = int(proposed_size / total_notional)
        else:
            quantity = 0
        
        return max(1, quantity)  # Minimum 1 contract