"""SQLAlchemy models compatible with SQLite and PostgreSQL."""

from typing import Optional

from sqlalchemy import CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for Trade AI persistence."""


class DemoAccount(Base):
    __tablename__ = "account"
    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_account_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    starting_cash: Mapped[float] = mapped_column(Float, nullable=False)


class DemoPosition(Base):
    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry: Mapped[float] = mapped_column(Float, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class DemoTrade(Base):
    __tablename__ = "trades"

    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class BacktestRun(Base):
    """Stored historical simulation results. Never live returns."""

    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[str] = mapped_column(String(32), nullable=False)
    end_date: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    result_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="HISTORICAL_SIMULATION")
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class FalsificationReport(Base):
    """Research-only falsification reports. Never live trades."""

    __tablename__ = "falsification_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[str] = mapped_column(String(32), nullable=False)
    end_date: Mapped[str] = mapped_column(String(32), nullable=False)
    overall_state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    result_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="FALSIFICATION_RESEARCH")
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class VolatilityForecast(Base):
    """Advisory volatility forecast metadata and results. Never live trades."""

    __tablename__ = "volatility_forecasts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    result_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="VOLATILITY_FORECAST_ADVISORY")
    payload: Mapped[str] = mapped_column(Text, nullable=False)


