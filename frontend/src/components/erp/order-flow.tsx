'use client';

import { useState } from 'react';
import { ArrowUp, Boxes, Check, Clock3, CornerDownLeft, MapPin, Package, PauseCircle,
  X } from 'lucide-react';
import type { FlowLot, Order, OrderDeviationInfo, OrderOrigin, OrderStep, StepResolution,
  StepType, SubOrderStep } from '@/types';
import { STEP_META, stepStateLabel } from '@/lib/process';
import { TYPE_META } from '@/lib/erp-record';
import { unitLabel } from '@/lib/article';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { orderStatus } from '@/lib/record-status';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
import { FlowTerm, kindColor } from '@/components/erp/process-steps';
import { actorHint, formatObjectId } from '@/lib/utils';

// ─── Der Ablauf eines laufenden Auftrags ───────────────────────────────────────────
//
// **Drei Spuren – der eigene Prozess in der Mitte** (Notiz #419). Die Achse dieses Auftrags
// läuft senkrecht durch die Mitte; links liegt der Auftrag, aus dem er **hervorgegangen** ist
// (und wohin er zurückgibt), rechts die, die er **abgezweigt** hat.
//
// **EINE Linie, EINE Regel** (Notizen #422/#429): die volle schwarze Linie läuft durch alles,
// was passiert und abgeschlossen ist – bis zu dem Modul, das aussteht; ab dort Haarlinie.
// Das gilt **überall gleich**: auf der Achse, auf dem Weg in einen Abzweig hinein, in ihm
// drin und auf dem Weg zurück. Gestrichelte Linien gibt es nicht mehr – ein Abzweig ist ein
// gegangener Weg wie jeder andere, kein Sonderfall mit eigener Strichart.
//
// **Fork und Merge** (Notizen #417/#424): die Abzweigung verlässt die Achse waagrecht und geht
// **oben mittig** in den Unterprozess; unten führt sie wieder **zurück in die Achse**. Dazwischen
// läuft die Achse als **Bypass** weiter – und trägt genau das, was auf dem Hauptauftrag
// geblieben ist (Notiz #425): «2 gingen in die Abweichung, 2 blieben hier». Alle Ecken sind
// leicht gerundet (#423), aus EINEM Baustein (``Elbow``).
//
// **Keine Sonderbehandlung, ein System für alles** (Notiz #418): die Module eines Abzweigs
// sind dieselben ``StepCard``s wie auf der Hauptachse.
//
// **Auf einer Kante steht, WAS fliesst** (``FlowLotChip``, Notizen #413/#426): kurz «4 ×
// 100000595», im Hover Artikel, Standort und Menge – beide Objektnummern öffnen ihren
// Datensatz. Die Mengen werden **von unten nach oben** gerechnet: unten steht, was der Auftrag
// heute hält, und jeder Ast gibt seine Bilanz (rein − zurück) an die Kante über sich weiter.
// **Nur bis zum Fortschritt** (Notiz #421): was ein Modul später einmal führen wird, ist nicht
// vorhersehbar – darum trägt keine Kante unterhalb des aktuellen Punktes eine Menge.
//
// **Ruht der Auftrag, ruht der Fluss** (Notiz #378): kein Modul lässt sich öffnen und alle
// treten zurück. Eine eigene Strichart braucht es dafür nicht – dass es nicht weitergeht,
// sagt die Linie schon, indem sie an der offenen Stelle zur Haarlinie wird.

/** Breite der Hauptspur; die Modul-Karten füllen sie, die Seitenspuren teilen sich den Rest. */
const MAIN = 460;
/** Mindestbreite einer Seitenspur – darunter scrollt das Diagramm lieber, als zu zerdrücken. */
const LANE_MIN = 280;
/** Länge des senkrechten Einlaufs: von der Abzweigung oben mittig in den Unterprozess. */
const ARM = 34;
/** Eckenradius der Prozesslinie (Notiz #423). */
const BEND = 12;

export type FlowDecision = { missing: string; canAct: boolean; onDecide?: () => void };

function completionHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  return actorHint(s.completed_by ?? 'System', s.completed_at);
}

/** Wie viele Schritte am Anfang schon durch sind – die Länge der starken Linie (#422). */
function walkedSteps(steps: { state: string }[]): number {
  let n = 0;
  while (n < steps.length && steps[n].state === 'done') n++;
  return n;
}

const isOpen = (b: OrderDeviationInfo) => b.status === 'draft' || b.status === 'released';

// ─── Linien ───────────────────────────────────────────────────────────────────────

/**
 * **Die eine Linie in zwei Lesarten** (Notizen #422/#429): **stark** = hier ist der Prozess
 * durchgelaufen, **Haarlinie** = hier steht er noch aus. Beide durchgezogen – auch der Weg in
 * einen Abzweig und zurück, denn auch das ist ein gegangener Weg.
 */
const lineColor = (strong: boolean) => (strong ? 'var(--fg-2)' : 'var(--border-2)');
const lineW = (strong: boolean) => (strong ? 3 : 2);

/** Ein senkrechtes Stück Achse. */
function Axis({ h = 22, strong = false, grow = false }: {
  h?: number; strong?: boolean; grow?: boolean;
}) {
  return (
    <div style={{
      width: lineW(strong), flex: grow ? 1 : 'none', background: lineColor(strong),
      height: grow ? undefined : h, minHeight: grow ? h : undefined,
    }} />
  );
}

/**
 * **Eine Ecke der Prozesslinie** – waagrecht und senkrecht mit leicht gerundetem Übergang
 * (Notiz #423). Vier Richtungen, EIN Baustein: der Fork aus der Achse in einen Abzweig, der
 * Merge zurück, und dieselben zwei gespiegelt für Herkunft und Rückweg.
 *
 * Gezeichnet als zwei Rahmenkanten eines Kastens – dadurch ist die Rundung genau eine
 * ``border-radius`` und keine zweite Geometrie. Die senkrechte Kante wird um ihre halbe
 * Stärke versetzt, damit sie exakt auf der Mittellinie der Spur sitzt (auf der auch die
 * ``Axis`` des Unterprozesses steht).
 *
 * **Wie viele Ecken es sind, sagt die Sache** (Notizen #430/#431): Fork und Merge münden in
 * eine Achse, die darüber und darunter weiterläuft – das ist ein **T**, keine Ecke. Herkunft
 * und Rückweg dagegen treffen die Achse dort, wo sie **beginnt** bzw. **endet**: die Linie
 * biegt ab, also braucht sie auch dort einen Radius. Das zweite Kästchen ist genau
 * ``BEND``×``BEND`` gross, womit sein Rand ein reiner Viertelkreis ist.
 */
