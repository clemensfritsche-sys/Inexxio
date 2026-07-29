'use client';

import { Truck, Check, X, PauseCircle, TriangleAlert, PackagePlus } from 'lucide-react';
import type { OrderDeviationInfo, OrderStep, StepType } from '@/types';
import { STEP_META } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
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
// **Abweichungen** (Notizen #85, #175, #178) gehören **an den Schritt, den sie unterbrochen
// haben** – nicht davor, nicht danach und nicht IN ihm. Eine Abweichung ist kein Knoten in der
// Reihenfolge (dann läse sie sich als «danach»), aber auch kein Teil des Moduls (sie ist das,
// was das Modul unterbrochen hat). Sie hängt darum **seitlich an der Karte, auf deren Höhe** –
// verbunden durch ein kurzes Aststück. Auf schmalen Schirmen rutscht sie unter die Karte
// (`.erp-devbranch`), weil daneben kein Platz mehr ist.
//
// Eine Abweichung OHNE Ursprungsschritt (an der Instanz gemeldet, oder bevor ein Schritt aktiv
// war) gehört keinem Schritt – sie gehört dem Auftrag und steht darum als eigener Abzweig
// **vor** dem ersten Schritt, am Anfang des Flusses.

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

export function OrderFlow({ steps, deviations = [], selectedId, onSelectStep, onOpenOrder, renderPanel }: {
  steps: OrderStep[];
  /** Alle Abweichungen des Auftrags – die ohne Ursprungsschritt stehen vor dem Fluss. */
  deviations?: OrderDeviationInfo[];
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
}) {
  if (steps.length === 0) return null;

  const rows: React.ReactNode[] = [];

  // Was kein Schritt für sich beansprucht, gehört dem Auftrag – und steht am Anfang.
  const claimed = new Set(steps.flatMap((s) => (s.deviations ?? []).map((d) => d.object_id)));
  for (const d of deviations.filter((x) => !claimed.has(x.object_id))) {
    rows.push(<DeviationBranch key={`dev-order-${d.object_id}`} info={d} onOpen={onOpenOrder} />);
  }
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
        badge={stepBadge(s)}
        state={s.state}
        hint={completionHint(s)}
        selected={selected}
        deviations={s.deviations ?? []}
        onOpenOrder={onOpenOrder}
        onClick={() => onSelectStep(String(s.id))}
      >
        {selected && renderPanel?.(s)}
      </FlowCard>
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

// Zustands-Symbol statt Zustands-Wort. Kein Symbol für «aktiv» – dass ein Schritt dran ist,
// sagt bereits die Farbe (er ist der einzige, der nicht zurücktritt).
const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done:    { icon: Check,       color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed:  { icon: X,           color: 'var(--danger)' },
};

function FlowCard({ type, label, icon: Icon, detail, badge, state, hint, selected, deviations, onOpenOrder, onClick, children }: {
  type: StepType;
  label: string;
  icon: React.ElementType;
  detail?: React.ReactNode;
  /** Fachlicher Zustand des Moduls (z. B. «Angefragt») – im Kopf, wo der Zustand hingehört. */
  badge?: React.ReactNode;
  state: string;
  hint?: string;
  selected?: boolean;
  deviations?: OrderDeviationInfo[];
  onOpenOrder?: (objectId: number) => void;
  onClick: () => void;
  children?: React.ReactNode;
}) {
  const kc = kindColor(type);
  // «Nicht relevant» = erledigt oder noch nicht erreicht: die Karte tritt zurück (weisse
  // Fläche, gedämpft). Nur was JETZT dran ist (aktiv/angehalten/Fehler), trägt seine Farbe.
  const muted = state === 'done' || state === 'locked';
  const mark = STATE_MARK[state];
  const MarkIcon = mark?.icon;
  const branch = deviations ?? [];
  return (
    <div
      style={{
        position: 'relative', width: '100%', maxWidth: STEP_MAXW,
        border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
        borderRadius: 'var(--r-lg)', background: kc.bg,
        boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
        // Zurücktreten heisst gedämpft, nicht farblos: die Karte behält ihre Modulfarbe und
        // verliert nur an Kraft. Weiss hätte einem erledigten Schritt seine Zugehörigkeit
        // genommen – man sähe im Rückblick nicht mehr, welches Modul dort stand.
        opacity: muted ? 0.5 : 1,
        transition: 'box-shadow .16s, border-color .16s, opacity .16s',
      }}
    >
      <div onClick={onClick} title={hint}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px', cursor: 'pointer' }}>
        <div style={{
          width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff',
          color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={19} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{label}</span>
          {detail && <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>{detail}</div>}
        </div>
        {badge}
        {MarkIcon && <MarkIcon size={18} style={{ color: mark.color, flexShrink: 0 }} />}
      </div>
      {/* Der Schritt wird DORT bearbeitet, wo er im Fluss steht – nicht in einem eigenen
          Container darunter. Gleiche Anatomie wie die Konfiguration in der Definition. */}
      {children && (
        <div style={{ borderTop: `1px solid ${kc.border}`, padding: '14px 18px 16px' }}>
          {children}
        </div>
      )}

      {/* Was diesen Schritt unterbrochen hat – NEBEN der Karte, auf ihrer Höhe (Notiz #178). */}
      {branch.length > 0 && (
        <div className="erp-devbranch">
          {branch.map((d) => <DeviationPill key={d.object_id} info={d} onOpen={onOpenOrder} />)}
        </div>
      )}
    </div>
  );
}

// Abweichung OHNE Ursprungsschritt: als **Abzweig** am Anfang des Flusses – eingerückt und
// mit kurzem Aststück, sichtbar, ohne den Fluss zu verstellen.
function DeviationBranch({ info, onOpen }: { info: OrderDeviationInfo; onOpen: (id: number) => void }) {
  return (
    <div style={{ width: '100%', maxWidth: STEP_MAXW, display: 'flex', justifyContent: 'flex-start', paddingLeft: 26 }}>
      <div style={{ display: 'flex', alignItems: 'stretch' }}>
        <div style={{ width: 18, borderLeft: '2px solid var(--border-2)', borderBottom: '2px solid var(--border-2)', borderBottomLeftRadius: 8, marginBottom: 13 }} />
        <span style={{ marginLeft: 8 }}><DeviationPill info={info} onOpen={onOpen} /></span>
      </div>
    </div>
  );
}

/**
 * Die EINE Darstellung eines Unter-Auftrags im Fluss – offen (gelb) oder erledigt (still).
 *
 * Abweichung **und** Nachschub sind dasselbe Muster: aus einem Schritt hervorgegangen, an
 * seiner Stelle sichtbar (Notizen #259/#260). Nur Symbol und Wort unterscheiden sie – die
 * Abweichung ist ein Problem (Warnzeichen), der Nachschub eine Beschaffung (Paket).
 */
function DeviationPill({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  const open = info.status === 'draft' || info.status === 'released';
  const supply = info.reason === 'supply';
  const Icon = supply ? PackagePlus : TriangleAlert;
  return (
    <button type="button" onClick={() => onOpen?.(info.object_id)}
      title={supply
        ? (open ? 'Nachschub läuft – der Schritt wird von selbst wieder aktiv' : 'Erledigter Nachschub')
        : (open ? 'Offene Abweichung – der Auftrag pausiert, bis sie geklärt ist' : 'Geklärte Abweichung')}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer',
        padding: '5px 11px', borderRadius: 'var(--r-pill)', font: '600 12px var(--font-body)',
        border: `1px solid ${open ? 'var(--warning)' : 'var(--border-1)'}`,
        background: open ? 'var(--warning-bg)' : '#fff',
        color: open ? 'var(--warning)' : 'var(--fg-4)',
      }}>
      <Icon size={13} /> {supply ? 'Nachschub' : 'Abweichung'} <ObjId value={info.object_id} />
    </button>
  );
}

/**
 * Fachlicher Zustand eines Moduls für seinen **Kopf** (Notiz #247): Beschaffung und Verkauf
 * haben einen eigenen Fortschritt (Angefragt → Offeriert → Bestellt → Geliefert), und der
 * gehört dorthin, wo man ihn ohne Öffnen sieht – nicht in die Fläche des Panels.
 */
function stepBadge(s: OrderStep): React.ReactNode {
  const po = (s.purchases ?? [])[0];
  if (po?.status) return <StatusBadge cfg={purchaseStatusConfig(po.status)} size={10} />;
  const sale = (s.sales ?? [])[0];
  if (sale?.status) return <StatusBadge cfg={saleStatusConfig(sale.status)} size={10} />;
  return null;
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
