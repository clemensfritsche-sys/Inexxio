'use client';

import { useMemo, type ReactNode } from 'react';
import { GitBranch, MoreHorizontal } from 'lucide-react';
import { FlowFrame, polyPath, type FlowAnchor } from './process-flow';
import {
  FlowColumn, PROCESS_MAXW, flowNodes, walkedEdges,
  type DiagramGroup, type DiagramStep, type FlowSpec,
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

/**
 * Ab dieser gemessenen Breite passen drei Spuren nebeneinander: die feste Mitte, zwei
 * lesbare Nachbarn und die Abstände dazwischen. Darunter stehen sie untereinander.
 */
const WIDE = PROCESS_MAXW + 2 * 240 + 60;
/** Wie breit ein Nachbar höchstens wird. Schmaler als die Mitte – sie ist der Fokus. */
const SIDE_MAXW = 420;

export function ProcessColumns({ order, renderStep, onExpand, onDeviate, deviateBlocked, journeyIn, journeyOut }: {
  order: Order;
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
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

  const main = useMemo(
    () => flowNodes({
      running: true, steps, groups,
      journeyIn: inStops.length, journeyOut: outStops.length,
    }),
    [steps, groups, inStops.length, outStops.length],
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
          <Branch key={`b-${s.prefix}`} side={s} main={main} anchors={a} />
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
            activeStepId={order.active_step_id ?? null} endStatus={order.end_status}
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
            display: 'grid', alignItems: 'start', gap: 26,
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
}

function side(rel: RelatedOrder, where: 'p' | 'd'): SideFlow {
  const prefix = `${where}${rel.object_id}:`;
  const steps = (rel.steps ?? []).map((s) => ({
    id: s.id, moduleType: s.module_type, label: s.label,
  }));
  const groups = (rel.unit_groups ?? []).map((g) => ({
    currentStepId: g.current_step_id ?? null, status: g.status,
    active: g.active, count: g.count,
  }));
  const nodes = flowNodes({ prefix, running: true, steps, groups });
  return { prefix, where, rel, steps, groups, nodes, walked: walkedEdges(nodes, true) };
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
 * **Die Abzweigung.** Sie geht von der Stelle im eigenen Ablauf zur Spalte daneben und –
 * wenn das Stück zurückkehrt – von deren Ende wieder an dieselbe Stelle.
 *
 * Genau das ist die Frage, die man auf einen Blick beantwortet haben will: *wo ist das
 * Stück ausgeschert, und wo kommt es zurück?* Kommt es nicht zurück (Aussonderung), gibt
 * es die zweite Linie nicht – das Fehlen **ist** die Aussage.
 */
function Branch({ side: s, main, anchors }: {
  side: SideFlow; main: FlowSpec[]; anchors: Record<string, FlowAnchor>;
}) {
  const anchorId = resolveAnchor(s, main);
  const A = anchors[anchorId];
  const from = anchors[`${s.prefix}start`];
  const to = anchors[`${s.prefix}end`];
  if (!A || !from || !to) return null;
  const right = from.cx > A.cx;
  const edge = right ? A.right : A.left;
  const mid = right ? from.left : from.right;
  const back = right ? to.left : to.right;
  const stroke = 'var(--warning)';
  return (
    <>
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
    </>
  );
}

/**
 * Welcher Knoten der Mitte trägt die Abzweigung? Der Zustandsknoten an der Stelle, an der
 * das Stück steht – und wenn es den nicht gibt (alle Stücke sind weg, also zeigt die
 * Mitte dort nichts an), das Modul selbst. Ein Anker, den es nicht gibt, hiesse **keine
 * Linie**, und dann fehlte genau die Auskunft, für die sie da ist.
 */
function resolveAnchor(s: SideFlow, main: FlowSpec[]): string {
  const ids = new Set(main.map((n) => n.id));
  const step = s.where === 'd' ? s.rel.origin_step_id ?? null : null;
  if (step != null) {
    // Das Stück stand **vor** diesem Modul – und der Zustandsknoten davor heisst nach
    // seinem *Vorgänger* (`state-<vorheriges Modul>`) bzw. `state-start` beim ersten.
    // Darum wird die Position gesucht, nicht der Name geraten.
    const at = main.findIndex((n) => n.kind === 'step' && n.step.id === step);
    if (at > 0 && main[at - 1].kind === 'state') return main[at - 1].id;
    if (at >= 0) return main[at].id;
    if (ids.has(`step-${step}`)) return `step-${step}`;
  }
  return s.where === 'p' ? 'start' : 'end';
}

// ─────────────────────────────────────────────────────────────────────────────

function useSteps(steps: NonNullable<Order['steps']>): DiagramStep[] {
  return useMemo(
    () => steps.map((s) => ({ id: s.id, moduleType: s.module_type, label: s.label })),
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
