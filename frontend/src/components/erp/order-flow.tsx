'use client';

import { Truck, Check, X, PauseCircle, TriangleAlert, PackagePlus, ClipboardList,
  CornerDownRight, Clock3 } from 'lucide-react';
import type { FlowLot, Order, OrderDeviationInfo, OrderOrigin, OrderStep, StepResolution,
  StepType, SubOrderStep } from '@/types';
import { STEP_META, stepStateLabel } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { orderStatus } from '@/lib/record-status';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
import { FlowTerm, kindColor } from '@/components/erp/process-steps';
import { actorHint, formatObjectId } from '@/lib/utils';

// ─── Der Ablauf eines laufenden Auftrags ───────────────────────────────────────────
//
// **Der Hauptprozess läuft in einer Achse – Abzweige hängen rechts daran.** Die Achse wird
// nie gekappt: sie führt von oben nach unten durch alle Module, und ein Unter-Auftrag
// (Abweichung · Nachschub · Bereitstellung) sitzt als **Ast** daneben. Damit bleibt der
// Prozess das, was er ist – eine Linie –, und der Abzweig stört sie nicht, er begleitet sie.
//
// **Auf jeder Kante steht, WAS fliesst** (``EdgePill``): «4 × 100000590». Nicht die Module
// sind die eigentliche Geschichte eines Auftrags, sondern das Material – welche Instanz, wie
// viel davon, und was unterwegs damit passiert. Genau daran sieht man, dass 2 Stück in eine
// Abweichung gingen und **0 zurückkamen**, weil sie verschrottet wurden (rote Pille).
// Die Mengen werden **von unten nach oben** gerechnet: unten steht, was der Auftrag heute
// hält, und jeder Ast gibt seine Bilanz (rein − zurück) an die Kante über sich weiter. So
// braucht es keine zweite Buchführung – der Fluss rechnet aus dem, was ohnehin dasteht.
//
// **Der Abzweig ist bewusst angeschnitten** (``BranchTeaser``): man sieht, dass es ihn gibt,
// welche Module er hat und wie weit er ist – aber nicht seinen Inhalt. Wer mehr will, klickt
// ihn an und ist im Datensatz. Ein Teaser, kein zweites Detailfenster.
//
// **Und in einem Unter-Auftrag geht der Blick zurück**: oben die Kette (``OrderChain``, wo
// stehe ich?), darüber der Eltern-Prozess als angeschnittener Teaser mit dem Ast, der zu
// diesem Auftrag führte. Dieselbe Bildsprache in beide Richtungen.
//
// **Ruht der Auftrag, ruht die Achse** (Notiz #378): die Module treten zurück, keines lässt
// sich öffnen, und die Achse wird gestrichelt – hier fliesst gerade nichts.

/** Breite der Hauptspur; die Modul-Karten zentrieren sich darin, Äste hängen rechts an. */
const MAIN = 430;
const BRANCH_MIN = 300;

export type FlowDecision = { missing: string; canAct: boolean; onDecide?: () => void };

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  return actorHint(s.completed_by ?? 'System', s.completed_at);
}

// ─── Materialfluss ────────────────────────────────────────────────────────────────

type Lots = Map<number, FlowLot>;

function lotsOf(list: FlowLot[]): Lots {
  const m: Lots = new Map();
  for (const l of list) {
    const cur = m.get(l.instance_object_id);
    m.set(l.instance_object_id, cur
      ? { ...cur, quantity: cur.quantity + l.quantity } : { ...l });
  }
  return m;
}

/** Bilanz eines Astes auf die Kante darüber: was er nahm, minus was er zurückgab. */
function plusBalance(below: Lots, branches: OrderDeviationInfo[]): Lots {
  const out: Lots = new Map(below);
  for (const b of branches) {
    const into = lotsOf(b.flow_in ?? []);
    const back = lotsOf(b.flow_out ?? []);
    for (const [id, lot] of into) {
      const lost = lot.quantity - (back.get(id)?.quantity ?? 0);
      if (lost <= 0) continue;
      const cur = out.get(id);
      out.set(id, cur ? { ...cur, quantity: cur.quantity + lost } : { ...lot, quantity: lost });
    }
  }
  return out;
}

