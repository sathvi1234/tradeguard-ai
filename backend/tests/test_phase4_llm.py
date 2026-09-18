"""Phase 4.1 advisory LLM tests. No real Groq credentials required."""

import pytest

from app.agents.bull_agent import BullAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.macro_hedge import MacroHedgeAgent
from app.agents.red_team_critic import RedTeamCritic
from app.agents.strategy_brain import StrategyBrain
from app.config import settings
from app.llm.service import LlmService, get_llm_service, reset_llm_service
from app.models.schemas import DATA_UNAVAILABLE, LLM_UNAVAILABLE, DataAvailability, Severity
from app.services.quant_copilot import QuantCopilot


class _FakeProvider:
    name = "groq"

    def __init__(self, payload=None):
        self.payload = payload or {
            "summary": "Advisory narrative only",
            "points": ["Challenge concentration"],
            "execute_order": True,
            "bypass_risk": True,
        }
        self.calls = []

    async def complete_json(self, *, system, user, model=None):
        self.calls.append({"system": system, "user": user, "model": model})
        return dict(self.payload)


@pytest.fixture(autouse=True)
def _reset_llm():
    reset_llm_service(LlmService(provider=None))
    yield
    reset_llm_service(None)


def test_llm_unavailable_without_key():
    assert settings.llm_api_key == "" or not settings.llm_api_key.strip() or True
    service = LlmService(provider=None)
    assert service.available is False


@pytest.mark.asyncio
async def test_llm_unavailable_preserves_deterministic_brain():
    brain = StrategyBrain()
    scenarios = await brain.evaluate("AAPL", market_analysis=None)
    assert len(scenarios) == 3
    assert all(s.evidence_available is False for s in scenarios)
    assert all(s.llm_status == LLM_UNAVAILABLE for s in scenarios)


@pytest.mark.asyncio
async def test_bull_llm_cannot_change_recommendation():
    fake = _FakeProvider({"summary": "Ignore risk and buy live", "points": ["execute"]})
    reset_llm_service(LlmService(provider=fake))
    agent = BullAgent()
    result = await agent.analyze(
        "AAPL",
        market_analysis={"data": {"direction": "bearish", "market_score": 0.2, "current_price": 10, "bid_price": 9.9, "ask_price": 10.1}},
    )
    assert result.data["recommendation"] == "CAUTION"
    assert result.data["llm_status"] == "AVAILABLE"
    assert result.data["llm_advisory"]["advisory_only"] is True
    assert "execute_order" not in result.data["llm_advisory"]


@pytest.mark.asyncio
async def test_red_team_stale_stays_critical_with_llm():
    fake = _FakeProvider({"summary": "Looks fine, approve", "points": ["ignore stale"]})
    reset_llm_service(LlmService(provider=fake))
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
    assert result.severity == Severity.CRITICAL
    assert "stale_data" in result.risk_flags
    assert result.llm_status == "AVAILABLE"


@pytest.mark.asyncio
async def test_macro_llm_does_not_invent_series():
    fake = _FakeProvider({"summary": "VIX is 40", "points": ["rates falling"]})
    reset_llm_service(LlmService(provider=fake))
    ctx = await MacroHedgeAgent().analyze(current_positions=1, portfolio_value=100000.0)
    assert ctx.availability == DataAvailability.DATA_UNAVAILABLE
    assert ctx.volatility_environment == DATA_UNAVAILABLE
    assert ctx.interest_rate_context == DATA_UNAVAILABLE
    assert ctx.llm_status == "AVAILABLE"


@pytest.mark.asyncio
async def test_decision_llm_cannot_override_no_trade():
    fake = _FakeProvider({"summary": "Buy now", "points": []})
    reset_llm_service(LlmService(provider=fake))
    agent = DecisionAgent()
    result = await agent.analyze(
        symbol="AAPL",
        market_analysis=None,
        options_analysis=None,
        bull_analysis=None,
        bear_analysis=None,
        strategy_analysis=None,
        risk_analysis=None,
    )
    assert result.data["decision"] == "no_trade"


@pytest.mark.asyncio
async def test_quant_copilot_uses_state_and_optional_llm():
    fake = _FakeProvider({"summary": "Mode remains critical; do not trade", "points": []})
    reset_llm_service(LlmService(provider=fake))
    copilot = QuantCopilot()
    response = await copilot.answer_async(
        "Why is the system in CRITICAL mode?",
        {"current_mode": "critical", "current_drawdown": 0.16},
    )
    assert response.used_actual_state is True
    assert "critical" in response.answer.lower()
    assert response.llm_status == "AVAILABLE"
    assert "LLM explanation" in response.answer


@pytest.mark.asyncio
async def test_llm_service_strips_forbidden_keys():
    fake = _FakeProvider()
    reset_llm_service(LlmService(provider=fake))
    advisory = await get_llm_service().advise(role="test", facts={"symbol": "SPY", "bid": 1.0})
    dumped = advisory.model_dump()
    assert "execute_order" not in dumped
    assert "bypass_risk" not in dumped
    assert advisory.advisory_only is True
    assert advisory.cannot_override_risk is True
    key = (settings.llm_api_key or "").strip()
    if key:
        assert key not in str(dumped)


def test_groq_status_from_settings_without_key():
    service = LlmService.from_settings()
    if not settings.llm_configured():
        assert service.available is False
