"""Phase 3 real Alpaca market-data tests. All Alpaca HTTP is mocked."""

from datetime import datetime, timedelta, timezone
from inspect import getsource
from unittest.mock import AsyncMock, patch

import pytest

from app.alpaca.exceptions import AlpacaError, AlpacaRateLimitError
from app.alpaca.freshness import evaluate_freshness
from app.alpaca.service import AlpacaService
from app.autonomous.master_orchestrator import MasterOrchestrator
from app.config import settings
from app.models.market_data import FreshnessStatus, OptionContract, OptionSnapshot
from app.models.schemas import DATA_UNAVAILABLE, DataAvailability
from app.services.contract_selector import ContractSelector, filter_contracts, filter_quoted
from app.services.portfolio_greeks import PortfolioGreeksService
from app.services.strategy_library import missing_required_market_fields
from app.trading.autonomous_engine import AutonomousTradingEngine


def _now():
    return datetime.now(timezone.utc)


def _account():
    return {
        "paper_trading_allowed": True,
        "trading_blocked": False,
        "portfolio_value": 100000.0,
        "cash": 80000.0,
        "buying_power": 90000.0,
        "equity": 100000.0,
        "status": "ACTIVE",
    }


@pytest.mark.asyncio
async def test_real_quote_normalization():
    service = AlpacaService()
    service._client = AsyncMock()
    service.client.get_latest_stock_quote = AsyncMock(
        return_value={"quote": {"bp": 10.0, "ap": 10.05, "bs": 100, "as": 200, "t": _now().isoformat()}}
    )
    quote = await service.get_latest_quote("SPY")
    assert quote.bid == 10.0
    assert quote.ask == 10.05
    assert quote.bid_size == 100
    assert quote.ask_size == 200
    assert quote.source == "alpaca"
    assert quote.freshness == FreshnessStatus.FRESH
    assert quote.availability == "AVAILABLE"


@pytest.mark.asyncio
async def test_quote_unavailable():
    service = AlpacaService()
    service._client = AsyncMock()
    service.client.get_latest_stock_quote = AsyncMock(side_effect=AlpacaError("network"))
    quote = await service.get_latest_quote("SPY")
    assert quote.availability == DATA_UNAVAILABLE
    assert quote.bid is None
    assert quote.freshness == FreshnessStatus.DATA_UNAVAILABLE


@pytest.mark.asyncio
async def test_stale_quote():
    service = AlpacaService()
    service._client = AsyncMock()
    old = (_now() - timedelta(seconds=settings.quote_max_age_seconds + 30)).isoformat()
    service.client.get_latest_stock_quote = AsyncMock(
        return_value={"quote": {"bp": 10.0, "ap": 10.05, "t": old}}
    )
    quote = await service.get_latest_quote("SPY")
    assert quote.freshness == FreshnessStatus.STALE
    assert quote.usable is False


def test_freshness_thresholds_use_config():
    ts = _now() - timedelta(seconds=settings.quote_max_age_seconds + 1)
    assert evaluate_freshness(ts) == FreshnessStatus.STALE
    assert evaluate_freshness(_now()) == FreshnessStatus.FRESH
    assert evaluate_freshness(None) == FreshnessStatus.DATA_UNAVAILABLE


def test_option_contract_normalization_and_filters():
    expired = OptionContract(
        occ_symbol="SPY201231C00400000",
        underlying_symbol="SPY",
        option_type="call",
        strike=400,
        expiration="2020-12-31",
        tradable=True,
        status="active",
    )
    untradable = OptionContract(
        occ_symbol="SPY260320C00500000",
        underlying_symbol="SPY",
        option_type="call",
        strike=500,
        expiration="2027-03-19",
        tradable=False,
        status="active",
    )
    good = OptionContract(
        occ_symbol="SPY260320C00510000",
        underlying_symbol="SPY",
        option_type="call",
        strike=510,
        expiration="2027-03-19",
        tradable=True,
        status="active",
    )
    kept = filter_contracts([expired, untradable, good])
    assert [c.occ_symbol for c in kept] == ["SPY260320C00510000"]


