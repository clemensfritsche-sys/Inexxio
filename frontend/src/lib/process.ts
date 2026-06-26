import { ShoppingCart, ClipboardCheck, ArrowLeftRight, Warehouse, User as UserIcon, Boxes, Wrench, Clock, CheckCircle2, XCircle, PackageMinus, Trash2, Receipt, Banknote } from 'lucide-react';
import type { StepType, LocationType } from '@/types';
import type { StepState } from '@/components/erp/process-stepper';
import type { StatusCfg } from '@/lib/status-flow';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:   { label: 'Beschaffung',    icon: ShoppingCart },
  inspection: { label: 'Datenerfassung', icon: ClipboardCheck },
  movement:   { label: 'Bewegung',       icon: ArrowLeftRight },
  resource:   { label: 'Ressource',      icon: Wrench },   // Verbrauch + Betriebsmittel (Modus pro Zeile)
  sale:       { label: 'Verkauf',        icon: Receipt },
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

// Anzeige-Projektion der ZWEI Achsen (quality + disposition) auf EINE Badge.
// Bedeutungs-Vorrang: Verbleib (scrapped/sold/consumed) ≻ Verdikt (failed) ≻
// am Lager (passed+in_stock) ≻ sonst «Im Prozess». Das Datenmodell bleibt getrennt;
// nur die Darstellung fasst beides zu einem Status zusammen.
const INSTANCE_STATUS: Record<string, StatusCfg> = {
  in_process: { label: 'Im Prozess',   color: '#d97706', bg: '#fffbeb', icon: Clock },
  in_stock:   { label: 'Freigegeben',  color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  failed:     { label: 'Gesperrt',     color: '#dc2626', bg: '#fef2f2', icon: XCircle },
  consumed:   { label: 'Verbraucht',   color: '#7c3aed', bg: '#f5f3ff', icon: PackageMinus },
  scrapped:   { label: 'Verschrottet', color: '#475569', bg: '#f1f5f9', icon: Trash2 },
  sold:       { label: 'Verkauft',     color: '#0d9488', bg: '#f0fdfa', icon: Banknote },
};

export function instanceStatusConfig(
  quality: string | null | undefined,
  disposition: string | null | undefined,
): StatusCfg {
  if (disposition === 'scrapped') return INSTANCE_STATUS.scrapped;
  if (disposition === 'sold') return INSTANCE_STATUS.sold;
  if (disposition === 'consumed') return INSTANCE_STATUS.consumed;
  if (quality === 'failed') return INSTANCE_STATUS.failed;
  if (quality === 'passed' && disposition === 'in_stock') return INSTANCE_STATUS.in_stock;
  return INSTANCE_STATUS.in_process;
}
