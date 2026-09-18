"""ORACLE-inspired intelligence APIs. No credentials. No duplicate position/order routes."""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.alpaca.iex_stream import get_iex_hub, overlay_snapshot
from app.api.autonomous import autonomous_engine
from app.config import settings
from app.models.schemas import DATA_UNAVAILABLE
from app.services.market_intelligence import MarketIntelligenceService
from app.services.market_snapshot import DEFAULT_WATCHLIST, normalize_symbols
from app.services.portfolio_greeks import PortfolioGreeksService
from app.services.position_restructuring import PositionRestructuringService
from app.services.quant_copilot import QuantCopilot, collect_copilot_state
from app.services.strategy_library import get_strategy_library
from app.trading.audit_logger import AuditEventType, AuditSeverity
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["intelligence"])
_greeks = PortfolioGreeksService()
_intel = MarketIntelligenceService()
_copilot = QuantCopilot()
_restructure = PositionRestructuringService()


class CopilotAskRequest(BaseModel):
    question: str = Field(..., description="Structured portfolio/trading question")


@router.get("/copilot")
async def copilot_info() -> dict:
    return {
        "can_execute": False,
        "llm_explanatory_only": True,
        "dry_run": settings.dry_run,
        "paper_trading": True,
        "endpoint": "POST /api/v1/copilot/ask",
        "intents": [
            "portfolio",
            "positions",
            "delta",
            "proposed",
            "rejected",
            "risks",
            "volatility",
            "protection",
            "critical",
            "debate",
            "red_team",
            "orders",
        ],
    }


@router.post("/copilot/ask")
async def copilot_ask(request: CopilotAskRequest) -> dict:
    state = await collect_copilot_state(autonomous_engine)
    result = await _copilot.answer_async(request.question, state)
    payload = result.model_dump()
    payload["can_execute"] = False
    return payload


@router.get("/market-data")
async def get_watchlist(symbols: Optional[str] = Query(default=None)) -> dict:
    alpaca = autonomous_engine.alpaca_service
    tickers = normalize_symbols(symbols, DEFAULT_WATCHLIST)
    items = [overlay_snapshot(item) for item in await alpaca.snapshot_watchlist(tickers)]
    live = any(item.get("live") or isinstance(item.get("price"), (int, float)) for item in items if isinstance(item, dict))
    clock = items[0].get("clock") if items else (await alpaca.get_market_clock()).model_dump(mode="json")
    hub = get_iex_hub()
    return {
        "symbols": tickers,
        "items": items,
        "clock": clock,
        "source": "alpaca",
        "feed": "iex",
        "ws_state": hub.state,
        "live_market_data": live or hub.state == "LIVE",
        "live_trading": False,
        "paper_trading": True,
        "dry_run": settings.dry_run,
    }


@router.get("/market-data/{symbol}")
async def get_market_data(symbol: str) -> dict:
    alpaca = autonomous_engine.alpaca_service
    snap = overlay_snapshot(await alpaca.snapshot_symbol(symbol.upper()))
    snap["dry_run"] = settings.dry_run
    snap["paper_trading"] = True
    snap["live_trading"] = False
    return snap


@router.get("/data-quality/{symbol}")
async def get_data_quality(symbol: str) -> dict:
    """Market Data Integrity report for a symbol. Never invents prices."""
    alpaca = autonomous_engine.alpaca_service
    from app.services.data_integrity import assess_market_data, attach_integrity

    try:
        snap = overlay_snapshot(await alpaca.snapshot_symbol(symbol.upper()))
        snap = attach_integrity(snap, expected_symbol=symbol.upper())
        report = snap.get("integrity") if isinstance(snap.get("integrity"), dict) else assess_market_data(snap, expected_symbol=symbol.upper())
        return {
            "symbol": symbol.upper(),
            "integrity_state": report.get("integrity_state"),
            "fail_closed": report.get("fail_closed"),
            "notes": report.get("notes"),
            "checks": report.get("checks"),
            "flags": report.get("flags"),
            "missing_fields": report.get("missing_fields"),
            "session": snap.get("session"),
            "market_status": snap.get("market_status"),
            "freshness": snap.get("freshness"),
            "quote_available": snap.get("quote_available"),
            "price_present": isinstance(snap.get("price"), (int, float)),
            "risk_guardian_is_final_authority": True,
            "fabricated": False,
            "live_trading": False,
            "dry_run": settings.dry_run,
            "source": "alpaca",
            "feed": snap.get("feed") or "iex",
        }
    except Exception as exc:
        logger.error("data-quality failed for %s: %s", symbol, exc)
        return {
            "symbol": symbol.upper(),
            "integrity_state": "DATA_ERROR",
            "fail_closed": True,
            "notes": "Market data provider error. Fail closed.",
            "checks": [{"check": "provider", "status": "DATA_ERROR", "detail": "Request failed."}],
            "flags": ["provider"],
            "missing_fields": ["price"],
            "risk_guardian_is_final_authority": True,
            "fabricated": False,
            "live_trading": False,
            "dry_run": settings.dry_run,
        }


