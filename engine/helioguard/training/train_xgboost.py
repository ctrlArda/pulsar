from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from helioguard.analysis import compute_dst_proxy, compute_magnetic_latitude, estimate_kp_from_solar_wind
from helioguard.config import settings
from helioguard.predictor import EXTENDED_FEATURE_COLUMNS, FEATURE_COLUMNS, build_feature_frame, quantile_model_paths


DEFAULT_CALM_BIAS_PENALTY = 2.8
DEFAULT_MAX_CALM_BIAS_PENALTY = 5.0
IMPUTATION_SPECS = {
    "bz": {"default": 0.0, "lower": -80.0, "upper": 80.0},
    "bt": {"default": 5.0, "lower": 0.0, "upper": 120.0},
    "speed": {"default": 400.0, "lower": 250.0, "upper": 3000.0},
    "density": {"default": 5.0, "lower": 0.01, "upper": 500.0},
    "temperature": {"default": 100000.0, "lower": 1000.0, "upper": 5e7},
}


def _impute_physical_series(series: pd.Series, *, default: float, lower: float | None = None, upper: float | None = None) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    clean = clean.interpolate(method="time", limit_direction="both")
    if clean.dropna().empty:
        clean = clean.fillna(default)
    else:
        median = float(clean.median())
        clean = clean.ffill().bfill().fillna(median).fillna(default)
    if lower is not None or upper is not None:
        clean = clean.clip(lower=lower, upper=upper)
    return clean.astype(float)


