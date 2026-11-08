'use client';

import { useMemo, type CSSProperties } from 'react';
import { MoreHorizontal } from 'lucide-react';
import {
  BEND, FLOW_GAP, FlowFrame, channelX, channels, gutterFor, polyPath, port,
  type FlowAnchor, type FlowMetrics,
} from './process-flow';
import { Axis, FlowColumn, PROCESS_MAXW, Stroke, type ColumnProps } from './flow-column';
import { EMPTY_GRAPH, axisEdges, columnRows, hasJourney, journeyKeys, rowOfNode, type ColumnRow, type DiagramStep, type JourneyOrigin } from '../../lib/process-graph';
import { useErpNav } from './obj-id';
import { formatObjectId } from '@/lib/utils';
import { FREIGEGEBEN, statusCfg } from '@/lib/process-status';
import type {
  GraphEdge, JourneyStop, ProcessGraph, ProcessStepResponse, RelatedOrder,
} from '@/types';

/**
 * **Der Auftrag in seinem Zusammenhang — drei Spuren, ein Rahmen, EIN Liniensystem.**
 *
 * ```
 *   übergeordneter          eigener Ablauf              Abweichungen
 *   Auftrag                 (der Fokus)
 *        │                        │
 *        └───────────────────────►●  Start
 *                                 │
 *                                 ●  fork ──────────────► ● Start
 *                                 │  (wer blieb)          │
 *                                 │                    [Modul]
 *                                 │                       │
 *                                 ●  join ◄───────────────⚑ Ende
 *                                 │  (wer zurückkam)
 *                              [Modul]
 * ```
 *
 * Diese Datei **layoutet und zeichnet** nur; Knoten, Kanten, Stücke und «gegangen» sagt
 * der Server (`services/flow`, aus dem Log).
 *
 * **Ein Raster**: jede Zeile der Mitte ist eine Rasterzeile, ein Nebenauftrag spannt von
 * seinem **fork** bis zu seinem **join** – die Hauptachse wächst dort mit.
 *
 * **Zwei Stärken, sonst nichts**: gegangen kräftig (`--fg-2`), ausstehend Haarlinie
 * (`--border-2`). Ob ein Stück zurückkehrt, sagt, **ob es die Linie gibt**.
 *
 * **Schmale Fenster** (unter `LANES_FROM`): die Nachbarn stehen untereinander, ohne Querlinien.
 */

/** Wie weit eine Linie **senkrecht** in ein Objekt ein- bzw. ausläuft – `2 · BEND`, damit
 *  die Ecke danach den vollen Radius bekommt. */
const LEAD = 2 * BEND;
/**
 * Luft **über und unter** dem Prozess eines Nachbarn — die Fahrbahn seiner Verbindungen
 * (§8.1a). Gerechnet: `LEAD` + `BEND`, damit die Querverbindung eine einzige Waagrechte bleibt.
 */
const NEIGHBOUR_PAD = LEAD + BEND + 8;
/** Luft über der Mitte – ein übergeordneter Auftrag mündet von oben ein. */
const TOP_LEAD = LEAD + 10;
/** Luft unter dem Raster – eine Rückführung verlässt die Spalte unter ihrer letzten Zeile. */
const BOTTOM_LEAD = LEAD + 10;

/** Eine Spalte des Bildes; `prefix` trennt die Knoten-Kennungen im gemeinsamen Rahmen. */
interface Column {
  prefix: string;
  objectId: number;
  graph: ProcessGraph;
  steps: DiagramStep[];
  rows: ColumnRow[];
  side: Side;
  rel?: RelatedOrder;
}

/** **Die Mitte — der Fokus, von aussen bestückt** (laufender Auftrag oder Entwurf); was
 *  eine Nachbarspalte ausmacht, entsteht hier. */