/**
 * **Was auf dieser Kante fliesst** – «4 × 100000590».
 *
 * Mehrere Artikel und Instanzen sind der Normalfall: dann steht je Instanz eine Zeile, und
 * ab der vierten fasst «+N» zusammen (der Hover nennt sie vollständig). Eine **rote Null**
 * ist die wichtigste Aussage von allen: hier kam nichts zurück.
 */
function EdgePill({ lots, muted }: { lots: Lots; muted?: boolean }) {
  const list = [...lots.values()];
  if (list.length === 0) return null;
  const shown = list.slice(0, 3);
  const rest = list.length - shown.length;
  const all = list.map((l) => `${l.quantity} × ${formatObjectId(l.instance_object_id)}`
    + (l.article_name ? ` (${l.article_name})` : '')).join('\n');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      {shown.map((l) => {
        const zero = l.quantity <= 0;
        return (
          <span key={l.instance_object_id} title={all}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 9px',
              borderRadius: 999, background: '#fff', cursor: 'help',
              border: `1px solid ${zero ? 'var(--danger)' : 'var(--border-1)'}`,
              opacity: muted ? 0.5 : 1,
              font: '600 11.5px var(--font-mono), monospace', fontVariantNumeric: 'tabular-nums',
              color: zero ? 'var(--danger)' : 'var(--fg-2)', whiteSpace: 'nowrap',
            }}>
            {l.quantity} × {formatObjectId(l.instance_object_id)}
          </span>
        );
      })}
      {rest > 0 && (
        <span title={all} style={{ font: '600 11px var(--font-body)', color: 'var(--fg-4)', cursor: 'help' }}>
          +{rest} weitere
        </span>
      )}
    </div>
  );
}

/** Ein Stück Achse. Gestrichelt = hier fliesst gerade nichts. */
function Axis({ h = 22, dashed = false }: { h?: number; dashed?: boolean }) {
  return (
    <div style={dashed
      ? { width: 2, height: h, flex: 'none',
          backgroundImage: 'linear-gradient(var(--border-2) 55%, transparent 55%)',
          backgroundSize: '2px 7px' }
      : { width: 2, height: h, flex: 'none', background: 'var(--border-2)' }} />
  );
}

/** Eine Zeile des Flusses: links die Achse (Inhalt zentriert), rechts Platz für Äste. */
function Row({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', width: '100%', alignItems: 'stretch' }}>
      <div style={{ width: MAIN, flex: 'none', display: 'flex', flexDirection: 'column',
        alignItems: 'center', minWidth: 0 }}>
        {children}
      </div>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>{aside}</div>
    </div>
  );
}

// ─── Der Fluss ────────────────────────────────────────────────────────────────────

