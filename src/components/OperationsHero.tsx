import { useEtaCountdown } from "../hooks/useEtaCountdown";
import { formatCompact, formatPercent, formatSigned, formatTimestamp } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import { translateGeneratedText } from "../lib/i18n";
import type { CrisisAlert, OperatingMode, TelemetrySnapshot } from "../types/helioguard";

interface OperationsHeroProps {
  telemetry: TelemetrySnapshot | null;
  alert: CrisisAlert | null;
  mode: OperatingMode;
  isSwitching: boolean;
  onSwitchMode: (mode: OperatingMode) => Promise<void>;
  locale: AppLocale;
}

function statusLabel(telemetry: TelemetrySnapshot | null, alert: CrisisAlert | null, locale: AppLocale): string {
  if (telemetry?.geoDirectExposure || alert?.severity === "critical") {
    return locale === "tr" ? "Dogrudan Maruziyet" : "Direct Exposure";
  }
  if ((telemetry?.precursorRiskPercent ?? 0) >= 65) {
    return locale === "tr" ? "Stratejik On Uyari" : "Strategic Pre-Warning";
  }
  if (alert?.severity === "warning" || (telemetry?.localRiskPercent ?? 0) >= 45) {
    return locale === "tr" ? "Yukseltilmis Risk" : "Elevated Risk";
  }
  return locale === "tr" ? "Izleme" : "Monitoring";
}

