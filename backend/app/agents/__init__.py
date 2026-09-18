"""AI Agents for autonomous trading analysis and debate."""

from .base import BaseAgent
from .market_scout import MarketScoutAgent
from .options_analyst import OptionsAnalystAgent
from .bull_agent import BullAgent
from .bear_agent import BearAgent
from .strategy_agent import OptionsStrategyAgent
from .risk_agent import RiskAgent
from .decision_agent import DecisionAgent
from .strategy_brain import StrategyBrain
from .red_team_critic import RedTeamCritic
from .macro_hedge import MacroHedgeAgent

__all__ = [
    "BaseAgent",
    "MarketScoutAgent",
    "OptionsAnalystAgent",
    "BullAgent",
    "BearAgent",
    "OptionsStrategyAgent",
    "RiskAgent",
    "DecisionAgent",
    "StrategyBrain",
    "RedTeamCritic",
    "MacroHedgeAgent",
]