"""Restricted LLM reviewer cannot override Risk Guardian."""

from datetime import datetime, timezone

import pytest

from app.llm.exceptions import LlmUnavailable
from app.llm.models import LLMReviewAction
from app.llm.reviewer import MAX_REDUCTION_PCT, RestrictedLLMReviewer, sanitize_for_llm
from app.llm.service import LlmService, reset_llm_service
from app.models.enums import TradingMode
from app.risk.review_pipeline import run_review_pipeline
from app.risk.risk_guardian import RiskGuardian
from app.trading.audit_logger import AuditEventType, AuditLogger


class _FakeProvider:
    name = "groq"

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def complete_json(self, *, system, user, model=None):
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.payload, Exception):
            raise self.payload
        return dict(self.payload)


def _kwargs(**overrides):
    base = {
        "portfolio_value": 100000.0,
        "current_equity": 100000.0,
        "current_drawdown": 0.0,
        "current_positions": 0,
        "max_loss": 200.0,
        "potential_reward": 400.0,
        "ai_confidence": 0.9,
        "contract_validity": {"is_liquid": True, "open_interest": 500},
        "market_data_timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
        "trading_mode": TradingMode.NORMAL,
        "skip_quote_age": True,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_llm():
    reset_llm_service(LlmService(provider=None))
    yield
    reset_llm_service(None)


def test_sanitize_strips_secrets():
    clean = sanitize_for_llm(
        {
            "alpaca_api_key": "secret-key",
            "database_url": "postgresql://user:pass@localhost/db",
            "symbol": "AAPL",
            "nested": {"password": "x", "size": 10},
        }
    )
    blob = str(clean)
    assert "secret-key" not in blob
    assert "postgresql" not in blob.lower()
    assert "password" not in blob
    assert clean["symbol"] == "AAPL"
    assert clean["nested"]["size"] == 10


@pytest.mark.asyncio
async def test_llm_cannot_approve_blocked_trade():
    fake = _FakeProvider({"action": "APPROVE", "reason": "looks good", "suggested_reduction_pct": 0, "confidence": 1})
    reset_llm_service(LlmService(provider=fake))
    audit = AuditLogger()
    pipeline = await run_review_pipeline(
        guardian=RiskGuardian(),
        symbol="AAPL",
        proposed_size=500,
        rg_kwargs=_kwargs(current_drawdown=0.20),
        audit=audit,
        quantity=5,
    )
    assert pipeline["first_risk_guardian"]["decision"] == "rejected"
    assert pipeline["llm_review"]["status"] == "SKIPPED"
    assert pipeline["allowed_to_execute"] is False
    assert pipeline["final_risk_guardian"]["decision"] == "rejected"
    assert fake.calls == []
    types = [e.event_type for e in audit.events]
    assert AuditEventType.TRADE_PROPOSAL in types
    assert AuditEventType.FINAL_RISK_GUARDIAN in types


@pytest.mark.asyncio
async def test_llm_increase_ignored_and_cannot_execute():
    fake = _FakeProvider(
        {
            "action": "INCREASE",
            "reason": "size up",
            "suggested_reduction_pct": -0.5,
            "confidence": 0.9,
            "execute_order": True,
        }
    )
    reset_llm_service(LlmService(provider=fake))
    pipeline = await run_review_pipeline(
        guardian=RiskGuardian(),
        symbol="MSFT",
        proposed_size=400,
        rg_kwargs=_kwargs(),
        quantity=4,
    )
    assert pipeline["llm_review"]["action"] == LLMReviewAction.NO_CHANGE.value
    assert pipeline["llm_review"]["fail_safe"] is True
    assert pipeline["applied_size"] == 400
    assert pipeline["llm_review"]["can_execute"] is False
    assert pipeline["llm_review"]["can_increase_size"] is False
    assert pipeline["risk_guardian_is_final_authority"] is True


@pytest.mark.asyncio
async def test_llm_shrink_capped_then_final_rg():
    fake = _FakeProvider(
        {
            "action": "SHRINK",
            "reason": "cut risk",
            "suggested_reduction_pct": 0.9,
            "confidence": 0.7,
            "risk_flags": ["crowded"],
        }
    )
    reset_llm_service(LlmService(provider=fake))
    pipeline = await run_review_pipeline(
        guardian=RiskGuardian(),
        symbol="NVDA",
        proposed_size=800,
        rg_kwargs=_kwargs(),
        quantity=8,
    )
    assert pipeline["llm_review"]["action"] == "SHRINK"
    assert pipeline["llm_review"]["suggested_reduction_pct"] == MAX_REDUCTION_PCT
    assert pipeline["applied_size"] == pytest.approx(800 * (1 - MAX_REDUCTION_PCT))
    assert pipeline["applied_size"] < pipeline["original_size"]
    assert pipeline["final_risk_guardian"]["decision"] in {"approved", "rejected"}
    assert pipeline["llm_is_final_authority"] is False


@pytest.mark.asyncio
async def test_llm_veto_enforced_by_risk_guardian():
    fake = _FakeProvider({"action": "VETO", "reason": "event risk", "suggested_reduction_pct": 0, "confidence": 0.8})
    reset_llm_service(LlmService(provider=fake))
    pipeline = await run_review_pipeline(
        guardian=RiskGuardian(),
        symbol="TSLA",
        proposed_size=300,
        rg_kwargs=_kwargs(),
        quantity=3,
    )
    assert pipeline["first_risk_guardian"]["decision"] == "approved"
    assert pipeline["llm_review"]["action"] == "VETO"
    assert pipeline["final_risk_guardian"]["decision"] == "rejected"
    assert pipeline["allowed_to_execute"] is False
    assert any("VETO" in r or "veto" in r.lower() for r in pipeline["final_risk_guardian"]["rejection_reasons"])


@pytest.mark.asyncio
async def test_unavailable_llm_fail_safe_does_not_raise_size():
    pipeline = await run_review_pipeline(
        guardian=RiskGuardian(),
        symbol="AAPL",
        proposed_size=250,
        rg_kwargs=_kwargs(),
        quantity=2,
    )
    assert pipeline["llm_review"]["fail_safe"] is True
    assert pipeline["llm_review"]["action"] == "NO_CHANGE"
    assert pipeline["applied_size"] == 250


@pytest.mark.asyncio
async def test_stale_and_market_closed_and_critical_not_overridable():
    fake = _FakeProvider({"action": "NO_CHANGE", "reason": "approve anyway", "confidence": 1})
    reset_llm_service(LlmService(provider=fake))
    guardian = RiskGuardian()
    stale = await run_review_pipeline(
        guardian=guardian,
        symbol="AAPL",
        proposed_size=200,
        rg_kwargs=_kwargs(skip_quote_age=False, integrity_state="DATA_STALE"),
    )
    assert stale["allowed_to_execute"] is False
    closed = await run_review_pipeline(
        guardian=guardian,
        symbol="AAPL",
        proposed_size=200,
        rg_kwargs=_kwargs(market_closed=True),
    )
    assert closed["allowed_to_execute"] is False
    assert closed["llm_review"]["status"] == "SKIPPED"
    critical = await run_review_pipeline(
        guardian=guardian,
        symbol="AAPL",
        proposed_size=200,
        rg_kwargs=_kwargs(trading_mode=TradingMode.CRITICAL),
    )
    assert critical["allowed_to_execute"] is False
    assert fake.calls == []


@pytest.mark.asyncio
async def test_invalid_and_timeout_fail_safe():
    bad = _FakeProvider({"action": "MAYBE", "reason": "???", "confidence": "high"})
    reset_llm_service(LlmService(provider=bad))
    invalid = await RestrictedLLMReviewer().review(
        proposal={"symbol": "AAPL", "proposed_size": 100},
        first_risk={"decision": "approved"},
    )
    assert invalid.fail_safe is True
    assert invalid.action == LLMReviewAction.NO_CHANGE.value
    timed = _FakeProvider(LlmUnavailable("timeout"))
    reset_llm_service(LlmService(provider=timed))
    timeout = await RestrictedLLMReviewer().review(
        proposal={"symbol": "AAPL", "proposed_size": 100},
        first_risk={"decision": "approved"},
    )
    assert timeout.fail_safe is True
    assert timeout.action == LLMReviewAction.NO_CHANGE.value


def test_reviewer_has_no_alpaca_order_access():
    import ast
    import inspect
    from app.llm import reviewer as reviewer_mod

    tree = ast.parse(inspect.getsource(reviewer_mod))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    joined = " ".join(imported).lower()
    assert "alpaca" not in joined
    assert "order_executor" not in joined
    source = inspect.getsource(RestrictedLLMReviewer.review)
    assert "post_order" not in source
    assert "execute_order" not in source

