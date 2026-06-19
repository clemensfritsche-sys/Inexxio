import { FilePen, CheckCircle2, Ban } from 'lucide-react';
import type { StorageLocationStatus, StorageLocationType } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

export const STORAGE_STATUS: Record<StorageLocationStatus, StatusCfg> = {
  draft:    { label: 'Entwurf',     color: '#d97706', bg: '#fffbeb', icon: FilePen },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  inactive: { label: 'Inaktiv',     color: '#64748b', bg: '#f1f5f9', icon: Ban },
};

export const STORAGE_STATUS_ORDER: StorageLocationStatus[] = ['draft', 'released', 'inactive'];

export function storageStatusConfig(status: string): StatusCfg {
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
