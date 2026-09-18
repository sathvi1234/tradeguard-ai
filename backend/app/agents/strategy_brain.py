"""Strategy Brain — BULL / FLAT / BEAR scenarios using existing Bull/Bear agents."""

from typing import Any, Dict, List, Optional

from app.agents.bear_agent import BearAgent
from app.agents.bull_agent import BullAgent
from app.llm.service import get_llm_service
from app.models.schemas import LLM_UNAVAILABLE, ScenarioType, StrategyScenario
from app.utils.logging import get_logger

logger = get_logger(__name__)


class StrategyBrain:
    """Coordinates Bull/Bear agents. Does not invent market evidence."""

    def __init__(
        self,
        bull_agent: Optional[BullAgent] = None,
        bear_agent: Optional[BearAgent] = None,
    ) -> None:
        self.bull_agent = bull_agent or BullAgent()
        self.bear_agent = bear_agent or BearAgent()
        self.logger = logger

    async def evaluate(
        self,
        symbol: str,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
    ) -> List[StrategyScenario]:
        evidence_available = bool(market_analysis) and not (market_analysis or {}).get("errors")
        if market_analysis and isinstance(market_analysis.get("data"), dict):
            evidence_available = bool(market_analysis.get("data"))

        bull = await self.bull_agent.analyze(
            symbol=symbol,
            market_analysis=market_analysis,
            options_analysis=options_analysis,
        )
        bear = await self.bear_agent.analyze(
            symbol=symbol,
            market_analysis=market_analysis,
            options_analysis=options_analysis,
        )

        bull_conf = bull.confidence if evidence_available else min(bull.confidence, 0.2)
        bear_conf = bear.confidence if evidence_available else min(bear.confidence, 0.2)
        missing_note = [] if evidence_available else ["market evidence unavailable"]

        bull_scenario = StrategyScenario(
            scenario=ScenarioType.BULL,
            confidence=bull_conf,
            thesis=bull.reasoning,
            supporting_evidence=list((bull.data or {}).get("bullish_evidence") or missing_note),
            risks=list((bull.data or {}).get("risks") or ["Market can reverse against the bull thesis"]),
            invalidation_conditions=["bull thesis fails if market evidence missing or trend reverses"],
            expected_direction="up",
            candidate_strategies=["directional_vertical_spread", "the_wheel"],
            evidence_available=evidence_available,
        )
        bear_scenario = StrategyScenario(
            scenario=ScenarioType.BEAR,
            confidence=bear_conf,
            thesis=bear.reasoning,
            supporting_evidence=list((bear.data or {}).get("bearish_evidence") or missing_note),
            risks=list((bear.data or {}).get("risks") or ["Market can continue higher against the bear thesis"]),
            invalidation_conditions=["bear thesis fails if market evidence missing or trend reverses"],
            expected_direction="down",
            candidate_strategies=["directional_vertical_spread"],
            evidence_available=evidence_available,
        )
        flat_conf = 0.3 if evidence_available else 0.1
        if evidence_available and abs(bull_conf - bear_conf) < 0.15:
            flat_conf = max(bull_conf, bear_conf)
        flat_scenario = StrategyScenario(
            scenario=ScenarioType.FLAT,
            confidence=flat_conf,
            thesis="Neutral/range outcome when bull and bear evidence conflict or data is incomplete.",
            supporting_evidence=missing_note or ["bull/bear disagreement"],
            risks=["breakout risk", "Regime confirmation incomplete when bull and bear conflict"],
            invalidation_conditions=["strong confirmed directional evidence"],
            expected_direction="flat",
            candidate_strategies=["theta_iron_condor", "calendar_spread"],
            evidence_available=evidence_available,
        )
        advisory = await get_llm_service().advise(
            role="strategy_brain",
            facts={
                "symbol": symbol,
                "evidence_available": evidence_available,
                "bull_thesis": bull_scenario.thesis,
                "bear_thesis": bear_scenario.thesis,
                "market_direction": (market_analysis or {}).get("data", {}).get("direction")
                if isinstance(market_analysis, dict)
                else None,
            },
        )
        for scenario in (bull_scenario, flat_scenario, bear_scenario):
            scenario.llm_status = advisory.status
            scenario.llm_advisory = advisory.summary
            if advisory.status == LLM_UNAVAILABLE:
                scenario.llm_advisory = None
        return [bull_scenario, flat_scenario, bear_scenario]
