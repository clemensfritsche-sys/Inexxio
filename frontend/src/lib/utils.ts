import { clsx, type ClassValue } from 'clsx';

/** Klassen zusammensetzen (Bedingungen, Listen) – ohne Mischen: wer zwei widersprüchliche
 *  Klassen setzt, setzt eine zu viel. */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

/**
 * Betrag im Schweizer Zahlenformat – OHNE Währung («12'345.60»), EINE Formatier-Stelle.
 *
 * ►►► **Die Nachkommastellen kommen von der WÄHRUNG** (ISO 4217 «minor units») ◄◄◄ – JPY
 * null, KWD drei; der Wert reist mit den Daten (`VoucherEmbed.currency_decimals`), Vorgabe zwei.
 *
 * **Der Tausender-Trenner ist das gerade `'`** – festgeschrieben, weil ICU je nach Laufzeit
 * `’` oder `'` liefert (sonst Hydrations-Fehler).
 */
export function formatAmount(v: string | number | null | undefined,
                             decimals = 2): string {
  if (v == null || v === '') return '—';
  return swiss(Number(v), decimals, decimals);
}

/** Die eine Stelle, an der eine Zahl ihre Schweizer Schreibweise bekommt. */
function swiss(n: number, min: number, max: number): string {
  return n
    .toLocaleString('de-CH', { minimumFractionDigits: min, maximumFractionDigits: max })
    .replace(/\u2019/g, "'");
}

// Datum und Uhrzeit stehen in `lib/when`.

/** Anzeigename einer Person – **dieselbe Regel wie im Backend** (`UserProfile.display_name`):
 *  «Vorname Nachname» → E-Mail. Eine Firma ist nie der Name einer Person. */
export function personFullName(user: { first_name?: string | null; last_name?: string | null }): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ');
}

export function userDisplayName(user: {
  first_name?: string | null; last_name?: string | null; email: string;
}): string {
  return personFullName(user) || user.email;
}

/** **Die EINE Schreibweise einer Objektnummer**: neunstellig, führende Nullen, **ohne**
 *  Tausender-Trennung – ein Bezeichner, keine Menge. */
export function formatObjectId(id: number | null | undefined): string {
  if (!id) return '—';
  return String(id).padStart(9, '0');
}
