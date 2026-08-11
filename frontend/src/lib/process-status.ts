import { Ban, CheckCircle2, Clock, AlertTriangle, XCircle } from 'lucide-react';
import { TONE, type StatusCfg } from '@/lib/status-flow';
import { STATUS_CATALOG } from '@/lib/status-catalog';

/**
 * **Die Anzeige eines Status — was der Katalog nicht sagen kann.**
 *
 * Beschriftung, Ampelton, Achsen und Bestands-Zugehörigkeit stehen in
 * `lib/status-catalog.ts`, und die Datei ist **generiert** aus
 * `backend/app/domain/statuses.py`. Hier bleibt genau das, was aus dem Fachmodell nicht
 * kommen kann: das **Symbol** – eine Gestaltungsfrage – und die Auflösung zur
 * Anzeige-Konfiguration.
 *
 * Vorher stand die ganze Liste hier ein zweites Mal, von Hand gepflegt. Ein neuer Status
 * kostete zwei Einträge; ein Test verglich sie, verhinderte das Auseinanderlaufen aber
 * nicht – er meldete es erst hinterher. Jetzt kostet er **einen**.
 *
 * Farbe hängt am **Status**, nie an der Position im Fluss (PROCESS_CORE.md §5.3): der
 * Katalog nennt den Ton, die Tokens die Farbe. Es gibt hier keine Farblogik in
 * einzelnen Komponenten — wer einen Status anzeigt, liest `statusCfg`.
 */

export {
  FREIGEGEBEN, IM_PROZESS, ABGESCHLOSSEN, ABGEBROCHEN, INAKTIV,
  STATUS_CATALOG, STATUS_VALUES,
  UNIT_STATUSES, ORDER_STATUSES, ARTICLE_STATUSES,
  START_BEFORE, START_AFTER, END_BEFORE,
  type StatusTone, type StockKind, type StatusEntry,
} from '@/lib/status-catalog';

/**
 * Symbol je Status. **Das Einzige, was hier von Hand steht** – und das Einzige, was ein
 * neuer Status hier braucht. Fehlt es, greift ein Standard: ein fehlendes Symbol ist
 * eine Lücke in der Gestaltung, kein Fehler im Modell, und darf die Anzeige nicht
 * blockieren.
 */
const ICONS: Record<string, StatusCfg['icon']> = {
  freigegeben: CheckCircle2,
  im_prozess: Clock,
  abgeschlossen: CheckCircle2,
  abgebrochen: XCircle,
  inaktiv: Ban,
};

const CFG: Record<string, StatusCfg> = Object.fromEntries(
  STATUS_CATALOG.map((s) => [
    s.value,
    { label: s.label, ...TONE[s.tone], icon: ICONS[s.value] ?? CheckCircle2 },
  ]),
);

/**
 * Anzeige eines Status. Ein unbekannter Wert wird **rot gemeldet**, nicht schöngefärbt:
 * er dürfte nicht existieren, und eine Anzeige, die ihn wie einen normalen Zustand
 * malt, verbirgt genau den Fehler, den man sehen müsste.
 */
export function statusCfg(status: string): StatusCfg {
  return CFG[status] ?? {
    label: status,
    ...TONE.danger,
    icon: AlertTriangle,
  };
}

export function statusLabel(status: string): string {
  return statusCfg(status).label;
}
