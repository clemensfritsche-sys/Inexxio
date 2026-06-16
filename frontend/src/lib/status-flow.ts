// Gemeinsamer Lebenszyklus für Artikel / Auftrag / Lagerplatz als Prozess:
// Entwurf → (Freigeben) → Freigegeben → (Deaktivieren) → Inaktiv → (Reaktivieren).
// Kein freies Status-Dropdown mehr – Statuswechsel erfolgen per Klick.

export type StatusTone = 'primary' | 'danger' | 'neutral';

export interface StatusAction {
  label: string;
  target: string;
  tone?: StatusTone;
  disabled?: boolean;
  hint?: string;
}

export function lifecycleActions(status: string): StatusAction[] {
  switch (status) {
    case 'draft':    return [{ label: 'Freigeben', target: 'released', tone: 'primary' }];
    case 'released': return [{ label: 'Deaktivieren', target: 'inactive', tone: 'danger' }];
    case 'inactive': return [{ label: 'Reaktivieren', target: 'released', tone: 'neutral' }];
    default:         return [];   // completed o. Ä. → kein manueller Wechsel
  }
}
