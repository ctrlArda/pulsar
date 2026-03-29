from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


OperatingMode = Literal["live", "archive"]
Severity = Literal["watch", "warning", "critical"]
ImpactSeverity = Literal["low", "medium", "high", "critical"]
TerminalLevel = Literal["info", "warn", "critical"]
SourceState = Literal["live", "cached", "archive", "degraded"]


class HeatCell(CamelModel):
    id: str
    label: str
    latitude: float
    longitude: float
    intensity: float


class KpTrendPoint(CamelModel):
    time_tag: str
    kp_index: float
    estimated_kp: float


class ThreatImpact(CamelModel):
    id: str
    title: str
    severity: ImpactSeverity
    affected_systems: list[str]
    rationale: str


class SopAction(CamelModel):
    sector: str
    action: str
    status: Literal["ready", "urgent"]


class TerminalLine(CamelModel):
    at: datetime
    source: str
    message: str
    level: TerminalLevel


class SourceStatus(CamelModel):
    id: str
    label: str
    state: SourceState
    detail: str
    observed_at: datetime | None = None
    href: str | None = None


class ModelContribution(CamelModel):
    feature: str
    label: str
    contribution: float
    direction: str


class DecisionCommentary(CamelModel):
    id: str
    title: str
    value: str
    category: str
    basis: Literal["measured", "modeled", "fused"]
    explanation: str
    implication: str
    confidence_note: str


class TurkishSatelliteAssessment(CamelModel):
    name: str
    norad_id: int
    mission_family: str
    orbit_class: str
    data_source: str
    observed_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_km: float | None = None
    azimuth_deg: float | None = None
    elevation_deg: float | None = None
    over_turkiye: bool
    visible_from_turkiye: bool
    drag_risk_percent: float
    charging_risk_percent: float
    radiation_risk_percent: float
    service_risk_percent: float
    overall_risk_percent: float
    dominant_driver: str
    summary: str
    observation_summary: str
    risk_reason: str
    scientific_note: str
    recommended_action: str


class TelemetrySnapshot(CamelModel):
    observed_at: datetime
    mode: OperatingMode
    solar_wind_speed: float
    bz: float
    bt: float
    density: float
    temperature: float
    dynamic_pressure_npa: float
    kp_index: float
    estimated_kp: float
    dst_index: float | None
    xray_flux: float
    xray_class: str
    proton_flux_pfu: float | None
    f107_flux: float
    cme_count: int
    early_detection: bool
    eta_seconds: int | None
    eta_window_start_seconds: int | None
    eta_window_end_seconds: int | None
    bow_shock_delay_seconds: int | None
    local_risk_percent: float
    risk_band_low: float
    risk_band_high: float
    local_magnetic_latitude: float
    local_solar_hour: float
    auroral_expansion_percent: float
    magnetopause_standoff_re: float
    magnetopause_shape_alpha: float
    geo_exposure_risk_percent: float
    geo_direct_exposure: bool
    predicted_dbdt_nt_per_min: float
    tec_vertical_tecu: float
    tec_delay_meters: float
    gnss_risk_percent: float
    forecast_confidence_percent: float
    source_coverage_percent: float
    data_freshness_seconds: int | None
    storm_scale_band: str
    official_geomagnetic_scale: str | None
    official_radio_blackout_scale: str | None
    official_solar_radiation_scale: str | None
    official_watch_headline: str | None
    official_alert_headline: str | None
    official_forecast_kp_max: float | None
    official_forecast_scale: str | None
    precursor_risk_percent: float | None
    precursor_risk_band_low: float | None
    precursor_risk_band_high: float | None
    precursor_horizon_hours: int | None
    precursor_confidence_percent: float | None
    precursor_headline: str | None
    precursor_cme_speed_kms: float | None
    precursor_arrival_at: datetime | None
    precursor_is_earth_directed: bool
    ml_risk_percent: float | None
    ml_risk_band_low: float | None
    ml_risk_band_high: float | None
    ml_predicted_dst_index: float | None
    ml_predicted_dst_band_low: float | None
    ml_predicted_dst_band_high: float | None
    ml_baseline_dst_index: float | None
    ml_target_name: str | None
    ml_target_unit: str | None
    ml_feature_contributions: list[ModelContribution]
    ml_lead_time_minutes: int | None
    validation_mae: float | None
    validation_band_coverage: float | None
    validation_rows: int | None
    validation_horizon_minutes: int | None
    turkish_satellite_count: int
    turkish_satellite_risk_percent: float
    turkish_satellite_headline: str | None
    turkish_satellites: list[TurkishSatelliteAssessment]
    decision_commentary: list[DecisionCommentary]
    summary_headline: str
    kp_history: list[KpTrendPoint]
    source_statuses: list[SourceStatus]
    power_lines: dict[str, Any]
    heat_grid: list[HeatCell]


class CrisisAlert(CamelModel):
    id: str
    created_at: datetime
    mode: OperatingMode
    severity: Severity
    title: str
    subtitle: str
    eta_seconds: int | None
    narrative: str
    telemetry: TelemetrySnapshot
    impacted_hardware: list[ThreatImpact]
    sop_actions: list[SopAction]


class DashboardState(CamelModel):
    mode: OperatingMode
    telemetry: TelemetrySnapshot | None
    active_alert: CrisisAlert | None
    alerts: list[CrisisAlert]
    terminal: list[TerminalLine]
