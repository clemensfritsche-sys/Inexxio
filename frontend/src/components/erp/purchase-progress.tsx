'use client';

import { Check, X } from 'lucide-react';

export type PState = 'done' | 'active' | 'pending' | 'rejected';
export interface PNode { key: string; label: string; state: PState; hint?: string }
export interface Delivery { pct: number; label: string; overdue: boolean; oi: number }

/**
 * **Der Beschaffungs-Ablauf in derselben Bildsprache wie der Auftrags-Prozess** (Notiz #182):
 * senkrecht, ein Knoten je Stufe, verbunden durch eine dünne Linie. Vorher war es ein
 * waagrechter Punkte-Stepper mit animiertem Lieferwagen – dieselbe Sache in einer zweiten
 * Bildsprache, und die Animation brachte `@keyframes` in die Fläche.
 *
 * Die Lieferfrist ist keine Stufe, sondern eine **Eigenschaft der Stufe «Bestellt»** – sie
 * steht als schmaler Balken unter deren Zeile, dort wo sie gilt.
 *
 * Ampel wie überall: erledigt = GRÜN, aktiv = GELB, abgelehnt = ROT, offen = neutral.
 */
const NODE: Record<PState, { bg: string; color: string; ring: string }> = {
  done: { bg: 'var(--success)', color: '#fff', ring: 'transparent' },
  active: { bg: 'var(--warning)', color: '#fff', ring: 'var(--warning-bg)' },
  pending: { bg: 'var(--bg-3)', color: 'var(--fg-4)', ring: 'transparent' },
  rejected: { bg: 'var(--danger)', color: '#fff', ring: 'transparent' },
};

export function PurchaseProgress({ nodes, delivery }: { nodes: PNode[]; delivery?: Delivery }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {nodes.map((n, i) => {
        const c = NODE[n.state];
        const last = i === nodes.length - 1;
        const showEta = !!delivery && i === delivery.oi;
        return (
          <div key={n.key} style={{ display: 'flex', gap: 11 }}>
            {/* Marke + Verbindungslinie nach unten */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
              <span title={n.hint} style={{
                width: 22, height: 22, borderRadius: '50%', background: c.bg, color: c.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                font: '700 10.5px var(--font-body)', cursor: n.hint ? 'help' : 'default',
                boxShadow: n.state === 'active' ? `0 0 0 3px ${c.ring}` : 'none',
              }}>
                {n.state === 'done' ? <Check size={12} /> : n.state === 'rejected' ? <X size={12} /> : i + 1}
              </span>
              {!last && <span style={{ flex: 1, width: 2, minHeight: 14, background: n.state === 'done' ? 'var(--success)' : 'var(--border-1)' }} />}
            </div>

            <div style={{ minWidth: 0, flex: 1, paddingBottom: last ? 0 : 10 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap', minHeight: 22 }}>
                <span style={{
                  font: `${n.state === 'active' ? 700 : 500} 13px var(--font-body)`,
                  color: n.state === 'pending' ? 'var(--fg-4)' : n.state === 'rejected' ? 'var(--danger)' : 'var(--fg-1)',
                }}>
                  {n.label}
                </span>
                {n.hint && <span style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)' }}>{n.hint}</span>}
              </div>

              {/* Lieferfrist: Eigenschaft der Stufe «Bestellt», kein eigener Knoten. */}
              {showEta && (
                <div style={{ marginTop: 5, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ position: 'relative', flex: 1, maxWidth: 180, height: 3, borderRadius: 2, background: 'var(--bg-3)', overflow: 'hidden' }}>
                    <span style={{
                      position: 'absolute', inset: 0, width: `${delivery!.pct}%`, borderRadius: 2,
                      background: delivery!.overdue ? 'var(--danger)' : 'var(--warning)',
                    }} />
                  </span>
                  <span style={{ font: '600 11.5px var(--font-body)', color: delivery!.overdue ? 'var(--danger)' : 'var(--warning)' }}>
                    {delivery!.label}
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
