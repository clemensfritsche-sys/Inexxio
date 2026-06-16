import type { PurchaseOrderStatus, ProcessStepMode } from '@/types';

export const PURCHASE_STATUS: Record<PurchaseOrderStatus, { label: string; color: string; bg: string }> = {
  requested: { label: 'Angefragt',    color: '#d97706', bg: '#fffbeb' },
  quoted:    { label: 'Offeriert',    color: '#2563eb', bg: '#eff6ff' },
  ordered:   { label: 'Bestellt',     color: '#7c3aed', bg: '#f5f3ff' },
  rejected:  { label: 'Abgelehnt',    color: '#dc2626', bg: '#fef2f2' },
  received:  { label: 'Wareneingang', color: '#0f766e', bg: '#f0fdfa' },
};

export const PURCHASE_STATUS_ORDER: PurchaseOrderStatus[] = [
  'requested', 'quoted', 'ordered', 'received', 'rejected',
];

export function purchaseStatusConfig(status: string): { label: string; color: string; bg: string } {
  return PURCHASE_STATUS[status as PurchaseOrderStatus] ?? PURCHASE_STATUS.requested;
}

export const PROCESS_MODE_LABEL: Record<ProcessStepMode, string> = {
  supplier: 'Lieferant',
  webshop: 'Webshop-Link',
};
