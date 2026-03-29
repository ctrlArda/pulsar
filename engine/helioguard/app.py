from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import time
import requests

from .config import settings
from .schemas import DashboardState, OperatingMode
from .worker import HelioguardWorker


app = FastAPI(title="HELIOGUARD Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
worker = HelioguardWorker(settings)


@app.on_event("startup")
async def startup_event() -> None:
    await worker.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await worker.stop()


@app.get("/health")
async def health() -> dict[str, object]:
    state = worker.get_state()
    telemetry = state.telemetry
    return {
        "status": "ok",
        "mode": state.mode,
        "telemetry": telemetry is not None,
        "observed_at": telemetry.observed_at if telemetry else None,
        "source_coverage_percent": telemetry.source_coverage_percent if telemetry else None,
        "forecast_confidence_percent": telemetry.forecast_confidence_percent if telemetry else None,
    }


@app.get("/api/state", response_model=DashboardState)
async def get_state() -> DashboardState:
    state = worker.get_state()
    if state.telemetry is None:
        await worker.run_once()
        state = worker.get_state()
    return state


_FLIGHTS_CACHE = {"time": 0, "data": []}

@app.get("/api/flights/live")
async def get_live_flights():
    global _FLIGHTS_CACHE
    now = time.time()
    # 60 saniyede bir güncelleyerek OpenSky API rate limit aşımını önleriz
    if now - _FLIGHTS_CACHE["time"] > 60:
        try:
            # Türkiye Bounding Box: lamin=35.8, lomin=25.6, lamax=42.1, lomax=44.8
            r = requests.get("https://opensky-network.org/api/states/all?lamin=35.8&lomin=25.6&lamax=42.1&lomax=44.8", timeout=10)
            if r.status_code == 200:
                states = r.json().get("states", [])
                formatted = []
                if states:
                    for s in states:
                        if s[5] is not None and s[6] is not None:
                            formatted.append({
                                "icao24": s[0],
                                "callsign": s[1].strip() if s[1] else "UNKNOWN",
                                "country": s[2],
                                "longitude": s[5],
                                "latitude": s[6],
                                "altitude": s[7] if s[7] else 0,
                                "velocity": s[9] if s[9] else 0,
                                "heading": s[10] if s[10] else 0
                            })
                _FLIGHTS_CACHE["data"] = formatted
                _FLIGHTS_CACHE["time"] = now
        except Exception as e:
            print("OpenSky fetch failed:", e)
    return {"flights": _FLIGHTS_CACHE["data"]}

@app.post("/api/mode/{mode}", response_model=DashboardState)
async def set_mode(mode: OperatingMode) -> DashboardState:
    return await worker.set_mode(mode)


@app.get("/api/webhooks/preview")
async def webhook_preview() -> dict[str, object]:
    state = worker.get_state()
    if state.telemetry is None:
        await worker.run_once()
        state = worker.get_state()
    telemetry = state.telemetry
    alert = state.active_alert
    return {
        "event": "helioguard.alert.updated" if alert is not None else "helioguard.telemetry.snapshot",
        "institutionTargets": ["ASELSAN SOC", "TUSAS Mission Ops", "TEIAS Control Center"],
        "payload": {
            "mode": state.mode,
            "headline": alert.title if alert else telemetry.summary_headline if telemetry else "Telemetri bekleniyor",
            "observedAt": telemetry.observed_at if telemetry else None,
            "nationalRiskPercent": telemetry.local_risk_percent if telemetry else None,
            "etaSeconds": telemetry.eta_seconds if telemetry else None,
            "etaWindowStartSeconds": telemetry.eta_window_start_seconds if telemetry else None,
            "etaWindowEndSeconds": telemetry.eta_window_end_seconds if telemetry else None,
            "kp": telemetry.kp_index if telemetry else None,
            "estimatedKp": telemetry.estimated_kp if telemetry else None,
            "dstIndex": telemetry.dst_index if telemetry else None,
            "bz": telemetry.bz if telemetry else None,
            "solarWindSpeed": telemetry.solar_wind_speed if telemetry else None,
            "dynamicPressureNpa": telemetry.dynamic_pressure_npa if telemetry else None,
            "xrayClass": telemetry.xray_class if telemetry else None,
            "protonFluxPfu": telemetry.proton_flux_pfu if telemetry else None,
            "officialForecastScale": telemetry.official_forecast_scale if telemetry else None,
            "precursorRiskPercent": telemetry.precursor_risk_percent if telemetry else None,
            "precursorRiskBandLow": telemetry.precursor_risk_band_low if telemetry else None,
            "precursorRiskBandHigh": telemetry.precursor_risk_band_high if telemetry else None,
            "precursorHorizonHours": telemetry.precursor_horizon_hours if telemetry else None,
            "precursorConfidencePercent": telemetry.precursor_confidence_percent if telemetry else None,
            "precursorHeadline": telemetry.precursor_headline if telemetry else None,
            "precursorCmeSpeedKms": telemetry.precursor_cme_speed_kms if telemetry else None,
            "precursorArrivalAt": telemetry.precursor_arrival_at if telemetry else None,
            "magnetopauseStandoffRe": telemetry.magnetopause_standoff_re if telemetry else None,
            "geoExposureRiskPercent": telemetry.geo_exposure_risk_percent if telemetry else None,
            "predictedDbdtNtPerMin": telemetry.predicted_dbdt_nt_per_min if telemetry else None,
            "tecDelayMeters": telemetry.tec_delay_meters if telemetry else None,
            "turkishSatelliteCount": telemetry.turkish_satellite_count if telemetry else None,
            "turkishSatelliteRiskPercent": telemetry.turkish_satellite_risk_percent if telemetry else None,
            "turkishSatelliteHeadline": telemetry.turkish_satellite_headline if telemetry else None,
            "turkishSatellites": [item.model_dump(mode="json", by_alias=True) for item in (telemetry.turkish_satellites if telemetry else [])[:5]],
            "mlPredictedDstIndex": telemetry.ml_predicted_dst_index if telemetry else None,
            "mlPredictedDstBandLow": telemetry.ml_predicted_dst_band_low if telemetry else None,
            "mlPredictedDstBandHigh": telemetry.ml_predicted_dst_band_high if telemetry else None,
            "sopActions": [item.action for item in (alert.sop_actions if alert else [])],
            "impactedSystems": [impact.title for impact in (alert.impacted_hardware if alert else [])],
        },
    }


@app.get("/api/stream/terminal")
async def stream_terminal() -> EventSourceResponse:
    async def event_generator():
        async for line in worker.stream_terminal():
            yield {"data": json.dumps(line.model_dump(mode="json", by_alias=True))}

    return EventSourceResponse(event_generator())
