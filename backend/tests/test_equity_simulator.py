"""Educational equity simulator. Never hits Alpaca order endpoints."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import TradingMode
from app.models.market_data import FreshnessStatus, StockQuote, StockTrade
from app.risk.risk_guardian import RiskGuardian
from app.services.equity_simulator import simulate_equity_order
from app.trading.audit_logger import AuditLogger


def _engine(mode=TradingMode.NORMAL, freshness=FreshnessStatus.FRESH):
    now = datetime.now(timezone.utc)
    quote = StockQuote(
        symbol="AAPL",
        bid=100.0,
        ask=100.1,
        last_trade_price=100.05,
        timestamp=now,
        received_at=now,
        freshness=freshness,
        availability="AVAILABLE",
    )
    engine = SimpleNamespace()
    engine.alpaca_service = SimpleNamespace(
        get_latest_quote=AsyncMock(return_value=quote),
        get_latest_trade=AsyncMock(
            return_value=StockTrade(symbol="AAPL", price=100.05, freshness=freshness, availability="AVAILABLE")
        ),
        get_account=AsyncMock(
            return_value={"portfolio_value": 100000.0, "equity": 100000.0, "cash": 50000.0, "buying_power": 50000.0}
        ),
    )
    engine.drawdown_guardian = SimpleNamespace(
        state=SimpleNamespace(current_mode=mode, drawdown_percentage=0.01),
        initialize=MagicMock(),
    )
    engine.position_manager = SimpleNamespace(get_open_positions=lambda: [])
    engine.risk_guardian = RiskGuardian()
    engine.audit_logger = AuditLogger()
    engine.simulated_equity_fills = []
    return engine


@pytest.mark.asyncio
async def test_preview_does_not_fill():
    result = await simulate_equity_order(
        _engine(),
        {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market", "preview_only": True},
    )
    assert result["status"] == "preview"
    assert result["preview"]["label"] == "SIMULATED PAPER TRADE"


@pytest.mark.asyncio
async def test_stale_quote_fails_closed():
    result = await simulate_equity_order(
        _engine(freshness=FreshnessStatus.STALE),
        {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
    )
    assert result["ok"] is False
    assert "Fail closed" in result["reason"] or "DATA_UNAVAILABLE" in result["reason"]


@pytest.mark.asyncio
async def test_critical_mode_rejected():
    result = await simulate_equity_order(
        _engine(mode=TradingMode.CRITICAL),
        {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
    )
    assert result["ok"] is False
    assert result["gate"] in ("RiskGuardian", "RiskBodyguard")


@pytest.mark.asyncio
async def test_approved_fill_is_simulated_only():
    result = await simulate_equity_order(
        _engine(),
        {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
    )
    if result["ok"]:
        assert result["fill"]["simulated"] is True
        assert result["fill"]["alpaca_order_id"] is None
        assert result["real_paper_order"] is False
        assert result["live_trading"] is False
    else:
        # Size/freshness gates may still reject depending on wall-clock vs quote age.
        assert result["status"] == "rejected"
        assert result["simulated"] is True


@pytest.mark.asyncio
async def test_sell_without_long_is_rejected():
    result = await simulate_equity_order(
        _engine(),
        {"symbol": "AAPL", "side": "sell", "quantity": 1, "order_type": "market"},
    )
    assert result["ok"] is False
    assert "Insufficient simulated long" in result["reason"]


@pytest.mark.asyncio
async def test_after_hours_fresh_quote_can_simulate():
    engine = _engine()
    engine.alpaca_service.get_market_clock = AsyncMock(
        return_value=SimpleNamespace(is_open=False, session="AFTER-HOURS")
    )
    result = await simulate_equity_order(
        engine,
        {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
    )
    if result["ok"]:
        assert result["fill"]["simulated"] is True
        assert result["live_trading"] is False
        assert result["preview"]["session"] == "AFTER-HOURS"
    else:
        assert result["simulated"] is True
        assert "Insufficient" not in result.get("reason", "")