def _load_inputs(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("Egitim icin en az bir CSV gerekli.")
    data = pd.concat(frames, ignore_index=True)
    rename_map = {
        "time": "time_tag",
        "timestamp": "time_tag",
        "bz_gsm": "bz",
        "bt": "bt",
        "velocity": "speed",
        "kp": "kp_index",
        "estimated_kp": "estimated_kp",
        "dst": "dst_index",
        "dst_proxy": "dst_index",
        "sym_h_index": "dst_index",
    }
    data = data.rename(columns=rename_map)
    required = {"time_tag", "bz", "speed", "density", "temperature"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Egitim CSV kolonlari eksik: {sorted(missing)}")
    data["time_tag"] = pd.to_datetime(data["time_tag"], utc=True, errors="coerce")
    data = data.sort_values("time_tag").dropna(subset=["time_tag"]).reset_index(drop=True)
    if "bt" not in data.columns:
        data["bt"] = np.nan
    data = data.set_index("time_tag")
    for column, spec in IMPUTATION_SPECS.items():
        data[column] = _impute_physical_series(
            data[column],
            default=float(spec["default"]),
            lower=float(spec["lower"]) if spec["lower"] is not None else None,
            upper=float(spec["upper"]) if spec["upper"] is not None else None,
        )
    data = data.reset_index()
    derived_estimated_kp = data.apply(
        lambda row: estimate_kp_from_solar_wind(
            float(row["bz"]),
            float(row["speed"]),
            float(row["density"]),
        ),
        axis=1,
    )
    if "estimated_kp" not in data.columns:
        data["estimated_kp"] = derived_estimated_kp
    else:
        data["estimated_kp"] = pd.to_numeric(data["estimated_kp"], errors="coerce").fillna(derived_estimated_kp)
    if "kp_index" not in data.columns:
        data["kp_index"] = data["estimated_kp"]
    else:
        data["kp_index"] = pd.to_numeric(data["kp_index"], errors="coerce").fillna(data["estimated_kp"])
    derived_dst_index = data.apply(
        lambda row: compute_dst_proxy(
            float(row["bz"]),
            float(row["speed"]),
            float(row["density"]),
        ),
        axis=1,
    )
    if "dst_index" not in data.columns:
        data["dst_index"] = derived_dst_index
    else:
        data["dst_index"] = pd.to_numeric(data["dst_index"], errors="coerce").fillna(derived_dst_index)
    return data


def _infer_horizon_steps(frame: pd.DataFrame) -> tuple[int, float]:
    deltas = frame["time_tag"].diff().dropna().dt.total_seconds().div(60.0)
    cadence_minutes = float(deltas[(deltas > 0) & (deltas < 180)].median()) if not deltas.empty else 1.0
    if cadence_minutes <= 0 or pd.isna(cadence_minutes):
        cadence_minutes = 1.0
    return max(int(round(60.0 / cadence_minutes)), 1), cadence_minutes


def _build_dst_target(frame: pd.DataFrame, horizon_steps: int) -> pd.Series:
    future_bz = pd.to_numeric(frame["bz"], errors="coerce").shift(-horizon_steps).ffill().bfill().fillna(0.0)
    future_speed = pd.to_numeric(frame["speed"], errors="coerce").shift(-horizon_steps).ffill().bfill().fillna(400.0)
    future_density = pd.to_numeric(frame["density"], errors="coerce").shift(-horizon_steps).ffill().bfill().fillna(5.0)
    future_dst_index = pd.to_numeric(frame["dst_index"], errors="coerce").shift(-horizon_steps)
    derived_future_dst = [
        compute_dst_proxy(float(bz), float(speed), float(density))
        for bz, speed, density in zip(future_bz, future_speed, future_density, strict=False)
    ]
    return future_dst_index.fillna(pd.Series(derived_future_dst, index=frame.index))


def _sample_weights(target: pd.Series, safety_first: bool = False) -> pd.Series:
    severity = target.apply(lambda value: max(abs(min(float(value), 0.0)), 0.0))
    normalized = (severity / 120.0).clip(lower=0.0, upper=3.0)
    base = 1.0 + normalized
    if safety_first:
        return base + (severity >= 80.0).astype(float) * 1.2 + (severity >= 150.0).astype(float) * 1.0
    return base


def _calm_bias_penalty(labels: np.ndarray, penalty_min: float, penalty_max: float) -> np.ndarray:
    severity = np.clip(np.abs(np.minimum(labels, 0.0)), 0.0, 250.0)
    return penalty_min + (severity / 250.0) * (penalty_max - penalty_min)


def _make_safety_first_objective(penalty_min: float, penalty_max: float):
    def _objective(preds: np.ndarray, dtrain: xgb.DMatrix) -> tuple[np.ndarray, np.ndarray]:
        labels = dtrain.get_label()
        residual = preds - labels
        # For Dst, a positive residual means the model predicted a calmer, less-negative storm than reality.
        danger_penalty = _calm_bias_penalty(labels, penalty_min, penalty_max)
        penalty = np.where(residual > 0.0, danger_penalty, 1.0 + (np.abs(np.minimum(labels, 0.0)) / 300.0))
        grad = penalty * residual
        hess = penalty.astype(np.float32)
        return grad.astype(np.float32), hess

    return _objective


def _make_safety_first_metric(penalty_min: float, penalty_max: float):
    def _metric(preds: np.ndarray, dtrain: xgb.DMatrix) -> tuple[str, float]:
        labels = dtrain.get_label()
        residual = preds - labels
        penalty = np.where(residual > 0.0, _calm_bias_penalty(labels, penalty_min, penalty_max), 1.0)
        value = float(np.mean(np.abs(residual) * penalty))
        return "safety_mae", value

    return _metric


def _top_feature_gains(model: xgb.Booster, limit: int = 8) -> list[dict[str, float | str]]:
    raw_scores = model.get_score(importance_type="gain")
    ordered = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"feature": feature, "gain": round(float(gain), 4)} for feature, gain in ordered]


