import { FilePen, Hammer, CheckCircle2, Ban } from 'lucide-react';
import type { OrderStatus } from '@/types';
import { TONE, pickCfg, type StatusCfg } from '@/lib/status-flow';

// Ampel: Entwurf/In Arbeit = GELB (aktiv), Abgeschlossen = GRÜN, Inaktiv = ROT (Ampel auf
// «Stopp»). «In Arbeit» ist das EINE Wort für «aktiv/läuft» – dasselbe wie bei der Instanz.
export const ORDER_STATUS: Record<OrderStatus, StatusCfg> = {
  draft:     { label: 'Entwurf',       ...TONE.pending, icon: FilePen },
  released:  { label: 'In Arbeit',     ...TONE.pending, icon: Hammer },
  completed: { label: 'Abgeschlossen', ...TONE.done,    icon: CheckCircle2 },
  inactive:  { label: 'Inaktiv',       ...TONE.danger,  icon: Ban },
};

export function orderStatusConfig(status: string): StatusCfg {
  return pickCfg(ORDER_STATUS, status, 'draft');
}
