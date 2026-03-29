from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from .config import Settings
from .data_sources import SpaceWeatherBundle
from .physics_engine import (
    dynamic_pressure_npa,
    estimate_dbdt_proxy_nt_per_min,
    estimate_dynamic_propagation,
    estimate_magnetopause_state,
    estimate_tec_delay_proxy,
    local_solar_hour,
    physics_residual_risk_bonus,
)
from .predictor import PredictiveEngine
from .schemas import (
    CrisisAlert,
    DecisionCommentary,
    HeatCell,
    KpTrendPoint,
    ModelContribution,
    SopAction,
    TelemetrySnapshot,
    ThreatImpact,
    TurkishSatelliteAssessment,
)


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


@dataclass(slots=True)
class PrecursorOutlook:
    risk_percent: float | None
    risk_band_low: float | None
    risk_band_high: float | None
    horizon_hours: int | None
    confidence_percent: float | None
    headline: str | None
    cme_speed_kms: float | None
    arrival_at: datetime | None
    earth_directed: bool
    earth_glancing: bool


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

def compute_dst_proxy(bz: float, speed: float, density: float) -> float:
    """
    Empirical estimate of the Kyoto Dst Index (Disturbance Storm Time) using solar wind parameters.
    A proxy for the 'Burton Equation' representing equatorial magnetic ring current injection.
    Values < -50 nT indicate a storm; < -250 nT is a superstorm.
    """
    dynamic_pressure = (density * 1e6) * (1.67e-27) * (speed * 1000)**2 * 1e9  # nPa roughly
    pressure_correction = 15.8 * math.sqrt(max(dynamic_pressure, 0.0)) - 20.0
    
    # Electric field injection
    v_m_s = speed * 1000
    bz_t = bz * 1e-9
    e_field = -v_m_s * min(bz_t, 0.0) * 1000  # mV/m
    
    injection_term = -15.0 * e_field if e_field > 0.5 else 0.0
    return clamp(pressure_correction + injection_term, -800.0, 50.0)