def _train_main_model(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    feature_columns: list[str],
    use_asymmetric_loss: bool,
    penalty_min: float = DEFAULT_CALM_BIAS_PENALTY,
    penalty_max: float = DEFAULT_MAX_CALM_BIAS_PENALTY,
    num_boost_round: int = 220,
) -> tuple[xgb.Booster, pd.Series]:
    params = {
        "objective": "reg:squarederror",
        "eta": 0.04,
        "max_depth": 5,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 2,
        "seed": 42,
        "eval_metric": "mae",
        "tree_method": "hist",
        "max_bin": 256,
    }
    dtrain = xgb.DMatrix(
        x_train,
        label=y_train,
        weight=_sample_weights(y_train, safety_first=use_asymmetric_loss),
        feature_names=feature_columns,
    )
    dtest = xgb.DMatrix(
        x_test,
        label=y_test,
        weight=_sample_weights(y_test, safety_first=use_asymmetric_loss),
        feature_names=feature_columns,
    ) if not x_test.empty else None
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train")] + ([(dtest, "test")] if dtest is not None else []),
        obj=_make_safety_first_objective(penalty_min, penalty_max) if use_asymmetric_loss else None,
        custom_metric=_make_safety_first_metric(penalty_min, penalty_max) if use_asymmetric_loss else None,
        early_stopping_rounds=36 if dtest is not None else None,
        verbose_eval=False,
    )
    predictions = pd.Series(model.predict(dtest), index=y_test.index) if dtest is not None else pd.Series(dtype=float)
    return model, predictions


def _train_quantile_model(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    feature_columns: list[str],
    alpha: float,
    safety_first: bool,
    num_boost_round: int = 180,
) -> tuple[xgb.Booster, pd.Series]:
    params = {
        "objective": "reg:quantileerror",
        "quantile_alpha": alpha,
        "eta": 0.035,
        "max_depth": 5,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 2,
        "seed": 42,
        "tree_method": "hist",
        "max_bin": 256,
    }
    dtrain = xgb.DMatrix(
        x_train,
        label=y_train,
        weight=_sample_weights(y_train, safety_first=safety_first),
        feature_names=feature_columns,
    )
    dtest = xgb.DMatrix(
        x_test,
        label=y_test,
        weight=_sample_weights(y_test, safety_first=safety_first),
        feature_names=feature_columns,
    ) if not x_test.empty else None
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train")] + ([(dtest, "test")] if dtest is not None else []),
        early_stopping_rounds=28 if dtest is not None else None,
        verbose_eval=False,
    )
    predictions = pd.Series(model.predict(dtest), index=y_test.index) if dtest is not None else pd.Series(dtype=float)
    return model, predictions


def _time_series_folds(n_rows: int, n_splits: int = 3, test_fraction: float = 0.1, min_train_fraction: float = 0.56) -> list[tuple[slice, slice]]:
    if n_rows < 1000:
        return []
    test_size = max(int(round(n_rows * test_fraction)), 512)
    max_train_end = n_rows - test_size
    min_train_end = max(int(round(n_rows * min_train_fraction)), test_size)
    if max_train_end <= min_train_end:
        return []
    candidate_train_ends = np.linspace(min_train_end, max_train_end, num=n_splits, dtype=int)
    folds: list[tuple[slice, slice]] = []
    seen: set[tuple[int, int]] = set()
    for train_end in candidate_train_ends:
        test_end = min(train_end + test_size, n_rows)
        if test_end <= train_end:
            continue
        key = (int(train_end), int(test_end))
        if key in seen:
            continue
        seen.add(key)
        folds.append((slice(0, int(train_end)), slice(int(train_end), int(test_end))))
    return folds


def _weighted_safety_mae(predictions: pd.Series, truth: pd.Series, penalty_min: float, penalty_max: float) -> float:
    residual = predictions.sub(truth, fill_value=0.0)
    penalties = np.where(
        residual.to_numpy() > 0.0,
        _calm_bias_penalty(truth.to_numpy(), penalty_min, penalty_max),
        1.0,
    )
    return float(np.mean(np.abs(residual.to_numpy()) * penalties))


