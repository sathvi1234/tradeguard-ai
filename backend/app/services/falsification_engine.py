"""Research-only falsification of historical backtests.

Never places trades. Never overrides Risk Guardian. Never claims proven profit.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.risk.risk_guardian import RiskGuardian
from app.services.backtest_engine import normalize_bars, run_backtest

PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"
INCONCLUSIVE = "INCONCLUSIVE"
RESULT_KIND = "FALSIFICATION_RESEARCH"

DISCLAIMER = (
    "Research-only falsification. Passing tests does not prove a strategy is profitable. "
    "Results are not live returns. Risk Guardian remains the final authority on any real or demo order."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ret(result: Optional[Dict[str, Any]]) -> Optional[float]:
    if not result or not result.get("ok"):
        return None
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    value = metrics.get("total_return")
    return float(value) if isinstance(value, (int, float)) else None


def _trades(result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = result.get("trades") if result else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _row(
    name: str,
    state: str,
    baseline: Any,
    challenged: Any,
    explanation: str,
    evidence: Dict[str, Any],
    metric_name: str = "total_return",
) -> Dict[str, Any]:
    degradation = None
    if isinstance(baseline, (int, float)) and isinstance(challenged, (int, float)):
        degradation = float(baseline) - float(challenged)
    return {
        "test": name,
        "state": state,
        "baseline_metric_name": metric_name,
        "baseline_metric": baseline,
        "challenged_metric": challenged,
        "performance_degradation": degradation,
        "explanation": explanation,
        "evidence": evidence,
        "timestamp": _now(),
        "research_only": True,
        "live_trading": False,
        "risk_guardian_overridden": False,
    }


def _run(
    bars: Sequence[Any],
    *,
    strategy: str,
    symbol: str,
    initial_capital: float,
    position_size: float,
    spy_bars: Optional[Sequence[Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    return run_backtest(
        bars=bars,
        strategy=strategy,
        symbol=symbol,
        initial_capital=initial_capital,
        position_size=position_size,
        spy_bars=spy_bars,
        **kwargs,
    )


def _test_look_ahead(baseline, bars, **kw) -> Dict[str, Any]:
    leaked = _run(bars, look_ahead=True, **kw)
    base_r, leak_r = _ret(baseline), _ret(leaked)
    if base_r is None or leak_r is None:
        return _row("look_ahead_bias", INCONCLUSIVE, base_r, leak_r, "Not enough data to compare strict vs look-ahead fills.", {"leaked_ok": bool(leaked.get("ok"))})
    if leak_r > base_r + 0.01:
        return _row(
            "look_ahead_bias",
            FAIL,
            base_r,
            leak_r,
            "Allowing the current bar close in the signal improved return. Reported edge may depend on look-ahead.",
            {"delta": leak_r - base_r},
        )
    if leak_r > base_r + 0.002:
        return _row("look_ahead_bias", WARNING, base_r, leak_r, "Small look-ahead improvement. Treat reported performance as an upper bound.", {"delta": leak_r - base_r})
    return _row("look_ahead_bias", PASS, base_r, leak_r, "Look-ahead (signal on current close) did not materially inflate return versus the strict engine.", {"delta": leak_r - base_r})


def _test_data_leakage(baseline, bars, **kw) -> Dict[str, Any]:
    leaked = _run(bars, fill_on="close", **kw)
    base_r, leak_r = _ret(baseline), _ret(leaked)
    if base_r is None or leak_r is None:
        return _row("data_leakage", INCONCLUSIVE, base_r, leak_r, "Could not compare open-fill vs close-fill leakage.", {})
    if leak_r > base_r + 0.01:
        return _row("data_leakage", FAIL, base_r, leak_r, "Filling at the same-bar close beat open-fill. Results may leak same-bar information.", {"delta": leak_r - base_r})
    if leak_r > base_r + 0.002:
        return _row("data_leakage", WARNING, base_r, leak_r, "Close-fill modestly beat open-fill. Same-bar leakage risk remains.", {"delta": leak_r - base_r})
    return _row("data_leakage", PASS, base_r, leak_r, "Same-bar close fills did not inflate results versus next-event open fills.", {"delta": leak_r - base_r})


def _test_train_test(bars, **kw) -> Dict[str, Any]:
    history = normalize_bars(bars)
    if len(history) < 40:
        return _row("train_test_contamination", INCONCLUSIVE, None, None, "Need at least 40 bars to split in-sample and out-of-sample.", {"bar_count": len(history)})
    cut = int(len(history) * 0.7)
    ins = _run(history[:cut], **kw)
    oos = _run(history[cut:], **kw)
    ins_r, oos_r = _ret(ins), _ret(oos)
    if ins_r is None or oos_r is None:
        return _row("train_test_contamination", INCONCLUSIVE, ins_r, oos_r, "In-sample or out-of-sample run was unavailable.", {"cut": cut})
    if ins_r - oos_r > 0.08:
        return _row("train_test_contamination", FAIL, ins_r, oos_r, "In-sample return far exceeded out-of-sample return. Possible train/test contamination or overfit.", {"cut": cut})
    if ins_r - oos_r > 0.03:
        return _row("train_test_contamination", WARNING, ins_r, oos_r, "Out-of-sample degraded versus in-sample. Do not generalize the full-sample result.", {"cut": cut})
    return _row("train_test_contamination", PASS, ins_r, oos_r, "Out-of-sample return was not severely worse than in-sample. This still does not prove profitability.", {"cut": cut})


def _test_survivorship(baseline, symbol: str, bars) -> Dict[str, Any]:
    history = normalize_bars(bars)
    base_r = _ret(baseline)
    if len(history) < 5:
        return _row("survivorship_bias_risk", INCONCLUSIVE, base_r, None, "Insufficient history to discuss survivorship.", {})
    return _row(
        "survivorship_bias_risk",
        WARNING,
        base_r,
        None,
        f"{symbol} is a single currently listed series. Delisted names are absent, so survivorship bias is not controlled.",
        {"universe": "single_symbol", "bar_count": len(history)},
        metric_name="total_return",
    )


def _test_random(baseline, bars, mode: str, **kw) -> Dict[str, Any]:
    name = "randomized_entries" if mode == "entries" else "randomized_signals"
    rand = _run(bars, random_mode=mode, rng_seed=42, **kw)
    base_r, rand_r = _ret(baseline), _ret(rand)
    if base_r is None or rand_r is None:
        return _row(name, INCONCLUSIVE, base_r, rand_r, "Randomized challenge could not be scored.", {"random_trades": len(_trades(rand))})
    if base_r <= rand_r + 0.005:
        return _row(name, FAIL, base_r, rand_r, "Strategy return was not better than a randomized policy. Skill is not established.", {"random_trades": len(_trades(rand))})
    if base_r <= rand_r + 0.02:
        return _row(name, WARNING, base_r, rand_r, "Strategy only modestly beat random. Treat the edge as unproven.", {"random_trades": len(_trades(rand))})
    return _row(name, PASS, base_r, rand_r, "Strategy beat this randomized policy on total return. Random still does not prove future profit.", {"random_trades": len(_trades(rand))})


def _test_buy_hold(baseline) -> Dict[str, Any]:
    bh = baseline.get("buy_and_hold") if isinstance(baseline.get("buy_and_hold"), dict) else {}
    base_r = _ret(baseline)
    bh_r = bh.get("total_return")
    bh_r = float(bh_r) if isinstance(bh_r, (int, float)) else None
    if base_r is None or bh_r is None:
        return _row("buy_and_hold_comparison", INCONCLUSIVE, base_r, bh_r, "Buy-and-hold comparison unavailable.", {})
    if base_r + 0.005 < bh_r:
        return _row("buy_and_hold_comparison", FAIL, base_r, bh_r, "Strategy underperformed same-symbol buy-and-hold. Timing skill is not supported.", {})
    if base_r < bh_r:
        return _row("buy_and_hold_comparison", WARNING, base_r, bh_r, "Strategy slightly lagged buy-and-hold.", {})
    return _row("buy_and_hold_comparison", PASS, base_r, bh_r, "Strategy beat or matched buy-and-hold in this sample only. Not proof of profit.", {})


def _test_spy(baseline) -> Dict[str, Any]:
    spy = baseline.get("spy_comparison") if isinstance(baseline.get("spy_comparison"), dict) else None
    base_r = _ret(baseline)
    spy_r = spy.get("total_return") if spy else None
    spy_r = float(spy_r) if isinstance(spy_r, (int, float)) else None
    if spy_r is None:
        return _row("spy_comparison", INCONCLUSIVE, base_r, None, "SPY comparison series was not available. No prices were fabricated.", {})
    if base_r is None:
        return _row("spy_comparison", INCONCLUSIVE, None, spy_r, "Baseline return missing.", {})
    if base_r + 0.005 < spy_r:
        return _row("spy_comparison", FAIL, base_r, spy_r, "Strategy underperformed SPY buy-and-hold over the same window.", {"spy_label": spy.get("label")})
    if base_r < spy_r:
        return _row("spy_comparison", WARNING, base_r, spy_r, "Strategy slightly lagged SPY buy-and-hold.", {})
    return _row("spy_comparison", PASS, base_r, spy_r, "Strategy beat or matched SPY in this sample only. Not proof of profit.", {})


def _test_cost_shift(name: str, baseline, challenged, fail_text: str, warn_text: str, pass_text: str) -> Dict[str, Any]:
    base_r, ch_r = _ret(baseline), _ret(challenged)
    if base_r is None or ch_r is None:
        return _row(name, INCONCLUSIVE, base_r, ch_r, "Cost challenge could not be scored.", {})
    if base_r > 0 and ch_r <= 0:
        return _row(name, FAIL, base_r, ch_r, fail_text, {})
    if (base_r - ch_r) > 0.03:
        return _row(name, WARNING, base_r, ch_r, warn_text, {"degradation": base_r - ch_r})
    return _row(name, PASS, base_r, ch_r, pass_text, {"degradation": base_r - ch_r})


def _test_parameters(baseline, bars, **kw) -> Dict[str, Any]:
    strategy = str(kw.get("strategy") or "")
    base_r = _ret(baseline)
    variants: List[Dict[str, Any]] = []
    if strategy == "sma_crossover":
        grid = [{"fast": 5, "slow": 20}, {"fast": 10, "slow": 30}, {"fast": 15, "slow": 40}]
    elif strategy == "rsi_mean_reversion":
        grid = [{"rsi_buy": 20, "rsi_sell": 80}, {"rsi_buy": 30, "rsi_sell": 70}, {"rsi_buy": 40, "rsi_sell": 60}]
    else:
        return _row("parameter_sensitivity", INCONCLUSIVE, base_r, None, "No parameter grid for this strategy. Buy-and-hold has no tunable signal parameters.", {"strategy": strategy})
    returns = []
    for params in grid:
        result = _run(bars, strategy_params=params, **kw)
        value = _ret(result)
        variants.append({"params": params, "total_return": value})
        if value is not None:
            returns.append(value)
    if len(returns) < 2 or base_r is None:
        return _row("parameter_sensitivity", INCONCLUSIVE, base_r, None, "Not enough parameter outcomes to compare.", {"variants": variants})
    challenged = min(returns)
    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in returns}
    if len(signs) > 1:
        return _row("parameter_sensitivity", FAIL, base_r, challenged, "Parameter changes flipped the sign of returns. The baseline is fragile to specification.", {"variants": variants})
    if max(returns) - min(returns) > 0.05:
        return _row("parameter_sensitivity", WARNING, base_r, challenged, "Returns moved substantially across nearby parameters.", {"variants": variants})
    return _row("parameter_sensitivity", PASS, base_r, challenged, "Nearby parameters produced similar return signs. Still not proof of a robust edge.", {"variants": variants})


def _test_position_size(baseline, bars, **kw) -> Dict[str, Any]:
    small = _run(bars, **{**kw, "position_size": 0.05})
    large = _run(bars, **{**kw, "position_size": 0.25})
    s_r, l_r = _ret(small), _ret(large)
    base_r = _ret(baseline)
    if None in (s_r, l_r, base_r):
        return _row("position_size_sensitivity", INCONCLUSIVE, base_r, l_r, "Position-size challenge unavailable.", {})
    if s_r > 0 and l_r <= 0:
        return _row("position_size_sensitivity", FAIL, s_r, l_r, "Larger size (still inside Risk Guardian 30% cap) erased a positive small-size result.", {"small": 0.05, "large": 0.25, "max_exposure": RiskGuardian.MAX_PORTFOLIO_EXPOSURE})
    if abs(l_r - s_r) > 0.05:
        return _row("position_size_sensitivity", WARNING, s_r, l_r, "Return changed materially with position size. Capacity and friction matter.", {"small": 0.05, "large": 0.25})
    return _row("position_size_sensitivity", PASS, s_r, l_r, "Position size changes did not reverse the sample outcome. Risk Guardian exposure cap still applies.", {"small": 0.05, "large": 0.25})


def _test_windows(bars, **kw) -> Dict[str, Any]:
    history = normalize_bars(bars)
    if len(history) < 30:
        return _row("historical_date_windows", INCONCLUSIVE, None, None, "Need at least 30 bars for window tests.", {"bar_count": len(history)})
    mid = len(history) // 2
    first = _run(history[:mid], **kw)
    second = _run(history[mid:], **kw)
    a, b = _ret(first), _ret(second)
    if a is None or b is None:
        return _row("historical_date_windows", INCONCLUSIVE, a, b, "A date window could not be scored.", {"mid": mid})
    if (a > 0 and b < 0) or (a < 0 and b > 0):
        return _row("historical_date_windows", FAIL, a, b, "First-half and second-half returns have opposite signs. The full-sample result is window-dependent.", {"mid": mid})
    if abs(a - b) > 0.05:
        return _row("historical_date_windows", WARNING, a, b, "Return differed across historical windows.", {"mid": mid})
    return _row("historical_date_windows", PASS, a, b, "Both windows agreed in sign. Agreement is not proof of profit.", {"mid": mid})


def _test_remove_trade(baseline, which: str) -> Dict[str, Any]:
    trades = _trades(baseline)
    name = "remove_best_trades" if which == "best" else "remove_worst_trades"
    if len(trades) < 2:
        return _row(name, INCONCLUSIVE, _ret(baseline), None, "Not enough closed trades to remove outliers.", {"trade_count": len(trades)})
    pnls = [float(t["pnl"]) for t in trades if isinstance(t.get("pnl"), (int, float))]
    if len(pnls) < 2:
        return _row(name, INCONCLUSIVE, _ret(baseline), None, "Trade PnL missing.", {})
    drop = max(pnls) if which == "best" else min(pnls)
    remaining = list(pnls)
    remaining.remove(drop)
    base_sum = sum(pnls)
    ch_sum = sum(remaining)
    if which == "best" and base_sum > 0 and ch_sum <= 0:
        return _row(name, FAIL, base_sum, ch_sum, "Removing the single best trade eliminated the entire sample profit. Results are luck-concentrated.", {"removed_pnl": drop}, metric_name="sum_trade_pnl")
    if which == "worst" and base_sum <= 0 and ch_sum > 0:
        return _row(name, WARNING, base_sum, ch_sum, "Removing the worst trade flipped the sample from loss to profit. Outlier-sensitive.", {"removed_pnl": drop}, metric_name="sum_trade_pnl")
    if which == "best" and (base_sum - ch_sum) > abs(base_sum) * 0.5 and base_sum > 0:
        return _row(name, WARNING, base_sum, ch_sum, "A large share of profit came from the best trade.", {"removed_pnl": drop}, metric_name="sum_trade_pnl")
    return _row(name, PASS, base_sum, ch_sum, "Outlier removal did not reverse the sample conclusion. Still not proof of profit.", {"removed_pnl": drop}, metric_name="sum_trade_pnl")


def _regime_split(bars: Sequence[Any], kind: str) -> Dict[str, List]:
    history = normalize_bars(bars)
    if kind == "market":
        start = history[0].close
        bull = [b for b in history if b.close >= start]
        bear = [b for b in history if b.close < start]
        return {"bull": bull, "bear": bear}
    rets = []
    for i in range(1, len(history)):
        prev = history[i - 1].close
        if prev > 0:
            rets.append(abs(history[i].close / prev - 1.0))
    if not rets:
        return {"high_vol": [], "low_vol": []}
    ordered = sorted(rets)
    cut = ordered[len(ordered) // 2]
    high = [history[i] for i in range(1, len(history)) if abs(history[i].close / history[i - 1].close - 1.0) >= cut]
    low = [history[i] for i in range(1, len(history)) if abs(history[i].close / history[i - 1].close - 1.0) < cut]
    return {"high_vol": high, "low_vol": low}


def _test_regimes(bars, kind: str, **kw) -> Dict[str, Any]:
    name = "market_regimes" if kind == "market" else "volatility_regimes"
    groups = _regime_split(bars, kind)
    scored = {}
    for label, subset in groups.items():
        if len(subset) < 8:
            scored[label] = None
        else:
            scored[label] = _ret(_run(subset, **kw))
    values = [v for v in scored.values() if v is not None]
    if len(values) < 2:
        return _row(name, INCONCLUSIVE, None, None, "A regime subset was too small to backtest without fabricating bars.", {"scores": scored})
    if min(values) < 0 < max(values):
        return _row(name, FAIL, max(values), min(values), "The strategy only worked in one regime of this sample. Full-sample results hide regime failure.", {"scores": scored})
    if max(values) - min(values) > 0.05:
        return _row(name, WARNING, max(values), min(values), "Performance differed across regimes.", {"scores": scored})
    return _row(name, PASS, max(values), min(values), "Regime subsets agreed in sign. This is not a live edge.", {"scores": scored})


def _test_monte_carlo(baseline) -> Dict[str, Any]:
    trades = _trades(baseline)
    pnls = [float(t["pnl"]) for t in trades if isinstance(t.get("pnl"), (int, float))]
    base_sum = sum(pnls) if pnls else None
    if len(pnls) < 3:
        return _row("monte_carlo_trade_order", INCONCLUSIVE, base_sum, None, "Need at least 3 closed trades for Monte Carlo reshuffles.", {"trade_count": len(pnls)}, metric_name="sum_trade_pnl")
    rng = random.Random(42)
    terminals = []
    for _ in range(200):
        sample = [pnls[rng.randrange(len(pnls))] for _ in range(len(pnls))]
        terminals.append(sum(sample))
    terminals.sort()
    p05 = terminals[max(0, int(0.05 * len(terminals)) - 1)]
    frac_pos = sum(1 for x in terminals if x > 0) / len(terminals)
    if base_sum is not None and base_sum > 0 and p05 <= 0:
        return _row("monte_carlo_trade_order", FAIL, base_sum, p05, "Bootstrap 5th percentile of reshuffled trade PnL is <= 0. Sample profit is consistent with luck.", {"p05": p05, "frac_positive": frac_pos, "sims": 200}, metric_name="sum_trade_pnl")
    if frac_pos < 0.6:
        return _row("monte_carlo_trade_order", WARNING, base_sum, p05, "Fewer than 60% of reshuffles stayed profitable. Edge is unstable under trade resampling.", {"p05": p05, "frac_positive": frac_pos, "sims": 200}, metric_name="sum_trade_pnl")
    return _row("monte_carlo_trade_order", PASS, base_sum, p05, "Most trade-order reshuffles stayed profitable in this sample. Resampling is not a live proof.", {"p05": p05, "frac_positive": frac_pos, "sims": 200}, metric_name="sum_trade_pnl")


def _overall(tests: List[Dict[str, Any]]) -> str:
    states = [str(t.get("state")) for t in tests]
    if FAIL in states:
        return FAIL
    if WARNING in states:
        return WARNING
    if states and all(s == INCONCLUSIVE for s in states):
        return INCONCLUSIVE
    if PASS in states:
        return PASS
    return INCONCLUSIVE


def run_falsification(
    *,
    bars: Sequence[Any],
    strategy: str,
    symbol: str,
    initial_capital: float = 100_000.0,
    position_size: float = 0.10,
    start_date: str = "",
    end_date: str = "",
    spy_bars: Optional[Sequence[Any]] = None,
    commission_per_trade: float = 1.0,
    slippage_bps: float = 5.0,
) -> Dict[str, Any]:
    shared = {
        "strategy": strategy,
        "symbol": symbol,
        "initial_capital": initial_capital,
        "position_size": position_size,
    }
    baseline = _run(
        bars,
        spy_bars=spy_bars,
        commission_per_trade=commission_per_trade,
        slippage_bps=slippage_bps,
        **shared,
    )
    tests = [
        _test_look_ahead(baseline, bars, **shared),
        _test_data_leakage(baseline, bars, **shared),
        _test_train_test(bars, **shared),
        _test_survivorship(baseline, symbol, bars),
        _test_random(baseline, bars, "entries", **shared),
        _test_random(baseline, bars, "signals", **shared),
        _test_buy_hold(baseline),
        _test_spy(baseline),
        _test_cost_shift(
            "transaction_cost_sensitivity",
            baseline,
            _run(bars, commission_per_trade=max(10.0, commission_per_trade * 10), slippage_bps=slippage_bps, **shared),
            "A 10x commission flipped a positive sample to a non-positive one. Edge does not survive frictions.",
            "Higher commissions materially reduced return.",
            "Higher commissions did not reverse the sample outcome.",
        ),
        _test_cost_shift(
            "slippage_sensitivity",
            baseline,
            _run(bars, commission_per_trade=commission_per_trade, slippage_bps=max(50.0, slippage_bps * 10), **shared),
            "High slippage flipped the sample from profit to non-profit.",
            "Higher slippage materially reduced return.",
            "Higher slippage did not reverse the sample outcome.",
        ),
        _test_cost_shift(
            "spread_cost_sensitivity",
            baseline,
            _run(bars, commission_per_trade=commission_per_trade, slippage_bps=slippage_bps, spread_bps=20.0, **shared),
            "Adding 20bp spread cost flipped the sample from profit to non-profit.",
            "Spread costs materially reduced return.",
            "Spread costs did not reverse the sample outcome.",
        ),
        _test_parameters(baseline, bars, **shared),
        _test_position_size(baseline, bars, **shared),
        _test_windows(bars, **shared),
        _test_remove_trade(baseline, "best"),
        _test_remove_trade(baseline, "worst"),
        _test_regimes(bars, "market", **shared),
        _test_regimes(bars, "vol", **shared),
        _test_monte_carlo(baseline),
    ]
    counts = {
        "total_tests": len(tests),
        "passed_tests": sum(1 for t in tests if t["state"] == PASS),
        "failed_tests": sum(1 for t in tests if t["state"] == FAIL),
        "warnings": sum(1 for t in tests if t["state"] == WARNING),
        "inconclusive_tests": sum(1 for t in tests if t["state"] == INCONCLUSIVE),
    }
    overall = _overall(tests)
    return {
        "ok": bool(baseline.get("ok")),
        "result_kind": RESULT_KIND,
        "result_label": "FALSIFICATION RESEARCH",
        "research_only": True,
        "live_trading": False,
        "live_returns": False,
        "risk_guardian_overridden": False,
        "risk_guardian_is_final_authority": True,
        "proven_profitable": False,
        "disclaimer": DISCLAIMER,
        "symbol": symbol.upper(),
        "strategy": strategy,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "position_size": position_size,
        "overall_state": overall,
        "summary": counts,
        "tests": tests,
        "baseline_backtest": {
            "ok": baseline.get("ok"),
            "result_kind": baseline.get("result_kind"),
            "metrics": baseline.get("metrics"),
            "buy_and_hold": baseline.get("buy_and_hold"),
            "spy_comparison": baseline.get("spy_comparison"),
            "number_of_trades": (baseline.get("metrics") or {}).get("number_of_trades"),
            "live_returns": False,
        },
        "timestamp": _now(),
        "notes": DISCLAIMER,
    }
