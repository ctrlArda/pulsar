from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import pandas as pd

from helioguard.analysis import estimate_kp_from_solar_wind
from helioguard.config import ROOT_DIR


OMNI_MONTHLY_BASE_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/monthly_1min"
FWF_WIDTHS = [
    4,
    4,
    3,
    3,
    3,
    3,
    4,
    4,
    4,
    7,
    7,
    6,
    7,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    7,
    9,
    6,
    7,
    7,
    6,
    8,
    8,
    8,
    8,
    8,
    8,
    6,
    6,
    6,
    6,
    6,
    6,
    6,
    7,
    5,
]
FWF_COLUMNS = [
    "year",
    "day",
    "hour",
    "minute",
    "imf_sc_id",
    "plasma_sc_id",
    "imf_points",
    "plasma_points",
    "percent_interp",
    "timeshift_sec",
    "rms_timeshift_sec",
    "rms_phase_front_normal",
    "dbot1_sec",
    "bt",
    "bx_gse",
    "by_gse",
    "bz_gse",
    "by_gsm",
    "bz_gsm",
    "rms_sd_b_scalar",
    "rms_sd_field_vector",
    "flow_speed",
    "vx_gse",
    "vy_gse",
    "vz_gse",
    "proton_density",
    "temperature",
    "flow_pressure",
    "electric_field",
    "plasma_beta",
    "alfven_mach_number",
    "x_gse_re",
    "y_gse_re",
    "z_gse_re",
    "bsn_x_gse_re",
    "bsn_y_gse_re",
    "bsn_z_gse_re",
    "ae_index",
    "al_index",
    "au_index",
    "sym_d_index",
    "sym_h_index",
    "asy_d_index",
    "asy_h_index",
    "pcn_index",
    "magnetosonic_mach_number",
]


@dataclass(frozen=True, slots=True)
class DatasetWindow:
    name: str
    month: str
    start: str
    end: str

    @property
    def source_url(self) -> str:
        return f"{OMNI_MONTHLY_BASE_URL}/omni_min{self.month}.asc"


RECOMMENDED_WINDOWS = [
    DatasetWindow("storm-halloween-2003", "200310", "2003-10-28T00:00:00Z", "2003-10-31T23:59:00Z"),
    DatasetWindow("storm-may-2024", "202405", "2024-05-10T00:00:00Z", "2024-05-13T23:59:00Z"),
    DatasetWindow("storm-jan-2026", "202601", "2026-01-01T00:00:00Z", "2026-01-31T23:59:00Z"),
    DatasetWindow("storm-feb-2026", "202602", "2026-02-01T00:00:00Z", "2026-02-28T23:59:00Z"),
]


def _download(url: str, destination: Path, refresh: bool) -> None:
    if destination.exists() and not refresh:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)


def _read_omni_ascii(path: Path) -> pd.DataFrame:
    frame = pd.read_fwf(path, widths=FWF_WIDTHS, names=FWF_COLUMNS, header=None)
    frame["time_tag"] = pd.to_datetime(
        frame["year"].astype("Int64").astype(str).str.zfill(4)
        + frame["day"].astype("Int64").astype(str).str.zfill(3)
        + frame["hour"].astype("Int64").astype(str).str.zfill(2)
        + frame["minute"].astype("Int64").astype(str).str.zfill(2),
        format="%Y%j%H%M",
        utc=True,
        errors="coerce",
    )
    for column in ["bt", "bz_gsm", "flow_speed", "proton_density", "temperature"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame.loc[frame["bt"].abs() > 900.0, "bt"] = pd.NA
    frame.loc[frame["bz_gsm"].abs() > 900.0, "bz_gsm"] = pd.NA
    frame.loc[frame["flow_speed"] > 9000.0, "flow_speed"] = pd.NA
    frame.loc[frame["proton_density"] > 900.0, "proton_density"] = pd.NA
    frame.loc[frame["temperature"] > 9_000_000.0, "temperature"] = pd.NA

    cleaned = frame.dropna(subset=["time_tag", "bt", "bz_gsm", "flow_speed", "proton_density", "temperature"]).copy()
    cleaned["estimated_kp"] = cleaned.apply(
        lambda row: estimate_kp_from_solar_wind(
            float(row["bz_gsm"]),
            float(row["flow_speed"]),
            float(row["proton_density"]),
        ),
        axis=1,
    )
    cleaned["kp_index"] = cleaned["estimated_kp"]
    return cleaned.rename(
        columns={
            "bz_gsm": "bz",
            "flow_speed": "speed",
            "proton_density": "density",
        }
    )[["time_tag", "bz", "bt", "speed", "density", "temperature", "estimated_kp", "kp_index"]]


def prepare_datasets(raw_dir: Path, output_dir: Path, refresh: bool = False) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []

    for window in RECOMMENDED_WINDOWS:
        raw_path = raw_dir / f"omni_min{window.month}.asc"
        _download(window.source_url, raw_path, refresh=refresh)
        frame = _read_omni_ascii(raw_path)

        start = pd.Timestamp(window.start)
        end = pd.Timestamp(window.end)
        sliced = frame[(frame["time_tag"] >= start) & (frame["time_tag"] <= end)].copy()
        output_path = output_dir / f"{window.name}.csv"
        sliced.to_csv(output_path, index=False)

        summaries.append(
            {
                **asdict(window),
                "source_url": window.source_url,
                "output_path": str(output_path),
                "rows": int(len(sliced)),
                "starts_at": sliced["time_tag"].min().isoformat() if not sliced.empty else None,
                "ends_at": sliced["time_tag"].max().isoformat() if not sliced.empty else None,
            }
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and convert official OMNI monthly ASCII files into HELIOGUARD training CSVs.")
    parser.add_argument(
        "--raw-dir",
        default=str(ROOT_DIR / "data" / "training" / "raw"),
        help="Directory to cache raw OMNI monthly files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "data" / "training"),
        help="Directory to write converted CSV files.",
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download source OMNI files even if cached.")
    args = parser.parse_args()

    summary = prepare_datasets(Path(args.raw_dir), Path(args.output_dir), refresh=args.refresh)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
