import { FilePen, CheckCircle2, Ban } from 'lucide-react';
import type { StorageLocationStatus } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';

export const STORAGE_STATUS: Record<StorageLocationStatus, StatusCfg> = {
  draft:    { label: 'Entwurf',     ...TONE.pending,  icon: FilePen },
  released: { label: 'Freigegeben', ...TONE.done,     icon: CheckCircle2 },
  inactive: { label: 'Inaktiv',     ...TONE.inactive, icon: Ban },
};

export function storageStatusConfig(status: string): StatusCfg {
  return STORAGE_STATUS[status as StorageLocationStatus] ?? STORAGE_STATUS.draft;
}

