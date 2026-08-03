'use client';

import { useState } from 'react';
import { ArrowDown, ArrowUp, Check, ClipboardPlus, MapPin, Package, X } from 'lucide-react';
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
// 100000595», im Hover Artikel, Standort und Menge – beide Objektnummern öffnen ihren
// Datensatz. Die Mengen werden **von unten nach oben** gerechnet: unten steht, was der Auftrag
// heute hält, und jeder Ast gibt seine Bilanz (rein − zurück) an die Kante über sich weiter.
// **Nur bis zum Fortschritt** (Notiz #421): was ein Modul später einmal führen wird, ist nicht
// vorhersehbar – darum trägt keine Kante unterhalb des aktuellen Punktes eine Menge.
//
// **Ruht der Auftrag, ruht der Fluss** (Notiz #378): kein Modul lässt sich öffnen und alle
// treten zurück. Eine eigene Strichart braucht es dafür nicht – dass es nicht weitergeht,
// sagt die Linie schon, indem sie an der offenen Stelle zur Haarlinie wird.

/**
 * **Feste Geometrie – und genau darum saubere Ecken** (Notizen #423/#445).
 *
 * Die Spuren waren elastisch (``flex: 1``), also war die Länge einer Abzweigung erst zur
 * Laufzeit bekannt – gezeichnet wurde sie deshalb aus CSS-Rahmenkanten mit ``border-radius``,
 * und an der Nahtstelle zweier Kästchen sah man jede halbe Pixelverschiebung. Mit **festen**
 * Spurbreiten ist der Weg von der Achse zur Spurmitte eine **Konstante** (``RUN``) – damit
 * lässt sich jede Ecke als EIN SVG-Pfad zeichnen: ein Strich, eine Strichstärke, ein echter
 * Viertelkreis, keine Naht.
 *
 * Zugleich wird das Diagramm dadurch schmaler und ruhiger: die Seitenspuren nehmen nur so
 * viel Platz, wie sie brauchen, statt den ganzen Rest zu füllen.
 */
