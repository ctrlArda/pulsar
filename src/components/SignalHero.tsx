import { EtaCountdown } from "./EtaCountdown";
import { formatCompact, formatPercent, formatSigned, formatTimestamp } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import { translateGeneratedText } from "../lib/i18n";
import type { CrisisAlert, OperatingMode, TelemetrySnapshot } from "../types/helioguard";

interface SignalHeroProps {
  telemetry: TelemetrySnapshot | null;
  activeAlert: CrisisAlert | null;
  mode: OperatingMode;
  isSwitching: boolean;
  onSwitchMode: (mode: OperatingMode) => Promise<void>;
  locale: AppLocale;
}

function resolveStatus(telemetry: TelemetrySnapshot | null, activeAlert: CrisisAlert | null, locale: AppLocale) {
  if (activeAlert?.severity === "critical" || telemetry?.earlyDetection) {
    return { label: locale === "tr" ? "Kirmizi Alarm" : "Red Alert", tone: "critical" as const };
  }
  if ((telemetry?.localRiskPercent ?? 0) >= 55) {
    return { label: locale === "tr" ? "Yuksek Risk" : "High Risk", tone: "warning" as const };
  }
  return { label: locale === "tr" ? "Izleme" : "Monitoring", tone: "watch" as const };
}

export function SignalHero({
  telemetry,
  activeAlert,
  mode,
  isSwitching,
  onSwitchMode,
  locale,
}: SignalHeroProps) {
  const status = resolveStatus(telemetry, activeAlert, locale);

  return (
    <section className={`hero hero-${status.tone}`}>
      <div className="hero-copy">
        <span className="eyebrow">{locale === "tr" ? "HELIOGUARD / Turkiye Uzay Hava Savunma Konsolu" : "HELIOGUARD / Turkey Space Weather Defense Console"}</span>
        <h1>{translateGeneratedText(activeAlert?.title ?? telemetry?.summaryHeadline ?? (locale === "tr" ? "Canli telemetri bekleniyor" : "Waiting for live telemetry"), locale)}</h1>
        <p>
          {translateGeneratedText(
            activeAlert?.subtitle ??
              (locale === "tr"
                ? "NOAA, DONKI ve gercek yoreunge verisi birlestirilerek Turkiye geneli icin bolgesel uzay firtinasi resmi uretiliyor."
                : "NOAA, DONKI, and real-orbit data are fused into a nationwide Turkey space-weather picture."),
            locale,
          )}
        </p>

        <div className="hero-badges">
          <span className={`status-badge status-${status.tone}`}>{status.label}</span>
          <span className="status-badge">{mode === "archive" ? (locale === "tr" ? "Arsiv Modu" : "Archive Mode") : locale === "tr" ? "Canli Mod" : "Live Mode"}</span>
          {telemetry ? <span className="status-badge">{locale === "tr" ? "Guncelleme" : "Updated"} {formatTimestamp(telemetry.observedAt, locale)}</span> : null}
          {telemetry?.officialForecastScale ? <span className="status-badge">{locale === "tr" ? "NOAA Outlook" : "NOAA Outlook"} {telemetry.officialForecastScale}</span> : null}
        </div>

        <div className="hero-actions">
          <button
            className={mode === "live" ? "active" : ""}
            disabled={isSwitching || mode === "live"}
            onClick={() => void onSwitchMode("live")}
            type="button"
          >
            {locale === "tr" ? "Canli Akis" : "Live Feed"}
          </button>
          <button
            className={mode === "archive" ? "active" : ""}
            disabled={isSwitching || mode === "archive"}
            onClick={() => void onSwitchMode("archive")}
            type="button"
          >
            {locale === "tr" ? "Arsiv Verisiyle Besle" : "Replay Archive"}
          </button>
        </div>
      </div>

      <div className="hero-metrics">
        <EtaCountdown locale={locale} observedAt={telemetry?.observedAt ?? null} etaSeconds={telemetry?.etaSeconds ?? activeAlert?.etaSeconds ?? null} />
        <div className="metric-grid">
          <article>
            <span className="eyebrow">Bz</span>
            <strong>{telemetry ? `${formatSigned(telemetry.bz, 1, locale)} nT` : "--"}</strong>
            <p>{locale === "tr" ? "Koruyucu kalkanin ters kutup zorlanmasi." : "Opposing magnetic pressure on the protective shield."}</p>
          </article>
          <article>
            <span className="eyebrow">{locale === "tr" ? "Gunes ruzgari" : "Solar wind"}</span>
            <strong>{telemetry ? `${formatCompact(telemetry.solarWindSpeed, 0, locale)} km/s` : "--"}</strong>
            <p>{locale === "tr" ? "L1 anlik akis hizi." : "Instantaneous flow speed at L1."}</p>
          </article>
          <article>
            <span className="eyebrow">{locale === "tr" ? "Ulusal risk" : "National risk"}</span>
            <strong>{telemetry ? formatPercent(telemetry.localRiskPercent, locale) : "--"}</strong>
            <p>{locale === "tr" ? "Fizik modeli merkez tahmini; risk bandi ve guven panelde verilir." : "Physics-model central estimate; its risk band and confidence are shown in the panel."}</p>
          </article>
          <article>
            <span className="eyebrow">{locale === "tr" ? "Yapay zeka" : "AI forecast"}</span>
            <strong>{telemetry ? formatPercent(telemetry.mlRiskPercent, locale) : "--"}</strong>
            <p>
              {telemetry?.mlLeadTimeMinutes
                ? locale === "tr"
                  ? `${telemetry.mlLeadTimeMinutes} dakika sonrasi olasilikli ulusal risk tahmini`
                  : `${telemetry.mlLeadTimeMinutes}-minute probabilistic national-risk forecast`
                : locale === "tr"
                  ? "Model dosyasi saglandiginda canli tahmin akisi devreye girer."
                  : "The live prediction stream activates when the model is present."}
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