export function OrderFlow({ steps, subOrders = [], origin, decision, paused = false,
  selectedId, onSelectStep, onOpenOrder, renderPanel, instances = [], orderObjectId }: {
  steps: OrderStep[];
  subOrders?: OrderDeviationInfo[];
  origin?: OrderOrigin | null;
  decision?: FlowDecision;
  paused?: boolean;
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
  /** Das Material des Auftrags – Grundlage der Mengen auf der Achse. */
  instances?: { object_id?: number | null; article_id?: number | null; held_quantity?: number | null;
    quantity?: number | null }[];
  /** Für die Schritt-Nummer «100000589-01». */
  orderObjectId?: number | null;
}) {
  if (steps.length === 0 && !origin) return null;

  // Die Knoten der Achse, in Reihenfolge: Module und die Äste an ihrer Stelle.
  type Node = { step?: OrderStep; branches?: OrderDeviationInfo[]; res?: StepResolution[] };
  const nodes: Node[] = [];
  const claimed = new Set(steps.flatMap((s) => (s.sub_orders ?? []).map((d) => d.object_id)));
  const loose = subOrders.filter((x) => !claimed.has(x.object_id));
  if (loose.length) nodes.push({ branches: loose });
  for (const s of steps) {
    const subs = s.sub_orders ?? [];
    const before = subs.filter((x) => x.stage === 'before');
    const after = subs.filter((x) => x.stage === 'after');
    const res = s.resolutions ?? [];
    if (before.length) nodes.push({ branches: before, res });
    nodes.push({ step: s, res: before.length ? [] : res });
    if (after.length) nodes.push({ branches: after });
  }

  // **Mengen von unten nach oben**: unten steht, was der Auftrag heute hält; jeder Ast gibt
  // seine Bilanz an die Kante über sich weiter. Kante i liegt ÜBER Knoten i.
  const base: Lots = lotsOf(instances
    .filter((i) => i.object_id != null)
    .map((i) => ({ instance_object_id: i.object_id as number, article_id: i.article_id ?? null,
      article_name: null, quantity: i.held_quantity ?? i.quantity ?? 0, unit: null })));
  const edges: Lots[] = new Array(nodes.length + 1);
  edges[nodes.length] = base;
  for (let i = nodes.length - 1; i >= 0; i--) {
    edges[i] = nodes[i].branches ? plusBalance(edges[i + 1], nodes[i].branches!) : edges[i + 1];
  }

  let gateUsed = false;
  const rows: React.ReactNode[] = [];
  nodes.forEach((n, i) => {
    rows.push(
      <Row key={`edge-${i}`}>
        <Axis dashed={paused} />
        <EdgePill lots={edges[i]} muted={paused} />
        <Axis dashed={paused} />
      </Row>,
    );
    if (n.branches) {
      const open = n.branches.some((b) => b.status === 'draft' || b.status === 'released');
      const gate = gateFor(n.res ?? [], open, !gateUsed && !!decision);
      if (gate === 'decide') gateUsed = true;
      rows.push(
        <Row key={`br-${n.branches[0].object_id}`}
          aside={<BranchArm branches={n.branches} onOpen={onOpenOrder} />}>
          <div style={{ width: 2, flex: 1, minHeight: 40,
            backgroundImage: open ? 'linear-gradient(var(--border-2) 55%, transparent 55%)' : undefined,
            backgroundSize: open ? '2px 7px' : undefined,
            background: open ? undefined : 'var(--border-2)' }} />
        </Row>,
      );
      if (gate) {
        rows.push(
          <Row key={`gate-${n.branches[0].object_id}`}>
            <Axis h={10} dashed={paused} />
            <Gateway state={gate} decision={decision} resolutions={n.res ?? []} />
          </Row>,
        );
      }
      return;
    }
    const s = n.step!;
    const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
    const selected = selectedId === String(s.id) && !paused;
    rows.push(
      <Row key={`step-${s.id}`}>
        <StepCard step={s} label={meta.label} icon={meta.icon} selected={selected} muted={paused}
          orderObjectId={orderObjectId} index={i}
          onClick={paused ? undefined : () => onSelectStep(String(s.id))}>
          {selected && renderPanel?.(s)}
        </StepCard>
      </Row>,
    );
    if ((n.res ?? []).length > 0) {
      rows.push(
        <Row key={`res-${s.id}`}>
          <Axis h={10} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {n.res!.map((r, k) => <ResolutionLine key={k} r={r} first />)}
          </div>
        </Row>,
      );
    }
  });

  return (
    <div style={{ width: '100%', overflowX: 'hidden' }}>
      <div style={{ minWidth: MAIN + BRANCH_MIN, display: 'flex', flexDirection: 'column',
        alignItems: 'flex-start' }}>
        {origin && <OriginArm origin={origin} onOpen={onOpenOrder} />}
        <Row><FlowTerm kind="start" /></Row>
        {rows}
        <Row key="edge-last">
          <Axis dashed={paused} />
          <EdgePill lots={edges[nodes.length]} muted={paused} />
          <Axis dashed={paused} />
        </Row>
        <Row><FlowTerm kind="end" /></Row>
        {origin?.returns_to_object_id != null && (
          <ReturnArm origin={origin} onOpen={onOpenOrder} />
        )}
      </div>
    </div>
  );
}

// ─── Modul-Karte ──────────────────────────────────────────────────────────────────

const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done: { icon: Check, color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed: { icon: X, color: 'var(--danger)' },
  active: { icon: Clock3, color: 'var(--warning)' },
};

/**
 * Ein Modul auf der Achse. **Nummer und Kurzzeile**: die Nummer verankert den Schritt im
 * Auftrag («100000589-01» – dieselbe Systematik wie eine Positionsnummer), die Kurzzeile
 * sagt, was hier konkret Sache ist, ohne dass man das Panel öffnen muss.
 */