type MidColumn =
  Omit<ColumnProps, 'prefix' | 'faded' | 'containerStyle' | 'rowStyle'
    | 'journeyIn' | 'journeyOut' | 'origins' | 'returns' | 'onToggleReturn'>
  & {
    /** Wie der Graph eines Nachbarn diese Spalte nennt (`order:<Nr>`); im Entwurf `DRAFT_OBJECT_ID`. */
    objectId: number;
  };

type Side = 'left' | 'mid' | 'right';

/** Von welcher bis zu welcher **Zeile** der Hauptachse ein Nachbar reicht. */
interface Span { from: number; to: number }

/** Der Rückführpunkt – die einzige Zeile, die am Ende ihrer Rasterzeile sitzt. */
const isJoin = (row?: ColumnRow) => !!row && 'node' in row && row.node.kind === 'join';

/** Die Spanne einer Spalte – fehlt sie, hängt der Nachbar an keinem Punkt dieser Achse. */
function spanOf(span: Map<string, Span>, col: Column): Span {
  return span.get(col.prefix) ?? { from: 0, to: 0 };
}


/** Die Kanalzuteilung: je Nachbar seine Spur, je Seite deren Anzahl. */
interface Wires {
  of: Map<string, number>;
  used: Record<Side, number>;
}

export function ProcessColumns({ mid: midProps, parents = [], deviations = [],
  deviationTotal = 0, journeyIn = [], journeyOut = [], origins = [], onToggleReturn,
  loopWalked = false }: {
  /** Was in der Mitte steht – der laufende Auftrag oder der Entwurf. */
  mid: MidColumn;
  /** Übergeordnete Aufträge (links). Im Entwurf die **Vorschau** aus `/validate`. */
  parents?: RelatedOrder[];
  /** Abweichungen (rechts) – gibt es nur am laufenden Auftrag. */
  deviations?: RelatedOrder[];
  /** Wie viele es insgesamt sind; gezeigt werden die ersten. */
  deviationTotal?: number;
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /** **Hier entstandene** Stücke – der Ast des Baums ohne Vorgänger. */
  origins?: JourneyOrigin[];
  /** **Nur im Entwurf**: die geplante Rückführung schalten – am Anfang ihrer Linie (`ReturnRow`). */
  onToggleReturn?: (parentObjectId: number) => void;
  /** **Die Schlaufe ist gegangen** – es gibt den Nachfolger (Wiederkehr §8): kräftige Linie. */
  loopWalked?: boolean;
}) {
  // Ein Auftrag, der schon als Spalte danebensteht, fehlt in der Journey-Zeile.
  const shownAside = useMemo(
    () => new Set([...parents, ...deviations].map((r) => r.object_id)),
    [parents, deviations],
  );
  const inStops = useMemo(
    () => journeyIn.filter((j) => !shownAside.has(j.object_id)), [journeyIn, shownAside]);
  const outStops = useMemo(
    () => journeyOut.filter((j) => !shownAside.has(j.object_id)), [journeyOut, shownAside]);

  // Was zu schalten ist, sagen die Eltern (`returns` vom Server); kein eigener Zustand.
  const returns = useMemo(
    () => (onToggleReturn ? parents.map((p) => ({ objectId: p.object_id, on: p.returns })) : []),
    [parents, onToggleReturn],
  );

  // Nur **ob** es die Zeilen gibt, zählt – die Listen wären als Abhängigkeit eine Endlosschleife.
  const withHead = !!midProps.head;
  const withTail = !!midProps.tail;
  const withLoop = !!midProps.loop;
  const journeyInRow = hasJourney(inStops, origins);
  const journeyOutRow = outStops.length > 0;
  const returnsRow = returns.length > 0;
  const mid: Column = useMemo(() => ({
    prefix: '', objectId: midProps.objectId, graph: midProps.graph, steps: midProps.steps,
    side: 'mid',
    // **Dieselben Zeilen, die die Spalte rendert** – inklusive der Slots.
    rows: columnRows(midProps.graph, {
      head: withHead, tail: withTail, loop: withLoop,
      journeyIn: journeyInRow, journeyOut: journeyOutRow, returns: returnsRow,
    }),
  }), [midProps.objectId, midProps.graph, midProps.steps, withHead, withTail, withLoop,
    journeyInRow, journeyOutRow, returnsRow]);

  const left = useMemo(() => parents.map((r) => side(r, 'left')), [parents]);
  const right = useMemo(() => deviations.map((r) => side(r, 'right')), [deviations]);
  const columns = useMemo(() => [mid, ...left, ...right], [mid, left, right]);
  /** Ohne Nachbarn gibt es keine Spuren – dann ist das Bild die Spalte selbst. */
  const solo = left.length === 0 && right.length === 0;

  // **Wo hängt ein Nachbar?** Von seinem fork bis zu seinem join; ohne Kante über alles.
  const span = useMemo(() => {
    const last = Math.max(0, mid.rows.length - 1);
    const all = { from: 0, to: last };
    const out = new Map<string, Span>();
    [...left, ...right].forEach((c) => {
      const ref = `order:${c.objectId}`;
      const edges = (mid.graph.edges ?? [])
        .filter((e) => (e.kind === 'out' && e.to === ref) || (e.kind === 'back' && e.frm === ref));
      const rows = edges
        .map((e) => rowOfNode(mid.rows, (e.kind === 'out' ? e.frm : e.to) ?? ''))
        .filter((r) => r >= 0);
      if (!rows.length) { out.set(c.prefix, all); return; }
      // **Ohne Rückfluss keine Klammer**: eine gekappte Ausleihe läuft vom fork bis ans Ende.
      const returns = edges.some((e) => e.kind === 'back');
      out.set(c.prefix, { from: Math.min(...rows), to: returns ? Math.max(...rows) : last });
    });
    return out;
  }, [left, right, mid]);

  // **Die Kanäle** (§1): überschneidende Abzweigungen bekommen verschiedene Spuren, gerechnet
  // auf Zeilennummern (steht fest, bevor gemessen wird).
  const wires = useMemo<Wires>(() => {
    const spans = (cols: Column[]) =>
      cols.map((c) => ({ key: c.prefix, ...spanOf(span, c) }));
    const l = channels(spans(left));
    const r = channels(spans(right));
    return {
      of: new Map([...l.of, ...r.of]),
      used: { left: l.used, right: r.used, mid: 0 },
    };
  }, [left, right, span]);

  // **Nachbarn mit überschneidenden Spannen stehen untereinander** in einem Band (sonst
  // lägen sie in derselben Zelle).
  const bands = useMemo(() => {
    const out: Array<Span & { cols: Column[] }> = [];
    [...right]
      .sort((a, b) => (spanOf(span, a).from - spanOf(span, b).from) || a.objectId - b.objectId)
      .forEach((c) => {
        const s = spanOf(span, c);
        const last = out[out.length - 1];
        if (last && s.from <= last.to) {
          last.to = Math.max(last.to, s.to);
          last.cols.push(c);
        } else out.push({ from: s.from, to: s.to, cols: [c] });
      });
    return out;
  }, [right, span]);

  const gutter = gutterFor(Math.max(wires.used.left, wires.used.right));

  return (
    <div className="mx-auto w-full"
      // Ohne Nachbarn trägt die Mitte ihr eigenes Mass.
      style={{ maxWidth: solo ? PROCESS_MAXW : undefined }}>
    <FlowFrame
      gutter={gutter}
      lines={(a, _size, m) => (
        <>
          <Wiring columns={columns} anchors={a} metrics={m} wires={wires}
            journeyIn={journeyKeys(inStops, origins)} journeyOut={journeyKeys(outStops)} />
          {withLoop && <LoopLine anchors={a} walked={loopWalked} />}
        </>
      )}
    >
      {(m) => {
        const column = (rowStyle?: (i: number) => CSSProperties) => (
          <FlowColumn
            {...midProps}
            prefix=""
            journeyIn={inStops} journeyOut={outStops} origins={origins}
            returns={returns} onToggleReturn={onToggleReturn}
            containerStyle={rowStyle ? { display: 'contents' } : undefined}
            rowStyle={rowStyle}
          />
        );
        if (solo || !m.lanes) {
          return (
            <div className="flex flex-col items-center gap-6">
              {/* Mit Wiederholung braucht ihre Linie links Platz neben den Karten. */}
              <div className="w-full" style={{ maxWidth: PROCESS_MAXW,
                paddingLeft: withLoop ? 2 * LOOP_OFFSET : undefined }}>{column()}</div>
              {[...left, ...right].map((c) => (
                <div key={c.prefix} className="w-full" style={{ maxWidth: PROCESS_MAXW }}>
                  <Neighbour col={c} />
                </div>
              ))}
              <Rest total={deviationTotal} shown={right.length} />
            </div>
          );
        }
        return (
          <>
            <div style={{
              display: 'grid', alignItems: 'start', justifyItems: 'center',
              columnGap: m.gap, rowGap: FLOW_GAP,
              paddingTop: TOP_LEAD, paddingBottom: BOTTOM_LEAD,
              // Die Mitte ist **fest** – als `minmax(0, …)` fiele sie auf die Mindestbreite.
              gridTemplateColumns: `${m.side}px ${m.mid}px ${m.side}px`,
              // Ausdrückliche Zeilen: im impliziten Raster zeigt `-1` nicht auf die letzte.
              gridTemplateRows: `repeat(${mid.rows.length}, auto)`,
              justifyContent: 'center',
            }}>
              {/* Der übergeordnete Auftrag spannt über alle Zeilen und lässt keine wachsen. */}
              {left.length > 0 && (
                <div style={{ gridColumn: 1, gridRow: '1 / -1', alignSelf: 'start', width: '100%' }}
                  className="flex flex-col gap-7">
                  {left.map((c) => <Neighbour key={c.prefix} col={c} />)}
                </div>
              )}
              {/* **Der Rückführpunkt sitzt am ENDE seiner Zeile** – dort, wo der Nachbar
                  aufhört (mit `NEIGHBOUR_PAD` als Luft). */}
              {column((i) => ({
                gridColumn: 2, gridRow: i + 1,
                ...(isJoin(mid.rows[i]) ? { alignSelf: 'end' as const } : null),
              }))}
              {bands.map((b) => (
                <div key={b.cols[0].prefix}
                  className="flex flex-col gap-7"
                  style={{
                    gridColumn: 3, alignSelf: 'start', width: '100%',
                    gridRow: `${b.from + 1} / ${b.to + 2}`,
                  }}>
                  {b.cols.map((c) => <Neighbour key={c.prefix} col={c} />)}
                </div>
              ))}
            </div>
            <Rest total={deviationTotal} shown={right.length} />
          </>
        );
      }}
    </FlowFrame>
    </div>
  );
}

