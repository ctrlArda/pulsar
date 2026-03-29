from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import xgboost as xgb

from .config import Settings
from .physics_engine import dynamic_pressure_npa

try:
    import shap  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    shap = None


SOLAR_CYCLE_25_START = datetime(2019, 12, 15, tzinfo=timezone.utc)
SOLAR_CYCLE_LENGTH_DAYS = 11 * 365.25
WINDOW_SPECS: list[tuple[str, int]] = [("10m", 10), ("60m", 60), ("360m", 360)]
WINDOW_STATS = ("last", "mean", "min", "max", "std", "slope")
WINDOWED_SIGNALS: dict[str, float] = {
    "bz": 0.0,
    "speed": 400.0,
    "density": 5.0,
    "estimated_kp": 1.0,
    "dst_index": -5.0,
}
SHORT_WINDOW_SIGNALS: dict[str, float] = {
    "bt": 5.0,
    "temperature": 100000.0,
}
PHYSICS_WINDOW_SIGNALS: dict[str, float] = {
    "ey": 0.3,
    "epsilon": 5.0,
    "dynamic_pressure": 2.0,
}
SIGNAL_LABELS = {
    "bz": "Bz",
    "bt": "Bt",
    "speed": "Solar wind speed",
    "density": "Plasma density",
    "temperature": "Temperature",
    "estimated_kp": "Estimated Kp",
    "dst_index": "Dst",
    "ey": "Solar wind Ey",
    "epsilon": "Akasofu epsilon",
    "dynamic_pressure": "Dynamic pressure",
}
WINDOW_LABELS = {
    "10m": "10m",
    "60m": "1h",
    "360m": "6h",
}
STAT_LABELS = {
    "last": "last value",
    "mean": "mean",
    "min": "minimum",
    "max": "maximum",
    "std": "volatility",
    "slope": "trend",
}


def _build_base_feature_columns() -> list[str]:
    columns = ["local_magnetic_latitude", "sample_count", "sample_count_10m", "sample_count_60m", "sample_count_360m"]
    for window_tag, _ in WINDOW_SPECS:
        for signal in WINDOWED_SIGNALS:
            for stat in WINDOW_STATS:
                columns.append(f"{signal}_{window_tag}_{stat}")
        for signal in PHYSICS_WINDOW_SIGNALS:
            for stat in WINDOW_STATS:
                columns.append(f"{signal}_{window_tag}_{stat}")
    for signal in SHORT_WINDOW_SIGNALS:
        for stat in WINDOW_STATS:
            columns.append(f"{signal}_10m_{stat}")
    return columns


BASE_FEATURE_COLUMNS = _build_base_feature_columns()
CONTEXT_FEATURE_COLUMNS = [
    "local_solar_hour",
    "local_solar_hour_sin",
    "local_solar_hour_cos",
    "is_daylight",
    "solar_cycle_progress_years",
    "solar_cycle_phase_sin",
    "solar_cycle_phase_cos",
]
FEATURE_COLUMNS = BASE_FEATURE_COLUMNS
EXTENDED_FEATURE_COLUMNS = [*BASE_FEATURE_COLUMNS, *CONTEXT_FEATURE_COLUMNS]


@dataclass(slots=True)
class FeatureContribution:
    feature: str
    label: str
    contribution: float
    direction: str


@dataclass(slots=True)
class PredictionResult:
    risk_percent: float
    risk_band_low: float | None
    risk_band_high: float | None
    lead_time_minutes: int
    predicted_dst_index: float
    predicted_dst_p10: float | None
    predicted_dst_p50: float
    predicted_dst_p90: float | None
    baseline_dst_index: float | None
    target_name: str
    target_unit: str
    feature_contributions: list[FeatureContribution]


def _normalize_timestamp(value: object) -> datetime:
    if isinstance(value, pd.Timestamp):
        timestamp = value.to_pydatetime()
    elif isinstance(value, datetime):
        timestamp = value
    else:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(parsed):
            return datetime.now(timezone.utc)
        timestamp = parsed.to_pydatetime()
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def compute_local_solar_hour(observed_at: object, longitude: float) -> float:
    timestamp = _normalize_timestamp(observed_at)
    utc_hour = timestamp.hour + (timestamp.minute / 60.0) + (timestamp.second / 3600.0)
    return float((utc_hour + (longitude / 15.0)) % 24.0)


def solar_cycle_features(observed_at: object) -> dict[str, float]:
    timestamp = _normalize_timestamp(observed_at)
    elapsed_days = max((timestamp - SOLAR_CYCLE_25_START).total_seconds() / 86400.0, 0.0)
    progress_years = elapsed_days / 365.25
    phase = (elapsed_days / SOLAR_CYCLE_LENGTH_DAYS) % 1.0
    angle = phase * 2.0 * math.pi
    return {
        "solar_cycle_progress_years": float(progress_years),
        "solar_cycle_phase_sin": float(math.sin(angle)),
        "solar_cycle_phase_cos": float(math.cos(angle)),
    }


