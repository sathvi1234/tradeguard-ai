"""Educational equity DRY_RUN simulator. Never calls a live broker. RiskGuardian is final."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.config import settings
from app.models.enums import TradingMode
from app.models.market_data import FreshnessStatus
from app.models.schemas import DATA_UNAVAILABLE
from app.risk.risk_bodyguard import RiskBodyguard
from app.trading.audit_logger import AuditEventType, AuditSeverity


def net_simulated_qty(fills: List[Dict[str, Any]], symbol: str) -> int:
    total = 0
    for row in fills:
        if str(row.get("symbol", "")).upper() != symbol.upper():
            continue
        qty = int(row.get("quantity") or 0)
        if str(row.get("side", "")).lower() == "buy":
            total += qty
        else:
            total -= qty
    return total


def positions_from_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Net simulated longs from DRY_RUN fills. Not Alpaca paper positions."""
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for row in fills:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        qty = int(row.get("quantity") or 0)
        price = float(row.get("price") or 0)
        side = str(row.get("side") or "").lower()
        acc = by_symbol.setdefault(
            symbol,
            {"qty": 0, "cost": 0.0, "bought": 0, "last": price, "company": row.get("company"), "updated": row.get("timestamp")},
        )
        if side == "buy":
            acc["qty"] += qty
            acc["cost"] += price * qty
            acc["bought"] += qty
        elif side == "sell":
            acc["qty"] -= qty
        acc["last"] = price
        acc["updated"] = row.get("timestamp")
        if row.get("company"):
            acc["company"] = row.get("company")
    positions: List[Dict[str, Any]] = []
    for symbol, acc in by_symbol.items():
        qty = int(acc["qty"])
        if qty <= 0:
            continue
        avg = (acc["cost"] / acc["bought"]) if acc["bought"] else acc["last"]
        last = float(acc["last"] or avg)
        positions.append(
            {
                "symbol": symbol,
                "company": acc.get("company") or DATA_UNAVAILABLE,
                "quantity": qty,
                "side": "long",
                "avg_entry": round(avg, 4),
                "current_price": last,
                "unrealized_pnl": round((last - avg) * qty, 2),
                "notional": round(last * qty, 2),
                "timestamp": acc.get("updated"),
                "status": "simulated_open",
                "simulated": True,
                "source": "DRY_RUN_SIMULATED",
                "label": "SIMULATED PAPER TRADE overlay — not an Alpaca account position",
                "live_trading": False,
                "real_paper_order": False,
            }
        )
    return positions


