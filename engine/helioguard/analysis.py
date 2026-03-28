from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from .config import Settings
from .data_sources import SpaceWeatherBundle
from .predictor import PredictiveEngine
from .schemas import CrisisAlert, HeatCell, KpTrendPoint, SopAction, TelemetrySnapshot, ThreatImpact


TURKIYE_REGIONS: list[tuple[str, float, float, float]] = [
    ("Trakya", 41.05, 27.75, 0.97),
    ("Marmara", 40.99, 29.12, 1.00),
    ("Ege", 38.42, 27.14, 0.88),
    ("Bati Akdeniz", 36.89, 30.70, 0.82),
    ("Cukurova", 37.00, 35.32, 0.92),
    ("Ic Anadolu", 39.93, 32.85, 0.86),
    ("Orta Karadeniz", 41.29, 36.33, 0.91),
    ("Dogu Anadolu", 39.90, 41.27, 0.94),
    ("Guneydogu", 37.07, 37.38, 0.90),
    ("Van Havzasi", 38.49, 43.38, 0.89),
]


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00").replace(" ", "T")
    if normalized.endswith(".000"):
        normalized = f"{normalized}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def estimate_kp_from_solar_wind(bz: float, speed: float, density: float) -> float:
    southward_factor = clamp(abs(min(bz, 0.0)) / 18.0, 0.0, 1.0)
    speed_factor = clamp((speed - 320.0) / 780.0, 0.0, 1.0)
    density_factor = clamp(density / 20.0, 0.0, 1.0)
    coupling = (southward_factor * 0.58) + (speed_factor * 0.27) + (density_factor * 0.15)
    if bz > 0:
        coupling *= 0.55
    if speed < 380.0 and abs(bz) < 6.0:
        coupling *= 0.65
    return clamp(1.0 + (coupling * 8.0), 0.0, 9.0)


def compute_local_risk_percent(
    estimated_kp: float,
    bz: float,
    speed: float,
    density: float,
    magnetic_latitude: float,
    early_detection: bool,
) -> float:
    return clamp(
        ((estimated_kp / 9.0) * 42.0)
        + clamp(abs(min(bz, 0.0)) / 20.0, 0.0, 1.0) * 24.0
        + clamp((speed - 350.0) / 650.0, 0.0, 1.0) * 18.0
        + clamp(density / 25.0, 0.0, 1.0) * 6.0
        + clamp((54.0 - abs(magnetic_latitude)) / 20.0, 0.0, 1.0) * 10.0
        + (8.0 if early_detection else 0.0),
        0.0,
        100.0,
    )


def classify_xray(flux: float) -> str:
    if flux >= 1e-4:
        return f"X{flux / 1e-4:.1f}"
    if flux >= 1e-5:
        return f"M{flux / 1e-5:.1f}"
    if flux >= 1e-6:
        return f"C{flux / 1e-6:.1f}"
    if flux >= 1e-7:
        return f"B{flux / 1e-7:.1f}"
    return f"A{flux / 1e-8:.1f}"


def compute_magnetic_latitude(latitude: float, longitude: float) -> float:
    try:
        from geomag import geomag

        field = geomag.GeoMag().GeoMag(latitude, longitude)
        inclination = math.radians(float(getattr(field, "dip", 0.0)))
        return math.degrees(math.atan(0.5 * math.tan(inclination)))
    except Exception:
        pole_latitude = math.radians(80.65)
        pole_longitude = math.radians(-72.68)
        lat = math.radians(latitude)
        lon = math.radians(longitude)
        cos_psi = math.sin(lat) * math.sin(pole_latitude) + math.cos(lat) * math.cos(pole_latitude) * math.cos(lon - pole_longitude)
        psi = math.acos(clamp(cos_psi, -1.0, 1.0))
        return 90.0 - math.degrees(psi)


