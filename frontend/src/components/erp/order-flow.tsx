'use client';

import { ArrowUp, Check, ClipboardList, Clock3, CornerDownRight, PackagePlus, PauseCircle,
  TriangleAlert, Truck, X } from 'lucide-react';
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
// **Drei Spuren – der eigene Prozess in der Mitte** (Notiz #419). Die Achse dieses Auftrags
// läuft senkrecht durch die Mitte; links liegen die Aufträge, aus denen er **hervorgegangen**
// ist (und wohin er zurückgibt), rechts die, die er **abgezweigt** hat. Damit steht der eigene
// Prozess dort, wo der Blick ohnehin hinfällt, und beide Nachbarschaften haben ihren festen
// Platz – statt «Eltern oben, Kinder rechts».
//
// **Ein Abzweig geht oben mittig in seinen Unterprozess hinein** (Notiz #417): von der Achse
// waagrecht hinaus, dann senkrecht in die Mitte des Unterprozesses – und dort läuft die Linie
// **durch** ihn hindurch, von seinem Kopf über seine Module bis zu dem, was zurückkommt.
// Gestrichelt ist immer nur der Übergang zwischen zwei Aufträgen; der Prozess selbst – hier
// wie dort – ist eine durchgezogene Linie.
//
// **Keine Sonderbehandlung, ein System für alles** (Notiz #418): die Module eines Abzweigs
// sind dieselben ``StepCard``s wie auf der Hauptachse – gleiche Anatomie, gleiche Modulfarbe,
// gleiche Zustands-Symbole, gleiche Nummerierung («100000591–01»). Es gibt kein zweites,
// kleineres Vokabular mehr für «dasselbe, nur nebenan».
//
// **Und keinen Kasten um den Abzweig** (Notiz #420): was ihn zusammenhält, ist der Prozess
// selbst – sein Kopf (gestrichelt: ein anderer Auftrag), seine Linie, seine Module. Ein
// Container darum wäre ein zweiter Rahmen um etwas, das schon aus Karten besteht.
//
// **Was gegangen ist, ist eine starke Volllinie** (Notiz #416): die Achse zeigt den
// Fortschritt selbst – erledigte Abschnitte kräftig, der Rest als Haarlinie. So sieht man ohne
// ein einziges Wort, wie weit der Auftrag ist.
//
// **Auf jeder Kante steht, WAS fliesst** (``EdgePill``, Notiz #413): «4 × 100000590». Nicht
// die Module sind die eigentliche Geschichte eines Auftrags, sondern das Material. Die Mengen
// werden **von unten nach oben** gerechnet: unten steht, was der Auftrag heute hält, und jeder
// Ast gibt seine Bilanz (rein − zurück) an die Kante über sich weiter – keine zweite
// Buchführung. Am Abzweig stehen beide Zahlen direkt an ihm: was hineinging und was
// zurückkam; eine **rote Null** ist die wichtigste Aussage von allen.
//
// **Ruht der Auftrag, ruht die Achse** (Notiz #378): die Module treten zurück, keines lässt
// sich öffnen, und die Achse wird gestrichelt – hier fliesst gerade nichts.

/** Breite der Hauptspur; die Modul-Karten füllen sie, die Seitenspuren teilen sich den Rest. */
const MAIN = 460;
/** Mindestbreite einer Seitenspur – darunter scrollt das Diagramm lieber, als zu zerdrücken. */
const LANE_MIN = 280;
/** Länge des senkrechten Einlaufs: von der Abzweigung oben mittig in den Unterprozess. */
const ARM = 30;

export type FlowDecision = { missing: string; canAct: boolean; onDecide?: () => void };

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  return actorHint(s.completed_by ?? 'System', s.completed_at);
}

/** Wie viele Schritte am Anfang schon durch sind – die Länge der starken Linie (#416). */
function walkedSteps(steps: { state: string }[]): number {
  let n = 0;
  while (n < steps.length && steps[n].state === 'done') n++;
  return n;
}

const isOpen = (b: OrderDeviationInfo) => b.status === 'draft' || b.status === 'released';

// ─── Linien ───────────────────────────────────────────────────────────────────────

/**
 * **Die eine Linie in drei Lesarten.** Durchgezogen = der Prozess; **stark** = hier ist er
 * schon durchgelaufen (#416); **gestrichelt** = hier endet der eigene Ablauf und es geht in
 * einen anderen Auftrag über (Herkunft, Abzweig, Rückweg).
 */
