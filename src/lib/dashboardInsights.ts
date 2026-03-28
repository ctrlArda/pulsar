import type { CrisisAlert, DashboardState, HeatCell, TelemetrySnapshot, ThreatImpact } from "../types/helioguard";
import type { AppLocale } from "./i18n";
import { translateGeneratedText } from "./i18n";

export type InfrastructureCategory = "grid" | "airport" | "port" | "gnss";

export interface InfrastructurePoint {
  id: string;
  cityId: string;
  region: string;
  category: InfrastructureCategory;
  latitude: number;
  longitude: number;
  labelTr: string;
  labelEn: string;
  detailTr: string;
  detailEn: string;
}

export interface CityOption {
  id: string;
  region: string;
  labelTr: string;
  labelEn: string;
  summaryTr: string;
  summaryEn: string;
}

export interface RegionRanking {
  id: string;
  label: string;
  riskPercent: number;
  confidence: number;
  detail: string;
}

export interface AlarmDriver {
  id: string;
  label: string;
  score: number;
  detail: string;
}

export interface EvidenceItem {
  id: string;
  source: string;
  value: string;
  detail: string;
  href?: string;
}

export interface TimelineEvent {
  id: string;
  title: string;
  detail: string;
  status: "done" | "active" | "upcoming";
}

export interface CityDrilldown {
  city: string;
  region: string;
  riskPercent: number;
  detail: string;
  infrastructures: InfrastructurePoint[];
  impacts: string[];
}

const cityOptions: CityOption[] = [
  { id: "istanbul", region: "Marmara", labelTr: "Istanbul", labelEn: "Istanbul", summaryTr: "Bogaz, havalimani ve ana iletim koridorlari", summaryEn: "Strait, airport, and primary transmission corridors" },
  { id: "ankara", region: "Ic Anadolu", labelTr: "Ankara", labelEn: "Ankara", summaryTr: "Ulusal sebekeye dagilan merkez dugum", summaryEn: "Central node feeding the national grid" },
  { id: "izmir", region: "Ege", labelTr: "Izmir", labelEn: "Izmir", summaryTr: "Liman, rafineri ve sanayi koridoru", summaryEn: "Port, refinery, and industry corridor" },
  { id: "antalya", region: "Bati Akdeniz", labelTr: "Antalya", labelEn: "Antalya", summaryTr: "Turizm havalimani ve kiyisal haberlesme", summaryEn: "Tourism airport and coastal communications" },
  { id: "adana", region: "Cukurova", labelTr: "Adana", labelEn: "Adana", summaryTr: "Cukurova enerji ve tarim omurgasi", summaryEn: "Cukurova energy and agriculture backbone" },
  { id: "samsun", region: "Orta Karadeniz", labelTr: "Samsun", labelEn: "Samsun", summaryTr: "Karadeniz lojistik ve liman akisi", summaryEn: "Black Sea logistics and port flow" },
  { id: "gaziantep", region: "Guneydogu", labelTr: "Gaziantep", labelEn: "Gaziantep", summaryTr: "Sinir ticareti ve lojistik GNSS baglantisi", summaryEn: "Border trade and logistics GNSS corridor" },
  { id: "erzurum", region: "Dogu Anadolu", labelTr: "Erzurum", labelEn: "Erzurum", summaryTr: "Dogu iletim ve yuksek irtifa baglantisi", summaryEn: "Eastern transmission and high-altitude connectivity" },
  { id: "van", region: "Van Havzasi", labelTr: "Van", labelEn: "Van", summaryTr: "Dogu siniri ve uydu bagimliligi yuksek alan", summaryEn: "Eastern border region with high satellite dependency" },
  { id: "edirne", region: "Trakya", labelTr: "Edirne", labelEn: "Edirne", summaryTr: "Avrupa baglanti koridoru", summaryEn: "Europe-facing connection corridor" },
];

