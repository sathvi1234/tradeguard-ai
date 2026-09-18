"""Bull Agent - Makes strongest case FOR the trade."""

from datetime import datetime
from typing import Dict, Any, Optional

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.agents.market_scout import MarketDirection
from app.llm.service import get_llm_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BullAgent(BaseAgent):
    """
    Makes the strongest bullish case FOR the proposed trade.
    
    Analyzes:
    - Bullish evidence
    - Trend strength
    - Momentum
    - Volume patterns
    - Catalysts
    - Options characteristics
    - Upside potential
    """
    
    def __init__(self):
        """Initialize Bull Agent."""
        super().__init__()
        self.agent_type = AgentType.BULL
    
    async def analyze(
        self,
        symbol: str,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Make bullish case for the trade.
        
        Args:
            symbol: Trading symbol
            market_analysis: Market Scout analysis
            options_analysis: Options Analyst analysis
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with bull recommendation
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
            
            # Build bullish evidence
            bullish_evidence = self._gather_bullish_evidence(
                market_direction,
                market_score,
                contract_info,
                greeks,
                liquidity
            )
            
            # Calculate upside potential
            upside_potential = self._calculate_upside(
                contract_info,
                market_data.get("current_price", 0),
                market_score
            )
            
            # Identify risks to the bull thesis
            bull_risks = self._identify_bull_risks(
                market_data,
                options_data,
                contract_info
            )
            
            # Determine recommendation
            if market_direction == MarketDirection.BULLISH.value and market_score > 0.6:
                recommendation = "BUY"
                confidence = 0.7 + (market_score * 0.2)
            elif market_direction == MarketDirection.NEUTRAL.value and market_score > 0.5:
                recommendation = "CONSIDER_BUY"
                confidence = 0.55 + (market_score * 0.15)
            else:
                recommendation = "CAUTION"
                confidence = 0.3 + (market_score * 0.1)
            
            # Build reasoning
            reasoning = self._build_bull_reasoning(
                recommendation,
                bullish_evidence,
                upside_potential,
                bull_risks
            )
            
            # Compile data
            data = {
                "recommendation": recommendation,
                "bullish_evidence": bullish_evidence,
                "upside_potential": upside_potential,
                "risks": bull_risks,
                "market_direction": market_direction,
                "market_score": market_score,
            }
            advisory = await get_llm_service().advise(
                role="bull_agent",
                facts={
                    "symbol": symbol,
                    "recommendation": recommendation,
                    "market_direction": market_direction,
                    "market_score": market_score,
                    "evidence": bullish_evidence,
                    "risks": bull_risks,
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
            logger.error(f"Bull agent analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={},
                errors=[str(e)]
            )
    
    def _gather_bullish_evidence(
        self,
        market_direction: str,
        market_score: float,
        contract_info: Dict,
        greeks: Dict,
        liquidity: Dict
    ) -> Dict[str, Any]:
        """Gather evidence supporting bullish thesis."""
        evidence = {
            "favorable_market_direction": market_direction == MarketDirection.BULLISH.value,
            "strong_momentum": market_score > 0.6,
            "liquid_options": liquidity.get("is_liquid", False),
            "positive_delta": greeks.get("delta", 0) > 0.3,
        }
        
        evidence["score"] = sum([
            1.0 if evidence["favorable_market_direction"] else 0,
            0.8 if evidence["strong_momentum"] else 0,
            0.6 if evidence["liquid_options"] else 0,
            0.7 if evidence["positive_delta"] else 0,
        ])
        
        return evidence
    
    def _calculate_upside(
        self,
        contract_info: Dict,
        current_price: float,
        market_score: float
    ) -> Dict[str, Any]:
        """Calculate upside potential."""
        strike = contract_info.get("strike", 0)
        
        if strike > 0 and current_price > 0:
            potential_move = ((strike * 1.05) - current_price) / current_price
            potential_reward = contract_info.get("potential_reward", 0)
        else:
            potential_move = 0
            potential_reward = 0
        
        # Upside weighted by market score
        upside_score = (potential_move + market_score) / 2 if potential_move > 0 else market_score
        
        return {
            "potential_move_pct": potential_move * 100,
            "potential_reward": potential_reward,
            "upside_score": max(0, upside_score),
        }
    
    def _identify_bull_risks(
        self,
        market_data: Dict,
        options_data: Dict,
        contract_info: Dict
    ) -> list:
        """Identify risks to bull thesis."""
        risks = []
        
        # Volatility risk
        if market_data.get("volatility_score", 0.5) < 0.4:
            risks.append("Low volatility may limit upside")
        
        # Spread risk
        spread_bps = contract_info.get("spread_bps", 0)
        if spread_bps > 30:
            risks.append(f"Wide spread ({spread_bps:.0f} bps) impacts entry")
        
        # Volume risk
        volume = contract_info.get("volume", 0)
        if volume < 10:
            risks.append("Low volume may affect execution")
        
        return risks
    
    def _build_bull_reasoning(
        self,
        recommendation: str,
        evidence: Dict,
        upside: Dict,
        risks: list
    ) -> str:
        """Build bull case reasoning."""
        parts = [
            f"Bull recommendation: {recommendation}",
            f"Supporting evidence score: {evidence.get('score', 0):.1f}/3.0",
        ]
        
        if upside.get("upside_score", 0) > 0:
            parts.append(f"Potential upside: {upside.get('potential_move_pct', 0):.1f}%")
        
        if risks:
            parts.append(f"Risks to thesis: {'; '.join(risks[:2])}")
        
        return " | ".join(parts)