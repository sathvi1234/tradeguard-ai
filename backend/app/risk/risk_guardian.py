"""Deterministic Risk Guardian - Final mathematical safety gate."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

from app.utils.logging import get_logger, log_risk_event
from app.models import TradingMode

logger = get_logger(__name__)


class RiskGuardianDecision(str, Enum):
    """Risk Guardian decision."""
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class RiskGuardianResult:
    """Result from Risk Guardian evaluation."""
    decision: RiskGuardianDecision
    risk_score: float  # 0.0 to 1.0
    limits_checked: List[str]
    rejection_reasons: List[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision": self.decision.value,
            "display_decision": "ALLOW" if self.decision == RiskGuardianDecision.APPROVED else "BLOCK",
            "risk_score": self.risk_score,
            "limits_checked": self.limits_checked,
            "rejection_reasons": self.rejection_reasons,
            "timestamp": self.timestamp.isoformat(),
        }


class RiskGuardian:
    """
    Deterministic mathematical safety gate for trading decisions.
    
    This is the FINAL authority on whether a trade can execute.
    NO LLM can bypass these rules.
    """
    
    # Hard limits (non-negotiable)
    MAX_PORTFOLIO_DRAWDOWN = 0.15  # 15% critical
    MAX_DAILY_LOSS = 0.05  # 5% of portfolio
    MAX_POSITION_SIZE = 1000.0  # USD
    MAX_PORTFOLIO_EXPOSURE = 0.30  # 30% of portfolio in single trade
    MAX_POSITIONS = 10  # Maximum open positions
    MIN_CONFIDENCE_SCORE = 0.60  # Minimum AI confidence (60%)
    MIN_RISK_REWARD_RATIO = 1.0  # Minimum 1:1 risk/reward
    MIN_CONTRACT_LIQUIDITY = 100  # Minimum open interest
    MAX_QUOTE_AGE_SECONDS = 300  # 5 minutes max
    
    def __init__(self):
        """Initialize Risk Guardian."""
        self.logger = logger
    
    async def evaluate_trade(
        self,
        symbol: str,
        proposed_size: float,
        portfolio_value: float,
        current_equity: float,
        current_drawdown: float,
        current_positions: int,
        max_loss: float,
        potential_reward: float,
        ai_confidence: float,
        contract_validity: Dict[str, Any],
        market_data_timestamp: datetime,
        trading_mode: TradingMode,
        **kwargs
    ) -> RiskGuardianResult:
        """
        Evaluate trade against all hard limits.
        
        Args:
            symbol: Trading symbol
            proposed_size: Proposed position size in USD
            portfolio_value: Current portfolio value
            current_equity: Current equity
            current_drawdown: Current drawdown percentage
            current_positions: Number of open positions
            max_loss: Maximum estimated loss
            potential_reward: Potential reward
            ai_confidence: AI agent confidence score (0-1)
            contract_validity: Contract validation data
            market_data_timestamp: When the market data was obtained
            trading_mode: Current trading mode
            **kwargs: Additional arguments
            
        Returns:
            RiskGuardianResult with decision
        """
        timestamp = datetime.utcnow()
        limits_checked = []
        rejection_reasons = []
        risk_score = 0.0
        decision = RiskGuardianDecision.APPROVED
        
        # Check: Paper trading enforced globally (outside this function)
        limits_checked.append("paper_trading")
        
        # Check 1: Maximum Portfolio Drawdown
        limits_checked.append("max_portfolio_drawdown")
        if current_drawdown >= self.MAX_PORTFOLIO_DRAWDOWN:
            rejection_reasons.append(
                f"Drawdown limit exceeded: {current_drawdown:.2%} >= {self.MAX_PORTFOLIO_DRAWDOWN:.2%}"
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Check 2: Daily Loss Limit
        limits_checked.append("max_daily_loss")
        if portfolio_value > 0:
            daily_loss_pct = abs(current_equity - portfolio_value) / portfolio_value
            if daily_loss_pct >= self.MAX_DAILY_LOSS:
                rejection_reasons.append(
                    f"Daily loss limit exceeded: {daily_loss_pct:.2%} >= {self.MAX_DAILY_LOSS:.2%}"
                )
                decision = RiskGuardianDecision.REJECTED
        
        # Check 3: Position Size Limit
        limits_checked.append("max_position_size")
        if proposed_size > self.MAX_POSITION_SIZE:
            rejection_reasons.append(
                f"Position size too large: ${proposed_size:.2f} > ${self.MAX_POSITION_SIZE:.2f}"
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Check 4: Portfolio Exposure Limit
        limits_checked.append("max_portfolio_exposure")
        if portfolio_value > 0:
            exposure_pct = proposed_size / portfolio_value
            if exposure_pct > self.MAX_PORTFOLIO_EXPOSURE:
                rejection_reasons.append(
                    f"Portfolio exposure too high: {exposure_pct:.2%} > {self.MAX_PORTFOLIO_EXPOSURE:.2%}"
                )
                decision = RiskGuardianDecision.REJECTED
        
        # Check 5: Maximum Open Positions
        limits_checked.append("max_open_positions")
        if current_positions >= self.MAX_POSITIONS:
            rejection_reasons.append(
                f"Maximum positions reached: {current_positions} >= {self.MAX_POSITIONS}"
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Check 6: Minimum Confidence Score
        limits_checked.append("min_confidence_score")
        if ai_confidence < self.MIN_CONFIDENCE_SCORE:
            rejection_reasons.append(
                f"Confidence too low: {ai_confidence:.2%} < {self.MIN_CONFIDENCE_SCORE:.2%}"
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Check 7: Risk/Reward Ratio
        limits_checked.append("min_risk_reward_ratio")
        if max_loss > 0:
            risk_reward_ratio = potential_reward / max_loss
            if risk_reward_ratio < self.MIN_RISK_REWARD_RATIO:
                rejection_reasons.append(
                    f"Risk/reward ratio too low: {risk_reward_ratio:.2f} < {self.MIN_RISK_REWARD_RATIO:.2f}"
                )
                decision = RiskGuardianDecision.REJECTED
        
        # Check 8: Contract Liquidity
        limits_checked.append("contract_liquidity")
        if not contract_validity.get("is_liquid", False):
            open_interest = contract_validity.get("open_interest", 0)
            if open_interest < self.MIN_CONTRACT_LIQUIDITY:
                rejection_reasons.append(
                    f"Insufficient liquidity: OI {open_interest} < {self.MIN_CONTRACT_LIQUIDITY}"
                )
                decision = RiskGuardianDecision.REJECTED
        
        # Check 9: Quote Freshness
        limits_checked.append("quote_freshness")
        if not kwargs.get("skip_quote_age") and market_data_timestamp:
            age_seconds = (timestamp - market_data_timestamp).total_seconds()
            if age_seconds > self.MAX_QUOTE_AGE_SECONDS:
                rejection_reasons.append(
                    f"Data too stale: {age_seconds:.0f}s > {self.MAX_QUOTE_AGE_SECONDS}s"
                )
                decision = RiskGuardianDecision.REJECTED
        
        # Check 11: Market Data Integrity Engine (does not replace other gates)
        limits_checked.append("market_data_integrity")
        integrity = kwargs.get("data_integrity") if isinstance(kwargs.get("data_integrity"), dict) else {}
        integrity_state = str(integrity.get("integrity_state") or kwargs.get("integrity_state") or "")
        skip_stale = bool(kwargs.get("skip_quote_age"))
        if integrity_state in {"DATA_INVALID", "DATA_UNAVAILABLE", "DATA_ERROR"}:
            rejection_reasons.append(
                f"Market data integrity fail closed ({integrity_state}). Risk Guardian is the final authority."
            )
            decision = RiskGuardianDecision.REJECTED
        elif integrity_state == "DATA_STALE" and not skip_stale:
            rejection_reasons.append(
                "Market data integrity fail closed (DATA_STALE). Risk Guardian is the final authority."
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Check 10: Trading Mode Restrictions
        limits_checked.append("trading_mode")
        if trading_mode == TradingMode.CRITICAL:
            rejection_reasons.append("Trading blocked in CRITICAL mode")
            decision = RiskGuardianDecision.REJECTED
        elif trading_mode == TradingMode.PROTECTION:
            # PROTECTION mode allows trades but with stricter rules
            if ai_confidence < self.MIN_CONFIDENCE_SCORE * 1.2:  # Higher confidence required
                rejection_reasons.append(
                    f"PROTECTION mode: confidence {ai_confidence:.2%} insufficient"
                )
                decision = RiskGuardianDecision.REJECTED

        limits_checked.append("market_closed")
        if kwargs.get("market_closed") is True:
            rejection_reasons.append("MARKET_CLOSED. Risk Guardian is the final authority.")
            decision = RiskGuardianDecision.REJECTED

        limits_checked.append("llm_veto_enforced")
        if kwargs.get("llm_veto") is True:
            rejection_reasons.append(
                "LLM reviewer VETO applied by Risk Guardian. The LLM is not the final authority."
            )
            decision = RiskGuardianDecision.REJECTED
        
        # Calculate risk score (0-1, where 1 is most risky)
        risk_score = self._calculate_risk_score(
            proposed_size,
            portfolio_value,
            current_drawdown,
            current_positions,
            max_loss,
            ai_confidence
        )
        
        # Log decision
        if decision == RiskGuardianDecision.APPROVED:
            log_risk_event(
                "trade_approved_by_risk_guardian",
                "low",
                {
                    "symbol": symbol,
                    "size": proposed_size,
                    "risk_score": risk_score,
                    "confidence": ai_confidence,
                }
            )
        else:
            log_risk_event(
                "trade_rejected_by_risk_guardian",
                "high" if current_drawdown >= self.MAX_PORTFOLIO_DRAWDOWN else "medium",
                {
                    "symbol": symbol,
                    "size": proposed_size,
                    "reasons": rejection_reasons,
                    "risk_score": risk_score,
                }
            )
        
        result = RiskGuardianResult(
            decision=decision,
            risk_score=risk_score,
            limits_checked=limits_checked,
            rejection_reasons=rejection_reasons,
            timestamp=timestamp
        )
        
        return result
    
    def _calculate_risk_score(
        self,
        proposed_size: float,
        portfolio_value: float,
        current_drawdown: float,
        current_positions: int,
        max_loss: float,
        ai_confidence: float
    ) -> float:
        """
        Calculate overall risk score (0.0 = low, 1.0 = high).
        
        Args:
            proposed_size: Proposed position size
            portfolio_value: Portfolio value
            current_drawdown: Current drawdown percentage
            current_positions: Number of open positions
            max_loss: Maximum estimated loss
            ai_confidence: AI confidence score
            
        Returns:
            Risk score from 0.0 to 1.0
        """
        risk_score = 0.0
        
        # Size risk (0-0.3)
        if portfolio_value > 0:
            size_pct = proposed_size / portfolio_value
            size_risk = min(0.3, size_pct * 3)
        else:
            size_risk = 0.3
        risk_score += size_risk
        
        # Drawdown risk (0-0.3)
        drawdown_risk = min(0.3, current_drawdown * 2)
        risk_score += drawdown_risk
        
        # Concentration risk (0-0.2)
        concentration_risk = min(0.2, (current_positions / self.MAX_POSITIONS) * 0.3)
        risk_score += concentration_risk
        
        # Loss risk (0-0.2)
        if max_loss > 0 and portfolio_value > 0:
            loss_pct = max_loss / portfolio_value
            loss_risk = min(0.2, loss_pct * 4)
        else:
            loss_risk = 0
        risk_score += loss_risk
        
        # Confidence risk (0-0.2, inverted)
        confidence_risk = (1.0 - ai_confidence) * 0.2
        risk_score += confidence_risk
        
        return min(1.0, max(0.0, risk_score))