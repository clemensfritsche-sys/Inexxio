import { Clock, CheckCircle2, FileText, Banknote, Ban } from 'lucide-react';
import { TONE, pickCfg, type StatusCfg } from '@/lib/status-flow';
import type { PNode } from '@/components/erp/purchase-progress';

// Verkauf (kaufmännisches Spiegelbild der Beschaffung):
// Angefragt → Bestätigt → Verrechnet → Bezahlt   (+ Storniert). Töne aus den Tokens.
export type SaleStatus = 'requested' | 'confirmed' | 'invoiced' | 'paid' | 'cancelled';

export const SALE_STATUS: Record<SaleStatus, StatusCfg> = {
  requested: { label: 'Angefragt',  ...TONE.pending, icon: Clock },
  confirmed: { label: 'Bestätigt',  ...TONE.pending, icon: CheckCircle2 },
  invoiced:  { label: 'Verrechnet', ...TONE.pending, icon: FileText },
  paid:      { label: 'Bezahlt',    ...TONE.done,    icon: Banknote },
  cancelled: { label: 'Storniert',  ...TONE.danger,  icon: Ban },
};

export function saleStatusConfig(status: string): StatusCfg {
  return pickCfg(SALE_STATUS, status, 'requested');
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
