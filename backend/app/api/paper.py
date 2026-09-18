"""Alpaca PAPER equity orders and public IEX market-data stream (no secrets)."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.alpaca.iex_stream import get_iex_hub
from app.api.autonomous import autonomous_engine
from app.config import PAPER_API_URL, settings
from app.services.market_snapshot import DEFAULT_WATCHLIST, normalize_symbols
from app.services.paper_orders import (
    list_paper_orders,
    list_paper_positions,
    refresh_paper_order,
    submit_paper_equity_order,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["paper"])


class PaperOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: int = Field(..., gt=0, le=1000)
    order_type: str = "market"
    preview_only: bool = False


@router.get("/stream/status")
async def stream_status() -> dict:
    status = get_iex_hub().status()
    status["live_trading"] = False
    status["paper_trading"] = True
    status["dry_run"] = settings.dry_run
    status["safety_mode"] = True
    return status


@router.websocket("/stream/market")
async def market_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = get_iex_hub()
    raw = websocket.query_params.get("symbols")
    symbols = normalize_symbols(raw, DEFAULT_WATCHLIST)
    await hub.add_client(websocket, symbols)
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            if str(message.get("action") or "").lower() == "subscribe":
                extra = message.get("symbols") or []
                if isinstance(extra, str):
                    extra = normalize_symbols(extra, [])
                elif isinstance(extra, list):
                    extra = [str(item) for item in extra]
                else:
                    extra = []
                if extra:
                    await hub.subscribe(extra)
    except WebSocketDisconnect:
        hub.remove_client(websocket)
    except Exception:
        hub.remove_client(websocket)


@router.post("/paper/orders")
async def submit_paper_order(body: PaperOrderRequest) -> dict:
    return await submit_paper_equity_order(autonomous_engine, body.model_dump())


@router.get("/paper/orders")
async def get_paper_orders(limit: int = Query(100, ge=1, le=500)) -> dict:
    orders = await list_paper_orders(autonomous_engine, limit=limit)
    return {
        "orders": orders,
        "count": len(orders),
        "source": "ALPACA_PAPER",
        "destination": PAPER_API_URL,
        "trade_type": "PAPER",
        "live_trading": False,
        "paper_trading": True,
        "dry_run": settings.dry_run,
    }


@router.get("/paper/orders/{order_id}")
async def get_paper_order(order_id: str) -> dict:
    mapped = await refresh_paper_order(autonomous_engine, order_id)
    return {
        "order": mapped,
        "source": "ALPACA_PAPER",
        "live_trading": False,
        "paper_trading": True,
    }


@router.get("/paper/positions")
async def get_paper_positions() -> dict:
    positions = await list_paper_positions(autonomous_engine)
    return {
        "positions": positions,
        "count": len(positions),
        "source": "ALPACA_PAPER",
        "live_trading": False,
        "paper_trading": True,
    }
