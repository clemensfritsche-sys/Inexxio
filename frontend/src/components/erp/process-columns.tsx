'use client';

import { useMemo, type CSSProperties, type ReactNode } from 'react';
import { MoreHorizontal } from 'lucide-react';
import {
  BEND, FlowFrame, FlowNode, flowMetrics, polyPath,
  type FlowAnchor, type FlowMetrics,
} from './process-flow';
import {
  Axis, FlowColumn, PROCESS_MAXW, Stroke, axisEdges, columnRows, rowOfNode,
  type ColumnRow, type DiagramStep, type UnitChip,
} from './process-diagram';
import { useErpNav } from './obj-id';
import { formatObjectId } from '@/lib/utils';
import { statusCfg } from '@/lib/process-status';
import type {
  GraphEdge, JourneyStop, Order, ProcessGraph, RelatedOrder,
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
 * ## Diese Datei rechnet nichts aus
 *
 * Sie **layoutet und zeichnet** – mehr nicht. Welche Knoten es gibt, welche Kanten sie
 * verbindet, wo Stücke stehen und welche Kante gegangen ist, sagt der Server
 * (`services/flow`, abgeleitet aus dem Ereignis-Log). Vorher stand genau das hier: die
 * Knotenfolge wurde aus Schritten und Stück-Gruppen zusammengebaut und die Linienstärke
 * aus dem **aktuellen** Zustand abgeleitet. Beides war eine zweite Wahrheit neben dem
 * Server, und die zweite las den Zustand statt den Log – sobald an einer Stelle nichts
 * mehr stand, verschwand sie samt der Abzweigung, die dort passiert war.
 *
 * ## Warum ein Raster mit Zeilen und keine drei nebeneinanderstehenden Säulen
 *
 * Ein Nebenauftrag hängt an **einem Zustandspunkt** der Hauptachse. Stehen die Spalten
 * unabhängig nebeneinander, liegt sein Start irgendwo – meist weit über oder unter dem
 * Punkt –, und die Verbindungslinie muss die halbe Höhe des Bildes überbrücken.
 *
 * Darum ist das Ganze **ein** Raster: jede Zeile der Mitte ist eine Rasterzeile, und ein
 * Nebenauftrag spannt von der Zeile seines **fork** bis zu der seines **join**. Die
 * Zeilen wachsen dann auf seine Höhe — und damit wächst die Hauptachse an genau dieser
 * Stelle mit. Was übrig bleibt, ist das Bild, das die Sache ohnehin ist: eine Teilung,
 * zwei parallele Wege, ein Zusammenfluss.
 *
 * ## Das Liniensystem: zwei Stärken, sonst nichts
 *
 * | | |
 * |---|---|
 * | **gegangen** | `--fg-2`, kräftig — hier ist Material durchgelaufen |
 * | **ausstehend** | `--border-2`, Haarlinie — hier steht es noch aus |
 *
 * Keine dritte Farbe, kein zweiter Linientyp. Eine Abzweigung ist **keine andere Art
 * Linie**, sondern derselbe Strang, der ausschert. Ob ein Stück zurückkehrt, sagt nicht
 * ein Strichmuster, sondern **ob es die Linie gibt**: eine gekappte Ausleihe hat keinen
 * Rückweg, und das Fehlen ist die Aussage.
 *
 * **Schmale Fenster**: unter `LANES_FROM` gibt es keine drei Spuren, die noch lesbar
 * wären. Dann stehen die Nachbarn untereinander – dieselben Spalten, nur ohne Querlinien.
 */

/** Zeilenabstand der Hauptachse – dieselbe Luft wie im Fluss einer einzelnen Spalte. */
const ROW_GAP = 14;
/**
 * Luft über dem Start-Objekt eines Nachbarn — **die Fahrbahn der Ausscherung**.
 *
 * Die Linie zweigt an der Hauptachse ab, läuft quer und muss **senkrecht** in das
 * Start-Objekt einlaufen (§8.1a). Dafür braucht sie einen Streifen, in dem keine Karte
 * steht: sonst liefe sie dahinter durch – gezeichnet, aber unsichtbar, weil die Knoten
 * über den Linien liegen.
 */
const NEIGHBOUR_DROP = 44;
/**
 * Wie weit eine Linie **senkrecht** in ein Objekt ein- bzw. aus ihm herausläuft.
 *
 * `2 · BEND`, damit die Ecke danach den vollen Radius bekommt: bei kürzerem Anlauf
 * staucht `polyPath` den Bogen, und genau das sieht man als Wackeln.
 */
const LEAD = 2 * BEND;
/**
 * Luft über dem Start-Objekt der Mitte. Ein übergeordneter Auftrag mündet **von oben**
 * ein; stünde der Start bei y = 0, gäbe es für diese Einmündung keinen Platz und die
 * Linie liefe aus dem Rahmen.
 */
const TOP_LEAD = 30;

/**
 * Eine Spalte des Bildes: ein Auftrag mit seinem Graph.
 *
 * `prefix` trennt die Knoten-Kennungen im gemeinsamen Rahmen – ohne ihn hiessen der
 * Start der Mitte und der Start eines Nachbarn gleich, und die Messung träfe den
 * falschen.
 */
interface Column {
  prefix: string;
  objectId: number;
  graph: ProcessGraph;
  steps: DiagramStep[];
  rows: ColumnRow[];
  side: 'left' | 'mid' | 'right';
  rel?: RelatedOrder;
}

export function ProcessColumns({ order, renderStep, onExpand, onDeviate, deviateBlocked,
  journeyIn, journeyOut }: {
  order: Order;
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  onExpand?: (stepId: number | null, active: boolean) => Promise<UnitChip[]>;
  /** Abweichung an einem Stück – nur in der **Mitte**, nie in einer fremden Spalte. */
  onDeviate?: (unitNumber: string) => void;
  /** Warum der Auslöser gesperrt ist (§5). Gesetzt = gesperrt, mit Grund im Hover. */
  deviateBlocked?: string;
  journeyIn: JourneyStop[];
  journeyOut: JourneyStop[];
}) {
  const steps = useSteps(order.steps ?? []);
  // **Eine Sache, eine Stelle.** Ein Auftrag, der schon als Spalte danebensteht, ist
  // kein zweiter Eintrag in der Journey-Zeile – dort bleibt, was die Spalten nicht
  // zeigen: der gewöhnliche Vorgänger bzw. Nachfolger auf der Zeitachse.
  const shownAside = useMemo(
    () => new Set([...(order.parents ?? []), ...(order.deviations ?? [])].map((r) => r.object_id)),
    [order.parents, order.deviations],
  );
  const inStops = useMemo(
    () => journeyIn.filter((j) => !shownAside.has(j.object_id)), [journeyIn, shownAside]);
  const outStops = useMemo(
    () => journeyOut.filter((j) => !shownAside.has(j.object_id)), [journeyOut, shownAside]);

  const mid: Column = useMemo(() => {
    const graph = order.flow ?? empty;
    return {
      prefix: '', objectId: order.object_id, graph, steps, side: 'mid',
      rows: columnRows(graph, {
        journeyIn: inStops.length > 0, journeyOut: outStops.length > 0,
      }),
    };
  }, [order.flow, order.object_id, steps, inStops.length, outStops.length]);

  const left = useMemo(() => (order.parents ?? []).map((r) => side(r, 'left')), [order.parents]);
  const right = useMemo(
    () => (order.deviations ?? []).map((r) => side(r, 'right')), [order.deviations]);
  const columns = useMemo(() => [mid, ...left, ...right], [mid, left, right]);

  // **Wo hängt ein Nachbar?** An seinem fork, bis zu seinem join – beides steht als
  // Kante in der Mitte. Findet sich keine (ein übergeordneter Auftrag hängt an unserem
  // Start), spannt er über alles: er ist vorher gelaufen und gehört nicht in den Takt.
  const span = useMemo(() => {
    const out = new Map<string, { from: number; to: number }>();
    right.forEach((c) => {
      const ref = `order:${c.objectId}`;
      const forks = (mid.graph.edges ?? []).filter((e) => e.kind === 'out' && e.to === ref);
      const joins = (mid.graph.edges ?? []).filter((e) => e.kind === 'back' && e.frm === ref);
      const rows = [
        ...forks.map((e) => rowOfNode(mid.rows, e.frm)),
        ...joins.map((e) => rowOfNode(mid.rows, e.to ?? '')),
      ].filter((r) => r >= 0);
      if (rows.length) out.set(c.prefix, { from: Math.min(...rows), to: Math.max(...rows) });
    });
    return out;
  }, [right, mid]);

  return (
    <FlowFrame lines={(a, size) => (
      <Wiring columns={columns} anchors={a} metrics={flowMetrics(size.w)} />
    )}>
      {(m) => {
        const column = (rowStyle?: (i: number) => CSSProperties) => (
          <FlowColumn
            graph={mid.graph} steps={steps} mode="ausfuehrung"
            activeStepId={order.active_step_id ?? null}
            // **Eingeklappt, ausser das Modul ist dran** (#696) – eine Regel, eine Stelle.
            expandedStepId={order.active_step_id ?? null}
            endStatus={order.end_status}
            renderStep={renderStep} onExpand={onExpand} onDeviate={onDeviate}
            deviateBlocked={deviateBlocked}
            journeyIn={inStops} journeyOut={outStops}
            containerStyle={rowStyle ? { display: 'contents' } : undefined}
            rowStyle={rowStyle}
          />
        );
        if (!m.lanes) {
          return (
            <div className="flex flex-col items-center gap-6">
              <div className="w-full" style={{ maxWidth: PROCESS_MAXW }}>{column()}</div>
              {[...left, ...right].map((c) => (
                <div key={c.prefix} className="w-full" style={{ maxWidth: PROCESS_MAXW }}>
                  <Neighbour col={c} />
                </div>
              ))}
              <Rest total={order.deviation_total ?? 0} shown={right.length} />
            </div>
          );
        }
        return (
          <>
            <div style={{
              display: 'grid', alignItems: 'start', justifyItems: 'center',
              columnGap: m.gap, rowGap: ROW_GAP, paddingTop: TOP_LEAD,
              // Die Mitte ist **fest**: als `minmax(0, …)` wäre sie eine Obergrenze, und
              // weil ihr Inhalt seine Breite aus der Spur bezieht, fiele sie auf die
              // Mindestbreite zusammen – der Fokus wäre die schmalste Spalte.
              gridTemplateColumns: `${m.side}px ${m.mid}px ${m.side}px`,
              // **Die Zeilen stehen ausdrücklich da.** Ohne sie sind es implizite Spuren,
              // und in einem impliziten Raster zeigt `-1` nicht auf die letzte Zeile.
              gridTemplateRows: `repeat(${mid.rows.length}, auto)`,
              justifyContent: 'center',
            }}>
              {/* **Der übergeordnete Auftrag steht daneben, nicht in einer Zeile.** Über
                  alle Zeilen gespannt zwingt er keine davon zu wachsen: er ist vorher
                  gelaufen und gehört nicht in den Takt dieser Achse. */}
              {left.length > 0 && (
                <div style={{ gridColumn: 1, gridRow: '1 / -1', alignSelf: 'start', width: '100%' }}
                  className="flex flex-col gap-7">
                  {left.map((c) => <Neighbour key={c.prefix} col={c} />)}
                </div>
              )}
              {column((i) => ({ gridColumn: 2, gridRow: i + 1 }))}
              {right.map((c) => {
                const s = span.get(c.prefix);
                return (
                  <div key={c.prefix}
                    style={{
                      gridColumn: 3, alignSelf: 'start', width: '100%',
                      gridRow: s ? `${s.from + 1} / ${s.to + 2}` : '1 / -1',
                    }}>
                    <Neighbour col={c} />
                  </div>
                );
              })}
            </div>
            <Rest total={order.deviation_total ?? 0} shown={right.length} />
          </>
        );
      }}
    </FlowFrame>
  );
}

const empty: ProcessGraph = { nodes: [], edges: [], problems: [] };

function side(rel: RelatedOrder, where: 'left' | 'right'): Column {
  const graph = rel.flow ?? empty;
  const steps = (rel.steps ?? []).map((s) => ({
    id: s.id, moduleType: s.module_type, label: s.label, waitingFor: s.waiting_for ?? [],
  }));
  return {
    prefix: `${where === 'left' ? 'p' : 'd'}${rel.object_id}:`,
    objectId: rel.object_id,
    graph, steps, rows: columnRows(graph), side: where, rel,
  };
}

/**
 * **Ein Nachbar ist sein Prozess — sonst nichts** (Testnotiz #702).
 *
 * Über der Spalte stand eine Karte mit Art, Objektnummer, Status und Stückzahl. Jede
 * dieser Angaben steht bereits im Bild: dass es eine Abweichung ist, sagt die Abzweigung;
 * wie weit sie ist, sagt ihre Linie; wie viele Stücke unterwegs sind, sagen die Pillen an
 * den Kanten. Eine Karte, die das wiederholt, ist eine zweite Wahrheit mit Platzbedarf.
 *
 * Geblieben ist das Einzige, was sie konnte und das Bild nicht: **hinführen**.
 */
function Neighbour({ col }: { col: Column }) {
  const nav = useErpNav();
  const rel = col.rel!;
  const cfg = statusCfg(rel.status);
  return (
    <FlowNode id={`${col.prefix}lane`} style={{ width: '100%' }}>
    <div
      role={nav ? 'button' : undefined}
      tabIndex={nav ? 0 : undefined}
      onClick={nav ? () => nav(rel.object_id) : undefined}
      onKeyDown={nav ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); nav(rel.object_id); }
      } : undefined}
      className="w-full"
      style={{ cursor: nav ? 'pointer' : undefined, paddingTop: NEIGHBOUR_DROP }}
      aria-label={`Auftrag ${formatObjectId(rel.object_id)} öffnen`}
      data-tip={`${col.side === 'left' ? 'Aus' : 'Abweichung'} ${formatObjectId(rel.object_id)}`
        + ` · ${cfg.label} · ${rel.unit_count} Stück`
        + ` · ${rel.returns ? 'kehrt zurück' : 'bleibt dort'} — öffnen`}
    >
      <FlowColumn
        graph={col.graph} steps={col.steps} prefix={col.prefix} mode="ausfuehrung"
        activeStepId={rel.active_step_id ?? null} endStatus={rel.end_status}
        faded
      />
    </div>
    </FlowNode>
  );
}

