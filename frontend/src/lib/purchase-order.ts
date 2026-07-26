import { Clock, FileText, ShoppingCart, XCircle, PackageCheck } from 'lucide-react';
import type { PurchaseOrderStatus, ProcessStepMode } from '@/types';
import { TONE, pickCfg, type StatusCfg } from '@/lib/status-flow';

// Beschaffungs-Ampel: offen/laufend (angefragt/offeriert/bestellt) = GELB,
// geliefert = GRÜN, abgelehnt = ROT. Die Schritte trennen sich zusätzlich per Symbol.
export const PURCHASE_STATUS: Record<PurchaseOrderStatus, StatusCfg> = {
  requested: { label: 'Angefragt',    ...TONE.pending, icon: Clock },
  quoted:    { label: 'Offeriert',    ...TONE.pending, icon: FileText },
  ordered:   { label: 'Bestellt',     ...TONE.pending, icon: ShoppingCart },
  rejected:  { label: 'Abgelehnt',    ...TONE.danger,  icon: XCircle },
  received:  { label: 'Geliefert',    ...TONE.done,    icon: PackageCheck },
};

export function purchaseStatusConfig(status: string): StatusCfg {
  return pickCfg(PURCHASE_STATUS, status, 'requested');
}

export const PROCESS_MODE_LABEL: Record<ProcessStepMode, string> = {
  supplier: 'Lieferant',
  webshop: 'Webshop-Link',
};
