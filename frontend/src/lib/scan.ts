// Zentrale Kodierung/Dekodierung von Objekt-Codes (QR/Barcode). Ein Code trägt nur die
// universelle 9-stellige Objektnummer. Der Parser ist tolerant (nackte Nummer ODER Text/URL
// mit einer 9-stelligen Zahl), damit gedruckte Etiketten gültig bleiben.

import { SCAN_RECORD_TYPE, TYPE_META } from '@/lib/erp-record';

const OBJECT_ID_MIN = 100_000_001;
const OBJECT_ID_MAX = 999_999_999;

// 9-stellig, erste Ziffer ≠ 0, mit Wortgrenzen (eine 10-stellige Zahl matcht NICHT).
const OBJECT_ID_RE = /\b([1-9]\d{8})\b/;

/** Inhalt, der in den QR-Code eines Objekts geschrieben wird. */
export function encodeObjectCode(objectId: number): string {
  return String(objectId);
}

/** Extrahiert aus einem gescannten Rohtext die Objektnummer (oder null). */
function parseScannedCode(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const match = raw.match(OBJECT_ID_RE);
  if (!match) return null;
  const n = Number(match[1]);
  return n >= OBJECT_ID_MIN && n <= OBJECT_ID_MAX ? n : null;
}

/** Prüft, ob eine gescannte Nummer zu einem erwarteten Ziel passt (Verifikation). */
function matchesExpected(objectId: number, expected: number | number[] | null | undefined): boolean {
  if (expected == null) return true;                       // kein Ziel ⇒ reiner Lookup
  return Array.isArray(expected) ? expected.includes(objectId) : expected === objectId;
}

// ─── Zentrale Scanner-Anfrage (Sequenz von Scan-Schritten) ────────────────────
// Jeder Schritt validiert seinen Scan; erst wenn alle stimmen, feuert `onComplete` mit den IDs.

/** Eintrag für die semantische Suche (manueller Fallback) im Scanner. */
export interface ScanCandidate {
  objectId: number;
  label: string;     // Anzeigetext (z. B. Artikelname / Typ)
}

// Erwarteter Objekttyp eines Scan-Schritts – für ein klares Symbol im Scanner
// («was muss ich jetzt scannen?»).
export type ScanKind = 'user' | 'instance' | 'company' | 'article' | 'process' | 'object';

/** **Wie die Sorte heisst – aus EINER Quelle**: ohne Angabe aus dem Typ (`TYPE_META`). */
export function scanKindLabel(step?: ScanStep | null): string {
  if (step?.label) return step.label;
  const type = step?.kind ? SCAN_RECORD_TYPE[step.kind] : undefined;
  return type ? TYPE_META[type].label : 'Objekt';
}

/**
 * **Der eine Satz, mit dem eine Datensatz-Suche fragt** – im Referenzfeld (`ObjectSelect`) wie
 * im Scanner. Er nennt nicht die Sorte: die steht als Beschriftung darüber.
 */
export const LOOKUP_HINT = 'Nummer oder Name';

/**
 * ►►► **Wo keine Beschriftung steht, nennt der Platzhalter die Sorte.** ◄◄◄ Gebaut wie im
 * Scanner (`objectCodes.prompt`) – eine Schreibweise.
 */
export function lookupHint(kind?: string | null): string {
  return kind ? `${kind} – ${LOOKUP_HINT}` : LOOKUP_HINT;
}

/**
 * **Die eine Wahl «das entscheidet sich erst am Band».** In einer Definition ist «bewusst
 * keiner» eine Entscheidung, keine Lücke: erste Zeile der Liste (`SearchSelect.emptyOption`)
 * und im leeren Feld. «Definiert» statt «scannen», weil auch getippt wird. Jedes solche Feld
 * erbt diesen Satz.
 */
export const RUNTIME_CHOICE = 'Beim Ausführen definieren';

