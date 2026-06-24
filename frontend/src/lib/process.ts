import { ShoppingCart, ClipboardCheck, ArrowLeftRight, Warehouse, User as UserIcon, Boxes, Wrench, Clock, CheckCircle2, XCircle, PackageMinus, Trash2, Receipt, Banknote, Sparkles, Layers, Target, TrendingUp, TrendingDown, Minus, FilePen, Ban } from 'lucide-react';
import type { StepType, InstanceQcStatus, LocationType, ProcessSource, ProcessStockEffect } from '@/types';
import type { StepState } from '@/components/erp/process-stepper';
import type { StatusCfg } from '@/lib/status-flow';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:   { label: 'Beschaffung',    icon: ShoppingCart },
  inspection: { label: 'Datenerfassung', icon: ClipboardCheck },
  movement:   { label: 'Bewegung',       icon: ArrowLeftRight },
  resource:   { label: 'Ressource',      icon: Wrench },
  sale:       { label: 'Verkauf',        icon: Receipt },
};

// Prozess-Quelle = SUBJEKT (worauf der Prozess wirkt) – KEINE Richtungswahl.
export const PROCESS_SOURCE_META: Record<ProcessSource, { label: string; hint: string; icon: React.ElementType }> = {
  produce:  { label: 'Neu', icon: Sparkles, hint: 'Subjekt: der Prozess erzeugt neue Instanzen (Produktion).' },
  stock:    { label: 'Bestand', icon: Layers, hint: 'Subjekt: vorhandener Bestand (FIFO) – z. B. Verkauf, Entnahme.' },
  instance: { label: 'Instanz', icon: Target, hint: 'Subjekt: eine konkrete bestehende Instanz – z. B. Wartung, Kontrolle.' },
};

export function sourceLabel(source: string | null | undefined): string {
  return source ? (PROCESS_SOURCE_META[source as ProcessSource]?.label ?? source) : '—';
}

// Abgeleitete Lager-Richtung (Folge der Schritte, NICHT gewählt).
export const STOCK_EFFECT_META: Record<ProcessStockEffect, StatusCfg> = {
  increase: { label: 'Bestand erhöhend', color: '#16a34a', bg: '#f0fdf4', icon: TrendingUp },
  decrease: { label: 'Bestand mindernd', color: '#dc2626', bg: '#fef2f2', icon: TrendingDown },
  neutral:  { label: 'Bestandsneutral',  color: '#64748b', bg: '#f1f5f9', icon: Minus },
};

export function stockEffectConfig(effect: string | null | undefined): StatusCfg {
  return STOCK_EFFECT_META[effect as ProcessStockEffect] ?? STOCK_EFFECT_META.neutral;
}

// Prozess-Lebenszyklus (eigenständiges Objekt): Entwurf → Freigegeben → Inaktiv.
export const PROCESS_STATUS: Record<string, StatusCfg> = {
  draft:    { label: 'Entwurf',     color: '#d97706', bg: '#fffbeb', icon: FilePen },
  released: { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  inactive: { label: 'Inaktiv',     color: '#64748b', bg: '#f1f5f9', icon: Ban },
};

export function processStatusConfig(status: string): StatusCfg {
  return PROCESS_STATUS[status] ?? PROCESS_STATUS.draft;
}

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

export const QC_STATUS: Record<InstanceQcStatus, StatusCfg> = {
  pending:  { label: 'Im Prozess',  color: '#d97706', bg: '#fffbeb', icon: Clock },
  passed:   { label: 'Freigegeben', color: '#16a34a', bg: '#f0fdf4', icon: CheckCircle2 },
  failed:   { label: 'Gesperrt',    color: '#dc2626', bg: '#fef2f2', icon: XCircle },
  consumed: { label: 'Verbraucht',  color: '#7c3aed', bg: '#f5f3ff', icon: PackageMinus },
  scrapped: { label: 'Verschrottet', color: '#475569', bg: '#f1f5f9', icon: Trash2 },
  sold:     { label: 'Verkauft',    color: '#0d9488', bg: '#f0fdfa', icon: Banknote },
};

export function qcStatusConfig(status: string): StatusCfg {
  return QC_STATUS[status as InstanceQcStatus] ?? QC_STATUS.pending;
}
