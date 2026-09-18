"""Technical indicator tests — computed from provided bars only."""

from types import SimpleNamespace

from app.services.technicals import analyze_bars, rsi, sma


def test_sma_and_rsi_from_real_series():
    values = [float(i) for i in range(1, 21)]
    assert sma(values, 5) == 18.0
    bars = [SimpleNamespace(close=v, high=v + 1, low=v - 1, volume=1000, vwap=v, open=v) for v in values]
    result = analyze_bars(bars)
    assert result["bar_count"] == 20
    assert result["sma_20"] == 10.5
    assert result["rsi_14"] != "DATA_UNAVAILABLE"


def test_insufficient_bars_stay_unavailable():
    bars = [SimpleNamespace(close=10.0, high=11.0, low=9.0, volume=1, vwap=10.0, open=10.0)]
    result = analyze_bars(bars)
    assert result["sma_20"] == "DATA_UNAVAILABLE"
    assert result["macd"] == "DATA_UNAVAILABLE"
    assert rsi([10.0, 11.0], 14) is None
