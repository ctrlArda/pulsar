export type OperatingMode = "live" | "archive";
export type Severity = "watch" | "warning" | "critical";
export type ImpactSeverity = "low" | "medium" | "high" | "critical";
export type TerminalLevel = "info" | "warn" | "critical";
export type SourceState = "live" | "cached" | "archive" | "degraded";

export interface GeoJsonPointGeometry {
  type: "Point";
  coordinates: [number, number];
}

export interface GeoJsonLineGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface GeoJsonFeature {
  type: "Feature";
  geometry: GeoJsonPointGeometry | GeoJsonLineGeometry;
  properties: Record<string, string | number | boolean | null>;
}

export interface GeoJsonFeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

export interface HeatCell {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  intensity: number;
}

export interface KpTrendPoint {
  timeTag: string;
  kpIndex: number;
  estimatedKp: number;
}

export interface ThreatImpact {
  id: string;
  title: string;
  severity: ImpactSeverity;
  affectedSystems: string[];
  rationale: string;
}

export interface SopAction {
  sector: string;
  action: string;
  status: "ready" | "urgent";
}

export interface TerminalLine {
  at: string;
  source: string;
  message: string;
  level: TerminalLevel;
}

export interface SourceStatus {
  id: string;
  label: string;
  state: SourceState;
  detail: string;
  observedAt: string | null;
  href: string | null;
}

export interface TelemetrySnapshot {
  observedAt: string;
  mode: OperatingMode;
  solarWindSpeed: number;
  bz: number;
  bt: number;
  density: number;
  temperature: number;
  kpIndex: number;
  estimatedKp: number;
  xrayFlux: number;
  xrayClass: string;
  f107Flux: number;
  cmeCount: number;
  earlyDetection: boolean;
  etaSeconds: number | null;
  etaWindowStartSeconds: number | null;
  etaWindowEndSeconds: number | null;
  localRiskPercent: number;
  riskBandLow: number;
  riskBandHigh: number;
  localMagneticLatitude: number;
  auroralExpansionPercent: number;
  forecastConfidencePercent: number;
  sourceCoveragePercent: number;
  dataFreshnessSeconds: number | null;
  stormScaleBand: string;
  officialGeomagneticScale: string | null;
  officialRadioBlackoutScale: string | null;
  officialSolarRadiationScale: string | null;
  officialWatchHeadline: string | null;
  officialAlertHeadline: string | null;
  officialForecastKpMax: number | null;
  officialForecastScale: string | null;
  mlRiskPercent: number | null;
  mlRiskBandLow: number | null;
  mlRiskBandHigh: number | null;
  mlLeadTimeMinutes: number | null;
  validationMae: number | null;
  validationRows: number | null;
  validationHorizonMinutes: number | null;
  summaryHeadline: string;
  kpHistory: KpTrendPoint[];
  sourceStatuses: SourceStatus[];
  powerLines: GeoJsonFeatureCollection;
  heatGrid: HeatCell[];
}

export interface CrisisAlert {
  id: string;
  createdAt: string;
  mode: OperatingMode;
  severity: Severity;
  title: string;
  subtitle: string;
  etaSeconds: number | null;
  narrative: string;
  telemetry: TelemetrySnapshot;
  impactedHardware: ThreatImpact[];
  sopActions: SopAction[];
}

export interface DashboardState {
  mode: OperatingMode;
  telemetry: TelemetrySnapshot | null;
  activeAlert: CrisisAlert | null;
  alerts: CrisisAlert[];
  terminal: TerminalLine[];
}
