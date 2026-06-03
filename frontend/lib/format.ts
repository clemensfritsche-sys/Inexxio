/**
 * All date/time formatting uses Intl.DateTimeFormat with user locale.
 * DB stores UTC; frontend converts to local time here.
 */

export function formatDateTime(utcString: string, locale = "de-CH"): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }).format(new Date(utcString));
}

export function formatDate(utcString: string, locale = "de-CH"): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }).format(new Date(utcString));
}

export function formatCurrency(amount: number, currency = "CHF", locale = "de-CH"): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(value: number, locale = "de-CH"): string {
  return new Intl.NumberFormat(locale).format(value);
}

export function formatObjectId(id: number): string {
  return id.toString().padStart(9, "0");
}
