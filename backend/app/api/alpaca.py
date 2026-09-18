"""Alpaca paper trading status endpoints."""

from fastapi import APIRouter

from app.alpaca.service import AlpacaService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/alpaca", tags=["alpaca"])
_service = AlpacaService()


@router.get("/status")
async def get_alpaca_status() -> dict:
    """Return Alpaca paper-trading connection health. Never includes secrets."""
    return await _service.get_status()
