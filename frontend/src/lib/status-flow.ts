// Gemeinsamer Lebenszyklus für Artikel / Auftrag / Lagerplatz als Prozess:
// Entwurf → (Freigeben) → Freigegeben → (Deaktivieren) → Inaktiv → (Reaktivieren).
// Kein freies Status-Dropdown mehr – Statuswechsel erfolgen per Klick.

import type { ElementType } from 'react';

export type StatusTone = 'primary' | 'danger' | 'neutral';

// Einheitliche Status-Anzeige: Label + semantische Farbe + Symbol (Symbole statt
// Text, Farbe = Bedeutung). `icon` ist optional, damit Altaufrufe gültig bleiben.
export interface StatusCfg {
  label: string;
  color: string;
  bg: string;
  icon?: ElementType;
}

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