def _cross_validate_time_series(
    features: pd.DataFrame,
    target: pd.Series,
    feature_columns: list[str],
    use_asymmetric_loss: bool,
    penalty_min: float,
    penalty_max: float,
) -> dict[str, object]:
    folds = _time_series_folds(len(features))
    if not folds:
        return {
            "cv_strategy": "expanding_window_unavailable",
            "cv_folds": [],
            "cv_mae_mean": None,
            "cv_mae_std": None,
            "cv_safety_mae_mean": None,
            "cv_safety_mae_std": None,
            "cv_dst_band_coverage_mean": None,
            "cv_dst_band_coverage_std": None,
        }

    fold_metrics: list[dict[str, float | int]] = []
    for fold_index, (train_slice, test_slice) in enumerate(folds, start=1):
        x_train = features.iloc[train_slice]
        y_train = target.iloc[train_slice]
        x_test = features.iloc[test_slice]
        y_test = target.iloc[test_slice]
        _, main_predictions = _train_main_model(
            x_train,
            y_train,
            x_test,
            y_test,
            feature_columns,
            use_asymmetric_loss,
            penalty_min=penalty_min,
            penalty_max=penalty_max,
            num_boost_round=120,
        )
        _, lower_predictions = _train_quantile_model(
            x_train,
            y_train,
            x_test,
            y_test,
            feature_columns,
            0.1,
            use_asymmetric_loss,
            num_boost_round=100,
        )
        _, upper_predictions = _train_quantile_model(
            x_train,
            y_train,
            x_test,
            y_test,
            feature_columns,
            0.9,
            use_asymmetric_loss,
            num_boost_round=100,
        )
        mae = float(main_predictions.sub(y_test, fill_value=0.0).abs().mean())
        safety_mae = _weighted_safety_mae(main_predictions, y_test, penalty_min, penalty_max)
        band_coverage = float(((y_test >= lower_predictions) & (y_test <= upper_predictions)).mean())
        fold_metrics.append(
            {
                "fold": fold_index,
                "train_rows": int(len(x_train)),
                "test_rows": int(len(x_test)),
                "mae": round(mae, 4),
                "safety_mae": round(safety_mae, 4),
                "dst_band_coverage": round(band_coverage, 4),
            }
        )

    maes = np.array([float(item["mae"]) for item in fold_metrics], dtype=float)
    safety_maes = np.array([float(item["safety_mae"]) for item in fold_metrics], dtype=float)
    coverages = np.array([float(item["dst_band_coverage"]) for item in fold_metrics], dtype=float)
    return {
        "cv_strategy": "expanding_window",
        "cv_folds": fold_metrics,
        "cv_mae_mean": round(float(maes.mean()), 4),
        "cv_mae_std": round(float(maes.std(ddof=0)), 4),
        "cv_safety_mae_mean": round(float(safety_maes.mean()), 4),
        "cv_safety_mae_std": round(float(safety_maes.std(ddof=0)), 4),
        "cv_dst_band_coverage_mean": round(float(coverages.mean()), 4),
        "cv_dst_band_coverage_std": round(float(coverages.std(ddof=0)), 4),
    }