def compute_local_risk_percent(
    estimated_kp: float,
    bz: float,
    speed: float,
    density: float,
    dst_index: float | None,
    magnetic_latitude: float,
    early_detection: bool,
) -> float:
    effective_dst = dst_index if dst_index is not None else compute_dst_proxy(bz, speed, density)
    
    # Kp ve Dst indeksini harmanlayarak altin standart risk hesapliyoruz
    return clamp(
        ((estimated_kp / 9.0) * 35.0)
        + clamp(abs(min(effective_dst, 0.0)) / 200.0, 0.0, 1.0) * 15.0 # Dst Etkisi
        + clamp(abs(min(bz, 0.0)) / 20.0, 0.0, 1.0) * 20.0
        + clamp((speed - 350.0) / 650.0, 0.0, 1.0) * 15.0
        + clamp(density / 25.0, 0.0, 1.0) * 5.0
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


def latest_proton_flux_pfu(bundle: SpaceWeatherBundle) -> float | None:
    if not bundle.protons:
        return None
    preferred_rows: list[tuple[float, datetime]] = []
    fallback_rows: list[tuple[float, datetime]] = []
    for row in bundle.protons:
        time_tag = parse_timestamp(str(row.get("time_tag")))
        flux = as_float(row.get("flux"), float("nan"))
        if math.isnan(flux):
            continue
        energy = str(row.get("energy") or row.get("energy_channel") or "").lower()
        if "10" in energy:
            preferred_rows.append((flux, time_tag))
        else:
            fallback_rows.append((flux, time_tag))
    rows = preferred_rows or fallback_rows
    if not rows:
        return None
    latest = max(rows, key=lambda item: item[1])
    return round(latest[0], 2)


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
    dst = pd.DataFrame(bundle.dst)

    if mag.empty or plasma.empty:
        return pd.DataFrame(columns=["time_tag", "bz", "bt", "speed", "density", "temperature", "estimated_kp", "dst_index"])

    mag = mag.rename(columns={"bz_gsm": "bz", "bt": "bt"})
    plasma = plasma.rename(columns={"speed": "speed", "density": "density", "temperature": "temperature"})
    if not minute_kp.empty:
        minute_kp = minute_kp.rename(columns={"time_tag": "time_tag", "estimated_kp": "estimated_kp", "kp_index": "kp_index"})
    if not dst.empty:
        dst = dst.rename(columns={"time_tag": "time_tag", "dst": "dst_index"})

    for frame in (mag, plasma):
        frame["time_tag"] = pd.to_datetime(frame["time_tag"], utc=True, errors="coerce")
    if not minute_kp.empty:
        minute_kp["time_tag"] = pd.to_datetime(minute_kp["time_tag"], utc=True, errors="coerce")
    if not dst.empty:
        dst["time_tag"] = pd.to_datetime(dst["time_tag"], utc=True, errors="coerce")

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
    if not dst.empty:
        merged = pd.merge_asof(
            merged.sort_values("time_tag"),
            dst.sort_values("time_tag")[["time_tag", "dst_index"]],
            on="time_tag",
            direction="nearest",
            tolerance=pd.Timedelta("15min"),
        )
    if "dst_index" not in merged.columns:
        merged["dst_index"] = pd.NA

    for column in ["bz", "bt", "speed", "density", "temperature", "dst_index"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")
    merged["dst_index"] = merged["dst_index"].fillna(
        merged.apply(
            lambda row: compute_dst_proxy(
                as_float(row.get("bz")),
                as_float(row.get("speed"), 400.0),
                as_float(row.get("density"), 5.0),
            ),
            axis=1,
        )
    )

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

    return merged.dropna(subset=["time_tag"]).tail(480)


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


def _parse_swpc_timestamp(compact: str, label: str) -> datetime | None:
    match = re.search(rf"{re.escape(label)}\s*(\d{{4}}\s+[A-Z][a-z]{{2}}\s+\d{{1,2}}\s+\d{{4}})\s+UTC", compact)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y %b %d %H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_watch_days(compact: str, default_year: int) -> list[tuple[datetime.date, str]]:
    results: list[tuple[datetime.date, str]] = []
    for match in re.finditer(r"([A-Z][a-z]{2}\s+\d{1,2}):\s+(G\d|R\d|S\d|None)", compact):
        try:
            day = datetime.strptime(f"{default_year} {match.group(1)}", "%Y %b %d").date()
        except ValueError:
            continue
        results.append((day, match.group(2)))
    return results


def _scale_value(scale: str | None) -> int:
    if not scale:
        return 0
    match = re.search(r"([GRS])(\d)", scale)
    return int(match.group(2)) if match else 0


def _message_is_current_watch(compact: str, now: datetime) -> bool:
    issue_time = _parse_swpc_timestamp(compact, "Issue Time:")
    if issue_time and now - issue_time > timedelta(days=4):
        return False
    watch_days = _parse_watch_days(compact, (issue_time or now).year)
    if watch_days:
        for day, scale in watch_days:
            if day >= now.date() and scale.startswith("G") and _scale_value(scale) >= 1:
                return True
        return False
    return True


def _message_is_current_alert(compact: str, now: datetime) -> bool:
    valid_from = _parse_swpc_timestamp(compact, "Valid From:")
    valid_to = _parse_swpc_timestamp(compact, "Valid To:")
    issue_time = _parse_swpc_timestamp(compact, "Issue Time:")
    if valid_from and now < valid_from:
        return False
    if valid_to and now > valid_to:
        return False
    if valid_from is None and valid_to is None and issue_time and now - issue_time > timedelta(hours=18):
        return False
    return True


def latest_official_alerts(bundle: SpaceWeatherBundle) -> tuple[str | None, str | None]:
    geomagnetic_watch: str | None = None
    active_alert: str | None = None
    now = datetime.now(timezone.utc)
    for item in bundle.alerts:
        message = str(item.get("message") or "")
        compact = " ".join(segment.strip() for segment in message.splitlines() if segment.strip())
        if (
            geomagnetic_watch is None
            and "WATCH: Geomagnetic Storm Category" in compact
            and _message_is_current_watch(compact, now)
        ):
            geomagnetic_watch = compact.split("Potential Impacts:")[0].strip()
        if (
            active_alert is None
            and ("ALERT: Geomagnetic K-index" in compact or "WARNING: Geomagnetic K-index" in compact)
            and _message_is_current_alert(compact, now)
        ):
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


def _xray_precursor_score(xray_flux: float) -> float:
    if xray_flux >= 1e-4:
        return 92.0
    if xray_flux >= 1e-5:
        return clamp(58.0 + math.log10(max(xray_flux / 1e-5, 1.0)) * 24.0, 58.0, 88.0)
    if xray_flux >= 1e-6:
        return clamp(24.0 + math.log10(max(xray_flux / 1e-6, 1.0)) * 20.0, 24.0, 52.0)
    if xray_flux >= 1e-7:
        return clamp(8.0 + math.log10(max(xray_flux / 1e-7, 1.0)) * 14.0, 8.0, 22.0)
    return 4.0


def _earth_arrival_from_enlil(analysis: dict[str, Any]) -> tuple[datetime | None, float | None, bool, bool]:
    arrival_at: datetime | None = None
    kp_max: float | None = None
    earth_directed = False
    earth_glancing = False

    for enlil in analysis.get("enlilList") or []:
        candidate_arrival = parse_timestamp(str(enlil.get("estimatedShockArrivalTime"))) if enlil.get("estimatedShockArrivalTime") else None
        candidate_kp_values = [
            as_float(enlil.get("kp_180"), float("nan")),
            as_float(enlil.get("kp_135"), float("nan")),
            as_float(enlil.get("kp_90"), float("nan")),
            as_float(enlil.get("kp_18"), float("nan")),
        ]
        candidate_kp = max((value for value in candidate_kp_values if not math.isnan(value)), default=float("nan"))
        if not math.isnan(candidate_kp):
            kp_max = max(kp_max or candidate_kp, candidate_kp)

        candidate_earth_directed = bool(enlil.get("isEarthGB")) or bool(enlil.get("isEarthMinorImpact")) or candidate_arrival is not None
        candidate_earth_glancing = bool(enlil.get("isEarthGB"))

        for impact in enlil.get("impactList") or []:
            location = str(impact.get("location") or "").lower()
            if "earth" not in location:
                continue
            candidate_earth_directed = True
            candidate_earth_glancing = bool(impact.get("isGlancingBlow"))
            impact_arrival = parse_timestamp(str(impact.get("arrivalTime"))) if impact.get("arrivalTime") else None
            if impact_arrival is not None:
                candidate_arrival = impact_arrival if candidate_arrival is None else min(candidate_arrival, impact_arrival)

        if candidate_earth_directed:
            earth_directed = True
        if candidate_earth_glancing:
            earth_glancing = True
        if candidate_arrival is not None:
            arrival_at = candidate_arrival if arrival_at is None else min(arrival_at, candidate_arrival)

    return arrival_at, kp_max, earth_directed, earth_glancing


def build_precursor_outlook(
    bundle: SpaceWeatherBundle,
    xray_flux: float,
    xray_class: str,
    observed_at: datetime,
    official_forecast_kp_max: float | None,
    official_forecast_scale: str | None,
) -> PrecursorOutlook:
    flare_score = _xray_precursor_score(xray_flux)
    official_score = clamp(
        max(
            clamp(((official_forecast_kp_max or 0.0) - 3.0) * 16.0, 0.0, 70.0),
            float(_scale_value(official_forecast_scale) * 18),
        ),
        0.0,
        80.0,
    )
    best_candidate: dict[str, Any] | None = None

    for item in bundle.cmes:
        analyses = item.get("cmeAnalyses") or []
        if not analyses:
            continue
        preferred_analyses = [analysis for analysis in analyses if analysis.get("isMostAccurate")] or analyses
        start_time = parse_timestamp(str(item.get("startTime"))) if item.get("startTime") else observed_at
        hours_since_start = max((observed_at - start_time).total_seconds() / 3600.0, 0.0)
        if hours_since_start > 96.0:
            continue
        freshness_score = clamp((96.0 - hours_since_start) / 96.0, 0.15, 1.0)
        linked_flare = any("FLR" in str(event.get("activityID") or "") for event in (item.get("linkedEvents") or []))

        for analysis in preferred_analyses:
            speed = as_float(analysis.get("speed"))
            half_angle = as_float(analysis.get("halfAngle"))
            longitude_value = analysis.get("longitude")
            longitude = None if longitude_value in (None, "") else as_float(longitude_value)
            arrival_at, kp_max, earth_directed, earth_glancing = _earth_arrival_from_enlil(analysis)
            if arrival_at is not None and arrival_at < observed_at - timedelta(hours=12):
                arrival_at = None

            if earth_directed:
                directness_score = 1.0 if not earth_glancing else 0.82
            elif longitude is not None:
                directness_score = clamp(((half_angle + 28.0) - abs(longitude)) / 70.0, 0.0, 0.85)
            else:
                directness_score = clamp((half_angle - 25.0) / 60.0, 0.0, 0.45)

            speed_score = clamp((speed - 320.0) / 900.0, 0.0, 1.0)
            width_score = clamp((half_angle - 15.0) / 80.0, 0.0, 1.0)
            kp_score = clamp((kp_max or 0.0) / 7.0, 0.0, 1.0)
            arrival_score = 0.18 if arrival_at is not None else 0.0
            flare_bonus = 0.12 if linked_flare else 0.0
            source_bonus = 0.08 if item.get("sourceLocation") else 0.0

            raw_score = clamp(
                (directness_score * 0.42)
                + (speed_score * 0.18)
                + (width_score * 0.10)
                + (kp_score * 0.16)
                + (freshness_score * 0.08)
                + arrival_score
                + flare_bonus
                + source_bonus,
                0.0,
                1.0,
            )
            candidate_risk = clamp((raw_score * 100.0 * 0.72) + (flare_score * 0.18) + (official_score * 0.10), 0.0, 100.0)

            candidate_confidence = clamp(
                36.0
                + (18.0 if earth_directed else 0.0)
                + (10.0 if arrival_at is not None else 0.0)
                + (8.0 if kp_max is not None else 0.0)
                + (8.0 if linked_flare else 0.0)
                + (6.0 if item.get("sourceLocation") else 0.0)
                + (10.0 if official_score > 0.0 else 0.0),
                35.0,
                92.0,
            )

            horizon_hours: int | None = None
            if arrival_at is not None:
                horizon_hours = max(int(round((arrival_at - observed_at).total_seconds() / 3600.0)), 0)
            elif directness_score >= 0.58 and speed > 0:
                inferred_hours = 149_600_000.0 / max(speed * 0.78, 260.0) / 3600.0
                horizon_hours = int(round(clamp(inferred_hours, 18.0, 96.0)))

            band_half_width = clamp(
                10.0
                + (18.0 if arrival_at is None else 8.0)
                + ((100.0 - candidate_confidence) / 8.0)
                + ((1.0 - directness_score) * 12.0),
                8.0,
                28.0,
            )
            candidate = {
                "risk_percent": round(candidate_risk, 1),
                "risk_band_low": round(clamp(candidate_risk - band_half_width, 0.0, 100.0), 1),
                "risk_band_high": round(clamp(candidate_risk + band_half_width, 0.0, 100.0), 1),
                "horizon_hours": horizon_hours,
                "confidence_percent": round(candidate_confidence, 1),
                "cme_speed_kms": round(speed, 1) if speed > 0 else None,
                "arrival_at": arrival_at,
                "earth_directed": earth_directed,
                "earth_glancing": earth_glancing,
            }
            if best_candidate is None or candidate["risk_percent"] > best_candidate["risk_percent"]:
                best_candidate = candidate

    if best_candidate is None:
        fallback_risk = clamp((flare_score * 0.58) + (official_score * 0.42) - 8.0, 0.0, 46.0)
        if fallback_risk < 16.0:
            return PrecursorOutlook(None, None, None, None, None, None, None, None, False, False)
        confidence = round(clamp(34.0 + (official_score * 0.22) + (flare_score * 0.18), 35.0, 74.0), 1)
        half_width = clamp(18.0 + ((100.0 - confidence) / 7.0), 16.0, 30.0)
        headline = "Flare prekursoru izleniyor" if flare_score >= 35.0 else "Orta vadeli uzay hava outlook'u yukseliyor"
        return PrecursorOutlook(
            risk_percent=round(fallback_risk, 1),
            risk_band_low=round(clamp(fallback_risk - half_width, 0.0, 100.0), 1),
            risk_band_high=round(clamp(fallback_risk + half_width, 0.0, 100.0), 1),
            horizon_hours=24 if official_score >= 18.0 else None,
            confidence_percent=confidence,
            headline=headline,
            cme_speed_kms=None,
            arrival_at=None,
            earth_directed=False,
            earth_glancing=False,
        )

    headline = None
    if best_candidate["earth_directed"] and (best_candidate["horizon_hours"] or 0) <= 72 and best_candidate["risk_percent"] >= 62.0:
        headline = "CME prekursoru kilitlendi"
    elif best_candidate["risk_percent"] >= 45.0:
        headline = "Gunes onculu risk penceresi acildi"
    elif flare_score >= 35.0:
        headline = "Flare prekursoru izleniyor"

    return PrecursorOutlook(
        risk_percent=best_candidate["risk_percent"],
        risk_band_low=best_candidate["risk_band_low"],
        risk_band_high=best_candidate["risk_band_high"],
        horizon_hours=best_candidate["horizon_hours"],
        confidence_percent=best_candidate["confidence_percent"],
        headline=headline,
        cme_speed_kms=best_candidate["cme_speed_kms"],
        arrival_at=best_candidate["arrival_at"],
        earth_directed=best_candidate["earth_directed"],
        earth_glancing=best_candidate["earth_glancing"],
    )


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
    if bundle.source_statuses:
        available = sum(1 for status in bundle.source_statuses if status.state != "degraded")
        return round((available / len(bundle.source_statuses)) * 100.0, 1)
    checks = [
        len(bundle.planetary_kp) > 0,
        len(bundle.minute_kp) > 0,
        len(bundle.mag) > 0,
        len(bundle.plasma) > 0,
        len(bundle.dst) > 0,
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


def validation_metrics(predictor: PredictiveEngine, lead_time_minutes: int | None) -> tuple[float | None, float | None, int | None, int | None]:
    if not predictor.metadata:
        return None, None, None, lead_time_minutes
    mae = as_float(predictor.metadata.get("mae"), float("nan"))
    band_coverage = as_float(predictor.metadata.get("dst_band_coverage"), float("nan"))
    rows = predictor.metadata.get("rows")
    cadence_minutes = as_float(predictor.metadata.get("cadence_minutes"), 1.0)
    horizon_steps = as_float(predictor.metadata.get("horizon_steps"), float(lead_time_minutes or 60))
    horizon_minutes = int(round(cadence_minutes * horizon_steps)) if cadence_minutes > 0 else lead_time_minutes
    mae_value = round(mae, 4) if not math.isnan(mae) else None
    band_coverage_value = round(band_coverage * 100.0, 1) if not math.isnan(band_coverage) else None
    rows_value = int(rows) if rows is not None else None
    return mae_value, band_coverage_value, rows_value, horizon_minutes


def ml_risk_from_predicted_dst(
    predicted_dst_index: float,
    estimated_kp: float,
    bz: float,
    speed: float,
    density: float,
    magnetic_latitude: float,
    early_detection: bool,
) -> float:
    return round(
        compute_local_risk_percent(
            estimated_kp=estimated_kp,
            bz=bz,
            speed=speed,
            density=density,
            dst_index=predicted_dst_index,
            magnetic_latitude=magnetic_latitude,
            early_detection=early_detection,
        ),
        1,
    )


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


def _satellite_top_driver(scores: dict[str, float]) -> tuple[str, float]:
    label, value = max(scores.items(), key=lambda item: item[1])
    return label, round(value, 1)


def _satellite_orbit_weight(orbit_class: str) -> tuple[float, float, float, float]:
    if orbit_class == "GEO":
        return 0.12, 0.48, 0.22, 0.18
    if orbit_class == "MEO":
        return 0.22, 0.30, 0.24, 0.24
    return 0.42, 0.16, 0.18, 0.24


def _satellite_action(name: str, orbit_class: str, dominant_driver: str, over_turkiye: bool) -> str:
    if dominant_driver == "charging":
        return f"{name} icin charging mitigasyonu, transponder duty-cycle dengelemesi ve safe-hold hazirligini artir."
    if dominant_driver == "drag":
        return f"{name} icin orbital drag butcesini, attitude profillerini ve gerekiyorsa yoreunge duzeltme penceresini hazirla."
    if dominant_driver == "radiation":
        return f"{name} icin radyasyon hassas yukleri izole et; gorev zamanlamasini daha sakin pencereye kaydirmayi degerlendir."
    if over_turkiye:
        return f"{name} Turkiye uzerindeyken gorev veri alimini korumali modda tut; yer segmentiyle yuksek siklikta durum senkronu sagla."
    if orbit_class == "GEO":
        return f"{name} GEO slotunda plazma maruziyetine karsi charging ve termal emniyet kontrol listesine gec."
    return f"{name} gorev yukunde telemetri ve attitude kontrol sapmalarina karsi korumali izleme modunu aktif tut."


def _satellite_driver_label(driver: str) -> str:
    return {
        "drag": "suruklenme",
        "charging": "plazma charging",
        "radiation": "radyasyon",
        "service": "gorev hizmeti",
    }.get(driver, driver)


def _satellite_summary(
    name: str,
    mission_family: str,
    dominant_driver: str,
    dominant_score: float,
    over_turkiye: bool,
    visible_from_turkiye: bool,
) -> str:
    geometry_note = "Turkiye uzerinde" if over_turkiye else "Turkiye gorus penceresinde" if visible_from_turkiye else "Turkiye disi kesitte"
    driver_label = _satellite_driver_label(dominant_driver)
    return f"{mission_family} sinifindaki {name} icin baskin etki {driver_label} (%{dominant_score:.0f}); {geometry_note}."


def build_turkish_satellite_assessments(
    satellites: list[dict[str, Any]],
    xray_flux: float,
    proton_flux_pfu: float | None,
    f107_flux: float,
    speed: float,
    density: float,
    dst_index: float,
    bz: float,
    dynamic_pressure: float,
    geo_exposure_risk_percent: float,
    tec_delay_meters: float,
    gnss_risk_percent: float,
    precursor_risk_percent: float | None,
) -> tuple[list[TurkishSatelliteAssessment], float, str | None]:
    assessments: list[TurkishSatelliteAssessment] = []
    proton_term = clamp(math.log10(max((proton_flux_pfu or 0.1), 0.1)) * 22.0 + 14.0, 0.0, 100.0)
    xray_term = clamp((math.log10(max(xray_flux, 1e-8)) + 8.0) * 30.0, 0.0, 100.0)
    precursor_term = precursor_risk_percent or 0.0

    for satellite in satellites:
        name = str(satellite.get("name") or "Bilinmeyen Uydu")
        orbit_class = str(satellite.get("orbit_class") or "UNKNOWN")
        mission_family = str(satellite.get("mission_family") or "Ulusal uydu")
        altitude_km = as_float(satellite.get("altitude_km"), float("nan"))
        latitude = as_float(satellite.get("latitude"), float("nan"))
        longitude = as_float(satellite.get("longitude"), float("nan"))
        elevation_deg = as_float(satellite.get("elevation_deg"), float("nan"))
        azimuth_deg = as_float(satellite.get("azimuth_deg"), float("nan"))
        over_turkiye = bool(satellite.get("over_turkiye"))
        visible_from_turkiye = bool(satellite.get("visible_from_turkiye"))

        altitude_factor = 0.75
        if not math.isnan(altitude_km):
            altitude_factor = clamp((900.0 - altitude_km) / 500.0, 0.2, 1.2)

        drag_risk = clamp(
            ((max(f107_flux - 115.0, 0.0) * 0.34) + (density * 5.5) + (max(speed - 380.0, 0.0) / 12.0) + (max(abs(min(dst_index, 0.0)) - 20.0, 0.0) / 3.5))
            * (1.0 if orbit_class == "LEO" else 0.18 if orbit_class == "GEO" else 0.45)
            * altitude_factor,
            0.0,
            100.0,
        )
        charging_risk = clamp(
            (
                (geo_exposure_risk_percent * (1.0 if orbit_class == "GEO" else 0.45))
                + (dynamic_pressure * 6.5)
                + (abs(min(bz, 0.0)) * 2.0)
                + (proton_term * 0.38)
                + (xray_term * 0.16)
                + (precursor_term * 0.20)
            ),
            0.0,
            100.0,
        )
        radiation_risk = clamp(
            (proton_term * (0.92 if orbit_class == "GEO" else 0.74))
            + (xray_term * 0.34)
            + (precursor_term * 0.26)
            + (max(abs(min(dst_index, 0.0)) - 25.0, 0.0) / 2.8),
            0.0,
            100.0,
        )
        service_risk = clamp(
            (
                (gnss_risk_percent * (0.62 if orbit_class == "LEO" else 0.18))
                + (tec_delay_meters * 4.5)
                + (drag_risk * 0.28)
                + (charging_risk * 0.32)
                + (radiation_risk * 0.22)
                + (10.0 if over_turkiye else 4.0 if visible_from_turkiye else 0.0)
            ),
            0.0,
            100.0,
        )
        weights = _satellite_orbit_weight(orbit_class)
        overall_risk = clamp(
            (drag_risk * weights[0])
            + (charging_risk * weights[1])
            + (radiation_risk * weights[2])
            + (service_risk * weights[3]),
            0.0,
            100.0,
        )
        dominant_driver, dominant_score = _satellite_top_driver(
            {
                "drag": drag_risk,
                "charging": charging_risk,
                "radiation": radiation_risk,
                "service": service_risk,
            }
        )
        geometry_summary = (
            f"N2YO/TLE cozumune gore {name} {orbit_class} sinifinda"
            f"{'' if math.isnan(altitude_km) else f', yaklasik {altitude_km:.0f} km irtifada'}"
            f"{'' if math.isnan(latitude) or math.isnan(longitude) else f', {abs(latitude):.1f}° {'K' if latitude >= 0 else 'G'} / {abs(longitude):.1f}° {'D' if longitude >= 0 else 'B'} konumunda'}"
            f"; durum {('Turkiye uzerinde' if over_turkiye else 'Turkiye gorus penceresinde' if visible_from_turkiye else 'Turkiye disi kesitte')}."
        )
        if dominant_driver == "drag":
            risk_reason = (
                f"Asil risk konumdan degil, atmosferik zorlanmadan geliyor: F10.7 {f107_flux:.0f} sfu, yogunluk {density:.1f} p/cm3 "
                f"ve ruzgar {speed:.0f} km/s kombinasyonu ust atmosferde drag baskisini artiriyor."
            )
        elif dominant_driver == "charging":
            risk_reason = (
                f"Asil risk plazma ve alan baglasimindan geliyor: Pdyn {dynamic_pressure:.1f} nPa, Bz {bz:.1f} nT, Dst {dst_index:.1f} nT "
                f"ve GEO maruziyet skoru %{geo_exposure_risk_percent:.0f} charging baskisini yukseltiyor."
            )
        elif dominant_driver == "radiation":
            risk_reason = (
                f"Asil risk enerjik parcacik ve flare baskisindan geliyor: proton akisi {(proton_flux_pfu or 0.0):.1f} pfu, "
                f"X-ray {classify_xray(xray_flux)} ve prekursor %{precursor_term:.0f} birlikte radyasyon zorlanmasi uretiyor."
            )
        else:
            risk_reason = (
                f"Operasyonel risk; GNSS gecikmesi {tec_delay_meters:.1f} m, servis skoru %{service_risk:.0f} ve uydu geometrisi nedeniyle "
                f"yer segmenti ve gorev surekliligine yansiyor."
            )
        scientific_note = (
            "Konum bilgisi N2YO/TLE gozlemidir; risk puani ise NOAA/DONKI olcumleri ile fiziksel proxy'lerin birlikte yorumlandigi "
            "operasyonel bir model sonucudur. Konum tek basina tehlike nedeni degildir, yalnizca etkinin nerede gorulecegini baglamlar."
        )
        assessments.append(
            TurkishSatelliteAssessment(
                name=name,
                norad_id=int(as_float(satellite.get("norad_id"), 0.0)),
                mission_family=mission_family,
                orbit_class=orbit_class,
                data_source=str(satellite.get("data_source") or "TLE catalog"),
                observed_at=parse_timestamp(str(satellite.get("observed_at"))) if satellite.get("observed_at") else None,
                latitude=None if math.isnan(latitude) else round(latitude, 2),
                longitude=None if math.isnan(longitude) else round(longitude, 2),
                altitude_km=None if math.isnan(altitude_km) else round(altitude_km, 1),
                azimuth_deg=None if math.isnan(azimuth_deg) else round(azimuth_deg, 1),
                elevation_deg=None if math.isnan(elevation_deg) else round(elevation_deg, 1),
                over_turkiye=over_turkiye,
                visible_from_turkiye=visible_from_turkiye,
                drag_risk_percent=round(drag_risk, 1),
                charging_risk_percent=round(charging_risk, 1),
                radiation_risk_percent=round(radiation_risk, 1),
                service_risk_percent=round(service_risk, 1),
                overall_risk_percent=round(overall_risk, 1),
                dominant_driver=dominant_driver,
                summary=_satellite_summary(name, mission_family, dominant_driver, dominant_score, over_turkiye, visible_from_turkiye),
                observation_summary=geometry_summary,
                risk_reason=risk_reason,
                scientific_note=scientific_note,
                recommended_action=_satellite_action(name, orbit_class, dominant_driver, over_turkiye),
            )
        )

    assessments.sort(key=lambda item: item.overall_risk_percent, reverse=True)
    if not assessments:
        return assessments, 0.0, None

    top_risk = assessments[0].overall_risk_percent
    average_risk = sum(item.overall_risk_percent for item in assessments) / len(assessments)
    fleet_risk = round(clamp((top_risk * 0.58) + (average_risk * 0.42), 0.0, 100.0), 1)
    top_satellite = assessments[0]
    if top_risk >= 70.0:
        headline = f"Turk uydu filosunda kritik maruziyet: {top_satellite.name}"
    elif top_risk >= 48.0:
        headline = f"Turk uydu operasyon riskinde artis: {top_satellite.name}"
    elif top_risk >= 26.0:
        headline = f"Turk uydulari icin izleme seviyesi yukseliyor: {top_satellite.name}"
    else:
        headline = "Turk uydu filosu nominal sinirlar icinde"
    return assessments, fleet_risk, headline


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
    dst_index: float,
    bz: float,
    speed: float,
    density: float,
    local_risk_percent: float,
    magnetopause_standoff_re: float,
    geo_exposure_risk_percent: float,
    predicted_dbdt_nt_per_min: float,
    tec_delay_meters: float,
    precursor_risk_percent: float | None,
    precursor_horizon_hours: int | None,
    precursor_cme_speed_kms: float | None,
    official_radio_blackout_scale: str | None,
    official_solar_radiation_scale: str | None,
    proton_flux_pfu: float | None,
    tle_text: str,
    turkish_satellites: list[TurkishSatelliteAssessment],
) -> list[ThreatImpact]:
    watchlist, active_leo_count = extract_watchlist(tle_text)
    impacts: list[ThreatImpact] = []
    radio_scale_value = _scale_value(official_radio_blackout_scale)
    solar_scale_value = _scale_value(official_solar_radiation_scale)

    if xray_flux >= 1e-6:
        radio_severity: str
        if xray_flux >= 1e-4 or radio_scale_value >= 3:
            radio_severity = "critical"
        elif xray_flux >= 1e-5 or radio_scale_value >= 1:
            radio_severity = "high"
        else:
            radio_severity = "medium"
        impacts.append(
            ThreatImpact(
                id="radio-blackout",
                title="HF/VHF radyo kararmasi",
                severity=radio_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "Havacilik HF/VHF telsizleri",
                    "Amator kisa dalga haberlesme",
                    "Deniz ve acil durum HF baglantilari",
                ],
                rationale=f"GOES X-ray akis seviyesi {xray_class}; D-katmani sogurumu radyo ufkunu kapatabilir.",
            )
        )

    if solar_scale_value >= 1 or (proton_flux_pfu or 0.0) >= 10.0:
        radiation_severity: str
        if solar_scale_value >= 3 or (proton_flux_pfu or 0.0) >= 1000.0:
            radiation_severity = "critical"
        elif solar_scale_value >= 2 or (proton_flux_pfu or 0.0) >= 100.0:
            radiation_severity = "high"
        else:
            radiation_severity = "medium"
        impacts.append(
            ThreatImpact(
                id="aviation-radiation",
                title="Yuksek irtifa radyasyon dozu",
                severity=radiation_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "35.000+ feet ticari ucus rotalari",
                    "KAAN yuksek irtifa intikal profilleri",
                    "Kizilelma uzun menzil gorev koridorlari",
                ],
                rationale=(
                    f"GOES integral proton akisi {(proton_flux_pfu or 0.0):.1f} pfu ve resmi solar radyasyon bandi "
                    f"{official_solar_radiation_scale or 'S0'}; yuksek irtifa ucuslarinda goreli doz artisi bekleniyor."
                ),
            )
        )

    if f107_flux >= 140 and (density >= 3 or speed >= 500 or active_leo_count > 0):
        systems = watchlist or ["Starlink filosu", "IMECE", "Gokturk", "ISS"]
        impacts.append(
            ThreatImpact(
                id="orbital-drag",
                title="LEO uydu surtunme artisi",
                severity="high" if f107_flux >= 180 or density >= 8 or speed >= 650 else "medium",
                affected_systems=systems,
                rationale=f"F10.7={f107_flux:.0f} sfu ve plazma yogunlugu {density:.1f}; aktif LEO varlik sayisi yaklasik {active_leo_count}.",
            )
        )

    if magnetopause_standoff_re <= 7.2 or geo_exposure_risk_percent >= 25.0:
        geo_severity: str
        if magnetopause_standoff_re <= 6.6:
            geo_severity = "critical"
        elif magnetopause_standoff_re <= 6.9 or geo_exposure_risk_percent >= 55.0:
            geo_severity = "high"
        else:
            geo_severity = "medium"
        impacts.append(
            ThreatImpact(
                id="geo-direct-exposure",
                title="GEO plazma maruziyeti",
                severity=geo_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "TURKSAT GEO slotlari",
                    "GEO haberlesme yukleri",
                    "Yuksek irtifa plazma charging alt sistemleri",
                ],
                rationale=(
                    f"Manyetopoz {magnetopause_standoff_re:.2f} Re seviyesine kadar sikisti; "
                    "GEO koruma esigi 6.6 Re civarinda oldugu icin charging ve dogrudan solar ruzgar maruziyeti artabilir."
                ),
            )
        )

    if tec_delay_meters >= 3.0 or estimated_kp >= 5.0 or dst_index <= -60.0:
        gnss_severity: str
        if tec_delay_meters >= 8.0 or estimated_kp >= 7.0 or dst_index <= -120.0:
            gnss_severity = "critical"
        elif tec_delay_meters >= 5.0 or estimated_kp >= 6.0 or dst_index <= -90.0:
            gnss_severity = "high"
        else:
            gnss_severity = "medium"
        impacts.append(
            ThreatImpact(
                id="gnss-scintillation",
                title="GNSS sintilasyon ve seyrusefer sapmasi",
                severity=gnss_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "KAAN ve Kizilelma gorev profilleri",
                    "Sivil hassas yaklasma ve otonom inis sistemleri",
                    "Hassas muhimmat ve saha lojistik GNSS alicilari",
                ],
                rationale=(
                    f"GNSS L1 gecikme proxy degeri {tec_delay_meters:.1f} m; "
                    "iyonosferik elektron icerigi artisi metre sinifinda seyrusefer sapmasi uretebilir."
                ),
            )
        )

    if predicted_dbdt_nt_per_min >= 18.0 or estimated_kp >= 4.5 or bz <= -8 or dst_index <= -50 or local_risk_percent >= 45:
        gic_severity: str
        if predicted_dbdt_nt_per_min >= 85.0 or estimated_kp >= 7 or bz <= -15 or dst_index <= -150:
            gic_severity = "critical"
        elif predicted_dbdt_nt_per_min >= 45.0 or estimated_kp >= 5 or bz <= -10 or dst_index <= -80 or local_risk_percent >= 60:
            gic_severity = "high"
        else:
            gic_severity = "medium"
        impacts.append(
            ThreatImpact(
                id="gic-dbdt",
                title="GIC ve hizli dB/dt riski",
                severity=gic_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "TEIAS 154/400 kV iletim omurgasi",
                    "Uzun yuksek gerilim iletim hatlari ve buyuk trafolar",
                    "Dogu-bati uzanimli ana enerji koridorlari",
                ],
                rationale=(
                    f"dB/dt proxy {predicted_dbdt_nt_per_min:.1f} nT/dk, Kp {estimated_kp:.1f} ve Bz {bz:.1f} nT; "
                    "Faraday temelli induksiyon baskisi trafo doygunlugu ve termal zorlanmayi buyutuyor."
                ),
            )
        )

    if precursor_risk_percent is not None and precursor_risk_percent >= 32.0:
        precursor_severity: str
        if precursor_risk_percent >= 68.0:
            precursor_severity = "high"
        elif precursor_risk_percent >= 48.0:
            precursor_severity = "medium"
        else:
            precursor_severity = "low"
        impacts.append(
            ThreatImpact(
                id="cme-precursor",
                title="CME ve flare prekursor izleme penceresi",
                severity=precursor_severity,  # type: ignore[arg-type]
                affected_systems=[
                    "Uydu gorev planlama ekipleri",
                    "Sivil / askeri havacilik dispatch merkezleri",
                    "TEIAS ve kritik altyapi koordinasyon masalari",
                ],
                rationale=(
                    f"DONKI/GOES prekursor katmani %{precursor_risk_percent:.0f} risk ve "
                    f"{precursor_horizon_hours if precursor_horizon_hours is not None else '--'} saat ufuk uretiyor; "
                    f"CME hizi {(precursor_cme_speed_kms or 0.0):.0f} km/s civarinda."
                ),
            )
        )

    if turkish_satellites:
        top_satellite = turkish_satellites[0]
        top_risk = top_satellite.overall_risk_percent
        if top_risk >= 28.0:
            satellite_severity: str
            if top_risk >= 72.0:
                satellite_severity = "critical"
            elif top_risk >= 52.0:
                satellite_severity = "high"
            else:
                satellite_severity = "medium"
            impacts.append(
                ThreatImpact(
                    id="turkish-satellite-fleet",
                    title="Turk uydu filosunda uzay hava maruziyeti",
                    severity=satellite_severity,  # type: ignore[arg-type]
                    affected_systems=[item.name for item in turkish_satellites[:5]],
                    rationale=(
                        f"N2YO/TLE tabanli uydu analizi en yuksek riski {top_satellite.name} icin %{top_risk:.0f} olarak hesapliyor; "
                        f"baskin surucu {top_satellite.dominant_driver}. {top_satellite.summary}"
                    ),
                )
            )

    return impacts


