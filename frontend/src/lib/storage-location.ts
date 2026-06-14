import type { StorageLocationStatus, StorageLocationType } from '@/types';

export const STORAGE_STATUS: Record<StorageLocationStatus, { label: string; color: string; bg: string }> = {
  draft:    { label: 'Entwurf',     color: '#d97706', bg: '#fffbeb' },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4' },
  inactive: { label: 'Inaktiv',     color: '#64748b', bg: '#f1f5f9' },
};

export const STORAGE_STATUS_ORDER: StorageLocationStatus[] = ['draft', 'released', 'inactive'];

export function storageStatusConfig(status: string): { label: string; color: string; bg: string } {
  return STORAGE_STATUS[status as StorageLocationStatus] ?? STORAGE_STATUS.draft;
}

export const STORAGE_TYPES: { value: StorageLocationType; label: string }[] = [
  { value: 'rack',     label: 'Regal' },
  { value: 'pallet',   label: 'Palettenplatz' },
  { value: 'floor',    label: 'Bodenlager' },
  { value: 'drawer',   label: 'Schublade' },
  { value: 'picking',  label: 'Kommissionierzone' },
  { value: 'external', label: 'Aussenlager' },
];

export function storageTypeLabel(value: string | null | undefined): string {
  if (!value) return '—';
  return STORAGE_TYPES.find((t) => t.value === value)?.label ?? value;
}
