import { formatTimestamp } from "../lib/format";
import type { AppLocale } from "../lib/i18n";
import { translateGeneratedText } from "../lib/i18n";
import type { TerminalLine } from "../types/helioguard";

interface LiveTerminalProps {
  lines: TerminalLine[];
  locale: AppLocale;
}

export function LiveTerminal({ lines, locale }: LiveTerminalProps) {
  return (
    <section className="panel terminal-panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{locale === "tr" ? "Canli terminal" : "Live terminal"}</span>
          <h2>{locale === "tr" ? "Ham uzay verisi akisi" : "Raw space-weather stream"}</h2>
        </div>
      </div>
      <div className="terminal-window">
        {lines.length ? (
          lines.map((line) => (
            <div key={`${line.at}-${line.source}-${line.message}`} className={`terminal-line terminal-${line.level}`}>
              <span>{formatTimestamp(line.at, locale)}</span>
              <strong>{line.source}</strong>
              <p>{translateGeneratedText(line.message, locale)}</p>
            </div>
          ))
        ) : (
          <p className="empty-state">{locale === "tr" ? "Worker log akisi baslatiliyor." : "Worker log stream is starting."}</p>
        )}
      </div>
    </section>
  );
}