const MAIN = 460;          // Hauptspur (Modul-Karten)
const SIDE = 336;          // Seitenspur (Abzweig bzw. Herkunft/Rückweg)
const GAP = 26;            // Luft zwischen Haupt- und Seitenspur
const ARM = 40;            // Höhe einer Abzweigung
const BEND = 12;           // Eckenradius der Prozesslinie
const LANE = SIDE + GAP;   // Breite einer Seitenspur inkl. Luft
const RUN = MAIN / 2 + GAP + SIDE / 2;   // Achse ↔ Mitte der Seitenspur

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
 * **Der Weg zwischen Achse und Seitenspur – EIN Pfad, echte Viertelkreise.**
 *
 * Vier Richtungen, vier Pfade über denselben Konstanten. Fork und Merge münden in eine Achse,
 * die darüber und darunter weiterläuft (ein **T**, eine Ecke); Herkunft und Rückweg treffen
 * sie dort, wo sie beginnt bzw. endet – die Linie biegt also **zweimal** ab (Notizen
 * #430/#431). Weil der Pfad durchgehend ist, gibt es an keiner Ecke eine Naht.
 */
const ELBOW: Record<string, { d: string; left: number; h: number; top?: number; bottom?: number }> = {
  // **Aus der Achse heraus – nicht als T, sondern als Gabelung** (Notiz #456): die Linie
  // biegt oben mit demselben Radius ab, mit dem sie unten in den Unterprozess einläuft. Sie
  // beginnt darum BEND über der Zelle, mitten auf der Achse.
  'fork-right': { left: -(MAIN / 2 + GAP), top: -BEND, h: ARM + BEND,
    d: `M0 0 A${BEND} ${BEND} 0 0 0 ${BEND} ${BEND} H${RUN - BEND} `
      + `A${BEND} ${BEND} 0 0 1 ${RUN} ${2 * BEND} V${ARM + BEND}` },
  // … und wieder hinein: herunter, nach links, dann mit Radius in die Achse einmünden.
  'merge-right': { left: -(MAIN / 2 + GAP), bottom: 0, h: ARM,
    d: `M${RUN} 0 V${ARM - 2 * BEND} A${BEND} ${BEND} 0 0 1 ${RUN - BEND} ${ARM - BEND} `
      + `H${BEND} A${BEND} ${BEND} 0 0 0 0 ${ARM}` },
  // aus dem Eltern-Auftrag herunter, nach rechts – und an der Achse hinunter
  'in-from-left': { left: SIDE / 2, bottom: 0, h: ARM,
    d: `M0 0 V${ARM - 2 * BEND} A${BEND} ${BEND} 0 0 0 ${BEND} ${ARM - BEND} `
      + `H${RUN - BEND} A${BEND} ${BEND} 0 0 1 ${RUN} ${ARM}` },
  // aus der Achse heraus, nach links – und hinunter auf den Rückweg-Knoten
  'out-to-left': { left: SIDE / 2, top: 0, h: ARM,
    d: `M${RUN} 0 V${BEND} A${BEND} ${BEND} 0 0 1 ${RUN - BEND} ${2 * BEND} `
      + `H${BEND} A${BEND} ${BEND} 0 0 0 0 ${3 * BEND} V${ARM}` },
};

function Elbow({ dir, strong }: {
  dir: 'fork-right' | 'merge-right' | 'in-from-left' | 'out-to-left'; strong?: boolean;
}) {
  const { d, left, h, top, bottom } = ELBOW[dir];
  return (
    <svg width={RUN} height={h} viewBox={`0 0 ${RUN} ${h}`} aria-hidden
      shapeRendering="geometricPrecision"
      style={{ position: 'absolute', left, top, bottom, overflow: 'visible', pointerEvents: 'none' }}>
      <path d={d} fill="none" stroke={lineColor(!!strong)} strokeWidth={lineW(!!strong)}
        strokeLinecap="butt" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * **Nachbar-Prozesse treten zurück** (Notizen #453/#460): links der übergeordnete Auftrag,
 * rechts der Abzweig. Beide gehören zum Bild, aber der Fokus liegt auf dem Prozess in der
 * **Mitte** – sie sind darum als Ganzes gedämpft und blassen zusätzlich zur Aussenkante hin
 * aus. Beim Hovern kommen sie ganz nach vorn: lesbar, ohne den Datensatz zu wechseln.
 *
 * Die Verbindungslinie bleibt davon unberührt – sie gehört zu diesem Fluss, nicht zum
 * Nachbarn. (Optik in ``globals.css: .ix-flow-aside``, damit der Hover ohne JS auskommt.)
 */
const aside = (to: 'left' | 'right') => ({
  className: 'ix-flow-aside',
  style: { ['--ix-fade' as string]: to } as React.CSSProperties,
});

/**
 * Eine Zeile des Flusses: die Achse in der Mitte, links Herkunft, rechts Abzweige.
 *
 * Die Spuren sind **fest** breit (siehe ``ELBOW``) und der Inhalt liegt jeweils an der zur
 * Achse zeigenden Kante – damit ist der Weg dorthin überall gleich lang. Ohne Nachbarn fällt
 * die Spurbreite auf 0 (``--flow-lane``), dann steht der Prozess allein und mittig.
 */
function Row({ children, left, right }: {
  children?: React.ReactNode; left?: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', width: '100%', justifyContent: 'center', alignItems: 'stretch' }}>
      <div style={{ width: 'var(--flow-lane)', flex: 'none', display: 'flex',
        justifyContent: 'flex-start', alignItems: 'center' }}>
        {left && <div style={{ width: SIDE, minWidth: 0 }}>{left}</div>}
      </div>
      <div style={{ width: MAIN, flex: 'none', display: 'flex', flexDirection: 'column',
        alignItems: 'center', minWidth: 0 }}>
        {children}
      </div>
      <div style={{ width: 'var(--flow-lane)', flex: 'none', display: 'flex',
        justifyContent: 'flex-end', alignItems: 'center' }}>
        {right && <div style={{ width: SIDE, minWidth: 0 }}>{right}</div>}
      </div>
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
        {qtyText(lot)} × {formatObjectId(lot.instance_object_id)}
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
  lots: Lots; onCreate: (lots: FlowLot[]) => void;
}) {
  const [hot, setHot] = useState(false);
  const list = [...lots.values()].filter((l) => l.quantity > 0);
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
  lots: Lots; onCreate?: (lots: FlowLot[]) => void; small?: boolean;
  /** Der Prozess ist hier schon vorbei – die Angabe tritt zurück, wie ein erledigtes Modul. */
  past?: boolean;
}) {
  if (lots.size === 0) return null;
  if (!onCreate) return <FlowLots lots={lots} past={past} small={small} />;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <FlowLots lots={lots} past={past} small={small} />
      <FlowShortcut lots={lots} onCreate={onCreate} />
    </span>
  );
}

function FlowLots({ lots, small, past }: { lots: Lots; small?: boolean; past?: boolean }) {
  const list = [...lots.values()];
  if (list.length === 0) return null;
  const shown = list.slice(0, 3);
  const rest = list.length - shown.length;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 3, margin: small ? '2px 0' : 0,
      // **Vergangenes verblasst** (Notiz #462) – dieselbe Dämpfung wie bei einem erledigten
      // Modul: was schon durch ist, soll den Blick nicht mehr auf sich ziehen.
      opacity: past ? 0.55 : 1, transition: 'opacity .16s' }}>
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
  selectedId, onSelectStep, onOpenOrder, renderPanel, lots = [], orderObjectId, goal,
  running = true, onCreateOrder }: {
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
  /** Objektnummer dieses Auftrags – die Terminal-Knoten nennen sie im Hover (#443/#444). */
  orderObjectId?: number | null;
  /** Was am Ende des Prozesses steht: Wunsch-Liefertermin und (intern) der Fakturierende. */
  goal?: { due?: string | null; seller?: string | null };
  /** Läuft der Auftrag noch? Ist er durch, ist in ihm nirgends mehr etwas aktiv (#467). */
  running?: boolean;
  /** Abkürzung am Prozess-Punkt: einen Auftrag auf genau dieses Material ansetzen (#455). */
  onCreateOrder?: (lots: FlowLot[]) => void;
}) {
  if (steps.length === 0 && !origin) return null;
  const processLabel = orderObjectId != null
    ? `Auftrag ${formatObjectId(orderObjectId)}` : 'Auftrag';

  // **Die Knoten der Achse**, in Reihenfolge: Module und die Äste an ihrer Stelle.
  //
  // **Mehrere Abzweige an derselben Stelle sind EINE Teilung in mehrere Richtungen** – nicht
  // mehrere Teilungen nacheinander. Das Material verlässt die Achse an EINEM Punkt; wie viel
  // wohin geht, sagt die Menge über jedem Unterprozess. Daraus folgt zweierlei:
  //
  //   * es gibt **einen** Fork und **einen** Merge (weniger Linien, keine Überlagerung), und
  //   * die Achse darunter trägt, was dem Auftrag **wirklich** geblieben ist – nicht einen
  //     Zwischenstand nach der ersten von zwei Teilungen (Testnotiz #469).
  //
  //            ┌──► Abweichung A (2 Stk)
  //      4 Stk ┤
  //            └──► Abweichung B (1 Stk)
  //      1 Stk  ▼  weiter im Prozess
  //
  // Die Alternative – je Ast ein eigener Fork mit eigenem Bypass – rechnete zwar auch
  // korrekt, behauptete aber eine Reihenfolge («erst A, dann B»), die es nicht gibt, und
  // liess die Achse zwischen zwei Ästen eine Menge tragen, die der Auftrag nie hielt.
  type Node = { step?: OrderStep; branches?: OrderDeviationInfo[]; res?: StepResolution[] };
  const nodes: Node[] = [];
  // Reihenfolge innerhalb einer Teilung = Entstehung (die Objektnummer steigt).
  const byAge = (l: OrderDeviationInfo[]) => [...l].sort((a, b) => a.object_id - b.object_id);
  const claimed = new Set(steps.flatMap((s) => (s.sub_orders ?? []).map((d) => d.object_id)));
  // Wer als Abzweig im Bild steht, braucht daneben keine Zeile mehr (#466, siehe `Resolutions`).
  const shownSubs = new Set([...claimed, ...subOrders.map((x) => x.object_id)]);
  const loose = subOrders.filter((x) => !claimed.has(x.object_id));
  if (loose.length) nodes.push({ branches: byAge(loose) });
  for (const s of steps) {
    const subs = s.sub_orders ?? [];
    const before = subs.filter((x) => x.stage === 'before');
    const after = subs.filter((x) => x.stage === 'after');
    const res = s.resolutions ?? [];
    if (before.length) nodes.push({ branches: byAge(before), res });
    nodes.push({ step: s, res: before.length ? [] : res });
    if (after.length) nodes.push({ branches: byAge(after) });
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
  // Linie stark.
  const nodeDone = (n: Node) => (n.step
    ? n.step.state === 'done'
    : (n.branches ?? []).every((b) => !isOpen(b)));
  let walked = 0;
  while (walked < nodes.length && nodeDone(nodes[walked])) walked++;

  // **Wo steht der Prozess GERADE?** – die eine Stelle, an der die Kante ihr Material stark
  // trägt und die Abkürzung sitzt; überall sonst ist es Vergangenheit (Notizen #462/#464/#467).
  // Die Regel des Nutzers in einem Satz: *stark ist es dort, wo der Prozessschritt gerade
  // aktiv ist.* Daraus folgt alles Weitere von selbst:
  //
  //   * **läuft der Auftrag nicht mehr** (abgeschlossen, abgebrochen, Entwurf) → gar keine
  //     Stelle. Sein Material ist längst beim übergeordneten Auftrag, dort ist der aktive
  //     Schritt – also verblasst hier alles und es gibt auch nichts anzusetzen (#467/#468).
  //   * **steht er an einem Abzweig** → am **Bypass**, nicht an der Kante darüber: dort hat
  //     sich das Material bereits geteilt, die Kante darüber zählt noch alles zusammen. Wer
  //     dort ansetzte, legte einen Auftrag auf Stücke an, die woanders hängen (#459/#464).
  //   * sonst → an der Kante über dem nächsten offenen Modul.
  const here: { at: number; bypass: boolean } | null = !running ? null
    : walked === nodes.length ? { at: nodes.length, bypass: false }
      : { at: walked, bypass: !!nodes[walked].branches };
  const liveEdge = (i: number) => here?.at === i && !here.bypass;
  const liveBypass = (i: number) => here?.at === i && here.bypass;

  let gateUsed = false;
  const rows: React.ReactNode[] = [];
  nodes.forEach((n, i) => {
    const reached = i <= walked;
    const passed = i < walked;
    rows.push(
      <Row key={`edge-${i}`}>
        <Axis strong={reached} />
        {reached && <EdgeMaterial lots={edges[i]} past={!liveEdge(i)}
          onCreate={liveEdge(i) ? onCreateOrder : undefined} />}
        <Axis strong={reached} />
      </Row>,
    );
    if (n.branches) {
      const res = n.res ?? [];
      // **Nur die offene Entscheidung ist ein Knoten** (Notiz #434). «wartet» und die
      // getroffene Antwort waren reine Information – und die steht längst im Fluss: ein
      // offener Abzweig IST das Warten, eine Auflösung steht als Zeile an ihrem Schritt.
      const decide = res.length === 0 && nodeDone(n) && !gateUsed && !!decision;
      if (decide) gateUsed = true;
      rows.push(
        // **Fork · Bypass · Merge**: die Achse läuft neben der Teilung weiter und trägt, was
        // auf dem Hauptauftrag geblieben ist (Notizen #425/#469).
        <Row key={`br-${n.branches[0].object_id}`}
          right={<BranchArm branches={n.branches} onOpen={onOpenOrder} />}>
          <Axis grow h={26} strong={reached} />
          {reached && <EdgeMaterial lots={edges[i + 1]} small past={!liveBypass(i)}
            onCreate={liveBypass(i) ? onCreateOrder : undefined} />}
          <Axis grow h={26} strong={passed} />
        </Row>,
      );
      if (decide || res.length > 0) {
        rows.push(
          <Row key={`gate-${n.branches[0].object_id}`}>
            <Axis h={10} strong={passed} />
            {decide ? <Gateway decision={decision} /> : <Resolutions list={res} shown={shownSubs} />}
          </Row>,
        );
      }
      return;
    }
    const s = n.step!;
    // **Ruhen heisst: nicht weiterarbeiten – nicht: nichts mehr ansehen** (Notizen #442/#465).
    // Zu bleibt genau EIN Schritt: der, an dem der Auftrag gerade hängt – dort lehnt das
    // Backend die Ausführung mit 409 ab, und davor sollte #378 bewahren. Alles andere ist
    // Lesen: ein **erledigter** Schritt trägt sein Protokoll, ein **künftiger** seine Planung.
    // Beide zu öffnen kann nichts auslösen, und in einem laufenden Auftrag geht es ohnehin.
    const readable = !paused || (s.state !== 'blocked' && s.state !== 'active');
    const selected = selectedId === String(s.id) && readable;
    rows.push(
      <Row key={`step-${s.id}`}>
        <StepCard type={s.step_type as StepType} state={s.state} selected={selected}
          muted={paused} detail={stepDetail(s)} badge={stepBadge(s)}
          hint={completionHint(s)}
          onClick={readable ? () => onSelectStep(String(s.id)) : undefined}>
          {selected && renderPanel?.(s)}
        </StepCard>
      </Row>,
    );
    if ((n.res ?? []).length > 0) {
      rows.push(
        <Row key={`res-${s.id}`}>
          <Axis h={10} strong={passed} />
          <Resolutions list={n.res!} shown={shownSubs} />
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
      <div style={{ width: '100%', minWidth: hasAside ? MAIN + 2 * LANE : MAIN,
        display: 'flex', flexDirection: 'column', alignItems: 'stretch',
        ...({ '--flow-lane': hasAside ? `${LANE}px` : '0px' } as React.CSSProperties) }}>
        {origin && (
          <>
            <Row left={<OriginArm origin={origin} onOpen={onOpenOrder} />} />
            <Row><Axis h={18} strong /></Row>
          </>
        )}
        <Row><FlowTerm kind="start" title={`Start · ${processLabel}`} /></Row>
        {rows}
        <Row key="edge-last">
          <Axis strong={done} />
          {/* Die letzte Kante zeigt, womit der Auftrag herauskommt – aber **stark nur, solange
              er läuft** (Notiz #467): ist er durch, hat er sein Material zurückgegeben und der
              aktive Schritt steht im übergeordneten Auftrag. */}
          {done && <EdgeMaterial lots={edges[nodes.length]} past={!liveEdge(nodes.length)}
            onCreate={liveEdge(nodes.length) ? onCreateOrder : undefined} />}
          <Axis strong={done} />
        </Row>
        <Row>
          {/* **Das Ziel gehört ans Prozessende** (Notiz #446) – und **neben** den Knoten,
              nicht darunter (#457): absolut gesetzt, damit der Kreis auf der Achse bleibt. */}
          <div style={{ position: 'relative', display: 'flex' }}>
            <FlowTerm kind="end" title={[`Ende · ${processLabel}`, goal?.due, goal?.seller]
              .filter(Boolean).join(' · ')} />
            {goal?.due && (
              <div style={{ position: 'absolute', left: '100%', top: '50%',
                transform: 'translateY(-50%)', marginLeft: 12, whiteSpace: 'nowrap',
                font: '500 11.5px var(--font-body)', color: 'var(--fg-4)' }}>{goal.due}</div>
            )}
          </div>
        </Row>
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
function StepCard({ type, state, detail, badge, hint, selected, muted: forced, compact,
  onClick, children }: {
  type: StepType; state: string;
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
          // Hängt der Klick am Container (Abzweig – die ganze Spalte öffnet den Datensatz),
          // erbt die Karte den Zeigefinger, statt ihn zu widerrufen (Notiz #454).
          cursor: onClick ? 'pointer' : 'inherit' }}>
        <div style={{ width: box, height: box, borderRadius: 'var(--r-sm)', flexShrink: 0,
          background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={compact ? 15 : 17} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: 'block', font: `800 ${compact ? 13.5 : 15}px var(--font-display)`,
            letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{meta.label}</span>
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

function BranchArm({ branches, onOpen }: {
  branches: OrderDeviationInfo[]; onOpen?: (id: number) => void;
}) {
  return (
    <div style={{ position: 'relative', width: '100%', minWidth: 0,
      paddingTop: ARM, paddingBottom: ARM }}>
      <Elbow dir="fork-right" strong={branches.some(branchStarted)} />
      <div {...aside('right')}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
          width: '100%', minWidth: 0 }}>
          {branches.map((b, i) => (
            <div key={b.object_id} style={{ display: 'flex', flexDirection: 'column',
              alignItems: 'center', width: '100%', minWidth: 0 }}>
              {i > 0 && <Axis h={20} strong={branchStarted(b)} />}
              <SubProcess info={b} onOpen={onOpen} />
            </div>
          ))}
        </div>
      </div>
      <Elbow dir="merge-right" strong={branches.every((b) => !isOpen(b))} />
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
          <FlowLots lots={inLots} small past={walked > 0} />
          <Axis h={10} strong={started} />
        </>
      )}
      <FlowTerm kind="start" size={30} title={`Start · ${hint}`} />
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
            hint={`${STEP_META[st.step_type as StepType]?.label ?? ''}: ${stepStateLabel(st.state)}`
              + ` · ${hint}`} />
        </div>
      ))}
      <Axis h={12} strong={started && walked === steps.length} />
      <FlowTerm kind="end" size={30} title={`Ende · ${hint}`} />
      {/* Was zurückkommt, steht erst da, wenn es zurück ist – und dann ist dieser Prozess
          vorbei, also tritt die Angabe zurück wie jede andere Vergangenheit (#467). */}
      {closed && outLots.size > 0 && (
        <>
          <Axis h={10} strong />
          <FlowLots lots={outLots} small past />
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

/** Wohin die Stücke beim Abschluss zurückgehen – derselbe Verweis, nur andersherum (#438). */
function ReturnArm({ origin, strong, onOpen }: {
  origin: OrderOrigin; strong?: boolean; onOpen?: (id: number) => void;
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
    && r.other_order_object_id != null && shown.has(r.other_order_object_id)));
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