def build_sops(impacts: list[ThreatImpact]) -> list[SopAction]:
    actions: list[SopAction] = []
    impact_ids = {impact.id for impact in impacts}
    if "gic-dbdt" in impact_ids:
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
            ]
        )
    if "gnss-scintillation" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Savunma Havaciligi",
                    action="KAAN ve Kizilelma gorev paketlerinde INS, radar-aided ve yer referansli yedek seyrusefer modlarini aktif hazirlikta tut.",
                    status="urgent",
                ),
                SopAction(
                    sector="Sivil Havacilik",
                    action="GNSS hassas yaklasma prosedurlerini gozden gecir; SBAS/GBAS ve konvansiyonel yedeklere gecis planini aktiflestir.",
                    status="ready",
                ),
                SopAction(
                    sector="Tarim ve Lojistik",
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
    if "aviation-radiation" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Havacilik",
                    action="35.000 feet ustu rotalarda radyasyon prosedurunu ac; gerekirse 25.000 feet bandina inis ve SATCOM yuk dengelemesini degerlendir.",
                    status="urgent",
                ),
                SopAction(
                    sector="Savunma Havaciligi",
                    action="KAAN ve Kizilelma gorev paketlerinde yuksek irtifa profillerini gozden gecir; ataletsel/yer referansli yedekleme planini hazirla.",
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
    if "geo-direct-exposure" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="GEO Uydu Operasyonlari",
                    action="TURKSAT sinifindaki GEO yuklerde charging mitigasyonu, transponder duty-cycle dengelemesi ve safe-hold prosedurlerini hazirla.",
                    status="urgent",
                ),
            ]
        )
    if "turkish-satellite-fleet" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Milli Uydu Operasyonlari",
                    action="IMECE, GOKTURK ve TURKSAT gorev kontrol ekiplerinde charging, drag ve payload sagligi icin ortak durum masasi ac.",
                    status="urgent",
                ),
                SopAction(
                    sector="Yer Segmenti",
                    action="Turk uydu telemetri pencerelerini siklastir; attitude, termal ve guc alt sistemlerinde anomaly watch moduna gec.",
                    status="ready",
                ),
            ]
        )
    if "cme-precursor" in impact_ids:
        actions.extend(
            [
                SopAction(
                    sector="Kurumsal Koordinasyon",
                    action="24-72 saatlik prekursor penceresi icin havacilik, uydu ve sebeke ekiplerinde vardiya on hazirligini yukselt.",
                    status="ready",
                ),
                SopAction(
                    sector="Planlama",
                    action="CME varis penceresi kesinlesene kadar görev profilleri, kritik bakimlar ve yuksek riskli operasyonlar icin alternatif zamanlama hazirla.",
                    status="ready",
                ),
            ]
        )
    return actions


