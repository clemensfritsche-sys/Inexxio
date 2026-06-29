import { FilePen, Hammer, CheckCircle2, Ban, AlertTriangle } from 'lucide-react';
import type { OrderStatus } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

export const ORDER_STATUS: Record<OrderStatus, StatusCfg> = {
  draft:     { label: 'Entwurf',        color: '#d97706', bg: '#fffbeb', icon: FilePen },
  released:  { label: 'In Bearbeitung', color: '#2563eb', bg: '#eff6ff', icon: Hammer },
  completed: { label: 'Abgeschlossen',  color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  inactive:  { label: 'Inaktiv',        color: '#64748b', bg: '#f1f5f9', icon: Ban },
};

// Manuell wählbare Status (completed wird automatisch gesetzt)
export const ORDER_STATUS_ORDER: OrderStatus[] = ['draft', 'released', 'inactive'];

export function orderStatusConfig(status: string): StatusCfg {
  return ORDER_STATUS[status as OrderStatus] ?? ORDER_STATUS.draft;
}

// Badge für einen Abweichungs-Unterauftrag: immer als «Abweichung» erkennbar, aber die
// FARBE folgt dem Status – grün bei Abschluss (man sieht auf einen Blick, dass die
// Abweichung erledigt ist), sonst amber/blau/slate analog zum Auftrag.
const DEVIATION_TONE: Record<string, { color: string; bg: string }> = {
  draft:     { color: '#d97706', bg: '#fffbeb' },
  released:  { color: '#2563eb', bg: '#eff6ff' },
  completed: { color: '#16a34a', bg: '#f0fdf4' },
  inactive:  { color: '#64748b', bg: '#f1f5f9' },
};

export function deviationBadge(status: string): StatusCfg {
  const tone = DEVIATION_TONE[status] ?? DEVIATION_TONE.draft;
  const label = status === 'completed' ? 'Abweichung erledigt' : 'Abweichung';
  return { label, color: tone.color, bg: tone.bg, icon: AlertTriangle };
}
