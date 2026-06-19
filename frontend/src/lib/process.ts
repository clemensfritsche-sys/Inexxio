import { ShoppingCart, ClipboardCheck, ArrowLeftRight, Warehouse, User as UserIcon, Boxes, Wrench } from 'lucide-react';
import type { StepType, InstanceQcStatus, LocationType } from '@/types';
import type { StepState } from '@/components/erp/process-stepper';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:   { label: 'Beschaffung',    icon: ShoppingCart },
  inspection: { label: 'Datenerfassung', icon: ClipboardCheck },
  movement:   { label: 'Bewegung',       icon: ArrowLeftRight },
  resource:   { label: 'Ressource',      icon: Wrench },
};

// Standort-Typen (Bewegung): Label + Icon
export const LOCATION_META: Record<LocationType, { label: string; icon: React.ElementType }> = {
  lagerplatz: { label: 'Lagerplatz', icon: Warehouse },
  user:       { label: 'Person',     icon: UserIcon },
  instance:   { label: 'Instanz',    icon: Boxes },
};

export function locationTypeLabel(type: string | null | undefined): string {
  return type ? (LOCATION_META[type as LocationType]?.label ?? type) : '—';
}

/** Einheitliche Bezeichnung einer Instanz: Charge (batch) bzw. Unit (Einzelteil). */
export function instanceKindLabel(kind: string | null | undefined): string {
  return kind === 'batch' ? 'Charge' : 'Unit';
}

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
  pending:  { label: 'Im Prozess',  color: '#d97706', bg: '#fffbeb' },
  passed:   { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4' },
  failed:   { label: 'Gesperrt',    color: '#dc2626', bg: '#fef2f2' },
  consumed: { label: 'Verbraucht',  color: '#7c3aed', bg: '#f5f3ff' },
};

export function qcStatusConfig(status: string): { label: string; color: string; bg: string } {
  return QC_STATUS[status as InstanceQcStatus] ?? QC_STATUS.pending;
}