function lineFill(strong: boolean, dashed: boolean): React.CSSProperties {
  const c = strong ? 'var(--fg-2)' : 'var(--border-2)';
  if (dashed) {
    return {
      backgroundImage: `linear-gradient(${c} 55%, transparent 55%)`,
      backgroundSize: '100% 7px',
    };
  }
  return { background: c };
}
const lineW = (strong: boolean) => (strong ? 3 : 2);

/**
 * **Der Übergang zwischen zwei Aufträgen** – die Abzweigung nach rechts, die Herkunft und der
 * Rückweg nach links. Immer gestrichelt (hier endet der eigene Ablauf), immer aus EINER
 * Stelle: waagrecht bis zur Spurmitte, dann senkrecht in den Prozess hinein bzw. hinaus.
 */
const LINK_H: React.CSSProperties = {
  position: 'absolute', height: 2,
  backgroundImage: 'linear-gradient(to right, var(--border-2) 55%, transparent 55%)',
  backgroundSize: '7px 100%',
};
const LINK_V: React.CSSProperties = {
  position: 'absolute', left: '50%', marginLeft: -1, width: 2, height: ARM,
  backgroundImage: 'linear-gradient(var(--border-2) 55%, transparent 55%)',
  backgroundSize: '100% 7px',
};

/** Ein senkrechtes Stück Achse. */
function Axis({ h = 22, strong = false, dashed = false, grow = false }: {
  h?: number; strong?: boolean; dashed?: boolean; grow?: boolean;
}) {
  return (
    <div style={{
      width: lineW(strong), flex: grow ? 1 : 'none',
      height: grow ? undefined : h, minHeight: grow ? h : undefined,
      ...lineFill(strong, dashed),
    }} />
  );
}

