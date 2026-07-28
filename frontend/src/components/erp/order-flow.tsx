'use client';

import { Truck, Check, Clock, X, PauseCircle } from 'lucide-react';
import type { OrderStep, StepType } from '@/types';
import { STEP_META } from '@/lib/process';
import { TONE, type StatusCfg } from '@/lib/status-flow';
import { StatusBadge } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { Connector, FlowTerm, STEP_MAXW, kindColor } from '@/components/erp/process-steps';

// ─── Der Ablauf eines laufenden Auftrags – dieselbe Darstellung wie die Definition ─
//
// Ein Prozess sieht überall gleich aus: der senkrechte BPMN-Fluss mit Start-/Endknoten und
// einer Karte je Modul – so, wie man ihn am Artikel definiert hat. Vorher war der laufende
// Auftrag ein waagrechter Punkte-Stepper: dieselbe Sache in einer zweiten Bildsprache, und
// man musste erst übersetzen, welcher Punkt welches Modul aus der Definition ist.
//
// Der einzige Unterschied zur Definition ist, was eine Karte ZEIGT: dort die Konfiguration,
// hier der **Zustand** (erledigt/in Arbeit/wartet/angehalten) und – im Hover – wer wann.
// Die abgeleiteten **Bereitstellungen** stehen als eigene Karten an ihrer Position im Fluss;
// sie sind Unter-Aufträge, kein Modul, und öffnen darum ihren Datensatz statt ein Panel.

const STATE_CFG: Record<string, StatusCfg> = {
  done:    { label: 'Erledigt',   ...TONE.done,    icon: Check },
  active:  { label: 'In Arbeit',  ...TONE.pending, icon: Clock },
  blocked: { label: 'Angehalten', ...TONE.pending, icon: PauseCircle },
  failed:  { label: 'Fehler',     ...TONE.danger,  icon: X },
  locked:  { label: 'Wartet',     color: 'var(--fg-4)', bg: 'var(--bg-3)', icon: Clock },
};

function stateCfg(state: string): StatusCfg {
  return STATE_CFG[state] ?? STATE_CFG.locked;
}

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

export function OrderFlow({ steps, selectedId, onSelectStep, onOpenOrder }: {
  steps: OrderStep[];
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
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
    const card = (
      <FlowCard
        key={`step-${s.id}`}
        type={s.step_type as StepType}
        label={meta.label}
        icon={meta.icon}
        detail={stepDetail(s)}
        state={s.state}
        hint={completionHint(s)}
        selected={selectedId === String(s.id)}
        onClick={() => onSelectStep(String(s.id))}
      />
    );
    // Position der Bereitstellung: vor der Ausführung (Ressource) oder danach
    // (Beschaffung/Verkauf) – die Regel steht im Backend, hier wird nur platziert.
    if (s.provisioning_stage === 'before') rows.push(...provisioningCards(s), card);
    else rows.push(card, ...provisioningCards(s));
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

function FlowCard({ type, label, icon: Icon, detail, state, hint, selected, onClick }: {
  type: StepType;
  label: string;
  icon: React.ElementType;
  detail?: React.ReactNode;
  state: string;
  hint?: string;
  selected?: boolean;
  onClick: () => void;
}) {
  const kc = kindColor(type);
  const cfg = stateCfg(state);
  // Ein noch nicht erreichter Schritt tritt zurück (kein Ampelton, gedämpfte Fläche) –
  // sichtbar bleibt er, aber er zieht keine Aufmerksamkeit auf sich.
  const waiting = state === 'locked';
  return (
    <div
      onClick={onClick}
      title={hint}
      style={{
        width: '100%', maxWidth: STEP_MAXW, cursor: 'pointer', textAlign: 'left',
        border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
        borderRadius: 'var(--r-lg)', background: waiting ? '#fff' : kc.bg,
        boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
        opacity: waiting ? 0.72 : 1,
        transition: 'box-shadow .16s, border-color .16s, opacity .16s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px' }}>
        <div style={{
          width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
          color: kc.fg, border: `1px solid ${kc.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={19} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{label}</span>
          {detail && <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>{detail}</div>}
        </div>
        <StatusBadge cfg={cfg} />
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
  if (s.state === 'active') return 'Jetzt an der Reihe';
  return undefined;
}