def test_option_quote_normalization_and_spread_filter():
    service = AlpacaService()
    snap = service._map_option_snapshot(
        "SPY260320C00500000",
        {
            "latestQuote": {"bp": 1.0, "ap": 1.02, "t": _now().isoformat()},
            "latestTrade": {"p": 1.01},
            "impliedVolatility": 0.22,
            "greeks": {"delta": 0.4, "gamma": 0.02, "theta": -0.03, "vega": 0.1},
        },
    )
    assert snap.bid == 1.0
    assert snap.ask == 1.02
    assert snap.implied_volatility == 0.22
    assert snap.greeks_quality == "REAL"

    contract = OptionContract(
        occ_symbol=snap.occ_symbol,
        underlying_symbol="SPY",
        option_type="call",
        strike=500,
        expiration="2027-03-19",
        tradable=True,
        status="active",
    )
    wide = snap.model_copy(update={"bid": 1.0, "ask": 2.0})
    usable = filter_quoted([contract], {snap.occ_symbol: wide}, max_spread_pct=0.15)
    assert usable == []
    tight = filter_quoted([contract], {snap.occ_symbol: snap}, max_spread_pct=0.15)
    assert len(tight) == 1


def test_missing_greeks_quality():
    service = AlpacaService()
    snap = service._map_option_snapshot(
        "SPY260320C00500000",
        {"latestQuote": {"bp": 1.0, "ap": 1.02, "t": _now().isoformat()}},
    )
    assert snap.delta is None
    assert snap.greeks_quality == DATA_UNAVAILABLE
    greeks = PortfolioGreeksService().snapshot(option_snapshots=[snap])
    assert greeks.availability == DataAvailability.EMPTY
    assert greeks.reason_code == "NO_OPTION_POSITIONS"


def test_greeks_from_real_snapshots():
    snap = OptionSnapshot(
        occ_symbol="X",
        delta=0.5,
        gamma=0.1,
        theta=-0.02,
        vega=0.2,
        greeks_quality="REAL",
        availability="AVAILABLE",
    )
    greeks = PortfolioGreeksService().snapshot(option_snapshots=[snap])
    assert greeks.quality == "REAL"
    assert greeks.portfolio_delta == 0.5


def test_real_data_requirement_enforcement():
    missing = missing_required_market_fields(
        "theta_iron_condor",
        {"underlying_quote": True, "option_chain": True, "option_quotes": True},
    )
    assert "iv" in missing
    ok = missing_required_market_fields(
        "directional_vertical_spread",
        {"underlying_quote": True, "option_chain": True, "option_quotes": True},
    )
    assert ok == []


@pytest.mark.asyncio
async def test_dynamic_contract_selection():
    selector = ContractSelector(alpaca=AsyncMock())
    quote = AsyncMock()
    quote.usable = True
    quote.bid = 100.0
    quote.ask = 100.1
    selector.alpaca.get_asset = AsyncMock(return_value={"tradable": True})
    selector.alpaca.get_latest_quote = AsyncMock(return_value=quote)
    selector.alpaca.get_option_contracts = AsyncMock(
        return_value=[
            OptionContract(
                occ_symbol="SPY260320C00105000",
                underlying_symbol="SPY",
                option_type="call",
                strike=105,
                expiration="2027-03-19",
                tradable=True,
                status="active",
            )
        ]
    )
    selector.alpaca.get_option_snapshots = AsyncMock(
        return_value={
            "SPY260320C00105000": OptionSnapshot(
                occ_symbol="SPY260320C00105000",
                bid=1.5,
                ask=1.55,
                freshness=FreshnessStatus.FRESH,
                availability="AVAILABLE",
            )
        }
    )
    picked = await selector.select(watchlist=["SPY"])
    assert picked is not None
    assert picked.underlying == "SPY"
    assert picked.occ_symbol == "SPY260320C00105000"


def test_hardcoded_contract_removed_from_orchestrator():
    source = getsource(MasterOrchestrator)
    assert "2024-12-20" not in source
    assert "strike=105" not in source
    assert "execute_order" not in source


@pytest.mark.asyncio
async def test_market_closed_behavior():
    engine = AutonomousTradingEngine(dry_run=True)
    from app.models.market_data import MarketClock

    engine.alpaca_service.get_account = AsyncMock(return_value=_account())
    engine.alpaca_service.get_market_clock = AsyncMock(
        return_value=MarketClock(is_open=False, availability="AVAILABLE", session="CLOSED")
    )
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "AAPL",
            "price": 100.0,
            "bid": 99.9,
            "ask": 100.1,
            "session": "CLOSED",
            "freshness": "STALE",
            "volume": 1000,
            "previous_close": 99.0,
            "day_change": 1.0,
            "day_change_pct": 0.01,
        }
    )
    engine.alpaca_service.get_bars = AsyncMock(return_value=[])
    engine.orchestrator.contract_selector.select = AsyncMock(return_value=None)
    from app.autonomous.debate_engine import DebateResult

    debate = DebateResult("closed-test")
    debate.completed = True
    debate.symbol = "AAPL"
    debate.final_decision = {"decision": "no_trade", "confidence": 0.4, "reasoning": "hold"}
    debate.agent_outputs = {
        "market_scout": {"reasoning": "AAPL 100", "data": {"current_price": 100, "valid": True}},
        "bull_agent": {"reasoning": "bull", "data": {"thesis": "upside"}},
        "bear_agent": {"reasoning": "bear", "data": {"thesis": "downside"}},
    }
    engine.debate_engine.run_debate = AsyncMock(return_value=debate)
    engine.debate_engine.market_scout.analyze = AsyncMock(
        return_value=type(
            "A",
            (),
            {
                "to_dict": lambda self: debate.agent_outputs["market_scout"],
                "errors": None,
                "data": {"current_price": 100},
                "confidence": 0.5,
            },
        )()
    )
    engine.order_executor.execute_order = AsyncMock()
    result = await engine.run_cycle()
    engine.order_executor.execute_order.assert_not_called()
    assert result["halt_reason"] == "MARKET_CLOSED"
    assert result["status"] == "no_trade"
    assert engine.last_risk_guardian["reason"] == "MARKET_CLOSED"
    assert engine.last_decision["execution_decision"] == "NO TRADE"


