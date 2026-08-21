// Zentrale Kodierung/Dekodierung von Objekt-Codes (QR/Barcode).
//
// Jeder Datensatz trägt eine universelle 9-stellige Objektnummer – sie ist der
// EINZIGE Schlüssel, den ein Code transportieren muss. Wir kodieren sie als QR
// und lesen sie per Kamera wieder ein.
//
// Der Parser ist bewusst tolerant: er akzeptiert die nackte Nummer ODER einen
// Text/URL, der eine 9-stellige Zahl enthält (z. B. ein künftiger Deep-Link
// `…/o/100000042` oder ein vom Handy-Kamera-App geöffneter Link). So bleiben
// einmal gedruckte Etiketten dauerhaft gültig, auch wenn wir die Kodierung
// später auf URLs umstellen.

export const OBJECT_ID_MIN = 100_000_001;
export const OBJECT_ID_MAX = 999_999_999;

// 9-stellig, erste Ziffer ≠ 0, mit Wortgrenzen (eine 10-stellige Zahl matcht NICHT).
const OBJECT_ID_RE = /\b([1-9]\d{8})\b/;

/** Inhalt, der in den QR-Code eines Objekts geschrieben wird. */
export function encodeObjectCode(objectId: number): string {
  return String(objectId);
}

/** Extrahiert aus einem gescannten Rohtext die Objektnummer (oder null). */
export function parseScannedCode(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const match = raw.match(OBJECT_ID_RE);
  if (!match) return null;
  const n = Number(match[1]);
  return n >= OBJECT_ID_MIN && n <= OBJECT_ID_MAX ? n : null;
}

/** Prüft, ob eine gescannte Nummer zu einem erwarteten Ziel passt (Verifikation). */
export function matchesExpected(objectId: number, expected: number | number[] | null | undefined): boolean {
  if (expected == null) return true;                       // kein Ziel ⇒ reiner Lookup
  return Array.isArray(expected) ? expected.includes(objectId) : expected === objectId;
}

// ─── Zentrale Scanner-Anfrage (Sequenz von Scan-Schritten) ────────────────────
//
// Ein Scan-Vorgang besteht aus einer Reihe von Schritten (z. B. «Aktueller
// Standort» → «Instanz» → «Zielstandort»). Jeder Schritt validiert den Scan;
// erst wenn alle Schritte erfolgreich sind, feuert `onComplete` mit den IDs.

/** Eintrag für die semantische Suche (manueller Fallback) im Scanner. */
export interface ScanCandidate {
  objectId: number;
  label: string;     // Anzeigetext (z. B. Artikelname / Typ)
}

// Erwarteter Objekttyp eines Scan-Schritts – für ein klares Symbol im Scanner
// («was muss ich jetzt scannen?»).
export type ScanKind = 'user' | 'instance' | 'company' | 'article' | 'process' | 'object';

/**
 * **Der eine Satz, mit dem eine Datensatz-Suche fragt.**
 *
 * Er steht im Referenzfeld (`ObjectSelect`) UND in der Suchleiste des Scanners – dieselbe
 * Frage, also derselbe Wortlaut. Zwei Formulierungen wären zwei Massstäbe, und der Dialog
 * sähe aus wie ein zweites Bauteil statt wie dasselbe Feld, nur gross.
 *
 * Er nennt bewusst **nicht** die Sorte: die steht als Beschriftung darüber – im Feld als
 * `Label`, im Scanner als Zeile über der Leiste. Ein Platzhalter verschwindet, sobald man
 * tippt; was man sucht, darf nicht mit dem ersten Zeichen verschwinden.
 */
export const LOOKUP_HINT = 'Nummer oder Name';

