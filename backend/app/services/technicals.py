"""Technical indicators from real bar data only. Never invent prices."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.models.schemas import DATA_UNAVAILABLE


def _closes(bars: List[Any]) -> List[float]:
    out: List[float] = []
    for bar in bars:
        close = getattr(bar, "close", None)
        if close is None and isinstance(bar, dict):
            close = bar.get("close")
        if isinstance(close, (int, float)) and close > 0:
            out.append(float(close))
    return out


def _volumes(bars: List[Any]) -> List[float]:
    out: List[float] = []
    for bar in bars:
        vol = getattr(bar, "volume", None)
        if vol is None and isinstance(bar, dict):
            vol = bar.get("volume")
        if isinstance(vol, (int, float)) and vol >= 0:
            out.append(float(vol))
    return out


def sma(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def ema(values: List[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period:
        return None
    k = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    for price in values[period:]:
        current = price * k + current * (1 - k)
    return current


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_line(values: List[float]) -> Optional[float]:
    fast = ema(values, 12)
    slow = ema(values, 26)
    if fast is None or slow is None:
        return None
    return fast - slow


def realized_vol(values: List[float]) -> Optional[float]:
    if len(values) < 3:
        return None
    rets: List[float] = []
    for i in range(1, len(values)):
        if values[i - 1] <= 0:
            continue
        rets.append(math.log(values[i] / values[i - 1]))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def volume_trend(volumes: List[float]) -> Optional[str]:
    if len(volumes) < 6:
        return None
    recent = sum(volumes[-3:]) / 3
    prior = sum(volumes[-6:-3]) / 3
    if prior <= 0:
        return None
    if recent > prior * 1.1:
        return "rising"
    if recent < prior * 0.9:
        return "falling"
    return "flat"


def _fmt(value: Optional[float], digits: int = 4) -> Any:
    if value is None:
        return DATA_UNAVAILABLE
    return round(value, digits)


def analyze_bars(bars: List[Any]) -> Dict[str, Any]:
    closes = _closes(bars)
    volumes = _volumes(bars)
    highs: List[float] = []
    lows: List[float] = []
    last_vwap = None
    for bar in bars:
        high = getattr(bar, "high", None) if not isinstance(bar, dict) else bar.get("high")
        low = getattr(bar, "low", None) if not isinstance(bar, dict) else bar.get("low")
        vwap = getattr(bar, "vwap", None) if not isinstance(bar, dict) else bar.get("vwap")
        if isinstance(high, (int, float)):
            highs.append(float(high))
        if isinstance(low, (int, float)):
            lows.append(float(low))
        if isinstance(vwap, (int, float)):
            last_vwap = float(vwap)

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    last = closes[-1] if closes else None
    trend = DATA_UNAVAILABLE
    if last is not None and sma20 is not None:
        if last > sma20 * 1.005:
            trend = "price above SMA20 (descriptive, not a forecast)"
        elif last < sma20 * 0.995:
            trend = "price below SMA20 (descriptive, not a forecast)"
        else:
            trend = "price near SMA20 (descriptive, not a forecast)"

    intraday = DATA_UNAVAILABLE
    if bars:
        first = bars[0]
        last_bar = bars[-1]
        o = getattr(first, "open", None) if not isinstance(first, dict) else first.get("open")
        c = getattr(last_bar, "close", None) if not isinstance(last_bar, dict) else last_bar.get("close")
        if isinstance(o, (int, float)) and isinstance(c, (int, float)) and o:
            intraday = {
                "session_open": o,
                "last_close": c,
                "change": round(c - o, 4),
                "change_pct": round((c - o) / o, 6),
                "note": "Computed from available bars only. Not a live tick tape.",
            }

    support = min(lows[-20:]) if len(lows) >= 5 else None
    resistance = max(highs[-20:]) if len(highs) >= 5 else None

    macd = macd_line(closes)
    return {
        "bar_count": len(bars),
        "sma_20": _fmt(sma20, 4),
        "sma_50": _fmt(sma50, 4),
        "ema_12": _fmt(ema(closes, 12), 4),
        "ema_26": _fmt(ema(closes, 26), 4),
        "rsi_14": _fmt(rsi(closes, 14), 2),
        "macd": _fmt(macd, 4) if macd is not None else DATA_UNAVAILABLE,
        "realized_vol_ann": _fmt(realized_vol(closes), 4),
        "volume_trend": volume_trend(volumes) or DATA_UNAVAILABLE,
        "vwap_last_bar": _fmt(last_vwap, 4),
        "anchored_vwap": DATA_UNAVAILABLE,
        "intraday": intraday,
        "trend": trend,
        "recent_low": _fmt(support, 4),
        "recent_high": _fmt(resistance, 4),
        "support_resistance_note": (
            "Recent N-bar high/low from available history. Not a predictive support/resistance model."
            if support is not None
            else DATA_UNAVAILABLE
        ),
        "unavailable_reason": None if len(closes) >= 15 else "Need more historical bars for SMA/RSI/MACD.",
    }
