"""Market snapshot helpers — real bars/session only."""

from datetime import datetime, timezone

from app.models.market_data import MarketClock, StockBar
from app.services.equity_simulator import positions_from_fills
from app.services.market_snapshot import bar_stats, classify_session, normalize_symbols


def test_classify_unknown_clock_is_not_data_unavailable():
    clock = MarketClock(availability="DATA_UNAVAILABLE", is_open=None)
    assert classify_session(clock) == "UNKNOWN"


def test_classify_regular_when_open():
    clock = MarketClock(
        is_open=True,
        timestamp=datetime(2026, 9, 17, 14, 30, tzinfo=timezone.utc),
        availability="AVAILABLE",
    )
    assert classify_session(clock) in {"REGULAR", "PRE-MARKET", "AFTER-HOURS", "OVERNIGHT"}


def test_classify_after_hours_weekday():
    clock = MarketClock(
        is_open=False,
        timestamp=datetime(2026, 9, 17, 22, 30, tzinfo=timezone.utc),
        availability="AVAILABLE",
    )
    assert classify_session(clock) == "AFTER-HOURS"
    clock = MarketClock(
        is_open=False,
        timestamp=datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc),
        availability="AVAILABLE",
    )
    assert classify_session(clock) == "CLOSED"


def test_bar_stats_change_from_previous_close():
    bars = [
        StockBar(close=100.0, volume=10),
        StockBar(close=110.0, volume=20),
    ]
    stats = bar_stats(bars, 110.0)
    assert stats["previous_close"] == 100.0
    assert stats["day_change"] == 10.0
    assert stats["volume"] == 20


def test_normalize_symbols_dedupes():
    assert normalize_symbols("aapl, AAPL, msft") == ["AAPL", "MSFT"]


def test_positions_from_fills_net_long():
    fills = [
        {"symbol": "AAPL", "side": "buy", "quantity": 2, "price": 100, "company": "Apple Inc."},
        {"symbol": "AAPL", "side": "sell", "quantity": 1, "price": 110},
    ]
    positions = positions_from_fills(fills)
    assert len(positions) == 1
    assert positions[0]["quantity"] == 1
    assert positions[0]["simulated"] is True
    assert positions[0]["live_trading"] is False
