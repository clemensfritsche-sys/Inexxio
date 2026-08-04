'use client';

import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { UnitList } from '@/components/erp/unit-numbers';
import { ArrowDown, ArrowRight, ArrowUp, Check, ClipboardPlus, Hash, MapPin, Package, Redo2,
  Scissors, X } from 'lucide-react';
import type { AffectedOrder, FlowEdge, FlowLot, FlowNode, MaterialOrder, Order,
  OrderDeviationInfo, OrderOrigin, OrderStep, StepResolution, StepType, SubOrderStep } from '@/types';
import { STEP_META, instanceStatusConfig, stepStateLabel } from '@/lib/process';
import { TYPE_META } from '@/lib/erp-record';
import { unitLabel } from '@/lib/article';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';
import { orderStatus } from '@/lib/record-status';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { saleStatusConfig } from '@/lib/sale';
import { FlowTerm, kindColor } from '@/components/erp/process-steps';
import { ARM, Axis, BEND, Elbow, LANE, MAIN, RUN, Row, SIDE, aside }
  from '@/components/erp/flow-line';
import { actorHint, formatObjectId } from '@/lib/utils';

// ─── Der Ablauf eines laufenden Auftrags ───────────────────────────────────────────
//
// **Drei Spuren – der eigene Prozess in der Mitte** (Notiz #419). Die Achse dieses Auftrags
// läuft senkrecht durch die Mitte; links liegt der Auftrag, aus dem er **hervorgegangen** ist
// (und wohin er zurückgibt), rechts die, die er **abgezweigt** hat.
//
// **EINE Linie, EINE Regel** (Notizen #422/#429): die volle schwarze Linie läuft durch alles,
// was passiert und abgeschlossen ist – bis zu dem Modul, das aussteht; ab dort Haarlinie.
// Gestrichelte Linien gibt es nicht – ein Abzweig ist ein gegangener Weg wie jeder andere.
// **Die Achse ist dabei ein Präfix, ein Abzweig nicht:** «bis zur offenen Stelle» setzt eine
// Reihenfolge voraus, und zwischen gleichzeitig laufenden Ästen gibt es keine. Zu **jedem**
// gestarteten Ast ist ein Weg gegangen worden, also ist zu jedem die Linie voll.
//
// **Fork und Merge** (Notizen #417/#424): die Abzweigung verlässt die Achse waagrecht und geht
// **oben mittig** in die Abzweig-Spur; unten führt sie wieder **zurück in die Achse**. Dazwischen
// läuft die Achse als **Bypass** weiter – und trägt genau das, was dem Auftrag geblieben ist
// (Notizen #425/#469). Mehrere Äste an derselben Stelle sind **EINE Teilung in mehrere
// Richtungen**: ein Fork, ein Merge, und sie hängen untereinander in der Spur. Alle Ecken sind
// leicht gerundet (#423), aus EINEM Baustein (``Elbow``).
//
// **Keine Sonderbehandlung, ein System für alles** (Notiz #418): die Module eines Abzweigs
// sind dieselben ``StepCard``s wie auf der Hauptachse.
//
// **Auf einer Kante steht, WAS fliesst** (``FlowLotChip``, Notizen #413/#426): kurz «4 ×
// 100000595» mit der **Ampelfarbe der Instanz** (#481), im Hover Zustand, Artikel und
// Standort – beide Objektnummern öffnen ihren Datensatz. Die Mengen werden **von oben nach
// unten** gerechnet: oben steht das Material des Auftrags – eine Tatsache, die sich nicht
// ändert –, und an jeder Teilung geht ab, was abzweigt. **Nur bis zum Fortschritt** (Notiz
// #421): was ein Modul später einmal führen wird, ist nicht vorhersehbar.
//
// **Ruht der Auftrag, ruht der Fluss** (Notiz #378): kein Modul lässt sich öffnen und alle
// treten zurück. Eine eigene Strichart braucht es dafür nicht – dass es nicht weitergeht,
// sagt die Linie schon, indem sie an der offenen Stelle zur Haarlinie wird.

// ─── Materialfluss (nur Anzeige – gerechnet wird im Backend) ──────────────────────
//
// **Das Frontend zeichnet, der Server weiss** (ADR 007): die Kanten kommen fertig aus
// `OrderResponse.flow_edges`/`flow_nodes` – Material im Zustand von damals, Fortschritt,
// Prozess-Punkt. Die frühere Client-Arithmetik (minus/plus/Stichtags-Zeitmaschine) ist
// ersatzlos entfallen; jede Abweichung von der Server-Sicht war eine Testnotiz.

/** Ist diese Menge endgültig aus dem Bestand? (nur für die Rückweg-Anzeige) */
const isGone = (l: FlowLot) =>
  l.disposition === 'scrapped' || l.disposition === 'sold' || l.disposition === 'consumed';

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

/**
 * **Eintritts-Sicht** einer Abzweig-Kante: oben am Unterprozess steht, was hineinging – im
 * Zustand von damals (Zeilen mit Zeitstempel fallen in «gehalten» zurück, #488). Reine
 * Projektion EINER Liste, keine Verrechnung zweier Quellen.
 */
function asEntry(lots: FlowLot[]): FlowLot[] {
  const out: FlowLot[] = [];
  const back = new Map<number, FlowLot>();
  for (const l of lots) {
    if (l.at) {
      const cur = back.get(l.instance_object_id);
      if (cur) {
        cur.quantity += l.quantity;
        cur.units = [...(cur.units ?? []), ...(l.units ?? [])];
        cur.unit_count = (cur.unit_count ?? 0) + (l.unit_count ?? 0);
      }
      else back.set(l.instance_object_id, { ...l, quality: null, disposition: 'in_process',
        reserved: false, at: null });
    } else out.push(l);
  }
  // **Eine Menge, ein Zustand, EINE Zeile** (Notiz #520): was zurückgedreht wird, gehört zu
  // dem, was ohnehin in Arbeit ist – sonst steht dieselbe Instanz zweimal auf der Kante.
  for (const [oid, row] of back) {
    const same = out.find((l) => l.instance_object_id === oid
      && (l.disposition ?? 'in_process') === 'in_process');
    if (same) {
      same.quantity += row.quantity;
      same.units = [...(same.units ?? []), ...(row.units ?? [])];
      same.unit_count = (same.unit_count ?? 0) + (row.unit_count ?? 0);
    }
    else out.push(row);
  }
  return out;
}

