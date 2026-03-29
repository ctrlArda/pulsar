import sys

with open('c:/Users/ardau/Desktop/tuah/engine/helioguard/data_sources.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'import ephem' not in text:
    text = 'import ephem\nimport math\n' + text

old_func = """def extract_turkish_satellite_catalog(tle_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    satellites: list[dict[str, Any]] = []
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
        parts = line2.split()
        mean_motion = _safe_float(parts[-1]) if parts else None
        inclination_deg = _safe_float(parts[2]) if len(parts) > 2 else None
        eccentricity = _safe_float(f"0.{parts[4]}") if len(parts) > 4 and parts[4].isdigit() else None
        satellites.append(
            {
                "name": name,
                "norad_id": int(norad_match.group(1)),
                "orbit_class": _orbit_class_from_mean_motion(mean_motion),
                "mission_family": _mission_family(name),
                "mean_motion": mean_motion,
                "inclination_deg": inclination_deg,
                "eccentricity": eccentricity,
                "data_source": "TLE catalog",
                "observed_at": None,
                "latitude": None,
                "longitude": None,
                "altitude_km": None,
                "azimuth_deg": None,
                "elevation_deg": None,
                "visible_from_turkiye": False,
                "over_turkiye": False,
            }
        )
    satellites.sort(key=lambda item: (item["orbit_class"], item["name"]))
    return satellites"""


new_func = """def extract_turkish_satellite_catalog(tle_text: str) -> list[dict[str, Any]]:
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
        parts = line2.split()
        mean_motion = _safe_float(parts[-1]) if parts else None
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
    return satellites"""


if old_func in text:
    text = text.replace(old_func, new_func)
    with open('c:/Users/ardau/Desktop/tuah/engine/helioguard/data_sources.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched successfully")
else:
    print("Could not find the function to patch.")
