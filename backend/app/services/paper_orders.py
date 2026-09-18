"""User-initiated Alpaca PAPER equity orders. Live trading remains blocked."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.alpaca.exceptions import AlpacaError, AlpacaLiveTradingBlocked
from app.config import LIVE_API_URL, PAPER_API_URL, settings
from app.models.enums import TradingMode
from app.models.market_data import FreshnessStatus
from app.models.schemas import DATA_UNAVAILABLE
from app.risk.risk_bodyguard import RiskBodyguard
from app.trading.audit_logger import AuditEventType, AuditSeverity


def _opt_float(value: Any) -> Optional[float]:
    if value is None or value == "" or value == DATA_UNAVAILABLE:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def map_alpaca_order(raw: Dict[str, Any]) -> Dict[str, Any]:
    filled_qty = _opt_float(raw.get("filled_qty")) or 0.0
    qty = _opt_float(raw.get("qty")) or filled_qty
    filled_avg = _opt_float(raw.get("filled_avg_price"))
    status = str(raw.get("status") or "").upper()
    total = round(filled_avg * filled_qty, 2) if filled_avg is not None and filled_qty else DATA_UNAVAILABLE
    return {
        "alpaca_order_id": raw.get("id"),
        "order_id": raw.get("id"),
        "trade_id": raw.get("id"),
        "client_order_id": raw.get("client_order_id"),
        "symbol": str(raw.get("symbol") or "").upper(),
        "side": str(raw.get("side") or "").lower(),
        "quantity": qty,
        "filled_qty": filled_qty,
        "price": filled_avg if filled_avg is not None else DATA_UNAVAILABLE,
        "filled_avg_price": filled_avg if filled_avg is not None else DATA_UNAVAILABLE,
        "total_value": total,
        "notional": total,
        "status": status or DATA_UNAVAILABLE,
        "order_type": raw.get("type"),
        "time_in_force": raw.get("time_in_force"),
        "submitted_at": raw.get("submitted_at"),
        "filled_at": raw.get("filled_at"),
        "timestamp": raw.get("filled_at") or raw.get("submitted_at"),
        "trade_type": "PAPER",
        "label": "PAPER",
        "source": "ALPACA_PAPER",
        "simulated": False,
        "real_paper_order": True,
        "paper_trading": True,
        "live_trading": False,
        "safety_mode": True,
        "extended_hours": raw.get("extended_hours"),
        "destination": PAPER_API_URL,
    }


def map_alpaca_position(raw: Dict[str, Any]) -> Dict[str, Any]:
    qty = _opt_float(raw.get("qty")) or 0.0
    avg = _opt_float(raw.get("avg_entry_price"))
    current = _opt_float(raw.get("current_price"))
    market_value = _opt_float(raw.get("market_value"))
    pnl = _opt_float(raw.get("unrealized_pl"))
    return {
        "symbol": str(raw.get("symbol") or "").upper(),
        "quantity": qty,
        "side": raw.get("side") or "long",
        "avg_entry": avg if avg is not None else DATA_UNAVAILABLE,
        "avg_entry_price": avg if avg is not None else DATA_UNAVAILABLE,
        "current_price": current if current is not None else DATA_UNAVAILABLE,
        "market_value": market_value if market_value is not None else DATA_UNAVAILABLE,
        "unrealized_pnl": pnl if pnl is not None else DATA_UNAVAILABLE,
        "pnl": pnl if pnl is not None else DATA_UNAVAILABLE,
        "type": "EQUITY",
        "simulated": False,
        "source": "ALPACA_PAPER",
        "label": "ALPACA PAPER ACCOUNT",
        "live_trading": False,
        "real_paper_order": True,
    }


def _blocked(code: str, reason: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {
        "ok": False,
        "submitted": False,
        "status": "rejected",
        "code": code,
        "reason": reason,
        "live_trading": False,
        "paper_trading": True,
        "real_paper_order": False,
        "destination": PAPER_API_URL,
    }
    if extra:
        payload.update(extra)
    return payload


async def list_paper_orders(engine: Any, limit: int = 100) -> List[Dict[str, Any]]:
    raw = await engine.alpaca_service.client.get_orders(status="all", limit=limit)
    rows = raw if isinstance(raw, list) else raw.get("orders") or []
    mapped = [map_alpaca_order(row) for row in rows if isinstance(row, dict)]
    seen = set()
    unique: List[Dict[str, Any]] = []
    for row in mapped:
        key = str(row.get("alpaca_order_id") or row.get("client_order_id") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(row)
    return unique


async def list_paper_positions(engine: Any) -> List[Dict[str, Any]]:
    raw = await engine.alpaca_service.client.get_positions()
    rows = raw if isinstance(raw, list) else []
    return [map_alpaca_position(row) for row in rows if isinstance(row, dict)]


async def refresh_paper_order(engine: Any, order_id: str) -> Dict[str, Any]:
    raw = await engine.alpaca_service.client.get_order(order_id)
    mapped = map_alpaca_order(raw if isinstance(raw, dict) else {})
    engine.order_tracker.update_order_status(
        mapped.get("client_order_id") or order_id,
        str(mapped.get("status") or "submitted").lower(),
        filled_quantity=int(mapped.get("filled_qty") or 0),
        filled_price=_opt_float(mapped.get("filled_avg_price")),
    )
    return mapped


async def submit_paper_equity_order(engine: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(payload.get("side") or "").strip().lower()
    quantity = int(payload.get("quantity") or 0)
    order_type = str(payload.get("order_type") or "market").strip().lower()
    preview_only = bool(payload.get("preview_only"))

    if settings.live_trading_blocked() and not settings.alpaca_paper_trade:
        return _blocked("LIVE_TRADING_BLOCKED", "BUY BLOCKED — LIVE TRADING DISABLED")
    if not settings.alpaca_paper_trade or not settings.is_paper_url():
        return _blocked("LIVE_TRADING_BLOCKED", "BUY BLOCKED — LIVE TRADING DISABLED")
    if settings.alpaca_base_url.rstrip("/").lower() == LIVE_API_URL:
        return _blocked("LIVE_TRADING_BLOCKED", "BUY BLOCKED — LIVE TRADING DISABLED")
    if not symbol or side not in ("buy", "sell") or quantity <= 0:
        return _blocked("INVALID_ORDER", "BUY BLOCKED — INVALID SYMBOL OR QUANTITY")
    if order_type not in ("market", "limit"):
        return _blocked("INVALID_ORDER", "Only market or extended-hours limit equity orders are supported for paper BUY/SELL")

    account = await engine.alpaca_service.get_account()
    if not account:
        return _blocked("ALPACA_OFFLINE", "BUY BLOCKED — ALPACA NOT AUTHENTICATED")

    quote = await engine.alpaca_service.get_latest_quote(symbol)
    trade = await engine.alpaca_service.get_latest_trade(symbol)
    clock = await engine.alpaca_service.get_market_clock()
    company = await engine.alpaca_service.get_company_name(symbol)
    last = trade.price if getattr(trade, "price", None) is not None else quote.last_trade_price
    if last is None and quote.bid and quote.ask:
        last = (quote.bid + quote.ask) / 2
    freshness = getattr(quote, "freshness", None)
    freshness_value = freshness.value if hasattr(freshness, "value") else str(freshness or DATA_UNAVAILABLE)
    session = getattr(clock, "session", None) or ("REGULAR" if clock.is_open else "CLOSED")

    from app.alpaca.iex_stream import get_iex_hub

    streamed = get_iex_hub().quotes.get(symbol) or {}
    if last is None and isinstance(streamed.get("price"), (int, float)):
        last = float(streamed["price"])
        freshness_value = "FRESH"
    if quote.bid is None and isinstance(streamed.get("bid"), (int, float)):
        quote.bid = float(streamed["bid"])
    if quote.ask is None and isinstance(streamed.get("ask"), (int, float)):
        quote.ask = float(streamed["ask"])

    preview = {
        "symbol": symbol,
        "company": company or DATA_UNAVAILABLE,
        "side": side.upper(),
        "quantity": quantity,
        "order_type": "MARKET",
        "time_in_force": "day",
        "estimated_price": last if last is not None else DATA_UNAVAILABLE,
        "estimated_notional": round(float(last) * quantity, 2) if isinstance(last, (int, float)) else DATA_UNAVAILABLE,
        "session": session,
        "freshness": freshness_value,
        "quote_freshness": freshness_value,
        "paper_trading": True,
        "live_trading": False,
        "destination": PAPER_API_URL,
        "label": "ALPACA PAPER ORDER",
    }
    if preview_only:
        return {"ok": True, "status": "preview", "submitted": False, "preview": preview}

    if last is None or not isinstance(last, (int, float)) or last <= 0:
        return _blocked("NO_QUOTE", "BUY BLOCKED — NO REAL QUOTE", {"preview": preview})
    if freshness in (FreshnessStatus.INVALID, FreshnessStatus.DATA_UNAVAILABLE) and not streamed:
        return _blocked("MARKET_DATA_STALE", "BUY BLOCKED — MARKET DATA STALE", {"preview": preview})
    if session == "REGULAR" and freshness_value == "STALE" and get_iex_hub().state != "LIVE":
        return _blocked("MARKET_DATA_STALE", "BUY BLOCKED — MARKET DATA STALE", {"preview": preview})
    if session in ("CLOSED", "OVERNIGHT"):
        return _blocked(
            "MARKET_CLOSED",
            "BUY BLOCKED — MARKET CLOSED. Alpaca does not accept this market order while the session is closed.",
            {"preview": preview},
        )

    notional = float(last) * quantity
    buying_power = float(account.get("buying_power") or 0)
    if side == "buy" and buying_power < notional:
        return _blocked(
            "INSUFFICIENT_BUYING_POWER",
            "BUY BLOCKED — INSUFFICIENT BUYING POWER",
            {"preview": preview, "buying_power": buying_power, "notional": round(notional, 2)},
        )

    alpaca_positions = await list_paper_positions(engine)
    held = 0.0
    for row in alpaca_positions:
        if row.get("symbol") == symbol:
            held += float(row.get("quantity") or 0)
    if side == "sell" and quantity > held:
        return _blocked(
            "INSUFFICIENT_POSITION",
            f"SELL BLOCKED — POSITION IS {int(held)} SHARE(S). Short selling is not enabled.",
            {"preview": preview},
        )

    if engine.drawdown_guardian.state is None:
        engine.drawdown_guardian.initialize(float(account.get("portfolio_value") or account.get("equity") or 0))
    dd_state = engine.drawdown_guardian.state
    mode = dd_state.current_mode if dd_state else TradingMode.NORMAL
    drawdown = dd_state.drawdown_percentage if dd_state else 0.0
    if mode == TradingMode.CRITICAL:
        return _blocked("CRITICAL", "BUY BLOCKED — DRAWDOWN GUARDIAN CRITICAL", {"preview": preview})

    bodyguard = RiskBodyguard().assess(
        engine.position_manager.get_open_positions(),
        trading_mode=mode,
        drawdown=drawdown,
        volatility_unavailable=True,
    )
    if bodyguard.freeze_new_trades:
        return _blocked(
            "RISK_BODYGUARD",
            "BUY BLOCKED — RISK BODYGUARD: " + ("; ".join(bodyguard.reasons) or "new trades frozen"),
            {"preview": preview, "gate": "RiskBodyguard"},
        )

    ts = quote.timestamp or trade.timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    skip_age = session in ("PRE-MARKET", "AFTER-HOURS") or get_iex_hub().state == "LIVE"
    rg = await engine.risk_guardian.evaluate_trade(
        symbol=symbol,
        proposed_size=notional,
        portfolio_value=float(account.get("portfolio_value") or account.get("equity") or notional),
        current_equity=float(account.get("equity") or account.get("portfolio_value") or notional),
        current_drawdown=drawdown,
        current_positions=len(alpaca_positions),
        max_loss=notional,
        potential_reward=notional,
        ai_confidence=1.0,
        contract_validity={"is_liquid": True, "open_interest": 10_000, "instrument": "equity"},
        market_data_timestamp=ts.replace(tzinfo=None),
        trading_mode=mode,
        skip_quote_age=skip_age,
    )
    if rg.decision.value != "approved":
        engine.audit_logger.log_event(
            AuditEventType.RISK_REJECTION,
            AuditSeverity.HIGH,
            symbol,
            "; ".join(rg.rejection_reasons),
            {"paper": True, "live_trading": False, "gate": "RiskGuardian"},
        )
        return _blocked(
            "RISK_GUARDIAN",
            "BUY BLOCKED — RISK GUARDIAN: " + "; ".join(rg.rejection_reasons),
            {"preview": preview, "gate": "RiskGuardian", "risk_guardian": rg.to_dict()},
        )

    from app.risk.review_pipeline import run_review_pipeline

    rg_kwargs = {
        "portfolio_value": float(account.get("portfolio_value") or account.get("equity") or notional),
        "current_equity": float(account.get("equity") or account.get("portfolio_value") or notional),
        "current_drawdown": drawdown,
        "current_positions": len(alpaca_positions),
        "max_loss": notional,
        "potential_reward": notional,
        "ai_confidence": 1.0,
        "contract_validity": {"is_liquid": True, "open_interest": 10_000, "instrument": "equity"},
        "market_data_timestamp": ts.replace(tzinfo=None),
        "trading_mode": mode,
        "skip_quote_age": skip_age,
    }
    pipeline = await run_review_pipeline(
        guardian=engine.risk_guardian,
        symbol=symbol,
        proposed_size=notional,
        rg_kwargs=rg_kwargs,
        first_result=rg,
        audit=engine.audit_logger,
        quantity=quantity,
        proposal={"symbol": symbol, "side": side, "quantity": quantity, "proposed_size": notional, "paper": True},
    )
    if not pipeline.get("allowed_to_execute"):
        return _blocked(
            "RISK_GUARDIAN",
            "BUY BLOCKED — FINAL RISK GUARDIAN after LLM review",
            {
                "preview": preview,
                "gate": "RiskGuardian",
                "risk_guardian": pipeline.get("final_risk_guardian"),
                "llm_review": pipeline.get("llm_review"),
            },
        )
    if isinstance(pipeline.get("applied_quantity"), int) and pipeline["applied_quantity"] != quantity:
        quantity = int(pipeline["applied_quantity"])
        if quantity < 1:
            return _blocked("RISK_GUARDIAN", "BUY BLOCKED — size reduced to zero", {"preview": preview, "review_pipeline": pipeline})

    client_order_id = f"tg-{uuid4().hex[:20]}"
    extended = session in ("PRE-MARKET", "AFTER-HOURS")
    if extended:
        limit = quote.ask if side == "buy" else quote.bid
        if not isinstance(limit, (int, float)) or limit <= 0:
            limit = last
        order_payload = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": side,
            "type": "limit",
            "time_in_force": "day",
            "limit_price": str(round(float(limit), 2)),
            "client_order_id": client_order_id,
            "extended_hours": True,
        }
        preview["order_type"] = "LIMIT"
        preview["extended_hours"] = True
        preview["limit_price"] = round(float(limit), 2)
    else:
        order_payload = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "client_order_id": client_order_id,
            "extended_hours": False,
        }
    try:
        submitted = await engine.alpaca_service.client.submit_paper_order(order_payload)
    except AlpacaLiveTradingBlocked:
        return _blocked("LIVE_TRADING_BLOCKED", "BUY BLOCKED — LIVE TRADING DISABLED", {"preview": preview})
    except AlpacaError as exc:
        engine.audit_logger.log_event(
            AuditEventType.ORDER_REJECTED,
            AuditSeverity.HIGH,
            symbol,
            str(exc),
            {"paper": True, "live_trading": False},
        )
        return _blocked("ALPACA_REJECTED", f"BUY BLOCKED — {exc}", {"preview": preview})

    mapped = map_alpaca_order(submitted if isinstance(submitted, dict) else {})
    mapped["company"] = company or DATA_UNAVAILABLE
    mapped["client_order_id"] = mapped.get("client_order_id") or client_order_id
    engine.order_tracker.track_order(
        mapped.get("client_order_id") or client_order_id,
        mapped.get("alpaca_order_id"),
        symbol,
        side,
        quantity,
        float(last),
    )
    if mapped.get("alpaca_order_id") and str(mapped.get("status") or "").upper() not in {
        "FILLED",
        "CANCELED",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    }:
        for _ in range(8):
            await asyncio.sleep(0.75)
            try:
                mapped = await refresh_paper_order(engine, str(mapped["alpaca_order_id"]))
                mapped["company"] = company or DATA_UNAVAILABLE
            except AlpacaError:
                break
            if str(mapped.get("status") or "").upper() in {
                "FILLED",
                "PARTIAL_FILL",
                "PARTIALLY_FILLED",
                "CANCELED",
                "CANCELLED",
                "REJECTED",
                "EXPIRED",
            }:
                break

    engine.audit_logger.log_event(
        AuditEventType.ORDER_FILLED if str(mapped.get("status") or "").upper() == "FILLED" else AuditEventType.ORDER_SUBMITTED,
        AuditSeverity.INFO,
        symbol,
        f"Alpaca paper {side.upper()} {quantity} {symbol} status={mapped.get('status')}",
        {
            "paper": True,
            "live_trading": False,
            "alpaca_order_id": mapped.get("alpaca_order_id"),
            "status": mapped.get("status"),
        },
    )
    return {
        "ok": True,
        "submitted": True,
        "status": mapped.get("status"),
        "order": mapped,
        "preview": preview,
        "live_trading": False,
        "paper_trading": True,
        "real_paper_order": True,
        "destination": PAPER_API_URL,
        "note": "Submitted to Alpaca paper trading. Not a live-money order.",
        "risk_guardian": rg.to_dict(),
    }