const qtyText = (l: FlowLot) => `${l.quantity}${l.unit ? ` ${unitLabel(l.unit)}` : ''}`;

/**
 * **Die Objektnummer inklusive Zusatz** (Testnotiz #532) – welche Stücke die Menge
 * ausmacht, nicht nur aus welcher Instanz sie stammt.
 *
 * Zusammenhängende Nummern werden zu einer Spanne (`…-1…-4`), damit die Kante eine Kante
 * bleibt; die vollständige Liste steht im Hover. Kennt die Zeile ihre Stücke nicht
 * (abgegangene Mengen – ihre Nummern sind entwertet, eine geratene Zuordnung wäre
 * schlimmer als keine), bleibt es bei der blossen Objektnummer.
 */
function lotNumbers(l: FlowLot): string {
  const us = l.units ?? [];
  if (!us.length) return formatObjectId(l.instance_object_id);
  const idx = us.map((u) => Number(u.number.split('-')[1] ?? 0)).sort((a, b) => a - b);
  const head = formatObjectId(l.instance_object_id);
  const contiguous = idx.every((n, i) => i === 0 || n === idx[i - 1] + 1);
  const complete = (l.unit_count ?? us.length) === us.length;
  if (idx.length === 1) return `${head}-${idx[0]}`;
  if (contiguous && complete) return `${head}-${idx[0]}…-${idx[idx.length - 1]}`;
  return `${head}-${idx[0]}…`;
}

/**
 * **Der Prozessbaum: woher das Material kam, wohin es weiterging** (Testnotiz #493).
 *
 * Ein Auftrag ist keine Insel – seine Instanzen hatten vorher ein Leben und haben danach
 * eines. Vor dem Startknoten steht darum, aus welchem **regulären** Auftrag sie kamen, nach
 * dem Endknoten, wohin sie gingen. Damit lässt sich «wie wo was passiert ist» über
 * Auftragsgrenzen hinweg verfolgen, statt an der Flagge zu enden.
 *
 * Es ist eine Aussage über **Material**, also trägt es die Materialsprache: eine Pille auf
 * der Linie, Menge zuerst, Objektnummer daneben, ein Klick öffnet den Datensatz. Ein voller
 * Auftrags-Knoten wäre hier falsch – der steht in der linken Spur und meint etwas anderes
 * («dieser Auftrag ging aus jenem hervor», nicht «sein Material kam von dort»).
 */
function TraceChip({ row, dir, onOpen }: {
  row: MaterialOrder; dir: 'in' | 'out'; onOpen?: (objectId: number) => void;
}) {
  const Icon = dir === 'in' ? ArrowDown : ArrowRight;
  return (
    <button type="button" onClick={() => onOpen?.(row.object_id)}
      title={dir === 'in'
        ? `${row.quantity} kamen aus ${row.name ?? 'Auftrag'} ${formatObjectId(row.object_id)} – öffnen`
        : `${row.quantity} gingen weiter an ${row.name ?? 'Auftrag'} ${formatObjectId(row.object_id)} – öffnen`}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 9px',
        borderRadius: 999, cursor: 'pointer', background: '#fff',
        border: '1px solid var(--border-1)', color: 'var(--fg-3)',
        font: '500 11.5px var(--font-body)', whiteSpace: 'nowrap',
      }}>
      <Icon size={11} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>{row.quantity}</span>
      <span style={{ font: '500 11px var(--font-mono), monospace', color: 'var(--fg-4)',
        fontVariantNumeric: 'tabular-nums' }}>{formatObjectId(row.object_id)}</span>
    </button>
  );
}