def build_decision_commentary(
    observed_at: datetime,
    eta_seconds: int | None,
    eta_window_start_seconds: int | None,
    eta_window_end_seconds: int | None,
    local_risk_percent: float,
    risk_band_low: float,
    risk_band_high: float,
    magnetopause_standoff_re: float,
    predicted_dbdt_nt_per_min: float,
    tec_delay_meters: float,
    precursor_risk_percent: float | None,
    precursor_horizon_hours: int | None,
    ml_predicted_dst_index: float | None,
    ml_predicted_dst_band_low: float | None,
    ml_predicted_dst_band_high: float | None,
    turkish_satellite_risk_percent: float,
    turkish_satellite_headline: str | None,
    turkish_satellites: list[TurkishSatelliteAssessment],
    forecast_confidence_percent: float,
) -> list[DecisionCommentary]:
    commentary: list[DecisionCommentary] = []

    if eta_seconds is not None:
        commentary.append(
            DecisionCommentary(
                id="eta",
                title="L1 varis penceresi",
                value=f"{eta_seconds} s",
                category="timeline",
                basis="fused",
                explanation=(
                    f"ETA, L1 plazma hizi ile bow-shock/yavaslama duzeltmesinin birlikte hesaplanmasidir. Pencere "
                    f"{eta_window_start_seconds or eta_seconds}-{eta_window_end_seconds or eta_seconds} s araliginda tutuluyor."
                ),
                implication="Bu, dunyaya ulasma aninin tek sayi degil pencere olarak ele alinmasi gerektigini gosterir.",
                confidence_note=f"Tahmin guveni %{forecast_confidence_percent:.0f}.",
            )
        )

    commentary.append(
        DecisionCommentary(
            id="national-risk",
            title="Ulusal risk neden boyle?",
            value=f"%{local_risk_percent:.1f}",
            category="risk",
            basis="fused",
            explanation=(
                f"Ulusal risk; Kp, Dst, Bz, hiz, yogunluk ve manyetik enlem uzerine kurulu fizik skorunun sonucudur. "
                f"Bu nedenle panelde tek nokta yerine %{risk_band_low:.1f}-%{risk_band_high:.1f} araligi verilir."
            ),
            implication="Bu skor kritik altyapi, havacilik ve uydu ekiplerinin ayni operasyon resmiyle hareket etmesi icin kullanilir.",
            confidence_note="Risk dogrudan olculen degil, olcum + fizik modelinden uretilen operasyonel skordur.",
        )
    )

    commentary.append(
        DecisionCommentary(
            id="magnetopause",
            title="Manyetopoz durumu",
            value=f"{magnetopause_standoff_re:.1f} Re",
            category="physics",
            basis="modeled",
            explanation=(
                "Manyetopoz stand-off mesafesi, dinamik basinc ve Bz ile Shue-temelli bir yaklasimla hesaplanir. "
                "Deger kuculdukce GEO koridorunun plazma maruziyeti artar."
            ),
            implication="Ozellikle TURKSAT benzeri GEO yuklerde charging ve alt sistem zorlanmasi icin erken uyaridir.",
            confidence_note="Bu alan dogrudan olculmez; L1 telemetriden fiziksel model ile turetilir.",
        )
    )

    commentary.append(
        DecisionCommentary(
            id="dbdt",
            title="dB/dt yorumu",
            value=f"{predicted_dbdt_nt_per_min:.1f} nT/dk",
            category="grid",
            basis="modeled",
            explanation=(
                "dB/dt su an yer manyetometresi asimilasyonu degil, L1 tarihcesi ve beklenen Dst ile kurulan fiziksel proxy'dir. "
                "Bu nedenle enerji yorumu trend bazlidir, sahadaki mutlak akimin yerine gecmez."
            ),
            implication="TEIAS ve buyuk trafo operasyonlarinda yuk/termal hazirlik kararlarini tetikler.",
            confidence_note="Yerel istasyon verisi gelirse bu panel dogrudan gozlemsel hale gelir.",
        )
    )

    commentary.append(
        DecisionCommentary(
            id="gnss",
            title="GNSS gecikmesi yorumu",
            value=f"{tec_delay_meters:.1f} m",
            category="navigation",
            basis="modeled",
            explanation=(
                "GNSS sapmasi su an IRI/IONEX asimilasyonu degil; Dst, Kp, F10.7 ve Bz uzerinden uretilen TEC proxy'sine dayanir. "
                "Bu nedenle konum hatasi mutlak degil, operasyonel risk gostergesidir."
            ),
            implication="KAAN, Kizilelma ve sivil hassas yaklasma operasyonlarinda INS/SBAS/GBAS yedek kararlarini besler.",
            confidence_note="Gercek IONEX/IRI baglanti geldikce bu alan daha dogrudan bilimsel hale gelir.",
        )
    )

    if precursor_risk_percent is not None:
        commentary.append(
            DecisionCommentary(
                id="precursor",
                title="Prekursor yorumu",
                value=f"%{precursor_risk_percent:.1f}",
                category="precursor",
                basis="fused",
                explanation=(
                    f"Prekursor katmani, DONKI CME/ENLIL ve GOES flare sinyallerini okuyarak {precursor_horizon_hours or '--'} saatlik "
                    "on uyari penceresi uretir."
                ),
                implication="Bu skor 'kesin varis zamani' degil, orta ufuklu hazirlik seviyesi olarak okunmalidir.",
                confidence_note="CME tahmini dogasi geregi olasiliksaldir; bu yuzden panelde tek sayi yerine ufuk ve guven verilir.",
            )
        )

    if ml_predicted_dst_index is not None:
        commentary.append(
            DecisionCommentary(
                id="ml-dst",
                title="ML Dst yorumu",
                value=f"{ml_predicted_dst_index:.1f} nT",
                category="ml",
                basis="modeled",
                explanation=(
                    f"XGBoost modeli 60 dakika sonraki Dst'yi tahmin eder ve bandi "
                    f"{ml_predicted_dst_band_low if ml_predicted_dst_band_low is not None else '--'} / "
                    f"{ml_predicted_dst_band_high if ml_predicted_dst_band_high is not None else '--'} ile verilir."
                ),
                implication="ML cikti tek basina karar vermez; fizik katmani ile birlikte risk ve SOP'ye donusturulur.",
                confidence_note="Model istatistiksel tahmindir; dogrudan olcum degildir.",
            )
        )

    if turkish_satellites:
        top_satellite = turkish_satellites[0]
        commentary.append(
            DecisionCommentary(
                id="satellite-fleet",
                title="Turk uydu filosu yorumu",
                value=f"%{turkish_satellite_risk_percent:.1f}",
                category="satellite",
                basis="fused",
                explanation=(
                    f"En yuksek riskli varlik {top_satellite.name}. {top_satellite.observation_summary} {top_satellite.risk_reason}"
                ),
                implication="Konum, etkinin hangi gorev ve yer segmenti penceresinde hissedilecegini baglamlar; asil risk uzay hava suruculerinden gelir.",
                confidence_note=top_satellite.scientific_note,
            )
        )

    return commentary


