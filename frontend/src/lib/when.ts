/**
 * ►►► **WANN — die eine Datums-Ausgabe des Hauses** (Testnotiz #992). ◄◄◄
 *
 * *«Bitte erstelle EINE zentrale Datums-Formatierungsfunktion für das ganze System und
 * ersetze alle bestehenden Ausgaben damit.»*
 *
 * Vorher gab es sieben: `localDate`, `localDateTime`, drei eigene Helfer im Beleg
 * (`daysUntil`/`relative`/`since`) und dazu je ein `toLocaleDateString` am Benutzer, am
 * Profil und an den Passkeys. Dieselbe Angabe las sich damit an fünf Stellen anders –
 * «03.07.2026», «31.07.26, 21:52», «13. Juli 2026», «vor 3 Tagen».
 *
 * ## Zwei Fragen, zwei Funktionen — und das ist kein Widerspruch
 *
 * **`when()` beantwortet «wann war das?»** – die Aussage, nach der man wirklich fragt:
 * «gerade eben», «vor 12 Minuten», «vor 3 Stunden», «Gestern», «vor 3 Tagen», danach das
 * Datum. Sie steht überall dort, wo ein Zeitpunkt eine **Auskunft** ist (Log, Angebote,
 * letzter Login, angelegt/geändert).
 *
 * *Für «heute» stand hier einmal die blosse **Uhrzeit** (`17:58`) – eine Zahl, aus der
 * man selbst ausrechnet, wie lange das her ist (Testnotiz #1003).*
 *
 * **`day()` beantwortet «welcher Tag steht auf dem Papier?»** – die Tatsache. Auf einem
 * **Beleg** ist das Rechnungsdatum kein «vor 3 Tagen»: es ist die Angabe, die gedruckt
 * wird und über die Steuerperiode entscheidet (MWSTG Art. 26). Zwei Formen **einer**
 * Regel, an einer Stelle, mit einem Namensstamm – wie `pick_problem`/`unpickable` im
 * Backend. Zwei *Regeln* wären es nicht.
 *
 * ## Und die volle Tatsache steht IMMER im Hover
 *
 * `whenTitle()` liefert sie (`13.09.2026, 17:58`), und `formatWhen()` gibt beides in
 * einem Zug zurück, damit eine Aufrufstelle sie nicht vergessen kann. Eine Aussage ohne
 * ihre Tatsache ist eine Zahl, die man nicht nachprüfen kann.
 *
 * ## Die Wörter stehen HIER, nicht im ICU
 *
 * `toLocaleDateString('de-CH', { month: 'short' })` liefert je nach ICU-Fassung «Sep.»
 * oder «Sept.» – dieselbe Falle wie beim Tausender-Trenner in `formatAmount` (dort ein
 * typografisches `’` im Browser und ein gerades `'` in Node, gemessen). Dieselbe Angabe
 * darf nicht je nach Laufzeit anders aussehen: server- und clientseitig gerendert wirft
 * React die Seite weg. Also schreibt dieses Modul jede Zeichenkette selbst.
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

/** Singular und Plural als **Angabe**, nicht als Rechnung: deutsche Beugung ist keine
 *  Zeichenkettenoperation, und eine Regel, die bei einem Wort zufällig stimmt, ist keine
 *  (die Lehre aus «Kundeen», #787). */
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

/**
 * **Der Tag, wie er auf dem Papier steht** – «13.09.2026». Ohne Wert: «—».
 *
 * Für alles, wo das Datum die **Tatsache** ist: Rechnungs-, Leistungs- und Fälligkeitsdatum
 * auf einem Beleg, ein Eintrittsdatum, ein Vertragstag.
 */
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
 * ►►► **Die Uhrzeit war eine Zahl, keine Aussage** (Testnotiz #1003). ◄◄◄ Für «heute»
 * stand hier `17:58` – und wer das liest, rechnet selbst aus, wie lange das her ist. Ein
 * Zeitpunkt beantwortet aber die Frage *wann war das*, und innerhalb eines Tages heisst
 * die Antwort «vor drei Stunden». Die **Tatsache** (Datum und Uhrzeit) steht unverändert
 * im Hover, wo man sie nachschlägt.
 *
 * **Die Kaskade ist eine Reihenfolge, kein Widerspruch**: was 20 Stunden her ist, war
 * gestern *und* ist «vor 20 Stunden» – die genauere Aussage gewinnt. «Gestern» beginnt
 * damit dort, wo Stunden zu zählen aufhört.
 *
 * **Ein reines Datum kennt keine Uhrzeit** – ein Fälligkeitstag *ist* heute, und «vor 7
 * Stunden» wäre eine erfundene Genauigkeit. Er sagt «Heute» und überspringt die Kaskade.
 *
 * `now` ist ein Parameter, damit die Funktion **rein** ist und sich prüfen lässt; ohne
 * ihn ist es der Moment des Renderns.
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
 * **Beides in einem Zug** – die Aussage und die Tatsache dazu.
 *
 * ```tsx
 * const w = formatWhen(entry.created_at);
 * <span data-tip={w.title}>{w.text}</span>
 * ```
 *
 * Es gibt sie, damit eine Aufrufstelle den Hover **nicht vergessen kann**: wer nur `when`
 * ruft, schreibt eine Aussage hin, die niemand nachprüfen kann.
 */
export function formatWhen(value: string | Date | null | undefined,
                           now: Date = new Date()): { text: string; title?: string } {
  return { text: when(value, now), title: whenTitle(value) };
}
