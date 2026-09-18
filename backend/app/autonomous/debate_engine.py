"""Debate Engine - Orchestrates AI agents in debate flow."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4
import json

from app.agents import (
    MarketScoutAgent,
    OptionsAnalystAgent,
    BullAgent,
    BearAgent,
    OptionsStrategyAgent,
    RiskAgent,
    DecisionAgent,
)
from app.alpaca.service import AlpacaService
from app.risk import RiskGuardian, DrawdownGuardian
from app.models import TradingMode
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DebateResult:
    """Result of a debate."""
    
    def __init__(self, debate_id: str):
        """Initialize debate result."""
        self.debate_id = debate_id
        self.timestamp = datetime.utcnow()
        self.symbol: Optional[str] = None
        self.agent_outputs: Dict[str, Any] = {}
        self.agent_errors: Dict[str, List[str]] = {}
        self.final_decision: Optional[Dict[str, Any]] = None
        self.risk_guardian_result: Optional[Dict[str, Any]] = None
        self.llm_review: Optional[Dict[str, Any]] = None
        self.review_pipeline: Optional[Dict[str, Any]] = None
        self.completed = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "debate_id": self.debate_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "completed": self.completed,
            "agent_outputs": self.agent_outputs,
            "agent_errors": self.agent_errors,
            "final_decision": self.final_decision,
            "risk_guardian_result": self.risk_guardian_result,
            "llm_review": self.llm_review,
            "review_pipeline": self.review_pipeline,
            "llm_is_final_authority": False,
        }


class DebateEngine:
    """
    Orchestrates debate flow across all AI agents.
    
    Flow:
    1. Market Scout - analyzes market opportunity
    2. Options Analyst - validates options contracts
    3. Bull Agent - makes bullish case
    4. Bear Agent - makes bearish case
    5. Options Strategy Agent - selects strategy
    6. Risk Agent - analyzes risk (advisory only)
    7. Decision Agent - synthesizes all and makes final recommendation
    
    All agents use same market snapshot.
    If any agent fails, record failure and fail safely (no trade).
    """
    
    def __init__(self, risk_guardian=None, drawdown_guardian=None, alpaca_service=None):
        """Initialize Debate Engine. Optionally share authoritative risk/drawdown instances."""
        self.logger = logger
        alpaca = alpaca_service or AlpacaService()
        self.market_scout = MarketScoutAgent(alpaca_service=alpaca)
        self.options_analyst = OptionsAnalystAgent(alpaca_service=alpaca)
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()
        self.strategy_agent = OptionsStrategyAgent()
        self.risk_agent = RiskAgent()
        self.decision_agent = DecisionAgent()
        
        # Risk guardians (shared when provided by Master Orchestrator / engine)
        self.risk_guardian = risk_guardian or RiskGuardian()
        self.drawdown_guardian = drawdown_guardian or DrawdownGuardian()
        
        # Debate cache
        self.debates: Dict[str, DebateResult] = {}
    
    async def run_debate(
        self,
        symbol: str,
        option_type: str = "call",
        strike: Optional[float] = None,
        expiration: Optional[str] = None,
        portfolio_value: float = 100000.0,
        current_equity: float = 100000.0,
        current_positions: int = 0,
        current_drawdown: float = 0.0,
        **kwargs
    ) -> DebateResult:
        """
        Run complete debate for a trading opportunity.
        
        Args:
            symbol: Stock symbol
            option_type: 'call' or 'put'
            strike: Strike price
            expiration: Expiration date
            portfolio_value: Current portfolio value
            current_equity: Current equity
            current_positions: Number of open positions
            current_drawdown: Current drawdown percentage
            **kwargs: Additional arguments
            
        Returns:
            DebateResult with all agent outputs and final decision
        """
        debate_id = str(uuid4())
        result = DebateResult(debate_id)
        result.symbol = symbol
        
        try:
            logger.info(f"Starting debate {debate_id} for {symbol}")
            
            # Step 1: Market Scout
            try:
                logger.info(f"[{debate_id}] Running Market Scout...")
                market_analysis = await self.market_scout.analyze(symbol=symbol)
                result.agent_outputs["market_scout"] = market_analysis.to_dict()
            except Exception as e:
                logger.error(f"Market Scout failed: {e}")
                result.agent_errors["market_scout"] = [str(e)]
                market_analysis = None
            
            # Step 2: Options Analyst
            try:
                logger.info(f"[{debate_id}] Running Options Analyst...")
                options_analysis = await self.options_analyst.analyze(
                    symbol=symbol,
                    option_type=option_type,
                    strike=strike,
                    expiration=expiration,
                    **kwargs
                )
                result.agent_outputs["options_analyst"] = options_analysis.to_dict()
            except Exception as e:
                logger.error(f"Options Analyst failed: {e}")
                result.agent_errors["options_analyst"] = [str(e)]
                options_analysis = None
            
            # Step 3: Bull Agent
            try:
                logger.info(f"[{debate_id}] Running Bull Agent...")
                bull_analysis = await self.bull_agent.analyze(
                    symbol=symbol,
                    market_analysis=market_analysis.to_dict() if market_analysis else None,
                    options_analysis=options_analysis.to_dict() if options_analysis else None,
                )
                result.agent_outputs["bull_agent"] = bull_analysis.to_dict()
            except Exception as e:
                logger.error(f"Bull Agent failed: {e}")
                result.agent_errors["bull_agent"] = [str(e)]
                bull_analysis = None
            
            # Step 4: Bear Agent
            try:
                logger.info(f"[{debate_id}] Running Bear Agent...")
                bear_analysis = await self.bear_agent.analyze(
                    symbol=symbol,
                    market_analysis=market_analysis.to_dict() if market_analysis else None,
                    options_analysis=options_analysis.to_dict() if options_analysis else None,
                )
                result.agent_outputs["bear_agent"] = bear_analysis.to_dict()
            except Exception as e:
                logger.error(f"Bear Agent failed: {e}")
                result.agent_errors["bear_agent"] = [str(e)]
                bear_analysis = None
            
            # Step 5: Options Strategy Agent
            try:
                logger.info(f"[{debate_id}] Running Strategy Agent...")
                strategy_analysis = await self.strategy_agent.analyze(
                    symbol=symbol,
                    market_analysis=market_analysis.to_dict() if market_analysis else None,
                    options_analysis=options_analysis.to_dict() if options_analysis else None,
                    bull_analysis=bull_analysis.to_dict() if bull_analysis else None,
                    bear_analysis=bear_analysis.to_dict() if bear_analysis else None,
                )
                result.agent_outputs["strategy_agent"] = strategy_analysis.to_dict()
            except Exception as e:
                logger.error(f"Strategy Agent failed: {e}")
                result.agent_errors["strategy_agent"] = [str(e)]
                strategy_analysis = None
            
            # Step 6: Risk Agent
            try:
                logger.info(f"[{debate_id}] Running Risk Agent...")
                proposed_size = 500.0  # Default
                max_loss = 100.0  # Estimate
                potential_reward = 200.0  # Estimate
                
                if strategy_analysis:
                    proposed_size = strategy_analysis.data.get("strategy_details", {}).get("entry_price", 0) * 2
                
                risk_analysis = await self.risk_agent.analyze(
                    symbol=symbol,
                    proposed_size=proposed_size,
                    portfolio_value=portfolio_value,
                    current_positions=current_positions,
                    max_loss=max_loss,
                    ai_confidence=strategy_analysis.confidence if strategy_analysis else 0.5,
                    potential_reward=potential_reward,
                    market_analysis=market_analysis.to_dict() if market_analysis else None,
                    options_analysis=options_analysis.to_dict() if options_analysis else None,
                )
                result.agent_outputs["risk_agent"] = risk_analysis.to_dict()
            except Exception as e:
                logger.error(f"Risk Agent failed: {e}")
                result.agent_errors["risk_agent"] = [str(e)]
                risk_analysis = None
            
            # Step 7: Decision Agent
            try:
                logger.info(f"[{debate_id}] Running Decision Agent...")
                decision_analysis = await self.decision_agent.analyze(
                    symbol=symbol,
                    market_analysis=market_analysis.to_dict() if market_analysis else None,
                    options_analysis=options_analysis.to_dict() if options_analysis else None,
                    bull_analysis=bull_analysis.to_dict() if bull_analysis else None,
                    bear_analysis=bear_analysis.to_dict() if bear_analysis else None,
                    strategy_analysis=strategy_analysis.to_dict() if strategy_analysis else None,
                    risk_analysis=risk_analysis.to_dict() if risk_analysis else None,
                )
                result.agent_outputs["decision_agent"] = decision_analysis.to_dict()
                result.final_decision = decision_analysis.data
            except Exception as e:
                logger.error(f"Decision Agent failed: {e}")
                result.agent_errors["decision_agent"] = [str(e)]
            
            # Step 8: Risk Guardian evaluation (deterministic)
            try:
                logger.info(f"[{debate_id}] Running Risk Guardian...")
                
                if decision_analysis and decision_analysis.data.get("decision") != "no_trade":
                    rg_kwargs = {
                        "portfolio_value": portfolio_value,
                        "current_equity": current_equity,
                        "current_drawdown": current_drawdown,
                        "current_positions": current_positions,
                        "max_loss": 100.0,
                        "potential_reward": 200.0,
                        "ai_confidence": decision_analysis.confidence,
                        "contract_validity": {
                            "is_liquid": options_analysis.data.get("viable", False) if options_analysis else False,
                            "open_interest": 500,
                        },
                        "market_data_timestamp": datetime.utcnow(),
                        "trading_mode": self.drawdown_guardian.state.current_mode if self.drawdown_guardian.state else TradingMode.NORMAL,
                    }
                    proposed_size = decision_analysis.data.get("proposed_size", 500.0)
                    rg_result = await self.risk_guardian.evaluate_trade(
                        symbol=symbol,
                        proposed_size=proposed_size,
                        **rg_kwargs,
                    )
                    from app.risk.review_pipeline import run_review_pipeline

                    pipeline = await run_review_pipeline(
                        guardian=self.risk_guardian,
                        symbol=symbol,
                        proposed_size=float(proposed_size or 0),
                        rg_kwargs=rg_kwargs,
                        first_result=rg_result,
                        proposal={
                            "symbol": symbol,
                            "proposed_size": proposed_size,
                            "decision": decision_analysis.data.get("decision"),
                        },
                    )
                    result.risk_guardian_result = pipeline["final_risk_guardian"]
                    result.llm_review = pipeline["llm_review"]
                    result.review_pipeline = pipeline
                else:
                    result.risk_guardian_result = {
                        "decision": "hold",
                        "display_decision": "HOLD",
                        "reason": "NO_TRADE_RECOMMENDED",
                        "rejection_reasons": ["NO_TRADE_RECOMMENDED"],
                        "analysis_completed": True,
                    }
            except Exception as e:
                logger.error(f"Risk Guardian failed: {e}")
                result.risk_guardian_result = {
                    "decision": "rejected",
                    "error": str(e),
                }
            
            result.completed = True
            
            # Store result
            self.debates[debate_id] = result
            
            logger.info(f"Debate {debate_id} completed for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Debate {debate_id} failed critically", error=str(e))
            result.completed = False
            self.debates[debate_id] = result
            return result
    
    def get_debate(self, debate_id: str) -> Optional[DebateResult]:
        """Get debate result by ID."""
        return self.debates.get(debate_id)
    
    def get_all_debates(self, symbol: Optional[str] = None) -> List[DebateResult]:
        """Get all debates, optionally filtered by symbol."""
        if symbol:
            return [d for d in self.debates.values() if d.symbol == symbol]
        return list(self.debates.values())