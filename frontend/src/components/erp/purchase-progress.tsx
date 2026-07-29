'use client';

import { Check, X } from 'lucide-react';
import { PURCHASE_STATUS } from '@/lib/purchase-order';
import { Connector, kindColor } from '@/components/erp/process-steps';

export type PState = 'done' | 'active' | 'pending' | 'rejected';
export interface PNode { key: string; label: string; state: PState; hint?: string }
export interface Delivery { pct: number; label: string; overdue: boolean; oi: number }

/**
 * **Der Beschaffungs-Ablauf ist ein Prozess IM Prozess** (Notiz #194) – und wird darum
 * genau so gezeichnet wie der Auftrags-Ablauf: senkrechte Karten, durch einen Konnektor
 * verbunden, in der Farbe ihres Moduls. Dieselben Bausteine (`Connector`, `kindColor`),
 * nur eine Nummer kleiner, weil sie IN einer Modul-Karte stehen.
 *
 * Zustand ohne Wort, exakt wie im Auftrags-Fluss: erledigte und noch nicht erreichte Stufen
 * treten zurück (gedämpft), nur die aktive trägt ihre Farbe; das Symbol rechts sagt Haken
 * (erledigt) bzw. Kreuz (abgelehnt), der Hover nennt Wer/Wann.
 *
 * Die Lieferfrist ist **keine Stufe**, sondern eine Eigenschaft der Stufe «Bestellt» – ein
 * schmaler Balken in deren Karte, dort wo er gilt.
 *
 * Start-/Endknoten gibt es hier bewusst nicht: die umgebende Modul-Karte IST der Rahmen.
 */
export function PurchaseProgress({ nodes, delivery }: { nodes: PNode[]; delivery?: Delivery }) {
  const kc = kindColor('purchase');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {nodes.map((n, i) => {
        const muted = n.state === 'done' || n.state === 'pending';
        const cfg = PURCHASE_STATUS[n.key as keyof typeof PURCHASE_STATUS];
        const Icon = cfg?.icon;
        return (
          <div key={n.key} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {i > 0 && <Connector />}
            <div title={n.hint} style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 11,
              padding: '10px 13px', borderRadius: 'var(--r-md)',
              border: `1px solid ${kc.border}`, background: kc.bg,
              opacity: muted ? 0.5 : 1, cursor: n.hint ? 'help' : 'default',
            }}>
              <span style={{
                width: 30, height: 30, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
                color: n.state === 'rejected' ? 'var(--danger)' : kc.fg, border: `1px solid ${kc.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {Icon ? <Icon size={15} /> : <span style={{ font: '700 12px var(--font-body)' }}>{i + 1}</span>}
              </span>

              <div style={{ minWidth: 0, flex: 1 }}>
                <span style={{ font: `${n.state === 'active' ? 800 : 600} 13.5px var(--font-display)`, color: 'var(--fg-1)' }}>
                  {n.label}
                </span>
                {n.hint && <div style={{ marginTop: 2, font: '500 11.5px var(--font-body)', color: 'var(--fg-3)' }}>{n.hint}</div>}

                {/* Lieferfrist: Eigenschaft der Stufe «Bestellt», kein eigener Knoten. */}
                {delivery && i === delivery.oi && (
                  <div style={{ marginTop: 7, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ position: 'relative', flex: 1, maxWidth: 200, height: 3, borderRadius: 2, background: 'var(--bg-3)', overflow: 'hidden' }}>
                      <span style={{
                        position: 'absolute', inset: 0, width: `${delivery.pct}%`, borderRadius: 2,
                        background: delivery.overdue ? 'var(--danger)' : 'var(--warning)',
                      }} />
                    </span>
                    <span style={{ font: '600 11.5px var(--font-body)', color: delivery.overdue ? 'var(--danger)' : 'var(--warning)' }}>
                      {delivery.label}
                    </span>
                  </div>
                )}
              </div>

              {n.state === 'done' && <Check size={17} style={{ color: 'var(--success)', flexShrink: 0 }} />}
              {n.state === 'rejected' && <X size={17} style={{ color: 'var(--danger)', flexShrink: 0 }} />}
            </div>
          </div>
        );
      })}
    </div>
  );
}
