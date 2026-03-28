import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";
import type { RegionRanking } from "../lib/dashboardInsights";

interface TopRegionsPanelProps {
  regions: RegionRanking[];
  locale: AppLocale;
}

export function TopRegionsPanel({ regions, locale }: TopRegionsPanelProps) {
  const copy = uiText[locale];

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{copy.ranking}</span>
          <h2>{copy.rankingTitle}</h2>
        </div>
      </div>
      {regions.length ? (
        <div className="ranking-list">
          {regions.map((region, index) => (
            <article key={region.id} className="ranking-card">
              <span className="ranking-index">#{index + 1}</span>
              <div>
                <h3>{region.label}</h3>
                <p>{region.detail}</p>
              </div>
              <div className="ranking-metrics">
                <strong>{region.riskPercent}%</strong>
                <span>{copy.confidence}: {region.confidence}%</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">{copy.topRegionsEmpty}</p>
      )}
    </section>
  );
}
