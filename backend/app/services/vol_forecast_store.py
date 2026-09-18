"""Persist advisory volatility forecasts."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.models import VolatilityForecast
from app.db.session import SessionLocal, ensure_schema, get_engine
from app.services.vol_forecast import RESULT_KIND


def save_volatility_forecast(result: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema(get_engine())
    run_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    stored = dict(result)
    stored["id"] = run_id
    stored["created_at"] = created
    stored["result_kind"] = RESULT_KIND
    stored["live_trading"] = False
    stored["can_approve_trades"] = False
    stored["overrides_risk_guardian"] = False
    row = VolatilityForecast(
        id=run_id,
        symbol=str(result.get("symbol") or ""),
        model_name=str(result.get("model_name") or "unavailable"),
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


def get_volatility_forecast(forecast_id: str) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        row = session.get(VolatilityForecast, forecast_id)
        if row is None:
            return None
        return json.loads(row.payload)
    finally:
        session.close()


def list_volatility_forecasts(limit: int = 25) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = (
            session.query(VolatilityForecast)
            .order_by(VolatilityForecast.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.payload)
            preds = payload.get("predictions") if isinstance(payload.get("predictions"), dict) else {}
            out.append(
                {
                    "id": row.id,
                    "symbol": row.symbol,
                    "model_name": row.model_name,
                    "created_at": row.created_at,
                    "result_kind": RESULT_KIND,
                    "vol_5d": preds.get("vol_5d"),
                    "vol_10d": preds.get("vol_10d"),
                    "advisory_only": True,
                    "live_trading": False,
                }
            )
        return out
    finally:
        session.close()