/** Wie weit die Schlaufe links neben den Karten läuft. */
const LOOP_OFFSET = 14;

/**
 * **Die Schlaufe — vom Ende zurück zum Start, links herum** (Wiederkehr §8): von der Karte
 * der Wiederholung hinauf in den Start. Links, weil rechts die Abweichungen stehen.
 */
function LoopLine({ anchors, walked }: {
  anchors: Record<string, FlowAnchor>; walked: boolean;
}) {
  const card = anchors.loop;
  const start = anchors.start;
  if (!card || !start) return null;
  const from = port(card, 'left');
  const to = port(start, 'left');
  const x = card.left - LOOP_OFFSET;
  return (
    <Stroke walked={walked}
      d={polyPath([from, [x, from[1]], [x, to[1]], to])} />
  );
}

function side(rel: RelatedOrder, where: 'left' | 'right'): Column {
  const graph = rel.flow ?? EMPTY_GRAPH;
  return {
    prefix: `${where === 'left' ? 'p' : 'd'}${rel.object_id}:`,
    objectId: rel.object_id,
    graph, steps: toDiagramSteps(rel.steps), rows: columnRows(graph), side: where, rel,
  };
}

/**
 * **Ein Nachbar ist sein Prozess — sonst nichts**: ein Klick führt hin. Er schaltet nichts;
 * die Rückführung schaltet man an ihrer Linie (`ReturnRow`, §5).
 */