export interface ScanStep {
  /**
   * **Was gerade gescannt werden soll – die SORTE, nie die Nummer** («Instanz», «Zielort»).
   * Die Nummer baut der Scanner (`objectCodes.prompt`). Steht als Beschriftung über der
   * Suchleiste, wie das `Label` über dem Referenzfeld.
   */
  label?: string;
  kind?: ScanKind;                            // erwarteter Objekttyp → Symbol im Scanner
  expected?: number | number[] | null;        // exakt zu treffende Objektnummer(n)
  candidates?: ScanCandidate[];               // Vorschläge für die manuelle Suche
  restrict?: boolean;                         // nur Kandidaten-IDs zulassen (sonst: jede gültige Nr.)
  /**
   * **Vorschläge suchen, statt eine Liste mitzugeben** – wo `candidates` das halbe ERP wäre,
   * reicht der Aufrufer seine Suche durch. Nur die Vorschlagsquelle wird breiter, die
   * Gültigkeit sagt weiterhin {@link validateForStep}.
   */
  suggest?: (query: string) => Promise<ScanCandidate[]>;
  /**
   * **Gibt es dieses Objekt überhaupt?** – nur für den freien Lookup; sonst käme jede formal
   * gültige 9-stellige Zahl durch.
   */
  exists?: (objectId: number) => Promise<boolean>;
  /**
   * **«Nichts» ist auch hier eine Wahl** (wie `SearchSelect.emptyOption`). Was es bedeutet,
   * weiss der Aufrufer – der Scanner ruft `pick()` und schliesst.
   */
  emptyOption?: { label: string; pick: () => void };
}

/**
 * **Wie ein Wert in den Scanner gekommen ist** (Kamera ↔ Tastatur; beides geloggt,
 * `process.confirm_step`). Ist ein Schritt getippt oder gewählt, gilt der ganze Vorgang als
 * `manual` – das schwächste Glied.
 */
export type ScanVia = 'scan' | 'manual';

export interface ScanRequest {
  steps: ScanStep[];
  onComplete: (objectIds: number[], via: ScanVia) => void;
  /** Wie ein Kamerabild zu einem Ergebnis wird. Ohne Angabe: {@link objectCodes} ({@link ScanReading}). */
  reading?: ScanReading;
}

/** Bewertet einen gescannten/eingegebenen Code gegen einen Schritt. */
export function validateForStep(objectId: number, step: ScanStep): boolean {
  if (step.expected != null) return matchesExpected(objectId, step.expected);
  if (step.restrict && step.candidates) return step.candidates.some((c) => c.objectId === objectId);
  return true;   // freier Lookup: jede gültige Objektnummer zählt
}

/**
 * **Was dieser Schritt anbietet — abgeleitet aus dem, was er ANNIMMT.** Ein
 * Verifikationsschritt bietet ``expected`` an; der Scanner bietet an, was er akzeptiert.
 * Bringt ein Aufrufer `candidates` mit, gewinnen sie (dieselben Nummern mit Namen).
 */
export function offersFor(step: ScanStep | undefined): ScanCandidate[] {
  if (!step) return [];
  if (step.candidates?.length) return step.candidates;
  if (step.expected == null) return [];
  const wanted = Array.isArray(step.expected) ? step.expected : [step.expected];
  return wanted.map((objectId) => ({ objectId, label: scanKindLabel(step) }));
}

// ─── Die Deutung – austauschbar, heute genau eine ────────────────────────────
// Der Dialog besitzt die Kamera; was ein Ergebnis BEDEUTET, steht hier. Drei Fragen:
//   read    – was steht in diesem Rohtext?
//   check   – darf dieser Wert den Schritt erfüllen? (`null` = ja, sonst der Grund)
//   prompt  – was soll im Bild stehen?
// Die Objektnummer-Semantik lebt vollständig in `objectCodes`.

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
    // Gibt es die Nummer? Nur der freie Lookup fragt; eine Verifikation kennt ihr Ziel.
    if (step.exists) {
      // Scheitert die Frage selbst, sagt der Rahmen das – nicht «nicht im ERP».
      const known = await step.exists(objectId).catch((e: unknown) => e);
      if (known !== true && known !== false) {
        return `${nr(objectId)} nicht geprüft – ${known instanceof Error && known.message ? known.message : 'keine Antwort vom Server'}`;
      }
      if (!known) return `${nr(objectId)} ist nicht im ERP`;
    }
    return null;
  },

  /**
   * **Der Platzhalter der Suchleiste – wortgleich mit dem des Referenzfelds.** Er sagt Sorte
   * und Nummer («Instanz 100000825 suchen»); die Nummer hängt hier an, keine Aufrufstelle baut
   * sie. Dass gescannt wird, sagen Zielrahmen und Suchstrahl.
   */
  prompt(step) {
    const kind = scanKindLabel(step);
    if (step && typeof step.expected === 'number') return `${kind} ${nr(step.expected)} suchen`;
    return lookupHint(kind);
  },
};