export const infrastructurePoints: InfrastructurePoint[] = [
  { id: "ist-air", cityId: "istanbul", region: "Marmara", category: "airport", latitude: 41.2753, longitude: 28.7519, labelTr: "Istanbul Havalimani", labelEn: "Istanbul Airport", detailTr: "HF/VHF ve GNSS yedekleme kritik", detailEn: "HF/VHF and GNSS redundancy critical" },
  { id: "ist-grid", cityId: "istanbul", region: "Marmara", category: "grid", latitude: 41.02, longitude: 29.03, labelTr: "Trakya-Marmara Sebeke Dugumu", labelEn: "Thrace-Marmara Grid Node", detailTr: "Yuksek yuk transfer koridoru", detailEn: "High-load transfer corridor" },
  { id: "ank-grid", cityId: "ankara", region: "Ic Anadolu", category: "grid", latitude: 39.95, longitude: 32.88, labelTr: "Ankara TEIAS Omurgasi", labelEn: "Ankara TEIAS Backbone", detailTr: "Ulusal dagitim merkezi", detailEn: "National distribution hub" },
  { id: "ank-gnss", cityId: "ankara", region: "Ic Anadolu", category: "gnss", latitude: 39.90, longitude: 32.75, labelTr: "Ic Anadolu GNSS Dugumu", labelEn: "Central Anatolia GNSS Node", detailTr: "Tarim ve lojistik rotalari", detailEn: "Agriculture and logistics routes" },
  { id: "izm-port", cityId: "izmir", region: "Ege", category: "port", latitude: 38.46, longitude: 27.13, labelTr: "Alsancak Limani", labelEn: "Alsancak Port", detailTr: "Deniz haberlesmesi ve lojistik", detailEn: "Maritime communications and logistics" },
  { id: "izm-grid", cityId: "izmir", region: "Ege", category: "grid", latitude: 38.59, longitude: 27.04, labelTr: "Aliaga Enerji Koridoru", labelEn: "Aliaga Energy Corridor", detailTr: "Sanayi ve rafineri besleme hatti", detailEn: "Industry and refinery feed line" },
  { id: "ant-air", cityId: "antalya", region: "Bati Akdeniz", category: "airport", latitude: 36.8993, longitude: 30.8005, labelTr: "Antalya Havalimani", labelEn: "Antalya Airport", detailTr: "Turizm hava trafigi kritik", detailEn: "Tourism air traffic critical" },
  { id: "ada-grid", cityId: "adana", region: "Cukurova", category: "grid", latitude: 37.01, longitude: 35.32, labelTr: "Cukurova Enerji Koridoru", labelEn: "Cukurova Energy Corridor", detailTr: "Tarim sulama ve iletim omurgasi", detailEn: "Irrigation and transmission backbone" },
  { id: "ada-air", cityId: "adana", region: "Cukurova", category: "airport", latitude: 36.9822, longitude: 35.2804, labelTr: "Cukurova Havalimani", labelEn: "Cukurova Airport", detailTr: "Bolgesel hava ulasimi", detailEn: "Regional air transport" },
  { id: "sam-port", cityId: "samsun", region: "Orta Karadeniz", category: "port", latitude: 41.29, longitude: 36.34, labelTr: "Samsun Limani", labelEn: "Samsun Port", detailTr: "Karadeniz ticaret akis noktasi", detailEn: "Black Sea trade flow node" },
  { id: "gzt-gnss", cityId: "gaziantep", region: "Guneydogu", category: "gnss", latitude: 37.05, longitude: 37.36, labelTr: "Gunaydogu Lojistik GNSS Koridoru", labelEn: "Southeast Logistics GNSS Corridor", detailTr: "Sinir lojistigi ve rota takibi", detailEn: "Border logistics and route tracking" },
  { id: "erz-grid", cityId: "erzurum", region: "Dogu Anadolu", category: "grid", latitude: 39.91, longitude: 41.29, labelTr: "Dogu Anadolu Iletim Dugumu", labelEn: "Eastern Anatolia Transmission Node", detailTr: "Uzun iletim hatlari", detailEn: "Long transmission lines" },
  { id: "van-gnss", cityId: "van", region: "Van Havzasi", category: "gnss", latitude: 38.50, longitude: 43.38, labelTr: "Van Sinir GNSS Dugumu", labelEn: "Van Border GNSS Node", detailTr: "Uydu bagimli seyrusefer", detailEn: "Satellite-dependent navigation" },
  { id: "edi-grid", cityId: "edirne", region: "Trakya", category: "grid", latitude: 41.68, longitude: 26.56, labelTr: "Trakya Avrupa Baglantisi", labelEn: "Thrace Europe Interconnect", detailTr: "Sinir otesi iletim koridoru", detailEn: "Cross-border transmission corridor" },
];

