import { formatCompact, formatPercent } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import type { TelemetrySnapshot } from "../types/helioguard";

interface ScientificPanelProps {
  telemetry: TelemetrySnapshot | null;
  locale: AppLocale;
}

function formatDuration(seconds: number | null, locale: AppLocale): string {
  if (seconds === null || seconds <= 0) {
    return "--";
  }
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours > 0) {
    return locale === "tr" ? `${hours} sa ${minutes} dk` : `${hours}h ${minutes}m`;
  }
  return locale === "tr" ? `${minutes} dk` : `${minutes}m`;
}

function formatFreshness(seconds: number | null, locale: AppLocale, archiveMode: boolean): string {
  if (seconds === null) {
    return "--";
  }
  if (seconds === 0 && archiveMode) {
    return locale === "tr" ? "Arsiv tekrar oynatimi" : "Archive replay";
  }
  if (seconds < 60) {
    return locale === "tr" ? `${seconds} sn` : `${seconds}s`;
  }
  return locale === "tr" ? `${Math.round(seconds / 60)} dk` : `${Math.round(seconds / 60)}m`;
}

export function ScientificPanel({ telemetry, locale }: ScientificPanelProps) {
  return (
    <section className="panel scientific-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{locale === "tr" ? "Bilimsel guven" : "Scientific confidence"}</span>
          <h2>{locale === "tr" ? "Belirsizlik, varis penceresi ve dogrulama" : "Uncertainty, arrival window, and validation"}</h2>
        </div>
      </div>

      {telemetry ? (
        <>
          <div className="science-grid">
            <article className="science-card">
              <span>{locale === "tr" ? "Varis penceresi" : "Arrival window"}</span>
              <strong>{`${formatDuration(telemetry.etaWindowStartSeconds, locale)} - ${formatDuration(telemetry.etaWindowEndSeconds, locale)}`}</strong>
              <p>{locale === "tr" ? `Merkez ETA ${formatDuration(telemetry.etaSeconds, locale)}.` : `Median ETA ${formatDuration(telemetry.etaSeconds, locale)}.`}</p>
            </article>

            <article className="science-card">
              <span>{locale === "tr" ? "Geomanyetik bant" : "Geomagnetic band"}</span>
              <strong>{telemetry.stormScaleBand}</strong>
              <p>{locale === "tr" ? `Tahmini Kp ${formatCompact(telemetry.estimatedKp, 1, locale)} etrafinda beklenen sinif araligi.` : `Expected storm class range around estimated Kp ${formatCompact(telemetry.estimatedKp, 1, locale)}.`}</p>
            </article>

            <article className="science-card">
              <span>{locale === "tr" ? "Fizik risk bandi" : "Physics risk band"}</span>
              <strong>{`${formatPercent(telemetry.riskBandLow, locale)} - ${formatPercent(telemetry.riskBandHigh, locale)}`}</strong>
              <p>{locale === "tr" ? "L1 telemetrisi ve fizik kurallarindan uretilen belirsizlik araligi." : "Uncertainty range derived from L1 telemetry and physics rules."}</p>
            </article>

            <article className="science-card">
              <span>{locale === "tr" ? "ML risk bandi" : "ML risk band"}</span>
              <strong>
                {telemetry.mlRiskBandLow !== null && telemetry.mlRiskBandHigh !== null
                  ? `${formatPercent(telemetry.mlRiskBandLow, locale)} - ${formatPercent(telemetry.mlRiskBandHigh, locale)}`
                  : "--"}
              </strong>
              <p>
                {telemetry.mlRiskPercent !== null
                  ? locale === "tr"
                    ? `+${telemetry.mlLeadTimeMinutes ?? 60} dk tahmini icin hata bandi.`
                    : `Error band for the +${telemetry.mlLeadTimeMinutes ?? 60}m forecast.`
                  : locale === "tr"
                    ? "Model mevcut degil."
                    : "Model unavailable."}
              </p>
            </article>

            <article className="science-card">
              <span>{locale === "tr" ? "Tahmin guveni" : "Forecast confidence"}</span>
              <strong>{formatPercent(telemetry.forecastConfidencePercent, locale)}</strong>
              <p>
                {locale === "tr"
                  ? `Kaynak kapsami ${formatPercent(telemetry.sourceCoveragePercent, locale)} | Veri tazeligi ${formatFreshness(telemetry.dataFreshnessSeconds, locale, telemetry.mode === "archive")}`
                  : `Source coverage ${formatPercent(telemetry.sourceCoveragePercent, locale)} | Data freshness ${formatFreshness(telemetry.dataFreshnessSeconds, locale, telemetry.mode === "archive")}`}
              </p>
            </article>

            <article className="science-card">
              <span>{locale === "tr" ? "Model dogrulama" : "Model validation"}</span>
              <strong>{telemetry.validationMae !== null ? `MAE ${formatCompact(telemetry.validationMae, 2, locale)}` : "--"}</strong>
              <p>
                {telemetry.validationRows !== null
                  ? locale === "tr"
                    ? `${formatCompact(telemetry.validationRows, 0, locale)} ornek | ${telemetry.validationHorizonMinutes ?? 60} dk ufuk`
                    : `${formatCompact(telemetry.validationRows, 0, locale)} samples | ${telemetry.validationHorizonMinutes ?? 60}m horizon`
                  : locale === "tr"
                    ? "Backtest metrikleri yuklenemedi."
                    : "Backtest metrics unavailable."}
              </p>
            </article>
          </div>

          <p className="science-note">
            {locale === "tr"
              ? "Bu panel tek bir kesin sayi yerine operasyonel olarak savunulabilir aralik, guven ve gecmis dogrulama metriklerini gosterir."
              : "This panel shows operationally defensible ranges, confidence, and historical validation metrics instead of a single deterministic number."}
          </p>
        </>
      ) : (
        <p className="empty-state">{locale === "tr" ? "Bilimsel guven paneli icin telemetri bekleniyor." : "Waiting for telemetry to populate scientific confidence."}</p>
      )}
    </section>
  );
}
