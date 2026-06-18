import type { ClaimStatus, ClaimDirection, ClaimReason, ClaimResolution } from '@/types';
import type { StatusAction } from '@/lib/status-flow';

export const CLAIM_STATUS: Record<ClaimStatus, { label: string; color: string; bg: string }> = {
  open:     { label: 'Offen',         color: '#d97706', bg: '#fffbeb' },
  accepted: { label: 'Angenommen',    color: '#2563eb', bg: '#eff6ff' },
  closed:   { label: 'Abgeschlossen', color: '#16a34a', bg: '#f0fdf4' },
  rejected: { label: 'Abgelehnt',     color: '#64748b', bg: '#f1f5f9' },
};

export function claimStatusConfig(status: string): { label: string; color: string; bg: string } {
  return CLAIM_STATUS[status as ClaimStatus] ?? CLAIM_STATUS.open;
}

// Lebenszyklus der Reklamation als Prozess (kein Status-Dropdown):
// Offen →[Annehmen]→ Angenommen →[Abschliessen]→ Abgeschlossen
//   ↘[Ablehnen]→ Abgelehnt ; terminal lässt sich wiedereröffnen.
export function claimActions(status: string): StatusAction[] {
  switch (status) {
    case 'open':
      return [
        { label: 'Annehmen', target: 'accepted', tone: 'primary' },
        { label: 'Ablehnen', target: 'rejected', tone: 'danger' },
      ];
    case 'accepted':
      return [{ label: 'Abschliessen', target: 'closed', tone: 'primary' }];
    case 'rejected':
    case 'closed':
      return [{ label: 'Wiedereröffnen', target: 'open', tone: 'neutral' }];
    default:
      return [];
  }
}

export const CLAIM_DIRECTIONS: { value: ClaimDirection; label: string }[] = [
  { value: 'internal', label: 'Intern' },
  { value: 'supplier', label: 'Lieferant' },
  { value: 'customer', label: 'Kunde' },
];

export function claimDirectionLabel(value: string | null | undefined): string {
  if (!value) return '—';
  return CLAIM_DIRECTIONS.find((d) => d.value === value)?.label ?? value;
}

export const CLAIM_REASONS: { value: ClaimReason; label: string }[] = [
  { value: 'defect',        label: 'Defekt / Mangel' },
  { value: 'damage',        label: 'Transportschaden' },
  { value: 'wrong_item',    label: 'Falschlieferung' },
  { value: 'quantity',      label: 'Mengenabweichung' },
  { value: 'documentation', label: 'Dokumentation' },
  { value: 'other',         label: 'Sonstiges' },
];

export function claimReasonLabel(value: string | null | undefined): string {
  if (!value) return '—';
  return CLAIM_REASONS.find((r) => r.value === value)?.label ?? value;
}

export const CLAIM_RESOLUTIONS: { value: ClaimResolution; label: string }[] = [
  { value: 'none',    label: 'Offen / keine' },
  { value: 'rework',  label: 'Nacharbeit' },
  { value: 'replace', label: 'Ersatzlieferung' },
  { value: 'return',  label: 'Rücksendung' },
  { value: 'credit',  label: 'Gutschrift' },
];

export function claimResolutionLabel(value: string | null | undefined): string {
  if (!value) return '—';
  return CLAIM_RESOLUTIONS.find((r) => r.value === value)?.label ?? value;
}
