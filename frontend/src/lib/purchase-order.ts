import { Ban, Clock, FileText, ShoppingCart, XCircle, PackageCheck } from 'lucide-react';
import type { PurchaseOrderStatus, ProcessStepMode } from '@/types';
import { TONE, pickCfg, type StatusCfg } from '@/lib/status-flow';

// Beschaffungs-Ampel: offen/laufend (angefragt/offeriert/bestellt) = GELB,
// geliefert = GRÜN, abgelehnt/storniert = ROT. Die Schritte trennen sich zusätzlich per Symbol.
//
// **«Abgelehnt» und «Storniert» sind nicht dasselbe** – darum zwei Wörter und zwei Symbole:
// abgelehnt heisst, der Besteller sagt zu einer Offerte nein (eine Entscheidung); storniert
// heisst, der Vorgang hat seinen Gegenstand verloren, weil sein Auftrag abgebrochen wurde.
// «Storniert» ist dabei kein neues Wort im Haus – der Verkauf trägt es längst.
export const PURCHASE_STATUS: Record<PurchaseOrderStatus, StatusCfg> = {
  requested: { label: 'Angefragt',    ...TONE.pending, icon: Clock },
  quoted:    { label: 'Offeriert',    ...TONE.pending, icon: FileText },
  ordered:   { label: 'Bestellt',     ...TONE.pending, icon: ShoppingCart },
  rejected:  { label: 'Abgelehnt',    ...TONE.danger,  icon: XCircle },
  cancelled: { label: 'Storniert',    ...TONE.danger,  icon: Ban },
  received:  { label: 'Geliefert',    ...TONE.done,    icon: PackageCheck },
};

export function purchaseStatusConfig(status: string): StatusCfg {
  return pickCfg(PURCHASE_STATUS, status, 'requested');
}

