"""Tests for Alpaca paper trading connection and portfolio initialization."""

from unittest.mock import AsyncMock, patch

import pytest

from app.alpaca.client import AlpacaClient
from app.alpaca.exceptions import AlpacaLiveTradingBlocked
from app.alpaca.service import AlpacaService
from app.config import ENV_FILE, PAPER_API_URL, Settings, settings
from app.trading.autonomous_engine import AutonomousTradingEngine


def test_env_file_is_backend_dotenv():
    """Settings must load backend/.env regardless of process cwd."""
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent.name == "backend"
    assert settings.alpaca_paper_trade is True
    assert settings.dry_run is True
    assert settings.alpaca_base_url.rstrip("/") == PAPER_API_URL


def test_live_url_is_blocked():
    client = AlpacaClient()
    client.base_url = "https://api.alpaca.markets"
    with pytest.raises(AlpacaLiveTradingBlocked):
        client._validate_paper_only()


@pytest.mark.asyncio
async def test_account_mapping_from_paper_api():
    service = AlpacaService()
    raw = {
        "status": "ACTIVE",
        "cash": "25000.50",
        "buying_power": "50000.00",
        "portfolio_value": "75123.45",
        "equity": "75123.45",
        "trading_blocked": False,
        "account_blocked": False,
        "currency": "USD",
    }
    mapped = service._map_account(raw)
    assert mapped["status"] == "ACTIVE"
    assert mapped["cash"] == 25000.50
    assert mapped["buying_power"] == 50000.00
    assert mapped["portfolio_value"] == 75123.45
    assert mapped["equity"] == 75123.45
    assert mapped["paper_trading_allowed"] is True
    assert mapped["live_trading"] is False


@pytest.mark.asyncio
async def test_get_status_healthy_when_account_returns():
    service = AlpacaService()
    with patch.object(service, "get_account", new_callable=AsyncMock) as mock_account:
        mock_account.return_value = {
            "status": "ACTIVE",
            "cash": 1000.0,
            "buying_power": 2000.0,
            "portfolio_value": 3000.0,
            "equity": 3000.0,
        }
        with patch.object(Settings, "alpaca_keys_configured", return_value=True):
            result = await service.get_status()
    assert result["healthy"] is True
    assert result["connected"] is True
    assert result["authenticated"] is True
    assert result["paper_trading"] is True
    assert result["dry_run"] is True
    assert result["live_trading"] is False
    blob = str(result).lower()
    assert "secret" not in blob
    assert "apca-" not in blob


@pytest.mark.asyncio
async def test_engine_initializes_portfolio_monitor_from_account():
    engine = AutonomousTradingEngine(dry_run=True)
    with patch.object(engine.alpaca_service, "get_account", new_callable=AsyncMock) as mock_account:
        mock_account.return_value = {
            "paper_trading_allowed": True,
            "trading_blocked": False,
            "portfolio_value": 100000.0,
            "cash": 80000.0,
            "buying_power": 90000.0,
            "equity": 100000.0,
            "status": "ACTIVE",
        }
        success = await engine.initialize()

    assert success is True
    snapshot = engine.portfolio_monitor.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot.account_value == 100000.0
    assert snapshot.cash == 80000.0
    assert snapshot.buying_power == 90000.0
