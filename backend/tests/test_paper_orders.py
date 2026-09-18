"""User-initiated Alpaca PAPER equity orders. Live trading remains blocked."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.alpaca.client import AlpacaClient
from app.alpaca.exceptions import AlpacaLiveTradingBlocked
from app.alpaca.iex_stream import _public_payload
from app.config import LIVE_API_URL, PAPER_API_URL, settings
from app.models.enums import TradingMode
from app.models.market_data import FreshnessStatus, StockQuote, StockTrade
from app.risk.risk_guardian import RiskGuardian
from app.services.paper_orders import list_paper_orders, map_alpaca_order, submit_paper_equity_order
from app.trading.audit_logger import AuditLogger


def _engine(mode=TradingMode.NORMAL, freshness=FreshnessStatus.FRESH, buying_power=50000.0, positions=None):
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
    client = SimpleNamespace(
        submit_paper_order=AsyncMock(
            return_value={
                "id": "ord-paper-1",
                "client_order_id": "tg-test",
                "symbol": "AAPL",
                "qty": "1",
                "filled_qty": "1",
                "filled_avg_price": "100.07",
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
                "status": "filled",
                "submitted_at": now.isoformat(),
                "filled_at": now.isoformat(),
            }
        ),
        get_orders=AsyncMock(return_value=[]),
        get_order=AsyncMock(return_value={}),
        get_positions=AsyncMock(return_value=positions or []),
    )
    engine = SimpleNamespace()
    engine.alpaca_service = SimpleNamespace(
        client=client,
        get_latest_quote=AsyncMock(return_value=quote),
        get_latest_trade=AsyncMock(
            return_value=StockTrade(symbol="AAPL", price=100.05, freshness=freshness, availability="AVAILABLE")
        ),
        get_account=AsyncMock(
            return_value={"portfolio_value": 100000.0, "equity": 100000.0, "cash": 50000.0, "buying_power": buying_power}
        ),
        get_market_clock=AsyncMock(
            return_value=SimpleNamespace(session="REGULAR", is_open=True, timestamp=now, availability="AVAILABLE")
        ),
        get_company_name=AsyncMock(return_value="Apple Inc."),
    )
    engine.drawdown_guardian = SimpleNamespace(
        state=SimpleNamespace(current_mode=mode, drawdown_percentage=0.01),
        initialize=MagicMock(),
    )
    engine.position_manager = SimpleNamespace(get_open_positions=lambda: [])
    engine.risk_guardian = RiskGuardian()
    engine.audit_logger = AuditLogger()
    engine.order_tracker = SimpleNamespace(track_order=MagicMock(), update_order_status=MagicMock())
    return engine


@pytest.mark.asyncio
async def test_submit_paper_order_never_uses_live_url():
    client = AlpacaClient()
    client.base_url = LIVE_API_URL
    with pytest.raises(AlpacaLiveTradingBlocked):
        await client.submit_paper_order(
            {"symbol": "AAPL", "qty": "1", "side": "buy", "type": "market", "time_in_force": "day"}
        )


def test_public_stream_payload_strips_secrets():
    payload = _public_payload(
        {
            "type": "quote",
            "symbol": "AAPL",
            "price": 100.0,
            "key": "SECRET",
            "secret": "SECRET",
            "alpaca_api_key": "SECRET",
            "alpaca_secret_key": "SECRET",
        }
    )
    blob = str(payload).lower()
    assert "secret" not in blob
    assert "alpaca_api_key" not in blob
    assert payload["price"] == 100.0
    assert payload["symbol"] == "AAPL"


def test_map_order_uses_filled_avg_price():
    mapped = map_alpaca_order(
        {
            "id": "ord-1",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "1",
            "filled_qty": "1",
            "filled_avg_price": "337.09",
            "status": "filled",
            "type": "market",
            "time_in_force": "day",
        }
    )
    assert mapped["alpaca_order_id"] == "ord-1"
    assert mapped["filled_avg_price"] == 337.09
    assert mapped["price"] == 337.09
    assert mapped["trade_type"] == "PAPER"
    assert mapped["live_trading"] is False
    assert mapped["destination"] == PAPER_API_URL


def test_orders_dedupe_by_alpaca_id():
    mapped = [
        map_alpaca_order({"id": "same", "symbol": "AAPL", "side": "buy", "qty": "1", "status": "filled"}),
        map_alpaca_order({"id": "same", "symbol": "AAPL", "side": "buy", "qty": "1", "status": "filled"}),
    ]
    seen = set()
    unique = []
    for row in mapped:
        key = row["alpaca_order_id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    assert len(unique) == 1


@pytest.mark.asyncio
async def test_dry_run_still_submits_paper_order():
    assert settings.dry_run is True
    engine = _engine()
    hub = SimpleNamespace(quotes={}, state="LIVE")
    with patch("app.alpaca.iex_stream.get_iex_hub", return_value=hub):
        result = await submit_paper_equity_order(
            engine,
            {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
    assert result["ok"] is True
    assert result["submitted"] is True
    assert result["live_trading"] is False
    assert result["destination"] == PAPER_API_URL
    engine.alpaca_service.client.submit_paper_order.assert_awaited()
    payload = engine.alpaca_service.client.submit_paper_order.await_args.args[0]
    assert payload["symbol"] == "AAPL"
    assert payload["qty"] == "1"
    assert payload["side"] == "buy"
    assert payload["type"] == "market"
    assert payload["time_in_force"] == "day"


@pytest.mark.asyncio
async def test_risk_guardian_reject_does_not_submit():
    engine = _engine(mode=TradingMode.CRITICAL)
    hub = SimpleNamespace(quotes={}, state="LIVE")
    with patch("app.alpaca.iex_stream.get_iex_hub", return_value=hub):
        result = await submit_paper_equity_order(
            engine,
            {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
    assert result["ok"] is False
    assert result["submitted"] is False
    engine.alpaca_service.client.submit_paper_order.assert_not_awaited()
    assert "CRITICAL" in result["reason"] or "DRAWDOWN" in result["reason"]


@pytest.mark.asyncio
async def test_sell_without_position_is_blocked():
    engine = _engine()
    hub = SimpleNamespace(quotes={}, state="LIVE")
    with patch("app.alpaca.iex_stream.get_iex_hub", return_value=hub):
        result = await submit_paper_equity_order(
            engine,
            {"symbol": "AAPL", "side": "sell", "quantity": 1, "order_type": "market"},
        )
    assert result["ok"] is False
    assert result["submitted"] is False
    engine.alpaca_service.client.submit_paper_order.assert_not_awaited()
    assert "POSITION" in result["reason"] or "Short" in result["reason"]


@pytest.mark.asyncio
async def test_insufficient_buying_power_is_blocked():
    engine = _engine(buying_power=10.0)
    hub = SimpleNamespace(quotes={}, state="LIVE")
    with patch("app.alpaca.iex_stream.get_iex_hub", return_value=hub):
        result = await submit_paper_equity_order(
            engine,
            {"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
        )
    assert result["ok"] is False
    engine.alpaca_service.client.submit_paper_order.assert_not_awaited()
    assert "BUYING POWER" in result["reason"]


@pytest.mark.asyncio
async def test_list_paper_orders_dedupes():
    engine = _engine()
    engine.alpaca_service.client.get_orders = AsyncMock(
        return_value=[
            {"id": "dup", "symbol": "AAPL", "side": "buy", "qty": "1", "status": "filled", "filled_avg_price": "10"},
            {"id": "dup", "symbol": "AAPL", "side": "buy", "qty": "1", "status": "filled", "filled_avg_price": "10"},
        ]
    )
    rows = await list_paper_orders(engine)
    assert len(rows) == 1
    assert rows[0]["alpaca_order_id"] == "dup"
