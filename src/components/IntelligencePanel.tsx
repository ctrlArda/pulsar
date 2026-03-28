import type { AlarmDriver } from "../lib/dashboardInsights";
import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";

interface IntelligencePanelProps {
  drivers: AlarmDriver[];
  aiSummary: string;
  locale: AppLocale;
}

export function IntelligencePanel({ drivers, aiSummary, locale }: IntelligencePanelProps) {
  const copy = uiText[locale];

  return (
    <section className="panel split-panel intelligence-panel">
      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">{copy.drivers}</span>
            <h2>{copy.driversTitle}</h2>
          </div>
        </div>
        <div className="drivers-list">
          {drivers.map((driver) => (
            <article key={driver.id} className="driver-card">
              <div className="driver-head">
                <h3>{driver.label}</h3>
                <strong>{driver.score}%</strong>
              </div>
              <div className="driver-bar">
                <span style={{ width: `${driver.score}%` }} />
              </div>
              <p>{driver.detail}</p>
            </article>
          ))}
        </div>
      </div>

      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">{copy.aiExplain}</span>
            <h2>{copy.aiExplainTitle}</h2>
          </div>
        </div>
        <div className="ai-explain-card">
          <p>{aiSummary}</p>
          <ul>
            {drivers.slice(0, 3).map((driver) => (
              <li key={driver.id}>
                <strong>{driver.label}</strong>
                <span>{driver.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
