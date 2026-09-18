"""Options Strategy Agent - Evaluates and selects optimal strategy."""

from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OptionsStrategy(str, Enum):
    """Options strategy types."""
    BUY_CALL = "buy_call"
    BUY_PUT = "buy_put"
    DEFINED_RISK_SPREAD = "defined_risk_spread"
    NO_TRADE = "no_trade"


class OptionsStrategyAgent(BaseAgent):
    """
    Evaluates options and selects optimal strategy.
    
    Considers:
    - Strike selection
    - Expiration selection
    - Premium costs
    - Greeks characteristics
    - IV environment
    - Liquidity
    - Risk/reward
    """
    
    def __init__(self):
        """Initialize Options Strategy Agent."""
        super().__init__()
        self.agent_type = AgentType.STRATEGY
    
    async def analyze(
        self,
        symbol: str,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
        bull_analysis: Optional[Dict[str, Any]] = None,
        bear_analysis: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Evaluate options strategies and select optimal one.
        
        Args:
            symbol: Trading symbol
            market_analysis: Market Scout analysis
            options_analysis: Options Analyst analysis
            bull_analysis: Bull agent analysis
            bear_analysis: Bear agent analysis
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with strategy recommendation
        """
        timestamp = datetime.utcnow()
        errors = []
        
        try:
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Extract all analysis data
            market_data = self._analysis_body(market_analysis)
            options_data = self._analysis_body(options_analysis)
            bull_data = self._analysis_body(bull_analysis)
            bear_data = self._analysis_body(bear_analysis)
            
            # Check if we have viable options data
            if not options_data.get("viable", False):
                errors.append("Options data not viable")
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning="Cannot evaluate strategy without viable options data",
                    data={"strategy": OptionsStrategy.NO_TRADE.value},
                    errors=errors
                )
            
            # Evaluate each strategy
            strategies = {
                OptionsStrategy.BUY_CALL: self._evaluate_buy_call(
                    options_data, bull_data, market_data
                ),
                OptionsStrategy.BUY_PUT: self._evaluate_buy_put(
                    options_data, bear_data, market_data
                ),
                OptionsStrategy.DEFINED_RISK_SPREAD: self._evaluate_spread(
                    options_data, market_data
                ),
            }
            
            # Select best strategy
            best_strategy, strategy_score, reasoning = self._select_strategy(
                strategies,
                bull_data,
                bear_data,
                market_data
            )
            
            # Build recommendation details
            strategy_details = self._build_strategy_details(
                best_strategy,
                strategies,
                options_data
            )
            
            # Compile data
            data = {
                "strategy": best_strategy.value,
                "strategy_score": strategy_score,
                "strategy_details": strategy_details,
                "bull_bias": bull_data.get("confidence", 0.5) > 0.5,
                "bear_bias": bear_data.get("confidence", 0.5) > 0.5,
                "all_strategies": {k.value: v for k, v in strategies.items()},
            }
            
            confidence = strategy_score
            
            analysis = AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                errors=errors if errors else None
            )
            
            self._log_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Strategy analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={"strategy": OptionsStrategy.NO_TRADE.value},
                errors=[str(e)]
            )
    
    def _evaluate_buy_call(
        self,
        options_data: Dict,
        bull_data: Dict,
        market_data: Dict
    ) -> Dict[str, Any]:
        """Evaluate BUY_CALL strategy."""
        contract = options_data.get("contract", {})
        greeks = options_data.get("greeks", {})
        risk_reward = options_data.get("risk_reward", {})
        
        score = 0.0
        
        # Favorable for bullish conviction
        bull_confidence = bull_data.get("confidence", 0.5)
        score += bull_confidence * 0.3
        
        # Check positive delta
        delta = greeks.get("delta", 0)
        if delta > 0.3:
            score += 0.2
        
        # Check risk/reward
        rr = risk_reward.get("risk_reward_ratio", 0)
        if rr > 1.5:
            score += 0.2
        
        # Check liquidity
        if options_data.get("liquidity", {}).get("is_liquid", False):
            score += 0.15
        
        # Penalize high theta (time decay)
        theta = greeks.get("theta", 0)
        if theta < -0.05:
            score -= 0.15
        
        return {
            "score": max(0, min(1.0, score)),
            "delta_alignment": delta > 0.3,
            "theta_decay": theta,
            "recommendation": "BUY_CALL",
        }
    
    def _evaluate_buy_put(
        self,
        options_data: Dict,
        bear_data: Dict,
        market_data: Dict
    ) -> Dict[str, Any]:
        """Evaluate BUY_PUT strategy."""
        contract = options_data.get("contract", {})
        greeks = options_data.get("greeks", {})
        risk_reward = options_data.get("risk_reward", {})
        
        score = 0.0
        
        # Favorable for bearish conviction
        bear_confidence = bear_data.get("confidence", 0.5)
        score += bear_confidence * 0.3
        
        # Check negative delta
        delta = greeks.get("delta", 0)
        if delta < -0.3:
            score += 0.2
        
        # Check risk/reward
        rr = risk_reward.get("risk_reward_ratio", 0)
        if rr > 1.5:
            score += 0.2
        
        # Check liquidity
        if options_data.get("liquidity", {}).get("is_liquid", False):
            score += 0.15
        
        # Penalize high theta decay
        theta = greeks.get("theta", 0)
        if theta < -0.05:
            score -= 0.15
        
        return {
            "score": max(0, min(1.0, score)),
            "delta_alignment": delta < -0.3,
            "theta_decay": theta,
            "recommendation": "BUY_PUT",
        }
    
    def _evaluate_spread(
        self,
        options_data: Dict,
        market_data: Dict
    ) -> Dict[str, Any]:
        """Evaluate DEFINED_RISK_SPREAD strategy."""
        contract = options_data.get("contract", {})
        greeks = options_data.get("greeks", {})
        
        score = 0.0
        
        # Prefer spreads in range-bound markets
        market_score = market_data.get("market_score", 0.5)
        if 0.4 < market_score < 0.6:
            score += 0.3
        
        # Prefer spreads to benefit from theta decay
        theta = greeks.get("theta", 0)
        if theta < -0.02:
            score += 0.3
        
        # Spreads defined risk appeals in uncertain conditions
        score += 0.2
        
        # Check liquidity for legs
        if options_data.get("liquidity", {}).get("is_liquid", False):
            score += 0.2
        
        return {
            "score": max(0, min(1.0, score)),
            "defined_risk": True,
            "theta_decay": theta,
            "recommendation": "DEFINED_RISK_SPREAD",
        }
    
    def _select_strategy(
        self,
        strategies: Dict[OptionsStrategy, Dict],
        bull_data: Dict,
        bear_data: Dict,
        market_data: Dict
    ) -> tuple:
        """
        Select best strategy.
        
        Returns:
            Tuple of (strategy, score, reasoning)
        """
        # Score each strategy
        call_score = strategies[OptionsStrategy.BUY_CALL]["score"]
        put_score = strategies[OptionsStrategy.BUY_PUT]["score"]
        spread_score = strategies[OptionsStrategy.DEFINED_RISK_SPREAD]["score"]
        
        # Find best
        scores = {
            OptionsStrategy.BUY_CALL: call_score,
            OptionsStrategy.BUY_PUT: put_score,
            OptionsStrategy.DEFINED_RISK_SPREAD: spread_score,
        }
        
        best_strategy = max(scores, key=scores.get)
        best_score = scores[best_strategy]
        
        # Default to NO_TRADE if all scores are low
        if best_score < 0.4:
            best_strategy = OptionsStrategy.NO_TRADE
            best_score = 0.0
            reasoning = "No strategy scores high enough for execution"
        else:
            reasoning = f"Selected {best_strategy.value} with score {best_score:.2f}"
        
        return best_strategy, best_score, reasoning
    
    def _build_strategy_details(
        self,
        strategy: OptionsStrategy,
        strategies: Dict,
        options_data: Dict
    ) -> Dict[str, Any]:
        """Build strategy execution details."""
        if strategy == OptionsStrategy.NO_TRADE:
            return {"reason": "All strategies scored below threshold"}
        
        contract = options_data.get("contract", {})
        
        return {
            "strike": contract.get("strike"),
            "expiration": contract.get("expiration"),
            "entry_price": contract.get("mid"),
            "bid": contract.get("bid"),
            "ask": contract.get("ask"),
            "strategy_score": strategies.get(strategy, {}).get("score", 0),
        }