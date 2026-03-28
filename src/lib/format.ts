function resolveLocale(locale?: string): string {
  if (!locale) {
    return "tr-TR";
  }
  return locale === "en" ? "en-US" : locale === "tr" ? "tr-TR" : locale;
}

export function formatSigned(value: number, digits = 1, locale?: string): string {
  const formatter = new Intl.NumberFormat(resolveLocale(locale), {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return `${value > 0 ? "+" : ""}${formatter.format(value)}`;
}

export function formatCompact(value: number, digits = 0, locale?: string): string {
  return new Intl.NumberFormat(resolveLocale(locale), {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number | null, locale?: string): string {
  if (value === null) {
    return resolveLocale(locale) === "en-US" ? "Preparing" : "Hazirlaniyor";
  }
  return `%${formatCompact(value, 0, locale)}`;
}

export function formatEta(etaSeconds: number | null): string {
  if (!etaSeconds || etaSeconds <= 0) {
    return "00:00";
  }
  const minutes = Math.floor(etaSeconds / 60);
  const seconds = Math.floor(etaSeconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatTimestamp(value: string, locale?: string): string {
  return new Intl.DateTimeFormat(resolveLocale(locale), {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "short",
  }).format(new Date(value));
}
