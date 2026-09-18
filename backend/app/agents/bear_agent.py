"""Bear Agent - Actively challenges the trade."""

from datetime import datetime
from typing import Dict, Any, Optional

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.agents.market_scout import MarketDirection
from app.llm.service import get_llm_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BearAgent(BaseAgent):
    """
    Actively challenges and makes bearish case AGAINST the trade.
    
    Analyzes:
    - Bearish signals
    - Weak trend
    - Volatility risk
    - Event risk
    - Liquidity risk
    - Expensive options
    - Downside risk
    """
    
    def __init__(self):
        """Initialize Bear Agent."""
        super().__init__()
        self.agent_type = AgentType.BEAR
    
    async def analyze(
        self,
        symbol: str,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Make bearish case against the trade.
        
        Args:
            symbol: Trading symbol
            market_analysis: Market Scout analysis
            options_analysis: Options Analyst analysis
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with bear recommendation
        """
        timestamp = datetime.utcnow()
        errors = []
        confidence = 0.5
        
        try:
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Extract market data
            market_data = self._analysis_body(market_analysis)
            market_direction = market_data.get("direction", MarketDirection.NEUTRAL.value)
            market_score = market_data.get("market_score", 0.5)
            
            options_data = self._analysis_body(options_analysis)
            contract_info = options_data.get("contract", {})
            greeks = options_data.get("greeks", {})
            liquidity = options_data.get("liquidity", {})
            risk_reward = options_data.get("risk_reward", {})
            
            # Gather bearish evidence
            bearish_evidence = self._gather_bearish_evidence(
                market_direction,
                market_score,
                contract_info,
                greeks,
                risk_reward
            )
            
            # Identify counter-arguments
            counter_arguments = self._identify_counter_arguments(
                market_data,
                options_data,
                contract_info,
                liquidity
            )
            
            # Assess downside risk
            downside_risk = self._assess_downside_risk(
                contract_info,
                market_data.get("current_price", 0),
                market_score
            )
            
            # Determine recommendation
            if market_direction == MarketDirection.BEARISH.value or market_score < 0.4:
                recommendation = "AVOID"
                confidence = 0.6 + ((1.0 - market_score) * 0.2)
            elif market_direction == MarketDirection.NEUTRAL.value:
                recommendation = "WAIT_FOR_CLARITY"
                confidence = 0.55
            else:
                recommendation = "RELUCTANT_APPROVAL"
                confidence = 0.4
            
            # Build reasoning
            reasoning = self._build_bear_reasoning(
                recommendation,
                bearish_evidence,
                counter_arguments,
                downside_risk
            )
            
            # Compile data
            data = {
                "recommendation": recommendation,
                "bearish_evidence": bearish_evidence,
                "counter_arguments": counter_arguments,
                "downside_risk": downside_risk,
                "market_direction": market_direction,
                "market_score": market_score,
            }
            advisory = await get_llm_service().advise(
                role="bear_agent",
                facts={
                    "symbol": symbol,
                    "recommendation": recommendation,
                    "market_direction": market_direction,
                    "market_score": market_score,
                    "evidence": bearish_evidence,
                    "counter_arguments": counter_arguments,
                    "bid": market_data.get("bid_price"),
                    "ask": market_data.get("ask_price"),
                    "current_price": market_data.get("current_price"),
                },
            )
            data["llm_advisory"] = advisory.to_agent_dict()
            data["llm_status"] = advisory.status
            if advisory.summary:
                reasoning = f"{reasoning} | LLM advisory (not authority): {advisory.summary}"
            
            analysis = AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=min(1.0, max(0.0, confidence)),
                reasoning=reasoning,
                data=data,
                errors=errors if errors else None
            )
            
            self._log_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Bear agent analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={},
                errors=[str(e)]
            )
    
    def _gather_bearish_evidence(
        self,
        market_direction: str,
        market_score: float,
        contract_info: Dict,
        greeks: Dict,
        risk_reward: Dict
    ) -> Dict[str, Any]:
        """Gather evidence supporting bearish thesis."""
        evidence = {
            "unfavorable_market_direction": market_direction == MarketDirection.BEARISH.value,
            "weak_momentum": market_score < 0.4,
            "negative_delta": greeks.get("delta", 0) < -0.3,
            "poor_risk_reward": risk_reward.get("risk_reward_ratio", 0) < 1.5,
        }
        
        evidence["score"] = sum([
            1.0 if evidence["unfavorable_market_direction"] else 0,
            0.8 if evidence["weak_momentum"] else 0,
            0.7 if evidence["negative_delta"] else 0,
            0.6 if evidence["poor_risk_reward"] else 0,
        ])
        
        return evidence
    
    def _identify_counter_arguments(
        self,
        market_data: Dict,
        options_data: Dict,
        contract_info: Dict,
        liquidity: Dict
    ) -> list:
        """Identify counter-arguments against the trade."""
        arguments = []
        
        # Expensive options
        spread_bps = contract_info.get("spread_bps", 0)
        if spread_bps > 40:
            arguments.append(f"Options expensive: {spread_bps:.0f} bps spread")
        
        # Low volume/liquidity
        volume = contract_info.get("volume", 0)
        oi = contract_info.get("open_interest", 0)
        if volume < 10 or oi < 500:
            arguments.append("Low liquidity increases slippage")
        
        # High theta decay
        theta = options_data.get("greeks", {}).get("theta", 0)
        if theta < -0.02:
            arguments.append(f"High theta decay ({theta:.3f}), time is against us")
        
        # Weak market
        if market_data.get("market_score", 0.5) < 0.4:
            arguments.append("Weak market conditions")
        
        # Volatility uncertainty
        if market_data.get("volatility_score", 0.5) > 0.7:
            arguments.append("High volatility = execution risk")
        
        return arguments
    
    def _assess_downside_risk(
        self,
        contract_info: Dict,
        current_price: float,
        market_score: float
    ) -> Dict[str, Any]:
        """Assess downside risk of the position."""
        strike = contract_info.get("strike", 0)
        max_loss = contract_info.get("max_loss", 0)
        
        # Downside move potential
        if strike > 0 and current_price > 0:
            downside_move = (current_price - (strike * 0.95)) / current_price
        else:
            downside_move = 0
        
        # Risk weighted by market weakness
        risk_score = (downside_move + (1.0 - market_score)) / 2 if downside_move > 0 else (1.0 - market_score)
        
        return {
            "potential_downside_pct": max(0, downside_move * 100),
            "max_loss": max_loss,
            "downside_risk_score": max(0, risk_score),
        }
    
    def _build_bear_reasoning(
        self,
        recommendation: str,
        evidence: Dict,
        counter_arguments: list,
        downside_risk: Dict
    ) -> str:
        """Build bear case reasoning."""
        parts = [
            f"Bear recommendation: {recommendation}",
            f"Bearish evidence score: {evidence.get('score', 0):.1f}/3.0",
        ]
        
        if downside_risk.get("potential_downside_pct", 0) > 0:
            parts.append(f"Potential downside: {downside_risk.get('potential_downside_pct', 0):.1f}%")
        
        if counter_arguments:
            parts.append(f"Concerns: {'; '.join(counter_arguments[:2])}")
        
        return " | ".join(parts)