import { Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { TONE, type StatusCfg } from '@/lib/status-flow';

/**
 * **Status → Farbe: die EINE zentrale Zuordnung.**
 *
 * Farbe hängt am **Status**, nie an der Position im Fluss (PROCESS_CORE.md §5.3). Sonst
 * skaliert die Darstellung nicht: dasselbe Stück sähe oben anders aus als unten, und
 * jede neue Ansicht müsste die Regel neu erfinden.
 *
 * Es gibt hier **keine** Farblogik in einzelnen Komponenten — wer einen Status anzeigt,
 * liest diese Karte. Sie spiegelt `backend/app/domain/statuses.py` und wird dagegen
 * getestet (`tests/test_frontend_mirrors.py`), damit die beiden Seiten nicht still
 * auseinanderlaufen.
 *
 * **Rot hat heute keinen Wert.** Der Ton steht in der Ampel, aber die Fehlerbehandlung
 * im Modul ist nicht entschieden (§11.5) — ein Statuswert dafür wäre erfunden. Der
 * Eintrag unten fängt darum nur ab, was es nicht geben dürfte, und macht es **sichtbar**
 * statt es zu verstecken.
 */

export const FREIGEGEBEN = 'freigegeben';
export const IM_PROZESS = 'im_prozess';

export const STATUS_CFG: Record<string, StatusCfg> = {
  [FREIGEGEBEN]: { label: 'Freigegeben', ...TONE.done, icon: CheckCircle2 },
  [IM_PROZESS]: { label: 'Im Prozess', ...TONE.pending, icon: Clock },
};

/** Alle Werte in Anzeige-Reihenfolge – die Auswahl im Modul-Editor liest sie. */
export const STATUS_VALUES = [FREIGEGEBEN, IM_PROZESS] as const;

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
