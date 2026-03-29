import { useState, useMemo } from "react";
import type { CrisisAlert, TelemetrySnapshot } from "../types/helioguard";

type MetricItem = {
  label: string;
  value: string;
  note?: string;
};

function fmtNumber(value: number | null | undefined, digits = 1, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(digits)}${suffix}`;
}

function fmtBool(value: boolean): string {
  return value ? "Evet" : "Hayır";
}

function fmtDate(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString("tr-TR");
}

function MetricGroup({ title, items }: { title: string; items: MetricItem[] }) {
  return (
    <div className="ios-card" style={{ display: "flex", flexDirection: "column", padding: 0 }}>
      <div className="ios-card-header">
        <h3 className="ios-card-title" style={{ fontSize: "0.95rem" }}>{title}</h3>
      </div>
      <div className="ios-card-body" style={{ padding: "16px 20px" }}>
        {items.map((item, idx) => (
          <div
            key={`${title}-${item.label}`}
            style={{
              display: "flex",
              flexDirection: "column",
              paddingBottom: idx === items.length - 1 ? 0 : 10,
              marginBottom: idx === items.length - 1 ? 0 : 10,
              borderBottom: idx === items.length - 1 ? "none" : "1px solid var(--border-light)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{item.label}</span>
              <span style={{ fontSize: "0.85rem", fontFamily: "var(--font-mono)", color: "var(--text)", fontWeight: 500 }}>{item.value}</span>
            </div>
            {item.note && <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginTop: 4 }}>{item.note}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonBlock({ title, payload }: { title: string; payload: unknown }) {
  const [open, setOpen] = useState(false);
  const content = useMemo(() => JSON.stringify(payload, null, 2), [payload]);

  return (
    <div className="ios-card" style={{ overflow: "hidden", padding: 0 }}>
      <button 
        onClick={() => setOpen(!open)}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "16px 20px",
          background: "transparent",
          border: "none",
          color: "var(--text)",
          fontWeight: 600,
          cursor: "pointer",
          fontSize: "0.95rem"
        }}
      >
        <span>{title}</span>
        <span style={{ color: "var(--text-muted)" }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ background: "var(--surface-solid)", borderTop: "1px solid var(--border-light)" }}>
            <pre
            style={{
                margin: 0,
                padding: "20px",
                overflowX: "auto",
                fontSize: "0.76rem",
                lineHeight: 1.5,
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
            }}
            >
            {content}
            </pre>
        </div>
      )}
    </div>
  );
}

export function FullTelemetryPanel({
  telemetry,
  activeAlert,
}: {
  telemetry: TelemetrySnapshot;
  activeAlert: CrisisAlert | null;
}) {
  const timingMetrics: MetricItem[] = [
    { label: "Gözlem Zamanı", value: fmtDate(telemetry.observedAt) },
    { label: "Mod", value: telemetry.mode.toUpperCase() },
    { label: "Özet Başlık", value: telemetry.summaryHeadline || "--" },
    { label: "Menzil (ETA)", value: fmtNumber(telemetry.etaSeconds, 0, " s") },
    { label: "Tahmin Başlangıç", value: fmtNumber(telemetry.etaWindowStartSeconds, 0, " s") },
    { label: "Tahmin Bitiş", value: fmtNumber(telemetry.etaWindowEndSeconds, 0, " s") },
    { label: "Şok Gecikmesi", value: fmtNumber(telemetry.bowShockDelaySeconds, 0, " s") },
    { label: "Tahmin Güveni", value: fmtNumber(telemetry.forecastConfidencePercent, 1, "%") },
    { label: "Kaynak Kapsamı", value: fmtNumber(telemetry.sourceCoveragePercent, 1, "%") },
    { label: "Veri Tazeliği", value: fmtNumber(telemetry.dataFreshnessSeconds, 0, " s") },
    { label: "Erken Tespit", value: fmtBool(telemetry.earlyDetection) },
    { label: "Fırtına Skalası", value: telemetry.stormScaleBand },
  ];

  const solarMetrics: MetricItem[] = [
    { label: "Güneş Rüzgar Hızı", value: fmtNumber(telemetry.solarWindSpeed, 1, " km/s") },
    { label: "Bz", value: fmtNumber(telemetry.bz, 2, " nT") },
    { label: "Bt", value: fmtNumber(telemetry.bt, 2, " nT") },
    { label: "Yoğunluk", value: fmtNumber(telemetry.density, 2, " p/cm³") },
    { label: "Sıcaklık", value: fmtNumber(telemetry.temperature, 1, " K") },
    { label: "Dinamik Basınç", value: fmtNumber(telemetry.dynamicPressureNpa, 2, " nPa") },
    { label: "Kp İndeksi", value: fmtNumber(telemetry.kpIndex, 2) },
    { label: "Tahmini Kp", value: fmtNumber(telemetry.estimatedKp, 2) },
    { label: "Dst İndeksi", value: fmtNumber(telemetry.dstIndex, 1, " nT") },
    { label: "X-Ray Sınıfı", value: telemetry.xrayClass },
    { label: "X-Ray Akısı", value: telemetry.xrayFlux.toExponential(2) },
    { label: "Proton Akısı", value: fmtNumber(telemetry.protonFluxPfu, 1, " pfu") },
    { label: "F10.7", value: fmtNumber(telemetry.f107Flux, 2, " sfu") },
    { label: "CME Sayısı", value: String(telemetry.cmeCount) },
  ];

  const physicsMetrics: MetricItem[] = [
    { label: "Yerel Manyetik Enlem", value: fmtNumber(telemetry.localMagneticLatitude, 2, "°") },
    { label: "Yerel Solar Saat", value: fmtNumber(telemetry.localSolarHour, 2, " sa") },
    { label: "Auroral Genişleme", value: fmtNumber(telemetry.auroralExpansionPercent, 1, "%") },
    { label: "Manyetopoz Standoff", value: fmtNumber(telemetry.magnetopauseStandoffRe, 2, " Re") },
    { label: "GEO Maruziyet Riski", value: fmtNumber(telemetry.geoExposureRiskPercent, 1, "%") },
    { label: "GEO Direkt Maruziyet", value: fmtBool(telemetry.geoDirectExposure) },
    { label: "Tahmini dB/dt", value: fmtNumber(telemetry.predictedDbdtNtPerMin, 1, " nT/dk") },
    { label: "TEC Gecikmesi", value: fmtNumber(telemetry.tecDelayMeters, 2, " m") },
    { label: "GNSS Riski", value: fmtNumber(telemetry.gnssRiskPercent, 1, "%") },
    { label: "Ulusal Risk", value: fmtNumber(telemetry.localRiskPercent, 1, "%") },
  ];

  const precursorMetrics: MetricItem[] = [
    { label: "Öncü Riski", value: fmtNumber(telemetry.precursorRiskPercent, 1, "%") },
    { label: "Öncü Ufku", value: fmtNumber(telemetry.precursorHorizonHours, 0, " sa") },
    { label: "Öncü Güveni", value: fmtNumber(telemetry.precursorConfidencePercent, 1, "%") },
    { label: "Öncü CME Hızı", value: fmtNumber(telemetry.precursorCmeSpeedKms, 1, " km/s") },
    { label: "Öncü Varış", value: fmtDate(telemetry.precursorArrivalAt) },
    { label: "Dünya Yönlü", value: fmtBool(telemetry.precursorIsEarthDirected) },
  ];

  const mlMetrics: MetricItem[] = [
    { label: "ML Görev Riski", value: fmtNumber(telemetry.mlRiskPercent, 1, "%") },
    { label: "ML Tahmin Dst", value: fmtNumber(telemetry.mlPredictedDstIndex, 1, " nT") },
    { label: "ML Dst P10", value: fmtNumber(telemetry.mlPredictedDstBandLow, 1, " nT") },
    { label: "ML Dst P90", value: fmtNumber(telemetry.mlPredictedDstBandHigh, 1, " nT") },
    { label: "Kurumsal Dst Baseline", value: fmtNumber(telemetry.mlBaselineDstIndex, 1, " nT") },
    { label: "ML Uyarı Süresi", value: fmtNumber(telemetry.mlLeadTimeMinutes, 0, " dk") },
    { label: "Validasyon MAE", value: fmtNumber(telemetry.validationMae, 4) },
    { label: "Validasyon Kapsamı", value: fmtNumber(telemetry.validationBandCoverage, 1, "%") },
  ];

  const officialMetrics: MetricItem[] = [
    { label: "Jeomanyetik Skala", value: telemetry.officialGeomagneticScale || "--" },
    { label: "Radyo Kesintisi", value: telemetry.officialRadioBlackoutScale || "--" },
    { label: "Solar Radyasyon", value: telemetry.officialSolarRadiationScale || "--" },
    { label: "İzleme Başlığı", value: telemetry.officialWatchHeadline || "--" },
    { label: "Alarm Başlığı", value: telemetry.officialAlertHeadline || "--" },
  ];

  const compactTelemetry = useMemo(
    () => ({
      ...telemetry,
      powerLines: {
        type: telemetry.powerLines.type,
        featureCount: telemetry.powerLines.features.length,
        sampleFeatures: telemetry.powerLines.features.slice(0, 3),
      },
    }),
    [telemetry]
  );

  return (
    <section className="ios-satellite-panel" style={{ marginTop: 24 }}>
      <div className="ios-satellite-header" style={{ borderBottom: "none", paddingBottom: 12 }}>
        <div>
          <h2 className="ios-satellite-title">Tam Telemetri ve Analiz Dökümü</h2>
          <p className="ios-satellite-desc">
            Aktif uzay havası parametreleri, ML tahminleri, NOAA ölçekleri ve sistem sağlık durumlarına ait detaylı teknik loglar.
          </p>
        </div>
      </div>

      <div style={{ padding: "0 24px 24px 24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
            <MetricGroup title="Zamanlama ve İzlem" items={timingMetrics} />
            <MetricGroup title="Güneş & L1 Lagrange" items={solarMetrics} />
            <MetricGroup title="Fiziksel Model" items={physicsMetrics} />
            <MetricGroup title="Öncü Veriler" items={precursorMetrics} />
            <MetricGroup title="Yapay Zeka Tahminleri" items={mlMetrics} />
            <MetricGroup title="Resmi Bildirimler" items={officialMetrics} />
          </div>

          <div style={{ display: "grid", gap: 16, marginTop: 24 }}>
            <JsonBlock title="Ham Telemetri Objesi (Debug)" payload={compactTelemetry} />
            <JsonBlock title="Aktif Alarm Payloadı" payload={activeAlert || { status: "Sistem Nominal", code: 200 }} />
          </div>
      </div>
    </section>
  );
}
