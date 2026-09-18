"""Historical backtest engine tests. No Alpaca orders. No live trading."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.session import ensure_schema, get_engine, sqlite_url
from app.services.backtest_engine import (
    LookAheadError,
    compute_metrics,
    generate_signal,
    normalize_bars,
    run_backtest,
    visible_history,
)
from app.services import backtest_store


def _ts(day: int) -> datetime:
    return datetime(2024, 1, 2, tzinfo=timezone.utc) + timedelta(days=day)


def _bars(closes: List[float], opens: Optional[List[float]] = None):
    out = []
    for i, close in enumerate(closes):
        open_px = opens[i] if opens else (closes[i - 1] if i else close)
        out.append(
            {
                "timestamp": _ts(i),
                "open": open_px,
                "high": max(open_px, close),
                "low": min(open_px, close),
                "close": close,
                "volume": 1_000,
            }
        )
    return out


def test_chronological_ordering_sorts_and_walks_forward():
    raw = _bars([10, 11, 12, 13, 14, 15, 16, 17])
    shuffled = list(reversed(raw))
    result = run_backtest(
        bars=shuffled,
        strategy="buy_and_hold",
        symbol="AAPL",
        initial_capital=10_000,
        position_size=0.3,
        commission_per_trade=0,
        slippage_bps=0,
    )
    stamps = [point["timestamp"] for point in result["equity_curve"]]
    assert stamps == sorted(stamps)
    parsed = normalize_bars(shuffled)
    for i, bar in enumerate(parsed):
        visible = visible_history(parsed, i)
        assert all(item.timestamp < bar.timestamp for item in visible)


def test_look_ahead_bias_spike_close_does_not_fill_same_bar():
    flat = [10.0] * 40
    opens = [10.0] * 40
    opens[-1] = 10.0
    flat[-1] = 80.0
    raw = _bars(flat, opens)
    spike = raw[-1]["timestamp"].isoformat()
    with pytest.raises(LookAheadError):
        bars = normalize_bars(raw)
        generate_signal("sma_crossover", bars, bars[-1])
    result = run_backtest(
        bars=raw,
        strategy="sma_crossover",
        symbol="AAPL",
        initial_capital=10_000,
        position_size=0.3,
        commission_per_trade=0,
        slippage_bps=0,
    )
    same_bar_buys = [
        fill
        for fill in result["fills"]
        if fill["side"] == "buy" and fill["timestamp"] == spike
    ]
    assert same_bar_buys == []
    assert result["look_ahead_bias"] is False
    assert result["future_data_leakage"] is False
    assert result["live_returns"] is False


def test_cash_accounting():
    raw = _bars([10.0] * 8)
    result = run_backtest(
        bars=raw,
        strategy="buy_and_hold",
        symbol="MSFT",
        initial_capital=1_000,
        position_size=0.3,
        commission_per_trade=1.0,
        slippage_bps=0,
    )
    buy = result["fills"][0]
    assert buy["side"] == "buy"
    assert buy["quantity"] == 30
    assert buy["price"] == 10.0
    assert buy["commission"] == 1.0
    assert buy["cash_after"] == pytest.approx(1_000 - 30 * 10.0 - 1.0)
    assert result["fills"][-1]["side"] == "sell"
    assert result["metrics"]["ending_cash"] == pytest.approx(1_000 - 2.0)


def test_position_accounting():
    raw = _bars([10.0] * 8)
    result = run_backtest(
        bars=raw,
        strategy="buy_and_hold",
        symbol="MSFT",
        initial_capital=1_000,
        position_size=0.3,
        commission_per_trade=0,
        slippage_bps=0,
    )
    assert result["fills"][0]["position_after"] == 30
    assert result["equity_curve"][1]["position"] == 30
    assert result["fills"][-1]["position_after"] == 0
    assert result["equity_curve"][-1]["position"] == 0


def test_transaction_costs_and_slippage_reduce_equity():
    raw = _bars([20.0] * 8)
    cheap = run_backtest(
        bars=raw,
        strategy="buy_and_hold",
        symbol="NVDA",
        initial_capital=5_000,
        position_size=0.3,
        commission_per_trade=0,
        slippage_bps=0,
    )
    costly = run_backtest(
        bars=raw,
        strategy="buy_and_hold",
        symbol="NVDA",
        initial_capital=5_000,
        position_size=0.3,
        commission_per_trade=2.0,
        slippage_bps=50,
    )
    assert costly["metrics"]["final_equity"] < cheap["metrics"]["final_equity"]
    assert costly["fills"][0]["price"] > cheap["fills"][0]["price"]
    assert costly["fills"][0]["commission"] == 2.0


def test_drawdown():
    closes = [100.0, 100.0, 80.0, 50.0, 50.0, 50.0, 50.0, 50.0]
    raw = _bars(closes, opens=[100.0] * 8)
    result = run_backtest(
        bars=raw,
        strategy="buy_and_hold",
        symbol="AAPL",
        initial_capital=10_000,
        position_size=0.3,
        commission_per_trade=0,
        slippage_bps=0,
    )
    assert result["metrics"]["maximum_drawdown"] == pytest.approx(0.15, abs=0.02)
    assert result["metrics"]["maximum_drawdown"] > 0
    dd = [point["drawdown"] for point in result["metrics"]["drawdown_curve"]]
    assert max(dd) == pytest.approx(result["metrics"]["maximum_drawdown"])


def test_sharpe_calculation():
    equities = [100.0, 102.0, 101.0, 104.0, 108.0, 107.0, 111.0, 110.0, 115.0]
    curve = [
        {"timestamp": _ts(i).isoformat(), "equity": value, "cash": value}
        for i, value in enumerate(equities)
    ]
    metrics = compute_metrics(initial_capital=100.0, equity_curve=curve, closed_trades=[])
    daily = [(equities[i] / equities[i - 1]) - 1.0 for i in range(1, len(equities))]
    mean = sum(daily) / len(daily)
    var = sum((item - mean) ** 2 for item in daily) / (len(daily) - 1)
    std = var**0.5
    expected = (mean / std) * (252**0.5)
    assert metrics["sharpe_ratio"] == pytest.approx(expected, rel=1e-9)
    assert metrics["volatility"] == pytest.approx(std * (252**0.5), rel=1e-9)


def test_results_are_labeled_historical_simulation():
    result = run_backtest(
        bars=_bars([10.0] * 8),
        strategy="buy_and_hold",
        symbol="SPY",
        initial_capital=10_000,
        position_size=0.1,
        commission_per_trade=0,
        slippage_bps=0,
    )
    assert result["result_kind"] == "HISTORICAL_SIMULATION"
    assert result["result_label"] == "HISTORICAL SIMULATION"
    assert result["live_returns"] is False
    assert result["live_trading"] is False
    assert result["spy_comparison"]["label"] == "SPY_buy_and_hold"
    assert result["buy_and_hold"]["total_return"] is not None


def test_persist_backtest_run(tmp_path: Path, monkeypatch):
    engine = get_engine(sqlite_url(tmp_path / "backtests.sqlite"))
    ensure_schema(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(backtest_store, "SessionLocal", lambda: Session())
    monkeypatch.setattr(backtest_store, "get_engine", lambda: engine)
    result = run_backtest(
        bars=_bars([12.0] * 8),
        strategy="buy_and_hold",
        symbol="AAPL",
        initial_capital=8_000,
        position_size=0.2,
        commission_per_trade=0,
        slippage_bps=0,
    )
    stored = backtest_store.save_backtest_run(result)
    fetched = backtest_store.get_backtest_run(stored["id"])
    assert fetched is not None
    assert fetched["result_kind"] == "HISTORICAL_SIMULATION"
    assert fetched["live_returns"] is False
    listed = backtest_store.list_backtest_runs()
    assert listed[0]["id"] == stored["id"]
    assert listed[0]["symbol"] == "AAPL"
