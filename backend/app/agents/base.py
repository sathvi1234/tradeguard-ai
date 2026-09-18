"""Base agent class for all AI agents in TradeGuard AI."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentType(str, Enum):
    """Agent type enumeration."""
    MARKET_SCOUT = "market_scout"
    OPTIONS_ANALYST = "options_analyst"
    BULL = "bull"
    BEAR = "bear"
    STRATEGY = "strategy"
    RISK = "risk"
    DECISION = "decision"
    STRATEGY_BRAIN = "strategy_brain"
    RED_TEAM = "red_team"
    MACRO_HEDGE = "macro_hedge"


class ConfidenceLevel(str, Enum):
    """Confidence level enumeration."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class AgentAnalysis:
    """Base analysis result from an agent."""
    agent_type: AgentType
    symbol: str
    timestamp: datetime
    confidence: float  # 0.0 to 1.0
    reasoning: str
    data: Dict[str, Any]  # Agent-specific data
    errors: Optional[list] = None  # List of errors if any
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['agent_type'] = self.agent_type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level based on score."""
        if self.confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


class BaseAgent(ABC):
    """Base class for all AI agents."""
    
    def __init__(self):
        """Initialize base agent."""
        self.agent_type: AgentType = AgentType.MARKET_SCOUT  # Override in subclass
        self.logger = logger
    
    @abstractmethod
    async def analyze(self, **kwargs) -> AgentAnalysis:
        """
        Analyze market data and return analysis.
        
        Must be implemented by subclasses.
        
        Returns:
            AgentAnalysis: Analysis result from the agent
        """
        pass
    
    def _validate_symbol(self, symbol: str) -> bool:
        """Validate symbol format."""
        if not symbol or not isinstance(symbol, str):
            return False
        
        # Basic validation - symbol should be 1-5 characters
        if len(symbol) < 1 or len(symbol) > 5:
            return False
        
        # Symbol should be alphanumeric
        if not symbol.replace('_', '').isalnum():
            return False
        
        return True
    
    def _validate_confidence(self, confidence: float) -> bool:
        """Validate confidence score (0.0 to 1.0)."""
        return isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0

    @staticmethod
    def _analysis_body(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Accept either a raw dict or AgentAnalysis.to_dict() with nested data."""
        if not payload:
            return {}
        nested = payload.get("data")
        if isinstance(nested, dict):
            body = dict(nested)
            for key in ("viable", "confidence", "direction"):
                if key in payload and key not in body:
                    body[key] = payload[key]
            return body
        return payload
    
    def _log_analysis(self, analysis: AgentAnalysis) -> None:
        """Log agent analysis."""
        self.logger.info(
            f"{self.agent_type.value} analysis",
            symbol=analysis.symbol,
            confidence=analysis.confidence,
            confidence_level=analysis.confidence_level.value,
            timestamp=analysis.timestamp.isoformat()
        )
    
    def _log_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """Log agent error."""
        error_context = context or {}
        self.logger.error(
            f"{self.agent_type.value} error",
            error=str(error),
            error_type=type(error).__name__,
            **error_context
        )


class AgentChain:
    """Chain of agents for sequential execution."""
    
    def __init__(self, agents: list):
        """
        Initialize agent chain.
        
        Args:
            agents: List of agents to execute in order
        """
        self.agents = agents
        self.logger = logger
    
    async def execute(self, **kwargs) -> Dict[str, AgentAnalysis]:
        """
        Execute all agents in sequence.
        
        Args:
            **kwargs: Arguments to pass to agents
            
        Returns:
            Dictionary of agent results
        """
        results = {}
        
        for agent in self.agents:
            try:
                self.logger.info(f"Executing {agent.agent_type.value}")
                analysis = await agent.analyze(**kwargs)
                results[agent.agent_type.value] = analysis
                
            except Exception as e:
                self.logger.error(
                    f"Agent execution failed: {agent.agent_type.value}",
                    error=str(e)
                )
                results[agent.agent_type.value] = None
        
        return results