function Elbow({ dir, strong, height = ARM, span }: {
  /** out: Achse → Spurmitte hinaus · back: Spurmitte → Achse zurück */
  dir: 'fork-right' | 'merge-right' | 'in-from-left' | 'out-to-left';
  strong?: boolean; height?: number;
  /** Wie weit die waagrechte Kante über die Spur hinaus zur Achse reicht. */
  span: number;
}) {
  const w = lineW(!!strong);
  const line = `${w}px solid ${lineColor(!!strong)}`;
  const half = `calc(50% - ${w / 2}px)`;
  const base: React.CSSProperties = { position: 'absolute', pointerEvents: 'none' };
  if (dir === 'fork-right') {
    // Aus der Achse nach rechts, dann hinunter in den Unterprozess (T an der Achse).
    return <div style={{ ...base, height, top: 0, left: -span, right: half,
      borderTop: line, borderRight: line, borderTopRightRadius: BEND }} />;
  }
  if (dir === 'merge-right') {
    // Aus dem Unterprozess herunter, dann nach links zurück in die Achse (T an der Achse).
    return <div style={{ ...base, height, bottom: 0, left: -span, right: half,
      borderBottom: line, borderRight: line, borderBottomRightRadius: BEND }} />;
  }
  if (dir === 'in-from-left') {
    // Aus dem Eltern-Auftrag herunter, nach rechts – und an der Achse hinunter (#430).
    return (
      <>
        <div style={{ ...base, height: height - BEND, bottom: BEND, left: half,
          right: -(span - BEND), borderLeft: line, borderBottom: line,
          borderBottomLeftRadius: BEND }} />
        <div style={{ ...base, height: BEND, width: BEND, bottom: 0, right: -span,
          borderTop: line, borderRight: line, borderTopRightRadius: BEND }} />
      </>
    );
  }
  // Aus der Achse heraus (#431), nach links – und hinunter auf den Rückweg-Knoten.
  return (
    <>
      <div style={{ ...base, height: BEND, width: BEND, top: 0, right: -span,
        borderBottom: line, borderRight: line, borderBottomRightRadius: BEND }} />
      <div style={{ ...base, height: height - BEND, top: BEND, left: half,
        right: -(span - BEND), borderTop: line, borderLeft: line,
        borderTopLeftRadius: BEND }} />
    </>
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

/**
 * **Was oberhalb eines Astes noch dabei war** – die Kante darüber ist die Kante darunter plus
 * das, was gerade NICHT beim Auftrag ist.
 *
 * Der Unterschied hängt am Zustand des Astes, und genau daran hing Notiz #425: **läuft** er
 * noch, ist alles Hineingegangene weiterhin dort – oben waren also 4, wovon 2 in die
 * Abweichung gingen und 2 auf dem Hauptauftrag blieben. Ist er **durch**, sind die
 * zurückgekehrten Stücke längst im unteren Wert enthalten; fehlt nur noch, was unterwegs
 * verloren ging (verschrottet/verkauft/verbaut).
 */
function plusBalance(below: Lots, branches: OrderDeviationInfo[]): Lots {
  const out: Lots = new Map(below);
  for (const b of branches) {
    const into = lotsOf(b.flow_in ?? []);
    const back = lotsOf(b.flow_out ?? []);
    for (const [id, lot] of into) {
      const away = isOpen(b) ? lot.quantity : lot.quantity - (back.get(id)?.quantity ?? 0);
      if (away <= 0) continue;
      const cur = out.get(id);
      out.set(id, cur ? { ...cur, quantity: cur.quantity + away } : { ...lot, quantity: away });
    }
  }
  return out;
}

const qtyText = (l: FlowLot) => `${l.quantity}${l.unit ? ` ${unitLabel(l.unit)}` : ''}`;

/**
 * **Was hier fliesst – kurz, und im Hover vollständig** (Notiz #426).
 *
 * Kurz steht das, was den Verlauf trägt: **Menge × Instanz**. Alles Weitere – Artikel,
 * Standort, Einheit – erscheint erst beim Hovern, damit die Kante eine Kante bleibt und keine
 * Tabelle wird. Beide Objektnummern sind **klickbar**: die Instanz führt zum Stück, der
 * Artikel zur Gattung. Eine **rote Null** ist die wichtigste Aussage von allen: hier kam
 * nichts zurück.
 */
function FlowLotChip({ lot }: { lot: FlowLot }) {
  const nav = useErpNav();
  const [open, setOpen] = useState(false);
  const zero = lot.quantity <= 0;
  const tone = zero ? 'var(--danger)' : 'var(--fg-2)';
  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      <button type="button" onClick={(e) => { e.stopPropagation(); nav?.(lot.instance_object_id); }}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 9px',
          borderRadius: 999, background: '#fff', cursor: nav ? 'pointer' : 'default',
          border: `1px solid ${zero ? 'var(--danger)' : 'var(--border-1)'}`,
          font: '600 11.5px var(--font-mono), monospace', fontVariantNumeric: 'tabular-nums',
          color: tone, whiteSpace: 'nowrap',
        }}>
        {lot.quantity} × {formatObjectId(lot.instance_object_id)}
      </button>
      {open && (
        <span style={{
          position: 'absolute', zIndex: 60, top: '100%', left: '50%', transform: 'translateX(-50%)',
          marginTop: 6, padding: '8px 11px', borderRadius: 'var(--r-md)', background: '#fff',
          border: '1px solid var(--border-1)', boxShadow: 'var(--shadow-md)',
          display: 'flex', flexDirection: 'column', gap: 5,
          width: 'max-content', maxWidth: 300, textAlign: 'left',
        }}>
          <LotFact icon={Package} title="Artikel">
            {lot.article_object_id != null && <ObjId value={lot.article_object_id} />}
            {lot.article_name && <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{lot.article_name}</span>}
            {lot.article_object_id == null && !lot.article_name && <Dash />}
          </LotFact>
          <LotFact icon={MapPin} title="Standort">
            {lot.location_label
              ? <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{lot.location_label}</span>
              : <Dash />}
          </LotFact>
          <LotFact icon={Boxes} title="Menge">
            <span style={{ fontSize: 12, color: zero ? 'var(--danger)' : 'var(--fg-1)',
              fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{qtyText(lot)}</span>
          </LotFact>
        </span>
      )}
    </span>
  );
}

const Dash = () => <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>—</span>;

/** Eine Zeile der Hover-Karte: Symbol statt Beschriftung (Notiz #433), Wort im Hover. */
function LotFact({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <span title={title} style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
      <Icon size={13} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, minWidth: 0 }}>
        {children}
      </span>
    </span>
  );
}