@pytest.mark.asyncio
async def test_api_failure_and_rate_limit():
    service = AlpacaService()
    service._client = AsyncMock()
    service.client.get_latest_stock_quote = AsyncMock(side_effect=AlpacaRateLimitError("429"))
    quote = await service.get_latest_quote("SPY")
    assert quote.error == "rate_limited"
    assert quote.availability == DATA_UNAVAILABLE

    service.client.get_option_contracts = AsyncMock(side_effect=AlpacaRateLimitError("429"))
    contracts = await service.get_option_contracts("SPY")
    assert contracts == []


@pytest.mark.asyncio
async def test_fail_closed_and_no_order_submission():
    from app.agents.base import AgentAnalysis, AgentType
    from app.autonomous.debate_engine import DebateResult
    from app.models.market_data import MarketClock, SelectedContract, StockQuote, StockTrade

    engine = AutonomousTradingEngine(dry_run=True)
    now = _now()
    engine.alpaca_service.get_account = AsyncMock(return_value=_account())
    engine.alpaca_service.get_market_clock = AsyncMock(
        return_value=MarketClock(is_open=True, availability="AVAILABLE")
    )
    engine.alpaca_service.get_latest_quote = AsyncMock(
        return_value=StockQuote(
            symbol="SPY",
            bid=500,
            ask=500.1,
            timestamp=now,
            freshness=FreshnessStatus.FRESH,
            availability="AVAILABLE",
        )
    )
    engine.alpaca_service.get_latest_trade = AsyncMock(
        return_value=StockTrade(symbol="SPY", price=500, freshness=FreshnessStatus.FRESH, availability="AVAILABLE")
    )
    engine.alpaca_service.get_bars = AsyncMock(return_value=[])
    engine.alpaca_service.get_option_snapshot = AsyncMock(return_value=None)
    engine.alpaca_service.snapshot_symbol = AsyncMock(
        return_value={
            "symbol": "SPY",
            "price": 500,
            "bid": 500,
            "ask": 500.1,
            "session": "REGULAR",
            "freshness": "FRESH",
        }
    )
    engine.orchestrator.contract_selector.select = AsyncMock(
        return_value=SelectedContract(
            underlying="SPY",
            occ_symbol="SPY260320C00500000",
            option_type="call",
            strike=500,
            expiration="2027-03-19",
            bid=2.4,
            ask=2.5,
        )
    )
    scout = AgentAnalysis(
        agent_type=AgentType.MARKET_SCOUT,
        symbol="SPY",
        timestamp=datetime.utcnow(),
        confidence=0.7,
        reasoning="ok",
        data={"valid": True},
    )
    debate = DebateResult("d-ok")
    debate.completed = True
    debate.final_decision = {"decision": "buy", "proposed_size": 100, "confidence": 0.6}
    debate.risk_guardian_result = {"decision": "approved"}
    with patch.object(engine.debate_engine.market_scout, "analyze", new_callable=AsyncMock, return_value=scout):
        with patch.object(engine.debate_engine, "run_debate", new_callable=AsyncMock, return_value=debate):
            with patch.object(engine.order_executor, "execute_order", new_callable=AsyncMock) as exec_mock:
                result = await engine.run_cycle()
                exec_mock.assert_not_called()
    assert settings.dry_run is True
    assert engine.dry_run is True
    assert result["order"] is None
    assert result["status"] == "halted_after_risk_guardian"
    assert result["halt_reason"] == "DRY_RUN_ONLY"


def test_dry_run_remains_enabled():
    assert settings.dry_run is True
    engine = AutonomousTradingEngine(dry_run=True)
    assert engine.dry_run is True
    assert engine.order_executor.dry_run is True
