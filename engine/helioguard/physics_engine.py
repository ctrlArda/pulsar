from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd


EARTH_RADIUS_KM = 6371.0
GPS_L1_FREQUENCY_HZ = 1_575_420_000.0
IONO_DELAY_PER_TECU_M = 40.3e16 / (GPS_L1_FREQUENCY_HZ**2)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalize_timestamp(value: object) -> datetime:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return datetime.now(timezone.utc)
    timestamp = parsed.to_pydatetime()
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def local_solar_hour(observed_at: object, longitude: float) -> float:
    timestamp = _normalize_timestamp(observed_at)
    utc_hour = timestamp.hour + (timestamp.minute / 60.0) + (timestamp.second / 3600.0)
    return float((utc_hour + (longitude / 15.0)) % 24.0)


def dynamic_pressure_npa(density_cm3: float, speed_kms: float) -> float:
    # Solar-wind dynamic pressure approximation in nPa.
    return max(0.0, 1.6726e-6 * max(density_cm3, 0.0) * max(speed_kms, 0.0) ** 2)


@dataclass(slots=True)
class MagnetopauseState:
    dynamic_pressure_npa: float
    standoff_re: float
    shape_alpha: float
    geo_exposure_risk_percent: float
    geo_direct_exposure: bool


def estimate_magnetopause_state(dynamic_pressure: float, bz_nt: float) -> MagnetopauseState:
    # Shue-style subsolar stand-off approximation driven by solar-wind pressure and IMF Bz.
    pressure = max(dynamic_pressure, 0.2)
    standoff_re = (10.22 + 1.29 * math.tanh(0.184 * (bz_nt + 8.14))) * (pressure ** (-1.0 / 6.6))
    shape_alpha = (0.58 - 0.007 * bz_nt) * (1.0 + 0.024 * math.log(pressure))
    geo_margin = clamp((6.9 - standoff_re) / 1.6, 0.0, 1.0)
    return MagnetopauseState(
        dynamic_pressure_npa=round(pressure, 2),
        standoff_re=round(clamp(standoff_re, 5.0, 15.0), 2),
        shape_alpha=round(clamp(shape_alpha, 0.45, 0.95), 3),
        geo_exposure_risk_percent=round(geo_margin * 100.0, 1),
        geo_direct_exposure=standoff_re <= 6.6,
    )


def _estimate_cadence_minutes(history: pd.DataFrame) -> float:
    if history.empty or "time_tag" not in history.columns:
        return 1.0
    times = pd.to_datetime(history["time_tag"], utc=True, errors="coerce").dropna()
    deltas = times.diff().dropna().dt.total_seconds().div(60.0)
    cadence = float(deltas[(deltas > 0.0) & (deltas < 180.0)].median()) if not deltas.empty else 1.0
    if not cadence or math.isnan(cadence) or cadence <= 0.0:
        return 1.0
    return cadence


def _numeric_series(history: pd.DataFrame, column: str, tail: int = 120) -> pd.Series:
    if history.empty or column not in history.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(history[column], errors="coerce").dropna().tail(tail)


@dataclass(slots=True)
class PropagationEstimate:
    median_seconds: int | None
    earliest_seconds: int | None
    latest_seconds: int | None
    bow_shock_delay_seconds: int | None


def estimate_dynamic_propagation(
    history: pd.DataFrame,
    current_speed: float,
    density_cm3: float,
    bz_nt: float,
    l1_distance_km: float,
    standoff_re: float,
) -> PropagationEstimate:
    if current_speed <= 0.0:
        return PropagationEstimate(None, None, None, None)

    cadence_minutes = _estimate_cadence_minutes(history)
    recent_speed = _numeric_series(history, "speed", 60)
    speed_std = float(recent_speed.std(ddof=0)) if len(recent_speed) > 1 else 0.0
    dynamic_pressure = dynamic_pressure_npa(density_cm3, current_speed)

    bow_shock_re = clamp((standoff_re * 1.32) + 3.2, standoff_re + 1.8, 18.5)
    effective_distance_km = max(l1_distance_km - (bow_shock_re * EARTH_RADIUS_KM), l1_distance_km * 0.88)
    slowdown_factor = 1.0 + clamp((dynamic_pressure - 2.0) / 80.0, 0.0, 0.08) + clamp(abs(min(bz_nt, 0.0)) / 120.0, 0.0, 0.10)
    bow_shock_delay_seconds = int(round(90.0 + (dynamic_pressure * 11.0) + (abs(min(bz_nt, 0.0)) * 5.0)))

    median_seconds = int(round((effective_distance_km / max(current_speed, 250.0)) * slowdown_factor + bow_shock_delay_seconds))

    speed_margin = max(35.0, speed_std, current_speed * 0.07)
    fast_speed = max(current_speed + speed_margin, 250.0)
    slow_speed = max(current_speed - speed_margin, 250.0)
    turbulence_factor = clamp((speed_std / 120.0) + (cadence_minutes / 20.0), 0.0, 0.18)
    earliest_seconds = int(
        round((effective_distance_km / fast_speed) * max(1.0, slowdown_factor - 0.03) + max(bow_shock_delay_seconds - 90, 30))
    )
    latest_seconds = int(
        round((effective_distance_km / slow_speed) * min(slowdown_factor + 0.05 + turbulence_factor, 1.25) + bow_shock_delay_seconds + 120)
    )
    return PropagationEstimate(
        median_seconds=median_seconds,
        earliest_seconds=min(earliest_seconds, latest_seconds),
        latest_seconds=max(earliest_seconds, latest_seconds),
        bow_shock_delay_seconds=bow_shock_delay_seconds,
    )


