'use client';

import { useState } from 'react';
import { Check, X, Clock } from 'lucide-react';

export type StepState = 'done' | 'active' | 'pending' | 'rejected' | 'blocked';
export interface StepNode { key: string; label: string; state: StepState; hint?: string; icon?: React.ElementType }

const NODE: Record<StepState, { bg: string; color: string; ring: string }> = {
  done:     { bg: '#0f766e', color: '#fff', ring: 'transparent' },
  active:   { bg: '#2563eb', color: '#fff', ring: '#dbeafe' },
  pending:  { bg: '#f1f5f9', color: '#94a3b8', ring: 'transparent' },
  rejected: { bg: '#dc2626', color: '#fff', ring: 'transparent' },
  // Wartet auf Material (Nachschub läuft) – Amber, kein Häkchen/X, sondern «wartend».
  blocked:  { bg: '#fffbeb', color: '#b45309', ring: '#fde68a' },
};

const LINE_DONE = '#0f766e';
const LINE_PENDING = '#e2e8f0';

/** Knoten-Inhalt: erledigt → Haken, abgelehnt → X, sonst das Schritt-Symbol
 *  (Symbole statt Zahlen – auf einen Blick erkennbar), ersatzweise die Nummer. */
function nodeContent(n: StepNode, i: number) {
  if (n.state === 'done') return <Check size={15} />;
  if (n.state === 'rejected') return <X size={15} />;
  if (n.state === 'blocked') return <Clock size={15} />;
  if (n.icon) { const Icon = n.icon; return <Icon size={15} />; }
  return i + 1;
}

/** Horizontaler Prozess-Stepper. Eine Linie zwischen zwei Knoten gilt als
 *  erledigt, sobald der LINKE Knoten erledigt ist – beide Hälften nutzen
 *  dieselbe Regel, daher keine inkonsistenten Farben mehr.
 *  Optional klickbar (onSelect) mit Hervorhebung des gewählten Knotens. */
export function ProcessStepper({ nodes, selectedKey, onSelect }: {
  nodes: StepNode[];
  selectedKey?: string;
  onSelect?: (key: string) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
      {nodes.map((n, i) => {
        const node = NODE[n.state];
        const leftDone = i > 0 && nodes[i - 1].state === 'done';
        const rightDone = n.state === 'done';
        const selected = selectedKey === n.key;
        const clickable = !!onSelect;
        const showHint = hover === n.key && !!n.hint;
        return (
          <div key={n.key}
            onClick={clickable ? () => onSelect(n.key) : undefined}
            onMouseEnter={() => setHover(n.key)} onMouseLeave={() => setHover((h) => (h === n.key ? null : h))}
            style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 0, cursor: clickable ? 'pointer' : (n.hint ? 'help' : 'default') }}>
            {showHint && (
              <div style={{ position: 'absolute', bottom: '100%', marginBottom: 6, zIndex: 20, padding: '5px 9px', borderRadius: 6, background: '#0f172a', color: '#fff', fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap', boxShadow: '0 4px 12px rgba(0,0,0,0.18)', pointerEvents: 'none' }}>
                {n.hint}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <div style={{ flex: 1, height: 2, background: i === 0 ? 'transparent' : (leftDone ? LINE_DONE : LINE_PENDING) }} />
              <div style={{
                width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
                background: node.bg, color: node.color,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                boxShadow: selected ? '0 0 0 3px #0f172a' : (n.state === 'active' || n.state === 'blocked') ? `0 0 0 4px ${node.ring}` : 'none',
                transition: 'box-shadow 0.15s',
              }}>
                {nodeContent(n, i)}
              </div>
              <div style={{ flex: 1, height: 2, background: i === nodes.length - 1 ? 'transparent' : (rightDone ? LINE_DONE : LINE_PENDING) }} />
            </div>
            <div style={{
              marginTop: 5, fontSize: 10, lineHeight: 1.2, textAlign: 'center',
              fontWeight: selected || n.state === 'active' || n.state === 'blocked' ? 700 : 500,
              color: n.state === 'pending' ? '#94a3b8' : n.state === 'rejected' ? '#dc2626' : n.state === 'blocked' ? '#b45309' : '#0F172A',
            }}>
              {n.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}