@router.get("/options/{symbol}")
async def get_options(symbol: str) -> dict:
    alpaca = autonomous_engine.alpaca_service
    underlying = symbol.upper()
    contracts = await alpaca.get_option_contracts(underlying)
    snapshots = await alpaca.get_option_snapshots(underlying)
    return {
        "symbol": underlying,
        "count": len(contracts),
        "contracts": [c.model_dump() for c in contracts],
        "snapshots": {k: v.model_dump(mode="json") for k, v in snapshots.items()},
        "source": "alpaca",
        "dry_run": settings.dry_run,
        "availability": "AVAILABLE" if contracts else DATA_UNAVAILABLE,
    }


@router.get("/greeks")
async def get_greeks() -> dict:
    from app.services.demo_ledger import get_demo_ledger
    from app.services.portfolio_greeks import OCC_PATTERN

    try:
        engine_positions = list(autonomous_engine.position_manager.get_open_positions() or [])
        demo_positions = get_demo_ledger().list_raw_positions()
        positions = engine_positions + demo_positions
        snaps = []
        for position in positions:
            symbol = str(getattr(position, "symbol", None) or (position.get("symbol") if isinstance(position, dict) else "") or "")
            occ = str(getattr(position, "occ_symbol", None) or (position.get("occ_symbol") if isinstance(position, dict) else "") or "")
            contract = occ or symbol
            if not OCC_PATTERN.match(contract.upper()):
                continue
            snap = await autonomous_engine.alpaca_service.get_option_snapshot(contract)
            if snap:
                snaps.append(snap)
        snapshot = _greeks.snapshot(positions=positions, option_snapshots=snaps)
        payload = snapshot.model_dump()
        if snapshot.reason_code == "NO_OPTION_POSITIONS":
            payload["greeks_state"] = "NO_OPTION_POSITIONS"
        elif snapshot.availability.value == "AVAILABLE":
            payload["greeks_state"] = "HAS_OPTIONS"
        else:
            payload["greeks_state"] = "GREEKS_UNAVAILABLE"
        return payload
    except Exception as exc:
        logger.error(f"Failed to compute portfolio Greeks: {exc}")
        return {
            "availability": DATA_UNAVAILABLE,
            "greeks_state": "ERROR",
            "reason_code": "GREEKS_ERROR",
            "notes": "Greeks request failed. Values are not invented.",
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "portfolio_delta": None,
            "portfolio_gamma": None,
            "portfolio_theta": None,
            "portfolio_vega": None,
        }


@router.get("/intelligence")
async def get_intelligence(symbol: str = "SPY") -> dict:
    from app.autonomous.master_orchestrator import _intel_payload

    alpaca = autonomous_engine.alpaca_service
    underlying = symbol.upper()
    clock = await alpaca.get_market_clock()
    snap = overlay_snapshot(await alpaca.snapshot_symbol(underlying, clock=clock))
    bars = []
    try:
        bars = await alpaca.get_bars(underlying, timeframe="1Day", limit=10)
    except Exception:
        bars = []
    contracts = await alpaca.get_option_contracts(underlying, limit=20)
    snapshots = await alpaca.get_option_snapshots(underlying)
    real = _intel_payload(snap, clock, None, bars)
    if contracts:
        real["option_chain_structure"] = f"{len(contracts)}_contracts"
    for option_snap in snapshots.values():
        if option_snap.open_interest is not None and "open_interest" not in real:
            real["open_interest"] = str(option_snap.open_interest)
        if option_snap.implied_volatility is not None and "iv" not in real:
            real["iv"] = str(option_snap.implied_volatility)
    intel = _intel.snapshot(underlying, real_data=real or None)
    payload = intel.model_dump()
    payload["unavailable_without_source"] = [
        "options_flow",
        "volume_profile_poc",
        "anchored_vwap",
        "vix_intelligence",
        "news_sentiment",
        "treasury_yields",
        "earnings_events",
    ]
    payload["live_trading"] = False
    payload["paper_trading"] = True
    payload["dry_run"] = settings.dry_run
    return payload


@router.get("/strategies")
async def get_strategies() -> dict:
    return {
        "auto_trade": False,
        "strategies": [s.model_dump() for s in get_strategy_library()],
    }


@router.get("/memory")
async def get_memory(symbol: Optional[str] = None, limit: int = 50) -> list:
    return [r.model_dump(mode="json") for r in autonomous_engine.trade_memory.list_records(symbol=symbol, limit=limit)]


