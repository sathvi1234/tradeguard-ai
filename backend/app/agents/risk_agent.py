"""Risk Agent - Analyzes risk characteristics (AI opinion only)."""

from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RiskRecommendation(str, Enum):
    """AI risk recommendation (not binding)."""
    APPROVE_CANDIDATE = "approve_candidate"
    REJECT_CANDIDATE = "reject_candidate"
    REQUIRES_REVIEW = "requires_review"


class RiskAgent(BaseAgent):
    """
    AI risk analysis agent (advisory only).
    
    Analyzes:
    - Portfolio exposure
    - Position sizing
    - Maximum loss
    - Concentration
    - Confidence/reward
    - Risk levels
    
    NOTE: This is ONLY an AI opinion.
    The deterministic RiskGuardian has final authority.
    """
    
    def __init__(self):
        """Initialize Risk Agent."""
        super().__init__()
        self.agent_type = AgentType.RISK
    
    async def analyze(
        self,
        symbol: str,
        proposed_size: float,
        portfolio_value: float,
        current_positions: int,
        max_loss: float,
        ai_confidence: float,
        potential_reward: float,
        market_analysis: Optional[Dict[str, Any]] = None,
        options_analysis: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Analyze risk of proposed trade.
        
        Args:
            symbol: Trading symbol
            proposed_size: Proposed position size in USD
            portfolio_value: Current portfolio value
            current_positions: Number of open positions
            max_loss: Maximum estimated loss
            ai_confidence: AI agent confidence score (0-1)
            potential_reward: Potential reward
            market_analysis: Market analysis
            options_analysis: Options analysis
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with risk assessment
        """
        timestamp = datetime.utcnow()
        errors = []
        
        try:
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Analyze position sizing
            sizing_analysis = self._analyze_sizing(
                proposed_size,
                portfolio_value,
                max_loss
            )
            
            # Analyze concentration
            concentration_analysis = self._analyze_concentration(
                proposed_size,
                portfolio_value,
                current_positions
            )
            
            # Analyze confidence/reward
            confidence_analysis = self._analyze_confidence_reward(
                ai_confidence,
                max_loss,
                potential_reward
            )
            
            # Calculate overall risk level
            risk_level, risk_score = self._calculate_risk_level(
                sizing_analysis,
                concentration_analysis,
                confidence_analysis
            )
            
            # Determine recommendation
            recommendation = self._determine_recommendation(
                risk_level,
                risk_score,
                ai_confidence
            )
            
            # Build reasoning
            reasoning = self._build_risk_reasoning(
                risk_level,
                sizing_analysis,
                concentration_analysis,
                confidence_analysis,
                recommendation
            )
            
            # Build warnings
            warnings = self._build_warnings(
                sizing_analysis,
                concentration_analysis,
                confidence_analysis
            )
            
            # Compile data
            data = {
                "recommendation": recommendation.value,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "sizing": sizing_analysis,
                "concentration": concentration_analysis,
                "confidence_reward": confidence_analysis,
                "warnings": warnings,
            }
            
            confidence = 1.0 - risk_score  # Higher confidence when lower risk
            
            analysis = AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=max(0.1, confidence),  # Keep some confidence even if risky
                reasoning=reasoning,
                data=data,
                errors=errors if errors else None
            )
            
            self._log_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Risk analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={},
                errors=[str(e)]
            )
    
    def _analyze_sizing(
        self,
        proposed_size: float,
        portfolio_value: float,
        max_loss: float
    ) -> Dict[str, Any]:
        """Analyze position sizing appropriateness."""
        # Size as % of portfolio
        if portfolio_value > 0:
            size_pct = proposed_size / portfolio_value
        else:
            size_pct = 1.0
        
        # Max loss as % of portfolio
        if portfolio_value > 0:
            loss_pct = max_loss / portfolio_value
        else:
            loss_pct = 1.0
        
        # Assessment
        if size_pct > 0.10:
            size_assessment = "LARGE"
            risk = "High position size"
        elif size_pct > 0.05:
            size_assessment = "MODERATE"
            risk = "Moderate position size"
        else:
            size_assessment = "SMALL"
            risk = None
        
        return {
            "proposed_size": proposed_size,
            "size_pct": size_pct * 100,
            "loss_pct": loss_pct * 100,
            "assessment": size_assessment,
            "risk": risk,
        }
    
    def _analyze_concentration(
        self,
        proposed_size: float,
        portfolio_value: float,
        current_positions: int
    ) -> Dict[str, Any]:
        """Analyze concentration risk."""
        # New position as % of portfolio
        if portfolio_value > 0:
            new_exposure_pct = proposed_size / portfolio_value
        else:
            new_exposure_pct = 1.0
        
        # Position count assessment
        if current_positions >= 5:
            position_assessment = "CONCENTRATED"
            position_risk = "Too many positions"
        elif current_positions >= 3:
            position_assessment = "MODERATE"
            position_risk = None
        else:
            position_assessment = "DIVERSIFIED"
            position_risk = None
        
        # Total exposure assessment
        total_exposure = new_exposure_pct
        if total_exposure > 0.30:
            exposure_assessment = "HIGH"
            exposure_risk = "High portfolio exposure"
        elif total_exposure > 0.15:
            exposure_assessment = "MODERATE"
            exposure_risk = None
        else:
            exposure_assessment = "LOW"
            exposure_risk = None
        
        return {
            "new_exposure_pct": new_exposure_pct * 100,
            "total_exposure_pct": total_exposure * 100,
            "position_count": current_positions,
            "position_assessment": position_assessment,
            "position_risk": position_risk,
            "exposure_assessment": exposure_assessment,
            "exposure_risk": exposure_risk,
        }
    
    def _analyze_confidence_reward(
        self,
        ai_confidence: float,
        max_loss: float,
        potential_reward: float
    ) -> Dict[str, Any]:
        """Analyze confidence and risk/reward."""
        # Risk/reward ratio
        if max_loss > 0:
            risk_reward_ratio = potential_reward / max_loss
        else:
            risk_reward_ratio = 0
        
        # Confidence assessment
        if ai_confidence >= 0.8:
            confidence_assessment = "HIGH"
            confidence_risk = None
        elif ai_confidence >= 0.6:
            confidence_assessment = "MODERATE"
            confidence_risk = None
        elif ai_confidence >= 0.4:
            confidence_assessment = "LOW"
            confidence_risk = "Low AI confidence"
        else:
            confidence_assessment = "VERY_LOW"
            confidence_risk = "Very low AI confidence"
        
        # Risk/reward assessment
        if risk_reward_ratio >= 2.0:
            rr_assessment = "FAVORABLE"
            rr_risk = None
        elif risk_reward_ratio >= 1.0:
            rr_assessment = "ACCEPTABLE"
            rr_risk = None
        elif risk_reward_ratio > 0:
            rr_assessment = "POOR"
            rr_risk = "Poor risk/reward ratio"
        else:
            rr_assessment = "NEGATIVE"
            rr_risk = "Negative risk/reward"
        
        return {
            "ai_confidence": ai_confidence * 100,
            "confidence_assessment": confidence_assessment,
            "confidence_risk": confidence_risk,
            "potential_reward": potential_reward,
            "max_loss": max_loss,
            "risk_reward_ratio": risk_reward_ratio,
            "rr_assessment": rr_assessment,
            "rr_risk": rr_risk,
        }
    
    def _calculate_risk_level(
        self,
        sizing: Dict,
        concentration: Dict,
        confidence_reward: Dict
    ) -> tuple:
        """
        Calculate overall risk level and score.
        
        Returns:
            Tuple of (risk_level, risk_score)
        """
        risk_score = 0.0
        
        # Sizing risk (0-0.3)
        if sizing.get("assessment") == "LARGE":
            risk_score += 0.3
        elif sizing.get("assessment") == "MODERATE":
            risk_score += 0.15
        
        # Concentration risk (0-0.3)
        if concentration.get("position_assessment") == "CONCENTRATED":
            risk_score += 0.2
        if concentration.get("exposure_assessment") == "HIGH":
            risk_score += 0.15
        
        # Confidence/reward risk (0-0.4)
        if confidence_reward.get("rr_assessment") == "NEGATIVE":
            risk_score += 0.25
        elif confidence_reward.get("rr_assessment") == "POOR":
            risk_score += 0.15
        
        if confidence_reward.get("confidence_assessment") == "VERY_LOW":
            risk_score += 0.15
        elif confidence_reward.get("confidence_assessment") == "LOW":
            risk_score += 0.08
        
        risk_score = min(1.0, risk_score)
        
        # Classify risk level
        if risk_score >= 0.7:
            risk_level = "CRITICAL"
        elif risk_score >= 0.5:
            risk_level = "HIGH"
        elif risk_score >= 0.3:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        return risk_level, risk_score
    
    def _determine_recommendation(
        self,
        risk_level: str,
        risk_score: float,
        ai_confidence: float
    ) -> RiskRecommendation:
        """Determine recommendation based on risk analysis."""
        if risk_level == "CRITICAL":
            return RiskRecommendation.REJECT_CANDIDATE
        elif risk_level == "HIGH":
            if ai_confidence >= 0.8:
                return RiskRecommendation.APPROVE_CANDIDATE
            else:
                return RiskRecommendation.REQUIRES_REVIEW
        elif risk_level == "MODERATE":
            return RiskRecommendation.APPROVE_CANDIDATE
        else:
            return RiskRecommendation.APPROVE_CANDIDATE
    
    def _build_risk_reasoning(
        self,
        risk_level: str,
        sizing: Dict,
        concentration: Dict,
        confidence_reward: Dict,
        recommendation: RiskRecommendation
    ) -> str:
        """Build risk analysis reasoning."""
        parts = [
            f"Risk assessment: {risk_level}",
            f"Position sizing: {sizing.get('assessment')}",
            f"Confidence: {confidence_reward.get('confidence_assessment')}",
            f"Risk/reward: {confidence_reward.get('rr_assessment')}",
        ]
        
        return " | ".join(parts)
    
    def _build_warnings(
        self,
        sizing: Dict,
        concentration: Dict,
        confidence_reward: Dict
    ) -> list:
        """Build warning list."""
        warnings = []
        
        if sizing.get("risk"):
            warnings.append(sizing["risk"])
        
        if concentration.get("position_risk"):
            warnings.append(concentration["position_risk"])
        
        if concentration.get("exposure_risk"):
            warnings.append(concentration["exposure_risk"])
        
        if confidence_reward.get("confidence_risk"):
            warnings.append(confidence_reward["confidence_risk"])
        
        if confidence_reward.get("rr_risk"):
            warnings.append(confidence_reward["rr_risk"])
        
        return warnings