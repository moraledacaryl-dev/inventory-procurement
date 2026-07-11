const numberFormatterCache = new Map<string, Intl.NumberFormat>();
const dateFormatterCache = new Map<string, Intl.DateTimeFormat>();

function numberFormatter(locale: string, options: Intl.NumberFormatOptions) {
  const key = `${locale}:${JSON.stringify(options)}`;
  let formatter = numberFormatterCache.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(locale, options);
    numberFormatterCache.set(key, formatter);
  }
  return formatter;
}

function dateFormatter(locale: string, options: Intl.DateTimeFormatOptions) {
  const key = `${locale}:${JSON.stringify(options)}`;
  let formatter = dateFormatterCache.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(locale, options);
    dateFormatterCache.set(key, formatter);
  }
  return formatter;
}

export function asNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function formatMoney(value: unknown, currency = "PHP", locale = "en-PH"): string {
  return numberFormatter(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(asNumber(value));
}

export function formatQuantity(value: unknown, maximumFractionDigits = 4, locale = "en-PH"): string {
  return numberFormatter(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(asNumber(value));
}

export function formatPercent(value: unknown, maximumFractionDigits = 1, locale = "en-PH"): string {
  return numberFormatter(locale, {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(asNumber(value));
}

export function formatDate(value: string | Date | null | undefined, locale = "en-PH"): string {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return dateFormatter(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "Asia/Manila",
  }).format(date);
}

export function formatDateTime(value: string | Date | null | undefined, locale = "en-PH"): string {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return dateFormatter(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Manila",
  }).format(date);
}