function cellRiskPercent(cell: HeatCell, telemetry: TelemetrySnapshot): number {
  return Math.round(Math.min(100, telemetry.localRiskPercent * (0.65 + cell.intensity)));
}

export function getTopRegions(telemetry: TelemetrySnapshot | null, locale: AppLocale): RegionRanking[] {
  if (!telemetry) {
    return [];
  }
  return [...telemetry.heatGrid]
    .map((cell) => ({
      id: cell.id,
      label: cell.label,
      riskPercent: cellRiskPercent(cell, telemetry),
      confidence: Math.round(Math.min(100, 58 + cell.intensity * 34)),
      detail: locale === "tr"
        ? `${cell.label} koridorunda manyetik yogunluk ${Math.round(cell.intensity * 100)} / 100 seviyesinde.`
        : `${cell.label} corridor magnetic load is ${Math.round(cell.intensity * 100)} / 100.`,
    }))
    .sort((left, right) => right.riskPercent - left.riskPercent)
    .slice(0, 5);
}

export function getAlarmDrivers(telemetry: TelemetrySnapshot | null, locale: AppLocale): AlarmDriver[] {
  if (!telemetry) {
    return [];
  }
  const kpScore = Math.round((telemetry.estimatedKp / 9) * 100);
  const bzScore = Math.round(Math.min(100, Math.abs(Math.min(telemetry.bz, 0)) * 6));
  const speedScore = Math.round(Math.min(100, Math.max(0, telemetry.solarWindSpeed - 320) / 6.8));
  const densityScore = Math.round(Math.min(100, telemetry.density * 5));
  const xrayScore = Math.round(Math.min(100, telemetry.xrayFlux * 1e8));
  const f107Score = Math.round(Math.min(100, Math.max(0, telemetry.f107Flux - 100)));
  const drivers = [
    {
      id: "kp",
      label: locale === "tr" ? "Kp / tahmini manyetik siddet" : "Kp / estimated magnetic severity",
      score: kpScore,
      detail: locale === "tr" ? `Tahmini Kp ${telemetry.estimatedKp.toFixed(1)}.` : `Estimated Kp ${telemetry.estimatedKp.toFixed(1)}.`,
    },
    {
      id: "bz",
      label: locale === "tr" ? "Bz guneylenmesi" : "Southward Bz orientation",
      score: bzScore,
      detail: locale === "tr" ? `Anlik Bz ${telemetry.bz.toFixed(1)} nT.` : `Current Bz ${telemetry.bz.toFixed(1)} nT.`,
    },
    {
      id: "speed",
      label: locale === "tr" ? "Gunes ruzgari hizi" : "Solar wind speed",
      score: speedScore,
      detail: locale === "tr" ? `Akis hizi ${Math.round(telemetry.solarWindSpeed)} km/s.` : `Flow speed ${Math.round(telemetry.solarWindSpeed)} km/s.`,
    },
    {
      id: "xray",
      label: locale === "tr" ? "X-ray kararma baskisi" : "X-ray blackout pressure",
      score: xrayScore,
      detail: locale === "tr" ? `${telemetry.xrayClass} sinifi.` : `${telemetry.xrayClass} class.`,
    },
    {
      id: "f107",
      label: locale === "tr" ? "F10.7 ve surtunme baskisi" : "F10.7 drag pressure",
      score: Math.max(f107Score, densityScore),
      detail: locale === "tr" ? `F10.7 ${Math.round(telemetry.f107Flux)} sfu, yogunluk ${telemetry.density.toFixed(1)}.` : `F10.7 ${Math.round(telemetry.f107Flux)} sfu, density ${telemetry.density.toFixed(1)}.`,
    },
  ];
  return drivers.sort((left, right) => right.score - left.score);
}

