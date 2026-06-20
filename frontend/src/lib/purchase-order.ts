import { Clock, FileText, ShoppingCart, XCircle, PackageCheck } from 'lucide-react';
import type { PurchaseOrderStatus, ProcessStepMode } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

export const PURCHASE_STATUS: Record<PurchaseOrderStatus, StatusCfg> = {
  requested: { label: 'Angefragt',    color: '#d97706', bg: '#fffbeb', icon: Clock },
  quoted:    { label: 'Offeriert',    color: '#2563eb', bg: '#eff6ff', icon: FileText },
  ordered:   { label: 'Bestellt',     color: '#7c3aed', bg: '#f5f3ff', icon: ShoppingCart },
  rejected:  { label: 'Abgelehnt',    color: '#dc2626', bg: '#fef2f2', icon: XCircle },
  received:  { label: 'Geliefert',    color: '#0f766e', bg: '#f0fdfa', icon: PackageCheck },
};

export const PURCHASE_STATUS_ORDER: PurchaseOrderStatus[] = [
  'requested', 'quoted', 'ordered', 'received', 'rejected',
];

export function purchaseStatusConfig(status: string): StatusCfg {
  return PURCHASE_STATUS[status as PurchaseOrderStatus] ?? PURCHASE_STATUS.requested;
}

export const PROCESS_MODE_LABEL: Record<ProcessStepMode, string> = {
  supplier: 'Lieferant',
  webshop: 'Webshop-Link',
};
