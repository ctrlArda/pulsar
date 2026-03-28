import type { TimelineEvent } from "../lib/dashboardInsights";
import type { AppLocale } from "../lib/i18n";
import { uiText } from "../lib/i18n";

interface TimelinePanelProps {
  events: TimelineEvent[];
  locale: AppLocale;
}

export function TimelinePanel({ events, locale }: TimelinePanelProps) {
  const copy = uiText[locale];

  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{copy.timeline}</span>
          <h2>{copy.timelineTitle}</h2>
        </div>
      </div>
      {events.length ? (
        <div className="timeline-list">
          {events.map((event) => (
            <article key={event.id} className={`timeline-item timeline-${event.status}`}>
              <span className="timeline-dot" />
              <div>
                <h3>{event.title}</h3>
                <p>{event.detail}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">{copy.timelineEmpty}</p>
      )}
    </section>
  );
}
