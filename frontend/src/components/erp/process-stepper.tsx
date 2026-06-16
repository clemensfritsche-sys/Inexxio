'use client';

import { Check, X } from 'lucide-react';

export type StepState = 'done' | 'active' | 'pending' | 'rejected';
export interface StepNode { key: string; label: string; state: StepState; hint?: string }

const NODE: Record<StepState, { bg: string; color: string; ring: string }> = {
  done:     { bg: '#0f766e', color: '#fff', ring: 'transparent' },
  active:   { bg: '#2563eb', color: '#fff', ring: '#dbeafe' },
  pending:  { bg: '#f1f5f9', color: '#94a3b8', ring: 'transparent' },
  rejected: { bg: '#dc2626', color: '#fff', ring: 'transparent' },
};

const LINE_DONE = '#0f766e';
const LINE_PENDING = '#e2e8f0';

/** Horizontaler Prozess-Stepper. Eine Linie zwischen zwei Knoten gilt als
 *  erledigt, sobald der LINKE Knoten erledigt ist – beide Hälften nutzen
 *  dieselbe Regel, daher keine inkonsistenten Farben mehr. */
export function ProcessStepper({ nodes }: { nodes: StepNode[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
      {nodes.map((n, i) => {
        const node = NODE[n.state];
        const leftDone = i > 0 && nodes[i - 1].state === 'done';
        const rightDone = n.state === 'done';
        return (
          <div key={n.key} title={n.hint} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 0, cursor: n.hint ? 'help' : 'default' }}>
            <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <div style={{ flex: 1, height: 2, background: i === 0 ? 'transparent' : (leftDone ? LINE_DONE : LINE_PENDING) }} />
              <div style={{
                width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                background: node.bg, color: node.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                boxShadow: n.state === 'active' ? `0 0 0 4px ${node.ring}` : 'none',
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
  );
}
