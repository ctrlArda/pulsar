from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .schemas import SourceStatus


TURKIYE_QUERY_POINTS: list[tuple[float, float]] = [
    (41.01, 28.97),  # Istanbul
    (40.19, 29.06),  # Bursa
    (38.42, 27.14),  # Izmir
    (36.89, 30.70),  # Antalya
    (39.93, 32.85),  # Ankara
    (37.87, 32.48),  # Konya
    (41.29, 36.33),  # Samsun
    (38.72, 35.48),  # Kayseri
    (37.00, 35.32),  # Adana
    (37.07, 37.38),  # Gaziantep
    (39.90, 41.27),  # Erzurum
    (38.49, 43.38),  # Van
]


@dataclass(slots=True)
class CachedText:
    text: str
    state: str
    cached_at: datetime


@dataclass(slots=True)
class CachedJson:
    payload: dict[str, Any]
    state: str
    cached_at: datetime


@dataclass(slots=True)
class SpaceWeatherBundle:
    mode: str
    fetched_at: datetime
    planetary_kp: list[dict[str, Any]]
    minute_kp: list[dict[str, Any]]
    mag: list[dict[str, Any]]
    plasma: list[dict[str, Any]]
    xray: list[dict[str, Any]]
    f107: list[dict[str, Any]]
    cmes: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    noaa_scales: dict[str, Any]
    kp_forecast: list[dict[str, Any]]
    tle_text: str
    power_lines: dict[str, Any]
    source_statuses: list[SourceStatus]


def parse_noaa_table(raw_text: str) -> list[dict[str, Any]]:
    rows = json.loads(raw_text)
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, row, strict=False)) for row in rows[1:] if len(row) >= len(header)]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _combine_source_state(states: list[str]) -> str:
    filtered = [state for state in states if state]
    unique = set(filtered)
    if not unique:
        return "degraded"
    if len(unique) == 1:
        return filtered[0]
    if unique == {"live", "cached"}:
        return "degraded"
    return "degraded"


