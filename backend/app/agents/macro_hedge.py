"""Macro & Hedge agent. Does not fabricate macro series."""

from typing import List, Optional

from app.llm.service import get_llm_service
from app.models.schemas import DATA_UNAVAILABLE, DataAvailability, MacroContext
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MacroHedgeAgent:
    """Portfolio-aware hedge context. External macro is DATA_UNAVAILABLE unless provided."""

    async def analyze(
        self,
        *,
        current_positions: int = 0,
        portfolio_value: Optional[float] = None,
        proposed_size: float = 0.0,
        real_macro: Optional[dict] = None,
    ) -> MacroContext:
        concentration = None
        exposure = None
        if portfolio_value and portfolio_value > 0 and proposed_size:
            exposure = proposed_size / portfolio_value
        if current_positions:
            concentration = float(current_positions)

        hedge: List[str] = []
        if current_positions >= 5:
            hedge.append("Consider reducing correlated names; hedge is advisory only")
        if exposure and exposure > 0.15:
            hedge.append("Single-ticket exposure is elevated versus portfolio")
        if not hedge:
            hedge.append("No hedge required from available portfolio counts; macro series DATA_UNAVAILABLE")

        advisory = await get_llm_service().advise(
            role="macro_hedge",
            facts={
                "current_positions": current_positions,
                "portfolio_value": portfolio_value,
                "proposed_size": proposed_size,
                "real_macro_present": bool(real_macro),
                "hedge_considerations": hedge,
            },
        )

        if not real_macro:
            return MacroContext(
                volatility_environment=DATA_UNAVAILABLE,
                broad_market_regime=DATA_UNAVAILABLE,
                interest_rate_context=DATA_UNAVAILABLE,
                major_event_risk=DATA_UNAVAILABLE,
                portfolio_exposure=exposure,
                concentration=concentration,
                hedge_considerations=hedge,
                availability=DataAvailability.DATA_UNAVAILABLE,
                notes=DATA_UNAVAILABLE,
                llm_status=advisory.status,
                llm_advisory=advisory.summary,
            )

        return MacroContext(
            volatility_environment=str(real_macro.get("volatility_environment", DATA_UNAVAILABLE)),
            broad_market_regime=str(real_macro.get("broad_market_regime", DATA_UNAVAILABLE)),
            interest_rate_context=str(real_macro.get("interest_rate_context", DATA_UNAVAILABLE)),
            major_event_risk=str(real_macro.get("major_event_risk", DATA_UNAVAILABLE)),
            portfolio_exposure=exposure,
            concentration=concentration,
            hedge_considerations=hedge,
            availability=DataAvailability.AVAILABLE,
            notes="Populated from explicit real_macro payload only.",
            llm_status=advisory.status,
            llm_advisory=advisory.summary,
        )
