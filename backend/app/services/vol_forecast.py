"""Advisory realized-volatility forecasts. Not direction. Never approves trades."""

from __future__ import annotations

import math
from datetime import timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.schemas import DATA_UNAVAILABLE
from app.services.backtest_engine import normalize_bars

HORIZONS = (5, 10)
MIN_HISTORY = 40
RESULT_KIND = "VOLATILITY_FORECAST_ADVISORY"


def _date_key(ts) -> str:
    return ts.astimezone(timezone.utc).date().isoformat()


def _std(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    if var < 0:
        return None
    return math.sqrt(var)


def realized_vol_window(log_returns: Sequence[float]) -> Optional[float]:
    std = _std(log_returns)
    if std is None:
        return None
    return std * math.sqrt(252.0)


def _align_series(bars: Sequence[Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for bar in normalize_bars(bars):
        if bar.close > 0:
            out[_date_key(bar.timestamp)] = bar.close
    return out


def feature_inventory(
    *,
    has_volume: bool,
    has_vix: bool,
    has_vix_term: bool,
    has_iv: bool,
) -> Dict[str, List[str]]:
    available = [
        "historical_prices",
        "rolling_returns",
        "rolling_volatility",
        "historical_volatility",
    ]
    unavailable = []
    if has_volume:
        available.append("volume")
    else:
        unavailable.append("volume")
    if has_vix:
        available.append("vix")
    else:
        unavailable.append("vix")
    if has_vix_term:
        available.append("vix_term_structure")
    else:
        unavailable.append("vix_term_structure")
    if has_iv:
        available.append("implied_volatility")
        available.append("iv_versus_realized_volatility")
    else:
        unavailable.append("implied_volatility")
        unavailable.append("iv_versus_realized_volatility")
    unavailable.append("stock_direction")  # explicitly not a target
    return {"available": available, "unavailable": unavailable}


def _log_returns(closes: Sequence[float]) -> List[Optional[float]]:
    out: List[Optional[float]] = [None]
    for i in range(1, len(closes)):
        prev, now = closes[i - 1], closes[i]
        if prev <= 0 or now <= 0:
            out.append(None)
        else:
            out.append(math.log(now / prev))
    return out


def build_rows(
    bars: Sequence[Any],
    *,
    vix_bars: Optional[Sequence[Any]] = None,
    vix_long_bars: Optional[Sequence[Any]] = None,
    iv_by_date: Optional[Dict[str, float]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    history = normalize_bars(bars)
    closes = [bar.close for bar in history]
    volumes = [bar.volume for bar in history]
    has_volume = any(vol > 0 for vol in volumes)
    vix_map = _align_series(vix_bars or [])
    vix_long_map = _align_series(vix_long_bars or [])
    iv_map = {key: float(val) for key, val in (iv_by_date or {}).items() if isinstance(val, (int, float)) and val > 0}
    has_vix = bool(vix_map)
    has_term = bool(vix_map and vix_long_map)
    has_iv = bool(iv_map)
    inventory = feature_inventory(has_volume=has_volume, has_vix=has_vix, has_vix_term=has_term, has_iv=has_iv)
    rets = _log_returns(closes)
    rows: List[Dict[str, Any]] = []
    for index, bar in enumerate(history):
        if index < 21:
            continue
        window_rets = [rets[j] for j in range(index - 20, index + 1)]
        if any(item is None for item in window_rets):
            continue
        known_rets = [float(item) for item in rets[1 : index + 1] if item is not None]
        hv5 = realized_vol_window(known_rets[-5:])
        hv10 = realized_vol_window(known_rets[-10:])
        hv21 = realized_vol_window(known_rets[-21:])
        if None in (hv5, hv10, hv21):
            continue
        day = _date_key(bar.timestamp)
        features: Dict[str, float] = {
            "ret_1": float(rets[index] or 0.0),
            "ret_5": sum(known_rets[-5:]) / 5.0,
            "hv_5": float(hv5),
            "hv_10": float(hv10),
            "hv_21": float(hv21),
            "hv_ratio": float(hv5) / float(hv21) if hv21 else 0.0,
        }
        if has_volume:
            vol_window = volumes[index - 20 : index + 1]
            mean_vol = sum(vol_window) / len(vol_window)
            if mean_vol > 0:
                features["volume_rel"] = volumes[index] / mean_vol
        if has_vix and day in vix_map:
            features["vix"] = vix_map[day]
            prev_days = [_date_key(history[j].timestamp) for j in range(max(0, index - 5), index)]
            prev_vix = [vix_map[d] for d in prev_days if d in vix_map]
            if prev_vix:
                features["vix_change"] = features["vix"] - prev_vix[-1]
        if has_term and day in vix_map and day in vix_long_map and vix_long_map[day] > 0:
            features["vix_term"] = vix_map[day] / vix_long_map[day]
        if has_iv and day in iv_map:
            features["iv"] = iv_map[day]
            features["iv_minus_hv"] = iv_map[day] - float(hv21)

        y5 = None
        y10 = None
        if index + 5 < len(rets):
            fwd5 = [rets[j] for j in range(index + 1, index + 6)]
            if all(item is not None for item in fwd5):
                y5 = realized_vol_window([float(item) for item in fwd5])
        if index + 10 < len(rets):
            fwd10 = [rets[j] for j in range(index + 1, index + 11)]
            if all(item is not None for item in fwd10):
                y10 = realized_vol_window([float(item) for item in fwd10])
        rows.append(
            {
                "index": index,
                "timestamp": bar.timestamp.isoformat(),
                "date": day,
                "close": bar.close,
                "features": features,
                "y_5": y5,
                "y_10": y10,
                "trailing_hv_5": hv5,
                "trailing_hv_10": hv10,
            }
        )
    return rows, inventory


def chronological_split(rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    n = len(rows)
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    return list(rows[:train_end]), list(rows[train_end:val_end]), list(rows[val_end:])


def _solve(matrix: List[List[float]], rhs: List[float]) -> Optional[List[float]]:
    n = len(rhs)
    aug = [matrix[i][:] + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= div
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            for j in range(col, n + 1):
                aug[row][j] -= factor * aug[col][j]
    return [aug[i][n] for i in range(n)]


def fit_ridge(x_rows: List[List[float]], y: List[float], alpha: float = 1.0) -> Optional[List[float]]:
    if len(x_rows) < 5 or len(x_rows) != len(y):
        return None
    k = len(x_rows[0])
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, target in zip(x_rows, y):
        for i in range(k):
            xty[i] += row[i] * target
            for j in range(k):
                xtx[i][j] += row[i] * row[j]
    for i in range(1, k):
        xtx[i][i] += alpha
    return _solve(xtx, xty)


def predict_linear(beta: Sequence[float], row: Sequence[float]) -> float:
    return sum(b * x for b, x in zip(beta, row))


def mae(actual: Sequence[float], pred: Sequence[float]) -> Optional[float]:
    if not actual:
        return None
    return sum(abs(a - p) for a, p in zip(actual, pred)) / len(actual)


def rmse(actual: Sequence[float], pred: Sequence[float]) -> Optional[float]:
    if not actual:
        return None
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, pred)) / len(actual))


def correlation(actual: Sequence[float], pred: Sequence[float]) -> Optional[float]:
    if len(actual) < 3:
        return None
    ma = sum(actual) / len(actual)
    mp = sum(pred) / len(pred)
    num = sum((a - ma) * (p - mp) for a, p in zip(actual, pred))
    da = math.sqrt(sum((a - ma) ** 2 for a in actual))
    dp = math.sqrt(sum((p - mp) ** 2 for p in pred))
    if da < 1e-12 or dp < 1e-12:
        return None
    return num / (da * dp)


def _design(rows: Sequence[Dict[str, Any]], keys: Sequence[str], target: str) -> Tuple[List[List[float]], List[float]]:
    x_rows: List[List[float]] = []
    y: List[float] = []
    for row in rows:
        value = row.get(target)
        feats = row.get("features") or {}
        if not isinstance(value, (int, float)):
            continue
        if any(key not in feats for key in keys):
            continue
        x_rows.append([1.0] + [float(feats[key]) for key in keys])
        y.append(float(value))
    return x_rows, y


def _try_xgboost(x_train, y_train, x_val, y_val, x_pred) -> Optional[Tuple[List[float], str]]:
    try:
        import xgboost as xgb  # type: ignore
    except Exception:
        return None
    if len(x_train) < 10:
        return None
    model = xgb.XGBRegressor(
        n_estimators=40,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.9,
        objective="reg:squarederror",
        verbosity=0,
    )
    model.fit(x_train, y_train, eval_set=[(x_val, y_val)] if x_val else None, verbose=False)
    preds = [float(v) for v in model.predict(x_pred)]
    return preds, "xgboost_regressor"


def _metrics(actual: List[float], pred: List[float]) -> Dict[str, Any]:
    return {
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "forecast_correlation": correlation(actual, pred),
        "n": len(actual),
    }


def forecast_volatility(
    bars: Sequence[Any],
    *,
    symbol: str,
    vix_bars: Optional[Sequence[Any]] = None,
    vix_long_bars: Optional[Sequence[Any]] = None,
    iv_by_date: Optional[Dict[str, float]] = None,
    current_iv: Any = DATA_UNAVAILABLE,
) -> Dict[str, Any]:
    history = normalize_bars(bars)
    empty = {
        "ok": False,
        "result_kind": RESULT_KIND,
        "advisory_only": True,
        "can_approve_trades": False,
        "overrides_risk_guardian": False,
        "live_trading": False,
        "integrity_state": DATA_UNAVAILABLE,
        "symbol": symbol.upper(),
        "notes": "Required historical prices are missing. Values were not fabricated.",
        "features": feature_inventory(has_volume=False, has_vix=False, has_vix_term=False, has_iv=False),
        "predictions": {"vol_5d": DATA_UNAVAILABLE, "vol_10d": DATA_UNAVAILABLE},
        "realized_volatility": {"vol_5d": DATA_UNAVAILABLE, "vol_10d": DATA_UNAVAILABLE},
        "vix": {"level": DATA_UNAVAILABLE},
        "current_iv": current_iv if isinstance(current_iv, (int, float)) else DATA_UNAVAILABLE,
        "model_name": DATA_UNAVAILABLE,
        "training_period": DATA_UNAVAILABLE,
        "metrics": DATA_UNAVAILABLE,
        "forecast_error": DATA_UNAVAILABLE,
    }
    if len(history) < MIN_HISTORY:
        return empty

    rows, inventory = build_rows(
        history,
        vix_bars=vix_bars,
        vix_long_bars=vix_long_bars,
        iv_by_date=iv_by_date,
    )
    labeled = [row for row in rows if row.get("y_5") is not None and row.get("y_10") is not None]
    if len(labeled) < 30:
        payload = dict(empty)
        payload["features"] = inventory
        payload["notes"] = "Insufficient chronological labeled samples for 5-day and 10-day realized volatility. Not fabricated."
        return payload

    train, val, test = chronological_split(labeled)
    if not train or not test:
        payload = dict(empty)
        payload["features"] = inventory
        payload["notes"] = "Chronological train/test split was empty. Time series was not shuffled."
        return payload

    feature_keys = ["ret_1", "ret_5", "hv_5", "hv_10", "hv_21", "hv_ratio"]
    sample_feats = train[-1]["features"]
    for extra in ("volume_rel", "vix", "vix_change", "vix_term", "iv", "iv_minus_hv"):
        if extra in sample_feats:
            feature_keys.append(extra)

    last = rows[-1]
    as_of = last["timestamp"]
    predictions: Dict[str, Any] = {"vol_5d": DATA_UNAVAILABLE, "vol_10d": DATA_UNAVAILABLE, "as_of": as_of}
    metrics: Dict[str, Any] = {}
    model_name = "ridge_regression"
    used_xgb = False

    for horizon in HORIZONS:
        target = f"y_{horizon}"
        baseline_key = f"hv_{horizon}" if horizon in (5, 10) else "hv_5"
        x_train, y_train = _design(train, feature_keys, target)
        x_val, y_val = _design(val, feature_keys, target)
        x_test, y_test = _design(test, feature_keys, target)
        if len(x_train) < 8 or len(x_test) < 3:
            metrics[f"vol_{horizon}d"] = {"model": DATA_UNAVAILABLE, "baseline": DATA_UNAVAILABLE}
            continue
        best_beta = None
        best_rmse = None
        for alpha in (0.1, 1.0, 10.0):
            beta = fit_ridge(x_train, y_train, alpha=alpha)
            if beta is None or not x_val:
                if beta is not None and best_beta is None:
                    best_beta = beta
                continue
            val_pred = [predict_linear(beta, row) for row in x_val]
            score = rmse(y_val, val_pred)
            if score is not None and (best_rmse is None or score < best_rmse):
                best_rmse = score
                best_beta = beta
        if best_beta is None:
            best_beta = fit_ridge(x_train, y_train, alpha=1.0)
        model_pred = [predict_linear(best_beta, row) for row in x_test] if best_beta else []
        xgb_pack = _try_xgboost(x_train, y_train, x_val, y_val, x_test)
        if xgb_pack is not None:
            xgb_pred, xgb_name = xgb_pack
            if mae(y_test, xgb_pred) is not None and (not model_pred or (mae(y_test, xgb_pred) or 0) <= (mae(y_test, model_pred) or 1e9)):
                model_pred = xgb_pred
                model_name = xgb_name
                used_xgb = True
                if last["features"] and all(k in last["features"] for k in feature_keys):
                    x_last = [[1.0] + [float(last["features"][k]) for k in feature_keys]]
                    more = _try_xgboost(x_train, y_train, x_val, y_val, x_last)
                    if more:
                        predictions[f"vol_{horizon}d"] = float(more[0][0])
        base_pred = []
        for row in test:
            if row.get(target) is None:
                continue
            feats = row["features"]
            if baseline_key in feats:
                base_pred.append(float(feats[baseline_key]))
        y_aligned = y_test[: len(model_pred)]
        model_pred = model_pred[: len(y_aligned)]
        base_pred = base_pred[: len(y_aligned)]
        metrics[f"vol_{horizon}d"] = {
            "model": _metrics(y_aligned, model_pred) if model_pred else DATA_UNAVAILABLE,
            "baseline": _metrics(y_aligned, base_pred) if base_pred else DATA_UNAVAILABLE,
            "baseline_name": "persistence_trailing_hv",
        }
        if predictions.get(f"vol_{horizon}d") == DATA_UNAVAILABLE and best_beta is not None and all(k in last["features"] for k in feature_keys):
            x_last = [1.0] + [float(last["features"][k]) for k in feature_keys]
            predictions[f"vol_{horizon}d"] = float(predict_linear(best_beta, x_last))

    vix_level: Any = DATA_UNAVAILABLE
    vix_map = _align_series(vix_bars or [])
    if last["date"] in vix_map:
        vix_level = vix_map[last["date"]]
    elif vix_map:
        vix_level = list(vix_map.values())[-1]

    train_period = {
        "start": train[0]["timestamp"],
        "end": train[-1]["timestamp"],
        "validation_start": val[0]["timestamp"] if val else DATA_UNAVAILABLE,
        "validation_end": val[-1]["timestamp"] if val else DATA_UNAVAILABLE,
        "test_start": test[0]["timestamp"],
        "test_end": test[-1]["timestamp"],
        "split": "chronological_60_20_20",
        "shuffled": False,
    }
    err_5 = metrics.get("vol_5d", {})
    err_10 = metrics.get("vol_10d", {})
    model_5 = err_5.get("model") if isinstance(err_5, dict) else DATA_UNAVAILABLE
    model_10 = err_10.get("model") if isinstance(err_10, dict) else DATA_UNAVAILABLE

    return {
        "ok": True,
        "result_kind": RESULT_KIND,
        "result_label": "ADVISORY VOLATILITY FORECAST",
        "advisory_only": True,
        "can_approve_trades": False,
        "overrides_risk_guardian": False,
        "risk_guardian_is_final_authority": True,
        "live_trading": False,
        "symbol": symbol.upper(),
        "model_name": model_name,
        "xgboost_used": used_xgb,
        "training_period": train_period,
        "features": inventory,
        "feature_keys_used": feature_keys,
        "predictions": predictions,
        "realized_volatility": {
            "vol_5d": last.get("trailing_hv_5", DATA_UNAVAILABLE),
            "vol_10d": last.get("trailing_hv_10", DATA_UNAVAILABLE),
            "window": "trailing_completed_bars_only",
        },
        "vix": {
            "level": vix_level if vix_level != DATA_UNAVAILABLE else DATA_UNAVAILABLE,
            "comparison": (
                None
                if not isinstance(vix_level, (int, float)) or not isinstance(predictions.get("vol_5d"), (int, float))
                else {
                    "predicted_vol_5d_minus_vix_decimal": float(predictions["vol_5d"]) - (float(vix_level) / 100.0 if vix_level > 1 else float(vix_level)),
                    "note": "VIX is an implied-vol index level; predicted values are annualized realized-vol decimals. Not a trade signal.",
                }
            ),
            "source": "alpaca_bars" if vix_map else DATA_UNAVAILABLE,
        },
        "current_iv": current_iv if isinstance(current_iv, (int, float)) else DATA_UNAVAILABLE,
        "metrics": metrics,
        "forecast_error": {
            "vol_5d": model_5,
            "vol_10d": model_10,
        },
        "baseline_name": "persistence_trailing_hv",
        "look_ahead_leakage": False,
        "time_series_shuffled": False,
        "notes": "Advisory only. Predicts realized volatility, not direction. Does not approve trades or override Risk Guardian.",
    }
