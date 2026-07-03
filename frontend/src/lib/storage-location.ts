import { FilePen, CheckCircle2, Ban } from 'lucide-react';
import type { StorageLocationStatus } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

export const STORAGE_STATUS: Record<StorageLocationStatus, StatusCfg> = {
  draft:    { label: 'Entwurf',     color: '#d97706', bg: '#fffbeb', icon: FilePen },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  inactive: { label: 'Inaktiv',     color: '#64748b', bg: '#f1f5f9', icon: Ban },
};

export function storageStatusConfig(status: string): StatusCfg {
  return STORAGE_STATUS[status as StorageLocationStatus] ?? STORAGE_STATUS.draft;
}