function TraceRow({ rows, dir, onOpen }: {
  rows: MaterialOrder[]; dir: 'in' | 'out'; onOpen?: (objectId: number) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center',
      padding: '2px 0' }}>
      {rows.map((r) => <TraceChip key={r.object_id} row={r} dir={dir} onOpen={onOpen} />)}
    </div>
  );
}

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
  // **Die Hover-Karte blasst NIE aus** (Testnotiz #504): Erklärungen müssen immer klar
  // lesbar sein. Sie steckte in gedämpften Behältern (vergangene Kante, Nachbar-Spur) und
  // erbte deren Deckkraft – gegen eine geerbte `opacity` kann ein Kind sich nicht wehren.
  // Darum hängt sie im Portal am `body`: ausserhalb jeder Dämpfung, jeder Überlauf-Kante
  // und jeder Stapel-Ordnung. Gedämpft bleibt allein die Pille selbst.
  const anchor = useRef<HTMLSpanElement>(null);
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const show = () => {
    const r = anchor.current?.getBoundingClientRect();
    if (r) setAt({ x: r.left + r.width / 2, y: r.bottom + 6 });
  };
  const hide = () => setAt(null);
  const open = at !== null;
  // **Jede Materialzeile trägt die Ampelfarbe ihrer Instanz** (Testnotiz #481): damit steht
  // an JEDER Stelle des Prozesses, in welchem Zustand das Stück gerade ist – verschrottet
  // ist rot, gesperrt gelb, frei am Lager grün. Dieselbe Projektion wie an der Instanz
  // selbst (`instanceStatusConfig`), kein zweites Regelwerk.
  const cfg = instanceStatusConfig(lot.quality, lot.disposition, lot.reserved);
  const Icon = cfg.icon;
  return (
    <span ref={anchor} style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      <button type="button" title={cfg.label}
        onClick={(e) => { e.stopPropagation(); nav?.(lot.instance_object_id); }}
        // **Der ganze Container trägt den Zustand** (Testnotiz #545): Fläche in der
        // Ampelfarbe, Schrift darauf gut lesbar. Vorher trugen Rahmen, Symbol UND Schrift
        // dieselbe Aussage dreimal – das wirkte überladen. Eine Fläche, eine Farbe, ein Satz.
        style={{
          display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
          borderRadius: 999, background: cfg.bg, cursor: nav ? 'pointer' : 'default',
          border: `1px solid ${cfg.color}22`,
          font: '600 11.5px var(--font-mono), monospace', fontVariantNumeric: 'tabular-nums',
          color: cfg.color, whiteSpace: 'nowrap',
        }}>
        {qtyText(lot)} × {lotNumbers(lot)}
      </button>
      {open && typeof document !== 'undefined' && createPortal(
        <span style={{
          // Am `body`, nicht im Fluss: keine geerbte Dämpfung (#504), kein Beschnitt an
          // einer Überlauf-Kante, und über allem, was darunter liegt (#474).
          position: 'fixed', zIndex: 2000, top: at.y, left: at.x, transform: 'translateX(-50%)',
          padding: '8px 11px', borderRadius: 'var(--r-md)', background: '#fff',
          border: '1px solid var(--border-1)', boxShadow: 'var(--shadow-md)',
          display: 'flex', flexDirection: 'column', gap: 5, pointerEvents: 'none',
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
          {/* **Welche Stücke** die Menge ausmachen – jedes Teil hat eine eigene Nummer. */}
          {(lot.units?.length ?? 0) > 0 && (
            <LotFact icon={Hash} title="Stücke">
              <UnitList units={lot.units} unit={lot.unit ? unitLabel(lot.unit) : undefined}
                max={12} />
            </LotFact>
          )}
        </span>, document.body)}
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

/**
 * **Der Abkürzungs-Knopf dort, wo der Prozess gerade steht** (Notiz #455).
 *
 * Genau an der Kante, an der die starke Linie endet, liegt das Material, um das es gerade
 * geht – und genau dort will man einen Auftrag darauf ansetzen (in der Praxis meist eine
 * Abweichung). Der Knopf nimmt **alle** Instanzen dieser Kante mit: mehrere Artikel werden
 * zu mehreren Positionen, jede mit ihren Instanzen und Mengen.
 *
 * Was daraus wird, entscheidet weiterhin die Auswahl (``subject.classify_pick``) – der Knopf
 * legt nichts an, er belegt einen Entwurf vor. Optisch bewusst zurückhaltend: erst im Hover
 * wird er deutlich, wie die Abkürzungen im Kopf eines Datensatzes.
 */
function FlowShortcut({ lots, onCreate }: {
  lots: FlowLot[]; onCreate: (lots: FlowLot[]) => void;
}) {
  const [hot, setHot] = useState(false);
  const list = lots.filter((l) => l.quantity > 0);
  if (list.length === 0) return null;
  const what = list.length === 1
    ? `${qtyText(list[0])} ${formatObjectId(list[0].instance_object_id)}`
    : `${list.length} Instanzen`;
  return (
    <button type="button" onClick={() => onCreate(list)}
      onMouseEnter={() => setHot(true)} onMouseLeave={() => setHot(false)}
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}
      title={`Auftrag auf ${what} anlegen – Artikel, Instanzen und Mengen sind vorbelegt`}
      style={{
        width: 24, height: 24, borderRadius: 999, flex: 'none', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: `1px solid ${hot ? 'var(--border-2)' : 'transparent'}`,
        background: hot ? '#fff' : 'transparent',
        color: hot ? 'var(--fg-2)' : 'var(--fg-4)', opacity: hot ? 1 : 0.4,
        transition: 'opacity .15s, background .15s, border-color .15s, color .15s',
      }}>
      <ClipboardPlus size={13} />
    </button>
  );
}

/** Die Materialzeilen einer Kante; ab der vierten fasst «+N» zusammen. */
/** Das Material einer Kante – und am **Prozess-Punkt** die Abkürzung darauf (#455). */
function EdgeMaterial({ lots, onCreate, past, small }: {
  lots: FlowLot[]; onCreate?: (lots: FlowLot[]) => void; small?: boolean;
  /** Der Prozess ist hier schon vorbei – die Angabe tritt zurück, wie ein erledigtes Modul. */
  past?: boolean;
}) {
  if (lots.length === 0) return null;
  if (!onCreate) return <FlowLots lots={lots} past={past} small={small} />;
  // **Die Pillen stehen mittig auf der Achse** (Testnotiz #533): der Knopf hängt absolut
  // daneben, statt die Gruppe nach links zu schieben. Vorher war «Container + Button» ein
  // gemeinsamer Block – zentriert war damit die Gruppe, nicht das Material.
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <FlowLots lots={lots} past={past} small={small} />
      <span style={{ position: 'absolute', left: '100%', marginLeft: 6, top: '50%',
                     transform: 'translateY(-50%)' }}>
        <FlowShortcut lots={lots} onCreate={onCreate} />
      </span>
    </span>
  );
}

function FlowLots({ lots, small, past }: { lots: FlowLot[]; small?: boolean; past?: boolean }) {
  const list = lots;
  if (list.length === 0) return null;
  const shown = list.slice(0, 3);
  const rest = list.length - shown.length;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 3, margin: small ? '2px 0' : 0,
      // **Vergangenes verblasst** (Notiz #462) – dieselbe Dämpfung wie bei einem erledigten
      // Modul: was schon durch ist, soll den Blick nicht mehr auf sich ziehen.
      opacity: past ? 0.55 : 1, transition: 'opacity .16s' }}>
      {shown.map((l, i) => <FlowLotChip key={`${l.instance_object_id}-${i}`} lot={l} />)}
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

