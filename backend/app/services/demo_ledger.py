"""Persistent Demo User virtual ledger. Never submits Alpaca orders."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import DemoAccount, DemoPosition, DemoTrade
from app.db.session import STARTING_CASH, ensure_schema, get_engine, sqlite_url
from app.models.enums import TradingMode
from app.models.schemas import DATA_UNAVAILABLE
from app.risk.risk_bodyguard import RiskBodyguard
from app.trading.audit_logger import AuditEventType, AuditSeverity

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class DemoLedger:
    """SQLAlchemy-backed virtual cash, positions, and DEMO_SIMULATED fills."""

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is not None:
            self.engine = get_engine(sqlite_url(Path(path)))
            ensure_schema(self.engine)
            self._factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)
        else:
            from app.db.session import init_db, SessionLocal

            init_db()
            self.engine = get_engine()
            self._factory = SessionLocal

    def _session(self) -> Session:
        return self._factory()

    def reset(self) -> None:
        with _LOCK, self._session() as session:
            session.query(DemoPosition).delete()
            session.query(DemoTrade).delete()
            account = session.get(DemoAccount, 1)
            if account is None:
                session.add(DemoAccount(id=1, cash=STARTING_CASH, realized_pnl=0, starting_cash=STARTING_CASH))
            else:
                account.cash = STARTING_CASH
                account.realized_pnl = 0
                account.starting_cash = STARTING_CASH
            session.commit()

    def account_row(self) -> Dict[str, float]:
        with self._session() as session:
            row = session.get(DemoAccount, 1)
            if row is None:
                return {"cash": STARTING_CASH, "realized_pnl": 0.0, "starting_cash": STARTING_CASH}
            return {
                "cash": float(row.cash),
                "realized_pnl": float(row.realized_pnl),
                "starting_cash": float(row.starting_cash),
            }

    def list_trades(self) -> List[Dict[str, Any]]:
        with self._session() as session:
            rows = session.query(DemoTrade).all()
        trades = [json.loads(row.payload) for row in rows]
        trades.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return trades

    def list_raw_positions(self) -> List[Dict[str, Any]]:
        with self._session() as session:
            rows = session.query(DemoPosition).filter(DemoPosition.quantity > 0).all()
        return [
            {
                "symbol": row.symbol,
                "quantity": int(row.quantity),
                "avg_entry": float(row.avg_entry),
                "company": row.company,
            }
            for row in rows
        ]

    def position_qty(self, symbol: str) -> int:
        with self._session() as session:
            row = session.get(DemoPosition, symbol.upper())
            return int(row.quantity) if row else 0

    def marked_positions(self, quotes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in self.list_raw_positions():
            symbol = str(row["symbol"]).upper()
            qty = int(row["quantity"])
            avg = float(row["avg_entry"])
            quote = quotes.get(symbol) or {}
            current = _opt_float(quote.get("price") or quote.get("current_price") or quote.get("last_trade_price"))
            market_value = round(current * qty, 2) if current is not None else DATA_UNAVAILABLE
            pnl = round((current - avg) * qty, 2) if current is not None else DATA_UNAVAILABLE
            pnl_pct = round((current - avg) / avg, 6) if current is not None and avg else DATA_UNAVAILABLE
            out.append(
                {
                    "symbol": symbol,
                    "company": row.get("company") or DATA_UNAVAILABLE,
                    "quantity": qty,
                    "side": "long",
                    "type": "EQUITY",
                    "avg_entry": round(avg, 4),
                    "avg_entry_price": round(avg, 4),
                    "current_price": current if current is not None else DATA_UNAVAILABLE,
                    "market_value": market_value,
                    "unrealized_pnl": pnl,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "simulated": True,
                    "trade_type": "DEMO_SIMULATED",
                    "label": "DEMO_SIMULATED",
                    "source": "DEMO_LEDGER",
                    "live_trading": False,
                    "real_paper_order": False,
                }
            )
        return out

    def portfolio_snapshot(self, quotes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        account = self.account_row()
        positions = self.marked_positions(quotes)
        market_value = 0.0
        unrealized = 0.0
        largest = 0.0
        for row in positions:
            mv = row.get("market_value")
            if isinstance(mv, (int, float)):
                market_value += mv
                largest = max(largest, mv)
            pnl = row.get("unrealized_pnl")
            if isinstance(pnl, (int, float)):
                unrealized += pnl
        cash = account["cash"]
        equity = round(cash + market_value, 2)
        starting = account["starting_cash"]
        peak = max(starting, equity)
        drawdown = (peak - equity) / peak if peak else 0.0
        exposure = market_value / equity if equity else 0.0
        concentration = largest / equity if equity else 0.0
        return {
            "account_value": equity,
            "equity": equity,
            "cash": round(cash, 2),
            "buying_power": round(cash, 2),
            "portfolio_value": equity,
            "positions_count": len(positions),
            "position_exposure": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(account["realized_pnl"], 2),
            "total_pnl": round(account["realized_pnl"] + unrealized, 2),
            "daily_pnl": round(unrealized, 2),
            "drawdown_pct": drawdown,
            "peak_equity": peak,
            "current_equity": equity,
            "exposure": exposure,
            "exposure_pct": exposure,
            "concentration": concentration,
            "starting_cash": starting,
            "positions": positions,
            "source": "DEMO_LEDGER",
            "trade_type": "DEMO_SIMULATED",
            "live_trading": False,
            "paper_trading": True,
            "dry_run": True,
            "label": "DEMO USER VIRTUAL ACCOUNT",
            "demo_portfolio": True,
            "virtual_money": True,
        }

    def apply_fill(self, fill: Dict[str, Any]) -> None:
        symbol = str(fill["symbol"]).upper()
        qty = int(fill["quantity"])
        price = float(fill["price"])
        side = str(fill["side"]).lower()
        notional = round(price * qty, 2)
        with _LOCK, self._session() as session:
            acc = session.get(DemoAccount, 1)
            if acc is None:
                acc = DemoAccount(id=1, cash=STARTING_CASH, realized_pnl=0, starting_cash=STARTING_CASH)
                session.add(acc)
                session.flush()
            cash = float(acc.cash)
            realized = float(acc.realized_pnl)
            pos = session.get(DemoPosition, symbol)
            held = int(pos.quantity) if pos else 0
            avg = float(pos.avg_entry) if pos else 0.0
            if side == "buy":
                cash -= notional
                new_qty = held + qty
                new_avg = ((avg * held) + notional) / new_qty if new_qty else price
                if pos is None:
                    session.add(
                        DemoPosition(
                            symbol=symbol,
                            quantity=new_qty,
                            avg_entry=new_avg,
                            company=fill.get("company"),
                        )
                    )
                else:
                    pos.quantity = new_qty
                    pos.avg_entry = new_avg
                    if fill.get("company"):
                        pos.company = fill.get("company")
            else:
                cash += notional
                realized += (price - avg) * qty
                new_qty = held - qty
                if pos is not None:
                    if new_qty <= 0:
                        session.delete(pos)
                    else:
                        pos.quantity = new_qty
            acc.cash = round(cash, 2)
            acc.realized_pnl = round(realized, 2)
            session.add(DemoTrade(trade_id=str(fill["trade_id"]), payload=json.dumps(fill)))
            session.commit()


_ledger: Optional[DemoLedger] = None


def get_demo_ledger() -> DemoLedger:
    global _ledger
    if _ledger is None:
        _ledger = DemoLedger()
    return _ledger


async def _quote_map(engine: Any, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    from app.alpaca.iex_stream import get_iex_hub, overlay_snapshot

    hub = get_iex_hub()

    async def one(symbol: str) -> None:
        streamed = hub.quotes.get(symbol.upper())
        if isinstance(streamed, dict) and isinstance(streamed.get("price") or streamed.get("last_trade_price"), (int, float)):
            out[symbol] = overlay_snapshot({"symbol": symbol, **streamed})
            return
        try:
            snap = await asyncio.wait_for(engine.alpaca_service.snapshot_symbol(symbol), timeout=3)
            out[symbol] = overlay_snapshot(snap)
        except Exception:
            if isinstance(streamed, dict):
                out[symbol] = overlay_snapshot({"symbol": symbol, **streamed})

    await asyncio.gather(*(one(symbol) for symbol in symbols))
    return out


async def demo_portfolio(engine: Any) -> Dict[str, Any]:
    ledger = get_demo_ledger()
    symbols = [row["symbol"] for row in ledger.list_raw_positions()]
    quotes = await _quote_map(engine, symbols)
    return ledger.portfolio_snapshot(quotes)


async def submit_demo_equity_order(engine: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(payload.get("side") or "").strip().lower()
    quantity = int(payload.get("quantity") or 0)
    preview_only = bool(payload.get("preview_only"))
    ledger = get_demo_ledger()

    blocked = {
        "ok": False,
        "submitted": False,
        "status": "rejected",
        "simulated": True,
        "trade_type": "DEMO_SIMULATED",
        "live_trading": False,
        "real_paper_order": False,
        "alpaca_order_submitted": False,
        "destination": None,
    }
    if settings.dry_run is False or not settings.alpaca_paper_trade:
        return {**blocked, "reason": "REAL MONEY TRADING = OFF"}
    if not symbol or side not in ("buy", "sell") or quantity <= 0:
        return {**blocked, "reason": "Invalid symbol or quantity"}

    from app.alpaca.iex_stream import get_iex_hub, overlay_snapshot

    snap = overlay_snapshot(await engine.alpaca_service.snapshot_symbol(symbol))
    last = _opt_float(snap.get("price") or snap.get("last_trade_price"))
    session = str(snap.get("session") or DATA_UNAVAILABLE)
    freshness = str(snap.get("freshness") or DATA_UNAVAILABLE)
    preview = {
        "symbol": symbol,
        "company": snap.get("company") or DATA_UNAVAILABLE,
        "side": side.upper(),
        "quantity": quantity,
        "order_type": "DEMO",
        "estimated_price": last if last is not None else DATA_UNAVAILABLE,
        "estimated_notional": round(last * quantity, 2) if last is not None else DATA_UNAVAILABLE,
        "session": session,
        "freshness": freshness,
        "quote_freshness": freshness,
        "market_status": snap.get("market_status"),
        "quote_available": bool(snap.get("quote_available") or last is not None),
        "simulation_eligible": bool(snap.get("simulation_eligible")),
        "simulation_reason": snap.get("simulation_reason"),
        "label": "DEMO ORDER",
        "trade_type": "DEMO_SIMULATED",
        "live_trading": False,
        "note": "Virtual money · simulation only. No real-money order will be placed.",
    }
    if preview_only:
        return {"ok": True, "status": "preview", "submitted": False, "preview": preview, "simulated": True}

    if last is None or last <= 0:
        reason = (
            "No fresh extended-hours quote is currently available."
            if session in ("PRE-MARKET", "AFTER-HOURS", "OVERNIGHT", "CLOSED")
            else "WAITING FOR REQUIRED MARKET DATA: price"
        )
        return {**blocked, "reason": reason, "preview": preview, "code": "NO_QUOTE"}

    account = ledger.account_row()
    notional = round(float(last) * quantity, 2)
    if side == "buy" and account["cash"] < notional:
        return {**blocked, "reason": "INSUFFICIENT VIRTUAL CASH", "preview": preview, "code": "INSUFFICIENT_CASH"}
    held = ledger.position_qty(symbol)
    if side == "sell" and quantity > held:
        return {
            **blocked,
            "reason": f"SELL BLOCKED — POSITION IS {held} SHARE(S). Short selling is not enabled.",
            "preview": preview,
            "code": "INSUFFICIENT_POSITION",
        }

    quotes = await _quote_map(engine, [row["symbol"] for row in ledger.list_raw_positions()] + [symbol])
    port = ledger.portfolio_snapshot(quotes)
    if engine.drawdown_guardian.state is None:
        engine.drawdown_guardian.initialize(float(port["equity"]))
    dd_state = engine.drawdown_guardian.state
    mode = dd_state.current_mode if dd_state else TradingMode.NORMAL
    drawdown = dd_state.drawdown_percentage if dd_state else 0.0
    if side == "buy" and mode == TradingMode.CRITICAL:
        return {**blocked, "reason": "BUY BLOCKED — DRAWDOWN GUARDIAN CRITICAL", "preview": preview, "code": "CRITICAL"}

    bodyguard = RiskBodyguard().assess([], trading_mode=mode, drawdown=drawdown, volatility_unavailable=False)
    if side == "buy" and bodyguard.freeze_new_trades:
        return {
            **blocked,
            "reason": "BUY BLOCKED — RISK BODYGUARD: " + "; ".join(bodyguard.reasons),
            "preview": preview,
            "code": "RISK_BODYGUARD",
        }

    hub_state = get_iex_hub().state
    fresh_ok = freshness in ("FRESH", "LIVE") or hub_state == "LIVE"
    extended = session in ("PRE-MARKET", "AFTER-HOURS", "OVERNIGHT", "CLOSED")
    if extended and not fresh_ok:
        return {
            **blocked,
            "reason": "Fresh market data required for simulation.",
            "preview": preview,
            "code": "NO_FRESH_EXTENDED_QUOTE",
            "market_status": snap.get("market_status"),
            "session": session,
            "freshness": freshness,
        }

    ts = datetime.now(timezone.utc)
    skip_age = session != "REGULAR" or hub_state == "LIVE"
    rg = await engine.risk_guardian.evaluate_trade(
        symbol=symbol,
        proposed_size=notional,
        portfolio_value=float(port["equity"]),
        current_equity=float(port["equity"]),
        current_drawdown=drawdown,
        current_positions=int(port["positions_count"]),
        max_loss=notional,
        potential_reward=notional,
        ai_confidence=1.0,
        contract_validity={"is_liquid": True, "open_interest": 10_000, "instrument": "equity"},
        market_data_timestamp=ts.replace(tzinfo=None),
        trading_mode=mode,
        skip_quote_age=skip_age,
        data_integrity=snap.get("integrity") if isinstance(snap.get("integrity"), dict) else None,
        integrity_state=snap.get("integrity_state"),
    )
    if rg.decision.value != "approved":
        engine.audit_logger.log_event(
            AuditEventType.RISK_REJECTION,
            AuditSeverity.HIGH,
            symbol,
            "; ".join(rg.rejection_reasons),
            {"demo": True, "live_trading": False, "gate": "RiskGuardian"},
        )
        return {
            **blocked,
            "reason": "BUY BLOCKED — RISK GUARDIAN: " + "; ".join(rg.rejection_reasons),
            "preview": preview,
            "code": "RISK_GUARDIAN",
            "risk_guardian": rg.to_dict(),
        }

    from app.risk.review_pipeline import run_review_pipeline

    rg_kwargs = {
        "portfolio_value": float(port["equity"]),
        "current_equity": float(port["equity"]),
        "current_drawdown": drawdown,
        "current_positions": int(port["positions_count"]),
        "max_loss": notional,
        "potential_reward": notional,
        "ai_confidence": 1.0,
        "contract_validity": {"is_liquid": True, "open_interest": 10_000, "instrument": "equity"},
        "market_data_timestamp": ts.replace(tzinfo=None),
        "trading_mode": mode,
        "skip_quote_age": skip_age,
        "data_integrity": snap.get("integrity") if isinstance(snap.get("integrity"), dict) else None,
        "integrity_state": snap.get("integrity_state"),
    }
    pipeline = await run_review_pipeline(
        guardian=engine.risk_guardian,
        symbol=symbol,
        proposed_size=notional,
        rg_kwargs=rg_kwargs,
        first_result=rg,
        audit=engine.audit_logger,
        quantity=quantity,
        proposal={"symbol": symbol, "side": side, "quantity": quantity, "proposed_size": notional, "demo": True},
    )
    if not pipeline.get("allowed_to_execute"):
        final_rg = pipeline.get("final_risk_guardian") or rg.to_dict()
        return {
            **blocked,
            "reason": "BUY BLOCKED — FINAL RISK GUARDIAN after LLM review",
            "preview": preview,
            "code": "RISK_GUARDIAN",
            "risk_guardian": final_rg,
            "llm_review": pipeline.get("llm_review"),
            "review_pipeline": pipeline,
        }
    if isinstance(pipeline.get("applied_quantity"), int):
        quantity = int(pipeline["applied_quantity"])
        if quantity < 1:
            return {
                **blocked,
                "reason": "BUY BLOCKED — size reduced to zero by restricted LLM review; Risk Guardian is final",
                "preview": preview,
                "code": "RISK_GUARDIAN",
                "review_pipeline": pipeline,
            }
        notional = float(last) * quantity
        preview["quantity"] = quantity
        preview["notional"] = notional

    fill = {
        "trade_id": f"demo-{uuid4().hex[:16]}",
        "order_id": None,
        "alpaca_order_id": None,
        "symbol": symbol,
        "company": snap.get("company") or DATA_UNAVAILABLE,
        "side": side,
        "quantity": quantity,
        "filled_qty": quantity,
        "price": float(last),
        "filled_avg_price": float(last),
        "notional": notional,
        "total_value": notional,
        "status": "FILLED",
        "timestamp": _now(),
        "submitted_at": _now(),
        "filled_at": _now(),
        "order_type": "DEMO",
        "time_in_force": "day",
        "trade_type": "DEMO_SIMULATED",
        "label": "DEMO_SIMULATED",
        "source": "DEMO_LEDGER",
        "simulated": True,
        "real_paper_order": False,
        "live_trading": False,
        "dry_run": True,
        "session": session,
        "freshness": freshness,
        "feed": snap.get("feed") or "iex",
        "destination": None,
        "note": "DEMO SIMULATION. Virtual money only. Not submitted to Alpaca.",
    }
    fill["order_id"] = fill["trade_id"]
    ledger.apply_fill(fill)
    engine.audit_logger.log_event(
        AuditEventType.ORDER_FILLED,
        AuditSeverity.INFO,
        symbol,
        f"DEMO_SIMULATED {side.upper()} {quantity} {symbol} @ {last}",
        {"demo": True, "live_trading": False, "trade_id": fill["trade_id"], "alpaca_submitted": False},
    )
    updated = await demo_portfolio(engine)
    return {
        "ok": True,
        "submitted": False,
        "filled": True,
        "status": "FILLED",
        "simulated": True,
        "trade_type": "DEMO_SIMULATED",
        "live_trading": False,
        "real_paper_order": False,
        "alpaca_order_submitted": False,
        "destination": None,
        "order": fill,
        "fill": fill,
        "preview": preview,
        "portfolio": updated,
        "note": "Demo virtual fill using real Alpaca market data. No POST /v2/orders.",
        "risk_guardian": rg.to_dict(),
        "llm_review": pipeline.get("llm_review"),
        "final_risk_guardian": pipeline.get("final_risk_guardian"),
        "execution_decision": "DEMO_SIMULATED",
        "real_money_execution": "BLOCKED",
    }
