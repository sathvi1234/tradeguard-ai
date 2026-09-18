"""Health check endpoint."""

from fastapi import APIRouter

from app.alpaca.iex_stream import get_iex_hub
from app.config import settings
from app.db.session import database_health

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Return service health without exposing secrets."""
    hub = get_iex_hub().status()
    db = database_health()
    return {
        "status": "healthy",
        "healthy": True,
        "version": settings.app_version,
        "environment": settings.environment,
        "paper_trading": settings.alpaca_paper_trade,
        "dry_run": settings.dry_run,
        "safety_mode": True,
        "live_trading": False,
        "live_trading_blocked": True,
        "iex_feed": hub.get("feed"),
        "iex_stream_state": hub.get("state"),
        "live_market_data": hub.get("live_market_data"),
        "llm_configured": settings.llm_configured(),
        "database": db.get("database"),
        "database_dialect": db.get("database_dialect"),
        "sqlite_fallback": db.get("sqlite_fallback"),
        "service": settings.app_name,
    }
