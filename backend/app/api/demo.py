"""Demo User virtual trading API. Never submits Alpaca orders."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.autonomous import autonomous_engine
from app.config import settings
from app.services.demo_ledger import demo_portfolio, get_demo_ledger, submit_demo_equity_order
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: int = Field(..., gt=0, le=1000)
    order_type: str = "demo"
    preview_only: bool = False


@router.post("/orders")
async def submit_demo_order(body: DemoOrderRequest) -> dict:
    result = await submit_demo_equity_order(autonomous_engine, body.model_dump())
    result["dry_run"] = settings.dry_run
    result["paper_trading"] = True
    result["live_trading"] = False
    result["alpaca_order_submitted"] = False
    return result


@router.get("/orders")
async def list_demo_orders(limit: int = Query(100, ge=1, le=500)) -> dict:
    trades = get_demo_ledger().list_trades()[:limit]
    return {
        "orders": trades,
        "count": len(trades),
        "source": "DEMO_LEDGER",
        "trade_type": "DEMO_SIMULATED",
        "live_trading": False,
        "alpaca_order_submitted": False,
        "dry_run": settings.dry_run,
    }


@router.get("/positions")
async def list_demo_positions() -> dict:
    port = await demo_portfolio(autonomous_engine)
    return {
        "positions": port.get("positions") or [],
        "count": int(port.get("positions_count") or 0),
        "source": "DEMO_LEDGER",
        "trade_type": "DEMO_SIMULATED",
        "live_trading": False,
        "dry_run": settings.dry_run,
    }


@router.get("/portfolio")
async def get_demo_portfolio() -> dict:
    payload = await demo_portfolio(autonomous_engine)
    payload["dry_run"] = settings.dry_run
    payload["live_trading"] = False
    payload["alpaca_order_submitted"] = False
    return payload
