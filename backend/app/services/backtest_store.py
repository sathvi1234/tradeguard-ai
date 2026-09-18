"""Persist backtest HISTORICAL SIMULATION results via the existing SQLAlchemy session."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.models import BacktestRun
from app.db.session import SessionLocal, ensure_schema, get_engine
from app.services.backtest_engine import RESULT_KIND


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_backtest_run(result: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema(get_engine())
    run_id = str(uuid.uuid4())
    created = _now_iso()
    stored = dict(result)
    stored["id"] = run_id
    stored["created_at"] = created
    stored["result_kind"] = RESULT_KIND
    stored["live_returns"] = False
    stored["live_trading"] = False
    row = BacktestRun(
        id=run_id,
        strategy=str(result.get("strategy") or ""),
        symbol=str(result.get("symbol") or ""),
        start_date=str(result.get("start") or result.get("start_date") or ""),
        end_date=str(result.get("end") or result.get("end_date") or ""),
        initial_capital=float(result.get("initial_capital") or 0),
        position_size=float(result.get("position_size") or 0),
        created_at=created,
        result_kind=RESULT_KIND,
        payload=json.dumps(stored, default=str),
    )
    session = SessionLocal()
    try:
        session.add(row)
        session.commit()
    finally:
        session.close()
    return stored


def get_backtest_run(run_id: str) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        row = session.get(BacktestRun, run_id)
        if row is None:
            return None
        return json.loads(row.payload)
    finally:
        session.close()


def list_backtest_runs(limit: int = 25) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = (
            session.query(BacktestRun)
            .order_by(BacktestRun.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.payload)
            metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
            out.append(
                {
                    "id": row.id,
                    "strategy": row.strategy,
                    "symbol": row.symbol,
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "initial_capital": row.initial_capital,
                    "position_size": row.position_size,
                    "created_at": row.created_at,
                    "result_kind": RESULT_KIND,
                    "live_returns": False,
                    "total_return": metrics.get("total_return"),
                    "number_of_trades": metrics.get("number_of_trades"),
                }
            )
        return out
    finally:
        session.close()
