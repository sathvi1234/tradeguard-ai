"""Advisory volatility forecast APIs. Never approve trades."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.autonomous import autonomous_engine
from app.config import settings
from app.models.schemas import DATA_UNAVAILABLE
from app.services.vol_forecast import RESULT_KIND, forecast_volatility
from app.services.vol_forecast_store import (
    get_volatility_forecast,
    list_volatility_forecasts,
    save_volatility_forecast,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/volatility", tags=["volatility"])


class VolatilityForecastRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    start_date: str
    end_date: str


def _median_iv(snapshots: Dict[str, Any]) -> Any:
    values: List[float] = []
    for snap in snapshots.values():
        iv = getattr(snap, "implied_volatility", None)
        if isinstance(iv, (int, float)) and iv > 0:
            values.append(float(iv))
    if not values:
        return DATA_UNAVAILABLE
    values.sort()
    return values[len(values) // 2]


async def _bars_or_empty(alpaca, symbol: str, start: str, end: str):
    try:
        return await alpaca.get_bars_range(symbol, start=start, end=end) or []
    except Exception:
        return []


@router.get("/features")
async def feature_status() -> dict:
    return {
        "result_kind": RESULT_KIND,
        "advisory_only": True,
        "can_approve_trades": False,
        "overrides_risk_guardian": False,
        "live_trading": False,
        "notes": (
            "Historical prices and volume come from Alpaca bars. "
            "VIX is used only if a VIX/VIXY bar series is returned. "
            "VIX term structure requires a second tenor series. "
            "Implied volatility is a latest option snapshot only — not a historical IV tape — "
            "so it is not injected into training rows."
        ),
        "training_features_when_present": [
            "historical_prices",
            "rolling_returns",
            "rolling_volatility",
            "historical_volatility",
            "volume",
            "vix",
            "vix_term_structure",
            "implied_volatility",
            "iv_versus_realized_volatility",
        ],
    }


@router.get("/forecasts")
async def list_forecasts(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {
        "forecasts": list_volatility_forecasts(limit=limit),
        "result_kind": RESULT_KIND,
        "advisory_only": True,
        "live_trading": False,
    }


@router.get("/forecasts/{forecast_id}")
async def get_forecast(forecast_id: str) -> dict:
    payload = get_volatility_forecast(forecast_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Volatility forecast not found")
    payload["can_approve_trades"] = False
    payload["overrides_risk_guardian"] = False
    payload["live_trading"] = False
    return payload


@router.post("/forecast")
async def run_forecast(request: VolatilityForecastRequest) -> dict:
    symbol = request.symbol.strip().upper()
    start = f"{request.start_date}T00:00:00Z"
    end = f"{request.end_date}T23:59:59Z"
    alpaca = autonomous_engine.alpaca_service
    bars = await _bars_or_empty(alpaca, symbol, start, end)
    vix_bars = await _bars_or_empty(alpaca, "VIX", start, end)
    if not vix_bars:
        vix_bars = await _bars_or_empty(alpaca, "I:VIX", start, end)
    if not vix_bars:
        vix_bars = await _bars_or_empty(alpaca, "VIXY", start, end)
    vix_long = await _bars_or_empty(alpaca, "VIX3M", start, end)
    if not vix_long:
        vix_long = None
    current_iv: Any = DATA_UNAVAILABLE
    try:
        snaps = await alpaca.get_option_snapshots(symbol)
        current_iv = _median_iv(snaps or {})
    except Exception:
        current_iv = DATA_UNAVAILABLE
    result = forecast_volatility(
        bars,
        symbol=symbol,
        vix_bars=vix_bars or None,
        vix_long_bars=vix_long,
        iv_by_date=None,
        current_iv=current_iv,
    )
    result["start_date"] = request.start_date
    result["end_date"] = request.end_date
    result["dry_run"] = settings.dry_run
    result["live_trading"] = False
    result["can_approve_trades"] = False
    result["overrides_risk_guardian"] = False
    result["advisory_only"] = True
    if not result.get("ok"):
        return result
    stored = save_volatility_forecast(result)
    logger.info("Stored advisory volatility forecast %s for %s", stored.get("id"), symbol)
    return stored