/** Die Materialzeilen einer Kante; ab der vierten fasst «+N» zusammen. */
function FlowLots({ lots, small }: { lots: Lots; small?: boolean }) {
  const list = [...lots.values()];
  if (list.length === 0) return null;
  const shown = list.slice(0, 3);
  const rest = list.length - shown.length;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 3, margin: small ? '2px 0' : 0 }}>
      {shown.map((l) => <FlowLotChip key={l.instance_object_id} lot={l} />)}
      {rest > 0 && (
        <span title={list.slice(3).map((l) => `${qtyText(l)} · ${formatObjectId(l.instance_object_id)}`).join('\n')}
          style={{ font: '600 11px var(--font-body)', color: 'var(--fg-4)', cursor: 'help' }}>
          +{rest} weitere
        </span>
      )}
    </div>
  );
}

// ─── Der Fluss ────────────────────────────────────────────────────────────────────

export function OrderFlow({ steps, subOrders = [], origin, decision, paused = false,
  selectedId, onSelectStep, onOpenOrder, renderPanel, lots = [], orderObjectId }: {
  steps: OrderStep[];
  subOrders?: OrderDeviationInfo[];
  origin?: OrderOrigin | null;
  decision?: FlowDecision;
  paused?: boolean;
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
  /** Das Material des Auftrags (`OrderResponse.flow_lots`) – Grundlage der Kanten. */
  lots?: FlowLot[];
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
  const base: Lots = lotsOf(lots);
  const edges: Lots[] = new Array(nodes.length + 1);
  edges[nodes.length] = base;
  for (let i = nodes.length - 1; i >= 0; i--) {
    edges[i] = nodes[i].branches ? plusBalance(edges[i + 1], nodes[i].branches!) : edges[i + 1];
  }

  // **Wie weit ist der Fluss gegangen?** (#422) – die führenden erledigten Knoten. Knoten i ist
  // ERREICHT, wenn `i <= walked`, und DURCHLAUFEN, wenn `i < walked`. Genau bis dorthin ist die
  // Linie stark, und genau bis dorthin trägt eine Kante Material (#421).
  const nodeDone = (n: Node) => (n.step
    ? n.step.state === 'done'
    : (n.branches ?? []).every((b) => !isOpen(b)));
  let walked = 0;
  while (walked < nodes.length && nodeDone(nodes[walked])) walked++;

  let gateUsed = false;
  const rows: React.ReactNode[] = [];
  nodes.forEach((n, i) => {
    const reached = i <= walked;
    const passed = i < walked;
    rows.push(
      <Row key={`edge-${i}`}>
        <Axis strong={reached} />
        {reached && <FlowLots lots={edges[i]} />}
        <Axis strong={reached} />
      </Row>,
    );
    if (n.branches) {
      const open = n.branches.some(isOpen);
      const res = n.res ?? [];
      // **Nur die offene Entscheidung ist ein Knoten** (Notiz #434). «wartet» und die
      // getroffene Antwort waren reine Information – und die steht längst im Fluss: ein
      // offener Abzweig IST das Warten, eine Auflösung steht als Zeile an ihrem Schritt.
      const decide = res.length === 0 && !open && !gateUsed && !!decision;
      if (decide) gateUsed = true;
      rows.push(
        // **Fork · Bypass · Merge**: die Achse läuft neben dem Abzweig weiter und trägt, was
        // auf dem Hauptauftrag geblieben ist (Notiz #425).
        <Row key={`br-${n.branches[0].object_id}`}
          right={<BranchArm branches={n.branches} reached={reached} onOpen={onOpenOrder} />}>
          <Axis grow h={26} strong={reached} />
          {reached && <FlowLots lots={edges[i + 1]} small />}
          <Axis grow h={26} strong={passed} />
        </Row>,
      );
      if (decide || res.length > 0) {
        rows.push(
          <Row key={`gate-${n.branches[0].object_id}`}>
            <Axis h={10} strong={passed} />
            {decide ? <Gateway decision={decision} /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {res.map((r, k) => <ResolutionLine key={k} r={r} first />)}
              </div>
            )}
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
          <Axis h={10} strong={passed} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {n.res!.map((r, k) => <ResolutionLine key={k} r={r} first />)}
          </div>
        </Row>,
      );
    }
  });

  const done = walked === nodes.length;
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
            <Row><Axis h={18} strong /></Row>
          </>
        )}
        <Row><FlowTerm kind="start" /></Row>
        {rows}
        <Row key="edge-last">
          <Axis strong={done} />
          {done && <FlowLots lots={edges[nodes.length]} />}
          <Axis strong={done} />
        </Row>
        <Row><FlowTerm kind="end" /></Row>
        {origin?.returns_to_object_id != null && (
          <>
            <Row><Axis h={18} strong={done} /></Row>
            <Row left={<ReturnArm origin={origin} strong={done} onOpen={onOpenOrder} />} />
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

// ─── Abzweig: Fork · Unterprozess · Merge ─────────────────────────────────────────

/** Wie ein Unter-Auftrag heisst. Symbol und Zustand trägt seither sein eigener Prozess
 *  (#435) – hier bleibt nur das Wort für den Hover. */
const SUB_LABEL: Record<string, string> = {
  deviation: 'Abweichung', supply: 'Nachschub',
  provisioning: 'Bereitstellung', return: 'Retoure',
};

/** Die Abzweige an EINER Stelle der Achse – jeder mit seinem eigenen Fork und Merge. */
function BranchArm({ branches, reached, onOpen }: {
  branches: OrderDeviationInfo[]; reached: boolean; onOpen?: (id: number) => void;
}) {
  return (
    <div style={{ width: '100%', minWidth: 0, display: 'flex', flexDirection: 'column',
      gap: 22, padding: '8px 0' }}>
      {branches.map((b) => (
        <BranchCell key={b.object_id} info={b} reached={reached} onOpen={onOpen} />
      ))}
    </div>
  );
}

/**
 * **Fork und Merge** (Notizen #417/#424): die Linie verlässt die Achse waagrecht, geht **oben
 * mittig** in den Unterprozess – und unten wieder **zurück in die Achse**. Beide Ecken sind
 * gerundet (#423) und tragen dieselbe Regel wie jede andere Linie: stark, wenn dieser Weg
 * schon gegangen wurde (#429). Der Rückweg wird erst stark, wenn der Abzweig durch ist.
 */
function BranchCell({ info, reached, onOpen }: {
  info: OrderDeviationInfo; reached: boolean; onOpen?: (id: number) => void;
}) {
  const closed = !isOpen(info);
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0,
      paddingTop: ARM, paddingBottom: ARM }}>
      <Elbow dir="fork-right" strong={reached} span={MAIN / 2} />
      <SubProcess info={info} onOpen={onOpen} />
      <Elbow dir="merge-right" strong={reached && closed} span={MAIN / 2} />
    </div>
  );
}

