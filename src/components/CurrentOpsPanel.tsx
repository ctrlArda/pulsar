import { formatCompact } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import type { SourceStatus, TelemetrySnapshot } from "../types/helioguard";

interface CurrentOpsPanelProps {
  telemetry: TelemetrySnapshot | null;
  locale: AppLocale;
}

function statusLabel(status: SourceStatus["state"], locale: AppLocale): string {
  switch (status) {
    case "live":
      return locale === "tr" ? "Canli" : "Live";
    case "cached":
      return locale === "tr" ? "Onbellek" : "Cached";
    case "archive":
      return locale === "tr" ? "Arsiv" : "Archive";
    default:
      return locale === "tr" ? "Dusuk" : "Degraded";
  }
}

export function CurrentOpsPanel({ telemetry, locale }: CurrentOpsPanelProps) {
  const sourceStatuses = telemetry?.sourceStatuses ?? [];

  return (
    <section className="panel current-ops-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{locale === "tr" ? "Canli operasyon" : "Live operations"}</span>
          <h2>{locale === "tr" ? "Resmi outlook ve kaynak durumu" : "Official outlook and source status"}</h2>
        </div>
      </div>

      {telemetry ? (
        <>
          <div className="ops-summary-grid">
            <article className="ops-card">
              <span>{locale === "tr" ? "NOAA skalalari" : "NOAA scales"}</span>
              <strong>{`${telemetry.officialGeomagneticScale ?? "G0"} / ${telemetry.officialRadioBlackoutScale ?? "R0"} / ${telemetry.officialSolarRadiationScale ?? "S0"}`}</strong>
              <p>{locale === "tr" ? "Anlik resmi geomanyetik, radyo kararmasi ve radyasyon seviyesi." : "Current official geomagnetic, blackout, and radiation level."}</p>
            </article>
            <article className="ops-card">
              <span>{locale === "tr" ? "NOAA Kp outlook" : "NOAA Kp outlook"}</span>
              <strong>
                {telemetry.officialForecastKpMax !== null
                  ? `Kp ${formatCompact(telemetry.officialForecastKpMax, 1, locale)}${telemetry.officialForecastScale ? ` / ${telemetry.officialForecastScale}` : ""}`
                  : "--"}
              </strong>
              <p>{locale === "tr" ? "Son resmi tahmin penceresindeki en yuksek Kp beklentisi." : "Highest Kp expected in the latest official forecast window."}</p>
            </article>
          </div>

          <div className="ops-alerts">
            <article className="ops-card">
              <span>{locale === "tr" ? "Resmi watch" : "Official watch"}</span>
              <strong>{telemetry.officialWatchHeadline ?? (locale === "tr" ? "Aktif watch yok" : "No active watch")}</strong>
            </article>
            <article className="ops-card">
              <span>{locale === "tr" ? "Resmi alert/warning" : "Official alert/warning"}</span>
              <strong>{telemetry.officialAlertHeadline ?? (locale === "tr" ? "Aktif alert yok" : "No active alert")}</strong>
            </article>
          </div>

          <div className="source-status-grid">
            {sourceStatuses.map((status) => (
              <article key={status.id} className={`source-card source-${status.state}`}>
                <div className="source-head">
                  <h3>{status.label}</h3>
                  <span className={`source-pill source-pill-${status.state}`}>{statusLabel(status.state, locale)}</span>
                </div>
                <p>{status.detail}</p>
                {status.href ? (
                  <a href={status.href} target="_blank" rel="noreferrer">
                    {status.href}
                  </a>
                ) : null}
              </article>
            ))}
          </div>
        </>
      ) : (
        <p className="empty-state">{locale === "tr" ? "Canli operasyon paneli icin telemetri bekleniyor." : "Waiting for telemetry to populate live operations."}</p>
      )}
    </section>
  );
}