export function getAiExplainability(telemetry: TelemetrySnapshot | null, locale: AppLocale): { summary: string; topSignals: AlarmDriver[] } {
  const topSignals = getAlarmDrivers(telemetry, locale).slice(0, 3);
  if (!telemetry) {
    return {
      summary: locale === "tr" ? "AI aciklamasi icin telemetri bekleniyor." : "Waiting for telemetry to explain the model.",
      topSignals: [],
    };
  }
  const mlDelta = telemetry.mlRiskPercent !== null ? telemetry.mlRiskPercent - telemetry.localRiskPercent : 0;
  const summary = locale === "tr"
    ? `Model, fizik skoruna gore ${mlDelta >= 0 ? "yukari" : "asagi"} yone ${Math.abs(mlDelta).toFixed(1)} puan sapma goruyor. En baskin sinyaller ${topSignals.map((item) => item.label.toLowerCase()).join(", ")}.`
    : `The model sees a ${mlDelta >= 0 ? "higher" : "lower"} path than physics by ${Math.abs(mlDelta).toFixed(1)} points. Dominant signals: ${topSignals.map((item) => item.label.toLowerCase()).join(", ")}.`;
  return { summary, topSignals };
}

export function getEvidenceItems(state: DashboardState, locale: AppLocale): EvidenceItem[] {
  const telemetry = state.telemetry;
  if (!telemetry) {
    return [];
  }
  const sourceStatuses = telemetry.sourceStatuses ?? [];
  return [
    {
      id: "noaa-plasma",
      source: "NOAA SWPC",
      value: locale === "tr" ? `Bz ${telemetry.bz.toFixed(1)} nT / ${Math.round(telemetry.solarWindSpeed)} km/s` : `Bz ${telemetry.bz.toFixed(1)} nT / ${Math.round(telemetry.solarWindSpeed)} km/s`,
      detail: locale === "tr" ? "DSCOVR/ACE L1 telemetrisi ile fizik motoru beslendi." : "Physics engine fed from DSCOVR/ACE L1 telemetry.",
      href: "https://services.swpc.noaa.gov/",
    },
    {
      id: "noaa-xray",
      source: "NOAA GOES",
      value: telemetry.xrayClass,
      detail: locale === "tr" ? `X-ray akis ${telemetry.xrayFlux.toExponential(2)}.` : `X-ray flux ${telemetry.xrayFlux.toExponential(2)}.`,
      href: "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",
    },
    {
      id: "donki",
      source: "NASA DONKI",
      value: `${telemetry.cmeCount}`,
      detail: locale === "tr" ? "CME backlog sayisi son sorgudan alindi." : "CME backlog count fetched from the latest query.",
      href: "https://api.nasa.gov/",
    },
    {
      id: "tle",
      source: "CelesTrak",
      value: locale === "tr" ? "LEO izleme listesi aktif" : "LEO watchlist active",
      detail: locale === "tr" ? "Uydu etkileri TLE tabanli izleme listesiyle esitleniyor." : "Satellite impacts are matched against a TLE-driven watchlist.",
      href: "https://celestrak.org/",
    },
    {
      id: "overpass",
      source: "Overpass / OSM",
      value: `${telemetry.powerLines.features.length}`,
      detail: locale === "tr" ? "Ulusal enerji hatti geometrisi." : "National energy-line geometry.",
      href: "https://wiki.openstreetmap.org/wiki/Overpass_API",
    },
    {
      id: "model",
      source: "XGBoost",
      value: telemetry.mlRiskPercent !== null ? `${Math.round(telemetry.mlRiskPercent)}%` : "--",
      detail: locale === "tr" ? "Gercek OMNI arsiv verisiyle egitilmis +60 dakika tahmin." : "Real-OMNI trained +60 minute prediction.",
    },
    {
      id: "official-outlook",
      source: "NOAA Outlook",
      value: telemetry.officialForecastScale ? `${telemetry.officialForecastScale} / Kp ${telemetry.officialForecastKpMax ?? "--"}` : telemetry.officialGeomagneticScale ?? "G0",
      detail: locale === "tr"
        ? `Resmi watch: ${telemetry.officialWatchHeadline ?? "aktif watch yok"}.`
        : `Official watch: ${telemetry.officialWatchHeadline ?? "no active watch"}.`,
      href: "https://services.swpc.noaa.gov/products/",
    },
    {
      id: "source-health",
      source: "Live Source Health",
      value: `${sourceStatuses.filter((item) => item.state === "live").length}/${sourceStatuses.length}`,
      detail: locale === "tr"
        ? "Canli/cached kaynak dengesi operasyon panelinde gorunur."
        : "The live-vs-cached source balance is visible in the operations panel.",
    },
  ];
}

