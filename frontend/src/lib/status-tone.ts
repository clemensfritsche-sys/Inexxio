// Status-Anzeige der Datensätze: die Ampeltöne und die Form einer Status-Konfiguration.

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

// ─── Ampel-Töne (token-basiert) ──────────────────────────────────────────────
// REINE Ampel-Logik für ALLE Datensatz-Status (Artikel/Auftrag/Instanz/Einzelinstanz).
// Genau DREI Bedeutungen, drei Farben:
//   pending = offen / in Arbeit / wartend / gesperrt              → GELB (--warning)
//   done    = gut / erledigt / freigegeben / verbaut / verkauft   → GRÜN (--success)
//   danger  = Problem / Fehler / inaktiv / verschrottet           → ROT  (--danger)
// «Aus»-Zustände (inaktiv/verschrottet) sind bewusst ROT – die Ampel steht auf «Stopp»,
// der Datensatz ist nicht mehr zu verwenden. Werte kommen ausschliesslich aus den
// Design-Tokens (colors_and_type.css) – keine hartkodierten Hex-Farben in Status-Configs.
export const TONE: Record<'pending' | 'done' | 'danger', { color: string; bg: string }> = {
  pending:  { color: 'var(--warning)', bg: 'var(--warning-bg)' },
  done:     { color: 'var(--success)', bg: 'var(--success-bg)' },
  danger:   { color: 'var(--danger)',  bg: 'var(--danger-bg)' },
};