export function OrderFlow({ steps, subOrders = [], flowNodes = [], flowEdges = [],
  origin, decision, paused = false,
  selectedId, onSelectStep, onOpenOrder, renderPanel, lots = [], orderObjectId, goal,
  onCreateOrder, materialFrom = [], materialTo = [] }: {
  steps: OrderStep[];
  subOrders?: OrderDeviationInfo[];
  /** **Die fertig gerechnete Achse aus dem Backend** (`flow_nodes`/`flow_edges`): Knoten,
   *  Kanten mit Material im Zustand von damals, Fortschritt und Prozess-Punkt. Das
   *  Frontend zeichnet nur noch – es rechnet nichts mehr aus (ADR 007). */
  flowNodes?: FlowNode[];
  flowEdges?: FlowEdge[];
  origin?: OrderOrigin | null;
  decision?: FlowDecision;
  paused?: boolean;
  selectedId?: string | null;
  onSelectStep: (stepId: string) => void;
  onOpenOrder: (objectId: number) => void;
  renderPanel?: (step: OrderStep) => React.ReactNode;
  /** Das lebende Material (nur für den Rückweg-Knoten eines Unter-Auftrags). */
  lots?: FlowLot[];
  /** Objektnummer dieses Auftrags – die Terminal-Knoten nennen sie im Hover (#443/#444). */
  orderObjectId?: number | null;
  /** Was am Ende des Prozesses steht: Wunsch-Liefertermin und (intern) der Fakturierende. */
  goal?: { due?: string | null; seller?: string | null };
  /** Abkürzung am Prozess-Punkt: einen Auftrag auf genau dieses Material ansetzen (#455). */
  onCreateOrder?: (lots: FlowLot[]) => void;
  /** **Der Prozessbaum** (#493): die regulären Aufträge, die dasselbe Material vor bzw. nach
   *  diesem verarbeitet haben – vor dem Start- und nach dem Endknoten. */
  materialFrom?: MaterialOrder[];
  materialTo?: MaterialOrder[];
}) {
  if (steps.length === 0 && !origin) return null;
  const processLabel = orderObjectId != null
    ? `Auftrag ${formatObjectId(orderObjectId)}` : 'Auftrag';

  // Nachschlagewerke für die Server-Knoten: Schritte nach id, Abzweige nach Objektnummer.
  const stepById = new Map(steps.map((s) => [s.id, s]));
  const branchById = new Map<number, OrderDeviationInfo>();
  for (const b of subOrders) branchById.set(b.object_id, b);
  for (const s of steps) for (const b of (s.sub_orders ?? [])) branchById.set(b.object_id, b);
  // Wer als Abzweig im Bild steht, braucht daneben keine Zeile mehr (#466, `Resolutions`).
  const shownSubs = new Set(branchById.keys());
  // Eine Teilung, die die Auflösungen ihres Schritts trägt, nimmt sie ihm ab.
  const claimedRes = new Set(flowNodes.filter((n) => n.kind === 'split' && n.step_id != null)
    .map((n) => n.step_id as number));

  const edgeAt = (i: number): FlowEdge => flowEdges[i] ?? { lots: [], reached: false, live: false };

  let gateUsed = false;
  const rows: React.ReactNode[] = [];
  flowNodes.forEach((n, i) => {
    const edge = edgeAt(i);
    rows.push(
      // **Vor UND nach jedem Modul steht, was fliesst** (Testnotiz #505): das Material
      // liegt auf der ganzen Achse, nicht erst ab dem Fortschritt. Wie weit der Prozess
      // gekommen ist, sagt die **Linienstärke** – dafür braucht es kein zweites Signal.
      <Row key={`edge-${i}`}>
        <Axis strong={edge.reached} />
        {/* Material trägt nur, wo der Prozess war – unterhalb wäre es eine Prognose
            (Notiz #521). Der Server liefert die Kante dort schlicht leer. */}
        <EdgeMaterial lots={edge.lots} past={!edge.live}
          onCreate={edge.live ? onCreateOrder : undefined} />
        <Axis strong={edge.reached} />
      </Row>,
    );
    if (n.kind === 'split') {
      const branches = n.branch_object_ids
        .map((id) => branchById.get(id)).filter(Boolean) as OrderDeviationInfo[];
      if (branches.length === 0) return;
      const res = (n.step_id != null ? stepById.get(n.step_id)?.resolutions : null) ?? [];
      // **Nur die offene Entscheidung ist ein Knoten** (Notiz #434) – ein offener Abzweig
      // IST das Warten, eine Auflösung steht als Zeile an ihrem Schritt.
      const decide = res.length === 0 && n.passed && !gateUsed && !!decision;
      if (decide) gateUsed = true;
      const bypass = n.bypass ?? { lots: [], reached: false, live: false };
      rows.push(
        // **Fork · Bypass · Merge**: die Achse läuft neben der Teilung weiter und trägt, was
        // auf dem Hauptauftrag geblieben ist (Notizen #425/#469/#496) – vom Server gerechnet.
        // **Die Ecke trägt die Strichstärke IHRER Achse** – Fork wie das Stück darüber
        // (`reached`), Merge wie das darunter (`passed`). Wo zwei Bits aufeinandertrafen,
        // stand an der Ecke ein sichtbarer Versatz (3 px ↔ 2 px).
        <Row key={`br-${branches[0].object_id}`}
          right={<BranchArm branches={branches} reached={n.reached} passed={n.passed}
            onOpen={onOpenOrder} />}>
          <Axis grow h={26} strong={n.reached} />
          <EdgeMaterial lots={bypass.lots} small past={!bypass.live}
            onCreate={bypass.live ? onCreateOrder : undefined} />
          <Axis grow h={26} strong={n.passed} />
        </Row>,
      );
      if (decide || res.length > 0) {
        rows.push(
          <Row key={`gate-${branches[0].object_id}`}>
            <Axis h={10} strong={n.passed} />
            {decide ? <Gateway decision={decision} /> : <Resolutions list={res} shown={shownSubs} />}
          </Row>,
        );
      }
      return;
    }
    const s = n.step_id != null ? stepById.get(n.step_id) : undefined;
    if (!s) return;
    // **Ansehen darf man jeden Schritt** (Notizen #442/#465/#471) – erledigt, laufend oder
    // künftig. Ein Panel zu öffnen ist Lesen; ob sich darin etwas AUSFÜHREN lässt,
    // entscheidet ohnehin das Backend (`resolve_exec_step`: nur der aktive Schritt).
    const selected = selectedId === String(s.id);
    rows.push(
      <Row key={`step-${s.id}`}>
        <StepCard type={s.step_type as StepType} state={s.state} selected={selected}
          muted={paused} badge={stepBadge(s.step_type, stepStatus(s))}
          hint={completionHint(s)}
          onClick={() => onSelectStep(String(s.id))}>
          {selected && renderPanel?.(s)}
        </StepCard>
      </Row>,
    );
    const res = !claimedRes.has(s.id) ? (s.resolutions ?? []) : [];
    if (res.length > 0) {
      rows.push(
        <Row key={`res-${s.id}`}>
          <Axis h={10} strong={n.passed} />
          <Resolutions list={res} shown={shownSubs} />
        </Row>,
      );
    }
  });

  const lastEdge = edgeAt(flowNodes.length);
  const hasAside = !!origin || flowNodes.some((n) => n.kind === 'split');
  return (
    // Ein Diagramm darf breiter sein als eine Textspalte – aber es scrollt in seinem eigenen
    // Kasten, statt die Seite waagrecht zu schieben.
    <div className="ix-noscrollbar" style={{ width: '100%', overflowX: 'auto' }}>
      <div style={{ width: '100%', minWidth: hasAside ? MAIN + 2 * LANE : MAIN,
        display: 'flex', flexDirection: 'column', alignItems: 'stretch',
        ...({ '--flow-lane': hasAside ? `${LANE}px` : '0px' } as React.CSSProperties) }}>
        {origin && (
          <>
            <Row left={<OriginArm origin={origin} onOpen={onOpenOrder} />} />
            <Row><Axis h={18} strong /></Row>
          </>
        )}
        {/* **Der Prozessbaum** (Notiz #493): woher das Material kam – VOR dem Startknoten,
            denn dort beginnt dieser Vorgang und dort endete der vorige. */}
        {materialFrom.length > 0 && (
          <>
            <Row><TraceRow rows={materialFrom} dir="in" onOpen={onOpenOrder} /></Row>
            <Row><Axis h={12} strong /></Row>
          </>
        )}
        <Row><FlowTerm kind="start" title={`Start · ${processLabel}`} /></Row>
        {rows}
        <Row key="edge-last">
          <Axis strong={lastEdge.reached} />
          {/* Die letzte Kante zeigt, womit der Auftrag herauskommt – stark nur, solange er
              läuft (Notiz #467): ist er durch, ist sein Material beim übergeordneten. */}
          {lastEdge.reached && <EdgeMaterial lots={lastEdge.lots} past={!lastEdge.live}
            onCreate={lastEdge.live ? onCreateOrder : undefined} />}
          <Axis strong={lastEdge.reached} />
        </Row>
        <Row>
          {/* **Das Ziel gehört ans Prozessende** (Notiz #446) – und **neben** den Knoten,
              nicht darunter (#457): absolut gesetzt, damit der Kreis auf der Achse bleibt. */}
          <div style={{ position: 'relative', display: 'flex' }}>
            <FlowTerm kind="end" title={[`Ende · ${processLabel}`,
              goal?.due && `Liefertermin ${goal.due}`, goal?.seller]
              .filter(Boolean).join(' · ')} />
            {goal?.due && (
              <div style={{ position: 'absolute', left: '100%', top: '50%',
                transform: 'translateY(-50%)', marginLeft: 12, whiteSpace: 'nowrap',
                font: '500 11.5px var(--font-body)', color: 'var(--fg-4)' }}>{goal.due}</div>
            )}
          </div>
        </Row>
        {/* … und wohin es weiterging – NACH dem Endknoten (#493). Nur, wenn es je
            weiterging: solange nichts folgt, folgt auch keine Zeile. */}
        {materialTo.length > 0 && (
          <>
            <Row><Axis h={12} strong /></Row>
            <Row><TraceRow rows={materialTo} dir="out" onOpen={onOpenOrder} /></Row>
          </>
        )}
        {origin?.returns_to_object_id != null && (
          <>
            <Row><Axis h={18} strong={lastEdge.reached} /></Row>
            {/* Was zurückgeht, ist das lebende Material des Auftrags – dieselbe Ableitung,
                die der Eltern für seinen Merge liest (`flow_back`). */}
            <Row left={<ReturnArm origin={origin} strong={lastEdge.reached} onOpen={onOpenOrder}
              lots={lots.filter((l) => !isGone(l))} />} />
          </>
        )}
      </div>
    </div>
  );
}

