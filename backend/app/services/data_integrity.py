"""Market Data Integrity Engine.

Validates Alpaca quotes before AI agents or trading logic consume them.
Never invents prices. Never treats MARKET_CLOSED as DATA_UNAVAILABLE.
Invalid or stale data fails closed. Risk Guardian remains the final authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.schemas import DATA_UNAVAILABLE
from app.services.market_snapshot import CLOSED_SESSIONS

LIVE_FRESH = "LIVE_FRESH"
MARKET_CLOSED = "MARKET_CLOSED"
DATA_STALE = "DATA_STALE"
DATA_WARNING = "DATA_WARNING"
DATA_INVALID = "DATA_INVALID"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
DATA_ERROR = "DATA_ERROR"

FAIL_CLOSED_STATES = {DATA_STALE, DATA_INVALID, DATA_UNAVAILABLE, DATA_ERROR}

FUTURE_SKEW_SECONDS = 5
MIN_BARS_WARNING = 5
EQUITY_SPREAD_WARNING = 0.05
EQUITY_SPREAD_INVALID = 0.25
JUMP_WARNING = 0.15
SPLIT_WARNING = 0.40
SPLIT_INVALID = 0.80
WEEKEND = {5, 6}

SEVERITY = {
    DATA_ERROR: 60,
    DATA_INVALID: 50,
    DATA_UNAVAILABLE: 40,
    DATA_STALE: 30,
    DATA_WARNING: 20,
    MARKET_CLOSED: 10,
    LIVE_FRESH: 0,
}


class IntegrityState(str, Enum):
    LIVE_FRESH = LIVE_FRESH
    MARKET_CLOSED = MARKET_CLOSED
    DATA_STALE = DATA_STALE
    DATA_WARNING = DATA_WARNING
    DATA_INVALID = DATA_INVALID
    DATA_UNAVAILABLE = DATA_UNAVAILABLE
    DATA_ERROR = DATA_ERROR


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None or value == "" or value == DATA_UNAVAILABLE:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _text(value: Any) -> str:
    if value is None or value == DATA_UNAVAILABLE:
        return ""
    return str(value).strip()


def _parse_time(value: Any) -> Optional[datetime]:
    if value is None or value == "" or value == DATA_UNAVAILABLE:
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(text)
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _session(item: Dict[str, Any]) -> str:
    session = str(item.get("session") or item.get("market_session") or "").upper().replace("_", "-")
    if session in ("PREMARKET",):
        session = "PRE-MARKET"
    if session in ("AFTERHOURS",):
        session = "AFTER-HOURS"
    return session


def _price(item: Dict[str, Any]) -> Optional[float]:
    for key in ("price", "last_trade_price", "current_price"):
        number = _finite(item.get(key))
        if number is not None:
            return number
    quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
    trade = item.get("trade") if isinstance(item.get("trade"), dict) else {}
    for blob in (quote, trade):
        for key in ("price", "last_trade_price"):
            number = _finite(blob.get(key))
            if number is not None:
                return number
    return None


def assess_market_data(
    item: Dict[str, Any],
    *,
    expected_symbol: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Run integrity checks. Does not mutate prices. Does not invent missing values."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    checks: List[Dict[str, Any]] = []
    flags: List[str] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})
        if status not in {LIVE_FRESH, MARKET_CLOSED}:
            flags.append(name)

    requested = (expected_symbol or _text(item.get("symbol"))).upper()
    listed = _text(item.get("symbol")).upper()
    quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
    trade = item.get("trade") if isinstance(item.get("trade"), dict) else {}
    nested_symbol = _text(quote.get("symbol") or trade.get("symbol")).upper()
    if requested and listed and listed != requested:
        add("symbol_match", DATA_INVALID, f"Snapshot symbol {listed} does not match requested {requested}.")
    elif requested and nested_symbol and nested_symbol != requested:
        add("symbol_match", DATA_INVALID, f"Quote symbol {nested_symbol} does not match requested {requested}.")
    else:
        add("symbol_match", LIVE_FRESH, "Symbol matches the requested ticker.")

    provider_error = _text(item.get("data_error") or quote.get("error") or trade.get("error"))
    if provider_error in {"rate_limited", "not_found"} or "error" in provider_error.lower():
        add("provider", DATA_ERROR, f"Market data error: {provider_error}.")
    elif provider_error:
        add("provider", DATA_ERROR, f"Market data error: {provider_error}.")
    else:
        add("provider", LIVE_FRESH, "No provider error reported.")

    session = _session(item)
    market_status = str(item.get("market_status") or "").upper()
    closed = market_status == "CLOSED" or session in CLOSED_SESSIONS
    if closed:
        add("session", MARKET_CLOSED, f"Session is {session or 'CLOSED'}. This is not a data outage.")
    else:
        add("session", LIVE_FRESH, f"Session is {session or 'UNKNOWN'}.")

    price = _price(item)
    bid = _finite(item.get("bid") if item.get("bid") != DATA_UNAVAILABLE else None)
    if bid is None:
        bid = _finite(quote.get("bid"))
    ask = _finite(item.get("ask") if item.get("ask") != DATA_UNAVAILABLE else None)
    if ask is None:
        ask = _finite(quote.get("ask"))

    missing: List[str] = []
    if price is None:
        missing.append("price")
    if bid is None:
        missing.append("bid")
    if ask is None:
        missing.append("ask")
    if price is None and not closed:
        add("missing_values", DATA_UNAVAILABLE, "Price is missing or null. Value is not invented.")
    elif price is None and closed:
        add("missing_values", MARKET_CLOSED, "No price while the session is closed. Not DATA_UNAVAILABLE.")
    elif bid is None or ask is None:
        add("missing_values", DATA_WARNING, "Optional bid/ask fields are missing. Last trade is not replaced with zero.")
    else:
        add("missing_values", LIVE_FRESH, "Required price is present.")

    if price is not None and price <= 0:
        add("price_sign", DATA_INVALID, "Price is zero or negative. Value is not replaced.")
    elif bid is not None and bid <= 0:
        add("price_sign", DATA_INVALID, "Bid is zero or negative. Value is not replaced.")
    elif ask is not None and ask <= 0:
        add("price_sign", DATA_INVALID, "Ask is zero or negative. Value is not replaced.")
    else:
        add("price_sign", LIVE_FRESH, "No zero or negative prices.")

    if bid is not None and ask is not None and bid > ask:
        add("bid_ask", DATA_INVALID, "Bid is greater than ask.")
    elif bid is not None and ask is not None:
        mid = (bid + ask) / 2
        spread_pct = (ask - bid) / mid if mid > 0 else None
        if spread_pct is not None and spread_pct > EQUITY_SPREAD_INVALID:
            add("bid_ask", DATA_INVALID, f"Bid-ask spread is abnormally large ({spread_pct:.1%}).")
        elif spread_pct is not None and spread_pct > EQUITY_SPREAD_WARNING:
            add("bid_ask", DATA_WARNING, f"Bid-ask spread is wide ({spread_pct:.1%}).")
        else:
            add("bid_ask", LIVE_FRESH, "Bid-ask relationship is valid.")
    else:
        add("bid_ask", LIVE_FRESH, "Bid/ask not both present; spread not invented.")

    ts = _parse_time(item.get("last_update") or item.get("timestamp") or quote.get("timestamp") or trade.get("timestamp"))
    if ts is None and (price is not None or bid is not None or ask is not None) and not closed:
        add("timestamp", DATA_INVALID, "Quote timestamp is missing or invalid.")
    elif ts is None and closed:
        add("timestamp", MARKET_CLOSED, "No quote timestamp while the session is closed.")
    elif ts is not None:
        age = (current - ts).total_seconds()
        if age < -FUTURE_SKEW_SECONDS:
            add("timestamp", DATA_INVALID, "Quote timestamp is in the future.")
        else:
            add("timestamp", LIVE_FRESH, "Quote timestamp is valid.")
        limit = settings.quote_max_age_seconds
        if age > limit:
            add("freshness", DATA_STALE, f"Quote is stale ({int(age)}s > {limit}s).")
        else:
            add("freshness", LIVE_FRESH, "Quote is within the freshness window.")
        if closed:
            weekday = ts.weekday()
            hour = ts.hour
            if session in CLOSED_SESSIONS and weekday < 5 and 13 <= hour <= 20 and session == "CLOSED":
                add("session_timestamp", DATA_WARNING, "Quote timestamp looks like a regular session while status is closed.")
            else:
                add("session_timestamp", MARKET_CLOSED, "Timestamp is consistent with a closed or extended session.")
        else:
            if ts.weekday() in WEEKEND:
                add("session_timestamp", DATA_WARNING, "Quote timestamp falls on a weekend while session is not CLOSED.")
            else:
                add("session_timestamp", LIVE_FRESH, "Timestamp aligns with the reported session.")
    else:
        add("freshness", DATA_UNAVAILABLE if not closed else MARKET_CLOSED, "No timestamp to evaluate freshness.")

    prev = _finite(item.get("previous_close"))
    if price is not None and prev is not None and prev > 0:
        jump = abs(price - prev) / prev
        if jump >= SPLIT_INVALID:
            add("corporate_action", DATA_INVALID, "Price jump vs previous close is extreme; possible unadjusted split.")
        elif jump >= SPLIT_WARNING:
            add("corporate_action", DATA_WARNING, "Price jump vs previous close may indicate a split or corporate action.")
        elif jump >= JUMP_WARNING:
            add("price_jump", DATA_WARNING, f"Abnormal price jump vs previous close ({jump:.1%}).")
        else:
            add("price_jump", LIVE_FRESH, "Price change vs previous close is within bounds.")
            add("corporate_action", LIVE_FRESH, "No split-sized discontinuity detected.")
    else:
        add("price_jump", LIVE_FRESH, "Previous close not available; jump not invented.")
        add("corporate_action", LIVE_FRESH, "Corporate-action check skipped without previous close.")

    bars = item.get("bars") if isinstance(item.get("bars"), list) else []
    bar_count = int(item.get("bar_count") or len(bars) or 0)
    if bar_count < MIN_BARS_WARNING:
        add("history", DATA_WARNING, f"Insufficient historical bars ({bar_count} < {MIN_BARS_WARNING}).")
    else:
        add("history", LIVE_FRESH, f"Historical bars present ({bar_count}).")

    seen: set[str] = set()
    dup = False
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        key = str(bar.get("timestamp") or "")
        if not key or key == DATA_UNAVAILABLE:
            continue
        if key in seen:
            dup = True
            break
        seen.add(key)
    quote_ts = _text(item.get("last_update") or quote.get("timestamp"))
    trade_ts = _text(trade.get("timestamp"))
    if quote_ts and trade_ts and quote_ts == trade_ts and len(bars) >= 2:
        pass
    if dup:
        add("duplicate_timestamps", DATA_WARNING, "Duplicate bar timestamps detected.")
    else:
        add("duplicate_timestamps", LIVE_FRESH, "No duplicate historical timestamps.")

    state = LIVE_FRESH
    for check in checks:
        status = check["status"]
        if SEVERITY.get(status, 0) > SEVERITY.get(state, 0):
            state = status

    if state == DATA_UNAVAILABLE and closed:
        state = MARKET_CLOSED

    fail_closed = state in FAIL_CLOSED_STATES
    report = {
        "integrity_state": state,
        "fail_closed": fail_closed,
        "usable_for_agents": not fail_closed,
        "usable_for_trading": not fail_closed,
        "checks": checks,
        "flags": sorted(set(flags)),
        "missing_fields": missing,
        "notes": _notes(state, closed, fail_closed),
        "risk_guardian_is_final_authority": True,
        "fabricated": False,
        "live_trading": False,
        "dry_run": True,
        "symbol": requested or listed,
    }
    return report


def _notes(state: str, closed: bool, fail_closed: bool) -> str:
    if state == MARKET_CLOSED:
        return "Market session is closed or extended. This is not DATA_UNAVAILABLE."
    if state == LIVE_FRESH:
        return "Quote passed integrity checks."
    if state == DATA_STALE:
        return "Quote is stale. Fail closed — agents and trading must not use this price."
    if state == DATA_INVALID:
        return "Quote failed integrity validation. Fail closed. Missing values are not replaced with zeros."
    if state == DATA_UNAVAILABLE:
        return "Required market data is missing. Fail closed. Values are not invented."
    if state == DATA_ERROR:
        return "Market data provider error. Fail closed."
    if state == DATA_WARNING:
        return "Quote is usable with warnings. Risk Guardian remains the final authority."
    if closed:
        return "Market session is closed or extended."
    if fail_closed:
        return "Integrity engine failed closed."
    return "Integrity evaluated."


def attach_integrity(item: Dict[str, Any], *, expected_symbol: Optional[str] = None) -> Dict[str, Any]:
    """Attach integrity report onto an existing snapshot dict. Does not invent prices."""
    if not isinstance(item, dict):
        return item
    report = assess_market_data(item, expected_symbol=expected_symbol or item.get("symbol"))
    item["integrity"] = report
    item["integrity_state"] = report["integrity_state"]
    item["integrity_fail_closed"] = report["fail_closed"]
    item["integrity_notes"] = report["notes"]
    return item


def fail_closed_for_agents(item: Optional[Dict[str, Any]]) -> bool:
    if not item:
        return True
    report = item.get("integrity") if isinstance(item.get("integrity"), dict) else None
    if report:
        return bool(report.get("fail_closed"))
    return False
