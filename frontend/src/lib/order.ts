import { FilePen, Hammer, CheckCircle2, Ban } from 'lucide-react';
import type { OrderStatus } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

export const ORDER_STATUS: Record<OrderStatus, StatusCfg> = {
  draft:     { label: 'Entwurf',        color: '#d97706', bg: '#fffbeb', icon: FilePen },
  released:  { label: 'In Bearbeitung', color: '#2563eb', bg: '#eff6ff', icon: Hammer },
  completed: { label: 'Abgeschlossen',  color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  inactive:  { label: 'Inaktiv',        color: '#64748b', bg: '#f1f5f9', icon: Ban },
};

export function orderStatusConfig(status: string): StatusCfg {
  return ORDER_STATUS[status as OrderStatus] ?? ORDER_STATUS.draft;
}
