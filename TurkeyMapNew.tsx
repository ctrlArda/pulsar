import React, { useEffect, useState, useMemo } from "react";
import { geoMercator, geoPath, geoGraticule } from "d3-geo";
import { motion, AnimatePresence } from "framer-motion";
import type { HeatCell } from "../types/helioguard";

const CITIES: Record<string, [number, number]> = {
  IST: [28.9784, 41.0082],
  ANK: [32.8597, 39.9334],
  IZM: [27.1428, 38.4237],
  BUR: [29.0609, 40.1824],
  ANT: [30.7133, 36.8969],
  ADA: [35.3213, 37.0000],
  KON: [32.4833, 37.8667],
  KAY: [35.4826, 38.7312],
  SAM: [36.33, 41.2867],
  TRB: [39.7168, 41.0027],
  ERZ: [41.2769, 39.9000],
  DIY: [40.2306, 37.9144],
  VAN: [43.3833, 38.4924],
  GAZ: [35.3250, 37.0662],
  MER: [34.6415, 36.8000]
};

const TELECOM_LINKS = [
  ["IST", "ANK"], ["IST", "IZM"], ["IST", "BUR"], ["BUR", "ANK"], ["IZM", "ANT"],
  ["ANK", "KON"], ["KON", "ANT"], ["ANK", "KAY"], ["KAY", "ADA"], ["ADA", "MER"],
  ["ADA", "GAZ"], ["GAZ", "DIY"], ["KAY", "DIY"], ["ANK", "SAM"], ["SAM", "TRB"],
  ["TRB", "ERZ"], ["ERZ", "VAN"], ["DIY", "VAN"]
];

interface TurkeyMapProps {
  telemetry: any;
  isDanger: boolean;
  width?: number;
  height?: number;
}