export interface ScanStep {
  /**
   * **Was gerade gescannt werden soll – die SORTE, nie die Nummer.**
   *
   * «Instanz», «Material», «Zielort». Die Nummer baut der Scanner selbst, wenn der
   * Schritt eine erwartet (`objectCodes.prompt` aus {@link expected}) – steht sie auch
   * hier, sagt sie der Dialog zweimal: «Instanz 100000825 100000825» (Testnotiz #737).
   *
   * Sie steht als **Beschriftung über der Suchleiste**, genau wie das `Label` über dem
   * Referenzfeld – dieselbe Anatomie, damit der Dialog sichtbar dasselbe Feld ist, nur
   * gross. Ein zusätzlicher Erklärtext (früher `hint`) und ein Dialog-Titel sind
   * entfallen, weil der ganze Container die Kamera ist.
   */
  label: string;
  kind?: ScanKind;                            // erwarteter Objekttyp → Symbol im Scanner
  expected?: number | number[] | null;        // exakt zu treffende Objektnummer(n)
  candidates?: ScanCandidate[];               // Vorschläge für die manuelle Suche
  restrict?: boolean;                         // nur Kandidaten-IDs zulassen (sonst: jede gültige Nr.)
  /**
   * **Vorschläge suchen, statt eine Liste mitzugeben.**
   *
   * `candidates` ist eine **fertige Menge** – brauchbar, wo der Aufrufer sie kennt (die
   * paar Zielorte einer Bewegung), unbrauchbar, wo sie das halbe ERP wäre: der freie
   * Lookup im Feed gab darum gar keine mit, und die Vorschlagsliste blieb für immer
   * leer. Wer «00787» tippte, sah nichts.
   *
   * Diese Frage geht stattdessen an den Aufrufer, der die Suche ohnehin besitzt – der
   * Feed reicht seine eigene durch, statt dass der Scanner eine zweite baut.
   *
   * **Nur die Vorschlagsquelle wird breiter, nicht die Gültigkeitsregel**: was ein
   * Schritt annimmt, sagt weiterhin allein {@link validateForStep} (`expected` ·
   * `restrict`+`candidates`).
   */
  suggest?: (query: string) => Promise<ScanCandidate[]>;
  /**
   * **Gibt es dieses Objekt überhaupt?** – nur für den freien Lookup.
   *
   * Ohne `expected`/`restrict` gilt jede formal gültige 9-stellige Zahl. Das ist für
   * einen Verifikationsschritt richtig (dort sagt `expected`, was stimmen muss), für
   * den freien Lookup aber zu lasch: irgendein fremder QR-Code mit neun Ziffern kam
   * durch, der Dialog meldete Erfolg – und beim Aufrufer passierte stillschweigend
   * nichts. Wer die Frage beantworten kann, reicht sie hier herein.
   */
  exists?: (objectId: number) => Promise<boolean>;
  /**
   * **«Nichts» ist auch hier eine Wahl.**
   *
   * Wo ein leerer Wert gültig ist (ein Bewegen-Modul ohne festes Ziel), führt das
   * Referenzfeld ihn als erste Zeile seiner Liste (`SearchSelect.emptyOption`). Der
   * Scanner IST dieses Feld, nur gross – also führt er dieselbe Zeile. Ohne sie müsste
   * man ihn schliessen, um eine Entscheidung zu treffen, die er selbst anbietet.
   *
   * Was «nichts» bedeutet, weiss nur der Aufrufer – der Scanner erfindet dafür keine
   * Nummer, er ruft `pick()` und schliesst.
   */
  emptyOption?: { label: string; pick: () => void };
}

/**
 * **Wie ein Wert in den Scanner gekommen ist.**
 *
 * Der Kamerascan ist der Regelweg, die Tastatur die Alternative – beides ist eine
 * Bestätigung, keines eine Umgehung, und beides wird geloggt (`process.confirm_step`
 * verlangt genau diese Angabe). Sie entsteht **hier**, weil nur der Dialog sie kennt:
 * ein Aufrufer sähe nur die Nummer und müsste raten, wie sie zustande kam.
 *
 * Vorsichtig gerechnet: ist auch nur ein Schritt getippt oder aus der Vorschlagsliste
 * gewählt worden, gilt der ganze Vorgang als `manual`. Eine Bestätigung ist so viel
 * wert wie ihr schwächstes Glied.
 */
export type ScanVia = 'scan' | 'manual';

export interface ScanRequest {
  steps: ScanStep[];
  onComplete: (objectIds: number[], via: ScanVia) => void;
  /**
   * Wie ein Kamerabild zu einem Ergebnis wird. Ohne Angabe: {@link objectCodes}.
   * Siehe {@link ScanReading} – das ist die Naht, an der später eine zweite Deutung
   * andockt, ohne den Dialog anzufassen.
   */
  reading?: ScanReading;
}

/** Bewertet einen gescannten/eingegebenen Code gegen einen Schritt. */
export function validateForStep(objectId: number, step: ScanStep): boolean {
  if (step.expected != null) return matchesExpected(objectId, step.expected);
  if (step.restrict && step.candidates) return step.candidates.some((c) => c.objectId === objectId);
  return true;   // freier Lookup: jede gültige Objektnummer zählt
}