def build_summary_headline(
    early_detection: bool,
    local_risk_percent: float,
    cme_count: int,
    estimated_kp: float,
    dst_index: float,
    magnetopause_standoff_re: float,
    predicted_dbdt_nt_per_min: float,
    precursor_risk_percent: float | None,
    precursor_horizon_hours: int | None,
    turkish_satellite_risk_percent: float = 0.0,
    turkish_satellite_headline: str | None = None,
) -> str:
    if turkish_satellite_risk_percent >= 68.0 and turkish_satellite_headline:
        return turkish_satellite_headline
    if magnetopause_standoff_re <= 6.6:
        return "KALKAN DARALIYOR: GEO koridoru plazmaya acik"
    if predicted_dbdt_nt_per_min >= 85.0:
        return "GRID UYARISI: dB/dt hizla tirmaniyor"
    if local_risk_percent < 45.0 and precursor_risk_percent is not None and precursor_risk_percent >= 58.0:
        if precursor_horizon_hours is not None:
            return f"CME PREKURSORU: {precursor_horizon_hours} sa icin erken izleme"
        return "CME PREKURSORU: orta vadeli risk penceresi acildi"
    if early_detection and (estimated_kp >= 5.0 or dst_index <= -80.0 or local_risk_percent >= 60.0):
        return "KIRMIZI ALARM: Erken tespit basarili"
    if local_risk_percent >= 65 or estimated_kp >= 6.0 or dst_index <= -100.0:
        return "Turkiye uzerindeki manyetik yuk hizla artiyor"
    if cme_count:
        return "Arka planda CME akisi izleniyor"
    return "Uzay havasi izleme modunda"