function StepCard({ step, label, icon: Icon, selected, muted: forced, orderObjectId, index,
  onClick, children }: {
  step: OrderStep; label: string; icon: React.ElementType;
  selected?: boolean; muted?: boolean; orderObjectId?: number | null; index: number;
  onClick?: () => void; children?: React.ReactNode;
}) {
  const kc = kindColor(step.step_type as StepType);
  const muted = forced || step.state === 'done' || step.state === 'locked';
  const mark = STATE_MARK[step.state];
  const MarkIcon = mark?.icon;
  const nr = orderObjectId != null
    ? `${formatObjectId(orderObjectId)}–${String(index + 1).padStart(2, '0')}` : null;
  return (
    <div style={{
      position: 'relative', width: '100%',
      border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
      borderRadius: 'var(--r-lg)', background: kc.bg,
      boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
      opacity: muted ? 0.55 : 1, transition: 'box-shadow .16s, border-color .16s, opacity .16s',
    }}>
      <div onClick={onClick} title={completionHint(step)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px',
          cursor: onClick ? 'pointer' : 'default' }}>
        <div style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', flexShrink: 0,
          background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={17} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ font: '800 15px var(--font-display)', letterSpacing: '-.01em',
              color: 'var(--fg-1)' }}>{label}</span>
            {nr && <span style={{ font: '500 11px var(--font-mono), monospace',
              color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' }}>{nr}</span>}
          </div>
          {stepDetail(step) && (
            <div style={{ marginTop: 2, fontSize: 12, color: 'var(--fg-3)' }}>{stepDetail(step)}</div>
          )}
        </div>
        {stepBadge(step)}
        {MarkIcon && <MarkIcon size={17} style={{ color: mark.color, flexShrink: 0 }} />}
      </div>
      {children && (
        <div style={{ borderTop: `1px solid ${kc.border}`, padding: '14px 16px 16px' }}>{children}</div>
      )}
    </div>
  );
}

// ─── Ast + Teaser ─────────────────────────────────────────────────────────────────

const SUB_META: Record<string, { label: string; icon: React.ElementType; open: string }> = {
  deviation: { label: 'Abweichung', icon: TriangleAlert,
    open: 'Offene Abweichung – ihr Stück fehlt dem Auftrag, bis sie geklärt ist' },
  supply: { label: 'Nachschub', icon: PackagePlus,
    open: 'Nachschub läuft – der Schritt wird von selbst wieder aktiv' },
  provisioning: { label: 'Bereitstellung', icon: Truck,
    open: 'Material wird an seinen Ort gebracht' },
  return: { label: 'Retoure', icon: CornerDownRight, open: 'Rücknahme + Gutschrift' },
};

/** Der Ast: ein waagrechter Strich von der Achse zu den Teasern, die daran hängen. */
function BranchArm({ branches, onOpen }: {
  branches: OrderDeviationInfo[]; onOpen?: (id: number) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', width: '100%', minWidth: 0 }}>
      <div style={{ width: MAIN / 2, marginLeft: -MAIN / 2, flex: 'none', height: 2,
        background: 'var(--border-2)' }} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10,
        padding: '8px 0' }}>
        {branches.map((b) => <BranchTeaser key={b.object_id} info={b} onOpen={onOpen} />)}
      </div>
    </div>
  );
}

/**
 * **Der angeschnittene Abzweig** – man sieht, dass es ihn gibt, welche Module er hat und wie
 * weit er ist; für den Inhalt klickt man ihn an und ist im Datensatz.
 *
 * Das Anschneiden ist Absicht, kein Platzmangel: ein Unter-Auftrag ist ein **eigener**
 * Datensatz mit eigenem Fenster. Ihn hier auszubreiten hiesse, dasselbe zweimal zu bauen –
 * und den Blick vom Hauptprozess wegzuziehen. Der Teaser nennt die Sache und öffnet sie.
 */