/**
 * **Der Unterprozess – ein ganz regulärer Prozess** (Notizen #417/#418/#420).
 *
 * Kein Kasten, kein zweites Vokabular: sein Kopf sagt, welcher Auftrag das ist, darunter
 * laufen seine Module an derselben Linie wie auf der Hauptachse – stark bis dorthin, wo er
 * steht. Oben steht, was hineinfliesst; **was zurückkommt, steht erst da, wenn es zurück ist**
 * (Notiz #421) – vorher wäre es eine Vorhersage.
 *
 * Angeklickt wird der Datensatz: gearbeitet wird an einem Schritt immer in SEINEM Auftrag.
 */
function SubProcess({ info, onOpen }: { info: OrderDeviationInfo; onOpen?: (id: number) => void }) {
  const steps = info.steps ?? [];
  const label = SUB_LABEL[info.reason ?? 'deviation'] ?? SUB_LABEL.deviation;
  const cfg = orderStatus({ status: info.status as Order['status'], abort_into_id: info.abort_into_id });
  const started = info.status !== 'draft';
  const closed = !isOpen(info);
  const walked = walkedSteps(steps);
  const inLots = lotsOf(info.flow_in ?? []);
  const outLots = lotsOf(info.flow_out ?? []);
  const hint = `${label} ${formatObjectId(info.object_id)}`
    + `${info.name ? ` «${info.name}»` : ''} · ${cfg.label} – klicken zum Öffnen`;
  return (
    <div title={hint} onClick={() => onOpen?.(info.object_id)}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%',
        minWidth: 0, cursor: onOpen ? 'pointer' : 'default' }}>
      {inLots.size > 0 && (
        <>
          <FlowLots lots={inLots} small />
          <Axis h={10} strong={started} />
        </>
      )}
      <FlowTerm kind="start" size={30} />
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
              + ` · ${hint}`} />
        </div>
      ))}
      <Axis h={12} strong={started && walked === steps.length} />
      <FlowTerm kind="end" size={30} />
      {closed && outLots.size > 0 && (
        <>
          <Axis h={10} strong />
          <FlowLots lots={outLots} small />
        </>
      )}
    </div>
  );
}

