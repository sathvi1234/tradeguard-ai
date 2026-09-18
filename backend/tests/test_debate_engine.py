"""Comprehensive tests for the debate engine and all AI agents."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from app.autonomous.debate_engine import DebateEngine, DebateResult
from app.agents import (
    MarketScoutAgent,
    OptionsAnalystAgent,
    BullAgent,
    BearAgent,
    OptionsStrategyAgent,
    RiskAgent,
    DecisionAgent,
)
from app.agents.base import AgentType, ConfidenceLevel
from app.risk import RiskGuardian, DrawdownGuardian
from app.models import TradingMode


@pytest.mark.asyncio
class TestMarketScoutAgent:
    """Tests for Market Scout Agent."""
    
    async def test_market_scout_bullish_opportunity(self):
        """Test Market Scout identifies bullish opportunity."""
        agent = MarketScoutAgent()
        
        # Mock Alpaca service
        with patch.object(agent.alpaca_service, 'get_market_data', new_callable=AsyncMock) as mock_data:
            mock_data.return_value = {
                "ask_price": 105.0,
                "bid_price": 104.95,
                "bid_size": 1000,
                "ask_size": 1000,
                "market_open": True,
            }
            
            analysis = await agent.analyze(symbol="AAPL")
            
            assert analysis.agent_type == AgentType.MARKET_SCOUT
            assert analysis.symbol == "AAPL"
            assert analysis.confidence > 0
            assert "direction" in analysis.data
    
    async def test_market_scout_invalid_symbol(self):
        """Test Market Scout rejects invalid symbol."""
        agent = MarketScoutAgent()
        
        analysis = await agent.analyze(symbol="")
        
        assert analysis.confidence == 0.0
        assert analysis.errors is not None
    
    async def test_market_scout_market_data_unavailable(self):
        """Test Market Scout handles missing market data."""
        agent = MarketScoutAgent()
        
        with patch.object(agent.alpaca_service, 'get_market_data', new_callable=AsyncMock) as mock_data:
            mock_data.side_effect = Exception("Service unavailable")
            
            analysis = await agent.analyze(symbol="AAPL")
            
            assert analysis.confidence == 0.0
            assert analysis.errors is not None


@pytest.mark.asyncio
class TestOptionsAnalystAgent:
    """Tests for Options Analyst Agent."""
    
    async def test_options_analyst_valid_contract(self):
        """Test Options Analyst validates good contract."""
        agent = OptionsAnalystAgent()
        
        with patch.object(agent, '_get_options_contract_data', new_callable=AsyncMock) as mock_data:
            mock_data.return_value = {
                "bid": 2.50,
                "ask": 2.51,
                "volume": 100,
                "open_interest": 500,
                "expiration": "2024-12-20",
                "strike": 105.0,
                "iv": 0.25,
                "delta": 0.5,
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.15,
            }
            
            analysis = await agent.analyze(
                symbol="AAPL",
                option_type="call",
                strike=105.0,
                expiration="2024-12-20"
            )
            
            assert analysis.symbol == "AAPL"
            assert analysis.confidence > 0.5
            assert analysis.data.get("viable") == True
    
    async def test_options_analyst_rejects_stale_quote(self):
        """Test Options Analyst rejects stale quotes."""
        agent = OptionsAnalystAgent()
        
        with patch.object(agent, '_get_options_contract_data', new_callable=AsyncMock) as mock_data:
            mock_data.return_value = {
                "bid": 0,
                "ask": 0,
                "volume": 0,
                "open_interest": 0,
                "expiration": "2024-12-20",
                "strike": 105.0,
                "iv": 0.25,
                "delta": 0.5,
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.15,
            }
            
            analysis = await agent.analyze(
                symbol="AAPL",
                option_type="call",
                strike=105.0,
                expiration="2024-12-20"
            )
            
            assert analysis.confidence == 0.0
            assert "No quotes available" in " ".join(analysis.errors or [])
    
    async def test_options_analyst_rejects_low_liquidity(self):
        """Test Options Analyst rejects low liquidity contracts."""
        agent = OptionsAnalystAgent()
        
        with patch.object(agent, '_get_options_contract_data', new_callable=AsyncMock) as mock_data:
            mock_data.return_value = {
                "bid": 2.50,
                "ask": 2.55,
                "volume": 0,
                "open_interest": 50,  # Below threshold of 100
                "expiration": "2024-12-20",
                "strike": 105.0,
                "iv": 0.25,
                "delta": 0.5,
                "gamma": 0.05,
                "theta": -0.02,
                "vega": 0.15,
            }
            
            analysis = await agent.analyze(
                symbol="AAPL",
                option_type="call",
                strike=105.0,
                expiration="2024-12-20"
            )
            
            assert analysis.confidence == 0.0


@pytest.mark.asyncio
class TestBullBearAgents:
    """Tests for Bull and Bear Agents."""
    
    async def test_bull_agent_bullish_market(self):
        """Test Bull Agent makes case in bullish market."""
        agent = BullAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis={
                "data": {
                    "direction": "bullish",
                    "market_score": 0.7,
                    "current_price": 100.0,
                }
            },
            options_analysis={
                "data": {
                    "contract": {"strike": 105.0, "volume": 100, "open_interest": 500},
                    "greeks": {"delta": 0.6},
                    "liquidity": {"is_liquid": True},
                    "risk_reward": {"risk_reward_ratio": 2.0},
                }
            }
        )
        
        assert analysis.agent_type == AgentType.BULL
        assert analysis.confidence > 0.5
        assert "BUY" in analysis.data.get("recommendation", "")
    
    async def test_bear_agent_bearish_market(self):
        """Test Bear Agent challenges in bearish market."""
        agent = BearAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis={
                "data": {
                    "direction": "bearish",
                    "market_score": 0.3,
                }
            },
            options_analysis={
                "data": {
                    "contract": {"strike": 105.0, "spread_bps": 50},
                    "greeks": {"delta": -0.4, "theta": -0.03},
                    "liquidity": {"is_liquid": False},
                }
            }
        )
        
        assert analysis.agent_type == AgentType.BEAR
        assert "AVOID" in analysis.data.get("recommendation", "")


@pytest.mark.asyncio
class TestStrategyAgent:
    """Tests for Options Strategy Agent."""
    
    async def test_strategy_agent_selects_buy_call(self):
        """Test Strategy Agent selects BUY_CALL in bull scenario."""
        agent = OptionsStrategyAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis={"data": {"market_score": 0.7}},
            options_analysis={
                "data": {
                    "viable": True,
                    "contract": {
                        "strike": 105.0,
                        "expiration": "2024-12-20",
                        "mid": 2.5,
                        "bid": 2.45,
                        "ask": 2.55,
                    },
                    "greeks": {"delta": 0.6, "theta": -0.02},
                    "liquidity": {"is_liquid": True},
                    "risk_reward": {"risk_reward_ratio": 1.8},
                }
            },
            bull_analysis={"data": {"confidence": 0.75}},
            bear_analysis={"data": {"confidence": 0.35}}
        )
        
        assert analysis.agent_type == AgentType.STRATEGY
        assert "buy_call" in analysis.data.get("strategy", "").lower()
    
    async def test_strategy_agent_no_trade_poor_viability(self):
        """Test Strategy Agent selects NO_TRADE for poor viability."""
        agent = OptionsStrategyAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis={"data": {"market_score": 0.5}},
            options_analysis={
                "data": {
                    "viable": False,
                }
            },
            bull_analysis={"data": {"confidence": 0.5}},
            bear_analysis={"data": {"confidence": 0.5}}
        )
        
        assert "no_trade" in analysis.data.get("strategy", "").lower()


@pytest.mark.asyncio
class TestRiskAgent:
    """Tests for Risk Agent."""
    
    async def test_risk_agent_low_risk(self):
        """Test Risk Agent assesses low risk appropriately."""
        agent = RiskAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            proposed_size=500.0,
            portfolio_value=100000.0,
            current_positions=2,
            max_loss=100.0,
            ai_confidence=0.75,
            potential_reward=200.0
        )
        
        assert analysis.agent_type == AgentType.RISK
        assert analysis.data.get("risk_level") in ["LOW", "MODERATE"]
        assert "approve" in analysis.data.get("recommendation", "").lower()
    
    async def test_risk_agent_high_risk(self):
        """Test Risk Agent rejects high risk."""
        agent = RiskAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            proposed_size=50000.0,  # 50% of portfolio
            portfolio_value=100000.0,
            current_positions=8,
            max_loss=10000.0,
            ai_confidence=0.3,
            potential_reward=5000.0
        )
        
        assert analysis.data.get("risk_level") in ["HIGH", "CRITICAL"]


@pytest.mark.asyncio
class TestDecisionAgent:
    """Tests for Decision Agent."""
    
    async def test_decision_agent_missing_analyses(self):
        """Test Decision Agent blocks trade with missing analyses."""
        agent = DecisionAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis=None,
            options_analysis=None,
        )
        
        assert analysis.data.get("decision") == "no_trade"
        assert analysis.confidence == 0.0
    
    async def test_decision_agent_low_confidence_no_trade(self):
        """Test Decision Agent rejects low confidence."""
        agent = DecisionAgent()
        
        analysis = await agent.analyze(
            symbol="AAPL",
            market_analysis={"data": {}, "confidence": 0.3},
            options_analysis={"data": {"viable": False}, "confidence": 0.2},
            bull_analysis={"data": {}, "confidence": 0.4},
            bear_analysis={"data": {}, "confidence": 0.6},
            strategy_analysis={"data": {"strategy": "buy_call"}, "confidence": 0.25},
            risk_analysis={"data": {"risk_level": "HIGH"}, "confidence": 0.3}
        )
        
        assert analysis.data.get("decision") == "no_trade"


@pytest.mark.asyncio
class TestRiskGuardian:
    """Tests for Deterministic Risk Guardian."""
    
    async def test_risk_guardian_approves_safe_trade(self):
        """Test Risk Guardian approves safe trade."""
        guardian = RiskGuardian()
        
        result = await guardian.evaluate_trade(
            symbol="AAPL",
            proposed_size=500.0,
            portfolio_value=100000.0,
            current_equity=100000.0,
            current_drawdown=0.05,
            current_positions=2,
            max_loss=100.0,
            potential_reward=200.0,
            ai_confidence=0.75,
            contract_validity={
                "is_liquid": True,
                "open_interest": 500,
            },
            market_data_timestamp=datetime.utcnow(),
            trading_mode=TradingMode.NORMAL,
        )
        
        assert result.decision.value == "approved"
    
    async def test_risk_guardian_rejects_excessive_drawdown(self):
        """Test Risk Guardian blocks trade at critical drawdown."""
        guardian = RiskGuardian()
        
        result = await guardian.evaluate_trade(
            symbol="AAPL",
            proposed_size=500.0,
            portfolio_value=100000.0,
            current_equity=85000.0,
            current_drawdown=0.16,  # Above 15% critical threshold
            current_positions=2,
            max_loss=100.0,
            potential_reward=200.0,
            ai_confidence=0.9,
            contract_validity={
                "is_liquid": True,
                "open_interest": 500,
            },
            market_data_timestamp=datetime.utcnow(),
            trading_mode=TradingMode.CRITICAL,
        )
        
        assert result.decision.value == "rejected"
    
    async def test_risk_guardian_rejects_low_confidence(self):
        """Test Risk Guardian rejects below minimum confidence."""
        guardian = RiskGuardian()
        
        result = await guardian.evaluate_trade(
            symbol="AAPL",
            proposed_size=500.0,
            portfolio_value=100000.0,
            current_equity=100000.0,
            current_drawdown=0.0,
            current_positions=2,
            max_loss=100.0,
            potential_reward=200.0,
            ai_confidence=0.5,  # Below 60% threshold
            contract_validity={
                "is_liquid": True,
                "open_interest": 500,
            },
            market_data_timestamp=datetime.utcnow(),
            trading_mode=TradingMode.NORMAL,
        )
        
        assert result.decision.value == "rejected"


@pytest.mark.asyncio
class TestDrawdownGuardian:
    """Tests for DrawdownGuardian mode transitions."""
    
    async def test_drawdown_guardian_initialization(self):
        """Test DrawdownGuardian initializes correctly."""
        guardian = DrawdownGuardian()
        
        state = guardian.initialize(100000.0)
        
        assert state.starting_equity == 100000.0
        assert state.current_mode == TradingMode.NORMAL
        assert state.drawdown_percentage == 0.0
    
    async def test_drawdown_guardian_normal_to_protection(self):
        """Test mode transition from NORMAL to PROTECTION at 10%."""
        guardian = DrawdownGuardian()
        guardian.initialize(100000.0)
        
        # Simulate 12% drawdown
        await guardian.update(current_equity=88000.0, daily_pnl=-12000.0)
        
        assert guardian.state.current_mode == TradingMode.PROTECTION
        assert len(guardian.transitions) == 1
    
    async def test_drawdown_guardian_protection_to_critical(self):
        """Test mode transition from PROTECTION to CRITICAL at 15%."""
        guardian = DrawdownGuardian()
        guardian.initialize(100000.0)
        
        # First to PROTECTION
        await guardian.update(current_equity=90000.0, daily_pnl=-10000.0)
        
        # Then to CRITICAL
        await guardian.update(current_equity=85000.0, daily_pnl=-15000.0)
        
        assert guardian.state.current_mode == TradingMode.CRITICAL
        assert len(guardian.transitions) == 2


@pytest.mark.asyncio
class TestDebateEngine:
    """Integration tests for Debate Engine."""
    
    async def test_debate_engine_full_flow(self):
        """Test complete debate flow."""
        engine = DebateEngine()
        
        # Mock all external services
        with patch.object(engine.market_scout.alpaca_service, 'get_market_data', new_callable=AsyncMock):
            result = await engine.run_debate(
                symbol="AAPL",
                option_type="call",
                strike=105.0,
                expiration="2024-12-20",
                portfolio_value=100000.0,
                current_equity=100000.0,
                current_positions=0,
                current_drawdown=0.0,
            )
        
        assert result.symbol == "AAPL"
        assert result.completed == True
        assert result.debate_id is not None
        assert len(result.agent_outputs) > 0
    
    async def test_debate_engine_stores_result(self):
        """Test debate results are stored and retrievable."""
        engine = DebateEngine()
        
        with patch.object(engine.market_scout.alpaca_service, 'get_market_data', new_callable=AsyncMock):
            result = await engine.run_debate(
                symbol="AAPL",
                option_type="call",
                strike=105.0,
                expiration="2024-12-20"
            )
        
        retrieved = engine.get_debate(result.debate_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"