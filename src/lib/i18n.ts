export type AppLocale = "tr" | "en";

export const uiText = {
  tr: {
    localeLabel: "TR",
    title: "Space Weather Sentinel",
    sources: "Canli taban: NOAA SWPC, NASA DONKI, CelesTrak, Overpass / Turkiye geneli",
    presentationOn: "Sunum Modu",
    presentationOff: "Standart Mod",
    downloadJson: "JSON Rapor",
    downloadTxt: "TXT Rapor",
    evidence: "Kanit paneli",
    evidenceTitle: "Kaynak, zaman damgasi ve veri izi",
    timeline: "Olay zaman tüneli",
    timelineTitle: "Erken tespit > tahmin > aksiyon",
    ranking: "Bolgesel siralama",
    rankingTitle: "En riskli ilk 5 bolge",
    drilldown: "Il / sehir inceleme",
    drilldownTitle: "Secili merkez icin detayli etki",
    drivers: "Neden alarm verdi?",
    driversTitle: "Alarm tetikleyicileri ve aciklanabilirlik",
    aiExplain: "AI aciklanabilirlik",
    aiExplainTitle: "Modeli en cok iten sinyaller",
    infrastructure: "Altyapi katmanlari",
    infrastructureTitle: "Havalimani, liman, sebeke ve GNSS dugumleri",
    selectCity: "Sehir sec",
    topRegionsEmpty: "Bolgesel siralama icin telemetri bekleniyor.",
    evidenceEmpty: "Kanit paneli icin telemetri bekleniyor.",
    timelineEmpty: "Zaman tuneli icin alarm kaydi bekleniyor.",
    drilldownEmpty: "Sehir detayi icin telemetri bekleniyor.",
    noInfrastructure: "Secili sehir icin tanimli altyapi dugumu yok.",
    reportGenerated: "Rapor indirildi",
    reportSubtitle: "Gercek veri + fizik + ML karar katmani",
    regionRisk: "Bolgesel risk",
    confidence: "Guven",
    relatedInfra: "Ilgili altyapi",
    affectedSystems: "Muhtemel etki alanlari",
    cityNarrativePrefix: "Secili sehirde beklenen tablo",
    source: "Kaynak",
    capturedAt: "Paket zamani",
    status: "Durum",
    detail: "Detay",
    nationalRisk: "Ulusal risk",
    likelyImpact: "Beklenen etki",
    actionNow: "Hemen simdi",
    actionNext: "Sonraki adim",
    mapLegendGrid: "Sebeke",
    mapLegendAirport: "Havalimani",
    mapLegendPort: "Liman",
    mapLegendGnss: "GNSS",
    mapLegendCity: "Secili sehir",
  },
  en: {
    localeLabel: "EN",
    title: "Space Weather Sentinel",
    sources: "Live backbone: NOAA SWPC, NASA DONKI, CelesTrak, Overpass / Nationwide Turkey",
    presentationOn: "Presentation Mode",
    presentationOff: "Standard Mode",
    downloadJson: "JSON Report",
    downloadTxt: "TXT Report",
    evidence: "Evidence Panel",
    evidenceTitle: "Source, timestamp, and data provenance",
    timeline: "Event Timeline",
    timelineTitle: "Early detection > prediction > action",
    ranking: "Regional Ranking",
    rankingTitle: "Top 5 highest-risk regions",
    drilldown: "City Drill-down",
    drilldownTitle: "Detailed impact for the selected city",
    drivers: "Why Did It Trigger?",
    driversTitle: "Alarm drivers and explainability",
    aiExplain: "AI Explainability",
    aiExplainTitle: "Signals pushing the model the most",
    infrastructure: "Infrastructure Layers",
    infrastructureTitle: "Airports, ports, grid nodes, and GNSS hubs",
    selectCity: "Select city",
    topRegionsEmpty: "Waiting for telemetry to rank regions.",
    evidenceEmpty: "Waiting for telemetry to build evidence.",
    timelineEmpty: "Waiting for an alert to build the timeline.",
    drilldownEmpty: "Waiting for telemetry to inspect a city.",
    noInfrastructure: "No mapped infrastructure node for the selected city.",
    reportGenerated: "Report downloaded",
    reportSubtitle: "Real data + physics + ML decision layer",
    regionRisk: "Regional risk",
    confidence: "Confidence",
    relatedInfra: "Relevant infrastructure",
    affectedSystems: "Likely affected systems",
    cityNarrativePrefix: "Expected picture for the selected city",
    source: "Source",
    capturedAt: "Package time",
    status: "Status",
    detail: "Detail",
    nationalRisk: "National risk",
    likelyImpact: "Likely impact",
    actionNow: "Right now",
    actionNext: "Next step",
    mapLegendGrid: "Grid",
    mapLegendAirport: "Airport",
    mapLegendPort: "Port",
    mapLegendGnss: "GNSS",
    mapLegendCity: "Selected city",
  },
} as const;

