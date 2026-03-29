from __future__ import annotations
import ephem
import math


import asyncio
import json
import re
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

TURKISH_SATELLITE_MARKERS = ("TURKSAT", "GOKTURK", "IMECE", "RASAT", "BILSAT", "CONNECTA", "KILICSAT")


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
    dst: list[dict[str, Any]]
    xray: list[dict[str, Any]]
    protons: list[dict[str, Any]]
    f107: list[dict[str, Any]]
    cmes: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    noaa_scales: dict[str, Any]
    kp_forecast: list[dict[str, Any]]
    tle_text: str
    turkish_satellites: list[dict[str, Any]]
    power_lines: dict[str, Any]
    source_statuses: list[SourceStatus]


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _orbit_class_from_mean_motion(mean_motion: float | None) -> str:
    if mean_motion is None:
        return "UNKNOWN"
    if 0.95 <= mean_motion <= 1.1:
        return "GEO"
    if mean_motion >= 11.0:
        return "LEO"
    if mean_motion >= 1.8:
        return "MEO"
    return "HEO"


def _mission_family(name: str) -> str:
    upper_name = name.upper()
    if "TURKSAT" in upper_name:
        return "Haberlesme / GEO"
    if "IMECE" in upper_name:
        return "Yer gozlem / EO"
    if "GOKTURK" in upper_name:
        return "Kesif / ISR"
    return "Ulusal uydu"


