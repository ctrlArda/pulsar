import type { EvidenceItem } from "../lib/dashboardInsights";
import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";

interface EvidencePanelProps {
  items: EvidenceItem[];
  locale: AppLocale;
  onDownloadJson: () => void;
  onDownloadTxt: () => void;
}

export function EvidencePanel({ items, locale, onDownloadJson, onDownloadTxt }: EvidencePanelProps) {
  const copy = uiText[locale];

  return (
    <section className="panel evidence-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{copy.evidence}</span>
          <h2>{copy.evidenceTitle}</h2>
        </div>
        <div className="report-actions">
          <button type="button" onClick={onDownloadJson}>
            {copy.downloadJson}
          </button>
          <button type="button" onClick={onDownloadTxt}>
            {copy.downloadTxt}
          </button>
        </div>
      </div>

      {items.length ? (
        <div className="evidence-grid">
          {items.map((item) => (
            <article key={item.id} className="evidence-card">
              <span>{copy.source}: {item.source}</span>
              <strong>{item.value}</strong>
              <p>{item.detail}</p>
              {item.href ? (
                <a href={item.href} target="_blank" rel="noreferrer">
                  {item.href}
                </a>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">{copy.evidenceEmpty}</p>
      )}
    </section>
  );
}
