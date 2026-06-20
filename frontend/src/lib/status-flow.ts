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

// Ersetzen (kein Versionieren): «replace» legt einen Nachfolger an und verknüpft.
// `canReactivate`/`canReplace` erlauben typspezifische Abweichungen (z. B. Auftrag
// ohne Reaktivieren).
export function lifecycleActions(
  status: string,
  opts?: { canReactivate?: boolean; canReplace?: boolean },
): StatusAction[] {
  const canReactivate = opts?.canReactivate ?? true;
  const canReplace = opts?.canReplace ?? true;
  switch (status) {
    case 'draft':    return [{ label: 'Freigeben', target: 'released', tone: 'primary' }];
    case 'released': {
      const a: StatusAction[] = [];
      if (canReplace) a.push({ label: 'Ersetzen', target: 'replace', tone: 'neutral' });
      a.push({ label: 'Deaktivieren', target: 'inactive', tone: 'danger' });
      return a;
    }
    case 'inactive': return canReactivate ? [{ label: 'Reaktivieren', target: 'released', tone: 'neutral' }] : [];
    default:         return [];   // completed o. Ä. → kein manueller Wechsel
  }
}