class SpaceWeatherDataSource:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        self._power_lines_cache: dict[str, Any] | None = None
        self._power_lines_cache_at: datetime | None = None
        self._power_lines_state: str = "degraded"
        self._donki_cache: list[dict[str, Any]] | None = None
        self._donki_cache_at: datetime | None = None
        self._donki_state: str = "degraded"
        self._tle_cache: str | None = None
        self._tle_cache_at: datetime | None = None
        self._tle_state: str = "degraded"

    async def load(self, mode: str) -> SpaceWeatherBundle:
        if mode == "archive":
            return self._load_archive_bundle()
        return await self._load_live_bundle()

    def _cache_path(self, name: str) -> Path:
        return self.settings.cache_dir / "live" / name

    def _write_cache(self, name: str, content: str) -> None:
        path = self._cache_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _read_cache(self, name: str) -> CachedText | None:
        path = self._cache_path(name)
        if not path.exists():
            return None
        return CachedText(
            text=path.read_text(encoding="utf-8"),
            state="cached",
            cached_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        )

    async def _fetch_text_with_cache(
        self,
        client: httpx.AsyncClient,
        name: str,
        url: str,
        params: dict[str, Any] | None = None,
        archive_name: str | None = None,
        fallback_text: str | None = None,
    ) -> CachedText:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            self._write_cache(name, response.text)
            return CachedText(text=response.text, state="live", cached_at=datetime.now(timezone.utc))
        except Exception:
            cached = self._read_cache(name)
            if cached is not None:
                return cached
            if archive_name is not None:
                archive_path = self.settings.archive_dir / self.settings.archive_bundle / archive_name
                if archive_path.exists():
                    return CachedText(
                        text=archive_path.read_text(encoding="utf-8"),
                        state="archive",
                        cached_at=datetime.now(timezone.utc),
                    )
            if fallback_text is not None:
                return CachedText(text=fallback_text, state="degraded", cached_at=datetime.now(timezone.utc))
            raise

    async def _load_live_bundle(self) -> SpaceWeatherBundle:
        start_date = (datetime.now(timezone.utc) - timedelta(days=6)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()
        noaa = self.settings.noaa_base_url.rstrip("/")
        donki = self.settings.donki_base_url.rstrip("/")

        async with httpx.AsyncClient(timeout=25) as client:
            (
                planetary_kp_raw,
                minute_kp_raw,
                mag_raw,
                plasma_raw,
                xray_raw,
                f107_raw,
                alerts_raw,
                scales_raw,
                kp_forecast_raw,
                donki_rows,
                tle_text,
                power_lines,
            ) = await asyncio.gather(
                self._fetch_text_with_cache(client, "noaa-planetary-k-index.json", f"{noaa}/products/noaa-planetary-k-index.json", archive_name="noaa-planetary-k-index.json"),
                self._fetch_text_with_cache(client, "planetary_k_index_1m.json", f"{noaa}/json/planetary_k_index_1m.json", archive_name="planetary_k_index_1m.json"),
                self._fetch_text_with_cache(client, "mag-1-day.json", f"{noaa}/products/solar-wind/mag-1-day.json", archive_name="mag-1-day.json"),
                self._fetch_text_with_cache(client, "plasma-1-day.json", f"{noaa}/products/solar-wind/plasma-1-day.json", archive_name="plasma-1-day.json"),
                self._fetch_text_with_cache(client, "xrays-6-hour.json", f"{noaa}/json/goes/primary/xrays-6-hour.json", archive_name="xrays-6-hour.json"),
                self._fetch_text_with_cache(client, "f107_cm_flux.json", f"{noaa}/json/f107_cm_flux.json", archive_name="f107_cm_flux.json"),
                self._fetch_text_with_cache(client, "alerts.json", f"{noaa}/products/alerts.json", fallback_text="[]"),
                self._fetch_text_with_cache(client, "noaa-scales.json", f"{noaa}/products/noaa-scales.json", fallback_text="{}"),
                self._fetch_text_with_cache(client, "noaa-planetary-k-index-forecast.json", f"{noaa}/products/noaa-planetary-k-index-forecast.json", fallback_text='[["time_tag","kp","observed","noaa_scale"]]'),
                self._fetch_donki(client, donki, start_date, end_date),
                self._fetch_tle(client),
                self._fetch_power_lines(client),
            )

        planetary_kp = parse_noaa_table(planetary_kp_raw.text)
        minute_kp = json.loads(minute_kp_raw.text)
        mag = parse_noaa_table(mag_raw.text)
        plasma = parse_noaa_table(plasma_raw.text)
        xray = json.loads(xray_raw.text)
        f107 = json.loads(f107_raw.text)
        alerts = json.loads(alerts_raw.text)
        noaa_scales = json.loads(scales_raw.text)
        kp_forecast = parse_noaa_table(kp_forecast_raw.text)

        source_statuses = [
            SourceStatus(
                id="noaa-rtsw",
                label="NOAA SWPC RTSW",
                state=_combine_source_state([planetary_kp_raw.state, minute_kp_raw.state, mag_raw.state, plasma_raw.state, xray_raw.state]),
                detail=f"L1, Kp ve GOES akisi | son paket {_parse_datetime(str((mag[-1] if mag else {}).get('time_tag'))) or mag_raw.cached_at}",
                observed_at=_parse_datetime(str((mag[-1] if mag else {}).get("time_tag"))) or mag_raw.cached_at,
                href="https://services.swpc.noaa.gov/",
            ),
            SourceStatus(
                id="noaa-forecast",
                label="NOAA Official Outlook",
                state=_combine_source_state([f107_raw.state, alerts_raw.state, scales_raw.state, kp_forecast_raw.state]),
                detail=f"Resmi alert/watch/scales akisi | son issue {_parse_datetime(str((alerts[0] if alerts else {}).get('issue_datetime'))) or scales_raw.cached_at}",
                observed_at=_parse_datetime(str((alerts[0] if alerts else {}).get("issue_datetime"))) or scales_raw.cached_at,
                href="https://services.swpc.noaa.gov/products/",
            ),
            SourceStatus(
                id="nasa-donki",
                label="NASA DONKI",
                state=self._donki_state,
                detail=f"CME olay listesi | son 7 gun | kayit {len(donki_rows)}",
                observed_at=self._donki_cache_at,
                href="https://api.nasa.gov/",
            ),
            SourceStatus(
                id="celestrak",
                label="CelesTrak",
                state=self._tle_state,
                detail="Aktif TLE katalougu ve LEO izleme listesi",
                observed_at=self._tle_cache_at,
                href="https://celestrak.org/",
            ),
            SourceStatus(
                id="overpass",
                label="Overpass / OSM",
                state=self._power_lines_state,
                detail=f"Turkiye iletim geometrisi | hat {len(power_lines.get('features', []))}",
                observed_at=self._power_lines_cache_at,
                href="https://wiki.openstreetmap.org/wiki/Overpass_API",
            ),
        ]

        return SpaceWeatherBundle(
            mode="live",
            fetched_at=datetime.now(timezone.utc),
            planetary_kp=planetary_kp,
            minute_kp=minute_kp,
            mag=mag,
            plasma=plasma,
            xray=xray,
            f107=f107,
            cmes=donki_rows,
            alerts=alerts,
            noaa_scales=noaa_scales,
            kp_forecast=kp_forecast,
            tle_text=tle_text,
            power_lines=power_lines,
            source_statuses=source_statuses,
        )

    def _load_archive_bundle(self) -> SpaceWeatherBundle:
        bundle_dir = self.settings.archive_dir / self.settings.archive_bundle
        fetched_at = datetime.now(timezone.utc)
        power_lines = load_json(bundle_dir / "power-lines.geojson")
        return SpaceWeatherBundle(
            mode="archive",
            fetched_at=fetched_at,
            planetary_kp=parse_noaa_table((bundle_dir / "noaa-planetary-k-index.json").read_text(encoding="utf-8")),
            minute_kp=load_json(bundle_dir / "planetary_k_index_1m.json"),
            mag=parse_noaa_table((bundle_dir / "mag-1-day.json").read_text(encoding="utf-8")),
            plasma=parse_noaa_table((bundle_dir / "plasma-1-day.json").read_text(encoding="utf-8")),
            xray=load_json(bundle_dir / "xrays-6-hour.json"),
            f107=load_json(bundle_dir / "f107_cm_flux.json"),
            cmes=load_json(bundle_dir / "donki-cme.json"),
            alerts=[],
            noaa_scales={},
            kp_forecast=[],
            tle_text=(bundle_dir / "active.tle").read_text(encoding="utf-8"),
            power_lines=power_lines,
            source_statuses=[
                SourceStatus(
                    id="archive-noaa",
                    label="Archive NOAA",
                    state="archive",
                    detail="Arsivlenmis NOAA telemetrisi",
                    observed_at=fetched_at,
                    href=None,
                ),
                SourceStatus(
                    id="archive-donki",
                    label="Archive DONKI",
                    state="archive",
                    detail="Arsivlenmis NASA CME kayitlari",
                    observed_at=fetched_at,
                    href=None,
                ),
                SourceStatus(
                    id="archive-celestrak",
                    label="Archive CelesTrak",
                    state="archive",
                    detail="Arsivlenmis TLE katalougu",
                    observed_at=fetched_at,
                    href=None,
                ),
                SourceStatus(
                    id="archive-overpass",
                    label="Archive Overpass",
                    state="archive",
                    detail=f"Arsivlenmis iletim geometrisi | hat {len(power_lines.get('features', []))}",
                    observed_at=fetched_at,
                    href=None,
                ),
            ],
        )

    async def _fetch_power_lines(self, client: httpx.AsyncClient) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        if self._power_lines_cache and self._power_lines_cache_at and (now - self._power_lines_cache_at) < timedelta(hours=self.settings.overpass_cache_hours):
            return self._power_lines_cache

        corridor_queries = "".join(
            f'way["power"~"line|minor_line"](around:{self.settings.overpass_radius_m},{latitude},{longitude});'
            for latitude, longitude in TURKIYE_QUERY_POINTS
        )
        query = f"[out:json][timeout:45];({corridor_queries}>;);out body geom;"
        try:
            response = await client.post(self.settings.overpass_api_url, data={"data": query})
            response.raise_for_status()
            payload = response.json()
            features = []
            seen_ids: set[int] = set()
            for element in payload.get("elements", []):
                if element.get("type") != "way" or "geometry" not in element:
                    continue
                osm_id = int(element.get("id"))
                if osm_id in seen_ids:
                    continue
                seen_ids.add(osm_id)
                coordinates = [(point["lon"], point["lat"]) for point in element["geometry"]]
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coordinates,
                        },
                        "properties": {
                            **element.get("tags", {}),
                            "osm_id": osm_id,
                        },
                    }
                )
            self._power_lines_cache = {"type": "FeatureCollection", "features": features}
            self._power_lines_cache_at = now
            self._power_lines_state = "live"
            self._write_cache("power-lines.geojson", json.dumps(self._power_lines_cache))
        except Exception:
            if self._power_lines_cache is None:
                cached = self._read_cache("power-lines.geojson")
                if cached is not None:
                    self._power_lines_cache = json.loads(cached.text)
                    self._power_lines_cache_at = cached.cached_at
                    self._power_lines_state = "cached"
                else:
                    bundle_dir = self.settings.archive_dir / self.settings.archive_bundle
                    self._power_lines_cache = load_json(bundle_dir / "power-lines.geojson")
                    self._power_lines_cache_at = now
                    self._power_lines_state = "archive"
        return self._power_lines_cache

    async def _fetch_power_lines_state(self) -> str:
        return self._power_lines_state

    async def _fetch_donki(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if self._donki_cache is not None and self._donki_cache_at and (now - self._donki_cache_at) < timedelta(hours=self.settings.donki_cache_hours):
            return self._donki_cache
        try:
            response = await client.get(
                f"{base_url}/CME",
                params={
                    "startDate": start_date,
                    "endDate": end_date,
                    "api_key": self.settings.nasa_api_key,
                },
            )
            response.raise_for_status()
            self._donki_cache = json.loads(response.text)
            self._donki_cache_at = now
            self._donki_state = "live"
            self._write_cache("donki-cme.json", response.text)
            return self._donki_cache
        except Exception:
            if self._donki_cache is None:
                cached = self._read_cache("donki-cme.json")
                if cached is not None:
                    self._donki_cache = json.loads(cached.text)
                    self._donki_cache_at = cached.cached_at
                    self._donki_state = "cached"
                else:
                    archive_path = self.settings.archive_dir / self.settings.archive_bundle / "donki-cme.json"
                    self._donki_cache = load_json(archive_path)
                    self._donki_cache_at = now
                    self._donki_state = "archive"
            return self._donki_cache

    async def _fetch_donki_state(self) -> str:
        return self._donki_state

    async def _fetch_tle(self, client: httpx.AsyncClient) -> str:
        now = datetime.now(timezone.utc)
        if self._tle_cache is not None and self._tle_cache_at and (now - self._tle_cache_at) < timedelta(hours=self.settings.tle_cache_hours):
            return self._tle_cache
        try:
            response = await client.get(self.settings.celestrak_url)
            response.raise_for_status()
            self._tle_cache = response.text
            self._tle_cache_at = now
            self._tle_state = "live"
            self._write_cache("active.tle", response.text)
            return self._tle_cache
        except Exception:
            if self._tle_cache is None:
                cached = self._read_cache("active.tle")
                if cached is not None:
                    self._tle_cache = cached.text
                    self._tle_cache_at = cached.cached_at
                    self._tle_state = "cached"
                else:
                    archive_path = self.settings.archive_dir / self.settings.archive_bundle / "active.tle"
                    self._tle_cache = archive_path.read_text(encoding="utf-8")
                    self._tle_cache_at = now
                    self._tle_state = "archive"
            return self._tle_cache

    async def _fetch_tle_state(self) -> str:
        return self._tle_state
