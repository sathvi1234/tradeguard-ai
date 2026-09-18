"""SQLAlchemy SQLite fallback and optional PostgreSQL."""

from pathlib import Path

from sqlalchemy import text

from app.db.session import database_health, ensure_schema, get_engine, sqlite_url
from app.services.demo_ledger import DemoLedger, STARTING_CASH
from app.services.portfolio_greeks import PortfolioGreeksService
from app.models.schemas import DataAvailability


def test_sqlite_fallback_and_persistence(tmp_path: Path):
    path = tmp_path / "ledger.sqlite"
    engine = get_engine(sqlite_url(path))
    ensure_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    first = DemoLedger(path)
    first.apply_fill({"trade_id": "t1", "symbol": "GOOGL", "side": "buy", "quantity": 1, "price": 100.0, "company": "Alphabet"})
    cash = first.account_row()["cash"]
    assert cash == STARTING_CASH - 100.0
    again = DemoLedger(path)
    assert again.account_row()["cash"] == cash
    assert again.list_raw_positions()[0]["symbol"] == "GOOGL"
    assert again.list_trades()[0]["trade_id"] == "t1"


def test_database_health_has_no_secrets():
    payload = database_health()
    blob = str(payload)
    assert "password" not in blob.lower()
    assert "postgresql+psycopg" not in blob
    assert payload["database"] in {"connected", "disconnected"}
    assert payload["database_dialect"] in {"sqlite", "postgresql", "other"}


def test_greeks_equity_positions_are_empty_not_error():
    snap = PortfolioGreeksService().snapshot(positions=[{"symbol": "GOOGL", "type": "EQUITY", "quantity": 1}])
    assert snap.reason_code == "NO_OPTION_POSITIONS"
    assert snap.availability == DataAvailability.EMPTY
    assert snap.delta is None


def test_greeks_option_without_snapshots_unavailable():
    snap = PortfolioGreeksService().snapshot(
        positions=[{"symbol": "AAPL250117C00150000", "type": "OPTION", "quantity": 1}]
    )
    assert snap.reason_code == "NO_OPTION_GREEKS"
    assert snap.availability == DataAvailability.DATA_UNAVAILABLE
    assert "Alpaca option snapshot Greeks" in snap.notes
