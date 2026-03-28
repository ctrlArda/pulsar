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


class TelemetrySnapshot(CamelModel):
    observed_at: datetime
    mode: OperatingMode
    solar_wind_speed: float
    bz: float
    bt: float
    density: float
    temperature: float
    kp_index: float
    estimated_kp: float
    xray_flux: float
    xray_class: str
    f107_flux: float
    cme_count: int
    early_detection: bool
    eta_seconds: int | None
    eta_window_start_seconds: int | None
    eta_window_end_seconds: int | None
    local_risk_percent: float
    risk_band_low: float
    risk_band_high: float
    local_magnetic_latitude: float
    auroral_expansion_percent: float
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
    ml_risk_percent: float | None
    ml_risk_band_low: float | None
    ml_risk_band_high: float | None
    ml_lead_time_minutes: int | None
    validation_mae: float | None
    validation_rows: int | None
    validation_horizon_minutes: int | None
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
