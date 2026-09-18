"""Stock analytics and educational equity simulation APIs."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.autonomous import autonomous_engine
from app.config import settings
from app.llm.service import get_llm_service
from app.models.schemas import DATA_UNAVAILABLE, LLM_UNAVAILABLE
from app.services.equity_simulator import positions_from_fills, simulate_equity_order
from app.services.market_intelligence import MarketIntelligenceService
from app.services.technicals import analyze_bars
from app.trading.audit_logger import AuditEventType, AuditSeverity
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analytics"])
_intel = MarketIntelligenceService()


class EquityOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: int = Field(..., gt=0, le=1000)
    order_type: str = "market"
    limit_price: Optional[float] = None
    preview_only: bool = False


class StockAskRequest(BaseModel):
    question: str = Field(..., min_length=3)


def _unavailable(value: Any) -> bool:
    return value is None or value == "" or value == DATA_UNAVAILABLE


async def _analytics_payload(symbol: str) -> Dict[str, Any]:
    alpaca = autonomous_engine.alpaca_service
    underlying = symbol.upper()
    snap = await alpaca.snapshot_symbol(underlying)
    bars = await alpaca.get_bars(underlying, timeframe="1Day", limit=60)
    contracts = await alpaca.get_option_contracts(underlying, limit=30)
    snapshots = await alpaca.get_option_snapshots(underlying)
    technicals = analyze_bars(bars)
    intel_real: Dict[str, str] = {}
    if isinstance(snap.get("spread"), (int, float)):
        intel_real["bid_ask_spread"] = str(snap["spread"])
    if isinstance(snap.get("volume"), (int, float)):
        intel_real["volume"] = str(snap["volume"])
    if snap.get("session") not in (None, "", DATA_UNAVAILABLE):
        intel_real["market_session"] = str(snap["session"])
    intel = _intel.snapshot(underlying, real_data=intel_real or None).model_dump()

    option_rows: List[Dict[str, Any]] = []
    for contract in contracts[:12]:
        option_snap = snapshots.get(contract.occ_symbol)
        row = {
            "occ_symbol": contract.occ_symbol,
            "expiration": contract.expiration or DATA_UNAVAILABLE,
            "strike": contract.strike if contract.strike is not None else DATA_UNAVAILABLE,
            "call_put": contract.option_type or DATA_UNAVAILABLE,
            "bid": option_snap.bid if option_snap and option_snap.bid is not None else DATA_UNAVAILABLE,
            "ask": option_snap.ask if option_snap and option_snap.ask is not None else DATA_UNAVAILABLE,
            "mid": (
                round((option_snap.bid + option_snap.ask) / 2, 4)
                if option_snap and option_snap.bid is not None and option_snap.ask is not None
                else DATA_UNAVAILABLE
            ),
            "volume": option_snap.volume if option_snap and option_snap.volume is not None else DATA_UNAVAILABLE,
            "open_interest": option_snap.open_interest if option_snap and option_snap.open_interest is not None else (
                contract.open_interest if contract.open_interest is not None else DATA_UNAVAILABLE
            ),
            "iv": option_snap.implied_volatility if option_snap and option_snap.implied_volatility is not None else DATA_UNAVAILABLE,
            "delta": option_snap.delta if option_snap and option_snap.delta is not None else DATA_UNAVAILABLE,
            "gamma": option_snap.gamma if option_snap and option_snap.gamma is not None else DATA_UNAVAILABLE,
            "theta": option_snap.theta if option_snap and option_snap.theta is not None else DATA_UNAVAILABLE,
            "vega": option_snap.vega if option_snap and option_snap.vega is not None else DATA_UNAVAILABLE,
        }
        option_rows.append(row)

    payload = dict(snap)
    payload.update(
        {
            "technicals": technicals,
            "options": option_rows,
            "options_count": len(contracts),
            "intelligence": intel,
            "unavailable_without_source": [
                "company_fundamentals",
                "news_sentiment",
                "options_flow",
                "volume_profile_poc",
                "anchored_vwap",
                "vix_intelligence",
                "treasury_yields",
                "iv_skew_surface",
            ],
            "source": "alpaca",
            "feed": snap.get("feed") or "iex",
            "dry_run": settings.dry_run,
            "paper_trading": True,
            "live_trading": False,
        }
    )
    from app.alpaca.iex_stream import overlay_snapshot

    return overlay_snapshot(payload)


def _facts_only(payload: Dict[str, Any]) -> Dict[str, Any]:
    tech = payload.get("technicals") or {}
    return {
        "symbol": payload.get("symbol"),
        "price": payload.get("price"),
        "bid": payload.get("bid"),
        "ask": payload.get("ask"),
        "spread": payload.get("spread"),
        "volume": payload.get("volume"),
        "session": payload.get("session"),
        "freshness": payload.get("freshness"),
        "company": payload.get("company"),
        "previous_close": payload.get("previous_close"),
        "day_change": payload.get("day_change"),
        "day_change_pct": payload.get("day_change_pct"),
        "sma_20": tech.get("sma_20"),
        "ema_12": tech.get("ema_12"),
        "rsi_14": tech.get("rsi_14"),
        "macd": tech.get("macd"),
        "vwap_last_bar": tech.get("vwap_last_bar"),
        "realized_vol_ann": tech.get("realized_vol_ann"),
        "trend": tech.get("trend"),
        "options_count": payload.get("options_count"),
        "unavailable_without_source": payload.get("unavailable_without_source"),
    }


def _template_sections(facts: Dict[str, Any], question: str) -> Dict[str, str]:
    missing = [k for k, v in facts.items() if _unavailable(v) and k != "unavailable_without_source"]
    snap = (
        f"{facts.get('symbol')} price={facts.get('price')} bid={facts.get('bid')} ask={facts.get('ask')} "
        f"session={facts.get('session')} freshness={facts.get('freshness')}"
    )
    return {
        "market_snapshot": snap,
        "bull_case": "No bullish thesis is asserted. Only listed quotes/bars are facts. News is DATA_UNAVAILABLE.",
        "bear_case": "No bearish thesis is asserted. Missing news/fundamentals remain DATA_UNAVAILABLE.",
        "key_risks": "Stale or missing data fails closed. Options/Greeks may be DATA_UNAVAILABLE. LLM does not recommend trades.",
        "technical_observations": str(facts.get("trend") or DATA_UNAVAILABLE),
        "options_observations": (
            f"Option contracts returned: {facts.get('options_count')}. "
            "IV/Greeks only where the options snapshot provided them."
        ),
        "what_to_watch": "Watch quote freshness, session state, and RiskGuardian — not unverified headlines.",
        "educational_explanation": (
            f"Question: {question}. This is educational commentary from available facts only. "
            f"Missing fields: {', '.join(missing) if missing else 'none in the compact fact set'}. "
            "Not a buy or sell instruction."
        ),
    }


@router.get("/analytics/{symbol}")
async def get_stock_analytics(symbol: str) -> dict:
    return await _analytics_payload(symbol)


@router.post("/analytics/{symbol}/analyze")
async def analyze_stock(symbol: str, body: StockAskRequest) -> dict:
    payload = await _analytics_payload(symbol.upper())
    facts = _facts_only(payload)
    sections = _template_sections(facts, body.question)
    llm = get_llm_service()
    llm_status = LLM_UNAVAILABLE
    if llm.available:
        advisory = await llm.advise(
            role="educational_stock_analyst",
            facts={
                "question": body.question,
                "facts": facts,
                "rules": [
                    "Advisory/educational only",
                    "Do not tell the user to buy or sell",
                    "Do not invent news, fundamentals, Greeks, or prices",
                    "If a field is missing, say DATA_UNAVAILABLE",
                ],
            },
        )
        llm_status = advisory.status
        if advisory.status == "AVAILABLE" and advisory.summary:
            sections["educational_explanation"] = advisory.summary
            if advisory.points:
                sections["what_to_watch"] = " ".join(str(p) for p in advisory.points[:6])
    autonomous_engine.audit_logger.log_event(
        AuditEventType.MARKET_SCAN,
        AuditSeverity.INFO,
        symbol.upper(),
        f"Stock analysis for {symbol.upper()}",
        {"dry_run": True, "question": body.question[:200], "llm_status": llm_status},
    )
    return {
        "symbol": symbol.upper(),
        "question": body.question,
        "advisory_only": True,
        "can_execute": False,
        "llm_status": llm_status,
        "sections": sections,
        "facts_used": facts,
        "unavailable_without_source": payload.get("unavailable_without_source"),
    }


@router.post("/simulate/equity")
async def simulate_equity(body: EquityOrderRequest) -> dict:
    result = await simulate_equity_order(autonomous_engine, body.model_dump())
    if result.get("status") == "rejected" and not result.get("ok"):
        return result
    return result


@router.get("/simulate/equity")
async def list_simulated_equity() -> dict:
    fills = list(getattr(autonomous_engine, "simulated_equity_fills", []))
    return {
        "simulated": True,
        "real_paper_order": False,
        "live_trading": False,
        "fills": fills,
        "positions": positions_from_fills(fills),
        "label": "SIMULATED PAPER TRADE overlay — not Alpaca account positions",
    }
