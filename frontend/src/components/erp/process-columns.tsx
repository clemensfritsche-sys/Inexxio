'use client';

import { useMemo, type ReactNode } from 'react';
import { GitBranch, MoreHorizontal } from 'lucide-react';
import { FlowFrame, polyPath, type FlowAnchor } from './process-flow';
import {
  FlowColumn, PROCESS_MAXW, flowNodes, statePointId, walkedEdges,
  type DiagramGroup, type DiagramStep, type FlowSpec, type UnitChip,
} from './process-diagram';
import { useErpNav } from './obj-id';
import { formatObjectId } from '@/lib/utils';
import { statusCfg } from '@/lib/process-status';
import type { JourneyStop, Order, RelatedOrder } from '@/types';

/**
 * **Der Auftrag in seinem Zusammenhang — drei Spuren, ein Rahmen.**
 *
 * ```
 * ┌───────────────────┬──────────────────┬────────────────────┐
 * │ Übergeordneter    │  Eigener Ablauf  │  Abweichungen      │
 * │ Auftrag           │  (der Fokus)     │                    │
 * └───────────────────┴──────────────────┴────────────────────┘
 * ```
 *
 * **Die Nachbarn zeigen ihren echten Ablauf**, nicht eine Zusammenfassung und kein
 * Symbol: es ist dieselbe Komponente (`FlowColumn`) mit denselben Daten. Eine gekürzte
 * Zweitform wäre eine zweite Darstellung derselben Sache – und die läuft irgendwann von
 * der ersten weg. Sie sind nur **verblasst**: der Fokus ist und bleibt die Mitte.
 *
 * **Die Linien führen.** Alle Spalten liegen in **einem** `FlowFrame`, also in einem
 * Koordinatensystem – dadurch lässt sich die Abzweigung genau dort zeichnen, wo sie
 * passiert ist, und der Rückweg genau dorthin, wo das Stück wieder einsteigt. Zwei
 * Rahmen hätten zwei Nullpunkte und damit keine gemeinsame Linie.
 *
 * **Schmale Fenster**: unter `WIDE` gibt es keine drei Spuren, die noch lesbar wären.
 * Dann stehen die Nachbarn untereinander – dieselben Spalten, nur ohne Querlinien; was
 * die Linie sagte, sagt dann die Kopfzeile über der Spalte.
 */

/** Abstand zwischen zwei Spuren. */
const GAP = 20;
/**
 * Wie schmal ein Nachbar werden darf, bevor drei Spuren keinen Sinn mehr ergeben.
 *
 * **Gemessen, nicht geschätzt.** Bei 240 px lag die Schwelle bei einem Rahmen von
 * 1160 px – und der Rahmen ist im Detailfenster rund 380 px schmaler als das Fenster
 * (Feed + Polsterung). Drei Spuren erschienen damit erst ab **1536 px Fensterbreite**,
 * also auf keinem Notebook: 1512 → gestapelt, 1440 → gestapelt, 1366 → gestapelt. Der
 * Nachbar ist eine verblasste Nebenspur, keine Leseansicht; bei 160 px trägt er seine
 * Modul-Karten noch, und die Schwelle liegt bei 1366 px Fensterbreite.
 */
const SIDE_MINW = 160;
/**
 * Ab dieser gemessenen **Rahmen**breite passen drei Spuren nebeneinander: die feste
 * Mitte, zwei noch lesbare Nachbarn und die Abstände. Darunter stehen sie untereinander.
 */