def severity_from_context(
    early_detection: bool,
    local_risk_percent: float,
    impacts: list[ThreatImpact],
    ml_risk_percent: float | None,
    precursor_risk_percent: float | None,
    precursor_horizon_hours: int | None,
    official_geomagnetic_scale: str | None,
    official_radio_blackout_scale: str | None,
    official_solar_radiation_scale: str | None,
) -> str | None:
    geomagnetic_scale = _scale_value(official_geomagnetic_scale)
    radio_scale = _scale_value(official_radio_blackout_scale)
    solar_scale = _scale_value(official_solar_radiation_scale)
    if (
        any(impact.severity == "critical" for impact in impacts)
        or (early_detection and local_risk_percent >= 60)
        or geomagnetic_scale >= 3
        or radio_scale >= 3
        or solar_scale >= 3
        or local_risk_percent >= 80
    ):
        return "critical"
    if (
        any(impact.severity == "high" for impact in impacts)
        or geomagnetic_scale >= 1
        or radio_scale >= 1
        or solar_scale >= 1
        or local_risk_percent >= 50
        or ((precursor_risk_percent or 0.0) >= 60.0 and (precursor_horizon_hours is None or precursor_horizon_hours <= 72))
        or (ml_risk_percent or 0) >= 60
    ):
        return "warning"
    if impacts or local_risk_percent >= 20 or (precursor_risk_percent or 0.0) >= 28.0:
        return "watch"
    return None


