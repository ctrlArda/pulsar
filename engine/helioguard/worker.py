from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import AsyncIterator

from .analysis import build_dashboard_artifacts
from .config import Settings
from .data_sources import SpaceWeatherDataSource
from .predictor import PredictiveEngine
from .storage import LocalStore
from .schemas import CrisisAlert, DashboardState, OperatingMode, TelemetrySnapshot, TerminalLine


class TerminalBroadcaster:
    def __init__(self) -> None:
        self._lines: deque[TerminalLine] = deque(maxlen=80)
        self._subscribers: set[asyncio.Queue[TerminalLine]] = set()

    def push(self, source: str, message: str, level: str = "info") -> TerminalLine:
        line = TerminalLine(
            at=datetime.now(timezone.utc),
            source=source,
            message=message,
            level=level,  # type: ignore[arg-type]
        )
        self._lines.appendleft(line)
        for queue in list(self._subscribers):
            queue.put_nowait(line)
        return line

    def snapshot(self) -> list[TerminalLine]:
        return list(self._lines)

    async def stream(self) -> AsyncIterator[TerminalLine]:
        queue: asyncio.Queue[TerminalLine] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            for line in reversed(self._lines):
                yield line
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


class HelioguardWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.data_source = SpaceWeatherDataSource(settings)
        self.predictor = PredictiveEngine(settings)
        self.terminal = TerminalBroadcaster()
        self.store = LocalStore(settings)
        self.current_mode: OperatingMode = settings.operating_mode
        self.telemetry: TelemetrySnapshot | None = None
        self.active_alert: CrisisAlert | None = None
        self.alerts: deque[CrisisAlert] = deque(maxlen=6)
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._last_published_alert_id: str | None = None

    async def start(self) -> None:
        if self._task is None:
            self.terminal.push("worker", "HELIOGUARD motoru baslatildi.", "info")
            await self.run_once()
            self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.settings.poll_interval_seconds)
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.terminal.push("worker", f"Poll hatasi: {exc}", "warn")

    async def set_mode(self, mode: OperatingMode) -> DashboardState:
        self.current_mode = mode
        self.terminal.push("mode", f"Sistem {mode} moduna gecirildi.", "warn" if mode == "archive" else "info")
        await self.run_once()
        return self.get_state()

    async def run_once(self) -> None:
        async with self._lock:
            bundle = await self.data_source.load(self.current_mode)
            telemetry, alert = build_dashboard_artifacts(bundle, self.predictor, self.settings)
            self.telemetry = telemetry
            self.active_alert = alert

            if alert is not None and alert.id != self._last_published_alert_id:
                self.alerts.appendleft(alert)
                self._last_published_alert_id = alert.id
                self.terminal.push(
                    "alert",
                    f"{alert.title} | risk %{telemetry.local_risk_percent:.0f} | ETA {telemetry.eta_seconds or 0}s",
                    "critical" if alert.severity == "critical" else "warn",
                )

            summary_level = "critical" if telemetry.early_detection else "warn" if telemetry.local_risk_percent >= 55 else "info"
            self.terminal.push(
                "noaa",
                f"Bz={telemetry.bz:.1f} nT | v={telemetry.solar_wind_speed:.0f} km/s | n={telemetry.density:.1f} | Kp*={telemetry.estimated_kp:.1f}",
                summary_level,
            )
            self.terminal.push(
                "science",
                f"X-ray {telemetry.xray_class} | F10.7={telemetry.f107_flux:.0f} | CME backlog={telemetry.cme_count}",
                "warn" if telemetry.xray_flux >= 1e-6 else "info",
            )
            self.terminal.push(
                "grid",
                f"Power-line katmani {len(telemetry.power_lines.get('features', []))} geometri | ulusal risk %{telemetry.local_risk_percent:.0f}",
                "warn" if telemetry.local_risk_percent >= 45 else "info",
            )

            await self.store.persist(telemetry, alert if alert and alert.id == self._last_published_alert_id else None)

    def get_state(self) -> DashboardState:
        return DashboardState(
            mode=self.current_mode,
            telemetry=self.telemetry,
            active_alert=self.active_alert,
            alerts=list(self.alerts),
            terminal=self.terminal.snapshot(),
        )

    async def stream_terminal(self) -> AsyncIterator[TerminalLine]:
        async for line in self.terminal.stream():
            yield line
