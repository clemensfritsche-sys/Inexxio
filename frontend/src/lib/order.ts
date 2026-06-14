import type { OrderStatus } from '@/types';

export const ORDER_STATUS: Record<OrderStatus, { label: string; color: string; bg: string }> = {
  draft:    { label: 'Entwurf',     color: '#d97706', bg: '#fffbeb' },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4' },
  inactive: { label: 'Inaktiv',     color: '#64748b', bg: '#f1f5f9' },
};

export const ORDER_STATUS_ORDER: OrderStatus[] = ['draft', 'released', 'inactive'];

export function orderStatusConfig(status: string): { label: string; color: string; bg: string } {
  return ORDER_STATUS[status as OrderStatus] ?? ORDER_STATUS.draft;
}
