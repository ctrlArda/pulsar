import { useEffect, useMemo, useState } from "react";
import { formatEta } from "../lib/format";

export function useEtaCountdown(observedAt: string | null, etaSeconds: number | null): string {
  const deadline = useMemo(() => {
    if (!observedAt || !etaSeconds) {
      return null;
    }
    return new Date(observedAt).getTime() + etaSeconds * 1000;
  }, [observedAt, etaSeconds]);

  const [remaining, setRemaining] = useState<number | null>(etaSeconds);

  useEffect(() => {
    if (!deadline) {
      setRemaining(etaSeconds);
      return;
    }

    const sync = () => {
      const seconds = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      setRemaining(seconds);
    };

    sync();
    const timer = window.setInterval(sync, 1000);
    return () => window.clearInterval(timer);
  }, [deadline, etaSeconds]);

  return formatEta(remaining);
}