/**
 * **Der Verweis auf einen anderen Auftrag** – woher dieser kam, wohin er zurückgibt
 * (Notizen #438/#439).
 *
 * Er trägt die **visuelle Identität eines Auftrags** aus der einen Quelle
 * (``lib/erp-record.TYPE_META.order``): dasselbe Symbol, dieselbe getönte Symbolfläche wie im
 * Feed und im Detail-Kopf. Ein Verweis auf einen Datensatz soll aussehen wie dieser Datensatz
 * – sonst muss man erst lesen, um zu erkennen, worauf man klickt. Die Anatomie ist die des
 * Detail-Kopfs: Symbol · Eyebrow · Name · Objektnummer.
 */
function OrderRefNode({ caption, objectId, name, icon: Dir, title, onClick }: {
  caption: string; objectId: number; name?: string | null;
  icon: React.ElementType; title: string; onClick?: () => void;
}) {
  const meta = TYPE_META.order;
  const Icon = meta.icon;
  return (
    <button type="button" onClick={onClick} title={title}
      style={{
        width: '100%', minWidth: 0, textAlign: 'left', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 11, padding: '10px 13px',
        border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
        background: '#fff', boxShadow: 'var(--shadow-sm)',
      }}>
      <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', flexShrink: 0,
        background: meta.bg, color: meta.fg,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={16} />
      </span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'block', font: '700 10px var(--font-body)',
          textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-4)' }}>
          {caption}
        </span>
        <span style={{ display: 'flex', alignItems: 'baseline', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ font: '800 13.5px var(--font-display)', letterSpacing: '-.01em',
            color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis',
            whiteSpace: 'nowrap' }}>{name || meta.label}</span>
          <span style={{ font: '500 11px var(--font-mono), monospace', color: 'var(--fg-4)',
            fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(objectId)}</span>
        </span>
      </span>
      <Dir size={14} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
    </button>
  );
}