/** Eine Zeile des Flusses: die Achse in der Mitte, links Herkunft, rechts Abzweige. */
function Row({ children, left, right }: {
  children?: React.ReactNode; left?: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', width: '100%', alignItems: 'stretch' }}>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>{left}</div>
      <div style={{ width: MAIN, flex: 'none', display: 'flex', flexDirection: 'column',
        alignItems: 'center', minWidth: 0 }}>
        {children}
      </div>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>{right}</div>
    </div>
  );
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
function EdgePill({ lots, muted, small }: { lots: Lots; muted?: boolean; small?: boolean }) {
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
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: small ? '1px 8px' : '2px 9px',
              borderRadius: 999, background: '#fff', cursor: 'help',
              border: `1px solid ${zero ? 'var(--danger)' : 'var(--border-1)'}`,
              opacity: muted ? 0.5 : 1,
              font: `600 ${small ? 11 : 11.5}px var(--font-mono), monospace`,
              fontVariantNumeric: 'tabular-nums',
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

  // **Wie weit ist der Fluss gegangen?** (#416) – die führenden erledigten Knoten. Knoten i
  // ist durchlaufen, wenn `i < walked`; die Kante ÜBER ihm, wenn `i <= walked`.
  const nodeDone = (n: Node) => (n.step
    ? n.step.state === 'done'
    : (n.branches ?? []).every((b) => !isOpen(b)));
  let walked = 0;
  while (walked < nodes.length && nodeDone(nodes[walked])) walked++;

  let gateUsed = false;
  const rows: React.ReactNode[] = [];
  nodes.forEach((n, i) => {
    rows.push(
      <Row key={`edge-${i}`}>
        <Axis strong={i <= walked} dashed={paused} />
        <EdgePill lots={edges[i]} muted={paused} />
        <Axis strong={i <= walked} dashed={paused} />
      </Row>,
    );
    if (n.branches) {
      const open = n.branches.some(isOpen);
      const gate = gateFor(n.res ?? [], open, !gateUsed && !!decision);
      if (gate === 'decide') gateUsed = true;
      rows.push(
        <Row key={`br-${n.branches[0].object_id}`}
          right={<BranchArm branches={n.branches} onOpen={onOpenOrder} />}>
          <Axis grow h={40} strong={i < walked} dashed={paused || open} />
        </Row>,
      );
      if (gate) {
        rows.push(
          <Row key={`gate-${n.branches[0].object_id}`}>
            <Axis h={10} strong={i < walked} dashed={paused} />
            <Gateway state={gate} decision={decision} resolutions={n.res ?? []} />
          </Row>,
        );
      }
      return;
    }
    const s = n.step!;
    const selected = selectedId === String(s.id) && !paused;
    rows.push(
      <Row key={`step-${s.id}`}>
        <StepCard type={s.step_type as StepType} state={s.state} selected={selected} muted={paused}
          nr={stepNr(orderObjectId, i)} detail={stepDetail(s)} badge={stepBadge(s)}
          hint={completionHint(s)}
          onClick={paused ? undefined : () => onSelectStep(String(s.id))}>
          {selected && renderPanel?.(s)}
        </StepCard>
      </Row>,
    );
    if ((n.res ?? []).length > 0) {
      rows.push(
        <Row key={`res-${s.id}`}>
          <Axis h={10} strong={i < walked} dashed={paused} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {n.res!.map((r, k) => <ResolutionLine key={k} r={r} first />)}
          </div>
        </Row>,
      );
    }
  });

  const hasAside = !!origin || nodes.some((n) => !!n.branches);
  return (
    // Ein Diagramm darf breiter sein als eine Textspalte – aber es scrollt in seinem eigenen
    // Kasten, statt die Seite waagrecht zu schieben.
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <div style={{ width: '100%', minWidth: hasAside ? MAIN + 2 * LANE_MIN : MAIN,
        display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
        {origin && (
          <>
            <Row left={<OriginArm origin={origin} onOpen={onOpenOrder} />} />
            <Row><Axis h={18} dashed /></Row>
          </>
        )}
        <Row><FlowTerm kind="start" /></Row>
        {rows}
        <Row key="edge-last">
          <Axis strong={walked === nodes.length} dashed={paused} />
          <EdgePill lots={edges[nodes.length]} muted={paused} />
          <Axis strong={walked === nodes.length} dashed={paused} />
        </Row>
        <Row><FlowTerm kind="end" /></Row>
        {origin?.returns_to_object_id != null && (
          <>
            <Row><Axis h={18} dashed /></Row>
            <Row left={<ReturnArm origin={origin} onOpen={onOpenOrder} />} />
          </>
        )}
      </div>
    </div>
  );
}

const stepNr = (orderObjectId: number | null | undefined, index: number) =>
  (orderObjectId != null
    ? `${formatObjectId(orderObjectId)}–${String(index + 1).padStart(2, '0')}` : null);

// ─── Modul-Karte (EINE für den ganzen Fluss) ──────────────────────────────────────

const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done: { icon: Check, color: 'var(--success)' },
  blocked: { icon: PauseCircle, color: 'var(--warning)' },
  failed: { icon: X, color: 'var(--danger)' },
  active: { icon: Clock3, color: 'var(--warning)' },
};

/**
 * **Ein Modul im Fluss – überall dasselbe** (Notiz #418).
 *
 * Ob es auf der Hauptachse steht oder im Prozess eines Abzweigs, ändert nichts an ihm:
 * gleiche Anatomie (Symbolkasten · Name · Nummer · Kurzzeile · Zustand), gleiche Modulfarbe,
 * gleiche Zustands-Symbole. Was ein Abzweig nicht mitliefert (Kurzzeile, Beleg-Status), bleibt
 * schlicht leer – das ist ein fehlendes Detail, kein anderes Bauteil.
 *
 * **Nummer und Kurzzeile**: die Nummer verankert den Schritt in seinem Auftrag
 * («100000589–01» – dieselbe Systematik wie eine Positionsnummer), die Kurzzeile sagt, was
 * hier konkret Sache ist, ohne dass man das Panel öffnen muss.
 */
function StepCard({ type, state, nr, detail, badge, hint, selected, muted: forced, compact,
  onClick, children }: {
  type: StepType; state: string; nr?: string | null;
  detail?: React.ReactNode; badge?: React.ReactNode; hint?: string;
  selected?: boolean; muted?: boolean; compact?: boolean;
  onClick?: () => void; children?: React.ReactNode;
}) {
  const meta = STEP_META[type] ?? STEP_META.purchase;
  const Icon = meta.icon;
  const kc = kindColor(type);
  const muted = forced || state === 'done' || state === 'locked';
  const mark = STATE_MARK[state];
  const MarkIcon = mark?.icon;
  const box = compact ? 28 : 34;
  return (
    <div style={{
      position: 'relative', width: '100%',
      border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
      borderRadius: 'var(--r-lg)', background: kc.bg,
      boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
      opacity: muted ? 0.55 : 1, transition: 'box-shadow .16s, border-color .16s, opacity .16s',
    }}>
      <div onClick={onClick} title={hint}
        style={{ display: 'flex', alignItems: 'center', gap: compact ? 10 : 12,
          padding: compact ? '10px 13px' : '13px 16px',
          cursor: onClick ? 'pointer' : 'default' }}>
        <div style={{ width: box, height: box, borderRadius: 'var(--r-sm)', flexShrink: 0,
          background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={compact ? 15 : 17} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ font: `800 ${compact ? 13.5 : 15}px var(--font-display)`,
              letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{meta.label}</span>
            {nr && <span style={{ font: '500 11px var(--font-mono), monospace',
              color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' }}>{nr}</span>}
          </div>
          {detail && <div style={{ marginTop: 2, fontSize: 12, color: 'var(--fg-3)' }}>{detail}</div>}
        </div>
        {badge}
        {MarkIcon && <MarkIcon size={compact ? 15 : 17} style={{ color: mark.color, flexShrink: 0 }} />}
      </div>
      {children && (
        <div style={{ borderTop: `1px solid ${kc.border}`, padding: '14px 16px 16px' }}>{children}</div>
      )}
    </div>
  );
}

// ─── Abzweig: die Abzweigung + der Unterprozess ───────────────────────────────────

const SUB_META: Record<string, { label: string; icon: React.ElementType; open: string }> = {
  deviation: { label: 'Abweichung', icon: TriangleAlert,
    open: 'Offene Abweichung – ihr Stück fehlt dem Auftrag, bis sie geklärt ist' },
  supply: { label: 'Nachschub', icon: PackagePlus,
    open: 'Nachschub läuft – der Schritt wird von selbst wieder aktiv' },
  provisioning: { label: 'Bereitstellung', icon: Truck,
    open: 'Material wird an seinen Ort gebracht' },
  return: { label: 'Retoure', icon: CornerDownRight, open: 'Rücknahme + Gutschrift' },
};

/** Die Abzweige an EINER Stelle der Achse – jeder mit seiner eigenen Abzweigung. */
function BranchArm({ branches, onOpen }: {
  branches: OrderDeviationInfo[]; onOpen?: (id: number) => void;
}) {
  return (
    <div style={{ width: '100%', minWidth: 0, display: 'flex', flexDirection: 'column',
      gap: 20, padding: '10px 0' }}>
      {branches.map((b) => <BranchCell key={b.object_id} info={b} onOpen={onOpen} />)}
    </div>
  );
}

/**
 * **Die Abzweigung** (Notiz #417): von der Achse waagrecht hinaus bis zur **Mitte** der
 * Seitenspur, dort senkrecht **oben mittig** in den Unterprozess hinein. Gestrichelt, weil
 * hier ein Auftrag in einen anderen übergeht – die Linie IM Unterprozess ist wieder
 * durchgezogen, denn dort läuft ein ganz normaler Prozess.
 */
function BranchCell({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingTop: ARM }}>
      {/* waagrecht: von der Achse (halbe Hauptspur nach links) bis zur Mitte dieser Spur */}
      <div style={{ ...LINK_H, top: 0, left: -MAIN / 2, right: '50%' }} />
      {/* senkrecht: oben mittig in den Unterprozess */}
      <div style={{ ...LINK_V, top: 0 }} />
      <SubProcess info={info} onOpen={onOpen} />
    </div>
  );
}

/**
 * **Der Unterprozess – ein ganz regulärer Prozess** (Notizen #417/#418/#420).
 *
 * Kein Kasten, kein zweites Vokabular: sein Kopf sagt, welcher Auftrag das ist (gestrichelt –
 * ein anderer Datensatz), darunter laufen seine Module an derselben durchgezogenen Linie wie
 * auf der Hauptachse. Oben steht, was hineinfliesst, unten was zurückkommt – und wenn dort
 * eine rote Null steht, ist unterwegs etwas verloren gegangen.
 *
 * Angeklickt wird der Datensatz: gearbeitet wird an einem Schritt immer in SEINEM Auftrag.
 */
function SubProcess({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  const steps = info.steps ?? [];
  const meta = SUB_META[info.reason ?? 'deviation'] ?? SUB_META.deviation;
  const cfg = orderStatus({ status: info.status as Order['status'], abort_into_id: info.abort_into_id });
  const started = info.status !== 'draft';
  const walked = walkedSteps(steps);
  const inLots = lotsOf(info.flow_in ?? []);
  const outLots = lotsOf(info.flow_out ?? []);
  const go = () => onOpen?.(info.object_id);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%',
      minWidth: 0 }}>
      {inLots.size > 0 && (
        <>
          <EdgePill lots={inLots} small />
          <Axis h={10} strong={started} />
        </>
      )}
      <BranchHead info={info} onOpen={onOpen} />
      {steps.length === 0 ? (
        <>
          <Axis h={12} />
          <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>Noch kein Ablauf definiert</span>
        </>
      ) : steps.map((st: SubOrderStep, i: number) => (
        <div key={st.id} style={{ width: '100%', display: 'flex', flexDirection: 'column',
          alignItems: 'center' }}>
          <Axis h={12} strong={started && i <= walked} />
          <StepCard compact type={st.step_type as StepType} state={st.state}
            nr={stepNr(info.object_id, i)}
            hint={`${STEP_META[st.step_type as StepType]?.label ?? ''}: ${stepStateLabel(st.state)}`
              + ` · ${meta.label} ${cfg.label} – klicken zum Öffnen`}
            onClick={go} />
        </div>
      ))}
      {outLots.size > 0 && (
        <>
          <Axis h={10} strong={started && walked === steps.length} />
          <EdgePill lots={outLots} small />
        </>
      )}
    </div>
  );
}

/**
 * **Der Kopf des Abzweigs** – welcher Auftrag hier abgeht, und wie es um ihn steht.
 *
 * Dieselbe Anatomie wie ein Modul (Symbolkasten · Name · Nummer · Zustand), aber **gestrichelt
 * umrandet**: das ist die im Fluss bereits etablierte Bedeutung für «gehört nicht zu dieser
 * Linie». Damit braucht der Abzweig keinen Container – der Kopf sagt, wo er anfängt, und die
 * Linie hält ihn zusammen (Notiz #420).
 */
function BranchHead({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  const open = isOpen(info);
  const meta = SUB_META[info.reason ?? 'deviation'] ?? SUB_META.deviation;
  const Icon = meta.icon;
  const tone = open ? 'var(--warning)' : 'var(--border-2)';
  const cfg = orderStatus({ status: info.status as Order['status'], abort_into_id: info.abort_into_id });
  return (
    <button type="button" onClick={() => onOpen?.(info.object_id)}
      title={`${meta.label} ${info.name ? `«${info.name}» ` : ''}– ${open ? meta.open : cfg.label}. Klicken zum Öffnen.`}
      style={{
        width: '100%', minWidth: 0, textAlign: 'left', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
        border: `1.5px dashed ${tone}`, borderRadius: 'var(--r-lg)',
        background: open ? 'var(--warning-bg)' : 'var(--bg-1)',
      }}>
      <span style={{ width: 28, height: 28, borderRadius: 'var(--r-sm)', flexShrink: 0,
        background: '#fff', border: `1px solid ${tone}`,
        color: open ? 'var(--warning)' : 'var(--fg-3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={15} />
      </span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ font: '800 13.5px var(--font-display)', letterSpacing: '-.01em',
            color: 'var(--fg-1)' }}>{meta.label}</span>
          <span style={{ font: '500 11px var(--font-mono), monospace', color: 'var(--fg-4)',
            fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(info.object_id)}</span>
        </span>
        {info.name && (
          <span style={{ display: 'block', marginTop: 1, fontSize: 12, color: 'var(--fg-3)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{info.name}</span>
        )}
      </span>
      <StatusBadge cfg={cfg} size={10} />
    </button>
  );
}

// ─── Herkunft / Rückweg (links – der Auftrag, aus dem dieser hervorging) ──────────

/**
 * **Woher dieser Auftrag kam** (Notizen #409/#419) – der Eltern-Prozess in der **linken**
 * Spur, mit der Abzweigung, die zu diesem Auftrag führte. Spiegelbild des Abzweigs: dort
 * verlässt die Linie die Achse nach rechts, hier mündet sie von links in sie ein.
 */
function OriginArm({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  const stepLabel = origin.step_type
    ? (STEP_META[origin.step_type as StepType]?.label ?? null) : null;
  const parentSteps = (origin.parent_steps ?? []).slice(-3);
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingBottom: ARM }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%',
        opacity: 0.75 }}>
        <ParentHead origin={origin} onOpen={onOpen} />
        {parentSteps.map((st: SubOrderStep) => (
          <div key={st.id} style={{ width: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center' }}>
            <Axis h={12} />
            <StepCard compact type={st.step_type as StepType} state={st.state}
              hint={`${STEP_META[st.step_type as StepType]?.label ?? ''}: ${stepStateLabel(st.state)}`}
              onClick={() => onOpen?.(origin.order_object_id)} />
          </div>
        ))}
      </div>
      {stepLabel && (
        <div style={{ textAlign: 'center', marginTop: 7, font: '500 11.5px var(--font-body)',
          color: 'var(--fg-4)' }}>
          Abzweig aus «{stepLabel}»
        </div>
      )}
      {/* senkrecht aus der Mitte nach unten … */}
      <div style={{ ...LINK_V, bottom: 0 }} />
      {/* … und waagrecht in die Achse. */}
      <div style={{ ...LINK_H, bottom: 0, left: '50%', right: -MAIN / 2 }} />
    </div>
  );
}

/** Der Kopf des Eltern-Auftrags – dieselbe Anatomie wie ein Abzweig-Kopf, nur nach oben. */
function ParentHead({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  const meta = SUB_META[origin.order_reason ?? ''] ?? { label: 'Auftrag', icon: ClipboardList, open: '' };
  const Icon = meta.icon;
  return (
    <button type="button" onClick={() => onOpen?.(origin.order_object_id)}
      title={`Hervorgegangen aus ${origin.order_name ?? 'Auftrag'} – öffnen`}
      style={{
        width: '100%', minWidth: 0, textAlign: 'left', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
        border: '1.5px dashed var(--border-2)', borderRadius: 'var(--r-lg)',
        background: 'var(--bg-1)',
      }}>
      <span style={{ width: 28, height: 28, borderRadius: 'var(--r-sm)', flexShrink: 0,
        background: '#fff', border: '1px solid var(--border-2)', color: 'var(--fg-3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={15} />
      </span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ font: '800 13.5px var(--font-display)', letterSpacing: '-.01em',
            color: 'var(--fg-1)' }}>{meta.label}</span>
          <span style={{ font: '500 11px var(--font-mono), monospace', color: 'var(--fg-4)',
            fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(origin.order_object_id)}</span>
        </span>
        {origin.order_name && (
          <span style={{ display: 'block', marginTop: 1, fontSize: 12, color: 'var(--fg-3)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {origin.order_name}
          </span>
        )}
      </span>
      <ArrowUp size={14} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
    </button>
  );
}

/** Wohin die Stücke beim Abschluss zurückgehen – der Rückweg, ebenfalls nach links. */
function ReturnArm({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  const id = origin.returns_to_object_id as number;
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingTop: ARM }}>
      {/* waagrecht aus der Achse … */}
      <div style={{ ...LINK_H, top: 0, left: '50%', right: -MAIN / 2 }} />
      {/* … und senkrecht auf die Pille. */}
      <div style={{ ...LINK_V, top: 0 }} />
      <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
        <button type="button" onClick={() => onOpen?.(id)}
          title={`Gibt beim Abschluss zurück an ${origin.returns_to_name ?? 'Auftrag'} – öffnen`}
          style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer',
            padding: '6px 12px', border: '1px dashed var(--border-2)', borderRadius: 999,
            background: 'transparent', font: '500 12px var(--font-body)', color: 'var(--fg-3)' }}>
          zurück an
          <span style={{ font: '600 12px var(--font-mono), monospace', color: 'var(--accent)',
            fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(id)}</span>
        </button>
      </div>
    </div>
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

// (`SubOrderStep` trägt bewusst kein Label – Modul-Name und Zustandswort kommen aus der EINEN
//  Quelle `lib/process.ts`, die gegen `domain/event_types.py` getestet ist.)
