import { ShoppingCart, Hash, ClipboardCheck } from 'lucide-react';
import type { StepType, InstanceQcStatus } from '@/types';
import type { StepState } from '@/components/erp/process-stepper';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:      { label: 'Beschaffung',      icon: ShoppingCart },
  serialization: { label: 'Serialisierung',   icon: Hash },
  inspection:    { label: 'Eingangskontrolle', icon: ClipboardCheck },
};

export function stepLabel(type: string): string {
  return STEP_META[type as StepType]?.label ?? type;
}

// Auftrag-Schrittstatus (Backend) → Stepper-Knotenstatus
export function toStepperState(state: string): StepState {
  if (state === 'done') return 'done';
  if (state === 'active') return 'active';
  if (state === 'failed') return 'rejected';
  return 'pending'; // locked
}

export const QC_STATUS: Record<InstanceQcStatus, { label: string; color: string; bg: string }> = {
  pending: { label: 'Prüfung offen', color: '#d97706', bg: '#fffbeb' },
  passed:  { label: 'Freigegeben',   color: '#16a34a', bg: '#f0fdf4' },
  failed:  { label: 'Gesperrt',      color: '#dc2626', bg: '#fef2f2' },
};

export function qcStatusConfig(status: string): { label: string; color: string; bg: string } {
  return QC_STATUS[status as InstanceQcStatus] ?? QC_STATUS.pending;
}
