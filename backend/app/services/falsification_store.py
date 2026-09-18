"""Persist research-only falsification reports."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.models import FalsificationReport
from app.db.session import SessionLocal, ensure_schema, get_engine
from app.services.falsification_engine import RESULT_KIND


def save_falsification_report(result: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema(get_engine())
    run_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    stored = dict(result)
    stored["id"] = run_id
    stored["created_at"] = created
    stored["result_kind"] = RESULT_KIND
    stored["live_trading"] = False
    stored["live_returns"] = False
    stored["proven_profitable"] = False
    stored["risk_guardian_overridden"] = False
    row = FalsificationReport(
        id=run_id,
        strategy=str(result.get("strategy") or ""),
        symbol=str(result.get("symbol") or ""),
        start_date=str(result.get("start_date") or ""),
        end_date=str(result.get("end_date") or ""),
        overall_state=str(result.get("overall_state") or "INCONCLUSIVE"),
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


def get_falsification_report(report_id: str) -> Optional[Dict[str, Any]]:
    session = SessionLocal()
    try:
        row = session.get(FalsificationReport, report_id)
        if row is None:
            return None
        return json.loads(row.payload)
    finally:
        session.close()


def list_falsification_reports(limit: int = 25) -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = (
            session.query(FalsificationReport)
            .order_by(FalsificationReport.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row.payload)
            summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
            out.append(
                {
                    "id": row.id,
                    "strategy": row.strategy,
                    "symbol": row.symbol,
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "overall_state": row.overall_state,
                    "created_at": row.created_at,
                    "result_kind": RESULT_KIND,
                    "live_returns": False,
                    "proven_profitable": False,
                    "summary": summary,
                }
            )
        return out
    finally:
        session.close()
