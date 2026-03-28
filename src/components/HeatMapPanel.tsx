import { useEffect, useMemo, useRef } from "react";
import { detailForInfrastructure, labelForInfrastructure, type InfrastructurePoint } from "../lib/dashboardInsights";
import { formatPercent } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";
import type { TelemetrySnapshot } from "../types/helioguard";

interface HeatMapPanelProps {
  telemetry: TelemetrySnapshot | null;
  locale: AppLocale;
  infrastructure: InfrastructurePoint[];
  selectedCityId: string;
}

function markerColor(category: InfrastructurePoint["category"]): string {
  switch (category) {
    case "airport":
      return "#54e2ff";
    case "port":
      return "#c8ff8f";
    case "gnss":
      return "#f6c65b";
    default:
      return "#ffb347";
  }
}

export function HeatMapPanel({ telemetry, locale, infrastructure, selectedCityId }: HeatMapPanelProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const copy = uiText[locale];

  const bounds = useMemo(() => {
    let minLon = Number.POSITIVE_INFINITY;
    let maxLon = Number.NEGATIVE_INFINITY;
    let minLat = Number.POSITIVE_INFINITY;
    let maxLat = Number.NEGATIVE_INFINITY;

    const ingest = (longitude: number, latitude: number) => {
      if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
        return;
      }
      minLon = Math.min(minLon, longitude);
      maxLon = Math.max(maxLon, longitude);
      minLat = Math.min(minLat, latitude);
      maxLat = Math.max(maxLat, latitude);
    };

    for (const feature of telemetry?.powerLines.features ?? []) {
      if (feature.geometry.type === "LineString") {
        for (const [longitude, latitude] of feature.geometry.coordinates) {
          ingest(longitude, latitude);
        }
      }
    }
    for (const cell of telemetry?.heatGrid ?? []) {
      ingest(cell.longitude, cell.latitude);
    }
    for (const point of infrastructure) {
      ingest(point.longitude, point.latitude);
    }

    if (!Number.isFinite(minLon) || !Number.isFinite(maxLon) || !Number.isFinite(minLat) || !Number.isFinite(maxLat)) {
      ingest(35.0, 39.0);
    }

    return { minLon, maxLon, minLat, maxLat };
  }, [telemetry?.heatGrid, telemetry?.powerLines.features, infrastructure]);

  const project = (longitude: number, latitude: number) => {
    const padding = 24;
    const width = 960 - padding * 2;
    const height = 520 - padding * 2;
    const lonRange = Math.max(bounds.maxLon - bounds.minLon, 0.01);
    const latRange = Math.max(bounds.maxLat - bounds.minLat, 0.01);
    const x = padding + ((longitude - bounds.minLon) / lonRange) * width;
    const y = padding + (1 - (latitude - bounds.minLat) / latRange) * height;
    return { x, y };
  };

  useEffect(() => {
    if (svgRef.current) {
      svgRef.current.setAttribute("aria-busy", "false");
    }
  }, [telemetry]);

  return (
    <section className="panel map-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{locale === "tr" ? "Ulusal isi haritasi" : "National heat map"}</span>
          <h2>{locale === "tr" ? "Turkiye enerji omurgasi ve risk koridorlari" : "Turkey grid backbone and risk corridors"}</h2>
        </div>
        {telemetry ? <span className="map-risk-tag">{copy.nationalRisk} {formatPercent(telemetry.localRiskPercent, locale)}</span> : null}
      </div>

      <div className="map-fallback zero-map">
        <svg ref={svgRef} viewBox="0 0 960 520" role="img" aria-label={locale === "tr" ? "Turkiye enerji hatti ve risk yogunlugu" : "Turkey power-line and risk intensity map"}>
          <defs>
            <linearGradient id="gridGlow" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#54e2ff" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#ff564a" stopOpacity="0.08" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="960" height="520" fill="url(#gridGlow)" />
          {Array.from({ length: 12 }).map((_, index) => (
            <line key={`v-${index}`} x1={index * 80} y1="0" x2={index * 80} y2="520" stroke="rgba(255,255,255,0.06)" />
          ))}
          {Array.from({ length: 8 }).map((_, index) => (
            <line key={`h-${index}`} x1="0" y1={index * 74} x2="960" y2={index * 74} stroke="rgba(255,255,255,0.06)" />
          ))}

          {(telemetry?.powerLines.features ?? []).map((feature) => {
            if (feature.geometry.type !== "LineString") {
              return null;
            }
            const path = feature.geometry.coordinates
              .map(([lon, lat], index) => {
                const point = project(lon, lat);
                return `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`;
              })
              .join(" ");
            return <path key={String(feature.properties.osm_id)} d={path} fill="none" stroke="#ffd166" strokeWidth="1.5" strokeOpacity="0.62" />;
          })}

          {(telemetry?.heatGrid ?? []).map((cell) => {
            const point = project(cell.longitude, cell.latitude);
            const radius = 20 + cell.intensity * 28;
            return (
              <g key={cell.id}>
                <circle cx={point.x} cy={point.y} r={radius} fill="rgba(255,86,74,0.12)" />
                <circle cx={point.x} cy={point.y} r={10 + cell.intensity * 12} fill="rgba(255,179,71,0.35)" stroke="#ffe0a3" strokeWidth="1" />
                <text x={point.x + 12} y={point.y - 10} fill="#eef4ff" fontSize="12">
                  {cell.label}
                </text>
              </g>
            );
          })}

          {infrastructure.map((point) => {
            const projected = project(point.longitude, point.latitude);
            const selected = point.cityId === selectedCityId;
            return (
              <g key={point.id}>
                <circle
                  cx={projected.x}
                  cy={projected.y}
                  r={selected ? 8 : 5}
                  fill={markerColor(point.category)}
                  stroke={selected ? "#ffffff" : "rgba(255,255,255,0.5)"}
                  strokeWidth={selected ? 2 : 1}
                />
                {selected ? (
                  <text x={projected.x + 10} y={projected.y + 4} fill="#eef4ff" fontSize="11">
                    {labelForInfrastructure(point, locale)}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>

        <div className="zero-map-meta">
          <p>{locale === "tr" ? "Harita tokeni gerektirmeyen SVG panel, gercek Overpass geometrieri ve Turkiye geneli worker risk alanlariyla uretiliyor." : "Token-free SVG map generated from real Overpass geometries and nationwide worker risk fields."}</p>
          <ul>
            <li>{locale === "tr" ? "Ana enerji hatti sayisi" : "Primary grid geometries"}: {telemetry?.powerLines.features.length ?? 0}</li>
            <li>{locale === "tr" ? "Isi hucreleri" : "Heat cells"}: {telemetry?.heatGrid.length ?? 0}</li>
            <li>{locale === "tr" ? "Veri kaynagi: Overpass + NOAA fizik skoru + bolgesel manyetik agirlik" : "Source: Overpass + NOAA physics score + regional magnetic weighting"}</li>
            <li>{locale === "tr" ? "Harita verisi atfi: OpenStreetMap contributors" : "Map attribution: OpenStreetMap contributors"}</li>
          </ul>
          <div className="map-legend">
            <span><i style={{ background: markerColor("grid") }} />{copy.mapLegendGrid}</span>
            <span><i style={{ background: markerColor("airport") }} />{copy.mapLegendAirport}</span>
            <span><i style={{ background: markerColor("port") }} />{copy.mapLegendPort}</span>
            <span><i style={{ background: markerColor("gnss") }} />{copy.mapLegendGnss}</span>
            <span><i style={{ background: "#ffffff" }} />{copy.mapLegendCity}</span>
          </div>
          {infrastructure.filter((item) => item.cityId === selectedCityId).slice(0, 2).map((point) => (
            <article key={point.id} className="infra-inline">
              <strong>{labelForInfrastructure(point, locale)}</strong>
              <p>{detailForInfrastructure(point, locale)}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
