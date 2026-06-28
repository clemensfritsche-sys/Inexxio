import { Clock, CheckCircle2, FileText, Banknote, Ban } from 'lucide-react';
import type { StatusCfg } from '@/lib/status-flow';
import type { PNode } from '@/components/erp/purchase-progress';

// Verkauf (kaufmännisches Spiegelbild der Beschaffung):
// Angefragt → Bestätigt → Verrechnet → Bezahlt   (+ Storniert)
export type SaleStatus = 'requested' | 'confirmed' | 'invoiced' | 'paid' | 'cancelled';

export const SALE_STATUS: Record<SaleStatus, StatusCfg> = {
  requested: { label: 'Angefragt',  color: '#d97706', bg: '#fffbeb', icon: Clock },
  confirmed: { label: 'Bestätigt',  color: '#2563eb', bg: '#eff6ff', icon: CheckCircle2 },
  invoiced:  { label: 'Verrechnet', color: '#7c3aed', bg: '#f5f3ff', icon: FileText },
  paid:      { label: 'Bezahlt',    color: '#0f766e', bg: '#f0fdfa', icon: Banknote },
  cancelled: { label: 'Storniert',  color: '#dc2626', bg: '#fef2f2', icon: Ban },
};

export function saleStatusConfig(status: string): StatusCfg {
  return SALE_STATUS[status as SaleStatus] ?? SALE_STATUS.requested;
}

const SALE_FLOW = [
  { key: 'requested', label: 'Angefragt' },
  { key: 'confirmed', label: 'Bestätigt' },
  { key: 'invoiced', label: 'Verrechnet' },
  { key: 'paid', label: 'Bezahlt' },
] as const;

function fmt(iso?: string | null): string | undefined {
  return iso ? new Date(iso).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' }) : undefined;
}

/** Knoten des Verkaufs-Fortschritts (analog zur Beschaffung). Storniert wird – wie
 *  «Abgelehnt» bei der Beschaffung – als roter Endknoten nach «Angefragt» gezeigt. */
export function saleNodes(sale: {
  status: string; confirmed_at?: string | null; invoiced_at?: string | null; paid_at?: string | null;
}): PNode[] {
  if (sale.status === 'cancelled') {
    return [
      { key: 'requested', label: 'Angefragt', state: 'done' },
      { key: 'cancelled', label: 'Storniert', state: 'rejected' },
    ];
  }
  const hint: Record<string, string | undefined> = {
    confirmed: fmt(sale.confirmed_at), invoiced: fmt(sale.invoiced_at), paid: fmt(sale.paid_at),
  };
  const ci = SALE_FLOW.findIndex((f) => f.key === sale.status);
  return SALE_FLOW.map((f, i) => ({
    key: f.key,
    label: f.label,
    state: i < ci ? 'done' : i === ci ? (sale.status === 'paid' ? 'done' : 'active') : 'pending',
    hint: hint[f.key],
  }));
}
