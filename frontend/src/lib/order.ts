import { FilePen, Loader, CheckCircle2, Ban } from 'lucide-react';
import type { OrderStatus } from '@/types';
import { TONE, pickCfg, type StatusCfg } from '@/lib/status-flow';

// **Gleiches Wort → gleiches Symbol** (Notiz #191): «Im Prozess» heisst am Auftrag dasselbe
// wie an der Instanz und trägt darum dasselbe Zeichen – `Loader`, das universelle «läuft
// gerade». Der frühere Hammer behauptete Fertigung (falsch für Beschaffung/Verkauf), die Uhr
// behauptete Warten (falsch für etwas, das aktiv läuft). Die Uhr bleibt dort, wo Warten die
// Aussage IST: «Angefragt».
// Ampel: Entwurf/Im Prozess = GELB (aktiv), Abgeschlossen = GRÜN, Inaktiv = ROT (Ampel auf
// «Stopp»). «Im Prozess» ist das EINE Wort für «aktiv/läuft» – beim Auftrag wie bei der
// Instanz und beim Prozessschritt. «In Arbeit» gibt es nicht mehr (Notizen #89/#90).
export const ORDER_STATUS: Record<OrderStatus, StatusCfg> = {
  draft:     { label: 'Entwurf',       ...TONE.pending, icon: FilePen },
  released:  { label: 'Im Prozess',    ...TONE.pending, icon: Loader },
  completed: { label: 'Abgeschlossen', ...TONE.done,    icon: CheckCircle2 },
  inactive:  { label: 'Inaktiv',       ...TONE.danger,  icon: Ban },
};

// «Abgebrochen» ist kein eigener Status im Datenmodell, sondern eine **Projektion**: ein
// inaktiver Auftrag, der in einen Abweichungsauftrag übergegangen ist (``abort_into_id``).
// Beide sind rot – aber «Inaktiv» heisst verworfen, «Abgebrochen» heisst fortgeführt.
export function orderStatusConfig(status: string, aborted = false): StatusCfg {
  if (aborted && status === 'inactive') return { label: 'Abgebrochen', ...TONE.danger, icon: Ban };
  return pickCfg(ORDER_STATUS, status, 'draft');
}
