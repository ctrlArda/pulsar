import React, { useEffect, useState } from "react";
import { useHelioguardFeed } from "./hooks/useHelioguardFeed";
import { motion, AnimatePresence } from "framer-motion";
import { TurkeyMap } from "./components/TurkeyMap";
import { TurkishSatellitePanel } from "./components/TurkishSatellitePanel";
import { FullTelemetryPanel } from "./components/FullTelemetryPanel";

interface DataPointProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  alert?: boolean;
}

const DataPoint: React.FC<DataPointProps> = ({ label, value, unit, alert = false }) => (
  <div className="ios-data-row">
    <span className="ios-data-label">{label}</span>
    <span className={`ios-data-value mono ${alert ? "danger" : ""}`}>
      {value} {unit && <span className="ios-data-unit">{unit}</span>}
    </span>
  </div>
);

function App() {
  const { state } = useHelioguardFeed();
  const telemetry = state.telemetry;
  const terminal = state.terminal;
  
  const isDanger = (telemetry?.geoDirectExposure || (telemetry?.localRiskPercent ?? 0) > 65) ?? false;

  const [localEtaSecs, setLocalEtaSecs] = useState<number | null>(null);

  useEffect(() => {
    if (telemetry?.etaSeconds !== undefined) {
      setLocalEtaSecs(telemetry.etaSeconds);
    }
  }, [telemetry?.etaSeconds]);

  useEffect(() => {
    if (localEtaSecs === null || localEtaSecs <= 0) return;
    const interval = setInterval(() => {
      setLocalEtaSecs((prev) => (prev && prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [localEtaSecs]);

  const formatSecs = (sec: number | null | undefined) => {
    if (!sec) return "--";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}s ${m}d`;
  };

  const getCountdownString = (sec: number | null) => {
    if (sec === null) return "--:--:--";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (!telemetry) {
     return (
       <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
         <div className="mono" style={{ color: "var(--text-muted)", fontSize: "0.9rem", letterSpacing: "0.02em" }}>Sistemler Hazırlanıyor...</div>
       </div>
     );
  }

  return (
    <main className="ios-page">
      {/* HEADER */}
      <header className="ios-header">
        <div>
           <div className="ios-header-eyebrow">Ulusal Karar Destek Sistemi (DSS)</div>
           <h1 className="ios-header-title">Uzay Havası ve Kritik Altyapı</h1>
           <div className="ios-header-subtitle">
             Mod: {telemetry.mode.toUpperCase()} &bull; Gözlem: {new Date(telemetry.observedAt).toLocaleString("tr-TR")}
           </div>
        </div>
        <div className="ios-status-group">
          <div className="ios-pill mono">
             Aktarım: {telemetry.dataFreshnessSeconds}s
          </div>
          <div className={`ios-pill ${isDanger ? "critical" : ""}`}>
            <div className={`status-dot ${isDanger ? "danger" : ""}`} style={{ borderRadius: "50%", width: 8, height: 8, background: isDanger ? "var(--danger)" : "var(--success)" }} />
            <span>{isDanger ? "TEYAKKUZ DURUMU" : "Sistem Normal"}</span>
          </div>
        </div>
      </header>

      {/* TOP: Map + ETA Panel */}
      <section className="ios-grid-top">
        {/* BIG MAP */}
        <div className="ios-card" style={{ padding: 0 }}>
            <div className="ios-card-header">
               <h2 className="ios-card-title">Ulusal Altyapı Şebeke Maruziyeti</h2>
               <p className="ios-card-subtitle">İdari sınırlar, fiber (GNSS) ve yüksek gerilim iletim hatları etkileşimi</p>
            </div>
            
            <div style={{ flex: 1, background: "var(--surface-solid)", position: "relative", minHeight: 420 }}>
               <TurkeyMap telemetry={telemetry} isDanger={isDanger} width={900} height={420} />
            </div>

            <div className="ios-map-footer">
               <div className="ios-map-stat">
                  <div className="ios-map-stat-label">Haberleşme Sensörü</div>
                  <div className="ios-map-stat-value mono" style={{ color: telemetry.gnssRiskPercent > 50 ? "var(--warning)" : "var(--success)"}}>
                    {telemetry.gnssRiskPercent.toFixed(1)}%
                  </div>
               </div>
               <div className="ios-map-stat">
                  <div className="ios-map-stat-label">Türkiye Pozisyonu</div>
                  <div className="ios-map-stat-value mono" style={{ color: telemetry.geoDirectExposure ? "var(--danger)" : "var(--success)"}}>
                    {telemetry.geoDirectExposure ? "GÜNDÜZ/DİREKT" : "GECE/DOLAYLI"}
                  </div>
               </div>
               <div className="ios-map-stat">
                  <div className="ios-map-stat-label">Enlem Riski</div>
                  <div className="ios-map-stat-value mono" style={{ color: telemetry.localRiskPercent > 60 ? "var(--danger)" : "var(--text)"}}>
                    {telemetry.localRiskPercent.toFixed(1)}%
                  </div>
               </div>
               <div className="ios-map-stat">
                  <div className="ios-map-stat-label">Manyetik Yük</div>
                  <div className="ios-map-stat-value mono" style={{ color: telemetry.predictedDbdtNtPerMin > 300 ? "var(--danger)" : "var(--text)"}}>
                    {telemetry.predictedDbdtNtPerMin.toFixed(1)} <span style={{fontSize: "0.75rem", color: "var(--text-tertiary)"}}>nT/dk</span>
                  </div>
               </div>
            </div>
        </div>

        {/* CRITICAL ETA PANEL */}
        <div className={`ios-card ${isDanger ? "critical" : ""}`}>
           <div className="ios-card-header" style={{ borderBottom: "none", paddingBottom: 0 }}>
             <h2 className="ios-card-title">Fırtına Tahmin (ETA) Merkezi</h2>
           </div>
           
           <div className="ios-card-body" style={{ display: "flex", flexDirection: "column" }}>
             <div className={`ios-huge-number ${isDanger ? "danger" : ""}`}>
               {getCountdownString(localEtaSecs)}
             </div>
             
             <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
               <DataPoint label="Tespit Durumu" value={telemetry.earlyDetection ? "AKTİF" : "BEKLEMEDE"} alert={!telemetry.earlyDetection} />
               <DataPoint label="ETA Başlangıç" value={formatSecs(telemetry.etaWindowStartSeconds)} />
               <DataPoint label="ETA Bitiş Tahmini" value={formatSecs(telemetry.etaWindowEndSeconds)} />
               <DataPoint label="Şok Gecikme" value={formatSecs(telemetry.bowShockDelaySeconds)} />
               <DataPoint label="Varış Güven Skoru" value={`${telemetry.forecastConfidencePercent.toFixed(1)}%`} alert={telemetry.forecastConfidencePercent < 70} />
             </div>

             <div className="ios-alert-box">
               <span style={{ fontWeight: 500, color: "var(--text)" }}>Aktif Gözlem: </span>
               {telemetry.summaryHeadline || telemetry.officialAlertHeadline || telemetry.officialWatchHeadline || "Mevcut uzay havası koşulları nominal sınırlar içerisindedir."}
             </div>
           </div>
        </div>
      </section>

      {/* DETAILED TELEMETRY GRID */}
      <section className="ios-grid-metrics">
         <div className="ios-card">
            <div className="ios-card-header"><h2 className="ios-card-title">Radyasyon Ortamı</h2></div>
            <div className="ios-card-body">
              <DataPoint label="X-Ray Sınıfı" value={telemetry.xrayClass} alert={telemetry.xrayClass.startsWith("X")} />
              <DataPoint label="X-Ray Akısı" value={telemetry.xrayFlux.toExponential(2)} />
              <DataPoint label="Proton Akısı" value={telemetry.protonFluxPfu?.toFixed(1) ?? "--"} unit="pfu" />
              <DataPoint label="CME Sayısı" value={telemetry.cmeCount} alert={telemetry.cmeCount > 2} />
              <DataPoint label="Radyasyon G" value={telemetry.officialSolarRadiationScale || "S0"} />
            </div>
         </div>

         <div className="ios-card">
            <div className="ios-card-header"><h2 className="ios-card-title">L1 Lagrange Sensör</h2></div>
            <div className="ios-card-body">
              <DataPoint label="Rüzgar Hızı" value={telemetry.solarWindSpeed.toFixed(0)} unit="km/s" alert={telemetry.solarWindSpeed > 600} />
              <DataPoint label="Plazma Yoğnlk." value={telemetry.density.toFixed(1)} unit="p/cm³" alert={telemetry.density > 20} />
              <DataPoint label="Dinamik Basınç" value={telemetry.dynamicPressureNpa.toFixed(2)} unit="nPa" />
              <DataPoint label="Bt (Manyetik)" value={telemetry.bt.toFixed(1)} unit="nT" />
              <DataPoint label="Bz (Yönelim)" value={telemetry.bz.toFixed(1)} unit="nT" alert={telemetry.bz < -10} />
            </div>
         </div>

         <div className="ios-card">
            <div className="ios-card-header"><h2 className="ios-card-title">İyonosfer Analizi</h2></div>
            <div className="ios-card-body">
              <DataPoint label="Kp İndeksi" value={telemetry.kpIndex.toFixed(2)} />
              <DataPoint label="Tahmini Kp" value={telemetry.estimatedKp.toFixed(2)} alert={telemetry.estimatedKp > 6} />
              <DataPoint label="Dst İndeksi" value={telemetry.dstIndex?.toFixed(0) ?? "--"} unit="nT" alert={(telemetry.dstIndex ?? 0) < -100} />
              <DataPoint label="Gecikme (TEC)" value={telemetry.tecDelayMeters.toFixed(2)} unit="m" />
              <DataPoint label="Manyetopoz Çk." value={telemetry.magnetopauseStandoffRe.toFixed(2)} unit="Re" alert={telemetry.magnetopauseStandoffRe < 6} />
            </div>
         </div>

         <div className="ios-card">
            <div className="ios-card-header"><h2 className="ios-card-title">Öncü Risk (Precursor)</h2></div>
            <div className="ios-card-body">
              <DataPoint label="Dünya Yönü" value={telemetry.precursorIsEarthDirected ? "EVET" : "HAYIR"} alert={telemetry.precursorIsEarthDirected} />
              <DataPoint label="CME Hızı" value={telemetry.precursorCmeSpeedKms?.toFixed(0) ?? "--"} unit="km/s" />
              <DataPoint label="Tahmini Çarpışma" value={telemetry.precursorArrivalAt ? new Date(telemetry.precursorArrivalAt).toLocaleTimeString("tr-TR").slice(0,5) : "--"} />
              <DataPoint label="Doğruluk" value={`${telemetry.precursorConfidencePercent?.toFixed(1) ?? 0}%`} />
              <DataPoint label="Öngörü Ufku" value={`${telemetry.precursorHorizonHours ?? 0}s`} />
            </div>
         </div>

         <div className="ios-card">
            <div className="ios-card-header"><h2 className="ios-card-title">Yapay Zeka Sentez</h2></div>
            <div className="ios-card-body">
              <DataPoint label="AI Tahmin (Dst)" value={telemetry.mlPredictedDstIndex?.toFixed(1) ?? "--"} unit="nT" alert={(telemetry.mlPredictedDstIndex ?? 0) < -100} />
              <DataPoint label="Risk Olasılığı" value={`%${telemetry.riskBandLow.toFixed(0)} - %${telemetry.riskBandHigh.toFixed(0)}`} />
              <DataPoint label="Güven (MAE)" value={telemetry.validationMae?.toFixed(2) ?? "--"} />
              <DataPoint label="Uyarı Sınırı" value={`${telemetry.mlLeadTimeMinutes ?? 60}dk`} />
              <DataPoint label="Algoritma Bandı" value={telemetry.stormScaleBand} />
            </div>
         </div>
      </section>

      <TurkishSatellitePanel telemetry={telemetry} />
      {/* Full telemetry tab is usually large, leaving it inside its own internal rendering */}
      <FullTelemetryPanel telemetry={telemetry} activeAlert={state.activeAlert} />

      {/* BOTTOM ROW: ML Details & Terminal Logs */}
      <section className="ios-grid-bottom">
        
        {/* ML / SHAP EXPLAINABILITY */}
        <div className="ios-card">
           <div className="ios-card-header"><h2 className="ios-card-title">Model Davranış Ağırlıkları</h2></div>
           <div className="ios-card-body">
             <DataPoint label="Kurumsal Baseline" value={telemetry.mlBaselineDstIndex?.toFixed(1) ?? "--"} unit="nT" />
             <DataPoint label="ML Tahmin Riski" value={`${telemetry.mlRiskPercent?.toFixed(1) ?? 0}%`} />
             <DataPoint label="Manyetik Ölçek" value={telemetry.officialGeomagneticScale || "G0"} />

             <div className="ios-alert-box" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
               <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 12, fontWeight: 500, display: "block" }}>
                 Gerçek Zamanlı Karar Ağacı Etki Faktörleri
               </span>
               <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                 {telemetry.mlFeatureContributions?.slice(0, 4).map((c: any) => (
                   <div key={c.feature}>
                     <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", marginBottom: 2 }}>
                       <span style={{ color: "var(--text)" }}>{c.label}</span>
                       <span className="mono" style={{ color: c.direction === "up" ? "var(--warning)" : "var(--accent)" }}>{c.contribution.toFixed(1)}%</span>
                     </div>
                     <div className="ios-weight-bar">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${c.contribution}%` }} style={{ height: "100%", background: c.direction === "up" ? "var(--warning)" : "var(--accent)", borderRadius: 3 }} />
                     </div>
                   </div>
                 ))}
               </div>
               {!telemetry.mlFeatureContributions?.length && <div className="mono" style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "auto" }}>[Yükleniyor...]</div>}
            </div>
           </div>
        </div>

        {/* TERMINAL / LOGS */}
        <div className="ios-card">
          <div className="ios-card-header">
            <h2 className="ios-card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
               Sistem Olay Günlüğü 
               <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", fontWeight: "normal" }}>(SSE Feed)</span>
            </h2>
          </div>
          <div className="ios-card-body" style={{ padding: 16 }}>
             <div className="ios-terminal">
                <div style={{ color: "var(--text-tertiary)", marginTop: 12, fontSize: "0.8rem" }}>
                  &gt; Bekleyen akış veya olay bulunmuyor.
                </div>
                <AnimatePresence>
                  {terminal?.slice(-30).reverse().map((t: any, i: number) => (
                    <motion.div 
                      key={i} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
                      style={{
                         color: t.level === "critical" ? "var(--danger)" : t.level === "warn" ? "var(--warning)" : "var(--text-muted)",
                         marginBottom: 8, fontSize: "0.8rem", lineHeight: 1.4, display: "flex", gap: "8px"
                      }}
                    >
                      <span style={{ color: "var(--text-tertiary)", flexShrink: 0 }}>[{new Date(t.at).toISOString().split("T")[1].slice(0, 8)}]</span>
                      <span style={{ color: "var(--text)", flexShrink: 0, opacity: 0.5, width: "6ch" }}>{t.source}</span>
                      <span style={{ color: t.level === "critical" ? "var(--danger)" : "var(--text)" }}>{t.message}</span>
                    </motion.div>
                  ))}
                </AnimatePresence>
             </div>
          </div>
        </div>

      </section>

    </main>
  );
}

export default App;