function Neighbour({ col }: { col: Column }) {
  const nav = useErpNav();
  const rel = col.rel!;
  const cfg = statusCfg(rel.status);
  const act = nav ? () => nav(rel.object_id) : undefined;
  return (
    <div
      role={act ? 'button' : undefined}
      tabIndex={act ? 0 : undefined}
      onClick={act}
      onKeyDown={act ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); }
      } : undefined}
      className="w-full"
      style={{ cursor: act ? 'pointer' : undefined,
               padding: `${NEIGHBOUR_PAD}px 0` }}
      aria-label={`Auftrag ${formatObjectId(rel.object_id)} öffnen`}
      data-tip={`${col.side === 'left' ? 'Aus' : 'Abweichung'} ${formatObjectId(rel.object_id)}`
        + ` · ${cfg.label} · ${rel.unit_count} Stück`
        + ` · ${rel.returns ? 'kehrt zurück' : 'bleibt dort'} — öffnen`}
    >
      <FlowColumn
        graph={col.graph} steps={col.steps} prefix={col.prefix} mode="ausfuehrung"
        activeStepId={rel.active_step_id ?? null} endStatus={FREIGEGEBEN}
        faded
      />
    </div>
  );
}

/** Abgeschnitten, aber nicht verschwiegen. */
function Rest({ total, shown }: { total: number; shown: number }) {
  if (total <= shown) return null;
  return (
    <p className="mt-3 flex items-center justify-center gap-1.5 text-[11px]"
      style={{ color: 'var(--fg-4)' }}>
      <MoreHorizontal size={13} />
      {total - shown} weitere {total - shown === 1 ? 'Abweichung' : 'Abweichungen'} –
      sie stehen im Feed unter ihrer eigenen Objektnummer.
    </p>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Linien — jede aus dem EINEN Generator, keine einzige aus Zahlen im Code
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Alle Linien des Bildes** – aus gemessenen Ankern und den Kanten des Graphs (§8). Eine
 * Kante wird gezeichnet, wenn beide Enden im Bild stehen.
 */
function Wiring({ columns, anchors, metrics, wires, journeyIn, journeyOut }: {
  columns: Column[];
  anchors: Record<string, FlowAnchor>;
  /** Ohne drei Spuren gibt es keine Querlinien – dann stehen die Nachbarn untereinander. */
  metrics: FlowMetrics;
  wires: Wires;
  /** Die Äste des Herkunfts-/Verbleibsbaums – nur in der Mitte, sie ist der Fokus. */
  journeyIn: Array<string | number>;
  journeyOut: Array<string | number>;
}) {
  const byOrder = new Map(columns.map((c) => [c.objectId, c]));
  const at = (col: Column, ref: string, end: 'start' | 'end'): Hit | null => {
    if (!ref.startsWith('order:')) {
      const a = anchors[`${col.prefix}${ref}`];
      return a ? { a, col } : null;
    }
    const other = byOrder.get(Number(ref.slice('order:'.length)));
    if (!other) return null;
    // **Eine Querlinie dockt an der Spalte an, nicht an einem Knoten darin** – oben an
    // ihrer ersten, unten an ihrer letzten Zeile.
    const rows = other.rows;
    const key = (end === 'start' ? rows[0] : rows[rows.length - 1])?.key;
    const a = key ? anchors[`${other.prefix}${key}`] : undefined;
    return a ? { a, col: other } : null;
  };

  return (
    <>
      {columns.map((c) => (
        <Axis key={c.prefix || 'mid'} edges={axisEdges(c.graph)}
          anchors={anchors} prefix={c.prefix}
          journeyIn={c.side === 'mid' ? journeyIn : []}
          journeyOut={c.side === 'mid' ? journeyOut : []} />
      ))}
      {metrics.lanes && columns.flatMap((c) =>
        (c.graph.edges ?? [])
          .filter((e) => e.kind === 'out' || e.kind === 'back')
          .map((e) => (
            <Cross key={`${c.prefix}${e.id}`} edge={e} col={c} at={at}
              metrics={metrics} wires={wires} />
          )),
      )}
    </>
  );
}

/**
 * **Die Querverbindung — der Strang schert aus und kommt zurück**, an einem Abzweige- bzw.
 * Rückführpunkt **vor** dem Modul (§12.4). Drei Regeln:
 *
 * 1. **Andocken nur an Ports** (`port(...)`) – eine Linie kennt nur den Rand eines Knotens.
 * 2. **Am Punkt immer in Flussrichtung** (nach unten): hinaus schert die Kurve aus, herein
 *    mündet sie ein – Zu- und Rückführung unterscheidet allein die Krümmung.
 * 3. **Senkrecht nur im eigenen Kanal** (`channels`, §1).
 */
function Cross({ edge, col, at, metrics, wires }: {
  edge: GraphEdge;
  col: Column;
  at: (col: Column, ref: string, end: 'start' | 'end') => Hit | null;
  metrics: FlowMetrics;
  wires: Wires;
}) {
  const outward = edge.kind === 'out';
  const here = at(col, outward ? edge.frm : (edge.to ?? ''), 'end');
  const there = at(col, outward ? (edge.to ?? '') : edge.frm, outward ? 'start' : 'end');
  if (!here || !there) return null;
  // Eine Querlinie führt **immer** von der Mitte weg oder zu ihr hin.
  const nb = here.col.side === 'mid' ? there.col : here.col;
  if (nb.side === 'mid' || (here.col.side !== 'mid' && there.col.side !== 'mid')) return null;

  // **Der Korridor liegt in der Spurlücke, nie unter einer Karte** (§8.1a).
  const half = (h: Hit) => (h.col.side === 'mid' ? metrics.mid : metrics.side) / 2;
  const dir = here.a.cx < there.a.cx ? 1 : -1;
  const centre = ((here.a.cx + dir * half(here)) + (there.a.cx - dir * half(there))) / 2;
  const corridor = channelX(centre, wires.of.get(nb.prefix) ?? 0, wires.used[nb.side]);

  const [hx, hy] = port(here.a, 'center');
  const points: Array<[number, number]> = outward
    ? (() => {
      const [tx, ty] = port(there.a, 'top');
      return [
        [hx, hy], [hx, hy + BEND],
        [corridor, hy + BEND], [corridor, ty - LEAD],
        [tx, ty - LEAD], [tx, ty],
      ];
    })()
    : (() => {
      const [tx, tb] = port(there.a, 'bottom');
      return [
        [tx, tb], [tx, tb + LEAD],
        [corridor, tb + LEAD], [corridor, hy - BEND],
        [hx, hy - BEND], [hx, hy],
      ];
    })();
  return <Stroke d={polyPath(points)} walked={edge.walked} />;
}

/** Ein aufgelöstes Kantenende: der gemessene Andockknoten und seine Spalte. */
interface Hit {
  a: FlowAnchor;
  col: Column;
}

// ─────────────────────────────────────────────────────────────────────────────

/** Die Module eines Auftrags, wie das Bild sie braucht — **eine Übersetzung** für Mitte und Nachbarn. */
export function toDiagramSteps(steps: ProcessStepResponse[] | null | undefined): DiagramStep[] {
  return (steps ?? []).map((s) => ({
    id: s.id, moduleType: s.module_type, label: s.label,
    // Eigenschaften des Modultyps reisen mit dem Schritt (Registry) – nie `moduleType === …`.
    tone: s.tone, terminal: s.terminal,
    verifies: s.verifies,
    moves: s.moves,
    // Die Sperre rendert `StepCard`.
    waitingFor: s.waiting_for ?? [],
    // Ableitungen des Servers – hier nicht nachgerechnet.
    openActions: s.open_actions, records: s.records,
  }));
}