// ─── Modul-Karte (EINE für den ganzen Fluss) ──────────────────────────────────────

/**
 * **Nur was die Linie NICHT sagt** (Notizen #450/#452). Dass der Prozess gerade an diesem
 * Modul steht, sieht man daran, dass es aktiv ist und die starke Linie hier endet – ein
 * Uhr-Symbol daneben wiederholt das nur. Dass er ruht, ebenso: die starke Linie führt nicht
 * hin, und kein Modul ist aktiv.
 *
 * Übrig bleiben die zwei Aussagen, die man der Linie nicht ansieht: **durch** (mit Wer/Wann
 * im Hover) und **fehlgeschlagen**.
 */
const STATE_MARK: Record<string, { icon: React.ElementType; color: string }> = {
  done: { icon: Check, color: 'var(--success)' },
  failed: { icon: X, color: 'var(--danger)' },
};

/**
 * **Ein Modul im Fluss – überall dasselbe** (Notiz #418).
 *
 * Ob es auf der Hauptachse steht oder im Prozess eines Abzweigs, ändert nichts an ihm:
 * gleiche Anatomie (Symbolkasten · Name · Nummer · Kurzzeile · Zustand), gleiche Modulfarbe,
 * gleiche Zustands-Symbole. Was ein Abzweig nicht mitliefert (Kurzzeile, Beleg-Status), bleibt
 * schlicht leer – das ist ein fehlendes Detail, kein anderes Bauteil.
 */
