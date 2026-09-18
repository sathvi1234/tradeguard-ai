"""Order validator - checks all safety gates before submission."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.trading.order_builder import OptionsOrder, OrderSide
from app.utils.logging import get_logger, log_risk_event

logger = get_logger(__name__)


class OrderValidator:
    """Validates orders against all safety criteria."""
    
    # Validation thresholds
    MIN_NOTIONAL = 10.0  # $10 minimum
    MAX_NOTIONAL = 50000.0  # $50k maximum
    MAX_BUYING_POWER_USAGE = 0.50  # Use max 50% of buying power
    MIN_BID_ASK_MIDPOINT = 0.01  # Minimum $0.01 for midpoint
    MAX_SPREAD_PERCENT = 0.10  # Max 10% spread
    
    def __init__(self):
        """Initialize order validator."""
        self.logger = logger
    
    def validate_order(
        self,
        order: OptionsOrder,
        current_price: float,
        bid_price: float,
        ask_price: float,
        buying_power: float,
        portfolio_value: float,
        current_positions: int,
        max_positions: int = 10,
        decision_approved: bool = True,
        risk_approved: bool = True,
        drawdown_approved: bool = True,
    ) -> Tuple[bool, List[str]]:
        """
        Validate order against all safety criteria.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check 1: Decision approval
        if not decision_approved:
            errors.append("Decision Agent did not approve")
        
        # Check 2: Risk approval
        if not risk_approved:
            errors.append("Risk Guardian did not approve")
        
        # Check 3: Drawdown approval
        if not drawdown_approved:
            errors.append("Drawdown Guardian blocked trade (CRITICAL mode)")
        
        # Check 4: Quote validity
        if bid_price <= 0 or ask_price <= 0:
            errors.append("Invalid bid/ask quotes")
        
        if bid_price > ask_price:
            errors.append("Bid exceeds ask")
        
        # Check 5: Spread validation
        midpoint = (bid_price + ask_price) / 2
        if midpoint > 0:
            spread_percent = (ask_price - bid_price) / midpoint
            if spread_percent > self.MAX_SPREAD_PERCENT:
                errors.append(f"Spread too wide: {spread_percent:.2%}")
        
        # Check 6: Contract validity
        if order.quantity <= 0:
            errors.append("Invalid quantity")
        
        if order.strike <= 0:
            errors.append("Invalid strike price")
        
        if not order.expiration:
            errors.append("Invalid expiration")
        
        # Check 7: Notional value
        notional = order.limit_price * order.quantity * 100 if order.limit_price else 0
        
        if notional < self.MIN_NOTIONAL:
            errors.append(f"Position too small: ${notional:.2f}")
        
        if notional > self.MAX_NOTIONAL:
            errors.append(f"Position too large: ${notional:.2f}")
        
        # Check 8: Buying power
        required_capital = notional * 0.25 if order.side == OrderSide.BUY else 0
        
        if required_capital > 0:
            bp_usage = required_capital / buying_power if buying_power > 0 else 1.0
            
            if bp_usage > self.MAX_BUYING_POWER_USAGE:
                errors.append(
                    f"Insufficient buying power: need ${required_capital:.2f}, "
                    f"have ${buying_power:.2f}"
                )
        
        # Check 9: Position limits
        if current_positions >= max_positions:
            errors.append(f"Maximum positions reached: {current_positions}/{max_positions}")
        
        # Check 10: Portfolio exposure
        if portfolio_value > 0:
            exposure = notional / portfolio_value
            if exposure > 0.30:
                errors.append(f"Position exposure too high: {exposure:.2%}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            log_risk_event(
                "order_validation_failed",
                "medium",
                {
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "errors": errors,
                }
            )
        else:
            logger.info(
                "Order validation passed",
                symbol=order.symbol,
                quantity=order.quantity,
                notional=notional,
            )
        
        return is_valid, errors
    
    def validate_quote_freshness(
        self,
        quote_timestamp: datetime,
        max_age_seconds: int = 300,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate quote is fresh enough.
        
        Returns:
            Tuple of (is_fresh, error_message)
        """
        age_seconds = (datetime.utcnow() - quote_timestamp).total_seconds()
        
        if age_seconds > max_age_seconds:
            error = f"Quote too old: {age_seconds:.0f}s > {max_age_seconds}s"
            logger.warning(error)
            return False, error
        
        return True, None
    
    def validate_duplicate_order(
        self,
        symbol: str,
        strike: float,
        expiration: str,
        recent_orders: List[Dict[str, Any]],
        max_age_seconds: int = 60,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for duplicate orders recently submitted.
        
        Returns:
            Tuple of (is_unique, error_message)
        """
        now = datetime.utcnow()
        
        for order in recent_orders:
            # Skip if too old
            order_age = (now - order.get("timestamp", now)).total_seconds()
            if order_age > max_age_seconds:
                continue
            
            # Check if same contract
            if (order.get("symbol") == symbol and
                order.get("strike") == strike and
                order.get("expiration") == expiration):
                
                error = f"Duplicate order for {symbol} {strike} {expiration} (age {order_age:.0f}s)"
                logger.warning(error)
                return False, error
        
        return True, None