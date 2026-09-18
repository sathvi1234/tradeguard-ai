"""Market Data Integrity Engine unit tests. No Alpaca network. No live orders."""

from datetime import datetime, timedelta, timezone

from app.risk.risk_guardian import RiskGuardian, RiskGuardianDecision
from app.models.enums import TradingMode
from app.services.data_integrity import (
    DATA_ERROR,
    DATA_INVALID,
    DATA_STALE,
    DATA_UNAVAILABLE,
    DATA_WARNING,
    LIVE_FRESH,
    MARKET_CLOSED,
    assess_market_data,
)
from app.services.market_snapshot import enrich_market_state


def _now() -> datetime:
    return datetime(2026, 6, 18, 15, 30, tzinfo=timezone.utc)  # Thursday regular hours UTC


def _base(**overrides):
    payload = {
        "symbol": "AAPL",
        "price": 190.0,
        "bid": 189.9,
        "ask": 190.1,
        "previous_close": 189.0,
        "session": "REGULAR",
        "market_status": "OPEN",
        "market_open": True,
        "freshness": "FRESH",
        "last_update": _now().isoformat(),
        "bar_count": 20,
        "bars": [{"timestamp": f"2026-06-{i:02d}T20:00:00+00:00", "close": 180 + i} for i in range(1, 21)],
        "quote": {"symbol": "AAPL", "bid": 189.9, "ask": 190.1, "timestamp": _now().isoformat()},
        "trade": {"symbol": "AAPL", "price": 190.0, "timestamp": _now().isoformat()},
    }
    payload.update(overrides)
    return payload


def test_live_fresh_regular_session():
    report = assess_market_data(_base(), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == LIVE_FRESH
    assert report["fail_closed"] is False
    assert report["fabricated"] is False


def test_market_closed_is_not_data_unavailable():
    report = assess_market_data(
        _base(
            session="CLOSED",
            market_status="CLOSED",
            market_open=False,
            price=None,
            bid=None,
            ask=None,
            last_update=None,
            quote={},
            trade={},
        ),
        expected_symbol="AAPL",
        now=_now(),
    )
    assert report["integrity_state"] == MARKET_CLOSED
    assert report["integrity_state"] != DATA_UNAVAILABLE
    assert report["fail_closed"] is False


def test_missing_price_when_open_is_unavailable():
    report = assess_market_data(
        _base(price=None, bid=None, ask=None, last_update=_now().isoformat(), quote={}, trade={}),
        expected_symbol="AAPL",
        now=_now(),
    )
    assert report["integrity_state"] == DATA_UNAVAILABLE
    assert report["fail_closed"] is True
    assert report["fabricated"] is False


def test_null_price_not_replaced_with_zero():
    report = assess_market_data(
        _base(price=None, bid=None, ask=None, quote={}, trade={}),
        expected_symbol="AAPL",
        now=_now(),
    )
    assert report["integrity_state"] == DATA_UNAVAILABLE
    assert report["fail_closed"] is True


def test_closed_with_valid_quote_stays_market_closed():
    report = assess_market_data(
        _base(session="OVERNIGHT", market_status="CLOSED", market_open=False),
        expected_symbol="AAPL",
        now=_now(),
    )
    assert report["integrity_state"] == MARKET_CLOSED
    assert report["fail_closed"] is False


def test_stale_quote_fail_closed():
    old = (_now() - timedelta(minutes=10)).isoformat()
    report = assess_market_data(_base(last_update=old, freshness="STALE"), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_STALE
    assert report["fail_closed"] is True


def test_invalid_timestamp():
    report = assess_market_data(_base(last_update="not-a-timestamp"), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID
    assert report["fail_closed"] is True


def test_future_timestamp():
    future = (_now() + timedelta(minutes=10)).isoformat()
    report = assess_market_data(_base(last_update=future), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID
    assert report["fail_closed"] is True


def test_duplicate_bar_timestamps():
    bars = [{"timestamp": "2026-06-01T20:00:00+00:00", "close": 1} for _ in range(6)]
    report = assess_market_data(_base(bars=bars, bar_count=6), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] in {DATA_WARNING, LIVE_FRESH}
    assert any(c["check"] == "duplicate_timestamps" and c["status"] == DATA_WARNING for c in report["checks"])


def test_zero_price_invalid():
    report = assess_market_data(_base(price=0, bid=1, ask=1.1), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID
    assert report["fail_closed"] is True


def test_negative_price_invalid():
    report = assess_market_data(_base(price=-5, bid=1, ask=1.1), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID


def test_bid_greater_than_ask():
    report = assess_market_data(_base(bid=191.0, ask=190.0), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID
    assert report["fail_closed"] is True


def test_abnormally_large_spread_invalid():
    report = assess_market_data(_base(bid=100.0, ask=140.0, price=120.0), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID


def test_wide_spread_warning():
    report = assess_market_data(_base(bid=100.0, ask=107.0, price=103.5, previous_close=103.0), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_WARNING
    assert report["fail_closed"] is False


def test_abnormal_price_jump_warning():
    report = assess_market_data(_base(price=220.0, previous_close=180.0, bid=219.9, ask=220.1), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_WARNING


def test_corporate_action_split_anomaly_invalid():
    report = assess_market_data(_base(price=20.0, previous_close=180.0, bid=19.9, ask=20.1), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID
    assert report["fail_closed"] is True


def test_symbol_mismatch():
    report = assess_market_data(_base(symbol="MSFT"), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_INVALID


def test_insufficient_history_warning():
    report = assess_market_data(_base(bars=[], bar_count=0), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_WARNING
    assert report["fail_closed"] is False


def test_provider_error():
    report = assess_market_data(_base(data_error="rate_limited"), expected_symbol="AAPL", now=_now())
    assert report["integrity_state"] == DATA_ERROR
    assert report["fail_closed"] is True


def test_enrich_attaches_integrity_and_keeps_closed_distinct():
    out = enrich_market_state(
        {
            "symbol": "AAPL",
            "price": 337.09,
            "session": "OVERNIGHT",
            "freshness": "STALE",
            "market_open": False,
            "last_update": (_now() - timedelta(hours=8)).isoformat(),
        }
    )
    assert out["market_status"] == "CLOSED"
    assert out["integrity_state"] in {DATA_STALE, MARKET_CLOSED}
    assert out["integrity_state"] != DATA_UNAVAILABLE


async def test_risk_guardian_rejects_invalid_integrity():
    guardian = RiskGuardian()
    result = await guardian.evaluate_trade(
        symbol="AAPL",
        proposed_size=100,
        portfolio_value=100000,
        current_equity=100000,
        current_drawdown=0.0,
        current_positions=0,
        max_loss=100,
        potential_reward=200,
        ai_confidence=0.9,
        contract_validity={"is_liquid": True, "open_interest": 1000},
        market_data_timestamp=_now().replace(tzinfo=None),
        trading_mode=TradingMode.NORMAL,
        data_integrity={"integrity_state": DATA_INVALID, "fail_closed": True},
    )
    assert result.decision == RiskGuardianDecision.REJECTED
    assert "market_data_integrity" in result.limits_checked
    assert any("integrity" in reason.lower() for reason in result.rejection_reasons)
