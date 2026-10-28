'use client';

import type { StatusCfg } from '@/lib/status-tone';

/**
 * ►►► **Das Mikro-Label** – Versalien, klein, gedämpft: die eine Beschriftung, mit der
 * das ERP eine Angabe benennt, ohne sie zu überschreien.
 *
 * Sie stand als Inline-Stil an jeder Stelle, an der jemand sie brauchte – mit leicht
 * verschiedenen Werten (11 ↔ 11.5 px, 600 ↔ 700, .05 ↔ .07 em). Das ist genau die Form,
 * in der eine Gestaltungsregel auseinanderläuft, ohne dass es jemandem auffällt: jede
 * Fassung sieht für sich richtig aus. Eine Sache, eine Stelle.
 */
export const MICRO_LABEL: React.CSSProperties = {
  font: '700 11px var(--font-body)', textTransform: 'uppercase',
  letterSpacing: '.07em', color: 'var(--fg-4)',
};

/**
 * ►►► **Der Punkt eines Zustands** – 6 px in der Farbe des Tons, das Wort steht daneben
 * (Design-System: «Status als Punkt + Wort»). EIN Bauteil für jeden Zustandspunkt. ◄◄◄
 */
export function StatusDot({ color, style }: { color: string; style?: React.CSSProperties }) {
  return (
    <span aria-hidden style={{
      display: 'inline-block', width: 6, height: 6, borderRadius: 999, flex: 'none',
      background: color, ...style,
    }} />
  );
}

/**
 * Der Zustand als Pille: Symbol + Farbe + Wort – **eine** Form, überall dieselbe (Feed wie
 * Detail-Kopf, #334): derselbe Zustand darf nicht je nach Ort anders aussehen.
 */
export function StatusBadge({ cfg, size = 10 }: { cfg: StatusCfg; size?: number }) {
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: size, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
    }}>
      {Icon && <Icon size={size + 3} strokeWidth={2.5} />}
      {cfg.label}
    </span>
  );
}


/** **Beschriftete Wertzeile** («Kunde · Max Muster») – eine Stelle für alle Zusammenfassungen. */
export function Row({ k, v, hint }: {
  k: string; v: string;
  /** Abgeleitetes Detail zur Zeile – gehört in den **Hover**, nicht in die Fläche. */
  hint?: string;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span data-tip={hint} style={{
        color: 'var(--fg-4)', flexShrink: 0, cursor: hint ? 'help' : undefined,
        display: 'inline-flex', alignItems: 'center', gap: 5,
      }}>
        {k}
      </span>
      <span style={{ color: 'var(--fg-1)', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}
