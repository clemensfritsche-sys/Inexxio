'use client';

import { Truck, Check, X, PauseCircle, TriangleAlert } from 'lucide-react';
import type { OrderDeviationInfo, OrderStep, StepType } from '@/types';
import { STEP_META } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { Connector, FlowTerm, STEP_MAXW, kindColor } from '@/components/erp/process-steps';

// ─── Der Ablauf eines laufenden Auftrags – dieselbe Darstellung wie die Definition ─
//
// Ein Prozess sieht überall gleich aus: der senkrechte BPMN-Fluss mit Start-/Endknoten und
// einer Karte je Modul – so, wie man ihn am Artikel definiert hat. Der einzige Unterschied
// ist, was eine Karte ZEIGT und KANN:
//
//   Definition → die Konfiguration, sortierbar
//   Ablauf     → den Zustand, und die gewählte Karte **öffnet ihr Panel in sich selbst**
//                (der Schritt wird dort bearbeitet, wo er im Fluss steht – nicht in einem
//                abgespaltenen Container darunter).
//
// **Zustand ohne Text** (Notiz #88): erledigte und noch nicht erreichte Schritte treten
// zurück (ausgegraut), nur der aktive trägt seine Farbe. Dazu ein Symbol statt eines Wortes –
// Haken (erledigt), Pause (angehalten), Kreuz (Fehler). Der Hover nennt Wer/Wann.
//
// **Abweichungen** (Notiz #85) stehen als dezenter Abzweig an der Stelle, an der sie gemeldet
// wurden (``origin_step_id``) – sichtbar, aber ohne den Hauptfluss zu verstellen.

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