export function TurkeyMap({ telemetry, isDanger, width = 900, height = 460 }: TurkeyMapProps) {
  const [layers, setLayers] = useState({ borders: true, power: true, telecom: true, heat: true });
  const [turkeyGeo, setTurkeyGeo] = useState<any>(null);

  useEffect(() => {
    fetch("/turkey_cities.json")
      .then((r) => r.json())
      .then((data) => setTurkeyGeo(data))
      .catch(console.error);
  }, []);

  const powerLines = telemetry?.powerLines?.features || [];
  const heatGrid = telemetry?.heatGrid || [];
  const gnssRisk = telemetry?.gnssRiskPercent ?? 0;
  const isTelecomDegraded = gnssRisk > 60;

  // D3 Projection configured for Turkey
  const projection = useMemo(() => {
    return geoMercator()
      .center([35.2433, 38.9637]) // Center of Turkey
      .scale(width * 2.9)         // Zoom level
      .translate([width / 2, height / 2]);
  }, [width, height]);

  const pathGenerator = useMemo(() => geoPath().projection(projection), [projection]);
  const graticule = useMemo(() => geoGraticule().step([3, 3]), []);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: height, display: "flex", flexDirection: "column" }}>
      
      {/* Map Layer Toggles - Apple segmented-control style */}
      <div style={{ position: "absolute", top: 20, left: 24, display: "flex", gap: 6, zIndex: 10, background: "var(--panel-strong)", padding: "6px", borderRadius: "999px", border: "1px solid var(--line)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)" }}>
        {[
          { id: "borders", label: "İdari Sınırlar" },
          { id: "power", label: "TEİAŞ 380kV" },
          { id: "telecom", label: "Erişim Ağları" },
          { id: "heat", label: "Manyetik Yük" }
        ].map(({ id, label }) => {
          const isActive = (layers as any)[id];
          return (
            <button
              key={id}
              onClick={() => setLayers((s) => ({ ...s, [id]: !(s as any)[id] }))}
              style={{
                background: isActive ? "var(--text)" : "transparent",
                color: isActive ? "var(--bg)" : "var(--muted)",
                border: "none",
                padding: "6px 14px",
                borderRadius: "999px",
                fontSize: "0.8rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.3s cubic-bezier(0.2, 0, 0, 1)",
                WebkitFontSmoothing: "antialiased"
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", overflow: "hidden" }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", maxWidth: width, height: "auto", overflow: "visible" }}>
          <defs>
            <filter id="glow-heavy" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-light" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Subtle hatch pattern for borders */}
            <pattern id="hatch" width="4" height="4" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="4" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            </pattern>
          </defs>

          {/* Graticule Grid */}
          <path
            d={pathGenerator(graticule()) || ""}
            fill="none"
            stroke="rgba(255,255,255,0.04)"
            strokeWidth={0.5}
            strokeDasharray="2 4"
          />

          {/* Base Map: High Detail Turkey Provinces */}
          <AnimatePresence>
            {layers.borders && turkeyGeo && (
              <motion.g
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5 }}
              >
                {turkeyGeo.features.map((feature: any, idx: number) => (
                  <path
                    key={`prov-${idx}`}
                    d={pathGenerator(feature) || ""}
                    fill="url(#hatch)"
                    stroke="rgba(255,255,255,0.15)"
                    strokeWidth={0.8}
                    style={{ transition: "fill 0.4s ease, stroke 0.4s ease" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.fill = "rgba(255,255,255,0.08)";
                      e.currentTarget.style.stroke = "rgba(255,255,255,0.4)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.fill = "url(#hatch)";
                      e.currentTarget.style.stroke = "rgba(255,255,255,0.15)";
                    }}
                  />
                ))}
              </motion.g>
            )}
          </AnimatePresence>

          {/* Heat Grid (Magnetic Stress) - Monochromatic representation */}
          <AnimatePresence>
            {layers.heat && heatGrid.map((cell: HeatCell, idx: number) => {
              const [cx, cy] = projection([cell.longitude, cell.latitude]) || [0, 0];
              if (!cx && !cy) return null;
              const activeIntensity = Math.max(0, cell.intensity);
              if (activeIntensity < 0.1) return null;
              return (
                <motion.circle
                  key={`heat-${idx}`}
                  cx={cx}
                  cy={cy}
                  r={12 + activeIntensity * 36}
                  fill={isDanger ? "rgba(255, 255, 255, 0.12)" : "rgba(255, 255, 255, 0.05)"}
                  filter="url(#glow-heavy)"
                  initial={{ r: 0, opacity: 0 }}
                  animate={{ r: 12 + activeIntensity * 36, opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.8, type: "spring" }}
                  style={{ pointerEvents: "none" }}
                />
              );
            })}
          </AnimatePresence>

          {/* TEIAS Power Lines */}
          <AnimatePresence>
            {layers.power && powerLines.map((feature: any, idx: number) => {
              if (feature.geometry.type !== "LineString") return null;
              const pathData = pathGenerator(feature);
              if (!pathData) return null;

              const voltage = feature.properties?.voltage || "unknown";
              let strokeColor = "rgba(255,255,255,0.1)";
              let strokeWidth = 0.5;
              let usesFilter = undefined;
              let strokeDash = "none";

              if (voltage === "380000") {
                strokeColor = isDanger ? "rgba(255, 255, 255, 0.85)" : "rgba(255,255,255,0.3)";
                strokeWidth = isDanger ? 1.5 : 1;
                usesFilter = isDanger ? "url(#glow-light)" : undefined;
              } else if (voltage === "154000") {
                strokeColor = isDanger ? "rgba(255, 255, 255, 0.4)" : "rgba(255,255,255,0.15)";
                strokeWidth = 0.8;
                strokeDash = "2 2";
              }

              return (
                <motion.path
                  key={`line-${idx}`}
                  d={pathData}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={strokeDash}
                  filter={usesFilter}
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 1.5, ease: "easeInOut" }}
                />
              );
            })}
          </AnimatePresence>

          {/* Fiber / Telecom Curved Lines */}
          <AnimatePresence>
            {layers.telecom && TELECOM_LINKS.map(([c1, c2], idx) => {
              const [x1, y1] = projection(CITIES[c1]) || [0, 0];
              const [x2, y2] = projection(CITIES[c2]) || [0, 0];
              
              const cx = (x1 + x2) / 2 + (y2 - y1) * 0.15;
              const cy = (y1 + y2) / 2 - (x2 - x1) * 0.15;
              const pathD = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;

              return (
                <motion.path
                  key={`tel-${idx}`}
                  d={pathD}
                  fill="none"
                  stroke={isTelecomDegraded ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.25)"}
                  strokeWidth={isTelecomDegraded ? 1.5 : 1}
                  strokeDasharray={isTelecomDegraded ? "4 4" : "none"}
                  filter={isTelecomDegraded ? "url(#glow-light)" : undefined}
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1, ease: "easeOut", delay: idx * 0.05 }}
                />
              );
            })}
          </AnimatePresence>

          {/* City Hub Markers - Redesigned */}
          {Object.entries(CITIES).map(([name, coords]) => {
            const [cx, cy] = projection(coords) || [0, 0];
            return (
              <g key={name} transform={`translate(${cx}, ${cy})`}>
                {layers.telecom && (
                  <motion.circle
                    r="8"
                    fill="transparent"
                    stroke={isTelecomDegraded ? "var(--text)" : "rgba(255,255,255,0.3)"}
                    strokeWidth={1}
                    animate={{
                      scale: isTelecomDegraded ? [1, 1.5, 1] : 1,
                      opacity: isTelecomDegraded ? [1, 0, 1] : 1
                    }}
                    transition={{
                      repeat: Infinity,
                      duration: 2,
                      ease: "easeInOut"
                    }}
                  />
                )}
                <circle r="3" fill="var(--bg)" stroke="var(--text)" strokeWidth="1.5" />
                <text
                  x="8"
                  y="4"
                  fontSize="0.75rem"
                  fill="var(--text)"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
                  fontWeight={600}
                  letterSpacing="0.05em"
                  style={{ textShadow: "0 2px 8px rgba(0,0,0,1)" }}
                >
                  {name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      
      {/* Map Coordination Legend */}
      <div style={{ position: "absolute", bottom: 20, right: 24, fontSize: "0.75rem", color: "var(--muted)", fontFamily: "ui-monospace, SFMono-Regular, monospace", textAlign: "right", zIndex: 10 }}>
        <div>SYS: 042-ALPHA</div>
        <div>TR-GNSS STATUS: {gnssRisk > 60 ? "DEGRADED" : "NOMINAL"}</div>
      </div>
    </div>
  );
}