"""Research-only falsification APIs. Never live trading."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.autonomous import autonomous_engine
from app.config import settings
from app.services.backtest_engine import strategy_catalog
from app.services.falsification_engine import DISCLAIMER, RESULT_KIND, run_falsification
from app.services.falsification_store import (
    get_falsification_report,
    list_falsification_reports,
    save_falsification_report,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/falsification", tags=["falsification"])


class FalsificationRunRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    strategy: str = Field(..., min_length=1, max_length=64)
    start_date: str
    end_date: str
    initial_capital: float = Field(100000.0, gt=0, le=10_000_000)
    position_size: float = Field(0.10, gt=0, le=0.30)


@router.get("/tests")
async def list_tests() -> dict:
    return {
        "result_kind": RESULT_KIND,
        "research_only": True,
        "live_trading": False,
        "risk_guardian_overridden": False,
        "proven_profitable": False,
        "disclaimer": DISCLAIMER,
        "strategies": strategy_catalog(),
        "tests": [
            "look_ahead_bias",
            "data_leakage",
            "train_test_contamination",
            "survivorship_bias_risk",
            "randomized_entries",
            "randomized_signals",
            "buy_and_hold_comparison",
            "spy_comparison",
            "transaction_cost_sensitivity",
            "slippage_sensitivity",
            "spread_cost_sensitivity",
            "parameter_sensitivity",
            "position_size_sensitivity",
            "historical_date_windows",
            "remove_best_trades",
            "remove_worst_trades",
            "market_regimes",
            "volatility_regimes",
            "monte_carlo_trade_order",
        ],
        "states": ["PASS", "FAIL", "WARNING", "INCONCLUSIVE"],
    }


@router.get("/reports")
async def list_reports(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {
        "reports": list_falsification_reports(limit=limit),
        "result_kind": RESULT_KIND,
        "live_trading": False,
        "proven_profitable": False,
        "disclaimer": DISCLAIMER,
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    payload = get_falsification_report(report_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Falsification report not found")
    payload["live_trading"] = False
    payload["proven_profitable"] = False
    payload["risk_guardian_overridden"] = False
    return payload


@router.post("/run")
async def run_research_falsification(request: FalsificationRunRequest) -> dict:
    symbol = request.symbol.strip().upper()
    start = f"{request.start_date}T00:00:00Z"
    end = f"{request.end_date}T23:59:59Z"
    alpaca = autonomous_engine.alpaca_service
    bars = await alpaca.get_bars_range(symbol, start=start, end=end)
    spy_bars = None
    if symbol != "SPY":
        spy_bars = await alpaca.get_bars_range("SPY", start=start, end=end) or None
    result = run_falsification(
        bars=bars,
        strategy=request.strategy,
        symbol=symbol,
        initial_capital=request.initial_capital,
        position_size=request.position_size,
        start_date=request.start_date,
        end_date=request.end_date,
        spy_bars=spy_bars,
    )
    result["dry_run"] = settings.dry_run
    result["live_trading"] = False
    result["live_returns"] = False
    result["proven_profitable"] = False
    result["risk_guardian_overridden"] = False
    if not result.get("ok"):
        return result
    stored = save_falsification_report(result)
    logger.info("Stored falsification report %s for %s", stored.get("id"), symbol)
    return stored
