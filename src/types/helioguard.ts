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

export interface ModelContribution {
  feature: string;
  label: string;
  contribution: number;
  direction: string;
}

export interface DecisionCommentary {
  id: string;
  title: string;
  value: string;
  category: string;
  basis: "measured" | "modeled" | "fused";
  explanation: string;
  implication: string;
  confidenceNote: string;
}

export interface TurkishSatelliteAssessment {
  name: string;
  noradId: number;
  missionFamily: string;
  orbitClass: string;
  dataSource: string;
  observedAt: string | null;
  latitude: number | null;
  longitude: number | null;
  altitudeKm: number | null;
  azimuthDeg: number | null;
  elevationDeg: number | null;
  overTurkiye: boolean;
  visibleFromTurkiye: boolean;
  dragRiskPercent: number;
  chargingRiskPercent: number;
  radiationRiskPercent: number;
  serviceRiskPercent: number;
  overallRiskPercent: number;
  dominantDriver: string;
  summary: string;
  observationSummary: string;
  riskReason: string;
  scientificNote: string;
  recommendedAction: string;
}

export interface TelemetrySnapshot {
  observedAt: string;
  mode: OperatingMode;
  solarWindSpeed: number;
  bz: number;
  bt: number;
  density: number;
  temperature: number;
  dynamicPressureNpa: number;
  kpIndex: number;
  estimatedKp: number;
  dstIndex: number | null;
  xrayFlux: number;
  xrayClass: string;
  protonFluxPfu: number | null;
  f107Flux: number;
  cmeCount: number;
  earlyDetection: boolean;
  etaSeconds: number | null;
  etaWindowStartSeconds: number | null;
  etaWindowEndSeconds: number | null;
  bowShockDelaySeconds: number | null;
  localRiskPercent: number;
  riskBandLow: number;
  riskBandHigh: number;
  localMagneticLatitude: number;
  localSolarHour: number;
  auroralExpansionPercent: number;
  magnetopauseStandoffRe: number;
  magnetopauseShapeAlpha: number;
  geoExposureRiskPercent: number;
  geoDirectExposure: boolean;
  predictedDbdtNtPerMin: number;
  tecVerticalTecu: number;
  tecDelayMeters: number;
  gnssRiskPercent: number;
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
  precursorRiskPercent: number | null;
  precursorRiskBandLow: number | null;
  precursorRiskBandHigh: number | null;
  precursorHorizonHours: number | null;
  precursorConfidencePercent: number | null;
  precursorHeadline: string | null;
  precursorCmeSpeedKms: number | null;
  precursorArrivalAt: string | null;
  precursorIsEarthDirected: boolean;
  mlRiskPercent: number | null;
  mlRiskBandLow: number | null;
  mlRiskBandHigh: number | null;
  mlPredictedDstIndex: number | null;
  mlPredictedDstBandLow: number | null;
  mlPredictedDstBandHigh: number | null;
  mlBaselineDstIndex: number | null;
  mlTargetName: string | null;
  mlTargetUnit: string | null;
  mlFeatureContributions: ModelContribution[];
  mlLeadTimeMinutes: number | null;
  validationMae: number | null;
  validationBandCoverage: number | null;
  validationRows: number | null;
  validationHorizonMinutes: number | null;
  turkishSatelliteCount: number;
  turkishSatelliteRiskPercent: number;
  turkishSatelliteHeadline: string | null;
  turkishSatellites: TurkishSatelliteAssessment[];
  decisionCommentary: DecisionCommentary[];
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

export interface WebhookPreview {
  event: string;
  institutionTargets: string[];
  payload: Record<string, unknown>;
}