function BranchTeaser({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  const open = info.status === 'draft' || info.status === 'released';
  const meta = SUB_META[info.reason ?? 'deviation'] ?? SUB_META.deviation;
  const Icon = meta.icon;
  const tone = open ? 'var(--warning)' : 'var(--border-1)';
  const cfg = orderStatus({ status: info.status as Order['status'], abort_into_id: info.abort_into_id });
  return (
    <div style={{ position: 'relative', paddingTop: 9 }}>
      {/* Die Kennung sitzt auf dem Rand – wie ein Reiter am Ordner. */}
      <span style={{ position: 'absolute', left: 14, top: 0, zIndex: 1,
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '1px 8px',
        borderRadius: 999, border: `1px solid ${tone}`, background: '#fff',
        font: '600 11px var(--font-mono), monospace', fontVariantNumeric: 'tabular-nums',
        color: open ? 'var(--warning)' : 'var(--fg-3)' }}>
        <Icon size={11} /> {formatObjectId(info.object_id)}
      </span>
      <button type="button" onClick={() => onOpen?.(info.object_id)}
        title={`${meta.label} ${info.name ? `«${info.name}» ` : ''}– ${open ? meta.open : cfg.label}. Klicken zum Öffnen.`}
        style={{
          width: '100%', textAlign: 'left', cursor: 'pointer', padding: '14px 0 12px 14px',
          border: `1.5px dashed ${tone}`, borderRight: 'none',
          borderRadius: 'var(--r-lg) 0 0 var(--r-lg)',
          background: open ? 'var(--warning-bg)' : 'var(--bg-2)',
          opacity: open ? 1 : 0.7,
          // Rechts ausblenden statt abschneiden: der Kasten läuft aus dem Bild – die
          // Einladung, ihn zu öffnen, statt einer harten Kante.
          maskImage: 'linear-gradient(to right, #000 60%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to right, #000 60%, transparent 100%)',
        }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
          paddingRight: 14 }}>
          <span style={{ font: '700 13px var(--font-body)', color: 'var(--fg-1)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {info.name || meta.label}
          </span>
          <StatusBadge cfg={cfg} size={10} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 340 }}>
          {(info.steps ?? []).map((st) => <TeaserStep key={st.id} step={st} />)}
          {(info.steps ?? []).length === 0 && (
            <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>Noch kein Ablauf definiert</span>
          )}
        </div>
      </button>
    </div>
  );
}

/** Ein Modul im Teaser – dieselbe Anatomie, eine Nummer kleiner und nicht bedienbar. */
function TeaserStep({ step }: { step: SubOrderStep }) {
  const type = step.step_type as StepType;
  const sm = STEP_META[type] ?? STEP_META.purchase;
  const kc = kindColor(type);
  const Icon = sm.icon;
  const quiet = step.state === 'done' || step.state === 'locked';
  const mark = STATE_MARK[step.state];
  return (
    <div title={`${sm.label}: ${stepStateLabel(step.state)}`}
      style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px',
        border: `1px solid ${kc.border}`, borderRadius: 'var(--r-md)', background: '#fff',
        opacity: quiet ? 0.6 : 1 }}>
      <span style={{ width: 24, height: 24, borderRadius: 5, flexShrink: 0, background: kc.bg,
        border: `1px solid ${kc.border}`, color: kc.fg,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={12} />
      </span>
      <span style={{ font: '700 12.5px var(--font-body)', color: 'var(--fg-1)',
        whiteSpace: 'nowrap' }}>{sm.label}</span>
      {mark && <mark.icon size={13} style={{ color: mark.color, flexShrink: 0 }} />}
    </div>
  );
}

// ─── Herkunft / Rückweg (im Unter-Auftrag) ────────────────────────────────────────

/**
 * **Woher dieser Auftrag kam** – der Eltern-Prozess als angeschnittener Teaser, mit dem Ast,
 * der zu diesem Auftrag führte. Spiegelbild des Abzweigs von der anderen Seite: dort sieht
 * man den Abzweig neben der Achse, hier die Achse neben dem Abzweig.
 */
function OriginArm({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  const stepLabel = origin.step_type
    ? (STEP_META[origin.step_type as StepType]?.label ?? null) : null;
  return (
    <div style={{ display: 'flex', width: '100%', alignItems: 'stretch', marginBottom: 4 }}>
      <div style={{ width: MAIN, flex: 'none', display: 'flex', flexDirection: 'column',
        alignItems: 'flex-start', minWidth: 0 }}>
        <button type="button" onClick={() => onOpen?.(origin.order_object_id)}
          title={`Hervorgegangen aus ${origin.order_name ?? 'Auftrag'}`
            + (stepLabel ? ` · ${stepLabel}` : '') + ' – öffnen'}
          style={{
            position: 'relative', width: '100%', textAlign: 'left', cursor: 'pointer',
            padding: '18px 0 14px 14px', border: '1.5px dashed var(--border-2)',
            borderRadius: 'var(--r-lg)', background: 'var(--bg-2)', opacity: 0.85,
            maskImage: 'linear-gradient(to bottom, transparent 0, #000 22%, #000 100%)',
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, #000 22%, #000 100%)',
          }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginBottom: 8,
            padding: '1px 8px', borderRadius: 999, border: '1px solid var(--border-2)',
            background: '#fff', font: '600 11px var(--font-mono), monospace',
            fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)' }}>
            ↑ {formatObjectId(origin.order_object_id)}
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, opacity: 0.55 }}>
            {(origin.parent_steps ?? []).slice(-3).map((st) => <TeaserStep key={st.id} step={st} />)}
          </div>
        </button>
        {/* Der Ast, der von dort hierher führte. */}
        <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: 2, height: 22, background: 'var(--border-2)' }} />
        </div>
        {stepLabel && (
          <div style={{ width: '100%', textAlign: 'center', font: '500 11.5px var(--font-body)',
            color: 'var(--fg-4)', marginBottom: 4 }}>
            aus «{stepLabel}»
          </div>
        )}
      </div>
      <div style={{ flex: 1 }} />
    </div>
  );
}