const WIDE = PROCESS_MAXW + 2 * SIDE_MINW + 2 * GAP;
/** Wie breit ein Nachbar höchstens wird. Schmaler als die Mitte – sie ist der Fokus. */
const SIDE_MAXW = 420;

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
  const sides = useMemo(
    () => [
      ...(order.parents ?? []).map((r) => side(r, 'p')),
      ...(order.deviations ?? []).map((r) => side(r, 'd')),
    ],
    [order.parents, order.deviations],
  );

  const walked = walkedEdges(main, true);

  return (
    <FlowFrame lines={(a, size) => (
      <>
        <Lines ids={main.map((n) => n.id)} anchors={a} walked={walked} />
        {sides.map((s) => (
          <Lines key={s.prefix} ids={s.nodes.map((n) => n.id)} anchors={a} walked={s.walked} />
        ))}
        {size.w >= WIDE && sides.map((s) => (
          <Branch key={`b-${s.prefix}`} side={s} anchors={a} />
        ))}
      </>
    )}>
      {(width) => {
        const wide = width >= WIDE;
        const left = sides.filter((s) => s.where === 'p');
        const right = sides.filter((s) => s.where === 'd');
        const column = (
          <FlowColumn
            nodes={main} mode="ausfuehrung" groups={groups}
            activeStepId={order.active_step_id ?? null}
            // **Eingeklappt, ausser das Modul ist dran** (#696) – eine Regel, eine Stelle.
            expandedStepId={order.active_step_id ?? null}
            endStatus={order.end_status}
            renderStep={renderStep} onExpand={onExpand} onDeviate={onDeviate}
            deviateBlocked={deviateBlocked}
            journeyIn={inStops} journeyOut={outStops}
          />
        );
        if (!wide) {
          return (
            <div className="flex flex-col items-center gap-6">
              <div className="w-full" style={{ maxWidth: PROCESS_MAXW }}>{column}</div>
              {[...left, ...right].map((s) => (
                <div key={s.prefix} className="w-full" style={{ maxWidth: PROCESS_MAXW }}>
                  <SideHead side={s} />
                  <Side side={s} />
                </div>
              ))}
              <Rest total={order.deviation_total ?? 0} shown={right.length} />
            </div>
          );
        }
        return (
          <div style={{
            display: 'grid', alignItems: 'start', gap: GAP,
            // Die Mitte ist **fest**: als `minmax(0, …)` wäre sie eine Obergrenze, und
            // weil ihr Inhalt seine Breite aus der Spur bezieht, fiele sie auf die
            // Mindestbreite zusammen – der Fokus wäre die schmalste Spalte.
            gridTemplateColumns: `minmax(0,1fr) ${PROCESS_MAXW}px minmax(0,1fr)`,
          }}>
            <Stack sides={left} align="end" />
            <div>{column}</div>
            <div>
              <Stack sides={right} align="start" />
              <Rest total={order.deviation_total ?? 0} shown={right.length} />
            </div>
          </div>
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
  // Aus einem **übergeordneten** Auftrag kommen die Stücke am Start herein – das ist kein
  // Zustandspunkt im eigenen Ablauf, sondern das Start-Objekt selbst.
  const points = where === 'p'
    ? ['start']
    : (rel.branches ?? []).map((b) => statePointId(b.at_step_id ?? null));
  return { prefix, where, rel, steps, groups, nodes, walked: walkedEdges(nodes, true), points };
}

/**
 * Eine Seitenspur. Sie rendert **auch leer** ein Element – ein ``null`` wäre kein
 * Grid-Element, und dann rutschte die Mitte in die erste Spur und bekäme deren Breite.
 * Genau so war der Fokus plötzlich die schmalste Spalte.
 */
function Stack({ sides, align }: { sides: SideFlow[]; align: 'start' | 'end' }) {
  if (!sides.length) return <div />;
  return (
    <div className="flex flex-col gap-7" style={{ alignItems: align === 'end' ? 'flex-end' : 'flex-start' }}>
      {sides.map((s) => (
        <div key={s.prefix} className="w-full" style={{ maxWidth: SIDE_MAXW }}>
          <SideHead side={s} />
          <Side side={s} />
        </div>
      ))}
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
      className="w-full flex flex-wrap items-center gap-x-2 gap-y-1 text-left mb-2 px-2 py-1.5 rounded-ds-md"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)' }}
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

/** Beim Nachbarn wird nichts ausgefüllt – er hat darum auch nichts aufzuklappen. */

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
// Linien
// ─────────────────────────────────────────────────────────────────────────────

function Lines({ ids, anchors, walked }: {
  ids: string[]; anchors: Record<string, FlowAnchor>; walked: number;
}) {
  const out: ReactNode[] = [];
  for (let i = 0; i < ids.length - 1; i++) {
    const A = anchors[ids[i]];
    const B = anchors[ids[i + 1]];
    if (!A || !B) continue;
    out.push(
      <path
        key={ids[i]}
        d={polyPath([[A.cx, A.bottom], [B.cx, B.top]])}
        fill="none"
        stroke={i < walked ? 'var(--fg-2)' : 'var(--border-2)'}
        strokeWidth={2}
      />,
    );
  }
  return <>{out}</>;
}

/**
 * **Die Abzweigung – sie hängt an einem ZUSTANDSPUNKT, nicht an einem Modul** (#700).
 *
 * Ein Stück kann nur abweichen, solange am Modul noch nichts eingegeben wurde: es hat das
 * Modul also gar nicht betreten. Folglich geht die Linie **vor** dem Modul von der
 * Prozesslinie ab – vom Punkt, an dem das Stück wartete – und führt an **denselben Punkt**
 * zurück, sodass es das Modul danach regulär durchläuft.
 *
 * Weil ein Zustandspunkt nach dem Modul heisst, vor dem er liegt, ist sein Anker direkt
 * berechenbar (`statePointId`) – gesucht oder geraten wird nichts. Kommt das Stück nicht
 * zurück (Aussonderung), gibt es die zweite Linie nicht: das Fehlen **ist** die Aussage.
 *
 * Ein Auftrag kann an **mehreren** Punkten zugegriffen haben – dann gibt es je Punkt ein
 * Linienpaar. Ein einzelner Anker hätte sich für einen entschieden und die anderen
 * verschwiegen.
 */
function Branch({ side: s, anchors }: {
  side: SideFlow; anchors: Record<string, FlowAnchor>;
}) {
  const from = anchors[`${s.prefix}start`];
  const to = anchors[`${s.prefix}end`];
  if (!from || !to) return null;
  const stroke = 'var(--warning)';
  return (
    <>
      {s.points.map((id) => {
        const A = anchors[id];
        if (!A) return null;
        const right = from.cx > A.cx;
        const edge = right ? A.right : A.left;
        const mid = right ? from.left : from.right;
        const back = right ? to.left : to.right;
        return (
          <g key={id}>
            <path
              d={polyPath([[edge, A.cy], [(edge + mid) / 2, A.cy], [(edge + mid) / 2, from.cy], [mid, from.cy]])}
              fill="none" stroke={stroke} strokeWidth={2}
            />
            {s.rel.returns && (
              <path
                d={polyPath([[back, to.cy], [(edge + back) / 2, to.cy], [(edge + back) / 2, A.cy], [edge, A.cy]])}
                fill="none" stroke={stroke} strokeWidth={2} strokeDasharray="5 4"
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