async def simulate_equity_order(engine: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(payload.get("side") or "").strip().lower()
    order_type = str(payload.get("order_type") or "market").strip().lower()
    quantity = int(payload.get("quantity") or 0)
    limit_price = payload.get("limit_price")
    preview_only = bool(payload.get("preview_only"))

    if not symbol or side not in ("buy", "sell") or quantity <= 0:
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "real_paper_order": False,
            "live_trading": False,
            "reason": "Invalid symbol, side, or quantity",
        }
    if order_type not in ("market", "limit"):
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "reason": "Order type must be market or limit",
        }
    if order_type == "limit":
        try:
            limit_price = float(limit_price)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "status": "rejected",
                "simulated": True,
                "reason": "LIMIT orders require a numeric limit_price",
            }
        if limit_price <= 0:
            return {
                "ok": False,
                "status": "rejected",
                "simulated": True,
                "reason": "limit_price must be positive",
            }

    if settings.dry_run is False or not settings.alpaca_paper_trade or not settings.is_paper_url():
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "live_trading": False,
            "reason": "Live trading is blocked. DRY_RUN and paper trading are required.",
        }

    quote = await engine.alpaca_service.get_latest_quote(symbol)
    trade = await engine.alpaca_service.get_latest_trade(symbol)
    account = await engine.alpaca_service.get_account()
    freshness = getattr(quote, "freshness", None)
    freshness_value = freshness.value if hasattr(freshness, "value") else str(freshness or DATA_UNAVAILABLE)

    last = trade.price if getattr(trade, "price", None) is not None else None
    mid = None
    if quote.bid is not None and quote.ask is not None:
        mid = (quote.bid + quote.ask) / 2
    estimated = last or mid or quote.last_trade_price
    if order_type == "limit":
        estimated = float(limit_price)

    preview = {
        "symbol": symbol,
        "side": side.upper(),
        "quantity": quantity,
        "order_type": order_type.upper(),
        "estimated_price": estimated if estimated is not None else DATA_UNAVAILABLE,
        "estimated_notional": round(estimated * quantity, 2) if isinstance(estimated, (int, float)) else DATA_UNAVAILABLE,
        "paper_trading": True,
        "dry_run": True,
        "live_trading": False,
        "quote_freshness": freshness_value,
        "quote_usable": bool(getattr(quote, "usable", False)),
        "session": DATA_UNAVAILABLE,
        "label": "SIMULATED PAPER TRADE",
    }
    get_clock = getattr(engine.alpaca_service, "get_market_clock", None)
    if callable(get_clock):
        clock = await get_clock()
        is_open = getattr(clock, "is_open", None)
        if is_open is True:
            preview["session"] = "REGULAR"
        elif is_open is False:
            session = getattr(clock, "session", None)
            preview["session"] = session or "CLOSED"
    if preview_only:
        return {"ok": True, "status": "preview", "simulated": True, "preview": preview}

    if estimated is None or not isinstance(estimated, (int, float)) or estimated <= 0:
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "preview": preview,
            "reason": "DATA_UNAVAILABLE: no usable price for simulation. Fail closed.",
        }
    if freshness in (FreshnessStatus.STALE, FreshnessStatus.DATA_UNAVAILABLE, FreshnessStatus.INVALID) or not getattr(
        quote, "usable", False
    ):
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "preview": preview,
            "reason": f"Fail closed: quote freshness={freshness_value}. RiskGuardian requires fresh usable data.",
        }

    if engine.drawdown_guardian.state is None and account:
        engine.drawdown_guardian.initialize(float(account.get("portfolio_value") or account.get("equity") or 0))
    dd_state = engine.drawdown_guardian.state
    mode = dd_state.current_mode if dd_state else TradingMode.NORMAL
    drawdown = dd_state.drawdown_percentage if dd_state else 0.0
    portfolio_value = float((account or {}).get("portfolio_value") or (account or {}).get("equity") or 0)
    notional = float(estimated) * quantity

    bodyguard = RiskBodyguard().assess(
        engine.position_manager.get_open_positions(),
        trading_mode=mode,
        drawdown=drawdown,
        volatility_unavailable=True,
    )
    if bodyguard.freeze_new_trades:
        reason = "; ".join(bodyguard.reasons) or "RiskBodyguard freeze_new_trades"
        engine.audit_logger.log_event(
            AuditEventType.ORDER_REJECTED,
            AuditSeverity.HIGH,
            symbol,
            reason,
            {"dry_run": True, "simulated": True, "gate": "RiskBodyguard"},
        )
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "preview": preview,
            "gate": "RiskBodyguard",
            "reason": reason,
            "bodyguard": bodyguard.model_dump(),
        }

    fills: List[Dict[str, Any]] = getattr(engine, "simulated_equity_fills", [])
    sim_net = net_simulated_qty(fills, symbol)
    if side == "sell" and quantity > sim_net:
        reason = (
            "Insufficient simulated long quantity. This simulator does not send SELL to Alpaca "
            f"and will not reduce real paper positions. Simulated long={sim_net}."
        )
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "preview": preview,
            "reason": reason,
        }

    ts = quote.timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    rg = await engine.risk_guardian.evaluate_trade(
        symbol=symbol,
        proposed_size=notional,
        portfolio_value=portfolio_value or notional,
        current_equity=portfolio_value or notional,
        current_drawdown=drawdown,
        current_positions=len(engine.position_manager.get_open_positions()) + len(fills),
        max_loss=notional,
        potential_reward=notional,
        ai_confidence=1.0,
        contract_validity={"is_liquid": True, "open_interest": 10_000, "instrument": "equity"},
        market_data_timestamp=ts.replace(tzinfo=None) if ts.tzinfo else ts,
        trading_mode=mode,
    )
    if rg.decision.value != "approved":
        reason = "; ".join(rg.rejection_reasons) or "RiskGuardian rejected"
        engine.audit_logger.log_event(
            AuditEventType.RISK_REJECTION,
            AuditSeverity.HIGH,
            symbol,
            reason,
            {"dry_run": True, "simulated": True, "gate": "RiskGuardian", "limits_checked": rg.limits_checked},
        )
        return {
            "ok": False,
            "status": "rejected",
            "simulated": True,
            "preview": preview,
            "gate": "RiskGuardian",
            "reason": reason,
            "risk_guardian": rg.to_dict(),
            "note": "AI recommends. Deterministic Risk Guardian decides.",
        }

    fill = {
        "order_id": str(uuid4()),
        "trade_id": None,
        "symbol": symbol,
        "company": DATA_UNAVAILABLE,
        "side": side,
        "quantity": quantity,
        "price": float(estimated),
        "notional": round(notional, 2),
        "total_value": round(notional, 2),
        "status": "filled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulated": True,
        "label": "SIMULATED PAPER TRADE",
        "trade_type": "EQUITY_DRY_RUN",
        "execution_class": "DRY_RUN_SIMULATED",
        "source": "DRY_RUN_SIMULATED",
        "risk_status": rg.decision.value if hasattr(rg.decision, "value") else str(rg.decision),
        "real_paper_order": False,
        "live_trading": False,
        "dry_run": True,
        "alpaca_order_id": None,
        "risk_guardian": rg.to_dict(),
    }
    fill["trade_id"] = fill["order_id"]
    get_name = getattr(engine.alpaca_service, "get_company_name", None)
    if callable(get_name):
        try:
            name = await get_name(symbol)
            if name:
                fill["company"] = name
        except Exception:
            pass
    if not hasattr(engine, "simulated_equity_fills"):
        engine.simulated_equity_fills = []
    engine.simulated_equity_fills.append(fill)
    engine.audit_logger.log_event(
        AuditEventType.ORDER_FILLED,
        AuditSeverity.INFO,
        symbol,
        f"DRY_RUN simulated {side.upper()} {quantity} {symbol} @ {estimated} — not submitted to Alpaca",
        {"dry_run": True, "simulated": True, "order_id": fill["order_id"], "alpaca_order_id": None},
    )
    return {
        "ok": True,
        "status": "filled",
        "simulated": True,
        "real_paper_order": False,
        "live_trading": False,
        "preview": preview,
        "fill": fill,
        "note": "SIMULATED PAPER TRADE. DRY_RUN. Not a live trade. Not submitted to Alpaca.",
        "risk_guardian": rg.to_dict(),
    }
