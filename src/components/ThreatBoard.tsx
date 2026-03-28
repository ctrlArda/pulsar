import type { AppLocale } from "../lib/i18n";
import { translateGeneratedText } from "../lib/i18n";
import type { CrisisAlert, ThreatImpact } from "../types/helioguard";

interface ThreatBoardProps {
  alert: CrisisAlert | null;
  locale: AppLocale;
}

function severityLabel(threat: ThreatImpact, locale: AppLocale) {
  switch (threat.severity) {
    case "critical":
      return locale === "tr" ? "Kritik" : "Critical";
    case "high":
      return locale === "tr" ? "Yuksek" : "High";
    case "medium":
      return locale === "tr" ? "Orta" : "Medium";
    default:
      return locale === "tr" ? "Dusuk" : "Low";
  }
}

export function ThreatBoard({ alert, locale }: ThreatBoardProps) {
  return (
    <section className="panel split-panel">
      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">{locale === "tr" ? "Hasar matrisi" : "Impact matrix"}</span>
            <h2>{locale === "tr" ? "Hangi cihazlar etki alacak" : "Which systems take impact"}</h2>
          </div>
        </div>
        <div className="threat-grid">
          {(alert?.impactedHardware ?? []).map((threat) => (
            <article key={threat.id} className={`threat-card threat-${threat.severity}`}>
              <span className="threat-severity">{severityLabel(threat, locale)}</span>
              <h3>{translateGeneratedText(threat.title, locale)}</h3>
              <p>{translateGeneratedText(threat.rationale, locale)}</p>
              <ul>
                {threat.affectedSystems.map((system) => (
                  <li key={system}>{translateGeneratedText(system, locale)}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>

      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">SOP</span>
            <h2>{locale === "tr" ? "Acil durum protokolleri" : "Emergency protocols"}</h2>
          </div>
        </div>
        <div className="sop-list">
          {(alert?.sopActions ?? []).map((item) => (
            <article key={`${item.sector}-${item.action}`}>
              <span>{translateGeneratedText(item.sector, locale)}</span>
              <p>{translateGeneratedText(item.action, locale)}</p>
            </article>
          ))}
          {!alert?.sopActions.length ? <p className="empty-state">{locale === "tr" ? "Aktif SOP icin alarm kaydi bekleniyor." : "Waiting for an active alert to populate SOP actions."}</p> : null}
        </div>
      </div>
    </section>
  );
}