/** Abgeschnitten, aber nicht verschwiegen: eine stumme Liste sähe aus wie alles. */
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
 * **Alle Linien des Bildes.** Sie entstehen aus gemessenen Ankern und den Kanten des
 * Graphs; die Zahl der Module ist unbekannt und wächst (PROCESS_CORE.md §8).
 *
 * **Eine Kante wird gezeichnet, wenn beide Enden im Bild stehen.** Das ist die ganze
 * Regel für die Querverbindungen: der Graph eines Nachbarn nennt *alle* Aufträge, mit
 * denen er zu tun hatte – die meisten davon stehen hier nicht. Keine Seite muss darum
 * wissen, welche Spalten gerade sichtbar sind.
 */
function Wiring({ columns, anchors, metrics }: {
  columns: Column[];
  anchors: Record<string, FlowAnchor>;
  /** Ohne drei Spuren gibt es keine Querlinien – dann stehen die Nachbarn untereinander. */
  metrics: FlowMetrics;
}) {
  const byOrder = new Map(columns.map((c) => [c.objectId, c]));
  const at = (col: Column, ref: string, end: 'start' | 'end'): Hit | null => {
    if (!ref.startsWith('order:')) {
      const a = anchors[`${col.prefix}${ref}`];
      return a ? { a, col } : null;
    }
    const other = byOrder.get(Number(ref.slice('order:'.length)));
    if (!other) return null;
    const a = anchors[`${other.prefix}${end}`];
    return a ? { a, col: other, lane: anchors[`${other.prefix}lane`] } : null;
  };

  return (
    <>
      {columns.map((c) => (
        <Axis key={c.prefix || 'mid'} edges={axisEdges(c.graph)}
          anchors={anchors} prefix={c.prefix} />
      ))}
      {metrics.lanes && columns.flatMap((c) =>
        (c.graph.edges ?? [])
          .filter((e) => e.kind === 'out' || e.kind === 'back')
          .map((e) => (
            <Cross key={`${c.prefix}${e.id}`} edge={e} col={c} at={at} metrics={metrics} />
          )),
      )}
    </>
  );
}