function StepCard({ type, state, badge, hint, selected, muted: forced,
  onClick, children }: {
  type: StepType; state: string;
  badge?: React.ReactNode; hint?: string;
  selected?: boolean; muted?: boolean;
  onClick?: () => void; children?: React.ReactNode;
}) {
  const meta = STEP_META[type] ?? STEP_META.purchase;
  const Icon = meta.icon;
  const kc = kindColor(type);
  const muted = forced || state === 'done' || state === 'locked';
  const mark = STATE_MARK[state];
  const MarkIcon = mark?.icon;
  const box = 34;
  return (
    <div style={{
      position: 'relative', width: '100%',
      border: `1px solid ${selected ? 'var(--fg-1)' : kc.border}`,
      borderRadius: 'var(--r-lg)', background: kc.bg,
      boxShadow: selected ? '0 0 0 3px var(--bg-3)' : 'var(--shadow-sm)',
      opacity: muted ? 0.55 : 1, transition: 'box-shadow .16s, border-color .16s, opacity .16s',
    }}>
      <div onClick={onClick} title={hint}
        style={{ display: 'flex', alignItems: 'center', gap: 12,
          padding: '13px 16px',
          // Hängt der Klick am Container (Abzweig – die ganze Spalte öffnet den Datensatz),
          // erbt die Karte den Zeigefinger, statt ihn zu widerrufen (Notiz #454).
          cursor: onClick ? 'pointer' : 'inherit' }}>
        <div style={{ width: box, height: box, borderRadius: 'var(--r-sm)', flexShrink: 0,
          background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={17} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          {/* **Keine Untertitel am Modul** (Testnotiz #490): ganz oder gar nicht – wer die
              Details sehen will, öffnet den Schritt und sieht dort ALLES. Eine halbe Zeile
              daneben ist eine zweite, unvollständige Wahrheit. */}
          <span style={{ display: 'block', font: '800 15px var(--font-display)',
            letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{meta.label}</span>
        </div>
        {badge}
        {MarkIcon && <MarkIcon size={17} style={{ color: mark.color, flexShrink: 0 }} />}
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

/**
 * **Die Teilung an EINER Stelle der Achse: ein Fork, ein Merge** (Notizen #417/#424).
 *
 * Die Linie verlässt die Achse waagrecht, geht **oben mittig** in die Abzweig-Spur – und
 * unten wieder **zurück in die Achse**. Beide Ecken sind gerundet (#423). Laufen mehrere
 * Unter-Aufträge von hier aus, hängen sie **an derselben Abzweigung** untereinander in der
 * Spur; wie viel wohin geht, sagt die Menge über jedem von ihnen.
 *
 * **Und die Linie ist hier kein Präfix.** Auf der Achse gilt «stark bis zur offenen Stelle»
 * (#422) – das setzt eine Reihenfolge voraus, die es zwischen gleichzeitig laufenden Ästen
 * nicht gibt. Zu **jedem** gestarteten Ast ist ein Weg gegangen worden, also ist zu jedem die
 * Linie voll; sie hängt am Zustand des Astes, nicht daran, wie weit die Achse gekommen ist.
 * Der Rückweg wird erst stark, wenn die **ganze** Teilung durch ist – vorher geht es auf der
 * Achse ja auch nicht weiter.
 */
const branchStarted = (b: OrderDeviationInfo) => b.status !== 'draft';

function BranchArm({ branches, reached, passed, onOpen }: {
  branches: OrderDeviationInfo[];
  /** **Die Ecke trägt die Strichstärke IHRER Achse** – dasselbe Bit wie das Achsenstück,
   *  an dem sie hängt (`reached` oben, `passed` unten). Zwei verschiedene Bits an einer
   *  Ecke bedeuteten 3 px gegen 2 px – und genau das sah man als Versatz. */
  reached?: boolean; passed?: boolean;
  onOpen?: (id: number) => void;
}) {
  // **Kommt nichts zurück, führt auch keine Linie zurück** (Testnotiz #481): wurde alles
  // verschrottet oder die Menge des Eltern-Auftrags reduziert, endet der Abzweig hier – und
  // genau das sagt das Bild dann auch. Solange er läuft, wissen wir es noch nicht.
  const back = branches.filter((b) => b.returns_material);
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0,
      paddingTop: ARM, paddingBottom: back.length ? ARM : 0 }}>
      <Elbow dir="fork-right" strong={reached} />
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
        width: '100%', minWidth: 0 }}>
        {branches.map((b, i) => (
          <div key={b.object_id} style={{ display: 'flex', flexDirection: 'column',
            alignItems: 'center', width: '100%', minWidth: 0 }}>
            {i > 0 && <Axis h={20} strong={branchStarted(b)} />}
            {/* **Der Hover gilt genau dem Ast, auf dem der Cursor steht** – nicht der ganzen
                Spur: lagen alle Abzweige in EINEM `aside`-Kasten, hellten sie gemeinsam auf. */}
            <div {...aside('right', { width: '100%', minWidth: 0 })}>
              <SubProcess info={b} onOpen={onOpen} />
            </div>
          </div>
        ))}
      </div>
      {back.length > 0 && <Elbow dir="merge-right" strong={passed} />}
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
  const walked = walkedSteps(steps);
  // **Oben, was hineinging – unten, was zurückgeht** (#481/#488/#497).
  //
  // Die Menge schrumpft nicht, wenn etwas verschrottet wird – die Instanz und ihre Menge
  // verschwinden ja nicht, nur ihr Zustand ändert sich. Oben steht darum der Zustand von
  // **damals** (in Arbeit, als es hineinging), unten das, was tatsächlich **zurück ist**
  // (`flow_back` – leer, solange der Abzweig läuft; vorher wäre es eine Vorhersage). Kommt
  // nichts zurück, sagt das weiterhin die Prozesslinie, indem sie gar nicht erst zurückführt.
  const inLots = asEntry(info.flow_in ?? []);
  // **Was zurückgeht – und wenn nichts zurückgeht, was daraus geworden ist** (#514).
  // «Keine Rücklinie» sagt zwar, DASS nichts zurückkommt, aber nicht warum. Die
  // ausgesonderte Menge in ihrer Ampelfarbe (rot) beantwortet genau das – dieselbe
  // Zeile wie überall, nur im Endzustand.
  const backLots = info.flow_back ?? [];
  const lostLots = backLots.length === 0 ? (info.flow_lost ?? []) : [];
  const hint = `${label} ${formatObjectId(info.object_id)}`
    + `${info.name ? ` «${info.name}»` : ''} · ${cfg.label} – klicken zum Öffnen`;
  return (
    <div title={hint} onClick={() => onOpen?.(info.object_id)}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%',
        minWidth: 0, cursor: onOpen ? 'pointer' : 'default' }}>
      {/* **Das Material steht UNTER dem Startknoten** (Testnotiz #513) – wie im geöffneten
          Auftrag: der Startknoten markiert den Anfang, das Material fliesst danach.
          Vorher stand es oben drüber, und derselbe Vorgang sah je nach Ansicht anders aus. */}
      <FlowTerm kind="start" title={`Start · ${hint}`} />
      {inLots.length > 0 && (
        <>
          <Axis h={10} strong={started} />
          <FlowLots lots={inLots} small past={walked > 0} />
        </>
      )}
      {steps.length === 0 ? (
        <>
          <Axis h={12} />
          <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>Noch kein Ablauf definiert</span>
        </>
      ) : steps.map((st: SubOrderStep, i: number) => (
        <div key={st.id} style={{ width: '100%', display: 'flex', flexDirection: 'column',
          alignItems: 'center' }}>
          <Axis h={12} strong={started && i <= walked} />
          <StepCard type={st.step_type as StepType} state={st.state}
            badge={stepBadge(st.step_type, st.status)}
            hint={`${STEP_META[st.step_type as StepType]?.label ?? ''}: ${stepStateLabel(st.state)}`
              + ` · ${hint}`} />
        </div>
      ))}
      <Axis h={12} strong={started && walked === steps.length} />
      {/* **Material steht NIE nach der Zielflagge** (Testnotiz #516): es gehört zwischen
          das letzte Modul und den Endknoten – auf der Hauptachse wie hier. Was zurückgeht
          (`backLots`), und wenn nichts zurückgeht, was daraus geworden ist (`lostLots`,
          #514: in seiner Ampelfarbe, damit man sieht, dass die Menge entfällt). */}
      {(backLots.length > 0 || lostLots.length > 0) && (
        <>
          <FlowLots lots={backLots.length > 0 ? backLots : lostLots} small />
          <Axis h={10} strong={backLots.length > 0} />
        </>
      )}
      <FlowTerm kind="end" title={`Ende · ${hint}`} />
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
      <div {...aside('left')}>
        <OrderRefNode caption="Hervorgegangen aus" objectId={origin.order_object_id}
          name={origin.order_name} icon={ArrowUp}
          title={`Hervorgegangen aus ${origin.order_name ?? 'Auftrag'} – öffnen`}
          onClick={() => onOpen?.(origin.order_object_id)} />
      </div>
      <Elbow dir="in-from-left" strong />
    </div>
  );
}

