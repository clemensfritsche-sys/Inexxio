'use client';

import { Check, X } from 'lucide-react';

export type StepState = 'done' | 'active' | 'pending' | 'rejected';
export interface StepNode { key: string; label: string; state: StepState }

const TONE: Record<StepState, { bg: string; color: string; line: string }> = {
  done:     { bg: '#0f766e', color: '#fff', line: '#0f766e' },
  active:   { bg: '#2563eb', color: '#fff', line: '#2563eb' },
  pending:  { bg: '#f1f5f9', color: '#94a3b8', line: '#e2e8f0' },
  rejected: { bg: '#dc2626', color: '#fff', line: '#dc2626' },
};

/** Horizontaler Prozess-Stepper: zeigt erledigte / aktuelle / offene Schritte. */
export function ProcessStepper({ nodes }: { nodes: StepNode[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
      {nodes.map((n, i) => {
        const tone = TONE[n.state];
        const prev = i > 0 ? nodes[i - 1] : null;
        return (
          <div key={n.key} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 0 }}>
            {/* Knoten + Verbindungslinien */}
            <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <div style={{ flex: 1, height: 2, background: prev ? TONE[prev.state].line : 'transparent' }} />
              <div style={{
                width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                background: tone.bg, color: tone.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                boxShadow: n.state === 'active' ? '0 0 0 4px #dbeafe' : 'none',
              }}>
                {n.state === 'done' ? <Check size={14} /> : n.state === 'rejected' ? <X size={14} /> : i + 1}
              </div>
              <div style={{ flex: 1, height: 2, background: i < nodes.length - 1 ? TONE[nodes[i + 1].state].line : 'transparent' }} />
            </div>
            {/* Label */}
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