export function OrderFlow({ steps, selectedId, onSelectStep, onOpenOrder, renderPanel }: {
  steps: OrderStep[];
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
}) {
  if (steps.length === 0) return null;

  const rows: React.ReactNode[] = [];
  const provisioningCards = (s: OrderStep) => (s.provisionings ?? []).map((p) => (
    <FlowCard
      key={`prov-${p.object_id}`}
      type="movement"
      label="Bereitstellung"
      icon={Truck}
      detail={<>Material an seinen Ort bringen · <ObjId value={p.object_id} /></>}
      state={p.status === 'completed' ? 'done' : 'blocked'}
      onClick={() => onOpenOrder(p.object_id)}
    />
  ));

  for (const s of steps) {
    const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
    const selected = selectedId === String(s.id);
    const card = (
      <FlowCard
        key={`step-${s.id}`}
        type={s.step_type as StepType}
        label={meta.label}
        icon={meta.icon}
        detail={stepDetail(s)}
        state={s.state}
        hint={completionHint(s)}
        selected={selected}
        onClick={() => onSelectStep(String(s.id))}
      >
        {selected && renderPanel?.(s)}
      </FlowCard>
    );
    // Position der Bereitstellung: vor der Ausführung (Ressource) oder danach
    // (Beschaffung/Verkauf) – die Regel steht im Backend, hier wird nur platziert.
    if (s.provisioning_stage === 'before') rows.push(...provisioningCards(s), card);
    else rows.push(card, ...provisioningCards(s));
    // Abweichungen: dezenter Abzweig an genau dieser Stelle.
    for (const d of s.deviations ?? []) {
      rows.push(<DeviationBranch key={`dev-${d.object_id}`} info={d} onOpen={onOpenOrder} />);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <FlowTerm kind="start" />
      {rows.map((r, i) => (
        <div key={i} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Connector />
          {r}
        </div>
      ))}
      <Connector />
      <FlowTerm kind="end" />
    </div>
  );
}

// Zustands-Symbol statt Zustands-Wort. Kein Symbol für «aktiv» – dass ein Schritt dran ist,
// sagt bereits die Farbe (er ist der einzige, der nicht zurücktritt).
const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done:    { icon: Check,       color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed:  { icon: X,           color: 'var(--danger)' },
};

function FlowCard({ type, label, icon: Icon, detail, state, hint, selected, onClick, children }: {
  type: StepType;
  label: string;
  icon: React.ElementType;
  detail?: React.ReactNode;
  state: string;
  hint?: string;
  selected?: boolean;
  onClick: () => void;
  children?: React.ReactNode;
}) {
  const kc = kindColor(type);
  // «Nicht relevant» = erledigt oder noch nicht erreicht: die Karte tritt zurück (weisse
  // Fläche, gedämpft). Nur was JETZT dran ist (aktiv/angehalten/Fehler), trägt seine Farbe.
  const muted = state === 'done' || state === 'locked';
  const mark = STATE_MARK[state];
  const MarkIcon = mark?.icon;
  return (
    <div
      style={{
        width: '100%', maxWidth: STEP_MAXW,
        border: `1px solid ${selected ? 'var(--fg-1)' : muted ? 'var(--border-1)' : kc.border}`,
        borderRadius: 'var(--r-lg)', background: muted ? '#fff' : kc.bg,
        boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
        transition: 'box-shadow .16s, border-color .16s, opacity .16s',
      }}
    >
      <div onClick={onClick} title={hint}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px', cursor: 'pointer', opacity: muted ? 0.55 : 1 }}>
        <div style={{
          width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
          color: muted ? 'var(--fg-4)' : kc.fg, border: `1px solid ${muted ? 'var(--border-1)' : kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={19} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{label}</span>
          {detail && <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>{detail}</div>}
        </div>
        {MarkIcon && <MarkIcon size={18} style={{ color: mark.color, flexShrink: 0 }} />}
      </div>
      {/* Der Schritt wird DORT bearbeitet, wo er im Fluss steht – nicht in einem eigenen
          Container darunter. Gleiche Anatomie wie die Konfiguration in der Definition. */}
      {children && (
        <div style={{ borderTop: '1px solid var(--border-1)', padding: '14px 18px 16px', background: '#fff', borderRadius: '0 0 var(--r-lg) var(--r-lg)' }}>
          {children}
        </div>
      )}
    </div>
  );
}

// Abweichung als **Abzweig** vom Hauptfluss: schmaler als eine Modul-Karte, eingerückt und
// mit einem kurzen Aststück – sichtbar, ohne den Fluss zu verstellen.
function DeviationBranch({ info, onOpen }: { info: OrderDeviationInfo; onOpen: (id: number) => void }) {
  const open = info.status === 'draft' || info.status === 'released';
  return (
    <div style={{ width: '100%', maxWidth: STEP_MAXW, display: 'flex', justifyContent: 'flex-start', paddingLeft: 26 }}>
      <div style={{ display: 'flex', alignItems: 'stretch' }}>
        <div style={{ width: 18, borderLeft: '2px solid var(--border-2)', borderBottom: '2px solid var(--border-2)', borderBottomLeftRadius: 8, marginBottom: 13 }} />
        <button type="button" onClick={() => onOpen(info.object_id)}
          title={open ? 'Offene Abweichung – der Auftrag pausiert, bis sie geklärt ist' : 'Geklärte Abweichung'}
          style={{
            marginLeft: 8, display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer',
            padding: '5px 11px', borderRadius: 'var(--r-pill)', font: '600 12px var(--font-body)',
            border: `1px solid ${open ? 'var(--warning)' : 'var(--border-1)'}`,
            background: open ? 'var(--warning-bg)' : '#fff',
            color: open ? 'var(--warning)' : 'var(--fg-4)',
          }}>
          <TriangleAlert size={13} /> Abweichung <ObjId value={info.object_id} />
        </button>
      </div>
    </div>
  );
}

// Kurzzeile je Modul: WAS gerade Sache ist – nicht die Konfiguration (die steht am Artikel).
function stepDetail(s: OrderStep): React.ReactNode {
  if (s.state === 'blocked') {
    if ((s.provisioning_order_object_ids ?? []).length > 0) return 'Material ist unterwegs';
    return (s.shortfall ?? []).length > 0 ? 'Bestand fehlt' : 'Wartet auf Material';
  }
  if (s.state === 'failed') return 'Nicht bestanden – über die Abweichung klären';
  return undefined;
}
