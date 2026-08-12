// ⚠ GENERIERT aus backend/app/domain/statuses.py – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_statuses
//
// **Die Statusliste ist eine Quelle, kein Spiegel.** Was hier steht, steht dort – ein
// neuer Status wird ausschliesslich im Backend ergänzt, und Beschriftung, Ampelton,
// Achsen und Bestands-Zugehörigkeit kommen von selbst hier an. Die Symbole liegen
// daneben (`lib/process-status.ts`): ein Symbol ist eine Gestaltungsfrage und kann nicht
// aus dem Fachmodell kommen; fehlt es, greift ein Standard – kein Grund für einen Fehler.

/** Ampelton eines Status. Die konkreten Farbwerte stehen in den Design-Tokens. */
export type StatusTone = 'done' | 'pending' | 'danger';

/** Zählt ein Stück in diesem Zustand zum aktuellen Bestand oder zur Historie? */
export type StockKind = 'live' | 'history';

export interface StatusEntry {
  value: string;
  label: string;
  tone: StatusTone;
  /** Welche Achsen ihn tragen können: unit | order | article. */
  axes: readonly string[];
  /** Nur für Zustände, die ein Stück tragen kann – sonst `null`. */
  stock: StockKind | null;
  /** **Ist dieser Zustand endgültig?** Die eine Eigenschaft, aus der alles folgt:
   *  die Farbe, ob ein Auftrag das Stück greifen darf, und der Schutz in der
   *  Datenbank. Aus einem Endzustand heraus gibt es keinen Übergang mehr. */
  terminal: boolean;
}


/** Die Werte – einzeln benannt, damit der Code sie nicht als Text führt. */
export const FREIGEGEBEN = "freigegeben";
export const IM_PROZESS = "im_prozess";
export const GESPERRT = "gesperrt";
export const VERSCHROTTET = "verschrottet";
export const ABGESCHLOSSEN = "abgeschlossen";
export const ABGEBROCHEN = "abgebrochen";
export const INAKTIV = "inaktiv";

/** Der Katalog. Reihenfolge = Anzeige-Reihenfolge (Leiste, Legende).*/
export const STATUS_CATALOG: readonly StatusEntry[] = [
  { value: FREIGEGEBEN, label: "Freigegeben", tone: "done", axes: ["unit", "article"], stock: "live", terminal: false },
  { value: IM_PROZESS, label: "Im Prozess", tone: "pending", axes: ["unit", "order"], stock: "live", terminal: false },
  { value: GESPERRT, label: "Gesperrt", tone: "pending", axes: ["unit"], stock: "live", terminal: false },
  { value: VERSCHROTTET, label: "Verschrottet", tone: "danger", axes: ["unit"], stock: "history", terminal: true },
  { value: ABGESCHLOSSEN, label: "Abgeschlossen", tone: "done", axes: ["order"], stock: null, terminal: false },
  { value: ABGEBROCHEN, label: "Abgebrochen", tone: "danger", axes: ["order"], stock: null, terminal: false },
  { value: INAKTIV, label: "Inaktiv", tone: "danger", axes: ["article"], stock: null, terminal: false },
];

/** Alle Werte in Anzeige-Reihenfolge. */
export const STATUS_VALUES: readonly string[] = STATUS_CATALOG.map((s) => s.value);

/** Wer welche Werte tragen kann – abgeleitet, keine zweite Liste. */
export const UNIT_STATUSES: readonly string[] = STATUS_CATALOG.filter((s) => s.axes.includes("unit")).map((s) => s.value);
export const ORDER_STATUSES: readonly string[] = STATUS_CATALOG.filter((s) => s.axes.includes("order")).map((s) => s.value);
export const ARTICLE_STATUSES: readonly string[] = STATUS_CATALOG.filter((s) => s.axes.includes("article")).map((s) => s.value);

/** Die festen Rand-Übergänge (PROCESS_CORE.md §4.1). */
export const START_BEFORE = FREIGEGEBEN;
export const START_AFTER = IM_PROZESS;
export const END_BEFORE = IM_PROZESS;
