"""Adaptive position restructuring recommendations. Never auto-executes."""

from typing import Any, List, Optional

from app.models.enums import TradingMode
from app.models.schemas import RestructuringAction, RestructuringRecommendation


class PositionRestructuringService:
    """Recommend HOLD/CLOSE/REDUCE/ROLL/HEDGE/REASSESS. RiskGuardian must approve any future execution."""

    def recommend(
        self,
        position: Any = None,
        *,
        trading_mode: Optional[TradingMode] = None,
        thesis_invalidated: bool = False,
        volatility_change: Optional[str] = None,
        concentration_high: bool = False,
        loss_pct: Optional[float] = None,
    ) -> RestructuringRecommendation:
        reasons: List[str] = []
        action = RestructuringAction.HOLD
        symbol = getattr(position, "symbol", None) if position is not None else None

        if trading_mode == TradingMode.CRITICAL:
            action = RestructuringAction.REASSESS
            reasons.append("CRITICAL drawdown mode: freeze new risk and reassess open exposure")

        if thesis_invalidated:
            action = RestructuringAction.CLOSE
            reasons.append("Thesis invalidated")

        dte = None
        if position is not None and hasattr(position, "days_to_expiration"):
            try:
                dte = position.days_to_expiration()
            except Exception:
                dte = None
        if dte is not None and dte <= 2:
            if action == RestructuringAction.HOLD:
                action = RestructuringAction.ROLL
            reasons.append(f"Approaching expiration (DTE={dte})")

        if loss_pct is not None and loss_pct <= -0.50:
            action = RestructuringAction.CLOSE
            reasons.append("Excessive loss vs entry")
        elif loss_pct is not None and loss_pct <= -0.25:
            if action in (RestructuringAction.HOLD, RestructuringAction.ROLL):
                action = RestructuringAction.REDUCE
            reasons.append("Loss pressure vs entry")

        if volatility_change == "unavailable":
            reasons.append("Volatility change DATA_UNAVAILABLE")
        elif volatility_change:
            reasons.append(f"Volatility change noted: {volatility_change}")
            if action == RestructuringAction.HOLD:
                action = RestructuringAction.REASSESS

        if concentration_high:
            if action == RestructuringAction.HOLD:
                action = RestructuringAction.HEDGE
            reasons.append("Portfolio concentration is elevated")

        if not reasons:
            reasons.append("No restructuring trigger from available data")

        return RestructuringRecommendation(
            action=action,
            reasons=reasons,
            symbol=symbol,
            recommendation_only=True,
            requires_risk_guardian=True,
        )
