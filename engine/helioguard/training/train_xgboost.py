from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import xgboost as xgb

from helioguard.analysis import compute_local_risk_percent, compute_magnetic_latitude, estimate_kp_from_solar_wind
from helioguard.config import settings
from helioguard.predictor import FEATURE_COLUMNS, build_feature_frame


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
    }
    data = data.rename(columns=rename_map)
    required = {"time_tag", "bz", "speed", "density", "temperature"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Egitim CSV kolonlari eksik: {sorted(missing)}")
    data["time_tag"] = pd.to_datetime(data["time_tag"], utc=True, errors="coerce")
    data = data.sort_values("time_tag").dropna(subset=["time_tag"]).reset_index(drop=True)
    data["bz"] = pd.to_numeric(data["bz"], errors="coerce").fillna(0.0)
    data["speed"] = pd.to_numeric(data["speed"], errors="coerce").fillna(0.0)
    data["density"] = pd.to_numeric(data["density"], errors="coerce").fillna(0.0)
    data["temperature"] = pd.to_numeric(data["temperature"], errors="coerce").fillna(0.0)
    if "bt" not in data.columns:
        data["bt"] = 0.0
    data["bt"] = pd.to_numeric(data["bt"], errors="coerce").fillna(0.0)
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
    return data


def _infer_horizon_steps(frame: pd.DataFrame) -> tuple[int, float]:
    deltas = frame["time_tag"].diff().dropna().dt.total_seconds().div(60.0)
    cadence_minutes = float(deltas[(deltas > 0) & (deltas < 180)].median()) if not deltas.empty else 1.0
    if cadence_minutes <= 0 or pd.isna(cadence_minutes):
        cadence_minutes = 1.0
    return max(int(round(60.0 / cadence_minutes)), 1), cadence_minutes


def _build_target(frame: pd.DataFrame, horizon_steps: int) -> pd.Series:
    magnetic_latitude = compute_magnetic_latitude(settings.turkiye_center_lat, settings.turkiye_center_lon)
    future_bz = pd.to_numeric(frame["bz"], errors="coerce").shift(-horizon_steps).ffill().fillna(0.0)
    future_speed = pd.to_numeric(frame["speed"], errors="coerce").shift(-horizon_steps).ffill().fillna(0.0)
    future_density = pd.to_numeric(frame["density"], errors="coerce").shift(-horizon_steps).ffill().fillna(0.0)
    shifted_estimated_kp = pd.to_numeric(frame["estimated_kp"], errors="coerce").shift(-horizon_steps)
    derived_future_kp = [
        estimate_kp_from_solar_wind(float(bz), float(speed), float(density))
        for bz, speed, density in zip(future_bz, future_speed, future_density, strict=False)
    ]
    future_estimated_kp = shifted_estimated_kp.fillna(pd.Series(derived_future_kp, index=frame.index))
    future_early_detection = (future_bz <= -10.0) & (future_speed >= 500.0)
    risk = pd.Series(
        [
            compute_local_risk_percent(
                estimated_kp=float(estimated_kp),
                bz=float(bz),
                speed=float(speed),
                density=float(density),
                magnetic_latitude=magnetic_latitude,
                early_detection=bool(early_detection),
            )
            for estimated_kp, bz, speed, density, early_detection in zip(
                future_estimated_kp,
                future_bz,
                future_speed,
                future_density,
                future_early_detection,
                strict=False,
            )
        ],
        index=frame.index,
    )
    return risk.clip(lower=0.0, upper=100.0)


def train(paths: list[Path], output: Path) -> dict[str, float]:
    data = _load_inputs(paths)
    data["bt"] = pd.to_numeric(data.get("bt", 0.0), errors="coerce").fillna(0.0)
    data["bz"] = pd.to_numeric(data["bz"], errors="coerce").fillna(0.0)
    data["speed"] = pd.to_numeric(data["speed"], errors="coerce").fillna(0.0)
    data["density"] = pd.to_numeric(data["density"], errors="coerce").fillna(0.0)
    data["temperature"] = pd.to_numeric(data["temperature"], errors="coerce").fillna(0.0)
    horizon_steps, cadence_minutes = _infer_horizon_steps(data)
    data["target"] = _build_target(data, horizon_steps)

    magnetic_latitude = compute_magnetic_latitude(settings.turkiye_center_lat, settings.turkiye_center_lon)
    feature_rows = []
    targets = []
    for index in range(9, len(data) - horizon_steps):
        history = data.iloc[index - 9 : index + 1][["time_tag", "bz", "bt", "speed", "density", "temperature", "estimated_kp"]]
        feature_rows.append(build_feature_frame(history, magnetic_latitude))
        targets.append(float(data.iloc[index]["target"]))

    if not feature_rows:
        raise ValueError("Yeterli zaman penceresi yok. En az 70 satirlik gercek telemetri gerekli.")

    features = pd.concat(feature_rows, ignore_index=True)[FEATURE_COLUMNS]
    target = pd.Series(targets)
    split_index = max(int(len(features) * 0.8), 1)
    x_train = features.iloc[:split_index]
    y_train = target.iloc[:split_index]
    x_test = features.iloc[split_index:]
    y_test = target.iloc[split_index:]

    params = {
        "objective": "reg:squarederror",
        "eta": 0.045,
        "max_depth": 5,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 2,
        "seed": 42,
    }
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_COLUMNS)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_names=FEATURE_COLUMNS) if not x_test.empty else None
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=350,
        evals=[(dtrain, "train")] + ([(dtest, "test")] if dtest is not None else []),
        verbose_eval=False,
    )

    predictions = pd.Series(model.predict(dtest), index=y_test.index) if dtest is not None else pd.Series(dtype=float)
    mae = float((predictions.sub(y_test, fill_value=0.0).abs().mean())) if not predictions.empty else 0.0
    output.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(output)
    metadata = {
        "rows": float(len(features)),
        "train_rows": float(len(x_train)),
        "test_rows": float(len(x_test)),
        "mae": round(mae, 4),
        "cadence_minutes": round(cadence_minutes, 4),
        "horizon_steps": float(horizon_steps),
        "features": FEATURE_COLUMNS,
    }
    output.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train HELIOGUARD XGBoost predictor on real OMNI/NOAA CSV data.")
    parser.add_argument("inputs", nargs="+", help="One or more CSV files containing real historical telemetri.")
    parser.add_argument("--output", default=str(settings.model_path), help="Path to save xgboost model JSON.")
    args = parser.parse_args()

    metadata = train([Path(item) for item in args.inputs], Path(args.output))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
