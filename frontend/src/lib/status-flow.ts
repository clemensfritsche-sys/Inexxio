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

/**
 * Status → Anzeige-Konfiguration, mit Rückfall auf den Anfangszustand.
 *
 * Dieser Dreizeiler lag fünfmal identisch im Code (Artikel, Auftrag, Beschaffung,
 * Verkauf, Instanz) – gleiche Bedeutung, fünf Funktionen. Die fachlichen Karten
 * bleiben je Domäne, die *Auflösung* ist jetzt eine.
 */
export function pickCfg<T extends string>(
  map: Record<T, StatusCfg>, status: string, fallback: T,
): StatusCfg {
  return map[status as T] ?? map[fallback];
}

export interface StatusAction {
  label: string;
  target: string;
  tone?: StatusTone;
  disabled?: boolean;
  hint?: string;
}

// ─── Semantische Status-Töne (token-basiert) ─────────────────────────────────
// EINE Quelle für ALLE Datensatz-Status (Artikel/Auftrag/Instanz/Lagerplatz/
// Beschaffung/Verkauf). Farbe = Bedeutung, konsequent über die ganze App:
//   pending  = offen / in Arbeit / im Prozess   → amber-orange (--warning)
//   info     = aktiv / informativ / reserviert  → slate (--accent)
//   done     = erledigt / freigegeben / am Lager → grün (--success)
//   danger   = Fehler / gesperrt / abgelehnt    → rot (--danger)
//   inactive = inaktiv / verschrottet           → warmes Grau
// Werte kommen ausschliesslich aus den Design-Tokens (colors_and_type.css) –
// keine hartkodierten Hex-Farben mehr in den Status-Configs.
export const TONE: Record<'pending' | 'info' | 'done' | 'danger' | 'inactive', { color: string; bg: string }> = {
  pending:  { color: 'var(--warning)',    bg: 'var(--warning-bg)' },
  info:     { color: 'var(--accent-ink)', bg: 'var(--accent-soft)' },
  done:     { color: 'var(--success)',    bg: 'var(--success-bg)' },
  danger:   { color: 'var(--danger)',     bg: 'var(--danger-bg)' },
  inactive: { color: 'var(--fg-3)',       bg: 'var(--bg-3)' },
};

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