export function getTimeline(state: DashboardState, locale: AppLocale): TimelineEvent[] {
  const telemetry = state.telemetry;
  const alert = state.activeAlert;
  if (!telemetry) {
    return [];
  }
  return [
    {
      id: "detect",
      title: locale === "tr" ? "L1 telemetri toplandi" : "L1 telemetry ingested",
      detail: locale === "tr" ? `Bz ${telemetry.bz.toFixed(1)} nT ve hiz ${Math.round(telemetry.solarWindSpeed)} km/s.` : `Bz ${telemetry.bz.toFixed(1)} nT and speed ${Math.round(telemetry.solarWindSpeed)} km/s.`,
      status: "done",
    },
    {
      id: "estimate",
      title: locale === "tr" ? "ETA hesaplandi" : "ETA calculated",
      detail: locale === "tr" ? `${telemetry.etaSeconds ?? 0} saniyelik gecis penceresi.` : `${telemetry.etaSeconds ?? 0}s propagation window.`,
      status: "done",
    },
    {
      id: "ml",
      title: locale === "tr" ? "ML tahmini olusturuldu" : "ML forecast generated",
      detail: locale === "tr" ? `+60 dakika risk ${Math.round(telemetry.mlRiskPercent ?? 0)}%.` : `+60 minute risk ${Math.round(telemetry.mlRiskPercent ?? 0)}%.`,
      status: "done",
    },
    {
      id: "alert",
      title: locale === "tr" ? "Ulusal risk paneli yenilendi" : "National risk panel updated",
      detail: translateGeneratedText(alert?.title ?? telemetry.summaryHeadline, locale),
      status: alert ? "active" : "done",
    },
    {
      id: "sop",
      title: locale === "tr" ? "SOP dagitimi hazir" : "SOP distribution ready",
      detail: locale === "tr" ? `${alert?.sopActions.length ?? 0} eylem maddesi operasyon ekiplerine hazir.` : `${alert?.sopActions.length ?? 0} action items ready for operations teams.`,
      status: alert?.sopActions.length ? "active" : "upcoming",
    },
  ];
}

export function getCityOptions(locale: AppLocale): Array<{ id: string; label: string }> {
  return cityOptions.map((city) => ({
    id: city.id,
    label: locale === "tr" ? city.labelTr : city.labelEn,
  }));
}

export function getCityDrilldown(
  cityId: string,
  telemetry: TelemetrySnapshot | null,
  alert: CrisisAlert | null,
  locale: AppLocale,
): CityDrilldown | null {
  const city = cityOptions.find((item) => item.id === cityId) ?? cityOptions[0];
  if (!telemetry) {
    return null;
  }
  const cell = telemetry.heatGrid.find((item) => item.label === city.region) ?? telemetry.heatGrid[0];
  const infrastructures = infrastructurePoints.filter((item) => item.cityId === city.id);
  const impacts = (alert?.impactedHardware ?? [])
    .map((impact) => translateGeneratedText(impact.title, locale))
    .slice(0, 3);
  return {
    city: locale === "tr" ? city.labelTr : city.labelEn,
    region: city.region,
    riskPercent: cell ? cellRiskPercent(cell, telemetry) : Math.round(telemetry.localRiskPercent),
    detail: locale === "tr" ? city.summaryTr : city.summaryEn,
    infrastructures,
    impacts,
  };
}

export function labelForInfrastructure(point: InfrastructurePoint, locale: AppLocale): string {
  return locale === "tr" ? point.labelTr : point.labelEn;
}

export function detailForInfrastructure(point: InfrastructurePoint, locale: AppLocale): string {
  return locale === "tr" ? point.detailTr : point.detailEn;
}