def build_history_frame(bundle: SpaceWeatherBundle) -> pd.DataFrame:
    mag = pd.DataFrame(bundle.mag)
    plasma = pd.DataFrame(bundle.plasma)
    minute_kp = pd.DataFrame(bundle.minute_kp)

    if mag.empty or plasma.empty:
        return pd.DataFrame(columns=["time_tag", "bz", "bt", "speed", "density", "temperature", "estimated_kp"])

    mag = mag.rename(columns={"bz_gsm": "bz", "bt": "bt"})
    plasma = plasma.rename(columns={"speed": "speed", "density": "density", "temperature": "temperature"})
    if not minute_kp.empty:
        minute_kp = minute_kp.rename(columns={"time_tag": "time_tag", "estimated_kp": "estimated_kp", "kp_index": "kp_index"})

    for frame in (mag, plasma):
        frame["time_tag"] = pd.to_datetime(frame["time_tag"], utc=True, errors="coerce")
    if not minute_kp.empty:
        minute_kp["time_tag"] = pd.to_datetime(minute_kp["time_tag"], utc=True, errors="coerce")

    merged = pd.merge_asof(
        mag.sort_values("time_tag")[["time_tag", "bz", "bt"]],
        plasma.sort_values("time_tag")[["time_tag", "speed", "density", "temperature"]],
        on="time_tag",
        direction="nearest",
        tolerance=pd.Timedelta("5min"),
    )
    if not minute_kp.empty:
        merged = pd.merge_asof(
            merged.sort_values("time_tag"),
            minute_kp.sort_values("time_tag")[["time_tag", "estimated_kp", "kp_index"]],
            on="time_tag",
            direction="nearest",
            tolerance=pd.Timedelta("5min"),
        )

    for column in ["bz", "bt", "speed", "density", "temperature"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    derived_estimated_kp = merged.apply(
        lambda row: estimate_kp_from_solar_wind(
            as_float(row.get("bz")),
            as_float(row.get("speed")),
            as_float(row.get("density")),
        ),
        axis=1,
    )
    if "estimated_kp" in merged.columns:
        merged["estimated_kp"] = pd.to_numeric(merged["estimated_kp"], errors="coerce").fillna(derived_estimated_kp)
    else:
        merged["estimated_kp"] = derived_estimated_kp
    if "kp_index" in merged.columns:
        merged["kp_index"] = pd.to_numeric(merged["kp_index"], errors="coerce").fillna(merged["estimated_kp"])
    else:
        merged["kp_index"] = merged["estimated_kp"]

    return merged.dropna(subset=["time_tag"]).tail(120)


def build_kp_history(bundle: SpaceWeatherBundle) -> list[KpTrendPoint]:
    points = bundle.minute_kp[-12:]
    return [
        KpTrendPoint(
            time_tag=str(point.get("time_tag")),
            kp_index=as_float(point.get("kp_index")),
            estimated_kp=as_float(point.get("estimated_kp")),
        )
        for point in points
    ]


def latest_official_alerts(bundle: SpaceWeatherBundle) -> tuple[str | None, str | None]:
    geomagnetic_watch: str | None = None
    active_alert: str | None = None
    for item in bundle.alerts:
        message = str(item.get("message") or "")
        compact = " ".join(segment.strip() for segment in message.splitlines() if segment.strip())
        if geomagnetic_watch is None and "WATCH: Geomagnetic Storm Category" in compact:
            geomagnetic_watch = compact.split("Potential Impacts:")[0].strip()
        if active_alert is None and ("ALERT: Geomagnetic K-index" in compact or "WARNING: Geomagnetic K-index" in compact):
            active_alert = compact.split("Potential Impacts:")[0].strip()
        if geomagnetic_watch and active_alert:
            break
    return geomagnetic_watch, active_alert


def latest_official_scales(bundle: SpaceWeatherBundle) -> tuple[str | None, str | None, str | None]:
    current = bundle.noaa_scales.get("0", {}) if isinstance(bundle.noaa_scales, dict) else {}
    geomagnetic = current.get("G", {}).get("Scale") if isinstance(current.get("G"), dict) else None
    radio = current.get("R", {}).get("Scale") if isinstance(current.get("R"), dict) else None
    solar = current.get("S", {}).get("Scale") if isinstance(current.get("S"), dict) else None
    return (
        f"G{geomagnetic}" if geomagnetic not in (None, "", "0") else "G0",
        f"R{radio}" if radio not in (None, "", "0") else "R0",
        f"S{solar}" if solar not in (None, "", "0") else "S0",
    )


def official_forecast_kp(bundle: SpaceWeatherBundle) -> tuple[float | None, str | None]:
    if not bundle.kp_forecast:
        return None, None
    forecast_rows = []
    for row in bundle.kp_forecast:
        observed = str(row.get("observed") or "").lower()
        if observed not in {"estimated", "predicted"}:
            continue
        time_tag = parse_timestamp(str(row.get("time_tag")))
        forecast_rows.append((time_tag, as_float(row.get("kp")), row.get("noaa_scale")))
    if not forecast_rows:
        return None, None
    start = min(item[0] for item in forecast_rows)
    end = start + pd.Timedelta(hours=24)
    next_day = [item for item in forecast_rows if item[0] <= end]
    if not next_day:
        next_day = forecast_rows
    max_row = max(next_day, key=lambda item: item[1])
    scale = str(max_row[2]) if max_row[2] not in (None, "") else geomagnetic_scale_from_kp(max_row[1])
    return round(max_row[1], 2), scale


def _recent_series(history: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
    if history.empty or column not in history.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(history[column], errors="coerce").dropna().tail(window)


def estimate_eta_window_seconds(history: pd.DataFrame, current_speed: float, settings: Settings) -> tuple[int | None, int | None]:
    if current_speed <= 0:
        return None, None
    recent_speed = _recent_series(history, "speed")
    speed_std = float(recent_speed.std(ddof=0)) if len(recent_speed) > 1 else 0.0
    speed_margin = max(40.0, speed_std, current_speed * 0.08)
    fast_speed = max(current_speed + speed_margin, 250.0)
    slow_speed = max(current_speed - speed_margin, 250.0)
    earliest = int(settings.l1_distance_km / fast_speed)
    latest = int(settings.l1_distance_km / slow_speed)
    return min(earliest, latest), max(earliest, latest)


def compute_source_coverage_percent(bundle: SpaceWeatherBundle) -> float:
    checks = [
        len(bundle.planetary_kp) > 0,
        len(bundle.minute_kp) > 0,
        len(bundle.mag) > 0,
        len(bundle.plasma) > 0,
        len(bundle.xray) > 0,
        len(bundle.f107) > 0,
        isinstance(bundle.cmes, list),
        isinstance(bundle.alerts, list),
        isinstance(bundle.noaa_scales, dict),
        isinstance(bundle.kp_forecast, list),
        bool(bundle.tle_text.strip()),
        len(bundle.power_lines.get("features", [])) > 0,
    ]
    return round((sum(checks) / len(checks)) * 100.0, 1)


def compute_forecast_confidence_percent(
    bundle: SpaceWeatherBundle,
    history: pd.DataFrame,
    observed_at: datetime,
    predictor: PredictiveEngine,
) -> tuple[float, int | None]:
    coverage_percent = compute_source_coverage_percent(bundle)
    history_factor = clamp((len(history) / 60.0) * 100.0, 30.0, 100.0) if not history.empty else 30.0
    if bundle.mode == "archive":
        freshness_seconds = 0
        freshness_factor = 100.0
    else:
        freshness_seconds = max(int((datetime.now(timezone.utc) - observed_at).total_seconds()), 0)
        freshness_factor = clamp(100.0 - (freshness_seconds / 18.0), 20.0, 100.0)
    model_factor = 100.0 if predictor.available else 60.0
    confidence = round(
        clamp(
            (coverage_percent * 0.35)
            + (history_factor * 0.25)
            + (freshness_factor * 0.20)
            + (model_factor * 0.20),
            35.0,
            96.0,
        ),
        1,
    )
    return confidence, freshness_seconds


def compute_risk_bands(
    history: pd.DataFrame,
    local_risk_percent: float,
    ml_risk_percent: float | None,
    confidence_percent: float,
    predictor: PredictiveEngine,
) -> tuple[float, float, float | None, float | None]:
    recent_bz = _recent_series(history, "bz")
    recent_speed = _recent_series(history, "speed")
    recent_density = _recent_series(history, "density")
    bz_std = float(recent_bz.std(ddof=0)) if len(recent_bz) > 1 else 0.0
    speed_std = float(recent_speed.std(ddof=0)) if len(recent_speed) > 1 else 0.0
    density_std = float(recent_density.std(ddof=0)) if len(recent_density) > 1 else 0.0
    volatility = clamp((bz_std * 2.4) + (speed_std / 38.0) + (density_std * 1.5), 2.5, 18.0)
    confidence_penalty = (100.0 - confidence_percent) / 8.0
    model_mae = as_float(predictor.metadata.get("mae") if predictor.metadata else None, 5.0)
    disagreement = abs((ml_risk_percent if ml_risk_percent is not None else local_risk_percent) - local_risk_percent)

    physics_half_width = clamp(3.5 + (volatility * 0.35) + confidence_penalty, 4.0, 20.0)
    local_low = round(clamp(local_risk_percent - physics_half_width, 0.0, 100.0), 1)
    local_high = round(clamp(local_risk_percent + physics_half_width, 0.0, 100.0), 1)

    if ml_risk_percent is None:
        return local_low, local_high, None, None

    ml_half_width = clamp(
        max(model_mae, 4.5) + (volatility * 0.25) + (disagreement * 0.55) + confidence_penalty,
        5.0,
        24.0,
    )
    ml_low = round(clamp(ml_risk_percent - ml_half_width, 0.0, 100.0), 1)
    ml_high = round(clamp(ml_risk_percent + ml_half_width, 0.0, 100.0), 1)
    return local_low, local_high, ml_low, ml_high


def geomagnetic_scale_from_kp(kp_index: float) -> str:
    if kp_index >= 9.0:
        return "G5"
    if kp_index >= 8.0:
        return "G4"
    if kp_index >= 7.0:
        return "G3"
    if kp_index >= 6.0:
        return "G2"
    if kp_index >= 5.0:
        return "G1"
    return "G0"


def estimate_storm_scale_band(history: pd.DataFrame, estimated_kp: float, confidence_percent: float) -> str:
    recent_kp = _recent_series(history, "estimated_kp")
    recent_bz = _recent_series(history, "bz")
    kp_std = float(recent_kp.std(ddof=0)) if len(recent_kp) > 1 else 0.0
    bz_std = float(recent_bz.std(ddof=0)) if len(recent_bz) > 1 else 0.0
    kp_margin = clamp(0.45 + (kp_std * 0.8) + (bz_std / 10.0) + ((100.0 - confidence_percent) / 120.0), 0.4, 1.8)
    lower = geomagnetic_scale_from_kp(clamp(estimated_kp - kp_margin, 0.0, 9.0))
    upper = geomagnetic_scale_from_kp(clamp(estimated_kp + kp_margin, 0.0, 9.0))
    return lower if lower == upper else f"{lower}-{upper}"


def validation_metrics(predictor: PredictiveEngine, lead_time_minutes: int | None) -> tuple[float | None, int | None, int | None]:
    if not predictor.metadata:
        return None, None, lead_time_minutes
    mae = as_float(predictor.metadata.get("mae"), float("nan"))
    rows = predictor.metadata.get("rows")
    cadence_minutes = as_float(predictor.metadata.get("cadence_minutes"), 1.0)
    horizon_steps = as_float(predictor.metadata.get("horizon_steps"), float(lead_time_minutes or 60))
    horizon_minutes = int(round(cadence_minutes * horizon_steps)) if cadence_minutes > 0 else lead_time_minutes
    mae_value = round(mae, 4) if not math.isnan(mae) else None
    rows_value = int(rows) if rows is not None else None
    return mae_value, rows_value, horizon_minutes


def build_heat_grid(settings: Settings, local_risk_percent: float, auroral_expansion_percent: float) -> list[HeatCell]:
    grid: list[HeatCell] = []
    base_intensity = clamp(local_risk_percent / 100.0, 0.0, 1.0)
    expansion_bonus = clamp(auroral_expansion_percent / 100.0, 0.0, 1.0) * 0.25
    for index, (label, latitude, longitude, corridor_weight) in enumerate(TURKIYE_REGIONS):
        region_magnetic_latitude = compute_magnetic_latitude(latitude, longitude)
        latitude_factor = clamp((58.0 - abs(region_magnetic_latitude)) / 24.0, 0.45, 1.0)
        intensity = clamp(base_intensity * corridor_weight * latitude_factor + expansion_bonus, 0.08, 1.0)
        grid.append(
            HeatCell(
                id=f"cell-{index}",
                label=label,
                latitude=latitude,
                longitude=longitude,
                intensity=intensity,
            )
        )
    return grid


def extract_watchlist(tle_text: str) -> tuple[list[str], int]:
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    watchlist: list[str] = []
    leos = 0
    for index in range(0, len(lines) - 2, 3):
        name = lines[index]
        line2 = lines[index + 2]
        parts = line2.split()
        if len(parts) < 8:
            continue
        mean_motion = as_float(parts[-1])
        if mean_motion >= 11.0:
            leos += 1
        upper_name = name.upper()
        if any(marker in upper_name for marker in ("STARLINK", "IMECE", "GOKTURK", "ISS")):
            watchlist.append(name)
    deduped = list(dict.fromkeys(watchlist))
    return deduped[:6], leos


def build_impacts(
    xray_flux: float,
    xray_class: str,
    f107_flux: float,
    estimated_kp: float,
    bz: float,
    speed: float,
    density: float,
    local_risk_percent: float,
    tle_text: str,
) -> list[ThreatImpact]:
    watchlist, active_leo_count = extract_watchlist(tle_text)
    impacts: list[ThreatImpact] = []

    if xray_flux >= 1e-6:
        impacts.append(
            ThreatImpact(
                id="radio-blackout",
                title="HF/VHF radyo kararmasi",
                severity="critical" if xray_flux >= 1e-5 else "high",
                affected_systems=[
                    "Havacilik HF/VHF telsizleri",
                    "Amator kisa dalga haberlesme",
                    "Deniz ve acil durum HF baglantilari",
                ],
                rationale=f"GOES X-ray akis seviyesi {xray_class}; D-katmani sogurumu radyo ufkunu kapatabilir.",
            )
        )

    if f107_flux >= 140 and (density >= 6 or speed >= 550 or active_leo_count > 0):
        systems = watchlist or ["Starlink filosu", "IMECE", "Gokturk", "ISS"]
        impacts.append(
            ThreatImpact(
                id="orbital-drag",
                title="LEO uydu surtunme artisi",
                severity="high" if f107_flux >= 160 or density >= 10 else "medium",
                affected_systems=systems,
                rationale=f"F10.7={f107_flux:.0f} sfu ve plazma yogunlugu {density:.1f}; aktif LEO varlik sayisi yaklasik {active_leo_count}.",
            )
        )

    if estimated_kp >= 5 or bz <= -10 or local_risk_percent >= 55:
        impacts.append(
            ThreatImpact(
                id="gic-gnss",
                title="GNSS sapmasi ve GIC riski",
                severity="critical" if estimated_kp >= 7 or bz <= -10 else "high",
                affected_systems=[
                    "TEIAS 154/400 kV iletim omurgasi",
                    "Turkiye genelindeki GNSS lojistik ve tarim sistemleri",
                    "Uzun yuksek gerilim iletim hatlari ve buyuk trafolar",
                ],
                rationale=f"Kp {estimated_kp:.1f}, Bz {bz:.1f} nT ve ruzgar hizi {speed:.0f} km/s kombinasyonu Turkiye genelindeki geomanyetik sapma ve GIC riskini buyutuyor.",
            )
        )

    return impacts


def build_sops(impacts: list[ThreatImpact]) -> list[SopAction]:
    actions: list[SopAction] = []
    impact_ids = {impact.id for impact in impacts}
    if "gic-gnss" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Enerji",
                    action="Yuksek gerilim hatlarindaki kapasitif kompanzasyon birimlerini kontrollu sekilde devreden cikar.",
                    status="urgent",
                ),
                SopAction(
                    sector="Enerji",
                    action="Trafo sogutma hatlarini tam guce al; yuk atma senaryolarini hazir tut.",
                    status="urgent",
                ),
                SopAction(
                    sector="Tarim ve Ulasim",
                    action="GNSS sapmasina karsi INS, eLoran benzeri yedekler ve saha referans beaconlarini capraz kontrol moduna al.",
                    status="ready",
                ),
            ]
        )
    if "radio-blackout" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Havacilik",
                    action="HF radyo zincirlerini SATCOM ile yedekle; rota ekiplerine iyonosferik kesinti bulteni gec.",
                    status="urgent",
                ),
                SopAction(
                    sector="Denizcilik",
                    action="Kisa dalga yerine uydu yedek iletisim planini aktive et.",
                    status="ready",
                ),
            ]
        )
    if "orbital-drag" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Uydu Operasyonlari",
                    action="Panel acilarini edge-on konuma yaklastir; collision avoidance yakit butcesini hazirla.",
                    status="urgent",
                ),
            ]
        )
    return actions


