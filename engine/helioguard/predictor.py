from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import xgboost as xgb

from .config import Settings


FEATURE_COLUMNS = [
    "local_magnetic_latitude",
    "sample_count",
    "bz_last",
    "bz_mean",
    "bz_min",
    "bz_max",
    "bz_std",
    "bz_slope",
    "bt_last",
    "bt_mean",
    "bt_max",
    "speed_last",
    "speed_mean",
    "speed_max",
    "speed_slope",
    "density_last",
    "density_mean",
    "density_max",
    "temperature_last",
    "temperature_mean",
    "temperature_max",
    "estimated_kp_last",
    "estimated_kp_mean",
    "estimated_kp_max",
]


@dataclass(slots=True)
class PredictionResult:
    risk_percent: float
    lead_time_minutes: int


def _series_features(series: pd.Series, prefix: str) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").ffill().bfill().fillna(0.0)
    if clean.empty:
        return {
            f"{prefix}_last": 0.0,
            f"{prefix}_mean": 0.0,
            f"{prefix}_min": 0.0,
            f"{prefix}_max": 0.0,
            f"{prefix}_std": 0.0,
            f"{prefix}_slope": 0.0,
        }
    return {
        f"{prefix}_last": float(clean.iloc[-1]),
        f"{prefix}_mean": float(clean.mean()),
        f"{prefix}_min": float(clean.min()),
        f"{prefix}_max": float(clean.max()),
        f"{prefix}_std": float(clean.std(ddof=0)),
        f"{prefix}_slope": float((clean.iloc[-1] - clean.iloc[0]) / max(len(clean) - 1, 1)),
    }


def build_feature_frame(history: pd.DataFrame, local_magnetic_latitude: float) -> pd.DataFrame:
    window = history.tail(10).copy()
    features: dict[str, float] = {
        "local_magnetic_latitude": float(local_magnetic_latitude),
        "sample_count": float(len(window)),
    }
    features.update(_series_features(window.get("bz", pd.Series(dtype=float)), "bz"))
    features.update(_series_features(window.get("bt", pd.Series(dtype=float)), "bt"))
    features.update(_series_features(window.get("speed", pd.Series(dtype=float)), "speed"))
    features.update(_series_features(window.get("density", pd.Series(dtype=float)), "density"))
    features.update(_series_features(window.get("temperature", pd.Series(dtype=float)), "temperature"))
    features.update(_series_features(window.get("estimated_kp", pd.Series(dtype=float)), "estimated_kp"))
    frame = pd.DataFrame([features])
    for column in FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0
    return frame[FEATURE_COLUMNS]


class PredictiveEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model: xgb.Booster | None = None
        self.metadata: dict[str, object] = {}
        self.reload()

    @property
    def available(self) -> bool:
        return self.model is not None

    def reload(self) -> None:
        if not self.settings.model_path.exists():
            self.model = None
            self.metadata = {}
            return

        model = xgb.Booster()
        model.load_model(self.settings.model_path)
        self.model = model
        if self.settings.model_meta_path.exists():
            self.metadata = json.loads(self.settings.model_meta_path.read_text(encoding="utf-8"))

    def predict(self, history: pd.DataFrame, local_magnetic_latitude: float) -> PredictionResult | None:
        if self.model is None or history.empty:
            return None
        features = build_feature_frame(history, local_magnetic_latitude)
        matrix = xgb.DMatrix(features, feature_names=FEATURE_COLUMNS)
        prediction = float(self.model.predict(matrix)[0])
        return PredictionResult(risk_percent=max(0.0, min(100.0, prediction)), lead_time_minutes=60)
