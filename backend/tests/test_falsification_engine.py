"""Falsification engine tests. Research only. No live orders."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.session import ensure_schema, get_engine, sqlite_url
from app.services.falsification_engine import (
    DISCLAIMER,
    FAIL,
    INCONCLUSIVE,
    PASS,
    WARNING,
    run_falsification,
)
from app.services import falsification_store


def _ts(day: int) -> datetime:
    return datetime(2024, 1, 2, tzinfo=timezone.utc) + timedelta(days=day)


def _bars(closes: List[float]):
    out = []
    for i, close in enumerate(closes):
        open_px = closes[i - 1] if i else close
        out.append(
            {
                "timestamp": _ts(i),
                "open": open_px,
                "high": max(open_px, close),
                "low": min(open_px, close),
                "close": close,
                "volume": 1_000,
            }
        )
    return out


def _trend(n: int = 80) -> List[float]:
    return [100.0 + i * 0.4 for i in range(n)]


def test_report_has_required_states_and_counts():
    report = run_falsification(bars=_bars(_trend()), strategy="buy_and_hold", symbol="AAPL")
    assert report["research_only"] is True
    assert report["live_trading"] is False
    assert report["proven_profitable"] is False
    assert report["risk_guardian_overridden"] is False
    assert report["risk_guardian_is_final_authority"] is True
    assert DISCLAIMER in report["disclaimer"]
    names = [row["test"] for row in report["tests"]]
    for required in (
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
    ):
        assert required in names
    summary = report["summary"]
    assert summary["total_tests"] == len(report["tests"]) == 19
    assert summary["passed_tests"] + summary["failed_tests"] + summary["warnings"] + summary["inconclusive_tests"] == 19
    assert report["overall_state"] in {PASS, FAIL, WARNING, INCONCLUSIVE}
    for row in report["tests"]:
        assert row["state"] in {PASS, FAIL, WARNING, INCONCLUSIVE}
        assert "baseline_metric" in row
        assert "challenged_metric" in row
        assert "performance_degradation" in row
        assert row["explanation"]
        assert isinstance(row["evidence"], dict)
        assert row["timestamp"]
        assert row["live_trading"] is False
        assert row["risk_guardian_overridden"] is False


def test_look_ahead_detects_inflated_result():
    closes = [10.0] * 40 + [12.0] * 40
    report = run_falsification(bars=_bars(closes), strategy="sma_crossover", symbol="MSFT")
    row = next(item for item in report["tests"] if item["test"] == "look_ahead_bias")
    assert row["state"] in {PASS, FAIL, WARNING, INCONCLUSIVE}
    if isinstance(row["baseline_metric"], float) and isinstance(row["challenged_metric"], float):
        if row["challenged_metric"] > row["baseline_metric"] + 0.01:
            assert row["state"] == FAIL


def test_survivorship_is_warning_not_pass():
    report = run_falsification(bars=_bars(_trend()), strategy="buy_and_hold", symbol="NVDA")
    row = next(item for item in report["tests"] if item["test"] == "survivorship_bias_risk")
    assert row["state"] == WARNING
    assert "delisted" in row["explanation"].lower() or "survivorship" in row["explanation"].lower()


def test_never_claims_proven_profit_on_pass():
    report = run_falsification(bars=_bars(_trend()), strategy="buy_and_hold", symbol="SPY")
    assert report["proven_profitable"] is False
    assert "does not prove" in report["disclaimer"].lower() or "not prove" in report["disclaimer"].lower()


def test_insufficient_history_is_inconclusive_not_fabricated():
    report = run_falsification(bars=_bars([10.0, 10.1, 10.2]), strategy="sma_crossover", symbol="AAPL")
    assert report["ok"] is False or report["summary"]["inconclusive_tests"] >= 1
    assert report["proven_profitable"] is False


def test_persist_falsification_report(tmp_path: Path, monkeypatch):
    engine = get_engine(sqlite_url(tmp_path / "falsify.sqlite"))
    ensure_schema(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(falsification_store, "SessionLocal", lambda: Session())
    monkeypatch.setattr(falsification_store, "get_engine", lambda: engine)
    report = run_falsification(bars=_bars(_trend(50)), strategy="buy_and_hold", symbol="AAPL")
    stored = falsification_store.save_falsification_report(report)
    fetched = falsification_store.get_falsification_report(stored["id"])
    assert fetched is not None
    assert fetched["result_kind"] == "FALSIFICATION_RESEARCH"
    assert fetched["live_trading"] is False
    listed = falsification_store.list_falsification_reports()
    assert listed[0]["id"] == stored["id"]
    assert listed[0]["proven_profitable"] is False
