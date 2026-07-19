import { FilePen, Hammer, CheckCircle2, Ban } from 'lucide-react';
import type { OrderStatus } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';

// «In Bearbeitung» trägt jetzt denselben amber-orangen Ton wie eine Instanz «Im Prozess»
// (TONE.pending) – der laufende Auftrag ist in Arbeit, nicht «fertig». Farben aus den Tokens.
export const ORDER_STATUS: Record<OrderStatus, StatusCfg> = {
  draft:     { label: 'Entwurf',        ...TONE.pending,  icon: FilePen },
  released:  { label: 'In Bearbeitung', ...TONE.pending,  icon: Hammer },
  completed: { label: 'Abgeschlossen',  ...TONE.done,     icon: CheckCircle2 },
  inactive:  { label: 'Inaktiv',        ...TONE.inactive, icon: Ban },
};

export function orderStatusConfig(status: string): StatusCfg {
  return ORDER_STATUS[status as OrderStatus] ?? ORDER_STATUS.draft;
}