/**
 * **Die Querverbindung — der Strang schert aus und kommt zurück.**
 *
 * Sie hängt an einem **Abzweigepunkt**, nicht an einem Modul (§12.4): ein Stück kann nur
 * abweichen, solange am Modul noch nichts eingegeben wurde – es hat das Modul also gar
 * nicht betreten. Die Linie geht darum **vor** dem Modul ab und mündet am Rückführpunkt
 * wieder ein, der ebenfalls davor liegt.
 *
 * **Sie verlässt die Achse mit einer Kurve, nicht mit einem Knick.** Der Zug beginnt
 * `2 · BEND` über dem Abzweigepunkt auf der Achse selbst und biegt dort mit vollem
 * Radius ab – wie eine Ausfahrt. Auf dem gemeinsamen Stück liegen beide Linien exakt
 * übereinander (gleiche Farbe, gleiche Stärke); zu sehen ist die Teilung, nicht die
 * Überlagerung.
 */
function Cross({ edge, col, at, metrics }: {
  edge: GraphEdge;
  col: Column;
  at: (col: Column, ref: string, end: 'start' | 'end') => Hit | null;
  metrics: FlowMetrics;
}) {
  const outward = edge.kind === 'out';
  const here = at(col, outward ? edge.frm : (edge.to ?? ''), 'end');
  const there = at(col, outward ? (edge.to ?? '') : edge.frm, outward ? 'start' : 'end');
  if (!here || !there) return null;

  // **Der Korridor liegt in der Spurlücke, nie unter einer Karte** (§8.1a): eine
  // gezeichnete Linie, die ein Knoten verdeckt, ist eine Linie, die es für den
  // Betrachter nicht gibt. Wie breit eine Spur ist, sagt das Raster – die Mitte trägt
  // `mid`, ein Nachbar `side`. Beide über `mid` zu rechnen traf die Lücke nur dann,
  // wenn die Linie zufällig in der Mitte begann.
  const half = (h: Hit) => (h.col.side === 'mid' ? metrics.mid : metrics.side) / 2;
  const dir = here.a.cx < there.a.cx ? 1 : -1;
  const corridor =
    ((here.a.cx + dir * half(here)) + (there.a.cx - dir * half(there))) / 2;

  // Die Rückführung verlässt den Nachbarn **unter seiner ganzen Spalte**, nicht knapp
  // unter seinem Ende-Objekt: darunter steht noch, was dort angekommen ist, und die
  // Linie liefe quer durch diese Pille.
  const clear = Math.max(there.a.bottom + LEAD, there.lane?.bottom ?? 0);

  const points: Array<[number, number]> = outward
    ? [
      [here.a.cx, here.a.cy - LEAD],
      [here.a.cx, here.a.cy],
      [corridor, here.a.cy],
      [corridor, there.a.top - LEAD],
      [there.a.cx, there.a.top - LEAD],
      [there.a.cx, there.a.top],
    ]
    : [
      [there.a.cx, there.a.bottom],
      [there.a.cx, clear],
      [corridor, clear],
      [corridor, here.a.cy],
      [here.a.cx, here.a.cy],
      [here.a.cx, here.a.cy + LEAD],
    ];
  return <Stroke d={polyPath(points)} walked={edge.walked} />;
}

/** Ein aufgelöstes Kantenende: der gemessene Knoten, seine Spalte, und deren Ausdehnung. */
interface Hit {
  a: FlowAnchor;
  col: Column;
  lane?: FlowAnchor;
}

// ─────────────────────────────────────────────────────────────────────────────

function useSteps(steps: NonNullable<Order['steps']>): DiagramStep[] {
  return useMemo(
    () => steps.map((s) => ({
      id: s.id, moduleType: s.module_type, label: s.label,
      // **Worauf das Modul wartet** – die Sperre wird eine Ebene tiefer gerendert
      // (`StepCard`), damit kein Modul sie selbst kennen muss (#698).
      waitingFor: s.waiting_for ?? [],
    })),
    [steps],
  );
}
