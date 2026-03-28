import { formatCompact } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import type { KpTrendPoint } from "../types/helioguard";

interface KpTimelineProps {
  points: KpTrendPoint[];
  locale: AppLocale;
}

function severityClass(point: KpTrendPoint) {
  if (point.estimatedKp >= 7) {
    return "critical";
  }
  if (point.estimatedKp >= 5) {
    return "warning";
  }
  return "watch";
}

export function KpTimeline({ points, locale }: KpTimelineProps) {
  const recent = points.slice(-12);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{locale === "tr" ? "Kp izlemesi" : "Kp monitor"}</span>
          <h2>{locale === "tr" ? "Noaa kor noktasini kapatan son trend" : "Trend closing NOAA's blind spot"}</h2>
        </div>
      </div>
      <div className="kp-track">
        {recent.map((point) => (
          <div key={point.timeTag} className="kp-column">
            <div
              className={`kp-bar kp-${severityClass(point)}`}
              style={{ height: `${Math.max(12, point.estimatedKp * 12)}px` }}
            />
            <strong>{formatCompact(point.estimatedKp, 1, locale)}</strong>
            <span>{new Date(point.timeTag).toLocaleTimeString(locale === "tr" ? "tr-TR" : "en-US", { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
