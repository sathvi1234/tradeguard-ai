"""Portfolio monitoring API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.trading.autonomous_engine import AutonomousTradingEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

# Get autonomous engine instance (from autonomous module)
from app.api.autonomous import autonomous_engine


@router.get("")
async def get_portfolio() -> dict:
    """Demo User virtual ledger is the portfolio source of truth."""
    try:
        from app.services.demo_ledger import demo_portfolio

        payload = await demo_portfolio(autonomous_engine)
        snapshot = autonomous_engine.portfolio_monitor.create_snapshot(
            account_value=float(payload.get("equity") or 0),
            cash=float(payload.get("cash") or 0),
            buying_power=float(payload.get("buying_power") or 0),
            positions_count=int(payload.get("positions_count") or 0),
            position_exposure=float(payload.get("position_exposure") or 0),
            realized_pnl=float(payload.get("realized_pnl") or 0),
            unrealized_pnl=float(payload.get("unrealized_pnl") or 0),
        )
        payload["peak_equity"] = snapshot.peak_equity
        payload["drawdown_pct"] = snapshot.drawdown_pct * 100
        payload["current_equity"] = snapshot.account_value
        payload["timestamp"] = snapshot.timestamp.isoformat()
        payload["source"] = "DEMO_LEDGER"
        payload["live_trading"] = False
        payload["paper_trading"] = True
        payload["trade_type"] = "DEMO_SIMULATED"
        payload["dry_run"] = True
        return payload
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve portfolio"
        )


@router.get("/history")
async def get_portfolio_history(
    limit: Optional[int] = Query(100, description="Max number of snapshots")
) -> list:
    """Get portfolio history."""
    try:
        snapshots = autonomous_engine.portfolio_monitor.get_snapshots(limit=limit)
        return [s.to_dict() for s in snapshots]
        
    except Exception as e:
        logger.error(f"Failed to get portfolio history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve portfolio history"
        )


@router.get("/stats")
async def get_portfolio_stats() -> dict:
    """Get portfolio statistics."""
    try:
        stats = autonomous_engine.portfolio_monitor.get_portfolio_stats()
        
        if not stats:
            raise HTTPException(
                status_code=404,
                detail="No portfolio statistics available"
            )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get portfolio stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve portfolio statistics"
        )


@router.get("/health")
async def get_portfolio_health() -> dict:
    """Get portfolio health status from the Demo User virtual ledger."""
    try:
        from app.services.demo_ledger import demo_portfolio

        port = await demo_portfolio(autonomous_engine)
        snapshot = autonomous_engine.portfolio_monitor.create_snapshot(
            account_value=float(port.get("equity") or 0),
            cash=float(port.get("cash") or 0),
            buying_power=float(port.get("buying_power") or 0),
            positions_count=int(port.get("positions_count") or 0),
            position_exposure=float(port.get("position_exposure") or 0),
            realized_pnl=float(port.get("realized_pnl") or 0),
            unrealized_pnl=float(port.get("unrealized_pnl") or 0),
        )
        health = autonomous_engine.portfolio_monitor.get_health_status()
        health["exposure"] = float(port.get("exposure") or 0)
        health["exposure_pct"] = float(port.get("exposure_pct") or 0)
        health["concentration"] = float(port.get("concentration") or 0)
        health["peak_equity"] = port.get("peak_equity") or snapshot.peak_equity
        health["current_equity"] = port.get("current_equity") or snapshot.account_value
        health["open_positions"] = int(port.get("positions_count") or 0)
        health["buying_power"] = float(port.get("buying_power") or 0)
        health["volatility"] = "Not enough data"
        health["source"] = "DEMO_LEDGER"
        return health
    except Exception as e:
        logger.error(f"Failed to get portfolio health: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve portfolio health"
        )


@router.get("/positions")
async def get_positions() -> list:
    """Get Demo User virtual positions. These persist in the demo ledger."""
    try:
        from app.services.demo_ledger import demo_portfolio

        port = await demo_portfolio(autonomous_engine)
        return list(port.get("positions") or [])
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve positions"
        )


@router.get("/positions/closed")
async def get_closed_positions() -> list:
    """Get all closed positions."""
    try:
        positions = autonomous_engine.position_manager.get_closed_positions()
        return [p.to_dict() for p in positions]
        
    except Exception as e:
        logger.error(f"Failed to get closed positions: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve closed positions"
        )


@router.get("/orders")
async def get_orders() -> list:
    """Get Demo User trade history from the virtual ledger."""
    try:
        from app.services.demo_ledger import get_demo_ledger

        return get_demo_ledger().list_trades()
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve orders"
        )


@router.get("/orders/open")
async def get_open_orders() -> list:
    """Get all open orders."""
    try:
        orders = autonomous_engine.order_tracker.get_open_orders()
        return [o.to_dict() for o in orders]
        
    except Exception as e:
        logger.error(f"Failed to get open orders: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve open orders"
        )


@router.get("/activity")
async def get_activity(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: Optional[int] = Query(100, description="Max number of events")
) -> list:
    """Get audit trail activity."""
    try:
        events = autonomous_engine.audit_logger.get_events(symbol=symbol, limit=limit)
        return [e.to_dict() for e in events]
        
    except Exception as e:
        logger.error(f"Failed to get activity: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve activity"
        )