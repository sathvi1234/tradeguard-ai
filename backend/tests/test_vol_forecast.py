"""Volatility forecast tests. Advisory only. No live trading."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.session import ensure_schema, get_engine, sqlite_url
from app.models.schemas import DATA_UNAVAILABLE
from app.services.vol_forecast import build_rows, chronological_split, forecast_volatility
from app.services import vol_forecast_store


def _bars(closes: List[float], volumes: Optional[List[float]] = None):
    out = []
    start = datetime(2023, 1, 3, tzinfo=timezone.utc)
    for i, close in enumerate(closes):
        day = start + timedelta(days=i)
        vol = volumes[i] if volumes else 1_000.0
        out.append(
            {
                "timestamp": day,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": vol,
            }
        )
    return out


def _path(n: int = 90) -> List[float]:
    price = 100.0
    closes = []
    for i in range(n):
        move = 0.004 if i < n // 2 else 0.02
        price *= 1.0 + (move if i % 2 == 0 else -move * 0.8)
        closes.append(price)
    return closes


def test_missing_data_returns_unavailable_not_zeros():
    result = forecast_volatility([], symbol="AAPL")
    assert result["ok"] is False
    assert result["integrity_state"] == DATA_UNAVAILABLE
    assert result["predictions"]["vol_5d"] == DATA_UNAVAILABLE
    assert result["predictions"]["vol_10d"] == DATA_UNAVAILABLE
    assert result["can_approve_trades"] is False
    assert result["overrides_risk_guardian"] is False
    assert 0 not in (result["predictions"]["vol_5d"], result["realized_volatility"]["vol_5d"])


def test_time_series_not_shuffled_and_no_feature_lookahead():
    closes = [100.0] * 40 + [180.0] + [100.0] * 30
    rows, _ = build_rows(_bars(closes))
    before = next(row for row in rows if row["index"] == 39)
    at_spike = next(row for row in rows if row["index"] == 40)
    assert before["features"]["hv_5"] < 0.2
    assert at_spike["features"]["hv_5"] > before["features"]["hv_5"]
    train, val, test = chronological_split(rows)
    if train and val:
        assert train[-1]["timestamp"] < val[0]["timestamp"]
    if val and test:
        assert val[-1]["timestamp"] < test[0]["timestamp"]


def test_prediction_output_and_metrics():
    result = forecast_volatility(_bars(_path(100)), symbol="MSFT")
    assert result["ok"] is True
    assert result["advisory_only"] is True
    assert result["can_approve_trades"] is False
    assert result["overrides_risk_guardian"] is False
    assert result["live_trading"] is False
    assert result["time_series_shuffled"] is False
    assert result["look_ahead_leakage"] is False
    assert isinstance(result["predictions"]["vol_5d"], float)
    assert isinstance(result["predictions"]["vol_10d"], float)
    assert result["predictions"]["vol_5d"] > 0
    assert result["model_name"] in {"ridge_regression", "xgboost_regressor"}
    assert result["training_period"]["shuffled"] is False
    metrics = result["metrics"]["vol_5d"]["model"]
    assert metrics["mae"] is not None
    assert metrics["rmse"] is not None
    assert "forecast_correlation" in metrics
    assert "historical_prices" in result["features"]["available"]
    assert "rolling_returns" in result["features"]["available"]
    assert "vix_term_structure" in result["features"]["unavailable"]
    assert "implied_volatility" in result["features"]["unavailable"]
    assert result["vix"]["level"] == DATA_UNAVAILABLE
    assert result["current_iv"] == DATA_UNAVAILABLE


def test_vix_used_only_when_series_exists():
    equity = _bars(_path(80))
    vix = _bars([20.0 + (i % 5) * 0.2 for i in range(80)])
    result = forecast_volatility(equity, symbol="AAPL", vix_bars=vix)
    assert "vix" in result["features"]["available"]
    assert isinstance(result["vix"]["level"], float)


def test_persist_forecast(tmp_path: Path, monkeypatch):
    engine = get_engine(sqlite_url(tmp_path / "vol.sqlite"))
    ensure_schema(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(vol_forecast_store, "SessionLocal", lambda: Session())
    monkeypatch.setattr(vol_forecast_store, "get_engine", lambda: engine)
    result = forecast_volatility(_bars(_path(80)), symbol="SPY")
    stored = vol_forecast_store.save_volatility_forecast(result)
    fetched = vol_forecast_store.get_volatility_forecast(stored["id"])
    assert fetched is not None
    assert fetched["can_approve_trades"] is False
    listed = vol_forecast_store.list_volatility_forecasts()
    assert listed[0]["id"] == stored["id"]
