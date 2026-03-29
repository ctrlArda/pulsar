from __future__ import annotations

import argparse
import asyncio
import sqlite3
from dataclasses import dataclass

from fastapi.testclient import TestClient

from .app import app, worker as api_worker
from .config import settings
from .worker import HelioguardWorker


@dataclass(slots=True)
class CheckResult:
    label: str
    ok: bool
    detail: str


def _status_prefix(ok: bool) -> str:
    return "[PASS]" if ok else "[FAIL]"


def _fmt_metric(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


async def _collect_worker_snapshot(mode: str) -> tuple[HelioguardWorker, dict[str, object]]:
    worker = HelioguardWorker(settings)
    worker.current_mode = mode  # type: ignore[assignment]
    await worker.run_once()
    state = worker.get_state()

    db = sqlite3.connect(settings.database_path)
    telemetry_rows = int(db.execute("select count(*) from live_telemetry").fetchone()[0])
    alert_rows = int(db.execute("select count(*) from crisis_alerts").fetchone()[0])
    db.close()

    snapshot = {
        "mode": state.mode,
        "headline": state.telemetry.summary_headline if state.telemetry else None,
        "has_telemetry": state.telemetry is not None,
        "has_alert": state.active_alert is not None,
        "speed": state.telemetry.solar_wind_speed if state.telemetry else None,
        "bz": state.telemetry.bz if state.telemetry else None,
        "estimated_kp": state.telemetry.estimated_kp if state.telemetry else None,
        "dst_index": state.telemetry.dst_index if state.telemetry else None,
        "dynamic_pressure": state.telemetry.dynamic_pressure_npa if state.telemetry else None,
        "magnetopause_standoff": state.telemetry.magnetopause_standoff_re if state.telemetry else None,
        "dbdt_proxy": state.telemetry.predicted_dbdt_nt_per_min if state.telemetry else None,
        "tec_delay": state.telemetry.tec_delay_meters if state.telemetry else None,
        "local_risk": state.telemetry.local_risk_percent if state.telemetry else None,
        "ml_risk": state.telemetry.ml_risk_percent if state.telemetry else None,
        "ml_predicted_dst": state.telemetry.ml_predicted_dst_index if state.telemetry else None,
        "confidence": state.telemetry.forecast_confidence_percent if state.telemetry else None,
        "storm_scale_band": state.telemetry.storm_scale_band if state.telemetry else None,
        "turkish_satellite_count": state.telemetry.turkish_satellite_count if state.telemetry else 0,
        "turkish_satellite_risk": state.telemetry.turkish_satellite_risk_percent if state.telemetry else None,
        "turkish_satellite_headline": state.telemetry.turkish_satellite_headline if state.telemetry else None,
        "turkish_satellite_names": [item.name for item in (state.telemetry.turkish_satellites if state.telemetry else [])],
        "source_states": {item.id: item.state for item in (state.telemetry.source_statuses if state.telemetry else [])},
        "all_sources_live": all(item.state == "live" for item in (state.telemetry.source_statuses if state.telemetry else [])),
        "decision_commentary": [
            {
                "title": item.title,
                "value": item.value,
                "basis": item.basis,
                "explanation": item.explanation,
            }
            for item in (state.telemetry.decision_commentary if state.telemetry else [])[:4]
        ],
        "precursor_risk": state.telemetry.precursor_risk_percent if state.telemetry else None,
        "precursor_horizon_hours": state.telemetry.precursor_horizon_hours if state.telemetry else None,
        "precursor_confidence": state.telemetry.precursor_confidence_percent if state.telemetry else None,
        "eta_seconds": state.telemetry.eta_seconds if state.telemetry else None,
        "eta_window_start": state.telemetry.eta_window_start_seconds if state.telemetry else None,
        "eta_window_end": state.telemetry.eta_window_end_seconds if state.telemetry else None,
        "risk_band_low": state.telemetry.risk_band_low if state.telemetry else None,
        "risk_band_high": state.telemetry.risk_band_high if state.telemetry else None,
        "power_line_features": len(state.telemetry.power_lines.get("features", [])) if state.telemetry else 0,
        "heat_cells": len(state.telemetry.heat_grid) if state.telemetry else 0,
        "hardware_impacts": len(state.active_alert.impacted_hardware) if state.active_alert else 0,
        "sop_actions": len(state.active_alert.sop_actions) if state.active_alert else 0,
        "terminal_lines": len(state.terminal),
        "telemetry_rows": telemetry_rows,
        "alert_rows": alert_rows,
    }
    return worker, snapshot


def _print_report(checks: list[CheckResult], snapshot: dict[str, object], api_snapshot: dict[str, object]) -> None:
    print("HELIOGUARD JURY SMOKE TEST")
    print("==========================")
    for check in checks:
        print(f"{_status_prefix(check.ok)} {check.label}: {check.detail}")

    print("")
    print("Demo Snapshot")
    print("-------------")
    print(f"Mode: {snapshot['mode']}")
    print(f"Headline: {snapshot['headline']}")
    print(f"Solar wind speed: {_fmt_metric(snapshot['speed'], ' km/s')}")
    print(f"Bz: {_fmt_metric(snapshot['bz'], ' nT')}")
    print(f"Estimated Kp: {_fmt_metric(snapshot['estimated_kp'])}")
    print(f"Dst: {_fmt_metric(snapshot['dst_index'], ' nT')}")
    print(f"Dynamic pressure: {_fmt_metric(snapshot['dynamic_pressure'], ' nPa')}")
    print(f"Magnetopause standoff: {_fmt_metric(snapshot['magnetopause_standoff'], ' Re')}")
    print(f"dB/dt proxy: {_fmt_metric(snapshot['dbdt_proxy'], ' nT/min')}")
    print(f"TEC delay proxy: {_fmt_metric(snapshot['tec_delay'], ' m')}")
    print(f"National risk: {_fmt_metric(snapshot['local_risk'], '%')}")
    print(f"National risk band: {_fmt_metric(snapshot['risk_band_low'], '%')} - {_fmt_metric(snapshot['risk_band_high'], '%')}")
    print(f"ML risk (+60m): {_fmt_metric(snapshot['ml_risk'], '%')}")
    print(f"ML Dst (+60m): {_fmt_metric(snapshot['ml_predicted_dst'], ' nT')}")
    print(f"ETA: {_fmt_metric(snapshot['eta_seconds'], ' s')}")
    print(f"ETA window: {_fmt_metric(snapshot['eta_window_start'], ' s')} - {_fmt_metric(snapshot['eta_window_end'], ' s')}")
    print(f"Forecast confidence: {_fmt_metric(snapshot['confidence'], '%')}")
    print(f"Storm-scale band: {snapshot['storm_scale_band']}")
    print(f"Turkish satellite fleet: {snapshot['turkish_satellite_count']} | risk {_fmt_metric(snapshot['turkish_satellite_risk'], '%')}")
    print(f"Turkish satellite headline: {snapshot['turkish_satellite_headline']}")
    print(
        "Turkish satellites: "
        + (", ".join(snapshot["turkish_satellite_names"]) if snapshot["turkish_satellite_names"] else "--")
    )
    print(f"Source states: {snapshot['source_states']}")
    if snapshot["decision_commentary"]:
        print("Decision commentary:")
        for item in snapshot["decision_commentary"]:
            print(f" - {item['title']} [{item['basis']} {item['value']}]: {item['explanation']}")
    print(f"Precursor risk: {_fmt_metric(snapshot['precursor_risk'], '%')}")
    print(f"Precursor horizon: {_fmt_metric(snapshot['precursor_horizon_hours'], ' h')}")
    print(f"Precursor confidence: {_fmt_metric(snapshot['precursor_confidence'], '%')}")
    print(f"Power-line features: {snapshot['power_line_features']}")
    print(f"Heat cells: {snapshot['heat_cells']}")
    print(f"Hardware impacts: {snapshot['hardware_impacts']}")
    print(f"SOP actions: {snapshot['sop_actions']}")
    print(f"Terminal lines: {snapshot['terminal_lines']}")
    print(f"SQLite rows (telemetry / alerts): {snapshot['telemetry_rows']} / {snapshot['alert_rows']}")
    print(f"API health: {api_snapshot['health']}")
    print(f"API telemetry: {api_snapshot['has_telemetry']}")
    print(f"API active alert: {api_snapshot['has_alert']}")


async def run(mode: str, strict_live: bool = False) -> int:
    worker, snapshot = await _collect_worker_snapshot(mode)

    api_worker.current_mode = mode  # type: ignore[assignment]
    with TestClient(app) as client:
        health = client.get("/health").json()
        state = client.get("/api/state").json()

    api_snapshot = {
        "health": health.get("status"),
        "has_telemetry": state.get("telemetry") is not None,
        "has_alert": state.get("activeAlert") is not None,
    }

    checks = [
        CheckResult("XGBoost model present", settings.model_path.exists(), str(settings.model_path)),
        CheckResult("Telemetry produced", bool(snapshot["has_telemetry"]), "Worker telemetry snapshot olustu"),
        CheckResult("Alarm produced", bool(snapshot["has_alert"]), "Crisis alert uretiliyor"),
        CheckResult("ML prediction active", snapshot["ml_risk"] is not None, f"ML risk={_fmt_metric(snapshot['ml_risk'], '%')}"),
        CheckResult("ML Dst target active", snapshot["ml_predicted_dst"] is not None, f"ML Dst={_fmt_metric(snapshot['ml_predicted_dst'], ' nT')}"),
        CheckResult("Dst available", snapshot["dst_index"] is not None, f"Dst={_fmt_metric(snapshot['dst_index'], ' nT')}"),
        CheckResult("Dynamic pressure available", snapshot["dynamic_pressure"] is not None, f"Pdyn={_fmt_metric(snapshot['dynamic_pressure'], ' nPa')}"),
        CheckResult("Magnetopause standoff available", snapshot["magnetopause_standoff"] is not None, f"Rmp={_fmt_metric(snapshot['magnetopause_standoff'], ' Re')}"),
        CheckResult("dB/dt proxy available", snapshot["dbdt_proxy"] is not None, f"dB/dt={_fmt_metric(snapshot['dbdt_proxy'], ' nT/min')}"),
        CheckResult("TEC delay proxy available", snapshot["tec_delay"] is not None, f"TEC={_fmt_metric(snapshot['tec_delay'], ' m')}"),
        CheckResult("ETA available", snapshot["eta_seconds"] is not None, f"ETA={_fmt_metric(snapshot['eta_seconds'], ' s')}"),
        CheckResult("Arrival window available", snapshot["eta_window_start"] is not None and snapshot["eta_window_end"] is not None, f"Window={_fmt_metric(snapshot['eta_window_start'], ' s')}-{_fmt_metric(snapshot['eta_window_end'], ' s')}"),
        CheckResult("Risk band available", snapshot["risk_band_low"] is not None and snapshot["risk_band_high"] is not None, f"Band={_fmt_metric(snapshot['risk_band_low'], '%')}-{_fmt_metric(snapshot['risk_band_high'], '%')}"),
        CheckResult("Forecast confidence available", snapshot["confidence"] is not None, f"Confidence={_fmt_metric(snapshot['confidence'], '%')}"),
        CheckResult("Turkish satellite fleet active", int(snapshot["turkish_satellite_count"]) > 0, f"Fleet={snapshot['turkish_satellite_count']} risk={_fmt_metric(snapshot['turkish_satellite_risk'], '%')}"),
        CheckResult("Precursor outlook active", snapshot["precursor_risk"] is not None, f"Risk={_fmt_metric(snapshot['precursor_risk'], '%')}"),
        CheckResult("Precursor horizon available", snapshot["precursor_horizon_hours"] is not None, f"Horizon={_fmt_metric(snapshot['precursor_horizon_hours'], ' h')}"),
        CheckResult("Heat map geometry available", int(snapshot["power_line_features"]) > 0 and int(snapshot["heat_cells"]) > 0, f"Lines={snapshot['power_line_features']} cells={snapshot['heat_cells']}"),
        CheckResult("SOP output available", int(snapshot["sop_actions"]) > 0, f"SOP={snapshot['sop_actions']}"),
        CheckResult("Terminal is streaming", int(snapshot["terminal_lines"]) >= 3, f"Lines={snapshot['terminal_lines']}"),
        CheckResult("SQLite persistence working", int(snapshot["telemetry_rows"]) >= 1 and int(snapshot["alert_rows"]) >= 1, f"Rows={snapshot['telemetry_rows']}/{snapshot['alert_rows']}"),
        CheckResult("FastAPI health endpoint", api_snapshot["health"] == "ok", f"health={api_snapshot['health']}"),
        CheckResult("FastAPI state endpoint", bool(api_snapshot["has_telemetry"]) and bool(api_snapshot["has_alert"]), "api/state veri donuyor"),
    ]
    if strict_live and mode == "live":
        checks.append(
            CheckResult(
                "Strict live sources",
                bool(snapshot["all_sources_live"]),
                f"states={snapshot['source_states']}",
            )
        )

    _print_report(checks, snapshot, api_snapshot)
    return 0 if all(check.ok for check in checks) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a jury-friendly HELIOGUARD smoke test.")
    parser.add_argument("--mode", choices=["archive", "live"], default="archive", help="Archive mode is recommended for jury demos.")
    parser.add_argument("--strict-live", action="store_true", help="Live modda tum kaynaklarin state=live olmasini zorunlu kil.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.mode, strict_live=args.strict_live)))


if __name__ == "__main__":
    main()