const exactTextMap: Record<string, string> = {
  "KIRMIZI ALARM: Erken tespit basarili": "RED ALERT: Early detection succeeded",
  "Turkiye uzerindeki manyetik yuk hizla artiyor": "Magnetic load over Turkey is rising quickly",
  "Arka planda CME akisi izleniyor": "CME activity is building in the background",
  "Uzay havasi izleme modunda": "Space weather monitoring mode",
  "HF/VHF radyo kararmasi": "HF/VHF radio blackout",
  "LEO uydu surtunme artisi": "LEO orbital drag increase",
  "GNSS sapmasi ve GIC riski": "GNSS deviation and GIC risk",
  "Enerji": "Energy",
  "Tarim ve Ulasim": "Agriculture and Mobility",
  "Havacilik": "Aviation",
  "Denizcilik": "Maritime",
  "Uydu Operasyonlari": "Satellite Operations",
  "HELIOGUARD motoru baslatildi.": "HELIOGUARD engine started.",
  "Sistem live moduna gecirildi.": "System switched to live mode.",
  "Sistem archive moduna gecirildi.": "System switched to archive mode.",
  "Fizik katmani DSCOVR L1 telemetrisi ile medyan ETA ve varis penceresi hesapliyor; XGBoost tahmini son 10 dakikadaki paternleri okuyarak 60 dakika sonraki Turkiye geneli risk bandini uretiyor. Sonuc guven puani, cihaz etkisi ve SOP listesine donusturuluyor.": "The physics layer computes a median ETA and arrival window from DSCOVR L1 telemetry; the XGBoost model reads the last 10 minutes of patterns to produce a nationwide Turkey risk band for the next 60 minutes. The result becomes a confidence score, device-impact estimate, and SOP list.",
};

export function translateGeneratedText(text: string, locale: AppLocale): string {
  if (locale === "tr" || !text) {
    return text;
  }
  if (exactTextMap[text]) {
    return exactTextMap[text];
  }

  const subtitleMatch = text.match(/^Turkiye geneli risk %(\d+)\. Anlik Bz ([^ ]+) nT, ruzgar (\d+) km\/s, Kp ([^ ]+)\.$/);
  if (subtitleMatch) {
    return `Nationwide Turkey risk ${subtitleMatch[1]}%. Current Bz ${subtitleMatch[2]} nT, solar wind ${subtitleMatch[3]} km/s, Kp ${subtitleMatch[4]}.`;
  }

  const xrayMatch = text.match(/^GOES X-ray akis seviyesi ([^;]+); (.+)$/);
  if (xrayMatch) {
    return `GOES X-ray flux level ${xrayMatch[1]}; D-layer absorption may suppress the radio horizon.`;
  }

  const leoMatch = text.match(/^F10\.7=(\d+) sfu ve plazma yogunlugu ([^;]+); aktif LEO varlik sayisi yaklasik (\d+)\.$/);
  if (leoMatch) {
    return `F10.7=${leoMatch[1]} sfu and plasma density ${leoMatch[2]}; estimated active LEO objects ${leoMatch[3]}.`;
  }

  const gicMatch = text.match(/^Kp ([^,]+), Bz ([^ ]+) nT ve ruzgar hizi (\d+) km\/s kombinasyonu Turkiye genelindeki geomanyetik sapma ve GIC riskini buyutuyor\.$/);
  if (gicMatch) {
    return `Kp ${gicMatch[1]}, Bz ${gicMatch[2]} nT, and solar wind speed ${gicMatch[3]} km/s increase nationwide geomagnetic deviation and GIC risk.`;
  }

  const alertMatch = text.match(/^(.+) \| risk %(\d+) \| ETA (\d+)s$/);
  if (alertMatch) {
    return `${translateGeneratedText(alertMatch[1], locale)} | risk ${alertMatch[2]}% | ETA ${alertMatch[3]}s`;
  }

  const gridMatch = text.match(/^Power-line katmani (\d+) geometri \| (?:yerel|ulusal) risk %(\d+)$/);
  if (gridMatch) {
    return `Power-line layer ${gridMatch[1]} geometries | national risk ${gridMatch[2]}%`;
  }

  const scienceMatch = text.match(/^X-ray ([^|]+) \| F10\.7=(\d+) \| CME backlog=(\d+)$/);
  if (scienceMatch) {
    return `X-ray ${scienceMatch[1]} | F10.7=${scienceMatch[2]} | CME backlog=${scienceMatch[3]}`;
  }

  const noaaMatch = text.match(/^Bz=([^|]+) \| v=([^|]+) \| n=([^|]+) \| Kp\*=([^|]+)$/);
  if (noaaMatch) {
    return `Bz=${noaaMatch[1]} | v=${noaaMatch[2]} | n=${noaaMatch[3]} | Kp*=${noaaMatch[4]}`;
  }

  return text;
}

export function localeTag(locale: AppLocale): string {
  return locale === "tr" ? "tr-TR" : "en-US";
}
