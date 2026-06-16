'use client';

import { useState } from 'react';
import { Check, X, Truck } from 'lucide-react';

export type PState = 'done' | 'active' | 'pending' | 'rejected';
export interface PNode { key: string; label: string; state: PState; hint?: string }
export interface Delivery { pct: number; label: string; overdue: boolean; oi: number }

const NODE: Record<PState, { bg: string; color: string; ring: string }> = {
  done:     { bg: '#0f766e', color: '#fff', ring: 'transparent' },
  active:   { bg: '#2563eb', color: '#fff', ring: '#dbeafe' },
  pending:  { bg: '#f1f5f9', color: '#94a3b8', ring: 'transparent' },
  rejected: { bg: '#dc2626', color: '#fff', ring: 'transparent' },
};
const LINE_DONE = '#0f766e';
const LINE_PENDING = '#e2e8f0';

/** Purchase-Fortschritt mit Audit-Hover je Knoten und animierter Lieferung
 *  auf der Verbindungslinie zwischen «Bestellt» und «Wareneingang». */
export function PurchaseProgress({ nodes, delivery }: { nodes: PNode[]; delivery?: Delivery }) {
  const [hover, setHover] = useState<string | null>(null);
  const N = nodes.length;

  return (
    <div style={{ position: 'relative' }}>
      <style>{`
        @keyframes inexxio-truck { 0%,100% { transform: translate(-50%, -1px); } 50% { transform: translate(-50%, 1px); } }
        @keyframes inexxio-flow { from { background-position: 0 0; } to { background-position: 14px 0; } }
      `}</style>

      <div style={{ display: 'flex', alignItems: 'flex-start' }}>
        {nodes.map((n, i) => {
          const c = NODE[n.state];
          const leftDone = i > 0 && nodes[i - 1].state === 'done';
          const rightDone = n.state === 'done';
          return (
            <div key={n.key} style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 0 }}
              onMouseEnter={() => setHover(n.key)} onMouseLeave={() => setHover((h) => (h === n.key ? null : h))}>
              {/* Audit-Tooltip */}
              {hover === n.key && n.hint && (
                <div style={{
                  position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
                  marginBottom: 6, background: '#0f172a', color: '#fff', fontSize: 11, lineHeight: 1.3,
                  padding: '6px 9px', borderRadius: 7, whiteSpace: 'nowrap', zIndex: 20,
                  boxShadow: '0 6px 18px rgba(0,0,0,0.18)',
                }}>
                  {n.hint}
                  <div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', width: 0, height: 0, borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderTop: '4px solid #0f172a' }} />
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <div style={{ flex: 1, height: 2, background: i === 0 ? 'transparent' : (leftDone ? LINE_DONE : LINE_PENDING) }} />
                <div style={{
                  width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                  background: c.bg, color: c.color, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700, cursor: n.hint ? 'help' : 'default',
                  boxShadow: n.state === 'active' ? `0 0 0 4px ${c.ring}` : 'none',
                }}>
                  {n.state === 'done' ? <Check size={14} /> : n.state === 'rejected' ? <X size={14} /> : i + 1}
                </div>
                <div style={{ flex: 1, height: 2, background: i === nodes.length - 1 ? 'transparent' : (rightDone ? LINE_DONE : LINE_PENDING) }} />
              </div>
              <div style={{
                marginTop: 5, fontSize: 10, lineHeight: 1.2, textAlign: 'center',
                fontWeight: n.state === 'active' ? 700 : 500,
                color: n.state === 'pending' ? '#94a3b8' : n.state === 'rejected' ? '#dc2626' : '#0F172A',
              }}>
                {n.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* Lieferungs-Animation auf der Linie zwischen «Bestellt» und «Wareneingang» */}
      {delivery && (
        <div style={{ position: 'absolute', top: 0, height: 26, left: `${((delivery.oi + 0.5) / N) * 100}%`, width: `${(1 / N) * 100}%` }}>
          {/* animierte Füll-Linie */}
          <div style={{ position: 'absolute', top: 12, left: 0, width: `${delivery.pct}%`, height: 2,
            background: delivery.overdue
              ? 'repeating-linear-gradient(90deg,#dc2626,#dc2626 6px,#fca5a5 6px,#fca5a5 12px)'
              : 'repeating-linear-gradient(90deg,#2563eb,#2563eb 6px,#93c5fd 6px,#93c5fd 12px)',
            animation: 'inexxio-flow 0.8s linear infinite' }} />
          {/* Lieferwagen */}
          <div style={{ position: 'absolute', top: 13, left: `${delivery.pct}%`, animation: 'inexxio-truck 1.2s ease-in-out infinite' }}>
            <Truck size={14} style={{ color: delivery.overdue ? '#dc2626' : '#2563eb' }} />
          </div>
          {/* Restzeit-Label */}
          <div style={{ position: 'absolute', top: -15, left: '50%', transform: 'translateX(-50%)', whiteSpace: 'nowrap',
            fontSize: 9, fontWeight: 700, color: delivery.overdue ? '#dc2626' : '#2563eb' }}>
            {delivery.label}
          </div>
        </div>
      )}
    </div>
  );
}