def _optimize_penalties(
    features: pd.DataFrame,
    target: pd.Series,
    feature_columns: list[str],
) -> tuple[float, float, list[dict[str, float | str]]]:
    candidate_mins = [2.2, 2.8, 3.4]
    candidate_maxes = [4.4, 5.0, 5.8]
    search_results: list[dict[str, float | str]] = []
    best_score = math.inf
    best_pair = (DEFAULT_CALM_BIAS_PENALTY, DEFAULT_MAX_CALM_BIAS_PENALTY)
    folds = _time_series_folds(len(features), n_splits=2, test_fraction=0.08, min_train_fraction=0.62)
    if not folds:
        return best_pair[0], best_pair[1], search_results

    train_slice, test_slice = folds[-1]
    x_train = features.iloc[train_slice]
    y_train = target.iloc[train_slice]
    x_test = features.iloc[test_slice]
    y_test = target.iloc[test_slice]

    for penalty_min in candidate_mins:
        for penalty_max in candidate_maxes:
            if penalty_max <= penalty_min:
                continue
            _, predictions = _train_main_model(
                x_train,
                y_train,
                x_test,
                y_test,
                feature_columns,
                True,
                penalty_min=penalty_min,
                penalty_max=penalty_max,
                num_boost_round=110,
            )
            mae = float(predictions.sub(y_test, fill_value=0.0).abs().mean())
            safety_mae = _weighted_safety_mae(predictions, y_test, penalty_min, penalty_max)
            score = (safety_mae * 0.72) + (mae * 0.28)
            search_results.append(
                {
                    "penalty_min": penalty_min,
                    "penalty_max": penalty_max,
                    "mae": round(mae, 4),
                    "safety_mae": round(safety_mae, 4),
                    "objective_score": round(score, 4),
                    "status": "candidate",
                }
            )
            if score < best_score:
                best_score = score
                best_pair = (penalty_min, penalty_max)

    search_results = [
        {
            **item,
            "status": "selected" if item["penalty_min"] == best_pair[0] and item["penalty_max"] == best_pair[1] else item["status"],
        }
        for item in search_results
    ]
    return best_pair[0], best_pair[1], search_results


