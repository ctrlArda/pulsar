import { useEtaCountdown } from "../hooks/useEtaCountdown";
import type { AppLocale } from "../lib/i18n";

interface EtaCountdownProps {
  observedAt: string | null;
  etaSeconds: number | null;
  locale: AppLocale;
}

export function EtaCountdown({ observedAt, etaSeconds, locale }: EtaCountdownProps) {
  const countdown = useEtaCountdown(observedAt, etaSeconds);

  return (
    <div className="eta-card">
      <span className="eyebrow">{locale === "tr" ? "Medyan varis sayaci" : "Median arrival countdown"}</span>
      <strong>{countdown}</strong>
      <p>{locale === "tr" ? "L1 nowcastindan uretilen merkez varis tahmini; belirsizlik panelde aralik olarak verilir." : "Median arrival estimate from the L1 nowcast; the uncertainty band is shown in the panel."}</p>
    </div>
  );
}