/** Wohin die Stücke beim Abschluss zurückgehen. */
function ReturnArm({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  const id = origin.returns_to_object_id as number;
  return (
    <Row>
      <div style={{ width: 2, height: 20, background: 'var(--border-2)' }} />
      <button type="button" onClick={() => onOpen?.(id)}
        title={`Gibt beim Abschluss zurück an ${origin.returns_to_name ?? 'Auftrag'} – öffnen`}
        style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer',
          padding: '6px 12px', border: '1px dashed var(--border-2)', borderRadius: 999,
          background: 'transparent', font: '500 12px var(--font-body)', color: 'var(--fg-3)' }}>
        zurück an
        <span style={{ font: '600 12px var(--font-mono), monospace', color: 'var(--accent)',
          fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(id)}</span>
      </button>
    </Row>
  );
}

/**
 * **Wo stehe ich?** – die Kette vom Hauptauftrag bis hierher. Ein Abzweig kann selbst einen
 * Abzweig haben; ohne Kette weiss man nach zwei Sprüngen nicht mehr, in welchem Vorgang man
 * gelandet ist. Jede Station ausser der aktuellen ist ein Sprung zurück.
 */
export function OrderChain({ origin, currentObjectId, onOpen }: {
  origin?: OrderOrigin | null; currentObjectId?: number | null;
  onOpen?: (objectId: number) => void;
}) {
  const chain = origin?.chain ?? [];
  if (chain.length < 2) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 14 }}>
      {chain.map((c) => {
        const here = c.object_id === currentObjectId;
        const meta = SUB_META[c.reason ?? ''] ?? { label: 'Auftrag', icon: ClipboardList, open: '' };
        const Icon = meta.icon;
        return (
          <button key={c.object_id} type="button" disabled={here}
            onClick={() => onOpen?.(c.object_id)} title={c.name ?? undefined}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 11px',
              borderRadius: 999, cursor: here ? 'default' : 'pointer',
              border: `1px solid ${here ? 'var(--fg-1)' : 'var(--border-1)'}`,
              background: here ? 'var(--fg-1)' : '#fff',
              color: here ? '#fff' : 'var(--fg-2)', font: '600 12px var(--font-body)',
            }}>
            <Icon size={12} />
            {meta.label}
            <span style={{ font: '600 11.5px var(--font-mono), monospace',
              fontVariantNumeric: 'tabular-nums', opacity: 0.75 }}>
              {formatObjectId(c.object_id)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Gate + Auflösung ─────────────────────────────────────────────────────────────

function gateFor(res: StepResolution[], branchOpen: boolean, decidable: boolean) {
  if (res.length > 0) return 'resolved' as const;
  if (branchOpen) return 'waiting' as const;
  return decidable ? ('decide' as const) : null;
}

const GATE_TONE = { decide: 'var(--warning)', waiting: 'var(--fg-4)', resolved: 'var(--success)' };
const GATE_ICON = { decide: X, waiting: Clock3, resolved: Check };

/**
 * **Das Gate – wo die Entscheidung fällt und danach steht.** Eine Raute ist im Flowchart das
 * Zeichen für «hier wird entschieden»; genau das passiert hier. Offen ist sie anklickbar und
 * stellt die eine Frage, danach trägt sie die Antwort.
 */
function Gateway({ state, decision, resolutions = [] }: {
  state: 'decide' | 'waiting' | 'resolved';
  decision?: FlowDecision;
  resolutions?: StepResolution[];
}) {
  const tone = GATE_TONE[state];
  const Icon = GATE_ICON[state];
  const act = state === 'decide' ? decision : undefined;
  const body = (
    <>
      <span style={{ width: 26, height: 26, flex: 'none', transform: 'rotate(45deg)',
        borderRadius: 5, border: `1.5px solid ${tone}`, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={12} style={{ transform: 'rotate(-45deg)', color: tone }} />
      </span>
      <span style={{ textAlign: 'center', font: '500 12px var(--font-body)', color: 'var(--fg-3)' }}>
        {state === 'resolved'
          ? resolutions.map((r, i) => <ResolutionLine key={i} r={r} first />)
          : state === 'decide'
            ? <>Es fehlt <b style={{ color: 'var(--fg-1)' }}>{act?.missing}</b> · entscheiden</>
            : 'wartet'}
      </span>
    </>
  );
  const layout: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
    border: 'none', background: 'none', padding: 0, maxWidth: MAIN,
  };
  if (!act?.canAct || !act.onDecide) return <div style={layout}>{body}</div>;
  return (
    <button type="button" onClick={act.onDecide} title="Unterdeckung entscheiden"
      style={{ ...layout, cursor: 'pointer' }}>{body}</button>
  );
}

const RESOLUTION_TONE: Record<string, string> = {
  quantity_confirmed: 'var(--success)',
  covered_from_stock: 'var(--success)',
  share_taken: 'var(--warning)',
};

function ResolutionLine({ r, first = false }: { r: StepResolution; first?: boolean }) {
  const who = actorHint(r.by, r.at);
  const tone = RESOLUTION_TONE[r.kind] ?? 'var(--fg-3)';
  return (
    <div title={who} style={{ marginTop: first ? 0 : 3, display: 'flex', alignItems: 'center',
      gap: 5, flexWrap: 'wrap', justifyContent: 'center',
      font: '500 12px var(--font-body)', color: 'var(--fg-3)', cursor: who ? 'help' : 'default' }}>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: tone, flexShrink: 0 }} />
      {r.kind === 'quantity_confirmed' && (
        <span>Menge angepasst <b style={{ color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
          {r.quantity_from} → {r.quantity_to}</b></span>
      )}
      {r.kind === 'covered_from_stock' && <span><b>{r.quantity}</b> ab Lager ersetzt</span>}
      {r.kind === 'share_taken' && (
        <span><b>{r.quantity}</b> abgegeben
          {r.other_order_object_id != null && <> an <ObjId value={r.other_order_object_id} /></>}</span>
      )}
      {r.article_name && <span style={{ color: 'var(--fg-4)' }}>· {r.article_name}</span>}
    </div>
  );
}

// ─── Kurzangaben am Modul ─────────────────────────────────────────────────────────

/** Fachlicher Zwischenstand (Beschaffung/Verkauf) – aber nur, solange der Schritt läuft. */
function stepBadge(s: OrderStep): React.ReactNode {
  if (s.state === 'done') return null;
  const po = (s.purchases ?? [])[0];
  if (po?.status) return <StatusBadge cfg={purchaseStatusConfig(po.status)} size={10} />;
  const sale = (s.sales ?? [])[0];
  if (sale?.status) return <StatusBadge cfg={saleStatusConfig(sale.status)} size={10} />;
  return null;
}

/**
 * **Was hier konkret Sache ist** – eine Zeile, ohne das Panel zu öffnen.
 *
 * Sie kommt aus dem Embed, das der Schritt ohnehin trägt: Lieferant und Menge bei der
 * Beschaffung, Ziel bei der Bewegung, Prüfumfang bei der Datenerfassung. Nichts wird
 * dafür zusätzlich geladen.
 */
function stepDetail(s: OrderStep): React.ReactNode {
  if (s.state === 'failed') return 'Nicht bestanden – über die Abweichung klären';
  const po = (s.purchases ?? [])[0];
  if (po) {
    const bits = [po.quantity != null ? `${po.quantity} ${po.article_unit ?? ''}`.trim() : null,
      po.supplier_name ?? null].filter(Boolean);
    return bits.length ? bits.join(' · ') : undefined;
  }
  const mv = s.movement;
  if (mv?.target_location_label) return mv.target_location_label;
  const insp = s.inspection;
  if (insp?.required_count) {
    const done = (insp.samples ?? []).length;
    return `${done}/${insp.required_count} Proben`;
  }
  const disp = s.disposal;
  if (disp?.note) return disp.note;
  return undefined;
}