def train(
    paths: list[Path],
    output: Path,
    *,
    feature_columns: list[str] | None = None,
    use_asymmetric_loss: bool = False,
    optimize_asymmetric_loss: bool = False,
    compute_cv: bool = True,
) -> dict[str, object]:
    selected_features = feature_columns or EXTENDED_FEATURE_COLUMNS
    data = _load_inputs(paths)
    horizon_steps, cadence_minutes = _infer_horizon_steps(data)
    data["target_dst_index"] = _build_dst_target(data, horizon_steps)

    magnetic_latitude = compute_magnetic_latitude(settings.turkiye_center_lat, settings.turkiye_center_lon)
    feature_rows = []
    targets = []
    for index in range(9, len(data) - horizon_steps):
        history = data.iloc[max(0, index - 359) : index + 1][["time_tag", "bz", "bt", "speed", "density", "temperature", "estimated_kp", "dst_index"]]
        feature_rows.append(build_feature_frame(history, magnetic_latitude, settings.turkiye_center_lon, selected_features))
        targets.append(float(data.iloc[index]["target_dst_index"]))

    if not feature_rows:
        raise ValueError("Yeterli zaman penceresi yok. En az 7 saatlik gercek telemetri gerekli.")

    features = pd.concat(feature_rows, ignore_index=True)[selected_features]
    target = pd.Series(targets, name="target_dst_index")
    penalty_min = DEFAULT_CALM_BIAS_PENALTY
    penalty_max = DEFAULT_MAX_CALM_BIAS_PENALTY
    penalty_search_results: list[dict[str, float | str]] = []
    if use_asymmetric_loss and optimize_asymmetric_loss:
        penalty_min, penalty_max, penalty_search_results = _optimize_penalties(features, target, selected_features)

    cv_metadata = (
        _cross_validate_time_series(features, target, selected_features, use_asymmetric_loss, penalty_min, penalty_max)
        if compute_cv
        else {
            "cv_strategy": "skipped",
            "cv_folds": [],
            "cv_mae_mean": None,
            "cv_mae_std": None,
            "cv_safety_mae_mean": None,
            "cv_safety_mae_std": None,
            "cv_dst_band_coverage_mean": None,
            "cv_dst_band_coverage_std": None,
        }
    )
    split_index = max(int(len(features) * 0.8), 1)
    x_train = features.iloc[:split_index]
    y_train = target.iloc[:split_index]
    x_test = features.iloc[split_index:]
    y_test = target.iloc[split_index:]

    main_model, main_predictions = _train_main_model(
        x_train,
        y_train,
        x_test,
        y_test,
        selected_features,
        use_asymmetric_loss,
        penalty_min=penalty_min,
        penalty_max=penalty_max,
    )
    lower_model, lower_predictions = _train_quantile_model(x_train, y_train, x_test, y_test, selected_features, 0.1, use_asymmetric_loss)
    upper_model, upper_predictions = _train_quantile_model(x_train, y_train, x_test, y_test, selected_features, 0.9, use_asymmetric_loss)

    mae = float((main_predictions.sub(y_test, fill_value=0.0).abs().mean())) if not main_predictions.empty else 0.0
    safety_mae = (
        float(
            (
                main_predictions.sub(y_test, fill_value=0.0).abs()
                * np.where(
                    main_predictions.sub(y_test, fill_value=0.0) > 0.0,
                    _calm_bias_penalty(y_test.to_numpy(), penalty_min, penalty_max),
                    1.0,
                )
            ).mean()
        )
        if not main_predictions.empty
        else 0.0
    )
    band_coverage = (
        float(((y_test >= lower_predictions) & (y_test <= upper_predictions)).mean())
        if not lower_predictions.empty and not upper_predictions.empty
        else 0.0
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    quantile_paths = quantile_model_paths(output)
    main_model.save_model(output)
    lower_model.save_model(quantile_paths["p10"])
    upper_model.save_model(quantile_paths["p90"])

    metadata = {
        "rows": float(len(features)),
        "train_rows": float(len(x_train)),
        "test_rows": float(len(x_test)),
        "mae": round(mae, 4),
        "safety_mae": round(safety_mae, 4),
        "dst_band_coverage": round(band_coverage, 4),
        "cadence_minutes": round(cadence_minutes, 4),
        "horizon_steps": float(horizon_steps),
        "target_name": "Future Dst (+60m)",
        "target_unit": "nT",
        "calm_bias_penalty_min": penalty_min if use_asymmetric_loss else None,
        "calm_bias_penalty_max": penalty_max if use_asymmetric_loss else None,
        "experimental_context_features": selected_features == EXTENDED_FEATURE_COLUMNS,
        "experimental_asymmetric_loss": use_asymmetric_loss,
        "optimized_asymmetric_loss": optimize_asymmetric_loss if use_asymmetric_loss else False,
        "quantile_model_paths": {
            "p10": str(quantile_paths["p10"].resolve()),
            "p90": str(quantile_paths["p90"].resolve()),
        },
        "train_test_strategy": "chronological_holdout_80_20 + expanding_window_cv",
        "imputation_strategy": "time_interpolate + median fallback + physical clipping",
        "explainability_backend": "xgboost_pred_contribs",
        "physics_features": ["ey", "epsilon", "dynamic_pressure"],
        "asymmetric_penalty_search": penalty_search_results,
        "top_feature_gains": _top_feature_gains(main_model),
        "features": selected_features,
    }
    metadata.update(cv_metadata)
    output.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train HELIOGUARD on real OMNI/NOAA history with a physical Dst target.")
    parser.add_argument("inputs", nargs="+", help="One or more CSV files containing real historical telemetry.")
    parser.add_argument("--output", default=str(settings.model_path), help="Path to save the central XGBoost model JSON.")
    parser.add_argument("--base-features", action="store_true", help="Disable solar-time and solar-cycle context features.")
    parser.add_argument("--asymmetric-loss", action="store_true", help="Apply safety-first asymmetric calm-bias penalty to the central model.")
    parser.add_argument("--optimize-asymmetric-loss", action="store_true", help="Search penalty coefficients over a compact grid before final training.")
    parser.add_argument("--skip-cv", action="store_true", help="Skip expanding-window CV to speed up training on slower machines.")
    args = parser.parse_args()

    metadata = train(
        [Path(item) for item in args.inputs],
        Path(args.output),
        feature_columns=FEATURE_COLUMNS if args.base_features else EXTENDED_FEATURE_COLUMNS,
        use_asymmetric_loss=args.asymmetric_loss,
        optimize_asymmetric_loss=args.optimize_asymmetric_loss,
        compute_cv=not args.skip_cv,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