def build_summary_headline(early_detection: bool, local_risk_percent: float, cme_count: int) -> str:
    if early_detection:
        return "KIRMIZI ALARM: Erken tespit basarili"
    if local_risk_percent >= 65:
        return "Turkiye uzerindeki manyetik yuk hizla artiyor"
    if cme_count:
        return "Arka planda CME akisi izleniyor"
    return "Uzay havasi izleme modunda"


def severity_from_context(early_detection: bool, local_risk_percent: float, impacts: list[ThreatImpact], ml_risk_percent: float | None) -> str | None:
    if early_detection or any(impact.severity == "critical" for impact in impacts) or local_risk_percent >= 75:
        return "critical"
    if any(impact.severity == "high" for impact in impacts) or local_risk_percent >= 50 or (ml_risk_percent or 0) >= 60:
        return "warning"
    if impacts or local_risk_percent >= 30:
        return "watch"
    return None


def build_dashboard_artifacts(bundle: SpaceWeatherBundle, predictor: PredictiveEngine, settings: Settings) -> tuple[TelemetrySnapshot, CrisisAlert | None]:
    history = build_history_frame(bundle)

    latest_mag = bundle.mag[-1] if bundle.mag else {}
    latest_plasma = bundle.plasma[-1] if bundle.plasma else {}
    latest_official_kp = bundle.planetary_kp[-1] if bundle.planetary_kp else {}
    latest_estimated_kp = bundle.minute_kp[-1] if bundle.minute_kp else {}
    latest_xray = max(
        bundle.xray,
        key=lambda row: as_float(row.get("flux")) if row.get("energy") == "0.1-0.8nm" else -1.0,
        default={},
    )
    latest_f107 = bundle.f107[0] if bundle.f107 else {}

    speed = as_float(latest_plasma.get("speed"))
    density = as_float(latest_plasma.get("density"))
    temperature = as_float(latest_plasma.get("temperature"))
    bz = as_float(latest_mag.get("bz_gsm"))
    bt = as_float(latest_mag.get("bt"))
    derived_estimated_kp = estimate_kp_from_solar_wind(bz, speed, density)
    kp_index = as_float(latest_official_kp.get("Kp"), derived_estimated_kp)
    estimated_kp = as_float(latest_estimated_kp.get("estimated_kp"), derived_estimated_kp)
    if not bundle.minute_kp:
        estimated_kp = derived_estimated_kp
    if not bundle.planetary_kp:
        kp_index = estimated_kp
    xray_flux = as_float(latest_xray.get("flux"))
    xray_class = classify_xray(xray_flux)
    f107_flux = as_float(latest_f107.get("flux"))
    magnetic_latitude = compute_magnetic_latitude(settings.turkiye_center_lat, settings.turkiye_center_lon)
    official_watch_headline, official_alert_headline = latest_official_alerts(bundle)
    official_geomagnetic_scale, official_radio_blackout_scale, official_solar_radiation_scale = latest_official_scales(bundle)
    official_forecast_kp_max, official_forecast_scale = official_forecast_kp(bundle)

    early_detection = bz <= -10 and speed >= 500
    eta_seconds = int(settings.l1_distance_km / speed) if speed > 0 else None
    auroral_expansion_percent = clamp(((estimated_kp - 4.0) / 5.0) * 100.0, 0.0, 100.0)
    local_risk_percent = compute_local_risk_percent(
        estimated_kp=estimated_kp,
        bz=bz,
        speed=speed,
        density=density,
        magnetic_latitude=magnetic_latitude,
        early_detection=early_detection,
    )

    prediction = predictor.predict(history, magnetic_latitude)
    ml_risk_percent = round(prediction.risk_percent, 1) if prediction else None
    ml_lead_time_minutes = prediction.lead_time_minutes if prediction else None

    impacts = build_impacts(
        xray_flux=xray_flux,
        xray_class=xray_class,
        f107_flux=f107_flux,
        estimated_kp=estimated_kp,
        bz=bz,
        speed=speed,
        density=density,
        local_risk_percent=local_risk_percent,
        tle_text=bundle.tle_text,
    )
    sops = build_sops(impacts)

    observed_at = max(
        parse_timestamp(str(latest_mag.get("time_tag"))) if latest_mag else datetime.now(timezone.utc),
        parse_timestamp(str(latest_plasma.get("time_tag"))) if latest_plasma else datetime.now(timezone.utc),
        parse_timestamp(str(latest_estimated_kp.get("time_tag"))) if latest_estimated_kp else datetime.now(timezone.utc),
    )
    eta_window_start_seconds, eta_window_end_seconds = estimate_eta_window_seconds(history, speed, settings)
    forecast_confidence_percent, data_freshness_seconds = compute_forecast_confidence_percent(bundle, history, observed_at, predictor)

    telemetry = TelemetrySnapshot(
        observed_at=observed_at,
        mode=bundle.mode,
        solar_wind_speed=round(speed, 1),
        bz=round(bz, 2),
        bt=round(bt, 2),
        density=round(density, 2),
        temperature=round(temperature, 1),
        kp_index=round(kp_index, 2),
        estimated_kp=round(estimated_kp, 2),
        xray_flux=xray_flux,
        xray_class=xray_class,
        f107_flux=round(f107_flux, 2),
        cme_count=len(bundle.cmes),
        early_detection=early_detection,
        eta_seconds=eta_seconds,
        eta_window_start_seconds=eta_window_start_seconds,
        eta_window_end_seconds=eta_window_end_seconds,
        local_risk_percent=round(local_risk_percent, 1),
        risk_band_low=0.0,
        risk_band_high=0.0,
        local_magnetic_latitude=round(magnetic_latitude, 2),
        auroral_expansion_percent=round(auroral_expansion_percent, 1),
        forecast_confidence_percent=forecast_confidence_percent,
        source_coverage_percent=compute_source_coverage_percent(bundle),
        data_freshness_seconds=data_freshness_seconds,
        storm_scale_band="G0",
        official_geomagnetic_scale=official_geomagnetic_scale,
        official_radio_blackout_scale=official_radio_blackout_scale,
        official_solar_radiation_scale=official_solar_radiation_scale,
        official_watch_headline=official_watch_headline,
        official_alert_headline=official_alert_headline,
        official_forecast_kp_max=official_forecast_kp_max,
        official_forecast_scale=official_forecast_scale,
        ml_risk_percent=ml_risk_percent,
        ml_risk_band_low=None,
        ml_risk_band_high=None,
        ml_lead_time_minutes=ml_lead_time_minutes,
        validation_mae=None,
        validation_rows=None,
        validation_horizon_minutes=None,
        summary_headline=build_summary_headline(early_detection, local_risk_percent, len(bundle.cmes)),
        kp_history=build_kp_history(bundle),
        source_statuses=bundle.source_statuses,
        power_lines=bundle.power_lines,
        heat_grid=build_heat_grid(settings, local_risk_percent, auroral_expansion_percent),
    )
    (
        telemetry.risk_band_low,
        telemetry.risk_band_high,
        telemetry.ml_risk_band_low,
        telemetry.ml_risk_band_high,
    ) = compute_risk_bands(history, telemetry.local_risk_percent, telemetry.ml_risk_percent, telemetry.forecast_confidence_percent, predictor)
    telemetry.storm_scale_band = estimate_storm_scale_band(history, telemetry.estimated_kp, telemetry.forecast_confidence_percent)
    (
        telemetry.validation_mae,
        telemetry.validation_rows,
        telemetry.validation_horizon_minutes,
    ) = validation_metrics(predictor, telemetry.ml_lead_time_minutes)

    severity = severity_from_context(early_detection, local_risk_percent, impacts, ml_risk_percent)
    if severity is None:
        return telemetry, None

    title = telemetry.summary_headline
    subtitle = (
        f"Turkiye geneli risk %{telemetry.local_risk_percent:.0f}. "
        f"Anlik Bz {telemetry.bz:.1f} nT, ruzgar {telemetry.solar_wind_speed:.0f} km/s, Kp {telemetry.estimated_kp:.1f}."
    )
    narrative = (
        "Fizik katmani DSCOVR L1 telemetrisi ile medyan ETA ve varis penceresi hesapliyor; XGBoost tahmini son 10 dakikadaki "
        "paternleri okuyarak 60 dakika sonraki Turkiye geneli risk bandini uretiyor. Sonuc guven puani, cihaz etkisi ve SOP "
        "listesine donusturuluyor."
    )

    alert = CrisisAlert(
        id=str(uuid5(NAMESPACE_URL, f"{bundle.mode}:{observed_at.isoformat()}:{severity}")),
        created_at=datetime.now(timezone.utc),
        mode=bundle.mode,
        severity=severity,
        title=title,
        subtitle=subtitle,
        eta_seconds=eta_seconds,
        narrative=narrative,
        telemetry=telemetry,
        impacted_hardware=impacts,
        sop_actions=sops,
    )
    return telemetry, alert
