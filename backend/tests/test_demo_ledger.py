"""Demo User virtual ledger — never submits Alpaca orders."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import TradingMode
from app.risk.risk_guardian import RiskGuardianDecision
from app.services.demo_ledger import DemoLedger, STARTING_CASH, submit_demo_equity_order


def test_demo_ledger_starts_at_100k(tmp_path: Path):
    ledger = DemoLedger(tmp_path / "demo.sqlite")
    account = ledger.account_row()
    assert account["cash"] == STARTING_CASH
    assert ledger.list_raw_positions() == []
    snap = ledger.portfolio_snapshot({})
    assert snap["exposure"] == 0
    assert snap["concentration"] == 0
    assert snap["equity"] == STARTING_CASH


def test_demo_buy_sell_persists(tmp_path: Path):
    ledger = DemoLedger(tmp_path / "demo.sqlite")
    buy = {
        "trade_id": "demo-buy-1",
        "symbol": "NVDA",
        "side": "buy",
        "quantity": 1,
        "price": 219.4,
        "company": "NVIDIA",
    }
    ledger.apply_fill(buy)
    pos = ledger.list_raw_positions()
    assert pos[0]["symbol"] == "NVDA"
    assert pos[0]["quantity"] == 1
    assert ledger.account_row()["cash"] == pytest.approx(STARTING_CASH - 219.4)
    marked = ledger.marked_positions({"NVDA": {"price": 220.0}})
    assert marked[0]["market_value"] == 220.0
    assert marked[0]["unrealized_pnl"] == pytest.approx(0.6)
    ledger.apply_fill(
        {
            "trade_id": "demo-sell-1",
            "symbol": "NVDA",
            "side": "sell",
            "quantity": 1,
            "price": 220.0,
        }
    )
    assert ledger.list_raw_positions() == []
    assert ledger.account_row()["realized_pnl"] == pytest.approx(0.6)
    trades = ledger.list_trades()
    assert {row["trade_id"] for row in trades} == {"demo-sell-1", "demo-buy-1"}


@pytest.mark.asyncio
async def test_demo_order_never_posts_to_alpaca(tmp_path: Path, monkeypatch):
    from app.services import demo_ledger as mod

    ledger = DemoLedger(tmp_path / "demo.sqlite")
    monkeypatch.setattr(mod, "_ledger", ledger)
    engine = MagicMock()
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "NVDA",
            "price": 219.4,
            "last_trade_price": 219.4,
            "session": "REGULAR",
            "freshness": "FRESH",
            "company": "NVIDIA",
            "feed": "iex",
        }
    )
    engine.drawdown_guardian.state = MagicMock(current_mode=TradingMode.NORMAL, drawdown_percentage=0.0)
    engine.drawdown_guardian.initialize = MagicMock()
    rg = MagicMock()
    rg.decision = RiskGuardianDecision.APPROVED
    rg.rejection_reasons = []
    rg.to_dict.return_value = {"decision": "approved", "display_decision": "ALLOW"}
    engine.risk_guardian.evaluate_trade = AsyncMock(return_value=rg)
    engine.audit_logger.log_event = MagicMock()
    engine.alpaca_service.client = MagicMock()
    result = await submit_demo_equity_order(engine, {"symbol": "NVDA", "side": "buy", "quantity": 1})
    assert result["ok"] is True
    assert result["alpaca_order_submitted"] is False
    assert result["trade_type"] == "DEMO_SIMULATED"
    assert result["fill"]["status"] == "FILLED"
    engine.alpaca_service.client.post_order.assert_not_called()
    assert result["alpaca_order_submitted"] is False
    assert result["destination"] is None


@pytest.mark.asyncio
async def test_demo_after_hours_requires_fresh_quote(tmp_path: Path, monkeypatch):
    from app.services import demo_ledger as mod

    ledger = DemoLedger(tmp_path / "demo.sqlite")
    monkeypatch.setattr(mod, "_ledger", ledger)
    engine = MagicMock()
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "NVDA",
            "price": 219.4,
            "session": "AFTER-HOURS",
            "freshness": "STALE",
            "company": "NVIDIA",
        }
    )
    engine.drawdown_guardian.state = MagicMock(current_mode=TradingMode.NORMAL, drawdown_percentage=0.0)
    result = await submit_demo_equity_order(engine, {"symbol": "NVDA", "side": "buy", "quantity": 1})
    assert result["ok"] is False
    assert "Fresh market data required for simulation" in result["reason"]
