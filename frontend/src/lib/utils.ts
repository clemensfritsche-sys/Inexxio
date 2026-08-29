import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Betrag im Schweizer Zahlenformat, 2 Nachkommastellen – OHNE Währung («12'345.60»).
 * EINE Formatier-Wahrheit (vorher in 7 Komponenten je eine eigene Kopie).
 *
 * **Der Tausender-Trenner wird festgeschrieben.** `toLocaleString('de-CH')` liefert je
 * nach ICU-Fassung ein typografisches `’` (U+2019, so im Browser) oder ein gerades `'`
 * (U+0027, so in Node) – gemessen, nicht vermutet. Das Design-System schreibt den
 * geraden fest (`9'999 CHF`), und dieselbe Zahl darf nicht je nach Laufzeit anders
 * aussehen: server- und clientseitig gerendert ergäbe das zwei verschiedene Texte an
 * derselben Stelle (React meldet es als Hydrations-Fehler und wirft die Seite weg).
 */
export function formatAmount(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—';
  return Number(v)
    .toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .replace(/\u2019/g, "'");
}

// ISO-Timestamp → Schweizer Datum («03.07.2026»), leer → «—».
export function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

/** Datum **und** Uhrzeit («31.07.26, 21:52») – die Form der Wer/Wann-Angaben. */
export function localDateTime(iso: string | null | undefined): string | undefined {
  return iso ? new Date(iso).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' }) : undefined;
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
  // EINE Regel für ALLE Rollen (Notiz #291): «Vorname Nachname» → Firma → E-Mail. Immer der
  // Name der Person im Datensatz, nicht der Firmenname (Firma nur als Rückfall). Spiegelt
  // ``UserProfile.display_name`` im Backend.
  const full = [user.first_name, user.last_name].filter(Boolean).join(' ');
  return full || user.company_name?.trim() || user.email.split('@')[0];
}

/**
 * **Die EINE Schreibweise einer Objektnummer**: neunstellig, führende Nullen, **ohne**
 * Tausender-Trennung (Notiz #263). Eine Objektnummer ist ein Bezeichner, keine Menge –
 * Trennzeichen laden zum Rechnen ein und machen sie schwerer vorlesbar/suchbar.
 */
export function formatObjectId(id: number | null | undefined): string {
  if (!id) return '—';
  return String(id).padStart(9, '0');
}
