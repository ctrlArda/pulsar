from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "engine" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    operating_mode: Literal["live", "archive"] = "live"
    archive_bundle: str = "march-2026-geomagnetic-storm"
    poll_interval_seconds: int = 60
    nasa_api_key: str = "DEMO_KEY"
    noaa_base_url: str = "https://services.swpc.noaa.gov"
    donki_base_url: str = "https://api.nasa.gov/DONKI"
    celestrak_url: str = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    turkiye_center_lat: float = 39.0
    turkiye_center_lon: float = 35.0
    overpass_radius_m: int = 110000
    l1_distance_km: float = 1_500_000
    donki_cache_hours: int = 24
    tle_cache_hours: int = 2
    overpass_cache_hours: int = 6
    archive_dir: Path = Field(default_factory=lambda: ROOT_DIR / "data" / "archive")
    cache_dir: Path = Field(default_factory=lambda: ROOT_DIR / "data" / "cache")
    database_path: Path = Field(default_factory=lambda: ROOT_DIR / "data" / "helioguard.db")
    model_path: Path = Field(default_factory=lambda: ROOT_DIR / "data" / "models" / "xgboost-model.json")
    model_meta_path: Path = Field(default_factory=lambda: ROOT_DIR / "data" / "models" / "xgboost-model.meta.json")


settings = Settings()
