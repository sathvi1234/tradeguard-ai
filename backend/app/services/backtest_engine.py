"""Chronological event-driven historical backtester.

Uses only bars with timestamp < current bar for signals (no look-ahead).
Fills at the current bar open after a prior-bar signal. Never live trading.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.risk.risk_guardian import RiskGuardian
from app.services.technicals import macd_line, rsi, sma

RESULT_KIND = "HISTORICAL_SIMULATION"
TRADING_DAYS = 252

BACKTEST_STRATEGIES: List[Dict[str, str]] = [
    {
        "key": "sma_crossover",
        "name": "SMA Crossover",
        "description": "Buy when SMA(10) crosses above SMA(30); sell on the opposite cross. Uses prior closes only.",
    },
    {
        "key": "rsi_mean_reversion",
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI(14) crosses below 30; sell when RSI crosses above 70. Uses prior closes only.",
    },
    {
        "key": "macd_trend",
        "name": "MACD Trend",
        "description": "Buy when MACD crosses above zero; sell when it crosses below. Uses prior closes only.",
    },
    {
        "key": "buy_and_hold",
        "name": "Buy and Hold",
        "description": "Single long entry at first tradable open; hold to the last close.",
    },
]


@dataclass(frozen=True)
class HistBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class LookAheadError(ValueError):
    """Raised when a signal would observe a future bar."""


def _as_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_bars(raw: Sequence[Any]) -> List[HistBar]:
    out: List[HistBar] = []
    for item in raw:
        if isinstance(item, HistBar):
            bar = item
        else:
            data = item if isinstance(item, dict) else {
                "timestamp": getattr(item, "timestamp", None),
                "open": getattr(item, "open", None),
                "high": getattr(item, "high", None),
                "low": getattr(item, "low", None),
                "close": getattr(item, "close", None),
                "volume": getattr(item, "volume", None),
            }
            ts = _as_dt(data.get("timestamp") or data.get("t"))
            o = data.get("open", data.get("o"))
            h = data.get("high", data.get("h"))
            low = data.get("low", data.get("l"))
            c = data.get("close", data.get("c"))
            v = data.get("volume", data.get("v")) or 0
            try:
                o_f, h_f, l_f, c_f = float(o), float(h), float(low), float(c)
            except (TypeError, ValueError):
                continue
            if ts is None or min(o_f, h_f, l_f, c_f) <= 0:
                continue
            bar = HistBar(timestamp=ts, open=o_f, high=h_f, low=l_f, close=c_f, volume=float(v or 0))
        out.append(bar)
    out.sort(key=lambda b: b.timestamp)
    return out


def assert_chronological(bars: Sequence[HistBar]) -> None:
    previous: Optional[datetime] = None
    for bar in bars:
        if previous is not None and bar.timestamp < previous:
            raise ValueError("Bars are not chronological")
        previous = bar.timestamp


def visible_history(bars: Sequence[HistBar], index: int) -> List[HistBar]:
    """Bars strictly before `index`. Current and future bars are excluded."""
    if index < 0:
        return []
    return list(bars[:index])


def _closes(bars: Sequence[HistBar]) -> List[float]:
    return [bar.close for bar in bars]


def generate_signal(
    strategy_key: str,
    visible: Sequence[HistBar],
    current: HistBar,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    """Signal from visible history only. Current bar OHLCV is not used."""
    if visible:
        last = visible[-1]
        if last.timestamp >= current.timestamp:
            raise LookAheadError("Signal history includes current or future timestamp")
    key = (strategy_key or "").strip().lower()
    cfg = params or {}
    if key == "buy_and_hold":
        return "BUY"
    closes = _closes(visible)
    if key == "sma_crossover":
        fast_n = int(cfg.get("fast", 10))
        slow_n = int(cfg.get("slow", 30))
        if fast_n <= 0 or slow_n <= fast_n or len(closes) < slow_n + 1:
            return "HOLD"
        fast = sma(closes, fast_n)
        slow = sma(closes, slow_n)
        prev_fast = sma(closes[:-1], fast_n)
        prev_slow = sma(closes[:-1], slow_n)
        if None in (fast, slow, prev_fast, prev_slow):
            return "HOLD"
        if prev_fast <= prev_slow and fast > slow:
            return "BUY"
        if prev_fast >= prev_slow and fast < slow:
            return "SELL"
        return "HOLD"
    if key == "rsi_mean_reversion":
        buy_level = float(cfg.get("rsi_buy", 30))
        sell_level = float(cfg.get("rsi_sell", 70))
        if len(closes) < 16:
            return "HOLD"
        now = rsi(closes, 14)
        prev = rsi(closes[:-1], 14)
        if now is None:
            return "HOLD"
        if now < buy_level and (prev is None or prev >= buy_level):
            return "BUY"
        if now > sell_level and (prev is None or prev <= sell_level):
            return "SELL"
        return "HOLD"
    if key == "macd_trend":
        now = macd_line(closes)
        prev = macd_line(closes[:-1])
        if now is None or prev is None:
            return "HOLD"
        if prev <= 0 and now > 0:
            return "BUY"
        if prev >= 0 and now < 0:
            return "SELL"
        return "HOLD"
    raise ValueError(f"Unknown backtest strategy: {strategy_key}")


def apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    bps = max(0.0, float(slippage_bps or 0)) / 10_000.0
    if side == "buy":
        return price * (1.0 + bps)
    return price * (1.0 - bps)


def _commission(qty: int, price: float, commission_per_trade: float, commission_bps: float) -> float:
    notional = abs(qty) * price
    return max(0.0, float(commission_per_trade or 0)) + notional * max(0.0, float(commission_bps or 0)) / 10_000.0


def _size_shares(equity: float, price: float, position_size: float) -> int:
    if price <= 0 or equity <= 0:
        return 0
    fraction = min(max(float(position_size), 0.0), RiskGuardian.MAX_PORTFOLIO_EXPOSURE)
    budget = equity * fraction
    return int(budget // price)


def _drawdown(equity: float, peak: float) -> float:
    if peak <= 0:
        return 0.0
    return max(0.0, (peak - equity) / peak)


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _stdev(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    var = sum((item - avg) ** 2 for item in values) / (len(values) - 1)
    return math.sqrt(var)


def compute_metrics(
    *,
    initial_capital: float,
    equity_curve: List[Dict[str, Any]],
    closed_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    final_equity = float(equity_curve[-1]["equity"]) if equity_curve else initial_capital
    total_return = (final_equity / initial_capital) - 1.0 if initial_capital else None
    n_days = max(len(equity_curve) - 1, 0)
    if total_return is None or n_days <= 0:
        annualized = None
    else:
        annualized = (1.0 + total_return) ** (TRADING_DAYS / n_days) - 1.0

    daily: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = float(equity_curve[i - 1]["equity"])
        now = float(equity_curve[i]["equity"])
        if prev > 0:
            daily.append((now / prev) - 1.0)

    vol = _stdev(daily)
    vol_ann = vol * math.sqrt(TRADING_DAYS) if vol is not None else None
    avg_daily = _mean(daily)
    sharpe = None
    if vol is not None and vol > 0 and avg_daily is not None:
        sharpe = (avg_daily / vol) * math.sqrt(TRADING_DAYS)
    downside = [r for r in daily if r < 0]
    dstd = _stdev(downside) if len(downside) >= 2 else (math.sqrt(sum(r * r for r in downside) / len(downside)) if downside else None)
    sortino = None
    if dstd is not None and dstd > 0 and avg_daily is not None:
        sortino = (avg_daily / dstd) * math.sqrt(TRADING_DAYS)

    peak = initial_capital
    max_dd = 0.0
    dd_curve: List[Dict[str, Any]] = []
    for point in equity_curve:
        equity = float(point["equity"])
        peak = max(peak, equity)
        dd = _drawdown(equity, peak)
        max_dd = max(max_dd, dd)
        dd_curve.append({"timestamp": point["timestamp"], "drawdown": dd})

    pnls = [float(t["pnl"]) for t in closed_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    holding = []
    for trade in closed_trades:
        days = trade.get("holding_days")
        if isinstance(days, (int, float)):
            holding.append(float(days))

    return {
        "total_return": total_return,
        "annualized_return": annualized,
        "win_rate": (len(wins) / len(pnls)) if pnls else None,
        "average_win": _mean(wins),
        "average_loss": _mean(losses),
        "expectancy": _mean(pnls),
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "maximum_drawdown": max_dd,
        "volatility": vol_ann,
        "number_of_trades": len(pnls),
        "average_holding_period_days": _mean(holding),
        "best_trade": max(pnls) if pnls else None,
        "worst_trade": min(pnls) if pnls else None,
        "drawdown_curve": dd_curve,
        "final_equity": final_equity,
        "ending_cash": equity_curve[-1].get("cash") if equity_curve else initial_capital,
    }


def _buy_hold_equity(bars: Sequence[HistBar], initial_capital: float) -> Dict[str, Any]:
    tradable = [b for b in bars if b.open > 0 and b.close > 0]
    if len(tradable) < 2 or initial_capital <= 0:
        return {
            "label": "buy_and_hold",
            "total_return": None,
            "final_equity": initial_capital,
            "notes": "Insufficient historical data for buy-and-hold comparison.",
        }
    entry = tradable[0]
    qty = int(initial_capital // entry.open)
    if qty <= 0:
        return {
            "label": "buy_and_hold",
            "total_return": None,
            "final_equity": initial_capital,
            "notes": "Initial capital too small to buy one share.",
        }
    cash = initial_capital - qty * entry.open
    last = tradable[-1]
    equity = cash + qty * last.close
    return {
        "label": "buy_and_hold",
        "entry_timestamp": entry.timestamp.isoformat(),
        "exit_timestamp": last.timestamp.isoformat(),
        "entry_price": entry.open,
        "exit_price": last.close,
        "quantity": qty,
        "final_equity": equity,
        "total_return": (equity / initial_capital) - 1.0,
        "result_kind": RESULT_KIND,
    }


def run_backtest(
    *,
    bars: Sequence[Any],
    strategy: str,
    symbol: str,
    initial_capital: float = 100_000.0,
    position_size: float = 0.10,
    commission_per_trade: float = 1.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 5.0,
    spy_bars: Optional[Sequence[Any]] = None,
    strategy_params: Optional[Dict[str, Any]] = None,
    look_ahead: bool = False,
    fill_on: str = "open",
    random_mode: Optional[str] = None,
    rng_seed: int = 42,
    spread_bps: float = 0.0,
) -> Dict[str, Any]:
    history = normalize_bars(bars)
    assert_chronological(history)
    capital = float(initial_capital)
    if capital <= 0:
        raise ValueError("initial_capital must be positive")
    if len(history) < 5:
        return {
            "ok": False,
            "result_kind": RESULT_KIND,
            "live_returns": False,
            "live_trading": False,
            "integrity_state": "DATA_UNAVAILABLE",
            "notes": "Insufficient historical data. Prices were not fabricated.",
            "symbol": symbol.upper(),
            "strategy": strategy,
        }

    cash = capital
    qty = 0
    avg_entry = 0.0
    entry_ts: Optional[datetime] = None
    entry_px = 0.0
    peak = capital
    equity_curve: List[Dict[str, Any]] = []
    closed: List[Dict[str, Any]] = []
    fills: List[Dict[str, Any]] = []
    risk_blocks = 0

    def mark(bar: HistBar) -> float:
        return cash + qty * bar.close

    def execute(side: str, shares: int, bar: HistBar) -> None:
        nonlocal cash, qty, avg_entry, entry_ts, entry_px, risk_blocks
        if shares <= 0:
            return
        raw_px = bar.close if fill_on == "close" else bar.open
        px = apply_slippage(raw_px, side, float(slippage_bps or 0) + float(spread_bps or 0))
        fee = _commission(shares, px, commission_per_trade, commission_bps)
        if side == "buy":
            cost = shares * px + fee
            equity_now = cash + qty * bar.open
            if cost > cash + 1e-9:
                return
            exposure = (shares * px) / equity_now if equity_now > 0 else 1
            if exposure > RiskGuardian.MAX_PORTFOLIO_EXPOSURE + 1e-9:
                risk_blocks += 1
                return
            if _drawdown(equity_now, peak) >= RiskGuardian.MAX_PORTFOLIO_DRAWDOWN:
                risk_blocks += 1
                return
            cash -= cost
            new_qty = qty + shares
            avg_entry = ((avg_entry * qty) + shares * px) / new_qty
            qty = new_qty
            if entry_ts is None:
                entry_ts = bar.timestamp
                entry_px = px
        else:
            shares = min(shares, qty)
            if shares <= 0:
                return
            proceeds = shares * px - fee
            cash += proceeds
            pnl = (px - avg_entry) * shares - fee
            hold_days = (bar.timestamp - entry_ts).total_seconds() / 86400.0 if entry_ts else None
            closed.append(
                {
                    "symbol": symbol.upper(),
                    "side": "sell",
                    "quantity": shares,
                    "entry_price": avg_entry,
                    "exit_price": px,
                    "pnl": pnl,
                    "entry_timestamp": entry_ts.isoformat() if entry_ts else None,
                    "exit_timestamp": bar.timestamp.isoformat(),
                    "holding_days": hold_days,
                }
            )
            qty -= shares
            if qty == 0:
                avg_entry = 0.0
                entry_ts = None
                entry_px = 0.0
        fills.append(
            {
                "timestamp": bar.timestamp.isoformat(),
                "side": side,
                "quantity": shares,
                "price": px,
                "commission": fee,
                "cash_after": cash,
                "position_after": qty,
            }
        )

    rng = random.Random(int(rng_seed))
    for index, bar in enumerate(history):
        visible = visible_history(history, index)
        if random_mode == "signals":
            signal = rng.choice(["BUY", "SELL", "HOLD", "HOLD", "HOLD"])
        elif random_mode == "entries":
            if qty == 0:
                signal = "BUY" if rng.random() < 0.08 else "HOLD"
            else:
                signal = "SELL" if rng.random() < 0.08 else "HOLD"
        elif look_ahead:
            leaked = list(history[: index + 1])
            fake = HistBar(
                timestamp=bar.timestamp + timedelta(seconds=1),
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            signal = generate_signal(strategy, leaked, fake, params=strategy_params)
        elif visible:
            last_visible = visible[-1]
            if last_visible.timestamp >= bar.timestamp:
                raise LookAheadError("Chronological walk observed a future or duplicate timestamp")
            signal = generate_signal(strategy, visible, bar, params=strategy_params)
        else:
            signal = "HOLD"

        if signal == "BUY" and qty == 0:
            fill_px = bar.close if fill_on == "close" else bar.open
            shares = _size_shares(cash, apply_slippage(fill_px, "buy", float(slippage_bps or 0) + float(spread_bps or 0)), position_size)
            execute("buy", shares, bar)
        elif signal == "SELL" and qty > 0:
            execute("sell", qty, bar)

        equity = mark(bar)
        peak = max(peak, equity)
        equity_curve.append(
            {
                "timestamp": bar.timestamp.isoformat(),
                "equity": equity,
                "cash": cash,
                "position": qty,
                "close": bar.close,
                "open": bar.open,
            }
        )

    if qty > 0:
        last = history[-1]
        px = apply_slippage(last.close, "sell", slippage_bps)
        fee = _commission(qty, px, commission_per_trade, commission_bps)
        proceeds = qty * px - fee
        pnl = (px - avg_entry) * qty - fee
        hold_days = (last.timestamp - entry_ts).total_seconds() / 86400.0 if entry_ts else None
        cash += proceeds
        closed.append(
            {
                "symbol": symbol.upper(),
                "side": "sell",
                "quantity": qty,
                "entry_price": avg_entry,
                "exit_price": px,
                "pnl": pnl,
                "entry_timestamp": entry_ts.isoformat() if entry_ts else None,
                "exit_timestamp": last.timestamp.isoformat(),
                "holding_days": hold_days,
                "end_of_period": True,
            }
        )
        fills.append(
            {
                "timestamp": last.timestamp.isoformat(),
                "side": "sell",
                "quantity": qty,
                "price": px,
                "commission": fee,
                "cash_after": cash,
                "position_after": 0,
                "end_of_period": True,
            }
        )
        qty = 0
        if equity_curve:
            equity_curve[-1]["equity"] = cash
            equity_curve[-1]["cash"] = cash
            equity_curve[-1]["position"] = 0

    stats = compute_metrics(initial_capital=capital, equity_curve=equity_curve, closed_trades=closed)
    buy_hold = _buy_hold_equity(history, capital)
    spy_cmp = None
    if spy_bars:
        spy_hist = normalize_bars(spy_bars)
        spy_cmp = _buy_hold_equity(spy_hist, capital)
        spy_cmp["label"] = "SPY_buy_and_hold"
        spy_cmp["symbol"] = "SPY"
    elif symbol.upper() == "SPY":
        spy_cmp = {**buy_hold, "label": "SPY_buy_and_hold", "symbol": "SPY"}

    return {
        "ok": True,
        "result_kind": RESULT_KIND,
        "result_label": "HISTORICAL SIMULATION",
        "live_returns": False,
        "live_trading": False,
        "dry_run": True,
        "symbol": symbol.upper(),
        "strategy": strategy,
        "initial_capital": capital,
        "position_size": min(max(float(position_size), 0.0), RiskGuardian.MAX_PORTFOLIO_EXPOSURE),
        "commission_per_trade": commission_per_trade,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "bar_count": len(history),
        "start": history[0].timestamp.isoformat(),
        "end": history[-1].timestamp.isoformat(),
        "equity_curve": equity_curve,
        "trades": closed,
        "fills": fills,
        "metrics": stats,
        "buy_and_hold": buy_hold,
        "spy_comparison": spy_cmp,
        "risk_guardian_limits": {
            "max_portfolio_exposure": RiskGuardian.MAX_PORTFOLIO_EXPOSURE,
            "max_portfolio_drawdown": RiskGuardian.MAX_PORTFOLIO_DRAWDOWN,
            "blocks": risk_blocks,
            "final_authority": True,
        },
        "look_ahead_bias": bool(look_ahead),
        "future_data_leakage": bool(look_ahead or fill_on == "close"),
        "notes": "HISTORICAL SIMULATION only. Not live returns. Signals used bars strictly before each fill.",
    }


def strategy_catalog() -> List[Dict[str, str]]:
    return list(BACKTEST_STRATEGIES)
