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
export type ScanKind = 'user' | 'instance' | 'article' | 'process' | 'object';

export interface ScanStep {
  label: string;                              // was gerade gescannt werden soll
  hint?: string;                              // optionaler Zusatzhinweis
  kind?: ScanKind;                            // erwarteter Objekttyp → Symbol im Scanner
  expected?: number | number[] | null;        // exakt zu treffende Objektnummer(n)
  candidates?: ScanCandidate[];               // Vorschläge für die manuelle Suche
  restrict?: boolean;                         // nur Kandidaten-IDs zulassen (sonst: jede gültige Nr.)
}

export interface ScanRequest {
  title?: string;
  steps: ScanStep[];
  onComplete: (objectIds: number[]) => void;
}

/** Bewertet einen gescannten/eingegebenen Code gegen einen Schritt. */
export function validateForStep(objectId: number, step: ScanStep): boolean {
  if (step.expected != null) return matchesExpected(objectId, step.expected);
  if (step.restrict && step.candidates) return step.candidates.some((c) => c.objectId === objectId);
  return true;   // freier Lookup: jede gültige Objektnummer zählt
}
