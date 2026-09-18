"""Phase 4.2 Quant Copilot tests. No live orders. No invented data."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.intelligence import router
from app.models.schemas import DATA_UNAVAILABLE, LLM_UNAVAILABLE
from app.services.quant_copilot import QuantCopilot, classify_intent, collect_copilot_state


def _base_state(**overrides):
    state = {
        "account": {
            "cash": 99386.0,
            "equity": 99998.0,
            "portfolio_value": 99998.0,
            "buying_power": 398000.0,
        },
        "positions": [],
        "orders": [],
        "greeks": {"availability": DATA_UNAVAILABLE, "portfolio_delta": None, "portfolio_vega": None, "quality": DATA_UNAVAILABLE},
        "market_intelligence": {"iv": DATA_UNAVAILABLE},
        "last_decision": None,
        "last_rejection_reasons": [],
        "last_red_team": None,
        "last_debate": None,
        "bodyguard": {"action": "HOLD", "advisory_only": True},
        "current_mode": "normal",
        "current_drawdown": 0.01,
        "memory": [],
        "can_execute": False,
    }
    state.update(overrides)
    return state


@pytest.fixture
def copilot():
    return QuantCopilot()


def test_copilot_api_routes_exist():
    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/api/v1/copilot/ask" in paths or any(p.endswith("/copilot/ask") for p in paths)
    assert any(p.endswith("/copilot") for p in paths)


def test_intent_classification():
    assert classify_intent("What is my current portfolio?") == "portfolio"
    assert classify_intent("What positions do I have?") == "positions"
    assert classify_intent("What is my portfolio delta?") == "delta"
    assert classify_intent("Why was this trade proposed?") == "proposed"
    assert classify_intent("Why was this trade rejected?") == "rejected"
    assert classify_intent("What are the main risks?") == "risks"
    assert classify_intent("What happens if volatility increases?") == "volatility"
    assert classify_intent("Why am I in PROTECTION mode?") == "protection"
    assert classify_intent("Why am I in CRITICAL mode?") == "critical"
    assert classify_intent("Explain the latest AI debate.") == "debate"
    assert classify_intent("Explain the Red Team objections.") == "red_team"


def test_portfolio_uses_account(copilot):
    r = copilot.answer("What is my current portfolio?", _base_state())
    assert r.can_execute is False
    assert "99386" in r.answer
    assert "cannot execute" in r.answer.lower()


def test_positions_empty_is_actual(copilot):
    r = copilot.answer("What positions do I have?", _base_state())
    assert "0 open positions" in r.answer
    assert DATA_UNAVAILABLE not in r.answer


def test_delta_unavailable(copilot):
    r = copilot.answer("What is my portfolio delta?", _base_state())
    assert DATA_UNAVAILABLE in r.answer
    assert "portfolio_delta" in r.unavailable


def test_delta_real(copilot):
    r = copilot.answer(
        "What is my portfolio delta?",
        _base_state(greeks={"availability": "AVAILABLE", "portfolio_delta": 0.42, "quality": "REAL"}),
    )
    assert "0.42" in r.answer
    assert "REAL" in r.answer


def test_proposed_and_rejected(copilot):
    missing = copilot.answer("Why was this trade proposed?", _base_state())
    assert "No trade has been proposed" in missing.answer
    proposed = copilot.answer(
        "Why was this trade proposed?",
        _base_state(last_decision={"decision": "buy", "reasoning": "scout bullish", "proposed_size": 100}),
    )
    assert "buy" in proposed.answer
    assert "scout bullish" in proposed.answer
    rejected = copilot.answer(
        "Why was this trade rejected?",
        _base_state(last_rejection_reasons=["size limit"]),
    )
    assert "size limit" in rejected.answer


def test_protection_critical_and_risks(copilot):
    prot = copilot.answer(
        "Why am I in PROTECTION mode?",
        _base_state(current_mode="protection", current_drawdown=0.11),
    )
    assert "protection" in prot.answer.lower()
    crit = copilot.answer(
        "Why am I in CRITICAL mode?",
        _base_state(current_mode="critical", current_drawdown=0.16),
    )
    assert "CRITICAL blocks new trades: True" in crit.answer
    risks = copilot.answer(
        "What are the main risks?",
        _base_state(
            last_red_team={"risk_flags": ["stale_data"], "objections": ["stale quotes"], "severity": "CRITICAL"},
            current_mode="critical",
            current_drawdown=0.16,
        ),
    )
    assert "stale_data" in risks.answer
    assert "Risk Guardian" in risks.answer


def test_volatility_does_not_invent_pnl(copilot):
    r = copilot.answer("What happens if volatility increases?", _base_state())
    assert DATA_UNAVAILABLE in r.answer
    assert "portfolio_vega" in r.unavailable
    assert "not a live forecast" in r.answer.lower() or "not a live" in r.answer.lower()


def test_debate_and_red_team_unavailable(copilot):
    debate = copilot.answer("Explain the latest AI debate.", _base_state())
    assert DATA_UNAVAILABLE in debate.answer
    red = copilot.answer("Explain the Red Team objections.", _base_state())
    assert DATA_UNAVAILABLE in red.answer
    red_ok = copilot.answer(
        "Explain the Red Team objections.",
        _base_state(last_red_team={"severity": "HIGH", "risk_flags": ["missing_information"], "objections": ["No contract"]}),
    )
    assert "No contract" in red_ok.answer
    assert "advisory only" in red_ok.answer.lower()


def test_copilot_never_executes(copilot):
    r = copilot.answer("What is my current portfolio?", _base_state())
    assert r.can_execute is False
    assert not hasattr(copilot, "execute_order")
    assert "execute_order" not in r.answer.lower()


@pytest.mark.asyncio
async def test_collect_state_uses_engine_without_orders():
    engine = MagicMock()
    engine.alpaca_service.get_account = AsyncMock(return_value={"cash": 1, "equity": 2, "portfolio_value": 2, "buying_power": 3})
    engine.position_manager.get_open_positions.return_value = []
    engine.order_tracker.get_all_tracked_orders.return_value = []
    engine.drawdown_guardian.state = None
    engine.last_decision = None
    engine.last_rejection_reasons = []
    engine.last_red_team = None
    engine.last_debate = None
    engine.last_bodyguard = None
    engine.debate_engine.get_all_debates.return_value = []
    engine.trade_memory.list_records.return_value = []
    quote = MagicMock()
    quote.bid = 10
    quote.ask = 10.1
    quote.model_dump.return_value = {"bid": 10, "ask": 10.1}
    engine.alpaca_service.get_latest_quote = AsyncMock(return_value=quote)
    clock = MagicMock()
    clock.is_open = True
    engine.alpaca_service.get_market_clock = AsyncMock(return_value=clock)
    engine.order_executor.execute_order = AsyncMock()

    with patch("app.services.demo_ledger.demo_portfolio", new_callable=AsyncMock, return_value=None):
        state = await collect_copilot_state(engine)
    assert state["can_execute"] is False
    assert state["account"]["cash"] == 1
    assert state["positions"] == []
    copilot = QuantCopilot()
    r = await copilot.answer_async("What is my current portfolio?", state)
    assert r.can_execute is False
    assert r.llm_status == LLM_UNAVAILABLE
    engine.order_executor.execute_order.assert_not_called()
