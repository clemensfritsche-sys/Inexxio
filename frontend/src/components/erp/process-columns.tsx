'use client';

import { useMemo, type CSSProperties, type ReactNode } from 'react';
import { GitBranch, MoreHorizontal } from 'lucide-react';
import { FlowFrame, flowMetrics, polyPath, type FlowAnchor, type FlowMetrics } from './process-flow';
import {
  FlowColumn, PROCESS_MAXW, flowNodes, statePointId, walkedEdges,
  type DiagramGroup, type DiagramStep, type FlowSpec, type UnitChip,
} from './process-diagram';
import { useErpNav } from './obj-id';
import { formatObjectId } from '@/lib/utils';
import { IM_PROZESS, statusCfg } from '@/lib/process-status';
import type { JourneyStop, Order, RelatedOrder } from '@/types';

/**
 * **Der Auftrag in seinem Zusammenhang — drei Spuren, ein Rahmen, EIN Liniensystem.**
 *
 * ```
 *   übergeordneter          eigener Ablauf              Abweichungen
 *   Auftrag                 (der Fokus)
 *        │                        │
 *        └───────────────────────►●  Start
 *                                 │
 *                              [Modul]
 *                                 │
 *                                 ●───────────────────► ● Start
 *                                 │  ausgeschert        │
 *                                 │                  [Modul]
 *                                 │                     │
 *                                 │◄────────────────────⚑ Ende
 *                              [Modul]   zurück
 * ```
 *
 * **Die Nachbarn zeigen ihren echten Ablauf**, nicht eine Zusammenfassung und kein
 * Symbol: es ist dieselbe Komponente (`FlowColumn`) mit denselben Daten. Eine gekürzte
 * Zweitform wäre eine zweite Darstellung derselben Sache – und die läuft irgendwann von
 * der ersten weg. Sie sind nur **verblasst**: der Fokus ist und bleibt die Mitte.
 *
 * ## Warum ein Raster mit Zeilen und keine drei nebeneinanderstehenden Säulen
 *
 * Ein Nebenauftrag hängt an **einem Zustandspunkt** der Hauptachse. Stehen die Spalten
 * unabhängig nebeneinander, liegt sein Start irgendwo – meist weit über oder unter dem
 * Punkt –, und die Verbindungslinie muss die halbe Höhe des Bildes überbrücken. Genau
 * daraus entstanden die langen, sich überlagernden Züge quer über fremde Karten.
 *
 * Darum ist das Ganze **ein** Raster: jeder Knoten der Mitte ist eine Zeile, und ein
 * Nebenauftrag steht in der Zeile seines Zustandspunkts. Die Zeile wächst dann auf seine
 * Höhe — und damit wächst **die Hauptachse an genau dieser Stelle mit**. Was übrig
 * bleibt, ist das Bild, das die Sache ohnehin ist: eine Teilung, zwei parallele Wege, ein
 * Zusammenfluss. Keine Rechnung, keine Rückkopplung von der Messung ins Layout — das
 * Raster tut es.
 *
 * ## Das Liniensystem: zwei Stärken, sonst nichts
 *
 * | | |
 * |---|---|
 * | **gegangen** | `--fg-2`, kräftig — hier ist Material durchgelaufen |
 * | **ausstehend** | `--border-2`, Haarlinie — hier steht es noch aus |
 *
 * Keine dritte Farbe, kein zweiter Linientyp. Eine Abzweigung ist **keine andere Art
 * Linie**, sondern derselbe Strang, der ausschert; sie folgt darum derselben Regel. Ob
 * ein Stück zurückkehrt, sagt nicht ein Strichmuster, sondern **ob es die Linie gibt**:
 * eine gekappte Ausleihe hat keinen Rückweg, und das Fehlen ist die Aussage.
 *
 * **Schmale Fenster**: unter `LANES_FROM` gibt es keine drei Spuren, die noch lesbar
 * wären. Dann stehen die Nachbarn untereinander – dieselben Spalten, nur ohne
 * Querlinien; was die Linie sagte, sagt dann die Kopfzeile über der Spalte.
 */

