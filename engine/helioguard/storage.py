from __future__ import annotations

import asyncio
import json
import sqlite3

from .config import Settings
from .schemas import CrisisAlert, TelemetrySnapshot


class LocalStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.settings.database_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists live_telemetry (
                    observed_at text not null,
                    mode text not null,
                    summary_headline text not null,
                    solar_wind_speed real not null,
                    bz real not null,
                    estimated_kp real not null,
                    local_risk_percent real not null,
                    eta_seconds integer,
                    payload text not null,
                    primary key (observed_at, mode)
                )
                """
            )
            connection.execute(
                """
                create table if not exists crisis_alerts (
                    id text primary key,
                    created_at text not null,
                    mode text not null,
                    severity text not null,
                    title text not null,
                    eta_seconds integer,
                    payload text not null
                )
                """
            )

    async def persist(self, telemetry: TelemetrySnapshot, alert: CrisisAlert | None) -> None:
        await asyncio.to_thread(self._persist_sync, telemetry, alert)

    def _persist_sync(self, telemetry: TelemetrySnapshot, alert: CrisisAlert | None) -> None:
        telemetry_payload = json.dumps(telemetry.model_dump(mode="json"), ensure_ascii=True)
        with self._connect() as connection:
            connection.execute(
                """
                insert into live_telemetry (
                    observed_at,
                    mode,
                    summary_headline,
                    solar_wind_speed,
                    bz,
                    estimated_kp,
                    local_risk_percent,
                    eta_seconds,
                    payload
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(observed_at, mode) do update set
                    summary_headline = excluded.summary_headline,
                    solar_wind_speed = excluded.solar_wind_speed,
                    bz = excluded.bz,
                    estimated_kp = excluded.estimated_kp,
                    local_risk_percent = excluded.local_risk_percent,
                    eta_seconds = excluded.eta_seconds,
                    payload = excluded.payload
                """,
                (
                    telemetry.observed_at.isoformat(),
                    telemetry.mode,
                    telemetry.summary_headline,
                    telemetry.solar_wind_speed,
                    telemetry.bz,
                    telemetry.estimated_kp,
                    telemetry.local_risk_percent,
                    telemetry.eta_seconds,
                    telemetry_payload,
                ),
            )
            if alert is not None:
                alert_payload = json.dumps(alert.model_dump(mode="json"), ensure_ascii=True)
                connection.execute(
                    """
                    insert into crisis_alerts (
                        id,
                        created_at,
                        mode,
                        severity,
                        title,
                        eta_seconds,
                        payload
                    ) values (?, ?, ?, ?, ?, ?, ?)
                    on conflict(id) do update set
                        severity = excluded.severity,
                        title = excluded.title,
                        eta_seconds = excluded.eta_seconds,
                        payload = excluded.payload
                    """,
                    (
                        alert.id,
                        alert.created_at.isoformat(),
                        alert.mode,
                        alert.severity,
                        alert.title,
                        alert.eta_seconds,
                        alert_payload,
                    ),
                )
