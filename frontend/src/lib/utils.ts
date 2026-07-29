import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Betrag im Schweizer Zahlenformat, 2 Nachkommastellen – OHNE Währung («12'345.60»).
// EINE Formatier-Wahrheit (vorher in 7 Komponenten je eine eigene Kopie).
export function formatAmount(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—';
  return Number(v).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Betrag MIT Währungspräfix («CHF 12'345.60»).
export function formatMoney(amount: string | number | null | undefined, currency: string): string {
  if (amount == null || amount === '') return '—';
  return `${currency} ${formatAmount(amount)}`;
}

// ISO-Timestamp → Schweizer Datum («03.07.2026»), leer → «—».
export function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

// Relative Zeitangabe («gerade eben», «vor 2 Std», «vor 1 Tag») – für Detail-Kacheln.
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return 'gerade eben';
  const m = Math.floor(s / 60);
  if (m < 60) return `vor ${m} Min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `vor ${h} Std`;
  const d = Math.floor(h / 24);
  if (d < 30) return d === 1 ? 'vor 1 Tag' : `vor ${d} Tagen`;
  const mo = Math.floor(d / 30);
  if (mo < 12) return mo === 1 ? 'vor 1 Monat' : `vor ${mo} Monaten`;
  const y = Math.floor(d / 365);
  return y === 1 ? 'vor 1 Jahr' : `vor ${y} Jahren`;
}

/**
 * Anzeigename einer Person – **dieselbe Regel wie im Backend** (`UserProfile.display_name`):
 * Firma → «Vorname Nachname» → E-Mail. Bei einem Lieferanten ist die Firma der Name, unter
 * dem man bestellt; der Ansprechpartner steht am Datensatz (Notiz #227). Vorher wich das
 * Frontend hier ab und zeigte die Person, wo das Backend die Firma zeigte.
 */
export function userDisplayName(user: {
  company_name?: string | null; first_name?: string | null; last_name?: string | null; email: string;
}): string {
  const full = [user.first_name, user.last_name].filter(Boolean).join(' ');
  return user.company_name?.trim() || full || user.email.split('@')[0];
}