/** Zeilenabstand der Hauptachse – dieselbe Luft wie im Fluss einer einzelnen Spalte. */
const ROW_GAP = 14;
/**
 * Der Streifen zwischen der Kopfzeile eines Nachbarn und seinem Start-Objekt.
 *
 * Er ist **die Fahrbahn der Ausscherung**: die Linie muss senkrecht in das Start-Objekt
 * einlaufen (§2.5) und darf dabei keine Karte überqueren. Ohne diesen Streifen liefe sie
 * hinter der Kopfzeile durch – gezeichnet, aber unsichtbar, weil die Knoten über den
 * Linien liegen.
 */
const HEAD_GAP = 22;
/**
 * Luft über dem Start-Objekt der Mitte. Ein übergeordneter Auftrag mündet **von oben**
 * ein; stünde der Start bei y = 0, gäbe es für diese Einmündung keinen Platz und die
 * Linie liefe aus dem Rahmen.
 */
const TOP_LEAD = 26;

export function ProcessColumns({ order, renderStep, onExpand, onDeviate, deviateBlocked, journeyIn, journeyOut }: {
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
  const groups = useGroups(order.unit_groups ?? []);
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

  // **Die Zustandspunkte, an denen abgezweigt wurde** – sie müssen im Bild existieren,
  // auch wenn dort gerade nichts steht (Testnotiz #700). Ohne sie fiele die Linie auf
  // das Modul zurück, und die Abzweigung sähe aus, als käme sie aus ihm heraus.
  const branchPoints = useMemo(
    () => new Set<number | null>(
      (order.deviations ?? []).flatMap((r) => (r.branches ?? []).map((b) => b.at_step_id ?? null)),
    ),
    [order.deviations],
  );
  const main = useMemo(
    () => flowNodes({
      running: true, steps, groups, branchPoints,
      journeyIn: inStops.length, journeyOut: outStops.length,
    }),
    [steps, groups, branchPoints, inStops.length, outStops.length],
  );
  const left = useMemo(() => (order.parents ?? []).map((r) => side(r, 'p')), [order.parents]);
  const right = useMemo(() => (order.deviations ?? []).map((r) => side(r, 'd')), [order.deviations]);
  const sides = useMemo(() => [...left, ...right], [left, right]);

  const walked = walkedEdges(main, true);
  const rowOf = (nodeId: string) => 1 + Math.max(0, main.findIndex((n) => n.id === nodeId));
  // Je Zustandspunkt **eine** Zelle: zwei Abweichungen an derselben Stelle stehen
  // untereinander in derselben Zeile, statt sich zu überlagern.
  const cells = useMemo(() => {
    const by = new Map<string, SideFlow[]>();
    right.forEach((s) => {
      const key = s.points[0] ?? statePointId(null);
      const list = by.get(key);
      if (list) list.push(s); else by.set(key, [s]);
    });
    return [...by].map(([anchor, list]) => ({ anchor, list }));
  }, [right]);

  return (
    <FlowFrame lines={(a, size) => (
      <Wiring
        main={main} walked={walked} left={left} right={right}
        anchors={a} metrics={flowMetrics(size.w)}
      />
    )}>
      {(m) => {
        const column = (nodeStyle?: (i: number) => CSSProperties) => (
          <FlowColumn
            nodes={main} mode="ausfuehrung" groups={groups}
            activeStepId={order.active_step_id ?? null}
            // **Eingeklappt, ausser das Modul ist dran** (#696) – eine Regel, eine Stelle.
            expandedStepId={order.active_step_id ?? null}
            endStatus={order.end_status}
            renderStep={renderStep} onExpand={onExpand} onDeviate={onDeviate}
            deviateBlocked={deviateBlocked}
            journeyIn={inStops} journeyOut={outStops}
            containerStyle={nodeStyle ? { display: 'contents' } : undefined}
            nodeStyle={nodeStyle}
          />
        );
        if (!m.lanes) {
          return (
            <div className="flex flex-col items-center gap-6">
              <div className="w-full" style={{ maxWidth: PROCESS_MAXW }}>{column()}</div>
              {sides.map((s) => (
                <div key={s.prefix} className="w-full" style={{ maxWidth: PROCESS_MAXW }}>
                  <Neighbour side={s} />
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
              // und in einem impliziten Raster zeigt `-1` nicht auf die letzte Zeile: der
              // übergeordnete Auftrag spannte dann über genau eine und blähte sie auf.
              gridTemplateRows: `repeat(${main.length}, auto)`,
              justifyContent: 'center',
            }}>
              {/* **Der übergeordnete Auftrag steht daneben, nicht in einer Zeile.** Über
                  alle Zeilen gespannt zwingt er keine davon zu wachsen: er ist vorher
                  gelaufen und gehört nicht in den Takt dieser Achse. Eine eigene Zeile
                  über dem Bild hätte den eigenen Prozess um seine ganze Höhe nach unten
                  geschoben – und der ist das, was man sehen will. */}
              {left.length > 0 && (
                <div style={{ gridColumn: 1, gridRow: '1 / -1', alignSelf: 'start', width: '100%' }}
                  className="flex flex-col gap-7">
                  {left.map((s) => <Neighbour key={s.prefix} side={s} />)}
                </div>
              )}
              {column((i) => ({ gridColumn: 2, gridRow: 1 + i }))}
              {cells.map((c) => (
                <div key={c.anchor} className="flex flex-col gap-7"
                  style={{ gridColumn: 3, gridRow: rowOf(c.anchor), alignSelf: 'start', width: '100%' }}>
                  {c.list.map((s) => <Neighbour key={s.prefix} side={s} />)}
                </div>
              ))}
            </div>
            <Rest total={order.deviation_total ?? 0} shown={right.length} />
          </>
        );
      }}
    </FlowFrame>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Eine Nachbar-Spalte
// ─────────────────────────────────────────────────────────────────────────────

interface SideFlow {
  prefix: string;
  where: 'p' | 'd';
  rel: RelatedOrder;
  steps: DiagramStep[];
  groups: DiagramGroup[];
  nodes: FlowSpec[];
  walked: number;
  /** Die Knoten-Ids **in der Mitte**, an denen dieser Nachbar ansetzt (Zustandspunkte). */
  points: string[];
}

function side(rel: RelatedOrder, where: 'p' | 'd'): SideFlow {
  const prefix = `${where}${rel.object_id}:`;
  const steps = (rel.steps ?? []).map((s) => ({
    id: s.id, moduleType: s.module_type, label: s.label, waitingFor: s.waiting_for ?? [],
  }));
  const groups = (rel.unit_groups ?? []).map((g) => ({
    currentStepId: g.current_step_id ?? null, status: g.status,
    active: g.active, count: g.count,
  }));
  const nodes = flowNodes({ prefix, running: true, steps, groups });
  // **Wo die Stücke diesen Auftrag verlassen bzw. betreten haben – am Zustandspunkt.**
  //
  // Beim übergeordneten Auftrag ist das die Stelle in **seinem** Ablauf, an der unsere
  // Stücke stehen (``active: false``): dort sind sie ausgeschert, nicht an seinem Ende.
  // Die Linie an sein Ende zu hängen wäre die Behauptung, sie hätten seinen Prozess
  // durchlaufen – und das ist bei einer Übernahme mitten im Ablauf schlicht falsch.
  const points = where === 'p'
    ? [...new Set(groups.filter((g) => !g.active)
        .map((g) => statePointId(g.currentStepId, prefix)))]
    : (rel.branches ?? []).map((b) => statePointId(b.at_step_id ?? null));
  return { prefix, where, rel, steps, groups, nodes, walked: walkedEdges(nodes, true), points };
}

/** Kopfzeile + Ablauf eines Nachbarn – **eine** Einheit, damit sie im Raster zusammenbleiben. */
function Neighbour({ side: s }: { side: SideFlow }) {
  return (
    <div className="w-full">
      <SideHead side={s} />
      <Side side={s} />
    </div>
  );
}

/** Wer ist das, und was verbindet ihn mit der Mitte. Ein Klick öffnet ihn. */
function SideHead({ side: s }: { side: SideFlow }) {
  const nav = useErpNav();
  const cfg = statusCfg(s.rel.status);
  return (
    <button
      type="button"
      onClick={nav ? () => nav(s.rel.object_id) : undefined}
      disabled={!nav}
      className="w-full flex flex-wrap items-center gap-x-2 gap-y-1 text-left px-2 py-1.5 rounded-ds-md"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)',
               marginBottom: HEAD_GAP }}
      data-tip="Öffnen – dann steht dieser Auftrag in der Mitte"
    >
      <GitBranch size={12} style={{ color: 'var(--fg-4)' }} />
      <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
        {s.where === 'p' ? 'aus' : 'Abweichung'}
      </span>
      <span className="ix-tnum text-xs" style={{ color: 'var(--fg-2)' }}>
        {formatObjectId(s.rel.object_id)}
      </span>
      <span className="text-[11px]" style={{ color: cfg.color }}>{cfg.label}</span>
      <span className="flex-1" />
      <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
        {s.rel.unit_count} Stück · {s.rel.returns ? 'kehrt zurück' : 'bleibt dort'}
      </span>
    </button>
  );
}

function Side({ side: s }: { side: SideFlow }) {
  return (
    <FlowColumn
      nodes={s.nodes} mode="ausfuehrung" groups={s.groups}
      activeStepId={s.rel.active_step_id ?? null} endStatus={s.rel.end_status}
      faded
    />
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
// Linien — **eine** Stelle, zwei Stärken
// ─────────────────────────────────────────────────────────────────────────────

/** Gegangen oder ausstehend – die einzige Unterscheidung, die eine Linie trägt. */
function Line({ d, walked }: { d: string; walked: boolean }) {
  if (!d) return null;
  return (
    <path
      d={d}
      fill="none"
      stroke={walked ? 'var(--fg-2)' : 'var(--border-2)'}
      strokeWidth={walked ? 2.5 : 1.5}
      strokeLinecap="round"
    />
  );
}

/** Die Achse einer Spalte: Knoten für Knoten, senkrecht, unten heraus und oben hinein. */
function Axis({ ids, anchors, walked }: {
  ids: string[]; anchors: Record<string, FlowAnchor>; walked: number;
}) {
  const out: ReactNode[] = [];
  for (let i = 0; i < ids.length - 1; i++) {
    const A = anchors[ids[i]];
    const B = anchors[ids[i + 1]];
    if (!A || !B) continue;
    out.push(
      <Line key={ids[i]} d={polyPath([[A.cx, A.bottom], [B.cx, B.top]])} walked={i < walked} />,
    );
  }
  return <>{out}</>;
}

/**
 * **Alle Linien des Bildes.** Sie entstehen aus gemessenen Ankern, nirgends aus Zahlen im
 * Code – die Zahl der Module ist unbekannt und wächst (PROCESS_CORE.md §8).
 */
function Wiring({ main, walked, left, right, anchors, metrics }: {
  main: FlowSpec[];
  walked: number;
  left: SideFlow[];
  right: SideFlow[];
  anchors: Record<string, FlowAnchor>;
  /** Ohne drei Spuren gibt es keine Querlinien – dann sagt es die Kopfzeile. */
  metrics: FlowMetrics;
}) {
  const ids = main.map((n) => n.id);
  const lanes = metrics.lanes;
  return (
    <>
      <Axis ids={ids} anchors={anchors} walked={walked} />
      {[...left, ...right].map((s) => (
        <Axis key={s.prefix} ids={s.nodes.map((n) => n.id)} anchors={anchors} walked={s.walked} />
      ))}
      {lanes && left.map((s) => (
        <Inflow key={`i-${s.prefix}`} side={s} anchors={anchors} metrics={metrics} />
      ))}
      {lanes && right.map((s) => (
        <Detour key={`d-${s.prefix}`} side={s} anchors={anchors} ids={ids} gap={metrics.gap} />
      ))}
    </>
  );
}

/**
 * **Der übergeordnete Auftrag mündet in unseren Start.**
 *
 * Aus seinem **Ende**, nicht aus seinem Start: dort hat er die Stücke abgegeben. Beide
 * Enden der Linie stehen senkrecht auf ihrem Objekt (§2.5) – ein Start-Objekt wird von
 * oben betreten, ein Ende-Objekt unten verlassen.
 */
function Inflow({ side: s, anchors, metrics }: {
  side: SideFlow; anchors: Record<string, FlowAnchor>; metrics: FlowMetrics;
}) {
  const to = anchors.start;
  if (!to) return null;
  // Der Korridor liegt in der Spurlücke, die Fahrbahn über dem Start – beide führen an
  // jeder Karte vorbei, nicht darunter durch.
  const corridor = to.cx - metrics.mid / 2 - metrics.gap / 2;
  const lane = to.top - TOP_LEAD / 2;
  return (
    <>
      {s.points.map((id) => {
        const P = anchors[id];
        if (!P) return null;
        return (
          <Line
            key={id}
            d={polyPath([
              [P.right, P.cy],
              [corridor, P.cy],
              [corridor, lane],
              [to.cx, lane],
              [to.cx, to.top],
            ])}
            walked
          />
        );
      })}
    </>
  );
}

/**
 * **Die Ausscherung — der Hauptstrang zweigt ab und kommt zurück.**
 *
 * Sie hängt an einem **Zustandspunkt**, nicht an einem Modul (#700): ein Stück kann nur
 * abweichen, solange am Modul noch nichts eingegeben wurde, es hat das Modul also gar
 * nicht betreten. Die Linie geht darum **vor** dem Modul ab und mündet **vor** demselben
 * Modul wieder ein – dazwischen liegt kein Prozessobjekt, es ist derselbe Punkt.
 *
 * Weil der Nebenauftrag in der **Zeile** seines Punktes steht, liegt sein Start neben dem
 * Punkt und sein Ende neben der Einmündung: beide Linien sind kurz, laufen abwärts und
 * kreuzen nichts. Der Weg daneben auf der Hauptachse ist der der Stücke, die geblieben
 * sind – Teilung, zwei Wege, Zusammenfluss.
 *
 * **Kehrt nichts zurück, gibt es keine Rückführungslinie.** Das Fehlen ist die Aussage;
 * ein zweites Strichmuster dafür wäre eine Sprache, die man erst lernen müsste.
 *
 * Ein Auftrag kann an **mehreren** Punkten zugegriffen haben – dann gibt es je Punkt ein
 * Linienpaar. Ein einzelner Anker hätte sich für einen entschieden und die anderen
 * verschwiegen.
 */
function Detour({ side: s, anchors, ids, gap }: {
  side: SideFlow; anchors: Record<string, FlowAnchor>; ids: string[]; gap: number;
}) {
  const start = anchors[`${s.prefix}start`];
  const end = anchors[`${s.prefix}end`];
  if (!start || !end) return null;
  // **Zurück heisst zurück.** Solange der Nebenauftrag läuft, steht die Rückführung aus –
  // dieselbe Aussage, aus der auch die Modulsperre entsteht (`process.pending_returns`).
  const home = s.rel.status !== IM_PROZESS;
  return (
    <>
      {s.points.map((id) => {
        const P = anchors[id];
        if (!P) return null;
        const next = anchors[ids[ids.indexOf(id) + 1]];
        // Der Korridor liegt in der Spurlücke, die Fahrbahn im Streifen unter der
        // Kopfzeile – beide führen an jeder Karte vorbei, nicht darunter durch.
        const corridor = P.right + gap / 2;
        const lane = start.top - HEAD_GAP / 2;
        return (
          <g key={id}>
            <Line
              d={polyPath([
                [P.right, P.cy],
                [corridor, P.cy],
                [corridor, lane],
                [start.cx, lane],
                [start.cx, start.top],
              ])}
              walked
            />
            {s.rel.returns && next && (
              <Line
                d={polyPath([
                  [end.cx, end.bottom],
                  [end.cx, next.top - ROW_GAP / 2],
                  [P.cx, next.top - ROW_GAP / 2],
                  [P.cx, next.top],
                ])}
                walked={home}
              />
            )}
          </g>
        );
      })}
    </>
  );
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

function useGroups(groups: NonNullable<Order['unit_groups']>): DiagramGroup[] {
  return useMemo(
    () => groups.map((g) => ({
      currentStepId: g.current_step_id ?? null, status: g.status,
      active: g.active, count: g.count,
    })),
    [groups],
  );
}
