"""Engine and session factory. PostgreSQL when DATABASE_URL is set; SQLite otherwise."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import BACKEND_DIR, normalize_database_url, settings
from app.db.models import Base, DemoAccount

STARTING_CASH = 100_000.00
DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "demo_ledger.sqlite"

_LOCK = threading.Lock()
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def sqlite_url(path: Path) -> str:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + resolved.as_posix()


def configured_database_url() -> str:
    raw = (settings.database_url or "").strip()
    if raw:
        return normalize_database_url(raw)
    return sqlite_url(DEFAULT_SQLITE_PATH)


def dialect_name(url: Optional[str] = None) -> str:
    value = (url or configured_database_url()).lower()
    if value.startswith("postgresql"):
        return "postgresql"
    if value.startswith("sqlite"):
        return "sqlite"
    return "other"


def _make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    kwargs: dict = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if url.startswith("postgresql"):
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(url, **kwargs)


def get_engine(url: Optional[str] = None) -> Engine:
    global _engine, _SessionLocal
    if url:
        return _make_engine(url)
    with _LOCK:
        if _engine is None:
            _engine = _make_engine(configured_database_url())
            _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
        return _engine


def SessionLocal() -> Session:
    global _SessionLocal
    get_engine()
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _SessionLocal()


def ensure_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = session.get(DemoAccount, 1)
        if row is None:
            session.add(
                DemoAccount(id=1, cash=STARTING_CASH, realized_pnl=0, starting_cash=STARTING_CASH)
            )
            session.commit()


def init_db() -> None:
    """Create schema. Use Alembic on PostgreSQL when available; create_all always as safety."""
    engine = get_engine()
    if dialect_name() == "postgresql":
        try:
            from alembic import command
            from alembic.config import Config

            from app.utils.logging import get_logger

            cfg = Config(str(BACKEND_DIR / "alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", configured_database_url())
            command.upgrade(cfg, "head")
        except Exception as exc:
            get_logger(__name__).warning(
                "Alembic upgrade failed; falling back to create_all",
                error_type=type(exc).__name__,
            )
            ensure_schema(engine)
            return
    ensure_schema(engine)


def reset_engine() -> None:
    global _engine, _SessionLocal
    with _LOCK:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _SessionLocal = None


def database_health() -> dict:
    """Connection status without secrets, URLs, or credentials."""
    url = configured_database_url()
    dialect = dialect_name(url)
    fallback = not bool((settings.database_url or "").strip())
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "database": "connected",
            "database_dialect": dialect,
            "sqlite_fallback": fallback,
        }
    except Exception:
        return {
            "database": "disconnected",
            "database_dialect": dialect,
            "sqlite_fallback": fallback,
        }
