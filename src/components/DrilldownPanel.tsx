import type { CityDrilldown } from "../lib/dashboardInsights";
import { detailForInfrastructure, labelForInfrastructure } from "../lib/dashboardInsights";
import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";

interface DrilldownPanelProps {
  cityOptions: Array<{ id: string; label: string }>;
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
  drilldown: CityDrilldown | null;
  locale: AppLocale;
}

export function DrilldownPanel({
  cityOptions,
  selectedCityId,
  onSelectCity,
  drilldown,
  locale,
}: DrilldownPanelProps) {
  const copy = uiText[locale];

  return (
    <section className="panel split-panel drilldown-panel">
      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">{copy.drilldown}</span>
            <h2>{copy.drilldownTitle}</h2>
          </div>
        </div>

        <label className="select-shell">
          <span>{copy.selectCity}</span>
          <select value={selectedCityId} onChange={(event) => onSelectCity(event.target.value)}>
            {cityOptions.map((city) => (
              <option key={city.id} value={city.id}>
                {city.label}
              </option>
            ))}
          </select>
        </label>

        {drilldown ? (
          <article className="city-card">
            <div className="city-risk">
              <h3>{drilldown.city}</h3>
              <strong>{drilldown.riskPercent}%</strong>
            </div>
            <p>{drilldown.detail}</p>
            <div className="city-meta">
              <span>{copy.regionRisk}: {drilldown.region}</span>
            </div>
            <div className="city-effects">
              <h4>{copy.affectedSystems}</h4>
              <ul>
                {drilldown.impacts.map((impact) => (
                  <li key={impact}>{impact}</li>
                ))}
              </ul>
            </div>
          </article>
        ) : (
          <p className="empty-state">{copy.drilldownEmpty}</p>
        )}
      </div>

      <div>
        <div className="panel-header">
          <div>
            <span className="eyebrow">{copy.infrastructure}</span>
            <h2>{copy.infrastructureTitle}</h2>
          </div>
        </div>
        <div className="infra-list">
          {drilldown?.infrastructures.length ? (
            drilldown.infrastructures.map((point) => (
              <article key={point.id} className={`infra-card infra-${point.category}`}>
                <h3>{labelForInfrastructure(point, locale)}</h3>
                <p>{detailForInfrastructure(point, locale)}</p>
              </article>
            ))
          ) : (
            <p className="empty-state">{copy.noInfrastructure}</p>
          )}
        </div>
      </div>
    </section>
  );
}