def build_dashboard_artifacts(bundle: SpaceWeatherBundle, predictor: PredictiveEngine, settings: Settings) -> tuple[TelemetrySnapshot, CrisisAlert | None]:
    history = build_history_frame(bundle)

    latest_mag = bundle.mag[-1] if bundle.mag else {}
    latest_plasma = bundle.plasma[-1] if bundle.plasma else {}
    latest_official_kp = bundle.planetary_kp[-1] if bundle.planetary_kp else {}
    latest_estimated_kp = bundle.minute_kp[-1] if bundle.minute_kp else {}
    latest_dst = bundle.dst[-1] if bundle.dst else {}
    latest_xray = max(
        bundle.xray,
        key=lambda row: as_float(row.get("flux")) if row.get("energy") == "0.1-0.8nm" else -1.0,
        default={},
    )
    proton_flux_pfu = latest_proton_flux_pfu(bundle)
    latest_f107 = bundle.f107[0] if bundle.f107 else {}

    speed = as_float(latest_plasma.get("speed"))
    density = as_float(latest_plasma.get("density"))
    temperature = as_float(latest_plasma.get("temperature"))
    bz = as_float(latest_mag.get("bz_gsm"))
    bt = as_float(latest_mag.get("bt"))
    dst_index = as_float(latest_dst.get("dst")) if latest_dst else compute_dst_proxy(bz, speed, density)
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
    observed_at = max(
        parse_timestamp(str(latest_mag.get("time_tag"))) if latest_mag else datetime.now(timezone.utc),
        parse_timestamp(str(latest_plasma.get("time_tag"))) if latest_plasma else datetime.now(timezone.utc),
        parse_timestamp(str(latest_estimated_kp.get("time_tag"))) if latest_estimated_kp else datetime.now(timezone.utc),
        parse_timestamp(str(latest_dst.get("time_tag"))) if latest_dst else datetime.now(timezone.utc),
    )
    magnetic_latitude = compute_magnetic_latitude(settings.turkiye_center_lat, settings.turkiye_center_lon)
    local_solar_hour_value = local_solar_hour(observed_at, settings.turkiye_center_lon)
    official_watch_headline, official_alert_headline = latest_official_alerts(bundle)
    official_geomagnetic_scale, official_radio_blackout_scale, official_solar_radiation_scale = latest_official_scales(bundle)
    official_forecast_kp_max, official_forecast_scale = official_forecast_kp(bundle)
    precursor = build_precursor_outlook(
        bundle=bundle,
        xray_flux=xray_flux,
        xray_class=xray_class,
        observed_at=observed_at,
        official_forecast_kp_max=official_forecast_kp_max,
        official_forecast_scale=official_forecast_scale,
    )

    early_detection = bz <= -10 and speed >= 500
    auroral_expansion_percent = clamp(((estimated_kp - 4.0) / 5.0) * 100.0, 0.0, 100.0)
    base_local_risk_percent = compute_local_risk_percent(
        estimated_kp=estimated_kp,
        bz=bz,
        speed=speed,
        density=density,
        dst_index=dst_index,
        magnetic_latitude=magnetic_latitude,
        early_detection=early_detection,
    )

    prediction = predictor.predict(history, magnetic_latitude)
    ml_risk_percent = None
    ml_risk_band_low = None
    ml_risk_band_high = None
    ml_predicted_dst_index = None
    ml_predicted_dst_band_low = None
    ml_predicted_dst_band_high = None
    ml_baseline_dst_index = None
    ml_target_name = None
    ml_target_unit = None
    ml_feature_contributions: list[ModelContribution] = []
    ml_lead_time_minutes = prediction.lead_time_minutes if prediction else None
    dynamic_pressure = dynamic_pressure_npa(density, speed)
    magnetopause_state = estimate_magnetopause_state(dynamic_pressure, bz)
    propagation = estimate_dynamic_propagation(
        history=history,
        current_speed=speed,
        density_cm3=density,
        bz_nt=bz,
        l1_distance_km=settings.l1_distance_km,
        standoff_re=magnetopause_state.standoff_re,
    )
    eta_seconds = propagation.median_seconds
    eta_window_start_seconds = propagation.earliest_seconds
    eta_window_end_seconds = propagation.latest_seconds
    effective_dst_for_proxies = min(dst_index, prediction.predicted_dst_p50) if prediction else dst_index
    tec_state = estimate_tec_delay_proxy(
        dst_index=effective_dst_for_proxies,
        estimated_kp=estimated_kp,
        f107_flux=f107_flux,
        bz_nt=bz,
        observed_at=observed_at,
        longitude=settings.turkiye_center_lon,
        regional_weight=1.08,
    )
    predicted_dbdt_nt_per_min = estimate_dbdt_proxy_nt_per_min(
        history=history,
        predicted_dst_index=prediction.predicted_dst_p50 if prediction else dst_index,
        dynamic_pressure=dynamic_pressure,
    )
    physics_bonus = physics_residual_risk_bonus(
        predicted_dbdt_nt_per_min=predicted_dbdt_nt_per_min,
        magnetopause_standoff_re=magnetopause_state.standoff_re,
        tec_delay_meters=tec_state.delay_meters_l1,
        geo_exposure_risk_percent=magnetopause_state.geo_exposure_risk_percent,
    )
    local_risk_percent = clamp(base_local_risk_percent + physics_bonus, 0.0, 100.0)
    turkish_satellite_assessments, turkish_satellite_risk_percent, turkish_satellite_headline = build_turkish_satellite_assessments(
        satellites=bundle.turkish_satellites,
        xray_flux=xray_flux,
        proton_flux_pfu=proton_flux_pfu,
        f107_flux=f107_flux,
        speed=speed,
        density=density,
        dst_index=dst_index,
        bz=bz,
        dynamic_pressure=dynamic_pressure,
        geo_exposure_risk_percent=magnetopause_state.geo_exposure_risk_percent,
        tec_delay_meters=tec_state.delay_meters_l1,
        gnss_risk_percent=tec_state.gnss_risk_percent,
        precursor_risk_percent=precursor.risk_percent,
    )
    if prediction:
        ml_predicted_dst_index = prediction.predicted_dst_index
        ml_predicted_dst_band_low = prediction.predicted_dst_p10
        ml_predicted_dst_band_high = prediction.predicted_dst_p90
        ml_baseline_dst_index = prediction.baseline_dst_index
        ml_target_name = prediction.target_name
        ml_target_unit = prediction.target_unit
        ml_feature_contributions = [
            ModelContribution(
                feature=item.feature,
                label=item.label,
                contribution=item.contribution,
                direction=item.direction,
            )
            for item in prediction.feature_contributions
        ]
        ml_risk_percent = ml_risk_from_predicted_dst(
            predicted_dst_index=prediction.predicted_dst_p50,
            estimated_kp=estimated_kp,
            bz=bz,
            speed=speed,
            density=density,
            magnetic_latitude=magnetic_latitude,
            early_detection=early_detection,
        )
        ml_risk_percent = round(clamp(ml_risk_percent + (physics_bonus * 0.85), 0.0, 100.0), 1)
        band_candidates = []
        if prediction.predicted_dst_p10 is not None:
            band_candidates.append(
                round(
                    clamp(
                        ml_risk_from_predicted_dst(
                            predicted_dst_index=prediction.predicted_dst_p10,
                            estimated_kp=estimated_kp,
                            bz=bz,
                            speed=speed,
                            density=density,
                            magnetic_latitude=magnetic_latitude,
                            early_detection=early_detection,
                        ) + (physics_bonus * 0.85),
                        0.0,
                        100.0,
                    ),
                    1,
                )
            )
        if prediction.predicted_dst_p90 is not None:
            band_candidates.append(
                round(
                    clamp(
                        ml_risk_from_predicted_dst(
                            predicted_dst_index=prediction.predicted_dst_p90,
                            estimated_kp=estimated_kp,
                            bz=bz,
                            speed=speed,
                            density=density,
                            magnetic_latitude=magnetic_latitude,
                            early_detection=early_detection,
                        ) + (physics_bonus * 0.85),
                        0.0,
                        100.0,
                    ),
                    1,
                )
            )
        if band_candidates:
            ml_risk_band_low = round(min(band_candidates + [ml_risk_percent]), 1)
            ml_risk_band_high = round(max(band_candidates + [ml_risk_percent]), 1)

    impacts = build_impacts(
        xray_flux=xray_flux,
        xray_class=xray_class,
        f107_flux=f107_flux,
        estimated_kp=estimated_kp,
        dst_index=dst_index,
        bz=bz,
        speed=speed,
        density=density,
        local_risk_percent=local_risk_percent,
        magnetopause_standoff_re=magnetopause_state.standoff_re,
        geo_exposure_risk_percent=magnetopause_state.geo_exposure_risk_percent,
        predicted_dbdt_nt_per_min=predicted_dbdt_nt_per_min,
        tec_delay_meters=tec_state.delay_meters_l1,
        precursor_risk_percent=precursor.risk_percent,
        precursor_horizon_hours=precursor.horizon_hours,
        precursor_cme_speed_kms=precursor.cme_speed_kms,
        official_radio_blackout_scale=official_radio_blackout_scale,
        official_solar_radiation_scale=official_solar_radiation_scale,
        proton_flux_pfu=proton_flux_pfu,
        tle_text=bundle.tle_text,
        turkish_satellites=turkish_satellite_assessments,
    )
    sops = build_sops(impacts)

    forecast_confidence_percent, data_freshness_seconds = compute_forecast_confidence_percent(bundle, history, observed_at, predictor)
    source_coverage_percent = compute_source_coverage_percent(bundle)

    telemetry = TelemetrySnapshot(
        observed_at=observed_at,
        mode=bundle.mode,
        solar_wind_speed=round(speed, 1),
        bz=round(bz, 2),
        bt=round(bt, 2),
        density=round(density, 2),
        temperature=round(temperature, 1),
        dynamic_pressure_npa=magnetopause_state.dynamic_pressure_npa,
        kp_index=round(kp_index, 2),
        estimated_kp=round(estimated_kp, 2),
        dst_index=round(dst_index, 1),
        xray_flux=xray_flux,
        xray_class=xray_class,
        proton_flux_pfu=proton_flux_pfu,
        f107_flux=round(f107_flux, 2),
        cme_count=len(bundle.cmes),
        early_detection=early_detection,
        eta_seconds=eta_seconds,
        eta_window_start_seconds=eta_window_start_seconds,
        eta_window_end_seconds=eta_window_end_seconds,
        bow_shock_delay_seconds=propagation.bow_shock_delay_seconds,
        local_risk_percent=round(local_risk_percent, 1),
        risk_band_low=0.0,
        risk_band_high=0.0,
        local_magnetic_latitude=round(magnetic_latitude, 2),
        local_solar_hour=round(local_solar_hour_value, 2),
        auroral_expansion_percent=round(auroral_expansion_percent, 1),
        magnetopause_standoff_re=magnetopause_state.standoff_re,
        magnetopause_shape_alpha=magnetopause_state.shape_alpha,
        geo_exposure_risk_percent=magnetopause_state.geo_exposure_risk_percent,
        geo_direct_exposure=magnetopause_state.geo_direct_exposure,
        predicted_dbdt_nt_per_min=predicted_dbdt_nt_per_min,
        tec_vertical_tecu=tec_state.vertical_tec_tecu,
        tec_delay_meters=tec_state.delay_meters_l1,
        gnss_risk_percent=tec_state.gnss_risk_percent,
        forecast_confidence_percent=forecast_confidence_percent,
        source_coverage_percent=source_coverage_percent,
        data_freshness_seconds=data_freshness_seconds,
        storm_scale_band="G0",
        official_geomagnetic_scale=official_geomagnetic_scale,
        official_radio_blackout_scale=official_radio_blackout_scale,
        official_solar_radiation_scale=official_solar_radiation_scale,
        official_watch_headline=official_watch_headline,
        official_alert_headline=official_alert_headline,
        official_forecast_kp_max=official_forecast_kp_max,
        official_forecast_scale=official_forecast_scale,
        precursor_risk_percent=precursor.risk_percent,
        precursor_risk_band_low=precursor.risk_band_low,
        precursor_risk_band_high=precursor.risk_band_high,
        precursor_horizon_hours=precursor.horizon_hours,
        precursor_confidence_percent=precursor.confidence_percent,
        precursor_headline=precursor.headline,
        precursor_cme_speed_kms=precursor.cme_speed_kms,
        precursor_arrival_at=precursor.arrival_at,
        precursor_is_earth_directed=precursor.earth_directed,
        ml_risk_percent=ml_risk_percent,
        ml_risk_band_low=ml_risk_band_low,
        ml_risk_band_high=ml_risk_band_high,
        ml_predicted_dst_index=ml_predicted_dst_index,
        ml_predicted_dst_band_low=ml_predicted_dst_band_low,
        ml_predicted_dst_band_high=ml_predicted_dst_band_high,
        ml_baseline_dst_index=ml_baseline_dst_index,
        ml_target_name=ml_target_name,
        ml_target_unit=ml_target_unit,
        ml_feature_contributions=ml_feature_contributions,
        ml_lead_time_minutes=ml_lead_time_minutes,
        validation_mae=None,
        validation_band_coverage=None,
        validation_rows=None,
        validation_horizon_minutes=None,
        turkish_satellite_count=len(turkish_satellite_assessments),
        turkish_satellite_risk_percent=turkish_satellite_risk_percent,
        turkish_satellite_headline=turkish_satellite_headline,
        turkish_satellites=turkish_satellite_assessments,
        decision_commentary=[],
        summary_headline=build_summary_headline(
            early_detection,
            local_risk_percent,
            len(bundle.cmes),
            estimated_kp,
            dst_index,
            magnetopause_state.standoff_re,
            predicted_dbdt_nt_per_min,
            precursor.risk_percent,
            precursor.horizon_hours,
            turkish_satellite_risk_percent,
            turkish_satellite_headline,
        ),
        kp_history=build_kp_history(bundle),
        source_statuses=bundle.source_statuses,
        power_lines=bundle.power_lines,
        heat_grid=build_heat_grid(settings, local_risk_percent, auroral_expansion_percent),
    )
    (
        telemetry.risk_band_low,
        telemetry.risk_band_high,
        heuristic_ml_low,
        heuristic_ml_high,
    ) = compute_risk_bands(history, telemetry.local_risk_percent, telemetry.ml_risk_percent, telemetry.forecast_confidence_percent, predictor)
    if telemetry.ml_risk_band_low is None:
        telemetry.ml_risk_band_low = heuristic_ml_low
    if telemetry.ml_risk_band_high is None:
        telemetry.ml_risk_band_high = heuristic_ml_high
    telemetry.storm_scale_band = estimate_storm_scale_band(history, telemetry.estimated_kp, telemetry.forecast_confidence_percent)
    (
        telemetry.validation_mae,
        telemetry.validation_band_coverage,
        telemetry.validation_rows,
        telemetry.validation_horizon_minutes,
    ) = validation_metrics(predictor, telemetry.ml_lead_time_minutes)
    telemetry.decision_commentary = build_decision_commentary(
        observed_at=telemetry.observed_at,
        eta_seconds=telemetry.eta_seconds,
        eta_window_start_seconds=telemetry.eta_window_start_seconds,
        eta_window_end_seconds=telemetry.eta_window_end_seconds,
        local_risk_percent=telemetry.local_risk_percent,
        risk_band_low=telemetry.risk_band_low,
        risk_band_high=telemetry.risk_band_high,
        magnetopause_standoff_re=telemetry.magnetopause_standoff_re,
        predicted_dbdt_nt_per_min=telemetry.predicted_dbdt_nt_per_min,
        tec_delay_meters=telemetry.tec_delay_meters,
        precursor_risk_percent=telemetry.precursor_risk_percent,
        precursor_horizon_hours=telemetry.precursor_horizon_hours,
        ml_predicted_dst_index=telemetry.ml_predicted_dst_index,
        ml_predicted_dst_band_low=telemetry.ml_predicted_dst_band_low,
        ml_predicted_dst_band_high=telemetry.ml_predicted_dst_band_high,
        turkish_satellite_risk_percent=telemetry.turkish_satellite_risk_percent,
        turkish_satellite_headline=telemetry.turkish_satellite_headline,
        turkish_satellites=telemetry.turkish_satellites,
        forecast_confidence_percent=telemetry.forecast_confidence_percent,
    )

    severity = severity_from_context(
        early_detection,
        local_risk_percent,
        impacts,
        ml_risk_percent,
        precursor.risk_percent,
        precursor.horizon_hours,
        official_geomagnetic_scale,
        official_radio_blackout_scale,
        official_solar_radiation_scale,
    )
    if severity is None:
        return telemetry, None

    title = telemetry.summary_headline
    subtitle = (
        f"Turkiye geneli risk %{telemetry.local_risk_percent:.0f}. "
        f"Anlik Bz {telemetry.bz:.1f} nT, ruzgar {telemetry.solar_wind_speed:.0f} km/s, Kp {telemetry.estimated_kp:.1f}."
    )
    if telemetry.precursor_risk_percent is not None and telemetry.precursor_horizon_hours is not None:
        subtitle += f" CME/flare prekursor ufku {telemetry.precursor_horizon_hours} sa, risk %{telemetry.precursor_risk_percent:.0f}."
    if telemetry.turkish_satellite_count:
        subtitle += (
            f" Turk uydu filosu %{telemetry.turkish_satellite_risk_percent:.0f} riskte; "
            f"en kritik varlik {telemetry.turkish_satellites[0].name}."
        )
    narrative = (
        "GOES X-ray ve DONKI CME prekursor katmani, L1 telemetrisi gelmeden once 24-72 saatlik outlook uretir; fizik motoru "
        "Shue-temelli manyetopoz sikismasi, bow-shock gecikmesi, dB/dt induksiyon proxy'si ve TEC/GNSS gecikme proxy'sini "
        "DSCOVR L1 telemetrisiyle birlikte hesapliyor; XGBoost tahmini son 6 saate kadar uzanan coklu olcekli paternlerden "
        "60 dakika sonraki Dst hedefini uretiyor. N2YO tabanli Turk uydu filo analizi de bu katmanin ustune baglanarak "
        "IMECE, GOKTURK ve TURKSAT yuku icin drag, charging, radyasyon ve gorev etkisini hesapliyor. Deterministik fizik, "
        "prekursor analizi ve ML birlikte cihaz etkisi, guven bandi ve SOP listesine donusturuluyor."
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
