import { useEffect, useMemo, useState } from "react";
import { DrilldownPanel } from "./components/DrilldownPanel";
import { CurrentOpsPanel } from "./components/CurrentOpsPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { HeatMapPanel } from "./components/HeatMapPanel";
import { IntelligencePanel } from "./components/IntelligencePanel";
import { KpTimeline } from "./components/KpTimeline";
import { LiveTerminal } from "./components/LiveTerminal";
import { ScientificPanel } from "./components/ScientificPanel";
import { SignalHero } from "./components/SignalHero";
import { ThreatBoard } from "./components/ThreatBoard";
import { TimelinePanel } from "./components/TimelinePanel";
import { TopRegionsPanel } from "./components/TopRegionsPanel";
import {
  getAiExplainability,
  getAlarmDrivers,
  getCityDrilldown,
  getCityOptions,
  getEvidenceItems,
  getTimeline,
  getTopRegions,
  infrastructurePoints,
  triggerReportDownload,
} from "./lib/dashboardInsights";
import { formatCompact, formatTimestamp } from "./lib/format";
import { type AppLocale, translateGeneratedText, uiText } from "./lib/i18n";
import { useHelioguardFeed } from "./hooks/useHelioguardFeed";

function App() {
  const { state, loading, error, isSwitching, switchMode } = useHelioguardFeed();
  const telemetry = state.telemetry;
  const [locale, setLocale] = useState<AppLocale>("tr");
  const [presentationMode, setPresentationMode] = useState(false);
  const [selectedCityId, setSelectedCityId] = useState("ankara");
  const copy = uiText[locale];

  const translatedHeadline = useMemo(() => {
    if (state.activeAlert) {
      return translateGeneratedText(state.activeAlert.title, locale);
    }
    if (telemetry) {
      return translateGeneratedText(telemetry.summaryHeadline, locale);
    }
    return locale === "tr" ? "Uzay havasi motoru baslatiliyor" : "Space-weather engine is starting";
  }, [locale, state.activeAlert, telemetry]);

  const topRegions = useMemo(() => getTopRegions(telemetry, locale), [telemetry, locale]);
  const alarmDrivers = useMemo(() => getAlarmDrivers(telemetry, locale), [telemetry, locale]);
  const aiExplainability = useMemo(() => getAiExplainability(telemetry, locale), [telemetry, locale]);
  const evidenceItems = useMemo(() => getEvidenceItems(state, locale), [locale, state]);
  const timeline = useMemo(() => getTimeline(state, locale), [locale, state]);
  const cityOptions = useMemo(() => getCityOptions(locale), [locale]);
  const drilldown = useMemo(() => getCityDrilldown(selectedCityId, telemetry, state.activeAlert, locale), [locale, selectedCityId, state.activeAlert, telemetry]);

  useEffect(() => {
    document.body.classList.toggle("presentation-mode", presentationMode);
    return () => document.body.classList.remove("presentation-mode");
  }, [presentationMode]);

  useEffect(() => {
    const syncFullscreen = () => setPresentationMode(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  async function togglePresentationMode() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen?.();
        setPresentationMode(true);
      } else {
        await document.exitFullscreen?.();
        setPresentationMode(false);
      }
    } catch {
      setPresentationMode((current) => !current);
    }
  }

  return (
    <main className={`app-shell ${presentationMode ? "presentation-shell" : ""}`}>
      <header className="masthead masthead-controls">
        <div>
          <span className="eyebrow">{copy.title}</span>
          <strong>{translatedHeadline}</strong>
        </div>
        <div className="masthead-meta">
          <span>{copy.sources}</span>
          {telemetry ? <span>{locale === "tr" ? "Son paket" : "Latest packet"} {formatTimestamp(telemetry.observedAt, locale)}</span> : null}
        </div>
        <div className="toolbar-controls">
          <div className="locale-toggle">
            <button className={locale === "tr" ? "active" : ""} type="button" onClick={() => setLocale("tr")}>
              TR
            </button>
            <button className={locale === "en" ? "active" : ""} type="button" onClick={() => setLocale("en")}>
              EN
            </button>
          </div>
          <button className="presentation-toggle" type="button" onClick={() => void togglePresentationMode()}>
            {presentationMode ? copy.presentationOff : copy.presentationOn}
          </button>
        </div>
      </header>

      <SignalHero
        telemetry={telemetry}
        activeAlert={state.activeAlert}
        mode={state.mode}
        isSwitching={isSwitching}
        onSwitchMode={switchMode}
        locale={locale}
      />

      {error ? <div className="banner-error">{error}</div> : null}

      <section className="summary-grid">
        <article className="panel">
          <span className="eyebrow">{locale === "tr" ? "Canli ozet" : "Live summary"}</span>
          <h2>{locale === "tr" ? "Firtina parametreleri" : "Storm parameters"}</h2>
          <dl className="stats-list">
            <div>
              <dt>{locale === "tr" ? "Kp / tahmini" : "Kp / estimated"}</dt>
              <dd>{telemetry ? `${formatCompact(telemetry.kpIndex, 1, locale)} / ${formatCompact(telemetry.estimatedKp, 1, locale)}` : "--"}</dd>
            </div>
            <div>
              <dt>X-Ray</dt>
              <dd>{telemetry ? `${telemetry.xrayClass} (${telemetry.xrayFlux.toExponential(2)})` : "--"}</dd>
            </div>
            <div>
              <dt>F10.7</dt>
              <dd>{telemetry ? `${formatCompact(telemetry.f107Flux, 0, locale)} sfu` : "--"}</dd>
            </div>
            <div>
              <dt>{locale === "tr" ? "CME sayisi" : "CME count"}</dt>
              <dd>{telemetry ? formatCompact(telemetry.cmeCount, 0, locale) : "--"}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <span className="eyebrow">{locale === "tr" ? "Tahmin motoru" : "Prediction engine"}</span>
          <h2>{locale === "tr" ? "ML + fizik isbirligi" : "ML + physics cooperation"}</h2>
          <p className="narrative">
            {translateGeneratedText(
              state.activeAlert?.narrative ??
                (locale === "tr"
                  ? "XGBoost tahmini, son 10 dakikalik bz, hiz, yogunluk ve sicaklik akisini alip fizik katmanina devreder. Sonuc, Turkiye geneli cihaz hasari ve SOP listesine donusur."
                  : "The XGBoost forecast consumes the last 10 minutes of bz, speed, density, and temperature, then hands the state to the physics layer. The result becomes nationwide device impact and SOP output."),
              locale,
            )}
          </p>
        </article>
      </section>

      {telemetry ? <KpTimeline points={telemetry.kpHistory} locale={locale} /> : null}

      <section className="summary-grid advanced-grid">
        <TopRegionsPanel regions={topRegions} locale={locale} />
        <EvidencePanel
          items={evidenceItems}
          locale={locale}
          onDownloadJson={() => triggerReportDownload(state, selectedCityId, locale, "json")}
          onDownloadTxt={() => triggerReportDownload(state, selectedCityId, locale, "txt")}
        />
      </section>

      <IntelligencePanel drivers={alarmDrivers} aiSummary={aiExplainability.summary} locale={locale} />
      <ScientificPanel telemetry={telemetry} locale={locale} />
      <CurrentOpsPanel telemetry={telemetry} locale={locale} />

      <HeatMapPanel telemetry={telemetry} locale={locale} infrastructure={infrastructurePoints} selectedCityId={selectedCityId} />
      <DrilldownPanel
        cityOptions={cityOptions}
        selectedCityId={selectedCityId}
        onSelectCity={setSelectedCityId}
        drilldown={drilldown}
        locale={locale}
      />

      <TimelinePanel events={timeline} locale={locale} />
      <ThreatBoard alert={state.activeAlert} locale={locale} />
      <LiveTerminal lines={state.terminal} locale={locale} />

      {loading ? <div className="loading-shield">{locale === "tr" ? "Panel verisi yukleniyor..." : "Loading panel data..."}</div> : null}
    </main>
  );
}

export default App;
