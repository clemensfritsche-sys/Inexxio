/**
 * **WANN — die eine Datums-Ausgabe des Hauses.** Jede Datums-Anzeige läuft hier durch; ein
 * Wächter verbietet jede zweite Formatierung.
 *
 * - **`when()` – «wann war das?»**: die Auskunft («gerade eben», «vor 3 Stunden»,
 *   «Gestern», danach das Datum).
 * - **`day()` – «welcher Tag steht auf dem Papier?»**: die Tatsache (Beleg, MWSTG Art. 26).
 *   Zwei Formen **einer** Regel, ein Namensstamm.
 * - **Die volle Tatsache steht IMMER im Hover** (`whenTitle`, `formatWhen`).
 * - **Die Wörter stehen HIER, nicht im ICU** – sonst sähe dieselbe Angabe je nach Laufzeit
 *   anders aus («Sep.»/«Sept.»).
 */

/** Die Monatskürzel – festgeschrieben, siehe oben. */
const MONTHS = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni',
                'Juli', 'Aug.', 'Sep.', 'Okt.', 'Nov.', 'Dez.'] as const;

/** Was dasteht, wo es nichts gibt – dieselbe Antwort wie überall im ERP. */
export const NOTHING = '—';

/** Ab hier ist «vor N Tagen» keine Auskunft mehr, sondern eine Rechenaufgabe. */
const NEAR_DAYS = 7;

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** «gerade eben» – darunter ist jede Zahl eine erfundene Genauigkeit. */
const JUST_NOW = 'gerade eben';

/** Singular und Plural als **Angabe**, nicht als Rechnung – deutsche Beugung ist keine
 *  Zeichenkettenoperation. */
const MINUTES: [string, string] = ['Minute', 'Minuten'];
const HOURS: [string, string] = ['Stunde', 'Stunden'];
const DAYS: [string, string] = ['Tag', 'Tagen'];

/** «vor 3 Stunden» ↔ «in 3 Stunden» – die Richtung sagt das Vorzeichen. */
function ago(n: number, [one, many]: [string, string], past: boolean): string {
  const word = n === 1 ? one : many;
  return past ? `vor ${n} ${word}` : `in ${n} ${word}`;
}

