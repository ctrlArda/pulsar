from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

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
    return worker.get_state()


@app.post("/api/mode/{mode}", response_model=DashboardState)
async def set_mode(mode: OperatingMode) -> DashboardState:
    return await worker.set_mode(mode)


@app.get("/api/stream/terminal")
async def stream_terminal() -> EventSourceResponse:
    async def event_generator():
        async for line in worker.stream_terminal():
            yield {"data": json.dumps(line.model_dump(mode="json", by_alias=True))}

    return EventSourceResponse(event_generator())