/**
 * **Was dieser Schritt anbietet — abgeleitet aus dem, was er ANNIMMT.**
 *
 * Das ist die Behebung eines strukturellen Bruchs: die Vorschlagsquelle war eine Angabe
 * **je Aufrufer** (`candidates`/`suggest`). Der Feed brachte seine Suche mit, ein
 * Prozessschrittmodul nicht – dort war die Liste darum für immer leer, und wer «00787»
 * tippte, sah nichts. Es war nie ein zweiter Dialog; es war eine Suche, die an jeder
 * Aufrufstelle einzeln zu leben hatte, und genau eine davon hatte sie.
 *
 * Ein Verifikationsschritt braucht dafür gar keine Suche: was er annimmt, **ist** seine
 * Vorschlagsliste (``expected``). Damit gilt an jeder Stelle dieselbe Regel – der
 * Scanner bietet an, was er akzeptiert – und niemand muss mehr etwas mitgeben.
 *
 * Ein Aufrufer darf weiterhin **beschriften**: bringt er `candidates` mit, gewinnen sie
 * (dieselben Nummern, nur mit Namen dran).
 */
export function offersFor(step: ScanStep | undefined): ScanCandidate[] {
  if (!step) return [];
  if (step.candidates?.length) return step.candidates;
  if (step.expected == null) return [];
  const wanted = Array.isArray(step.expected) ? step.expected : [step.expected];
  return wanted.map((objectId) => ({ objectId, label: step.label }));
}

// ─── Die Deutung – austauschbar, heute genau eine ────────────────────────────
//
// **Der Dialog besitzt die Kamera und liefert ein Ergebnis. Was dieses Ergebnis
// BEDEUTET, steht hier.** Vorher griff der Dialog direkt zu `parseScannedCode` und
// `validateForStep` – damit wusste er, dass ein Scan eine Objektnummer ist. Das ist
// eine Annahme, die heute stimmt und morgen eine zweite Deutung ausschliesst.
//
// Drei Fragen, mehr braucht eine Deutung nicht:
//   read    – was steht in diesem Rohtext?
//   check   – darf dieser Wert den Schritt erfüllen? (`null` = ja, sonst der Grund)
//   prompt  – was soll im Bild stehen?
//
// Der Dialog kennt nur diesen Vertrag; die Objektnummer-Semantik lebt vollständig in
// `objectCodes`, und wer die Deutung tauscht, tauscht ein Objekt – keine Zeile im Dialog.

export interface ScanReading {
  read(raw: string): number | null;
  check(value: number, step: ScanStep): Promise<string | null>;
  prompt(step: ScanStep | undefined): string;
}

/** Neunstellig, mit führenden Nullen – dieselbe Schreibweise wie überall im ERP. */
function nr(objectId: number): string {
  return String(objectId).padStart(9, '0');
}

/** Die heutige Deutung: **eine Objektnummer lesen, prüfen, benennen.** */
export const objectCodes: ScanReading = {
  read: parseScannedCode,

  async check(objectId, step) {
    if (!validateForStep(objectId, step)) {
      return step.expected != null
        ? `${nr(objectId)} ist nicht das erwartete Objekt`
        : `${nr(objectId)} steht hier nicht zur Wahl`;
    }
    // Formal gültig – aber gibt es die Nummer? Nur der freie Lookup fragt das; ein
    // Verifikationsschritt kennt sein Ziel bereits.
    if (step.exists && !(await step.exists(objectId))) {
      return `${nr(objectId)} ist nicht im ERP`;
    }
    return null;
  },

  /**
   * **Der Platzhalter der Suchleiste – wortgleich mit dem des Referenzfelds.**
   *
   * Er sagt, was man EINGIBT, nicht was man tun soll. «scannen» stand hier, solange der
   * Satz nur im Kamerabild vorkam; in einem Textfeld wäre das Verb falsch – und es war
   * das Einzige, was die beiden Oberflächen daran hinderte, denselben Satz zu tragen.
   * Dass gescannt wird, sagen Zielrahmen und Suchstrahl; **was** gesucht wird, steht als
   * Beschriftung darüber ({@link ScanStep.label}) statt im Platzhalter, der beim ersten
   * Zeichen verschwindet.
   *
   * Bei einer Verifikation ist es die erwartete Nummer selbst – genau das, was man
   * tippen würde, und weiterhin **hier** gebaut statt an der Aufrufstelle (Notiz #737).
   */
  prompt(step) {
    if (step && typeof step.expected === 'number') return nr(step.expected);
    return LOOKUP_HINT;
  },
};