export function OperationsHero({
  telemetry,
  alert,
  mode,
  isSwitching,
  onSwitchMode,
  locale,
}: OperationsHeroProps) {
  const countdown = useEtaCountdown(telemetry?.observedAt ?? null, telemetry?.etaSeconds ?? alert?.etaSeconds ?? null);
  const heroTitle = translateGeneratedText(
    alert?.title ?? telemetry?.summaryHeadline ?? (locale === "tr" ? "Uzay Firtinasi Harekat Merkezi" : "Solar Storm Operations Center"),
    locale,
  );

  return (
    <section className="hero ops-hero">
      <div className="ops-hero-copy">
        <span className="eyebrow">
          {locale === "tr" ? "HELIOGUARD / Gunes Firtinasi Harekat Merkezi" : "HELIOGUARD / Solar Storm Operations Center"}
        </span>
        <h1>{heroTitle}</h1>
        <p>
          {translateGeneratedText(
            alert?.subtitle ??
              (locale === "tr"
                ? "Gercek zamanli uzay telemetrisi, fizik motoru ve tahmin katmani tek ekranda karar diline cevriliyor."
                : "Real-time space telemetry, the physics engine, and the forecast stack are translated into an operator-ready decision layer."),
            locale,
          )}
        </p>

        <div className="ops-hero-badges">
          <span className={`status-badge ${telemetry?.geoDirectExposure ? "status-critical" : "status-watch"}`}>{statusLabel(telemetry, alert, locale)}</span>
          <span className="status-badge">
            {mode === "archive" ? (locale === "tr" ? "Arsiv Replay" : "Archive Replay") : locale === "tr" ? "Canli Feed" : "Live Feed"}
          </span>
          {telemetry ? <span className="status-badge">{locale === "tr" ? "Paket" : "Packet"} {formatTimestamp(telemetry.observedAt, locale)}</span> : null}
          {telemetry?.officialForecastScale ? <span className="status-badge">NOAA {telemetry.officialForecastScale}</span> : null}
        </div>

        <div className="segmented-control ops-hero-actions">
          <button
            className={mode === "live" ? "active" : ""}
            disabled={isSwitching || mode === "live"}
            onClick={() => void onSwitchMode("live")}
            type="button"
          >
            {locale === "tr" ? "Canli Akis" : "Live"}
          </button>
          <button
            className={mode === "archive" ? "active" : ""}
            disabled={isSwitching || mode === "archive"}
            onClick={() => void onSwitchMode("archive")}
            type="button"
          >
            {locale === "tr" ? "Arsiv Replay" : "Archive"}
          </button>
        </div>
      </div>

      <div className="ops-eta-stage">
        <div className={`ops-eta-core ${telemetry?.geoDirectExposure ? "ops-eta-core-warning" : ""}`}>
          <span className="ios-label">{locale === "tr" ? "Merkez ETA" : "Center ETA"}</span>
          <strong className="ios-big-number">{countdown}</strong>
          <p className="ios-label">
            {locale === "tr"
              ? `Varis penceresi ${telemetry ? `${formatCompact((telemetry.etaWindowStartSeconds ?? 0) / 60, 0, locale)}-${formatCompact((telemetry.etaWindowEndSeconds ?? 0) / 60, 0, locale)} dk` : "--"}`
              : `Arrival window ${telemetry ? `${formatCompact((telemetry.etaWindowStartSeconds ?? 0) / 60, 0, locale)}-${formatCompact((telemetry.etaWindowEndSeconds ?? 0) / 60, 0, locale)} min` : "--"}`}
          </p>
        </div>
        <div className="ops-eta-ring ops-eta-ring-a" />
        <div className="ops-eta-ring ops-eta-ring-b" />
      </div>

      <div className="ops-hero-side">
        <article className="ops-side-card">
          <span>{locale === "tr" ? "Nowcast" : "Nowcast"}</span>
          <strong>{telemetry ? formatPercent(telemetry.localRiskPercent, locale) : "--"}</strong>
          <p>
            {telemetry
              ? locale === "tr"
                ? `Bz ${formatSigned(telemetry.bz, 1, locale)} nT | v ${formatCompact(telemetry.solarWindSpeed, 0, locale)} km/s`
                : `Bz ${formatSigned(telemetry.bz, 1, locale)} nT | v ${formatCompact(telemetry.solarWindSpeed, 0, locale)} km/s`
              : "--"}
          </p>
        </article>
        <article className="ops-side-card">
          <span>{locale === "tr" ? "ML +60m" : "ML +60m"}</span>
          <strong>{telemetry ? formatPercent(telemetry.mlRiskPercent, locale) : "--"}</strong>
          <p>
            {telemetry && telemetry.mlPredictedDstIndex !== null
              ? `${telemetry.mlTargetName ?? "Dst"} ${formatCompact(telemetry.mlPredictedDstIndex, 0, locale)} ${telemetry.mlTargetUnit ?? "nT"}`
              : locale === "tr"
                ? "Model bekleniyor"
                : "Waiting for model"}
          </p>
        </article>
        <article className="ops-side-card">
          <span>{locale === "tr" ? "Precursor 24-72h" : "Precursor 24-72h"}</span>
          <strong>{telemetry ? formatPercent(telemetry.precursorRiskPercent, locale) : "--"}</strong>
          <p>
            {telemetry && telemetry.precursorRiskPercent !== null
              ? `${telemetry.precursorHorizonHours ?? "--"}${locale === "tr" ? " sa" : "h"} | ${telemetry.precursorHeadline ?? "GOES + DONKI"}`
              : locale === "tr"
                ? "Orta vadeli outlook pasif"
                : "Medium-horizon outlook inactive"}
          </p>
        </article>
        <article className="ops-side-card">
          <span>{locale === "tr" ? "Guven / kaynaklar" : "Confidence / sources"}</span>
          <strong>{telemetry ? formatPercent(telemetry.forecastConfidencePercent, locale) : "--"}</strong>
          <p>
            {telemetry
              ? locale === "tr"
                ? `${formatPercent(telemetry.sourceCoveragePercent, locale)} kapsama | ${telemetry.officialGeomagneticScale ?? "G0"}`
                : `${formatPercent(telemetry.sourceCoveragePercent, locale)} coverage | ${telemetry.officialGeomagneticScale ?? "G0"}`
              : "--"}
          </p>
        </article>
      </div>
    </section>
  );
}