export function relevantThreats(alert: CrisisAlert | null, locale: AppLocale): string[] {
  return (alert?.impactedHardware ?? []).map((impact: ThreatImpact) => translateGeneratedText(impact.rationale, locale));
}

export function buildReportContent(state: DashboardState, cityId: string, locale: AppLocale): { json: string; txt: string } {
  const drilldown = getCityDrilldown(cityId, state.telemetry, state.activeAlert, locale);
  const evidence = getEvidenceItems(state, locale);
  const timeline = getTimeline(state, locale);
  const ranking = getTopRegions(state.telemetry, locale);
  const drivers = getAlarmDrivers(state.telemetry, locale);
  const ai = getAiExplainability(state.telemetry, locale);
  const payload = {
    generatedAt: new Date().toISOString(),
    locale,
    mode: state.mode,
    telemetry: state.telemetry,
    activeAlert: state.activeAlert,
    cityDrilldown: drilldown,
    evidence,
    timeline,
    topRegions: ranking,
    alarmDrivers: drivers,
    aiExplainability: ai,
  };
  const txt = [
    "HELIOGUARD REPORT",
    `mode: ${state.mode}`,
    `headline: ${state.activeAlert?.title ?? state.telemetry?.summaryHeadline ?? "--"}`,
    `national_risk: ${state.telemetry?.localRiskPercent ?? "--"}%`,
    `national_risk_band: ${state.telemetry ? `${state.telemetry.riskBandLow}-${state.telemetry.riskBandHigh}%` : "--"}`,
    `ml_risk: ${state.telemetry?.mlRiskPercent ?? "--"}%`,
    `ml_risk_band: ${state.telemetry && state.telemetry.mlRiskBandLow !== null && state.telemetry.mlRiskBandHigh !== null ? `${state.telemetry.mlRiskBandLow}-${state.telemetry.mlRiskBandHigh}%` : "--"}`,
    `forecast_confidence: ${state.telemetry?.forecastConfidencePercent ?? "--"}%`,
    `arrival_window_seconds: ${state.telemetry ? `${state.telemetry.etaWindowStartSeconds ?? "--"}-${state.telemetry.etaWindowEndSeconds ?? "--"}` : "--"}`,
    `storm_scale_band: ${state.telemetry?.stormScaleBand ?? "--"}`,
    `official_scales: ${state.telemetry ? `${state.telemetry.officialGeomagneticScale ?? "--"}/${state.telemetry.officialRadioBlackoutScale ?? "--"}/${state.telemetry.officialSolarRadiationScale ?? "--"}` : "--"}`,
    `official_watch: ${state.telemetry?.officialWatchHeadline ?? "--"}`,
    `official_alert: ${state.telemetry?.officialAlertHeadline ?? "--"}`,
    `validation_mae: ${state.telemetry?.validationMae ?? "--"}`,
    `city: ${drilldown?.city ?? "--"}`,
    `city_risk: ${drilldown?.riskPercent ?? "--"}%`,
    "",
    "TOP REGIONS",
    ...ranking.map((item) => `- ${item.label}: ${item.riskPercent}% (${item.confidence}% conf)`),
    "",
    "ALARM DRIVERS",
    ...drivers.map((item) => `- ${item.label}: ${item.score}% | ${item.detail}`),
    "",
    "EVIDENCE",
    ...evidence.map((item) => `- ${item.source}: ${item.value} | ${item.detail}`),
    "",
    "SOURCE STATUS",
    ...(state.telemetry?.sourceStatuses ?? []).map((item) => `- ${item.label}: ${item.state} | ${item.detail}`),
    "",
    "TIMELINE",
    ...timeline.map((item) => `- [${item.status}] ${item.title}: ${item.detail}`),
  ].join("\n");
  return { json: JSON.stringify(payload, null, 2), txt };
}

export function triggerReportDownload(state: DashboardState, cityId: string, locale: AppLocale, kind: "json" | "txt"): void {
  const content = buildReportContent(state, cityId, locale);
  const blob = new Blob([content[kind]], { type: kind === "json" ? "application/json" : "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `helioguard-${state.mode}-${cityId}.${kind}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
