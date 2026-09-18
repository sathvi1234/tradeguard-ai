"""Typed contracts for Trade AI cycle context and ORACLE-inspired services."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import TradingMode

DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
LLM_UNAVAILABLE = "LLM_UNAVAILABLE"


class ScenarioType(str, Enum):
    BULL = "BULL"
    FLAT = "FLAT"
    BEAR = "BEAR"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CycleHaltReason(str, Enum):
    NONE = "NONE"
    MISSING_DATA = "MISSING_DATA"
    STALE_DATA = "STALE_DATA"
    INVALID_CONTRACT = "INVALID_CONTRACT"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    CRITICAL_MODE = "CRITICAL_MODE"
    DRY_RUN_ONLY = "DRY_RUN_ONLY"
    LIVE_TRADING_BLOCKED = "LIVE_TRADING_BLOCKED"
    RISK_GUARDIAN_REJECTED = "RISK_GUARDIAN_REJECTED"
    DUPLICATE_CYCLE = "DUPLICATE_CYCLE"
    NO_TRADE = "NO_TRADE"
    MARKET_CLOSED = "MARKET_CLOSED"


class BodyguardAction(str, Enum):
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    HEDGE = "HEDGE"
    FREEZE_NEW_TRADES = "FREEZE_NEW_TRADES"


class RestructuringAction(str, Enum):
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    REDUCE = "REDUCE"
    ROLL = "ROLL"
    HEDGE = "HEDGE"
    REASSESS = "REASSESS"


class StrategyCategory(str, Enum):
    INCOME = "INCOME"
    DIRECTIONAL = "DIRECTIONAL"
    VOLATILITY = "VOLATILITY"
    DEFINED_RISK = "DEFINED_RISK"
    EARNINGS = "EARNINGS"


class TradeOutcome(str, Enum):
    NO_TRADE = "NO_TRADE"
    REJECTED = "REJECTED"
    DRY_RUN_SIMULATED = "DRY_RUN_SIMULATED"
    BLOCKED = "BLOCKED"
    RECORDED = "RECORDED"


class DataAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    EMPTY = "EMPTY"


class StrategyScenario(BaseModel):
    scenario: ScenarioType
    confidence: float = 0.0
    thesis: str = ""
    supporting_evidence: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    invalidation_conditions: List[str] = Field(default_factory=list)
    expected_direction: str = "unknown"
    candidate_strategies: List[str] = Field(default_factory=list)
    evidence_available: bool = False
    llm_status: str = LLM_UNAVAILABLE
    llm_advisory: Optional[str] = None


class RedTeamResult(BaseModel):
    approved_for_review: bool = False
    risk_flags: List[str] = Field(default_factory=list)
    objections: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.0
    advisory_only: bool = True
    llm_status: str = LLM_UNAVAILABLE
    llm_advisory: Optional[str] = None


class MacroContext(BaseModel):
    volatility_environment: str = DATA_UNAVAILABLE
    broad_market_regime: str = DATA_UNAVAILABLE
    interest_rate_context: str = DATA_UNAVAILABLE
    major_event_risk: str = DATA_UNAVAILABLE
    portfolio_exposure: Optional[float] = None
    concentration: Optional[float] = None
    hedge_considerations: List[str] = Field(default_factory=list)
    availability: DataAvailability = DataAvailability.DATA_UNAVAILABLE
    notes: str = DATA_UNAVAILABLE
    llm_status: str = LLM_UNAVAILABLE
    llm_advisory: Optional[str] = None


class BodyguardAssessment(BaseModel):
    action: BodyguardAction = BodyguardAction.HOLD
    reasons: List[str] = Field(default_factory=list)
    freeze_new_trades: bool = False
    positions_reviewed: int = 0
    drawdown_mode: Optional[TradingMode] = None
    advisory_only: bool = True


class TradeMemoryRecord(BaseModel):
    timestamp: datetime
    symbol: Optional[str] = None
    contract: Optional[Dict[str, Any]] = None
    strategy: Optional[str] = None
    decision: Optional[str] = None
    entry: Optional[Dict[str, Any]] = None
    exit: Optional[Dict[str, Any]] = None
    pnl: Optional[float] = None
    risk_mode: Optional[str] = None
    confidence: Optional[float] = None
    agent_reasoning_summaries: Dict[str, str] = Field(default_factory=dict)
    red_team_objections: List[str] = Field(default_factory=list)
    risk_guardian_result: Optional[Dict[str, Any]] = None
    outcome: TradeOutcome = TradeOutcome.NO_TRADE
    lessons: List[str] = Field(default_factory=list)
    dry_run: bool = True
    cycle_id: Optional[str] = None


class StrategyDefinition(BaseModel):
    name: str
    key: str
    category: StrategyCategory
    market_conditions: List[str]
    required_data: List[str]
    max_risk_characteristics: str
    typical_objective: str
    candidate_selection_rules: List[str]
    invalidation_conditions: List[str]
    auto_trade: bool = False
    required_market_fields: List[str] = Field(default_factory=list)


class PortfolioGreeksSnapshot(BaseModel):
    availability: DataAvailability = DataAvailability.DATA_UNAVAILABLE
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None
    portfolio_delta: Optional[float] = None
    portfolio_gamma: Optional[float] = None
    portfolio_theta: Optional[float] = None
    portfolio_vega: Optional[float] = None
    source: str = DATA_UNAVAILABLE
    quality: str = DATA_UNAVAILABLE
    notes: str = "Real option Greeks are required; values are not invented."
    reason_code: str = "NO_OPTION_GREEKS"


class MarketIntelligenceSnapshot(BaseModel):
    availability: DataAvailability = DataAvailability.DATA_UNAVAILABLE
    options_flow: str = DATA_UNAVAILABLE
    volume: str = DATA_UNAVAILABLE
    open_interest: str = DATA_UNAVAILABLE
    volume_profile_poc: str = DATA_UNAVAILABLE
    iv: str = DATA_UNAVAILABLE
    iv_skew: str = DATA_UNAVAILABLE
    vwap: str = DATA_UNAVAILABLE
    anchored_vwap: str = DATA_UNAVAILABLE
    vix_intelligence: str = DATA_UNAVAILABLE
    market_regime: str = DATA_UNAVAILABLE
    earnings_events: str = DATA_UNAVAILABLE
    news_sentiment: str = DATA_UNAVAILABLE
    bid_ask_spread: str = DATA_UNAVAILABLE
    option_chain_structure: str = DATA_UNAVAILABLE
    market_session: str = DATA_UNAVAILABLE
    price: str = DATA_UNAVAILABLE
    bid: str = DATA_UNAVAILABLE
    ask: str = DATA_UNAVAILABLE
    spread: str = DATA_UNAVAILABLE
    previous_close: str = DATA_UNAVAILABLE
    day_change: str = DATA_UNAVAILABLE
    day_change_pct: str = DATA_UNAVAILABLE
    quote_timestamp: str = DATA_UNAVAILABLE
    volatility: str = DATA_UNAVAILABLE
    market_status: str = DATA_UNAVAILABLE
    freshness: str = DATA_UNAVAILABLE
    quote_available: str = DATA_UNAVAILABLE
    notes: str = "No fabricated market intelligence. Sources must be real."


class CopilotResponse(BaseModel):
    question: str
    answer: str
    used_actual_state: bool = True
    unavailable: List[str] = Field(default_factory=list)
    llm_provider: str = DATA_UNAVAILABLE
    llm_status: str = LLM_UNAVAILABLE
    intent: str = "unknown"
    can_execute: bool = False
    sources: List[str] = Field(default_factory=list)


class RestructuringRecommendation(BaseModel):
    action: RestructuringAction = RestructuringAction.HOLD
    reasons: List[str] = Field(default_factory=list)
    symbol: Optional[str] = None
    recommendation_only: bool = True
    requires_risk_guardian: bool = True


class TradingCycleContext(BaseModel):
    cycle_id: str
    timestamp: datetime
    symbol: Optional[str] = None
    dry_run: bool = True
    paper_trading: bool = True
    live_trading_blocked: bool = True
    trading_mode: TradingMode = TradingMode.NORMAL
    drawdown: float = 0.0
    portfolio_value: Optional[float] = None
    cash: Optional[float] = None
    buying_power: Optional[float] = None
    current_positions: int = 0
    data_stale: bool = False
    missing_data: List[str] = Field(default_factory=list)
    halt_reason: CycleHaltReason = CycleHaltReason.NONE
    stages: List[str] = Field(default_factory=list)
    market_intelligence: Optional[MarketIntelligenceSnapshot] = None
    macro: Optional[MacroContext] = None
    scenarios: List[StrategyScenario] = Field(default_factory=list)
    red_team: Optional[RedTeamResult] = None
    debate: Optional[Dict[str, Any]] = None
    risk_guardian_result: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None
    bodyguard: Optional[BodyguardAssessment] = None
    executed: bool = False
    execution_simulated: bool = False

    def record_stage(self, name: str) -> None:
        self.stages.append(name)