// ─── Herkunft / Rückweg (links – der Auftrag, aus dem dieser hervorging) ──────────

/**
 * **Woher dieser Auftrag kam** (Notizen #409/#419/#427) – in der **linken** Spur, mit
 * derselben Ausführlichkeit wie ein Abzweig rechts: Kopf des Eltern-Auftrags, darunter **genau
 * der eine Schritt**, aus dem dieser Auftrag hervorging.
 *
 * Nicht mehr: der ganze Eltern-Prozess gehört in den Eltern-Auftrag, hier zählt die Stelle.
 * Dass davor noch mehr liegt, sagt eine dezente Zeile darüber («⋯ 2 Schritte davor») – der
 * Ausblick nach oben, ohne ihn auszubreiten.
 */
function OriginArm({ origin, onOpen }: { origin: OrderOrigin; onOpen?: (id: number) => void }) {
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingBottom: ARM }}>
      <OrderRefNode caption="Hervorgegangen aus" objectId={origin.order_object_id}
        name={origin.order_name} icon={ArrowUp}
        title={`Hervorgegangen aus ${origin.order_name ?? 'Auftrag'} – öffnen`}
        onClick={() => onOpen?.(origin.order_object_id)} />
      <Elbow dir="in-from-left" strong span={MAIN / 2} />
    </div>
  );
}

/** Wohin die Stücke beim Abschluss zurückgehen – derselbe Verweis, nur andersherum (#438). */
function ReturnArm({ origin, strong, onOpen }: {
  origin: OrderOrigin; strong?: boolean; onOpen?: (id: number) => void;
}) {
  const id = origin.returns_to_object_id as number;
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingTop: ARM }}>
      <Elbow dir="out-to-left" strong={strong} span={MAIN / 2} />
      <OrderRefNode caption="Gibt zurück an" objectId={id} name={origin.returns_to_name}
        icon={CornerDownLeft}
        title={`Gibt beim Abschluss zurück an ${origin.returns_to_name ?? 'Auftrag'} – öffnen`}
        onClick={() => onOpen?.(id)} />
    </div>
  );
}

// ─── Gate + Auflösung ─────────────────────────────────────────────────────────────

/**
 * **Die offene Entscheidung als Knoten im Fluss** – eine Raute ist im Flowchart das Zeichen
 * für «hier wird entschieden», und genau das ist hier zu tun.
 *
 * Die früheren Zustände «wartet» und «erledigt» sind entfallen (Notiz #434): sie waren
 * Information, die der Fluss ohnehin trägt – ein offener Abzweig IST das Warten, und was
 * entschieden wurde, steht als Auflösungszeile an seiner Stelle. Übrig bleibt, was man
 * anklicken kann.
 */
function Gateway({ decision }: { decision?: FlowDecision }) {
  const tone = 'var(--warning)';
  const body = (
    <>
      <span style={{ width: 26, height: 26, flex: 'none', transform: 'rotate(45deg)',
        borderRadius: 5, border: `1.5px solid ${tone}`, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <X size={12} style={{ transform: 'rotate(-45deg)', color: tone }} />
      </span>
      <span style={{ textAlign: 'center', font: '500 12px var(--font-body)', color: 'var(--fg-3)' }}>
        Es fehlt <b style={{ color: 'var(--fg-1)' }}>{decision?.missing}</b> · entscheiden
      </span>
    </>
  );
  const layout: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
    border: 'none', background: 'none', padding: 0, maxWidth: MAIN,
  };
  if (!decision?.canAct || !decision.onDecide) return <div style={layout}>{body}</div>;
  return (
    <button type="button" onClick={decision.onDecide} title="Unterdeckung entscheiden"
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
