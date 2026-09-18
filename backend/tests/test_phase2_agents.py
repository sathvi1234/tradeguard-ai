"""Phase 2 Trade AI agents, services, and Master Orchestrator tests."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.macro_hedge import MacroHedgeAgent
from app.agents.red_team_critic import RedTeamCritic
from app.agents.strategy_brain import StrategyBrain
from app.autonomous.debate_engine import DebateResult
from app.models.enums import TradingMode
from app.models.schemas import (
    DATA_UNAVAILABLE,
    BodyguardAction,
    DataAvailability,
    ScenarioType,
    Severity,
    TradeOutcome,
)
from app.risk.risk_bodyguard import RiskBodyguard
from app.services.market_intelligence import MarketIntelligenceService
from app.services.portfolio_greeks import PortfolioGreeksService
from app.services.position_restructuring import PositionRestructuringService
from app.services.post_trade_memory import PostTradeMemory
from app.services.quant_copilot import QuantCopilot
from app.services.strategy_library import get_strategy_library
from app.trading.autonomous_engine import AutonomousTradingEngine
from app.trading.order_executor import OrderExecutor


from app.models.market_data import FreshnessStatus, MarketClock, SelectedContract, StockQuote, StockTrade


def _account():
    return {
        "paper_trading_allowed": True,
        "trading_blocked": False,
        "portfolio_value": 100000.0,
        "cash": 80000.0,
        "buying_power": 90000.0,
        "equity": 100000.0,
        "status": "ACTIVE",
    }


def _selected():
    return SelectedContract(
        underlying="SPY",
        occ_symbol="SPY260320C00500000",
        option_type="call",
        strike=500.0,
        expiration="2026-03-20",
        bid=2.40,
        ask=2.50,
        last_price=2.45,
    )


def _fresh_quote(symbol="SPY"):
    from datetime import timezone
    now = datetime.now(timezone.utc)
    return StockQuote(
        symbol=symbol,
        bid=500.0,
        ask=500.1,
        timestamp=now,
        received_at=now,
        freshness=FreshnessStatus.FRESH,
        availability="AVAILABLE",
    )


def _open_clock():
    return MarketClock(is_open=True, availability="AVAILABLE")


async def _stub_market(engine):
    engine.alpaca_service.get_market_clock = AsyncMock(return_value=_open_clock())
    engine.alpaca_service.get_latest_quote = AsyncMock(return_value=_fresh_quote())
    engine.alpaca_service.get_latest_trade = AsyncMock(
        return_value=StockTrade(symbol="SPY", price=500.05, freshness=FreshnessStatus.FRESH, availability="AVAILABLE")
    )
    engine.alpaca_service.get_bars = AsyncMock(return_value=[])
    engine.alpaca_service.get_option_snapshot = AsyncMock(return_value=None)
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "SPY",
            "price": 500.05,
            "last_trade_price": 500.05,
            "bid": 500.0,
            "ask": 500.1,
            "session": "REGULAR",
            "freshness": "FRESH",
            "volume": 1000,
            "previous_close": 499.0,
            "day_change": 1.05,
            "day_change_pct": 0.002,
        }
    )
    engine.orchestrator.contract_selector.select = AsyncMock(return_value=_selected())


@pytest.mark.asyncio
async def test_strategy_brain_three_scenarios():
    brain = StrategyBrain()
    scenarios = await brain.evaluate("AAPL", market_analysis=None)
    kinds = {s.scenario for s in scenarios}
    assert kinds == {ScenarioType.BULL, ScenarioType.FLAT, ScenarioType.BEAR}
    assert all(s.evidence_available is False for s in scenarios)
    assert all(s.confidence <= 0.3 for s in scenarios)


@pytest.mark.asyncio
async def test_red_team_flags_missing_and_stale():
    critic = RedTeamCritic()
    result = await critic.critique(
        symbol="AAPL",
        decision={"decision": "buy", "proposed_size": 500},
        confidence=0.95,
        missing_data=["quotes"],
        data_stale=True,
        contract=None,
    )
    assert result.advisory_only is True
    assert "stale_data" in result.risk_flags
    assert "missing_information" in result.risk_flags
    assert result.severity == Severity.CRITICAL
    assert result.approved_for_review is False


@pytest.mark.asyncio
async def test_macro_data_unavailable():
    agent = MacroHedgeAgent()
    ctx = await agent.analyze(current_positions=1, portfolio_value=100000.0)
    assert ctx.availability == DataAvailability.DATA_UNAVAILABLE
    assert ctx.volatility_environment == DATA_UNAVAILABLE
    assert ctx.interest_rate_context == DATA_UNAVAILABLE
    assert ctx.notes == DATA_UNAVAILABLE


def test_risk_bodyguard_critical_freezes_new_trades():
    assessment = RiskBodyguard().assess(
        [],
        trading_mode=TradingMode.CRITICAL,
        drawdown=0.16,
    )
    assert assessment.freeze_new_trades is True
    assert assessment.action == BodyguardAction.FREEZE_NEW_TRADES
    assert assessment.advisory_only is True


def test_post_trade_memory_persistence(tmp_path):
    memory = PostTradeMemory(db_path=tmp_path / "mem.sqlite")
    from app.models.schemas import TradeMemoryRecord

    record = TradeMemoryRecord(
        timestamp=datetime.utcnow(),
        symbol="AAPL",
        decision="no_trade",
        outcome=TradeOutcome.DRY_RUN_SIMULATED,
        dry_run=True,
        cycle_id="c1",
        lessons=["dry run is not a live fill"],
    )
    memory.record(record)
    rows = memory.list_records(symbol="AAPL")
    assert len(rows) == 1
    assert rows[0].dry_run is True
    assert rows[0].outcome == TradeOutcome.DRY_RUN_SIMULATED


def test_strategy_library_definitions():
    lib = get_strategy_library()
    keys = {s.key for s in lib}
    assert len(lib) == 8
    assert "theta_iron_condor" in keys
    assert "zero_dte_mean_reversion" in keys
    assert all(s.auto_trade is False for s in lib)


def test_greeks_unavailable_without_real_feed():
    snap = PortfolioGreeksService().snapshot(positions=[])
    assert snap.availability == DataAvailability.EMPTY
    assert snap.reason_code == "NO_OPTION_POSITIONS"
    assert snap.portfolio_delta is None


def test_market_intelligence_unavailable_by_default():
    snap = MarketIntelligenceService().snapshot("AAPL")
    assert snap.availability == DataAvailability.DATA_UNAVAILABLE
    assert snap.iv == DATA_UNAVAILABLE
    assert snap.options_flow == DATA_UNAVAILABLE


def test_quant_copilot_uses_actual_state():
    copilot = QuantCopilot()
    response = copilot.answer(
        "Why is the system in CRITICAL mode?",
        {"current_mode": "critical", "current_drawdown": 0.16},
    )
    assert response.used_actual_state is True
    assert "critical" in response.answer.lower()
    assert response.llm_provider == DATA_UNAVAILABLE or response.llm_status == "LLM_UNAVAILABLE"


def test_restructuring_is_recommendation_only():
    rec = PositionRestructuringService().recommend(
        None,
        trading_mode=TradingMode.CRITICAL,
        thesis_invalidated=True,
    )
    assert rec.recommendation_only is True
    assert rec.requires_risk_guardian is True
    assert rec.action.value in {"CLOSE", "REASSESS"}


def test_order_executor_live_path_is_blocked():
    executor = OrderExecutor(dry_run=False)
    assert executor.dry_run is False


@pytest.mark.asyncio
async def test_order_executor_rejects_non_dry_run():
    executor = OrderExecutor(dry_run=True)
    from app.trading.order_builder import OrderBuilder

    order = OrderBuilder().build_buy_call("AAPL", 105, "2026-12-20", 1, 2.5, 2.55)
    executed = await executor.execute_order(order, "d1", dry_run=False)
    assert executed.status == "rejected"
    assert "Live trading" in (executed.error_message or "")


@pytest.mark.asyncio
async def test_master_orchestrator_sequencing_and_missing_data():
    engine = AutonomousTradingEngine(dry_run=True)
    await _stub_market(engine)
    debate = DebateResult("debate-missing")
    debate.completed = True
    debate.final_decision = {"decision": "no_trade", "reasoning": "scout failed"}
    debate.risk_guardian_result = {"decision": "hold", "display_decision": "HOLD"}
    with patch.object(engine.alpaca_service, "get_account", new_callable=AsyncMock) as mock_account:
        mock_account.return_value = _account()
        with patch.object(
            engine.debate_engine.market_scout,
            "analyze",
            new_callable=AsyncMock,
            side_effect=Exception("no quotes"),
        ):
            with patch.object(engine.debate_engine, "run_debate", new_callable=AsyncMock, return_value=debate):
                result = await engine.run_cycle()
    assert result["order"] is None
    assert "market_scout" in result.get("stages", [])
    assert result["status"] in ("no_trade", "halted_after_risk_guardian", "risk_rejected")


@pytest.mark.asyncio
async def test_no_execution_when_risk_guardian_rejects():
    engine = AutonomousTradingEngine(dry_run=True)
    await _stub_market(engine)
    debate = DebateResult("debate-1")
    debate.completed = True
    debate.final_decision = {
        "decision": "buy",
        "proposed_size": 500,
        "confidence": 0.8,
        "selected_contracts": {
            "symbol": "SPY",
            "strike": 500,
            "expiration": "2026-03-20",
            "entry_price": 2.5,
            "bid": 2.4,
            "ask": 2.55,
        },
    }
    debate.risk_guardian_result = {"decision": "rejected", "rejection_reasons": ["limit"]}

    from app.agents.base import AgentAnalysis, AgentType

    scout = AgentAnalysis(
        agent_type=AgentType.MARKET_SCOUT,
        symbol="SPY",
        timestamp=datetime.utcnow(),
        confidence=0.7,
        reasoning="ok",
        data={"direction": "bullish"},
        errors=None,
    )
    with patch.object(engine.alpaca_service, "get_account", new_callable=AsyncMock, return_value=_account()):
        with patch.object(engine.debate_engine.market_scout, "analyze", new_callable=AsyncMock, return_value=scout):
            with patch.object(engine.debate_engine, "run_debate", new_callable=AsyncMock, return_value=debate):
                with patch.object(engine.order_executor, "execute_order", new_callable=AsyncMock) as exec_mock:
                    result = await engine.run_cycle()
                    exec_mock.assert_not_called()
    assert result["status"] == "risk_rejected"
    assert result["order"] is None


@pytest.mark.asyncio
async def test_no_execution_in_critical_mode():
    engine = AutonomousTradingEngine(dry_run=True)
    account_ok = _account()
    account_dd = dict(_account())
    account_dd["portfolio_value"] = 84000.0
    account_dd["equity"] = 84000.0
    with patch.object(engine.alpaca_service, "get_account", new_callable=AsyncMock) as mock_account:
        mock_account.return_value = account_ok
        await engine.initialize()
        mock_account.return_value = account_dd
        with patch(
            "app.services.demo_ledger.demo_portfolio",
            new_callable=AsyncMock,
            return_value={
                "equity": 84000.0,
                "cash": 84000.0,
                "buying_power": 84000.0,
                "positions_count": 0,
                "position_exposure": 0,
                "realized_pnl": 0,
                "unrealized_pnl": 0,
                "positions": [],
            },
        ):
            with patch.object(engine.order_executor, "execute_order", new_callable=AsyncMock) as exec_mock:
                result = await engine.run_cycle()
                exec_mock.assert_not_called()
    assert result["status"] == "critical_mode"
    assert result["halt_reason"] == "CRITICAL_MODE"


@pytest.mark.asyncio
async def test_orchestrator_shares_risk_instances():
    engine = AutonomousTradingEngine(dry_run=True)
    assert engine.debate_engine.risk_guardian is engine.risk_guardian
    assert engine.debate_engine.drawdown_guardian is engine.drawdown_guardian
    assert engine.orchestrator.engine is engine


@pytest.mark.asyncio
async def test_fail_closed_stale_data_no_trade():
    engine = AutonomousTradingEngine(dry_run=True)
    await _stub_market(engine)
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "SPY",
            "price": 500.05,
            "bid": 500.0,
            "ask": 500.1,
            "session": "REGULAR",
            "freshness": "STALE",
        }
    )
    debate = DebateResult("stale-debate")
    debate.completed = True
    debate.final_decision = {"decision": "no_trade", "reasoning": "stale quotes are analysis-only"}
    debate.risk_guardian_result = {"decision": "hold", "display_decision": "HOLD"}
    from app.agents.base import AgentAnalysis, AgentType

    scout = AgentAnalysis(
        agent_type=AgentType.MARKET_SCOUT,
        symbol="SPY",
        timestamp=datetime.utcnow(),
        confidence=0.4,
        reasoning="stale but priced",
        data={"current_price": 500.05, "freshness": "STALE", "valid": True},
    )
    with patch.object(engine.alpaca_service, "get_account", new_callable=AsyncMock, return_value=_account()):
        with patch.object(engine.debate_engine.market_scout, "analyze", new_callable=AsyncMock, return_value=scout):
            with patch.object(engine.debate_engine, "run_debate", new_callable=AsyncMock, return_value=debate):
                with patch.object(engine.order_executor, "execute_order", new_callable=AsyncMock) as exec_mock:
                    result = await engine.run_cycle()
                    exec_mock.assert_not_called()
    assert result["status"] == "no_trade"
    assert result["order"] is None