@router.get("/risk/bodyguard")
async def get_bodyguard() -> dict:
    from app.risk.risk_bodyguard import RiskBodyguard

    mode = autonomous_engine.drawdown_guardian.state.current_mode if autonomous_engine.drawdown_guardian.state else None
    dd = autonomous_engine.drawdown_guardian.state.drawdown_percentage if autonomous_engine.drawdown_guardian.state else 0.0
    assessment = RiskBodyguard().assess(
        autonomous_engine.position_manager.get_open_positions(),
        trading_mode=mode,
        drawdown=dd,
    )
    return assessment.model_dump()


@router.get("/restructuring")
async def get_restructuring() -> dict:
    positions = autonomous_engine.position_manager.get_open_positions()
    mode = autonomous_engine.drawdown_guardian.state.current_mode if autonomous_engine.drawdown_guardian.state else None
    recs = [_restructure.recommend(p, trading_mode=mode).model_dump() for p in positions]
    if not recs:
        recs = [_restructure.recommend(None, trading_mode=mode).model_dump()]
    return {"recommendation_only": True, "items": recs}


@router.get("/voice")
async def get_voice_status() -> dict:
    """Simulated Call Agent / mock voice only. No telephony credentials."""
    return {
        "simulated": True,
        "mock_voice": True,
        "real_phone_call": False,
        "telephony": "disabled",
        "provider": "MOCK_VOICE",
        "dry_run": settings.dry_run,
        "paper_trading": True,
        "live_trading": False,
        "audit_event": AuditEventType.VOICE_ALERT.value,
        "stages": [
            "CALLING",
            "CONNECTED",
            "ANALYZING PORTFOLIO",
            "ANALYZING RISK",
            "RISK ALERT",
            "CALL COMPLETED",
        ],
        "labels": ["SIMULATED AI VOICE", "NO REAL PHONE CALL"],
        "speech_synthesis": "browser_native",
    }


@router.post("/voice/call")
async def simulate_voice_call() -> dict:
    """Log a mock voice alert from current engine state. Never places a phone call."""
    engine = autonomous_engine
    dd_state = engine.drawdown_guardian.state
    mode = dd_state.current_mode.value if dd_state else None
    drawdown = dd_state.drawdown_percentage if dd_state else None
    snapshot = engine.portfolio_monitor.get_latest_snapshot()
    debate = engine.last_debate or {}
    rg = (debate.get("risk_guardian_result") if isinstance(debate, dict) else None) or {}
    bodyguard = engine.last_bodyguard or {}
    positions = [p.to_dict() for p in engine.position_manager.get_open_positions()]
    reason = engine.last_cycle_message or engine.last_halt_reason
    if mode == "critical":
        reason = reason or "CRITICAL mode: new trades are blocked"
        severity = AuditSeverity.CRITICAL
    elif mode == "protection":
        reason = reason or "PROTECTION mode mock voice alert"
        severity = AuditSeverity.HIGH
    else:
        reason = reason or "Simulated Call Agent walkthrough"
        severity = AuditSeverity.INFO

    event = engine.audit_logger.log_event(
        AuditEventType.VOICE_ALERT,
        severity,
        None,
        f"SIMULATED AI VOICE — {reason}",
        {
            "simulated": True,
            "real_phone_call": False,
            "dry_run": True,
            "mode": mode,
            "drawdown": drawdown,
        },
    )
    snap = snapshot.to_dict() if snapshot else {}
    value = snap.get("account_value")
    dd_text = f"{drawdown * 100:.2f} percent" if isinstance(drawdown, (int, float)) else "unavailable"
    rg_decision = rg.get("decision") if isinstance(rg, dict) else None
    gate = str(rg_decision or engine.last_cycle_status or "no cycle yet")
    script = (
        "Hello Demo User. This is your Trade AI risk assistant. "
        "Your current portfolio is being monitored in paper trading mode. "
        f"The current portfolio value is {value if value is not None else 'unavailable'}. "
        f"The current drawdown is {dd_text}. "
        f"The current risk mode is {mode or 'unavailable'}. "
        f"Risk Guardian has determined that new trading activity is {gate}. "
        "This is a simulated educational alert. No real phone call."
    )
    return {
        "simulated": True,
        "mock_voice": True,
        "real_phone_call": False,
        "telephony": "disabled",
        "labels": ["SIMULATED AI VOICE", "NO REAL PHONE CALL"],
        "stages": [
            "CALLING",
            "CONNECTED",
            "ANALYZING PORTFOLIO",
            "ANALYZING RISK",
            "RISK ALERT",
            "CALL COMPLETED",
        ],
        "script": script,
        "audit_event_id": event.event_id,
        "reason": reason,
        "risk_mode": mode,
        "drawdown": drawdown,
        "portfolio": snap or None,
        "positions": positions,
        "risk_guardian": rg,
        "risk_bodyguard": bodyguard,
        "critical": mode == "critical",
    }
