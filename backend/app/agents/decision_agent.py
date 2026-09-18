"""Decision Agent - Synthesizes all analyses and makes final recommendation."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.agents.strategy_agent import OptionsStrategy
from app.llm.service import get_llm_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DecisionAgent(BaseAgent):
    """
    Synthesizes all agent analyses and makes final recommendation.
    
    Rules:
    - Bull/Bear conflict lowers confidence
    - Missing information = NO_TRADE
    - Low confidence = NO_TRADE
    - Poor risk/reward = NO_TRADE
    - High risk = NO_TRADE
    
    Decision Agent NEVER submits an order.
    """
    
    def __init__(self):
        """Initialize Decision Agent."""
        super().__init__()
        self.agent_type = AgentType.DECISION
    
    async def analyze(
        self,
        symbol: str,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
        bull_analysis: Optional[Dict[str, Any]] = None,
        bear_analysis: Optional[Dict[str, Any]] = None,
        strategy_analysis: Optional[Dict[str, Any]] = None,
        risk_analysis: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Synthesize all analyses and make final decision.
        
        Args:
            symbol: Trading symbol
            market_analysis: Market Scout analysis
            options_analysis: Options Analyst analysis
            bull_analysis: Bull Agent analysis
            bear_analysis: Bear Agent analysis
            strategy_analysis: Strategy Agent analysis
            risk_analysis: Risk Agent analysis
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with final decision and recommendation
        """
        timestamp = datetime.utcnow()
        errors = []
        
        try:
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Check for missing analyses
            missing = self._check_missing_analyses(
                market_analysis,
                options_analysis,
                bull_analysis,
                bear_analysis,
                strategy_analysis,
                risk_analysis
            )
            
            if missing:
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning=f"Cannot make decision: Missing {len(missing)} analyses",
                    data={
                        "decision": OptionsStrategy.NO_TRADE.value,
                        "missing_analyses": missing,
                    },
                    errors=missing
                )
            
            # Extract data from all analyses
            market_data = market_analysis.get("data", {})
            options_data = options_analysis.get("data", {})
            bull_data = bull_analysis.get("data", {})
            bear_data = bear_analysis.get("data", {})
            strategy_data = strategy_analysis.get("data", {})
            risk_data = risk_analysis.get("data", {})
            
            # Analyze agent disagreement
            disagreement_score, disagreement_analysis = self._analyze_disagreement(
                bull_analysis,
                bear_analysis
            )
            
            # Calculate composite confidence
            composite_confidence = self._calculate_composite_confidence(
                market_analysis,
                options_analysis,
                bull_analysis,
                bear_analysis,
                strategy_analysis,
                risk_analysis,
                disagreement_score
            )
            
            # Extract strategy recommendation
            strategy = strategy_data.get("strategy", OptionsStrategy.NO_TRADE.value)
            
            # Check decision rules
            decision_reasoning = self._check_decision_rules(
                symbol,
                strategy,
                composite_confidence,
                options_data,
                bull_data,
                bear_data,
                risk_data,
                disagreement_analysis
            )
            
            # Make final decision
            final_decision = decision_reasoning.get("decision", OptionsStrategy.NO_TRADE.value)
            final_confidence = decision_reasoning.get("confidence", 0.0)
            
            # Build selected contracts info
            selected_contracts = self._build_selected_contracts(
                options_data,
                final_decision,
                strategy_data
            )
            
            # Build position size recommendation
            proposed_size = self._calculate_proposed_size(
                final_decision,
                composite_confidence,
                risk_data
            )
            
            # Build complete reasoning
            reasoning = self._build_complete_reasoning(
                final_decision,
                final_confidence,
                disagreement_analysis,
                decision_reasoning
            )
            
            # Compile all debate data
            data = {
                "decision": final_decision,
                "proposed_size": proposed_size,
                "confidence": final_confidence,
                "composite_confidence_calc": composite_confidence,
                "selected_contracts": selected_contracts,
                "disagreement_score": disagreement_score,
                "disagreement_analysis": disagreement_analysis,
                "market_view": market_data.get("direction", "neutral"),
                "bull_recommendation": bull_data.get("recommendation", "unknown"),
                "bear_recommendation": bear_data.get("recommendation", "unknown"),
                "strategy_recommendation": strategy,
                "risk_level": risk_data.get("risk_level", "unknown"),
                "decision_rules": decision_reasoning.get("rules_violated", []),
            }
            advisory = await get_llm_service().advise(
                role="decision_explanation",
                facts={
                    "symbol": symbol,
                    "decision": final_decision,
                    "confidence": final_confidence,
                    "proposed_size": proposed_size,
                    "rules_violated": decision_reasoning.get("rules_violated", []),
                    "market_view": market_data.get("direction", "neutral"),
                    "bull_recommendation": bull_data.get("recommendation", "unknown"),
                    "bear_recommendation": bear_data.get("recommendation", "unknown"),
                },
            )
            data["llm_status"] = advisory.status
            data["llm_explanation"] = advisory.summary
            data["llm_advisory_only"] = True
            if advisory.summary:
                reasoning = f"{reasoning} | LLM explanation (advisory): {advisory.summary}"
            
            analysis = AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=final_confidence,
                reasoning=reasoning,
                data=data,
                errors=errors if errors else None
            )
            
            self._log_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Decision analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={"decision": OptionsStrategy.NO_TRADE.value},
                errors=[str(e)]
            )
    
    def _check_missing_analyses(self, *analyses) -> list:
        """Check for missing or invalid analyses."""
        missing = []
        
        analysis_names = [
            "market",
            "options",
            "bull",
            "bear",
            "strategy",
            "risk",
        ]
        
        for i, analysis in enumerate(analyses):
            if not analysis or analysis.get("confidence", 0) == 0:
                missing.append(analysis_names[i])
        
        return missing
    
    def _analyze_disagreement(
        self,
        bull_analysis: Dict,
        bear_analysis: Dict
    ) -> tuple:
        """
        Analyze Bull/Bear disagreement.
        
        Returns:
            Tuple of (disagreement_score, analysis_dict)
        """
        bull_confidence = bull_analysis.get("confidence", 0.5)
        bear_confidence = bear_analysis.get("confidence", 0.5)
        
        bull_rec = bull_analysis.get("data", {}).get("recommendation", "unknown")
        bear_rec = bear_analysis.get("data", {}).get("recommendation", "unknown")
        
        # Calculate disagreement magnitude
        disagreement_magnitude = abs(bull_confidence - bear_confidence)
        
        # Are they genuinely opposed?
        opposing = False
        if ("BUY" in bull_rec and ("AVOID" in bear_rec or "WAIT" in bear_rec)):
            opposing = True
        elif ("AVOID" in bull_rec and "BUY" in bear_rec):
            opposing = True
        
        # Disagreement score (0 = perfect agreement, 1 = maximum disagreement)
        if opposing:
            disagreement_score = 0.5 + (disagreement_magnitude * 0.5)
        else:
            disagreement_score = disagreement_magnitude * 0.3
        
        analysis = {
            "bull_confidence": bull_confidence,
            "bear_confidence": bear_confidence,
            "bull_recommendation": bull_rec,
            "bear_recommendation": bear_rec,
            "genuinely_opposing": opposing,
            "disagreement_score": disagreement_score,
        }
        
        return disagreement_score, analysis
    
    def _calculate_composite_confidence(
        self,
        market_analysis: Dict,
        options_analysis: Dict,
        bull_analysis: Dict,
        bear_analysis: Dict,
        strategy_analysis: Dict,
        risk_analysis: Dict,
        disagreement_score: float
    ) -> Dict[str, Any]:
        """
        Calculate composite confidence from all agents.
        
        Returns:
            Dictionary with composite confidence calculation
        """
        market_conf = market_analysis.get("confidence", 0.5)
        options_conf = options_analysis.get("confidence", 0.5)
        bull_conf = bull_analysis.get("confidence", 0.5)
        bear_conf = bear_analysis.get("confidence", 0.5)
        strategy_conf = strategy_analysis.get("confidence", 0.5)
        risk_conf = 1.0 - risk_analysis.get("data", {}).get("risk_score", 0.5)
        
        # Base composite (equal weight)
        base_composite = (
            market_conf * 0.15 +
            options_conf * 0.15 +
            bull_conf * 0.2 +
            bear_conf * 0.2 +
            strategy_conf * 0.15 +
            risk_conf * 0.15
        )
        
        # Adjust for disagreement (lower confidence if agents disagree)
        disagreement_penalty = disagreement_score * 0.2
        
        final_composite = base_composite - disagreement_penalty
        
        return {
            "base": base_composite,
            "market_conf": market_conf,
            "options_conf": options_conf,
            "bull_conf": bull_conf,
            "bear_conf": bear_conf,
            "strategy_conf": strategy_conf,
            "risk_conf": risk_conf,
            "disagreement_penalty": disagreement_penalty,
            "final": max(0.0, min(1.0, final_composite)),
        }
    
    def _check_decision_rules(
        self,
        symbol: str,
        strategy: str,
        composite_confidence: float,
        options_data: Dict,
        bull_data: Dict,
        bear_data: Dict,
        risk_data: Dict,
        disagreement_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Check decision rules and determine if trade should proceed.
        
        Returns:
            Dictionary with decision and reasoning
        """
        rules_violated = []
        decision = strategy
        confidence = composite_confidence
        
        # Rule 1: Missing information = NO_TRADE
        if not options_data or not options_data.get("viable", False):
            rules_violated.append("Options data not viable")
            decision = OptionsStrategy.NO_TRADE.value
        
        # Rule 2: Low confidence = NO_TRADE
        if composite_confidence < 0.5:
            rules_violated.append(f"Confidence too low: {composite_confidence:.2%}")
            decision = OptionsStrategy.NO_TRADE.value
            confidence = 0.0
        
        # Rule 3: Poor risk/reward = NO_TRADE
        rr_ratio = options_data.get("risk_reward", {}).get("risk_reward_ratio", 0)
        if rr_ratio < 1.0 and rr_ratio > 0:
            rules_violated.append(f"Risk/reward too poor: {rr_ratio:.2f}")
            decision = OptionsStrategy.NO_TRADE.value
        
        # Rule 4: High risk = NO_TRADE
        risk_level = risk_data.get("risk_level", "LOW")
        if risk_level == "CRITICAL":
            rules_violated.append("Risk level CRITICAL")
            decision = OptionsStrategy.NO_TRADE.value
        elif risk_level == "HIGH" and composite_confidence < 0.7:
            rules_violated.append("High risk with low confidence")
            decision = OptionsStrategy.NO_TRADE.value
        
        # Rule 5: Strong disagreement lowers confidence
        if disagreement_analysis.get("genuinely_opposing", False):
            if disagreement_analysis.get("disagreement_score", 0) > 0.6:
                rules_violated.append("Bull/Bear strongly opposed")
                confidence *= 0.7
        
        return {
            "decision": decision,
            "confidence": max(0.0, min(1.0, confidence)),
            "rules_violated": rules_violated,
        }
    
    def _build_selected_contracts(
        self,
        options_data: Dict,
        decision: str,
        strategy_data: Dict
    ) -> Optional[Dict[str, Any]]:
        """Build selected contracts information."""
        if decision == OptionsStrategy.NO_TRADE.value:
            return None
        
        contract = options_data.get("contract", {})
        
        return {
            "symbol": contract.get("symbol"),
            "type": contract.get("type"),
            "strike": contract.get("strike"),
            "expiration": contract.get("expiration"),
            "entry_price": contract.get("mid"),
            "bid": contract.get("bid"),
            "ask": contract.get("ask"),
            "strategy": decision,
        }
    
    def _calculate_proposed_size(
        self,
        decision: str,
        confidence: float,
        risk_data: Dict
    ) -> float:
        """Calculate proposed position size."""
        if decision == OptionsStrategy.NO_TRADE.value:
            return 0.0
        
        # Base size on risk recommendation
        risk_rec = risk_data.get("recommendation", "reject_candidate")
        
        if risk_rec == "reject_candidate":
            return 0.0
        elif risk_rec == "requires_review":
            return 100.0
        else:  # approve_candidate
            # Scale by confidence
            base_size = 500.0
            return base_size * confidence
    
    def _build_complete_reasoning(
        self,
        decision: str,
        confidence: float,
        disagreement_analysis: Dict,
        decision_reasoning: Dict
    ) -> str:
        """Build comprehensive reasoning explanation."""
        parts = [
            f"Decision: {decision}",
            f"Confidence: {confidence:.1%}",
        ]
        
        if disagreement_analysis.get("genuinely_opposing", False):
            parts.append("Bull/Bear in genuine disagreement")
        
        if decision_reasoning.get("rules_violated"):
            violations = decision_reasoning["rules_violated"]
            parts.append(f"Violations: {'; '.join(violations[:2])}")
        
        if decision == OptionsStrategy.NO_TRADE.value:
            parts.append("Trade blocked by decision rules")
        
        return " | ".join(parts)