def estimate_dbdt_proxy_nt_per_min(
    history: pd.DataFrame,
    predicted_dst_index: float | None,
    dynamic_pressure: float,
) -> float:
    cadence_minutes = _estimate_cadence_minutes(history)
    if cadence_minutes <= 0.0:
        cadence_minutes = 1.0

    recent_bz = _numeric_series(history, "bz")
    recent_bt = _numeric_series(history, "bt")
    recent_speed = _numeric_series(history, "speed")
    recent_density = _numeric_series(history, "density")
    recent_dst = _numeric_series(history, "dst_index")

    bz_rate = float(recent_bz.diff().abs().dropna().quantile(0.8)) / cadence_minutes if len(recent_bz) > 2 else 0.0
    bt_rate = float(recent_bt.diff().abs().dropna().quantile(0.8)) / cadence_minutes if len(recent_bt) > 2 else 0.0
    if not recent_speed.empty and not recent_density.empty:
        pressure_series = 1.6726e-6 * recent_density.to_numpy() * recent_speed.to_numpy() ** 2
        pressure_rate = float(pd.Series(pressure_series).diff().abs().dropna().quantile(0.8)) / cadence_minutes
    else:
        pressure_rate = 0.0

    last_bz = float(recent_bz.iloc[-1]) if not recent_bz.empty else 0.0
    last_speed = float(recent_speed.iloc[-1]) if not recent_speed.empty else 400.0
    effective_dst = predicted_dst_index
    if effective_dst is None:
        effective_dst = float(recent_dst.iloc[-1]) if not recent_dst.empty else -10.0
    storm_term = abs(min(effective_dst, 0.0)) / 12.0
    coupling_term = abs(min(last_bz, 0.0)) * (last_speed / 450.0)

    proxy = (
        (3.0 * bz_rate)
        + (2.0 * bt_rate)
        + (12.0 * pressure_rate)
        + (1.2 * coupling_term)
        + (0.6 * storm_term)
        + (0.45 * dynamic_pressure)
    )
    return round(clamp(proxy, 3.0, 250.0), 1)


@dataclass(slots=True)
class TecProxyState:
    local_solar_hour: float
    vertical_tec_tecu: float
    delay_meters_l1: float
    gnss_risk_percent: float


def estimate_tec_delay_proxy(
    dst_index: float,
    estimated_kp: float,
    f107_flux: float,
    bz_nt: float,
    observed_at: object,
    longitude: float,
    regional_weight: float = 1.0,
) -> TecProxyState:
    solar_hour = local_solar_hour(observed_at, longitude)
    daylight_term = max(math.cos(((solar_hour - 14.0) / 12.0) * math.pi), 0.0)
    quiet_vtec = 8.0 + (10.0 * daylight_term) + max(f107_flux - 80.0, 0.0) / 10.0
    storm_vtec = (
        (abs(min(dst_index, 0.0)) / 18.0)
        + max(estimated_kp - 2.0, 0.0) * 2.4
        + abs(min(bz_nt, 0.0)) * 0.55
    )
    vertical_tec = clamp((quiet_vtec + storm_vtec) * regional_weight, 4.0, 110.0)
    slant_factor = 1.05 + (0.35 * daylight_term)
    delay_meters = vertical_tec * IONO_DELAY_PER_TECU_M * slant_factor
    gnss_risk = clamp((delay_meters / 8.0) * 100.0, 5.0, 100.0)
    return TecProxyState(
        local_solar_hour=round(solar_hour, 2),
        vertical_tec_tecu=round(vertical_tec, 1),
        delay_meters_l1=round(delay_meters, 2),
        gnss_risk_percent=round(gnss_risk, 1),
    )


def physics_residual_risk_bonus(
    predicted_dbdt_nt_per_min: float,
    magnetopause_standoff_re: float,
    tec_delay_meters: float,
    geo_exposure_risk_percent: float,
) -> float:
    dbdt_bonus = clamp((predicted_dbdt_nt_per_min - 12.0) / 6.0, 0.0, 10.0)
    standoff_bonus = clamp((6.9 - magnetopause_standoff_re) * 8.0, 0.0, 12.0)
    tec_bonus = clamp((tec_delay_meters - 2.5) * 1.2, 0.0, 8.0)
    geo_bonus = clamp(geo_exposure_risk_percent / 14.0, 0.0, 8.0)
    return round(clamp(dbdt_bonus + standoff_bonus + tec_bonus + geo_bonus, 0.0, 22.0), 1)
