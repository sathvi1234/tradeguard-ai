from app.services.market_snapshot import enrich_market_state


def test_closed_stale_quote_is_not_data_unavailable():
    out = enrich_market_state(
        {
            "symbol": "AAPL",
            "price": 337.09,
            "session": "OVERNIGHT",
            "freshness": "STALE",
            "market_open": False,
        }
    )
    assert out["quote_available"] is True
    assert out["session"] == "OVERNIGHT"
    assert out["market_session"] == "OVERNIGHT"
    assert out["market_status"] == "CLOSED"
    assert out["freshness"] == "STALE"
    assert out["simulation_eligible"] is False
    assert out["simulation_reason"] == "WAITING FOR FRESH DATA"


def test_pre_market_is_closed_status_not_unavailable():
    out = enrich_market_state(
        {
            "symbol": "GOOGL",
            "price": 175.12,
            "session": "PRE_MARKET",
            "freshness": "FRESH",
            "market_open": False,
        }
    )
    assert out["market_status"] == "CLOSED"
    assert out["market_session"] == "PRE-MARKET"
    assert out["session"] == "PRE-MARKET"
    assert out["quote_available"] is True


def test_missing_freshness_with_price_becomes_stale_not_unavailable():
    out = enrich_market_state(
        {
            "symbol": "AAPL",
            "price": 337.09,
            "session": "OVERNIGHT",
            "freshness": "DATA_UNAVAILABLE",
            "market_open": False,
        }
    )
    assert out["freshness"] == "STALE"
    assert out["quote_available"] is True
    assert out["market_status"] == "CLOSED"
