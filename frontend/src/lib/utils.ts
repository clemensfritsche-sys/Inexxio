import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Betrag im Schweizer Zahlenformat – OHNE Währung («12'345.60»).
 * EINE Formatier-Wahrheit (vorher in 7 Komponenten je eine eigene Kopie).
 *
 * ►►► **Die Nachkommastellen kommen von der WÄHRUNG** (ISO 4217 «minor units»). ◄◄◄
 *
 * Fast alle haben zwei – und darum stand hier eine feste `2`, und niemand hätte je
 * gemerkt, dass sie falsch ist: **JPY und KRW haben null**, **KWD hat drei**. Ein
 * Yen-Betrag mit zwei Nachkommastellen ist kein Schönheitsfehler, sondern ein Betrag,
 * den es nicht gibt. Der Wert reist mit den Daten (`VoucherEmbed.currency_decimals`, aus
 * `domain/currency`); zwei ist die Vorgabe für alles, was keine Währung nennt.
 *
 * **Der Tausender-Trenner wird festgeschrieben.** `toLocaleString('de-CH')` liefert je
 * nach ICU-Fassung ein typografisches `’` (U+2019, so im Browser) oder ein gerades `'`
 * (U+0027, so in Node) – gemessen, nicht vermutet. Das Design-System schreibt den
 * geraden fest (`9'999 CHF`), und dieselbe Zahl darf nicht je nach Laufzeit anders
 * aussehen: server- und clientseitig gerendert ergäbe das zwei verschiedene Texte an
 * derselben Stelle (React meldet es als Hydrations-Fehler und wirft die Seite weg).
 */
export function formatAmount(v: string | number | null | undefined,
                             decimals = 2): string {
  if (v == null || v === '') return '—';
  return swiss(Number(v), decimals, decimals);
}

/**
 * Eine **Messgrösse** (Gewicht, Länge …): höchstens `maxDecimals` Nachkommastellen,
 * keine aufgefüllten Nullen – mit demselben festgeschriebenen Trenner wie `formatAmount`.
 */
export function formatNumber(v: string | number, maxDecimals = 3): string {
  return swiss(Number(v), 0, maxDecimals);
}

/** Die eine Stelle, an der eine Zahl ihre Schweizer Schreibweise bekommt. */
function swiss(n: number, min: number, max: number): string {
  return n
    .toLocaleString('de-CH', { minimumFractionDigits: min, maximumFractionDigits: max })
    .replace(/\u2019/g, "'");
}

// Datum und Uhrzeit stehen in `lib/when` (#992) – ein Wächter verbietet jede zweite
// Datums-Formatierung daneben.

/**
 * Anzeigename einer Person – **dieselbe Regel wie im Backend** (`UserProfile.display_name`,
 * Notiz #291): «Vorname Nachname» → E-Mail, für alle Rollen. Die Firma ist ein eigener
 * Datensatz mit eigenem Namen und nie der Name einer Person.
 */
export function personFullName(user: { first_name?: string | null; last_name?: string | null }): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ');
}

export function userDisplayName(user: {
  first_name?: string | null; last_name?: string | null; email: string;
}): string {
  return personFullName(user) || user.email;
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
