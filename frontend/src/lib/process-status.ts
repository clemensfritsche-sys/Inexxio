import { Ban, CheckCircle2, Clock, AlertTriangle, XCircle } from 'lucide-react';
import { TONE, type StatusCfg } from '@/lib/status-flow';

/**
 * **Die Statusliste — die eine Stelle, für alles.**
 *
 * Fünf Wörter für drei Achsen: Einzelinstanz, Auftrag, Artikel. Sie **teilen sich** die
 * Werte, wo sie dasselbe meinen – `im_prozess` heisst am Stück wie am Auftrag dasselbe,
 * also steht es einmal da, mit einer Beschriftung und einer Farbe. Vorher lag dieselbe
 * Aussage in drei Dateien mit drei Beschriftungen, und beim Auftrag sogar als
 * «Freigegeben»: das ist keine Zustand, sondern die Aktion, mit der er entstanden ist.
 *
 * Farbe hängt am **Status**, nie an der Position im Fluss (PROCESS_CORE.md §5.3). Sonst
 * skaliert die Darstellung nicht: dasselbe Stück sähe oben anders aus als unten, und
 * jede neue Ansicht müsste die Regel neu erfinden.
 *
 * Es gibt hier **keine** Farblogik in einzelnen Komponenten — wer einen Status anzeigt,
 * liest diese Karte. Sie spiegelt `backend/app/domain/statuses.py` und wird dagegen
 * getestet (`tests/test_frontend_mirrors.py`), damit die beiden Seiten nicht still
 * auseinanderlaufen.
 */

/** Einsatzbereit. Am Stück: in keinem Auftrag. Am Artikel: auftragsfähig. */
export const FREIGEGEBEN = 'freigegeben';
/** Läuft gerade – am Stück wie am Auftrag. */
export const IM_PROZESS = 'im_prozess';
/** Ziel erreicht (Auftrag). */
export const ABGESCHLOSSEN = 'abgeschlossen';
/** Das Ziel ist nicht mehr erreichbar (Auftrag). */
export const ABGEBROCHEN = 'abgebrochen';
/** Ausser Betrieb (Artikel). Endgültig. */
export const INAKTIV = 'inaktiv';

export const STATUS_CFG: Record<string, StatusCfg> = {
  [FREIGEGEBEN]: { label: 'Freigegeben', ...TONE.done, icon: CheckCircle2 },
  [IM_PROZESS]: { label: 'Im Prozess', ...TONE.pending, icon: Clock },
  [ABGESCHLOSSEN]: { label: 'Abgeschlossen', ...TONE.done, icon: CheckCircle2 },
  [ABGEBROCHEN]: { label: 'Abgebrochen', ...TONE.danger, icon: XCircle },
  [INAKTIV]: { label: 'Inaktiv', ...TONE.danger, icon: Ban },
};

/** Alle Werte in Anzeige-Reihenfolge. */
export const STATUS_VALUES = [
  FREIGEGEBEN, IM_PROZESS, ABGESCHLOSSEN, ABGEBROCHEN, INAKTIV,
] as const;

/** Wer welche Werte tragen kann – drei Teilmengen EINER Liste, nicht drei Listen. */
export const UNIT_STATUSES = [FREIGEGEBEN, IM_PROZESS] as const;
export const ORDER_STATUSES = [IM_PROZESS, ABGESCHLOSSEN, ABGEBROCHEN] as const;
export const ARTICLE_STATUSES = [FREIGEGEBEN, INAKTIV] as const;

/**
 * **Welche davon sind aktueller Bestand?** Das Gegenstück ist die Historie: Stücke, die
 * es noch als Datensatz gibt, aber nicht mehr als Material.
 *
 * Heute ist das die **volle** Liste – einen terminalen Zustand für ein Stück gibt es im
 * Modell nicht (PROCESS_CORE.md §4.2 kennt genau einen Ausgang, und der ist
 * `freigegeben`). Der Bestand trennt trotzdem entlang dieser Zeile: der Historien-Block
 * erscheint an dem Tag, an dem der erste solche Zustand dazukommt, ohne dass jemand eine
 * Oberfläche anfassen muss. Solange es ihn nicht gibt, steht er auch nicht da – ein
 * leerer Block wäre ein Versprechen, das die Ansicht nicht halten kann.
 *
 * Spiegelt `domain/statuses.LIVE_UNIT_STATUSES`, getestet.
 */
export const LIVE_UNIT_STATUSES: readonly string[] = UNIT_STATUSES;

/** Zählt dieser Zustand zum aktuellen Bestand? */
export function isLive(status: string): boolean {
  return LIVE_UNIT_STATUSES.includes(status);
}

/**
 * Anzeige eines Status. Ein unbekannter Wert wird **rot gemeldet**, nicht schöngefärbt:
 * er dürfte nicht existieren, und eine Anzeige, die ihn wie einen normalen Zustand
 * malt, verbirgt genau den Fehler, den man sehen müsste.
 */
export function statusCfg(status: string): StatusCfg {
  return STATUS_CFG[status] ?? {
    label: status,
    ...TONE.danger,
    icon: AlertTriangle,
  };
}

export function statusLabel(status: string): string {
  return statusCfg(status).label;
}

/** Die festen Rand-Übergänge (§4.1) – nicht je Auftrag einstellbar. */
export const START_BEFORE = FREIGEGEBEN;
export const START_AFTER = IM_PROZESS;
export const END_BEFORE = IM_PROZESS;