def extract_turkish_satellite_catalog(tle_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    satellites: list[dict[str, Any]] = []
    
    now = datetime.now(timezone.utc)
    observer = ephem.Observer()
    observer.lat = '39.0'
    observer.lon = '35.0'
    observer.elevation = 0
    observer.date = now

    for index in range(0, len(lines) - 2, 3):
        name = lines[index]
        upper_name = name.upper()
        if not any(marker in upper_name for marker in TURKISH_SATELLITE_MARKERS):
            continue
        line1 = lines[index + 1]
        line2 = lines[index + 2]
        norad_match = re.search(r"1\s+(\d+)", line1)
        if norad_match is None:
            continue
        
        # line2 format typically has mean motion at [52:63]
        if len(line2) >= 63:
            mean_motion_str = line2[52:63].strip()
            mean_motion = _safe_float(mean_motion_str)
        else:
            mean_motion = None
            
        parts = line2.split()
        inclination_deg = _safe_float(parts[2]) if len(parts) > 2 else None
        eccentricity = _safe_float(f"0.{parts[4]}") if len(parts) > 4 and parts[4].isdigit() else None
        
        latitude = None
        longitude = None
        altitude_km = None
        azimuth_deg = None
        elevation_deg = None
        
        try:
            sat = ephem.readtle(name, line1, line2)
            sat.compute(observer)
            latitude = math.degrees(sat.sublat)
            longitude = math.degrees(sat.sublong)
            altitude_km = sat.elevation / 1000.0  # MSL
            azimuth_deg = math.degrees(sat.az)
            elevation_deg = math.degrees(sat.alt)
        except Exception:
            pass
            
        over_turkiye = bool(
            latitude is not None and longitude is not None
            and 35.5 <= latitude <= 42.8
            and 25.0 <= longitude <= 45.5
        )

        satellites.append(
            {
                "name": name,
                "norad_id": int(norad_match.group(1)),
                "orbit_class": _orbit_class_from_mean_motion(mean_motion),
                "mission_family": _mission_family(name),
                "mean_motion": mean_motion,
                "inclination_deg": inclination_deg,
                "eccentricity": eccentricity,
                "data_source": "TLE catalog (Ephem offline hesaplama)",
                "observed_at": now.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
                "altitude_km": altitude_km,
                "azimuth_deg": azimuth_deg,
                "elevation_deg": elevation_deg,
                "visible_from_turkiye": bool((elevation_deg or -90.0) > 0.0),
                "over_turkiye": over_turkiye,
            }
        )
    satellites.sort(key=lambda item: (item["orbit_class"], item["name"]))
    return satellites


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
        self._n2yo_cache: list[dict[str, Any]] | None = None
        self._n2yo_cache_at: datetime | None = None
        self._n2yo_state: str = "degraded"

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
                dst_raw,
                xray_raw,
                proton_raw,
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
                self._fetch_text_with_cache(client, "kyoto-dst.json", f"{noaa}/products/kyoto-dst.json", fallback_text='[["time_tag","dst"]]'),
                self._fetch_text_with_cache(client, "xrays-1-day.json", f"{noaa}/json/goes/primary/xrays-1-day.json", archive_name="xrays-1-day.json", fallback_text="[]"),
                self._fetch_text_with_cache(client, "integral-protons-1-day.json", f"{noaa}/json/goes/primary/integral-protons-1-day.json", archive_name="integral-protons-1-day.json", fallback_text="[]"),
                self._fetch_text_with_cache(client, "f107_cm_flux.json", f"{noaa}/json/f107_cm_flux.json", archive_name="f107_cm_flux.json"),
                self._fetch_text_with_cache(client, "alerts.json", f"{noaa}/products/alerts.json", fallback_text="[]"),
                self._fetch_text_with_cache(client, "noaa-scales.json", f"{noaa}/products/noaa-scales.json", fallback_text="{}"),
                self._fetch_text_with_cache(client, "noaa-planetary-k-index-forecast.json", f"{noaa}/products/noaa-planetary-k-index-forecast.json", fallback_text='[["time_tag","kp","observed","noaa_scale"]]'),
                self._fetch_donki(client, donki, start_date, end_date),
                self._fetch_tle(client),
                self._fetch_power_lines(client),
            )
            turkish_satellites = await self._fetch_n2yo_turkish_satellites(client)

        planetary_kp = parse_noaa_table(planetary_kp_raw.text)
        minute_kp = json.loads(minute_kp_raw.text)
        mag = parse_noaa_table(mag_raw.text)
        plasma = parse_noaa_table(plasma_raw.text)
        dst = parse_noaa_table(dst_raw.text)
        xray = json.loads(xray_raw.text)
        protons = json.loads(proton_raw.text)
        f107 = json.loads(f107_raw.text)
        alerts = json.loads(alerts_raw.text)
        noaa_scales = json.loads(scales_raw.text)
        kp_forecast = parse_noaa_table(kp_forecast_raw.text)

        source_statuses = [
            SourceStatus(
                id="noaa-rtsw",
                label="NOAA SWPC RTSW",
                state=_combine_source_state([planetary_kp_raw.state, minute_kp_raw.state, mag_raw.state, plasma_raw.state, dst_raw.state, xray_raw.state, proton_raw.state]),
                detail=f"L1, Kp, Dst ve GOES akisi | son paket {_parse_datetime(str((mag[-1] if mag else {}).get('time_tag'))) or mag_raw.cached_at}",
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
                id="n2yo",
                label="N2YO Orbit API",
                state=self._n2yo_state,
                detail=f"Turk uydu yoreunge ve gorunurluk cozumleri | uydu {len(turkish_satellites)}",
                observed_at=self._n2yo_cache_at,
                href="https://www.n2yo.com/api/",
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
            dst=dst,
            xray=xray,
            protons=protons,
            f107=f107,
            cmes=donki_rows,
            alerts=alerts,
            noaa_scales=noaa_scales,
            kp_forecast=kp_forecast,
            tle_text=tle_text,
            turkish_satellites=turkish_satellites,
            power_lines=power_lines,
            source_statuses=source_statuses,
        )

    def _load_archive_bundle(self) -> SpaceWeatherBundle:
        bundle_dir = self.settings.archive_dir / self.settings.archive_bundle
        fetched_at = datetime.now(timezone.utc)
        power_lines = load_json(bundle_dir / "power-lines.geojson")
        tle_text = (bundle_dir / "active.tle").read_text(encoding="utf-8")
        archive_satellites_path = bundle_dir / "n2yo-turkish-satellites.json"
        turkish_satellites = (
            load_json(archive_satellites_path)
            if archive_satellites_path.exists()
            else extract_turkish_satellite_catalog(tle_text)
        )
        return SpaceWeatherBundle(
            mode="archive",
            fetched_at=fetched_at,
            planetary_kp=parse_noaa_table((bundle_dir / "noaa-planetary-k-index.json").read_text(encoding="utf-8")),
            minute_kp=load_json(bundle_dir / "planetary_k_index_1m.json"),
            mag=parse_noaa_table((bundle_dir / "mag-1-day.json").read_text(encoding="utf-8")),
            plasma=parse_noaa_table((bundle_dir / "plasma-1-day.json").read_text(encoding="utf-8")),
            dst=parse_noaa_table((bundle_dir / "kyoto-dst.json").read_text(encoding="utf-8")) if (bundle_dir / "kyoto-dst.json").exists() else [],
            xray=load_json(bundle_dir / "xrays-1-day.json") if (bundle_dir / "xrays-1-day.json").exists() else load_json(bundle_dir / "xrays-6-hour.json"),
            protons=load_json(bundle_dir / "integral-protons-1-day.json") if (bundle_dir / "integral-protons-1-day.json").exists() else [],
            f107=load_json(bundle_dir / "f107_cm_flux.json"),
            cmes=load_json(bundle_dir / "donki-cme.json"),
            alerts=[],
            noaa_scales={},
            kp_forecast=[],
            tle_text=tle_text,
            turkish_satellites=turkish_satellites,
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
                    id="archive-n2yo",
                    label="Archive TurkSat Fleet",
                    state="archive",
                    detail=f"Arsivlenmis Turk uydu envanteri | uydu {len(turkish_satellites)}",
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

    async def _fetch_n2yo_turkish_satellites(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if (
            self._n2yo_cache is not None
            and self._n2yo_cache_at is not None
            and (now - self._n2yo_cache_at) < timedelta(minutes=self.settings.n2yo_cache_minutes)
        ):
            return self._n2yo_cache

        tle_text = await self._fetch_tle(client)
        catalog = extract_turkish_satellite_catalog(tle_text)
        if not catalog:
            self._n2yo_cache = []
            self._n2yo_cache_at = now
            self._n2yo_state = "degraded"
            return self._n2yo_cache

        if not self.settings.n2yo_api_key.strip():
            self._n2yo_cache = catalog
            self._n2yo_cache_at = now
            self._n2yo_state = "degraded"
            return self._n2yo_cache

        async def fetch_satellite_position(satellite: dict[str, Any]) -> dict[str, Any]:
            url = (
                f"{self.settings.n2yo_base_url.rstrip('/')}/positions/"
                f"{satellite['norad_id']}/{self.settings.turkiye_center_lat}/{self.settings.turkiye_center_lon}/"
                f"{self.settings.turkiye_observer_alt_m}/{self.settings.n2yo_positions_seconds}/"
                f"&apiKey={self.settings.n2yo_api_key}"
            )
            try:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
                positions = payload.get("positions") or []
                first_position = positions[0] if positions else {}
                latitude = _safe_float(first_position.get("satlatitude"))
                longitude = _safe_float(first_position.get("satlongitude"))
                altitude_km = _safe_float(first_position.get("sataltitude"))
                azimuth_deg = _safe_float(first_position.get("azimuth"))
                elevation_deg = _safe_float(first_position.get("elevation"))
                observed_at = None
                timestamp = first_position.get("timestamp")
                if timestamp is not None:
                    observed_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                over_turkiye = bool(
                    latitude is not None
                    and longitude is not None
                    and 35.5 <= latitude <= 42.8
                    and 25.0 <= longitude <= 45.5
                )
                return {
                    **satellite,
                    "data_source": "N2YO live",
                    "observed_at": observed_at.isoformat() if observed_at else None,
                    "latitude": latitude,
                    "longitude": longitude,
                    "altitude_km": altitude_km,
                    "azimuth_deg": azimuth_deg,
                    "elevation_deg": elevation_deg,
                    "visible_from_turkiye": bool((elevation_deg or -90.0) > 0.0),
                    "over_turkiye": over_turkiye,
                }
            except Exception:
                return satellite

        try:
            results = await asyncio.gather(*(fetch_satellite_position(item) for item in catalog))
            live_count = sum(1 for item in results if item.get("data_source") == "N2YO live")
            self._n2yo_cache = results
            self._n2yo_cache_at = now
            self._n2yo_state = "live" if live_count == len(results) else "cached" if live_count else "degraded"
            self._write_cache("n2yo-turkish-satellites.json", json.dumps(results))
            return self._n2yo_cache
        except Exception:
            cached = self._read_cache("n2yo-turkish-satellites.json")
            if cached is not None:
                self._n2yo_cache = json.loads(cached.text)
                self._n2yo_cache_at = cached.cached_at
                self._n2yo_state = "cached"
                return self._n2yo_cache
            self._n2yo_cache = catalog
            self._n2yo_cache_at = now
            self._n2yo_state = "degraded"
            return self._n2yo_cache