def _estimate_cadence_minutes(history: pd.DataFrame) -> float:
    if history.empty or "time_tag" not in history.columns:
        return 1.0
    times = pd.to_datetime(history["time_tag"], utc=True, errors="coerce").dropna()
    deltas = times.diff().dropna().dt.total_seconds().div(60.0)
    cadence = float(deltas[(deltas > 0) & (deltas < 180)].median()) if not deltas.empty else 1.0
    if not cadence or math.isnan(cadence) or cadence <= 0.0:
        return 1.0
    return cadence


def _window_slice(history: pd.DataFrame, minutes: int, cadence_minutes: float) -> pd.DataFrame:
    if history.empty:
        return history
    rows = max(int(round(minutes / max(cadence_minutes, 1.0))), 1)
    return history.tail(rows)


def _series_features(series: pd.Series, prefix: str, default_val: float = 0.0) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").replace([math.inf, -math.inf], pd.NA)
    clean = clean.interpolate(limit_direction="both")
    median = float(clean.median()) if not clean.dropna().empty else default_val
    clean = clean.ffill().bfill().fillna(median).fillna(default_val)
    if clean.empty:
        return {
            f"{prefix}_last": default_val,
            f"{prefix}_mean": default_val,
            f"{prefix}_min": default_val,
            f"{prefix}_max": default_val,
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


def compute_solar_wind_ey_mvm(speed_kms: pd.Series, bz_nt: pd.Series) -> pd.Series:
    speed = pd.to_numeric(speed_kms, errors="coerce").astype(float)
    bz = pd.to_numeric(bz_nt, errors="coerce").astype(float)
    southward_bz = bz.clip(upper=0.0).abs()
    return speed * southward_bz * 1e-3


def compute_akasofu_epsilon_gw(speed_kms: pd.Series, bt_nt: pd.Series, bz_nt: pd.Series) -> pd.Series:
    speed_m_s = pd.to_numeric(speed_kms, errors="coerce").astype(float) * 1000.0
    bt_t = pd.to_numeric(bt_nt, errors="coerce").astype(float).clip(lower=0.0) * 1e-9
    bz_nt_series = pd.to_numeric(bz_nt, errors="coerce").astype(float)
    bt_nt_series = pd.to_numeric(bt_nt, errors="coerce").astype(float).clip(lower=1e-6)
    cosine = (bz_nt_series / bt_nt_series).clip(lower=-1.0, upper=1.0)
    clock_angle = cosine.apply(math.acos)
    sin_term = clock_angle.apply(lambda value: math.sin(value / 2.0) ** 4)
    l0_m = 7.0 * 6371_000.0
    mu0 = 4.0 * math.pi * 1e-7
    epsilon_w = (speed_m_s * (bt_t**2) * sin_term * (l0_m**2)) / mu0
    return epsilon_w / 1e9


def compute_dynamic_pressure_series(speed_kms: pd.Series, density_cm3: pd.Series) -> pd.Series:
    speed = pd.to_numeric(speed_kms, errors="coerce").astype(float)
    density = pd.to_numeric(density_cm3, errors="coerce").astype(float)
    return pd.Series(
        [dynamic_pressure_npa(float(n), float(v)) for n, v in zip(density, speed, strict=False)],
        index=speed.index,
        dtype=float,
    )


def build_feature_frame(
    history: pd.DataFrame,
    local_magnetic_latitude: float,
    local_longitude: float = 35.0,
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    selected_columns = feature_columns or FEATURE_COLUMNS
    observed_at = history["time_tag"].iloc[-1] if not history.empty and "time_tag" in history.columns else datetime.now(timezone.utc)
    local_solar_hour = compute_local_solar_hour(observed_at, local_longitude)
    cadence_minutes = _estimate_cadence_minutes(history)
    features: dict[str, float] = {
        "local_magnetic_latitude": float(local_magnetic_latitude),
        "local_solar_hour": float(local_solar_hour),
        "local_solar_hour_sin": float(math.sin((local_solar_hour / 24.0) * 2.0 * math.pi)),
        "local_solar_hour_cos": float(math.cos((local_solar_hour / 24.0) * 2.0 * math.pi)),
        "is_daylight": 1.0 if 6.0 <= local_solar_hour <= 18.0 else 0.0,
        "sample_count": float(len(_window_slice(history, 10, cadence_minutes))),
    }
    features.update(solar_cycle_features(observed_at))

    for window_tag, minutes in WINDOW_SPECS:
        window = _window_slice(history, minutes, cadence_minutes)
        features[f"sample_count_{window_tag}"] = float(len(window))
        for signal, default_val in WINDOWED_SIGNALS.items():
            features.update(_series_features(window.get(signal, pd.Series(dtype=float)), f"{signal}_{window_tag}", default_val=default_val))
        ey_series = compute_solar_wind_ey_mvm(window.get("speed", pd.Series(dtype=float)), window.get("bz", pd.Series(dtype=float)))
        epsilon_series = compute_akasofu_epsilon_gw(
            window.get("speed", pd.Series(dtype=float)),
            window.get("bt", pd.Series(dtype=float)),
            window.get("bz", pd.Series(dtype=float)),
        )
        dynamic_pressure_series = compute_dynamic_pressure_series(
            window.get("speed", pd.Series(dtype=float)),
            window.get("density", pd.Series(dtype=float)),
        )
        derived_signals = {
            "ey": ey_series,
            "epsilon": epsilon_series,
            "dynamic_pressure": dynamic_pressure_series,
        }
        for signal, default_val in PHYSICS_WINDOW_SIGNALS.items():
            features.update(_series_features(derived_signals[signal], f"{signal}_{window_tag}", default_val=default_val))

    short_window = _window_slice(history, 10, cadence_minutes)
    for signal, default_val in SHORT_WINDOW_SIGNALS.items():
        features.update(_series_features(short_window.get(signal, pd.Series(dtype=float)), f"{signal}_10m", default_val=default_val))

    frame = pd.DataFrame([features])
    for column in selected_columns:
        if column not in frame.columns:
            frame[column] = 0.0
    return frame[selected_columns]


def quantile_model_paths(model_path: Path) -> dict[str, Path]:
    return {
        "p10": model_path.with_suffix(".p10.json"),
        "p50": model_path.with_suffix(".p50.json"),
        "p90": model_path.with_suffix(".p90.json"),
    }


def explain_feature_name(feature: str) -> str:
    if feature in {"local_magnetic_latitude", "local_solar_hour", "local_solar_hour_sin", "local_solar_hour_cos", "is_daylight"}:
        return {
            "local_magnetic_latitude": "Local magnetic latitude",
            "local_solar_hour": "Local solar time",
            "local_solar_hour_sin": "Local solar-time phase (sin)",
            "local_solar_hour_cos": "Local solar-time phase (cos)",
            "is_daylight": "Daylight flag",
        }[feature]
    if feature.startswith("solar_cycle_"):
        return {
            "solar_cycle_progress_years": "Solar-cycle progress",
            "solar_cycle_phase_sin": "Solar-cycle phase (sin)",
            "solar_cycle_phase_cos": "Solar-cycle phase (cos)",
        }.get(feature, feature)
    if feature.startswith("sample_count"):
        return {
            "sample_count": "10m sample count",
            "sample_count_10m": "10m sample count",
            "sample_count_60m": "1h sample count",
            "sample_count_360m": "6h sample count",
        }.get(feature, feature)
    parts = feature.split("_")
    stat = parts[-1]
    if len(parts) >= 3 and parts[-2] in WINDOW_LABELS:
        window_tag = parts[-2]
        signal = "_".join(parts[:-2])
        return f"{SIGNAL_LABELS.get(signal, signal)} {WINDOW_LABELS[window_tag]} {STAT_LABELS.get(stat, stat)}"
    return feature


class PredictiveEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model: xgb.Booster | None = None
        self.quantile_models: dict[str, xgb.Booster] = {}
        self.metadata: dict[str, object] = {}
        self.feature_columns: list[str] = FEATURE_COLUMNS
        self.explainability_backend = "xgboost_pred_contribs"
        self._shap_explainer = None
        self.reload()

    @property
    def available(self) -> bool:
        return self.model is not None

    def reload(self) -> None:
        if not self.settings.model_path.exists():
            self.model = None
            self.quantile_models = {}
            self.metadata = {}
            self.feature_columns = FEATURE_COLUMNS
            self.explainability_backend = "xgboost_pred_contribs"
            self._shap_explainer = None
            return

        model = xgb.Booster()
        model.load_model(self.settings.model_path)
        self.model = model
        self.quantile_models = {}
        if self.settings.model_meta_path.exists():
            self.metadata = json.loads(self.settings.model_meta_path.read_text(encoding="utf-8"))
            configured_columns = self.metadata.get("features")
            if isinstance(configured_columns, list) and all(isinstance(item, str) for item in configured_columns):
                self.feature_columns = configured_columns
            else:
                self.feature_columns = FEATURE_COLUMNS
            self.explainability_backend = str(self.metadata.get("explainability_backend", "xgboost_pred_contribs"))
        else:
            self.metadata = {}
            self.feature_columns = FEATURE_COLUMNS
            self.explainability_backend = "xgboost_pred_contribs"

        configured_paths = self.metadata.get("quantile_model_paths", {})
        default_paths = quantile_model_paths(self.settings.model_path)
        for key in ("p10", "p50", "p90"):
            candidate = None
            if isinstance(configured_paths, dict) and configured_paths.get(key):
                candidate = Path(str(configured_paths[key]))
                if not candidate.is_absolute():
                    candidate = self.settings.model_path.parent / candidate
            else:
                candidate = default_paths[key]
            if candidate.exists():
                quantile_model = xgb.Booster()
                quantile_model.load_model(candidate)
                self.quantile_models[key] = quantile_model

        if "p50" in self.quantile_models:
            self.model = self.quantile_models["p50"]
        self._shap_explainer = None
        if shap is not None and self.model is not None:
            try:
                self._shap_explainer = shap.TreeExplainer(self.model)
                self.explainability_backend = "shap_treeexplainer"
            except Exception:
                self._shap_explainer = None
                self.explainability_backend = str(self.metadata.get("explainability_backend", "xgboost_pred_contribs"))

    def _predict_scalar(self, model: xgb.Booster, matrix: xgb.DMatrix) -> float:
        return float(model.predict(matrix)[0])

    def _feature_contributions(self, matrix: xgb.DMatrix, feature_frame: pd.DataFrame | None = None) -> tuple[float | None, list[FeatureContribution]]:
        if self.model is None:
            return None, []
        if self._shap_explainer is not None and feature_frame is not None:
            try:
                values = self._shap_explainer.shap_values(feature_frame[self.feature_columns])
                base_value = self._shap_explainer.expected_value
                if hasattr(values, "shape") and len(values) > 0:
                    row = values[0]
                    feature_rows = []
                    for feature_name, contribution in zip(self.feature_columns, row, strict=False):
                        contribution_value = float(contribution)
                        if abs(contribution_value) < 0.05:
                            continue
                        feature_rows.append(
                            FeatureContribution(
                                feature=feature_name,
                                label=explain_feature_name(feature_name),
                                contribution=round(contribution_value, 3),
                                direction="worsening" if contribution_value < 0 else "calming",
                            )
                        )
                    feature_rows.sort(key=lambda item: abs(item.contribution), reverse=True)
                    baseline = float(base_value[0] if hasattr(base_value, "__len__") else base_value)
                    return round(baseline, 3), feature_rows[:5]
            except Exception:
                pass
        contributions = self.model.predict(matrix, pred_contribs=True)
        if contributions.size == 0:
            return None, []
        row = contributions[0]
        baseline = float(row[-1])
        feature_rows = []
        for feature_name, contribution in zip(self.feature_columns, row[:-1], strict=False):
            contribution_value = float(contribution)
            if abs(contribution_value) < 0.05:
                continue
            feature_rows.append(
                FeatureContribution(
                    feature=feature_name,
                    label=explain_feature_name(feature_name),
                    contribution=round(contribution_value, 3),
                    direction="worsening" if contribution_value < 0 else "calming",
                )
            )
        feature_rows.sort(key=lambda item: abs(item.contribution), reverse=True)
        return round(baseline, 3), feature_rows[:5]

    def predict(self, history: pd.DataFrame, local_magnetic_latitude: float) -> PredictionResult | None:
        if self.model is None or history.empty:
            return None
        features = build_feature_frame(history, local_magnetic_latitude, self.settings.turkiye_center_lon, self.feature_columns)
        matrix = xgb.DMatrix(features, feature_names=self.feature_columns)
        predicted_dst_p50 = self._predict_scalar(self.model, matrix)
        predicted_dst_p10 = self._predict_scalar(self.quantile_models["p10"], matrix) if "p10" in self.quantile_models else None
        predicted_dst_p90 = self._predict_scalar(self.quantile_models["p90"], matrix) if "p90" in self.quantile_models else None
        cadence_minutes = float(self.metadata.get("cadence_minutes", 1.0) or 1.0)
        horizon_steps = float(self.metadata.get("horizon_steps", 60.0) or 60.0)
        lead_time_minutes = max(int(round(cadence_minutes * horizon_steps)), 1)
        baseline_dst_index, feature_contributions = self._feature_contributions(matrix, features)
        return PredictionResult(
            risk_percent=0.0,
            risk_band_low=None,
            risk_band_high=None,
            lead_time_minutes=lead_time_minutes,
            predicted_dst_index=round(predicted_dst_p50, 2),
            predicted_dst_p10=round(predicted_dst_p10, 2) if predicted_dst_p10 is not None else None,
            predicted_dst_p50=round(predicted_dst_p50, 2),
            predicted_dst_p90=round(predicted_dst_p90, 2) if predicted_dst_p90 is not None else None,
            baseline_dst_index=baseline_dst_index,
            target_name=str(self.metadata.get("target_name", "Future Dst (+60m)")),
            target_unit=str(self.metadata.get("target_unit", "nT")),
            feature_contributions=feature_contributions,
        )