/**
 * Wohin die Stücke beim Abschluss zurückgehen – derselbe Verweis, nur andersherum (#438).
 *
 * **Und WAS zurückgeht, steht auf der Linie** (Testnotiz #497): nach dem Endknoten war die
 * Rückgabe eine blosse Behauptung – man sah, DASS etwas zurückgeht, aber nicht was. Die
 * Materialzeile gehört genau dorthin, wo sie überall sonst steht: auf die Kante.
 */
function ReturnArm({ origin, lots, strong, onOpen }: {
  origin: OrderOrigin; lots: FlowLot[]; strong?: boolean; onOpen?: (id: number) => void;
}) {
  const id = origin.returns_to_object_id as number;
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingTop: ARM }}>
      <Elbow dir="out-to-left" strong={strong} />
      <div {...aside('left')}>
        <OrderRefNode caption="Gibt zurück an" objectId={id} name={origin.returns_to_name}
          icon={ArrowDown}
          title={`Gibt beim Abschluss zurück an ${origin.returns_to_name ?? 'Auftrag'} – öffnen`}
          onClick={() => onOpen?.(id)} />
      </div>
      {lots.length > 0 && (
        // Auf der Kante, die zum Eltern führt – zwischen Achse und Knoten, wie jede andere
        // Materialzeile auch.
        <div style={{ position: 'absolute', left: 0, right: 0, top: ARM / 2,
          transform: 'translateY(-50%)', display: 'flex', justifyContent: 'center',
          pointerEvents: 'none' }}>
          <div style={{ pointerEvents: 'auto' }}><FlowLots lots={lots} small /></div>
        </div>
      )}
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

/**
 * **Was an dieser Stelle entschieden wurde** – und nichts, was daneben schon steht (Notiz #466).
 *
 * «1 abgegeben an 100000597» war in aller Regel eine **zweite Erzählung desselben Vorgangs**:
 * wer sich hier einen Anteil geholt hat, wird dadurch zur Abweichung **dieses** Auftrags –
 * steht also ohnehin als Abzweig im Fluss, mit der Menge auf seiner Kante. Die Zeile bleibt
 * darum nur für den Fall, in dem der Nehmer **nicht** als Abzweig erscheint: greift eine
 * Auswahl über mehrere Halter, wird nur der erste sein Eltern-Auftrag – die übrigen erfahren
 * sonst nirgends, warum ihnen plötzlich etwas fehlt.
 */
function Resolutions({ list, shown }: { list: StepResolution[]; shown: Set<number> }) {
  const rows = list.filter((r) => !(r.kind === 'share_taken'
    && r.other_order_object_id != null && shown.has(r.other_order_object_id))
    // **«Menge angepasst» sagt der Fluss selbst** (Testnotiz #486): der Abzweig führt nicht
    // mehr zurück, also läuft der Prozess mit weniger weiter. Die Zeile daneben erzählte
    // dasselbe ein zweites Mal – und zwar in Zahlen statt im Bild.
    && r.kind !== 'quantity_confirmed');
  if (rows.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {rows.map((r, k) => <ResolutionLine key={k} r={r} first />)}
    </div>
  );
}

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

/**
 * **Fachlicher Zwischenstand** (Beschaffung/Verkauf) – aus Typ + Status, EINE Stelle.
 *
 * Die Hauptachse liest ihn aus dem Embed, der Abzweig aus ``SubOrderStep.status`` – gerendert
 * wird er hier, damit derselbe Schritt im Abzweig nicht anders aussieht als beim Öffnen des
 * Unter-Auftrags (Testnotiz #492).
 */
function stepBadge(type: string, status?: string | null): React.ReactNode {
  if (!status) return null;
  if (type === 'purchase') return <StatusBadge cfg={purchaseStatusConfig(status)} size={10} />;
  if (type === 'sale') return <StatusBadge cfg={saleStatusConfig(status)} size={10} />;
  return null;
}

/** Der Zwischenstand eines Schritts auf der Hauptachse – nur, solange er läuft (#279). */
function stepStatus(s: OrderStep): string | null {
  if (s.state === 'done') return null;
  return (s.purchases ?? [])[0]?.status ?? (s.sales ?? [])[0]?.status ?? null;
}


// (`SubOrderStep` trägt bewusst kein Label – Modul-Name und Zustandswort kommen aus der EINEN
//  Quelle `lib/process.ts`, die gegen `domain/event_types.py` getestet ist.)


// ─── Der Entwurf: derselbe Rahmen, schon beim Modellieren ─────────────────────────

/**
 * **Was man gleich sehen wird, sieht man schon beim Modellieren.**
 *
 * Wer gebundene Instanzen wählt, nimmt sie einem laufenden Auftrag weg – der Entwurf ist damit
 * eine **Abweichung**, und nach der Freigabe hängt er als Abzweig an genau diesem Auftrag. Das
 * Bild dafür gibt es längst (drei Spuren, Herkunft links); es kam bisher nur einen Schritt zu
 * spät. Jetzt steht der Rahmen schon da, während man den Ablauf modelliert – dieselben
 * Bausteine, dieselbe Geometrie, kein zweites Vokabular.
 *
 * **Und die Rückgabe-Linie IST die Entscheidung.** Die Unterdeckung des Halters hat drei
 * Antworten; zwei davon sind schlicht die Frage, ob das Material zurückkommt:
 *
 *     Linie da    → **warten** (`wait`)   – der Auftrag ruht, bis die Menge wieder da ist
 *     Linie weg   → **reduzieren** (`accept`) – er wird mit dem fertig, was ihm bleibt
 *
 * Man klickt also nicht mehr in einem Dialog auf ein Wort, sondern zeichnet den Fluss, den man
 * meint. **«Ersetzen» bleibt bewusst draussen**: das ist keine Aussage über diesen Entwurf,
 * sondern eine Beschaffung im anderen Auftrag – sie gehört dorthin, wo sie wirkt (an den
 * laufenden Auftrag, `ShortfallDialog`).
 *
 * **Je Halter eine Linie**: greift die Auswahl auf zwei laufende Aufträge zu, darf der eine
 * warten und der andere reduzieren. Ein Schalter für alle wäre eine Entscheidung, die so
 * niemand getroffen hat.
 */
