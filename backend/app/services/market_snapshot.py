"""Build real Alpaca snapshots for UI. Never invent prices, Greeks, or P&L."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

try:
    from zoneinfo import ZoneInfo

    ET: Optional[Any] = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - Windows without tzdata
    ET = None

from app.models.market_data import MarketClock, StockBar, StockQuote, StockTrade
from app.models.schemas import DATA_UNAVAILABLE

DEFAULT_WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "TSLA",
    "GOOGL",
    "META",
    "AMD",
    "SPY",
    "QQQ",
]
BARS_LOOKBACK_DAYS = 120
DATA_FEED = "iex"


def bars_start_iso(days: int = BARS_LOOKBACK_DAYS) -> str:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.date().isoformat()


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + 7 * (n - 1))


def _eastern_tz(ts: datetime):
    if ET is not None:
        return ET
    utc = ts.astimezone(timezone.utc)
    dst_start = _nth_weekday(utc.year, 3, 6, 2).replace(hour=7)  # 2nd Sunday March 02:00 EST
    dst_end = _nth_weekday(utc.year, 11, 6, 1).replace(hour=6)  # 1st Sunday November 02:00 EDT
    offset = timedelta(hours=-4) if dst_start <= utc < dst_end else timedelta(hours=-5)
    return timezone(offset)


def classify_session(clock: MarketClock) -> str:
    """Map Alpaca clock to a US equity session label. Display-only; not a trade gate."""
    if clock.availability == DATA_UNAVAILABLE and clock.is_open is None:
        return "UNKNOWN"
    ts = clock.timestamp
    if ts is None:
        if clock.is_open is True:
            return "REGULAR"
        if clock.is_open is False:
            return "CLOSED"
        return "UNKNOWN"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    local = ts.astimezone(_eastern_tz(ts))
    weekday = local.weekday()
    minutes = local.hour * 60 + local.minute
    if weekday >= 5:
        return "CLOSED"
    if clock.is_open is True:
        return "REGULAR"
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return "PRE-MARKET"
    if 16 * 60 <= minutes < 20 * 60:
        return "AFTER-HOURS"
    if minutes >= 20 * 60 or minutes < 4 * 60:
        return "OVERNIGHT"
    return "CLOSED"


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def bar_stats(bars: List[StockBar], last_price: Optional[float]) -> Dict[str, Any]:
    previous_close = DATA_UNAVAILABLE
    day_change = DATA_UNAVAILABLE
    day_change_pct = DATA_UNAVAILABLE
    volume = DATA_UNAVAILABLE
    if not bars:
        return {
            "previous_close": previous_close,
            "day_change": day_change,
            "day_change_pct": day_change_pct,
            "volume": volume,
            "bar_count": 0,
        }
    last_bar = bars[-1]
    if last_bar.volume is not None:
        volume = last_bar.volume
    prev = None
    if len(bars) >= 2 and bars[-2].close is not None:
        prev = bars[-2].close
    elif last_bar.open is not None:
        prev = last_bar.open
    price = last_price if last_price is not None else last_bar.close
    if prev is not None and prev > 0 and price is not None:
        previous_close = prev
        day_change = round(price - prev, 4)
        day_change_pct = round((price - prev) / prev, 6)
    elif prev is not None:
        previous_close = prev
    return {
        "previous_close": previous_close,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "volume": volume,
        "bar_count": len(bars),
    }


CLOSED_SESSIONS = {
    "CLOSED",
    "CLOSE",
    "OVERNIGHT",
    "PRE-MARKET",
    "PRE_MARKET",
    "PREMARKET",
    "AFTER-HOURS",
    "AFTER_HOURS",
    "AFTERHOURS",
}


def enrich_market_state(item: Dict[str, Any]) -> Dict[str, Any]:
    """Separate session, freshness, quote presence, and provider errors. Never collapse those into one DATA_UNAVAILABLE flag."""
    if not isinstance(item, dict):
        return item
    price = _finite(item.get("price"))
    if price is None:
        price = _finite(item.get("last_trade_price"))
    freshness = str(item.get("freshness") or item.get("data_freshness") or "").upper()
    session = str(item.get("session") or item.get("market_session") or "").upper().replace("_", "-")
    if session in ("PREMARKET",):
        session = "PRE-MARKET"
    if session in ("AFTERHOURS",):
        session = "AFTER-HOURS"
    if session in ("", "DATA_UNAVAILABLE"):
        if item.get("market_open") is True:
            session = "REGULAR"
        elif item.get("market_open") is False:
            session = "CLOSED"
        else:
            session = "UNKNOWN"
    nested_quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
    nested_trade = item.get("trade") if isinstance(item.get("trade"), dict) else {}
    quote_error = item.get("data_error") or nested_quote.get("error") or nested_trade.get("error")
    quote_available = price is not None and price > 0
    if freshness in ("", "DATA_UNAVAILABLE") and quote_available:
        freshness = "STALE"
    elif freshness in ("", "DATA_UNAVAILABLE") and quote_error:
        freshness = "UNKNOWN"
    elif freshness in ("", "DATA_UNAVAILABLE"):
        freshness = "UNKNOWN"
    if item.get("market_open") is True or session in {"REGULAR", "OPEN"}:
        market_status = "OPEN"
    elif item.get("market_open") is False or session in CLOSED_SESSIONS:
        market_status = "CLOSED"
    else:
        market_status = "UNKNOWN"
    live = bool(item.get("live")) or freshness in {"FRESH", "LIVE"} or item.get("ws_state") == "LIVE"
    if live and freshness == "STALE":
        freshness = "FRESH"
    simulation_eligible = bool(quote_available and (freshness in {"FRESH", "LIVE"} or item.get("ws_state") == "LIVE"))
    if quote_error:
        simulation_reason = "MARKET DATA ERROR"
    elif not quote_available:
        simulation_reason = "NO QUOTE AVAILABLE"
    elif not simulation_eligible and market_status == "CLOSED":
        simulation_reason = "WAITING FOR FRESH DATA"
    elif not simulation_eligible:
        simulation_reason = "DATA STALE — simulation requires a fresh quote."
    else:
        simulation_reason = "SIMULATION ELIGIBLE"
    item["price"] = price if price is not None else item.get("price")
    item["session"] = session
    item["market_session"] = session
    item["freshness"] = freshness
    item["data_freshness"] = freshness
    item["quote_available"] = quote_available
    item["market_status"] = market_status
    item["simulation_eligible"] = simulation_eligible
    item["simulation_reason"] = simulation_reason
    item["data_error"] = quote_error
    item["live"] = live
    item["live_market_data"] = bool(item.get("live_market_data") or live)
    from app.services.data_integrity import attach_integrity

    return attach_integrity(item)


def snapshot_from_parts(
    symbol: str,
    quote: StockQuote,
    trade: StockTrade,
    clock: MarketClock,
    bars: List[StockBar],
    company: Optional[str],
    *,
    feed: str = DATA_FEED,
) -> Dict[str, Any]:
    session = classify_session(clock)
    last = trade.price if trade.price is not None else quote.last_trade_price
    if last is None and quote.bid is not None and quote.ask is not None:
        last = (quote.bid + quote.ask) / 2
    stats = bar_stats(bars, last)
    spread = (
        round(quote.ask - quote.bid, 6)
        if quote.bid is not None and quote.ask is not None and quote.bid > 0 and quote.ask > 0
        else DATA_UNAVAILABLE
    )
    mid = (
        round((quote.bid + quote.ask) / 2, 6)
        if quote.bid is not None and quote.ask is not None and quote.bid > 0 and quote.ask > 0
        else DATA_UNAVAILABLE
    )
    spread_pct = (
        round((quote.ask - quote.bid) / ((quote.bid + quote.ask) / 2), 6)
        if isinstance(spread, float) and isinstance(mid, float) and mid > 0
        else DATA_UNAVAILABLE
    )
    freshness = quote.freshness.value if hasattr(quote.freshness, "value") else str(quote.freshness or DATA_UNAVAILABLE)
    updated = quote.timestamp or trade.timestamp
    live = freshness == "FRESH" and quote.availability != DATA_UNAVAILABLE
    payload = {
        "symbol": symbol.upper(),
        "company": company or DATA_UNAVAILABLE,
        "company_note": None
        if company
        else "Company name is not available from the Alpaca asset record for this symbol.",
        "price": last if last is not None else DATA_UNAVAILABLE,
        "bid": quote.bid if quote.bid is not None and quote.bid > 0 else DATA_UNAVAILABLE,
        "ask": quote.ask if quote.ask is not None and quote.ask > 0 else DATA_UNAVAILABLE,
        "mid": mid,
        "spread": spread,
        "spread_pct": spread_pct,
        "volume": stats["volume"],
        "previous_close": stats["previous_close"],
        "day_change": stats["day_change"],
        "day_change_pct": stats["day_change_pct"],
        "session": session,
        "market_open": clock.is_open,
        "freshness": freshness,
        "last_update": updated.isoformat() if updated else DATA_UNAVAILABLE,
        "source": "alpaca",
        "feed": feed,
        "live": live,
        "quote": quote.model_dump(mode="json"),
        "trade": trade.model_dump(mode="json"),
        "clock": clock.model_dump(mode="json"),
        "bars": [b.model_dump(mode="json") for b in bars],
        "bar_count": stats["bar_count"],
        "paper_trading": True,
        "live_trading": False,
        "live_market_data": live,
        "data_error": quote.error or trade.error or clock.error,
    }
    return enrich_market_state(payload)


def normalize_symbols(raw: Optional[str], fallback: Iterable[str] = DEFAULT_WATCHLIST) -> List[str]:
    if not raw:
        return [s.upper() for s in fallback]
    out: List[str] = []
    for part in raw.split(","):
        symbol = "".join(ch for ch in part.strip().upper() if ch.isalpha() or ch == ".")
        if 1 <= len(symbol) <= 8 and symbol not in out:
            out.append(symbol)
    return out[:20] if out else [s.upper() for s in fallback]
