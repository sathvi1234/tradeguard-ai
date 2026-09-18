"""Historical backtest APIs. Results are HISTORICAL SIMULATION only."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.autonomous import autonomous_engine
from app.config import settings
from app.services.backtest_engine import RESULT_KIND, run_backtest, strategy_catalog
from app.services.backtest_store import get_backtest_run, list_backtest_runs, save_backtest_run
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


class BacktestRunRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    strategy: str = Field(..., min_length=1, max_length=64)
    start_date: str = Field(..., description="Inclusive YYYY-MM-DD")
    end_date: str = Field(..., description="Inclusive YYYY-MM-DD")
    initial_capital: float = Field(100000.0, gt=0, le=10_000_000)
    position_size: float = Field(0.10, gt=0, le=0.30)
    commission_per_trade: float = Field(1.0, ge=0, le=50)
    slippage_bps: float = Field(5.0, ge=0, le=100)


@router.get("/strategies")
async def list_strategies() -> dict:
    return {
        "strategies": strategy_catalog(),
        "result_kind": RESULT_KIND,
        "live_trading": False,
        "notes": "Equity bar strategies only. Option-library strategies need historical option chains and are not simulated here.",
    }


@router.get("/runs")
async def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {
        "runs": list_backtest_runs(limit=limit),
        "result_kind": RESULT_KIND,
        "live_returns": False,
        "live_trading": False,
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    payload = get_backtest_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    payload["live_returns"] = False
    payload["live_trading"] = False
    payload["result_kind"] = RESULT_KIND
    return payload


@router.post("/run")
async def run_historical_backtest(request: BacktestRunRequest) -> dict:
    symbol = request.symbol.strip().upper()
    start = f"{request.start_date}T00:00:00Z"
    end = f"{request.end_date}T23:59:59Z"
    alpaca = autonomous_engine.alpaca_service
    bars = await alpaca.get_bars_range(symbol, start=start, end=end)
    spy_bars = None
    if symbol != "SPY":
        spy_bars = await alpaca.get_bars_range("SPY", start=start, end=end) or None
    result = run_backtest(
        bars=bars,
        strategy=request.strategy,
        symbol=symbol,
        initial_capital=request.initial_capital,
        position_size=request.position_size,
        commission_per_trade=request.commission_per_trade,
        slippage_bps=request.slippage_bps,
        spy_bars=spy_bars,
    )
    result["start_date"] = request.start_date
    result["end_date"] = request.end_date
    result["dry_run"] = settings.dry_run
    result["live_trading"] = False
    result["live_returns"] = False
    result["result_kind"] = RESULT_KIND
    result["result_label"] = "HISTORICAL SIMULATION"
    if not result.get("ok"):
        return result
    stored = save_backtest_run(result)
    logger.info("Stored historical backtest %s for %s", stored.get("id"), symbol)
    return stored