export function DraftFlowFrame({ holders, returns, onToggleReturn, onOpenOrder, children }: {
  /** Die laufenden Aufträge, denen diese Auswahl etwas wegnimmt (`AffectedOrder`-Zeilen). */
  holders: AffectedOrder[];
  /** Objektnummern der Halter, an die zurückgegeben wird – der Rest wird reduziert. */
  returns: Set<number>;
  onToggleReturn: (objectId: number) => void;
  onOpenOrder?: (objectId: number) => void;
  children: React.ReactNode;
}) {
  // Ohne Halter gibt es keinen Rahmen: ein gewöhnlicher neuer Auftrag geht aus nichts hervor
  // und gibt an nichts zurück – leere Spuren wären reine Dekoration.
  if (holders.length === 0) return <>{children}</>;
  return (
    <div className="ix-noscrollbar" style={{ width: '100%', overflowX: 'auto' }}>
      <div style={{ width: '100%', minWidth: MAIN + 2 * LANE,
        display: 'flex', flexDirection: 'column', alignItems: 'stretch',
        ...({ '--flow-lane': `${LANE}px` } as React.CSSProperties) }}>
        <Row left={<DraftOriginArm holders={holders} onOpen={onOpenOrder} />} />
        <Row><Axis h={18} strong /></Row>
        {/* **Kein eigener Start-/Endknoten** (Testnotiz #498): der Schritt-Editor zeichnet
            seinen Fluss samt Terminal-Knoten selbst – ein zweiter davor wäre dasselbe Symbol
            ein zweites Mal. Der Rahmen liefert die Spuren, nicht den Prozess. */}
        <Row>{children}</Row>
        <Row><Axis h={18} strong /></Row>
        {/* **Je Halter seine eigene Rückgabe-Linie – mit der Schere DARAUF** (#499): wo
            entschieden wird, wird auch bedient. Eine gekappte Linie ist schlicht keine Linie;
            der Knoten bleibt und trägt den Knopf, mit dem sie wiederkommt. */}
        {holders.map((h, i) => (
          <Row key={h.object_id}
            left={<DraftReturnArm holder={h} connected={returns.has(h.object_id)}
              onToggle={onToggleReturn} />}>
            {i < holders.length - 1 && <Axis grow h={ARM} strong />}
          </Row>
        ))}
      </div>
    </div>
  );
}

/** Die Menge, die ein Halter durch die Auswahl verliert – «2 Stk von 100000595». */
const holderLoss = (h: AffectedOrder) =>
  `${h.quantity}${h.unit ? ` ${unitLabel(h.unit)}` : ''}`;

/** Woher der Entwurf sein Material nimmt – ein Knoten je Halter, EINE Einmündung. */
function DraftOriginArm({ holders, onOpen }: {
  holders: AffectedOrder[]; onOpen?: (objectId: number) => void;
}) {
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingBottom: ARM }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
        width: '100%', minWidth: 0 }}>
        {holders.map((h, i) => (
          <div key={h.object_id} style={{ display: 'flex', flexDirection: 'column',
            alignItems: 'center', width: '100%', minWidth: 0 }}>
            {i > 0 && <Axis h={20} strong />}
            <div {...aside('left', { width: '100%', minWidth: 0 })}>
              <OrderRefNode caption="Nimmt aus" objectId={h.object_id} name={h.name}
                icon={ArrowDown}
                title={`${holderLoss(h)} aus ${h.name ?? 'Auftrag'} ${formatObjectId(h.object_id)} – öffnen`}
                onClick={onOpen ? () => onOpen(h.object_id) : undefined} />
            </div>
          </div>
        ))}
      </div>
      <Elbow dir="in-from-left" strong />
    </div>
  );
}

/**
 * **Die Rückgabe-Linie und ihre Schere – an EINER Stelle** (Testnotiz #499).
 *
 * Entschieden wird hier, ob das Material zurückgeht; also wird hier auch bedient. Die Schere
 * sitzt **auf** der Linie (auf ihrem waagrechten Stück, mittig), nicht als kleines Zeichen im
 * Knoten daneben – «manage dort das Zeugs, wo es auftritt».
 *
 * Gekappt heisst schlicht: **keine Linie**. Der Knoten bleibt stehen und tritt zurück, und an
 * derselben Stelle, an der die Schere sass, steht der Knopf, der sie wiederbringt. Damit ist
 * die Entscheidung an genau einem Ort sichtbar UND umkehrbar – ohne zweite Liste darunter.
 */
function DraftReturnArm({ holder, connected, onToggle }: {
  holder: AffectedOrder; connected: boolean; onToggle: (objectId: number) => void;
}) {
  const label = holder.name ?? 'Auftrag';
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0, paddingTop: ARM }}>
      {connected && <Elbow dir="out-to-left" strong />}
      {/* Auf dem waagrechten Stück der Ecke (`out-to-left`: y = 2·BEND), mittig zwischen
          Achse und Spurmitte – dort, wo die Linie verläuft. */}
      <button type="button" onClick={() => onToggle(holder.object_id)}
        title={connected
          ? `${holderLoss(holder)} gehen zurück – ${label} wartet darauf. Klick: Linie kappen, `
            + 'dann wird dort die Menge reduziert.'
          : `${holderLoss(holder)} bleiben hier – ${label} wird auf die verbleibende Menge `
            + 'reduziert. Klick: Rückgabe wieder anschalten.'}
        style={{
          position: 'absolute', left: SIDE / 2 + RUN / 2, top: 2 * BEND,
          transform: 'translate(-50%, -50%)', width: 28, height: 28, borderRadius: 999,
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
          border: `1px solid ${connected ? 'var(--fg-2)' : 'var(--border-2)'}`,
          background: '#fff', color: connected ? 'var(--fg-2)' : 'var(--fg-4)', padding: 0,
        }}>
        {connected ? <Scissors size={14} /> : <Redo2 size={14} />}
      </button>
      <div {...aside('left', { width: '100%', minWidth: 0, opacity: connected ? 1 : 0.55 })}>
        <OrderRefNode
          caption={connected ? 'Gibt zurück an' : 'Keine Rückgabe – wird reduziert'}
          objectId={holder.object_id} name={holder.name} icon={ArrowDown}
          title={`${label} ${formatObjectId(holder.object_id)}`} />
      </div>
    </div>
  );
}
