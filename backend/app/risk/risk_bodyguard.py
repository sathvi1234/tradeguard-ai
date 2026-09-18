"""Continuous risk bodyguard — post-position monitoring. No live execution."""

from typing import Any, List, Optional

from app.models.enums import TradingMode
from app.models.schemas import BodyguardAction, BodyguardAssessment


class RiskBodyguard:
    """Monitors open positions after they exist. Cannot bypass Risk Guardian."""

    def assess(
        self,
        positions: Optional[List[Any]] = None,
        *,
        trading_mode: Optional[TradingMode] = None,
        drawdown: float = 0.0,
        stop_hit: bool = False,
        take_profit_hit: bool = False,
        exposure_limit_breached: bool = False,
        concentration_high: bool = False,
        dte_critical: bool = False,
        volatility_unavailable: bool = False,
    ) -> BodyguardAssessment:
        positions = list(positions or [])
        reasons: List[str] = []
        action = BodyguardAction.HOLD
        freeze = trading_mode == TradingMode.CRITICAL

        if freeze:
            action = BodyguardAction.FREEZE_NEW_TRADES
            reasons.append("CRITICAL mode: freeze new trades")

        if stop_hit:
            action = BodyguardAction.EXIT
            reasons.append("Stop-loss condition")
        elif take_profit_hit:
            if action not in (BodyguardAction.EXIT, BodyguardAction.FREEZE_NEW_TRADES):
                action = BodyguardAction.EXIT
            reasons.append("Take-profit condition")

        if exposure_limit_breached:
            if action == BodyguardAction.HOLD:
                action = BodyguardAction.REDUCE
            reasons.append("Portfolio exposure limit")

        if concentration_high:
            if action == BodyguardAction.HOLD:
                action = BodyguardAction.HEDGE
            reasons.append("Position concentration")

        if dte_critical:
            reasons.append("Expiration / DTE pressure")
            if action == BodyguardAction.HOLD:
                action = BodyguardAction.REDUCE

        if volatility_unavailable:
            reasons.append("Volatility: Not enough data")

        if drawdown >= 0.15 and not freeze:
            action = BodyguardAction.FREEZE_NEW_TRADES
            freeze = True
            reasons.append("Drawdown at or above 15%")

        if not positions and action == BodyguardAction.HOLD:
            reasons.append("No open positions to manage")

        if freeze and action != BodyguardAction.FREEZE_NEW_TRADES:
            # Preserve EXIT/REDUCE for existing risk, but freeze new trades.
            reasons.append("New trades remain frozen")

        return BodyguardAssessment(
            action=action,
            reasons=reasons,
            freeze_new_trades=freeze or action == BodyguardAction.FREEZE_NEW_TRADES,
            positions_reviewed=len(positions),
            drawdown_mode=trading_mode,
            advisory_only=True,
        )