function parse(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  // Ein reines Datum («2026-09-13») ist ein **Kalendertag**, keine UTC-Mitternacht: als
  // solche gelesen wäre es in der Schweiz der Vortag um 02:00.
  const d = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Wie viele **Kalendertage** liegen dazwischen? Gestern 23:50 ist «gestern», auch wenn
 *  es sieben Stunden her ist – 24-Stunden-Blöcke beantworten eine andere Frage. */
function calendarDays(from: Date, to: Date): number {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** **Der Tag, wie er auf dem Papier steht** – «13.09.2026». Ohne Wert: «—». */
export function day(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return NOTHING;
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/**
 * **Tag und Uhrzeit** – «13.09.2026, 17:58». Die volle Tatsache, wie sie in den Hover
 * gehört. Ohne Wert: `undefined` (dann gibt es keinen Hover, statt eines leeren).
 */
export function whenTitle(value: string | Date | null | undefined): string | undefined {
  const d = parse(value);
  if (!d) return undefined;
  return `${day(d)}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * ►►► **«Wann war das?» – die Aussage, nicht die Zahl.** ◄◄◄
 *
 * ==================  ====================================================
 * unter einer Minute  `gerade eben`
 * unter einer Stunde  `vor 12 Minuten`
 * unter einem Tag     `vor 3 Stunden`
 * gestern             `Gestern`
 * 2–6 Tage her        `vor 3 Tagen`
 * älter, dieses Jahr  `13. Sep.` – die Jahreszahl sagt nichts Neues
 * anderes Jahr        `13. Sep. 2025`
 * morgen              `Morgen`
 * 2–6 Tage voraus     `in 5 Tagen`
 * weiter voraus       `13. Sep.` bzw. `13. Sep. 2027`
 * ==================  ====================================================
 *
 * Die genauere Aussage gewinnt («vor 20 Stunden» vor «Gestern»). **Ein reines Datum kennt
 * keine Uhrzeit** – es sagt «Heute» und überspringt die Stunden. `now` macht die Funktion rein.
 */
export function when(value: string | Date | null | undefined,
                     now: Date = new Date()): string {
  const d = parse(value);
  if (!d) return NOTHING;
  const dayOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const gap = now.getTime() - d.getTime();
  const past = gap >= 0;
  const abs = Math.abs(gap);
  if (!dayOnly && abs < MINUTE) return JUST_NOW;
  if (!dayOnly && abs < HOUR) return ago(Math.floor(abs / MINUTE), MINUTES, past);
  if (!dayOnly && abs < DAY) return ago(Math.floor(abs / HOUR), HOURS, past);
  const n = calendarDays(now, d);
  if (n === 0) return 'Heute';
  if (n === -1) return 'Gestern';
  if (n === 1) return 'Morgen';
  if (n < 0 && n > -NEAR_DAYS) return ago(-n, DAYS, true);
  if (n > 0 && n < NEAR_DAYS) return ago(n, DAYS, false);
  const short = `${d.getDate()}. ${MONTHS[d.getMonth()]}`;
  return d.getFullYear() === now.getFullYear() ? short : `${short} ${d.getFullYear()}`;
}

/**
 * **Der Kalendertag eines Zeitpunkts als Aussage** – «Heute», «Gestern», «13. Sep.»; die
 * Stunden-Kaskade gilt hier nicht, gefragt ist der Tag (z. B. die Trennzeile eines
 * Verlaufs). Gerechnet wird in der Ortszeit, wie bei `day()`.
 */
export function whenDay(value: string | Date | null | undefined,
                        now: Date = new Date()): string {
  const d = parse(value);
  if (!d) return NOTHING;
  return when(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, now);
}

/**
 * **Beides in einem Zug** – die Aussage und die Tatsache für den Hover.
 *
 * ```tsx
 * const w = formatWhen(entry.created_at);
 * <span data-tip={w.title}>{w.text}</span>
 * ```
 */
export function formatWhen(value: string | Date | null | undefined,
                           now: Date = new Date()): { text: string; title?: string } {
  return { text: when(value, now), title: whenTitle(value) };
}

/**
 * ►►► **ZEIT zuerst, dann was passiert ist** ◄◄◄ – die Form einer Aussage über einen Vorgang.
 *
 * ```tsx
 * const w = happened(quote.sent_at, 'offeriert');   // «Vor 3 Tagen offeriert»
 * ```
 *
 * Der erste Buchstabe wird gross (Satzanfang).
 */
export function happened(value: string | Date | null | undefined, what: string,
                         now: Date = new Date()): { text: string; title?: string } {
  const said = when(value, now);
  const text = said === NOTHING
    ? what
    : `${said.charAt(0).toUpperCase()}${said.slice(1)} ${what}`;
  return { text, title: whenTitle(value) };
}


// ─── Kalendertage als Text (Zeiterfassung) ───────────────────────────────────────────

const WEEKDAYS_LONG = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const MONTHS_LONG = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
  'September', 'Oktober', 'November', 'Dezember'];

/** «Freitag, 23.10.2026» – der Titel eines Tages. */
export function dayTitle(value: string | Date | null | undefined): string {
  const d = parse(value);
  return d ? `${WEEKDAYS_LONG[d.getDay()]}, ${day(d)}` : NOTHING;
}

/** «05.10.» – ein Tag in einer Spanne, das Jahr steht daneben. */
export function dayShort(value: string | Date | null | undefined): string {
  const d = parse(value);
  return d ? `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.` : NOTHING;
}

/** «Oktober 2026» aus «2026-10». */
export function monthTitle(month: string): string {
  const [y, m] = month.split('-').map(Number);
  return `${MONTHS_LONG[m - 1] ?? ''} ${y}`;
}

/** «TT.MM.JJJJ» → «JJJJ-MM-TT» (ein Tag, den es gibt), sonst `null`. */
export function parseDay(text: string): string | null {
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(text.trim());
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = new Date(Date.UTC(y, mo - 1, d));
  if (t.getUTCDate() !== d || t.getUTCMonth() !== mo - 1 || y < 1900 || y > 2100) return null;
  return `${y}-${pad(mo)}-${pad(d)}`;
}
