'use client';

import { useState, type CSSProperties, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, CornerUpLeft, Flag, GitBranch, MoreHorizontal, Play, Scissors, Sprout } from 'lucide-react';
import { TYPE_META } from '@/lib/erp-record';
import { BEND, FLOW_GAP, FlowNode, LANE, POINT, polyPath, port, type FlowAnchor } from './process-flow';
import { UnitNumber } from './unit-number';
import { statusCfg, isPickable, IM_PROZESS, START_AFTER, START_BEFORE, END_BEFORE, statusLabel } from '@/lib/process-status';
import { formatObjectId } from '@/lib/utils';
import { whenTitle } from '@/lib/when';
import { useErpNav } from './obj-id';
import { StatusDot } from './fields';
import type { GraphEdge, GraphUnits, JourneyStop, ProcessEventResponse, ProcessGraph } from '@/types';
import { DiagramMode, DiagramStep, JOURNEY_LIMIT, JourneyOrigin, columnRows, hasJourney, historyTip, journeyId } from '@/lib/process-graph';
import { StepCard } from '@/components/erp/module-card';

/**
 * **Die Prozessdarstellung — EINE Komponente, zwei Modi** (PROCESS_CORE.md §8.1):
 * `definition` (Entwurf, Artikel: Module anlegen, löschen, sortieren) · `ausfuehrung`
 * (freigegebener Auftrag: Zustand, aktuelle Stelle). Die Einzelinstanzen stehen im Slot
 * `head` darüber (ein Artikel hat keine). Start, Modul und Ende teilen sich `FlowNode`.
 */

/**
 * **Der Herkunfts-/Verbleibsbaum — dieselbe Linie, nur verzweigt.** Je Nachbar-Auftrag ein
 * Ast (gruppiert, nicht je Stück), alle auf **einem** Bus in Start bzw. aus dem Ende
 * (§8.1a″). Setzt voraus, dass die Zeile nicht umbricht.
 */
function fanPaths(anchors: Record<string, FlowAnchor>, prefix: string,
                  where: 'in' | 'out', keys: Array<string | number>,
                  outTrunk: string): string[] {
  const at = (id: string) => anchors[`${prefix}${id}`];
  const trunk = where === 'in' ? at('start') : at(outTrunk);
  if (!trunk) return [];
  const bus = where === 'in' ? trunk.top - BEND : trunk.bottom + BEND;
  return keys.flatMap((k) => {
    const c = at(journeyId(where, k));
    if (!c) return [];
    return [where === 'in'
      ? polyPath([[c.cx, c.bottom], [c.cx, bus], [trunk.cx, bus], [trunk.cx, trunk.top]])
      : polyPath([[trunk.cx, trunk.bottom], [trunk.cx, bus], [c.cx, bus], [c.cx, c.top]])];
  });
}

/** Ein Stück, wenn jemand einen Zustandspunkt aufklappt: welches, und seit wann hier (Log). */
interface UnitChip {
  number: string;
  startedAt?: string | null;
  /** **Der Zustand reist mit dem Stück** – aus ihm folgt, ob es noch greifbar ist. */
  status?: string | null;
}

/** **Die Breite gehört zum Prozessbild, nicht zu seinem Aufrufer** – überall gleich. */
export const PROCESS_MAXW = LANE.MID_MAX;

/** **Was in einer Spalte steht** – Entwurf und laufender Auftrag bestücken dieselbe Spalte. */
export interface ColumnProps {
  /** **Das Bild dieser Spalte** – vom Server, nicht hier abgeleitet. */
  graph: ProcessGraph;
  /** Der Inhalt der Module. Der Graph sagt *wo* ein Modul steht, dies *was* darin steht. */
  steps: DiagramStep[];
  /** Kennung dieser Spalte im gemeinsamen Rahmen – sonst kollidieren die Knoten-Ids. */
  prefix?: string;
  mode: DiagramMode;
  activeStepId?: number | null;
  /** Welches Modul startet **aufgeklappt**; sonst sind alle zu. */
  expandedStepId?: number | null;
  endStatus: string;
  head?: ReactNode;
  tail?: ReactNode;
  /** **Die Wiederholung** – die Karte unter dem Ende (Projektakte Wiederkehr §8). */
  loop?: ReactNode;
  onDelete?: (id: number) => void;
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  onExpand?: (edgeId: string) => Promise<UnitChip[]>;
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /**
   * **Kontext statt Fokus** – ein fremder Auftrag daneben tritt nur **tonal** zurück
   * (keine Fläche, keine Trennlinie: die Querlinien liefen hindurch). Die Linie dorthin bleibt voll.
   */
  faded?: boolean;
  /** **Abweichung an genau diesem Stück** (Abweichungsauftrag §3.1): der Auslöser sitzt
   *  dort, wo das Stück gerade im Prozess steht – nicht in einem Menü darüber. */
  onDeviate?: (unitNumber: string) => void;
  /** Warum der Auslöser gerade gesperrt ist. Gesetzt = gesperrt, mit Grund im Hover. */
  deviateBlocked?: string;
  /** **Die Spalte in ein fremdes Raster stellen** (`display: contents`): die Knoten werden
   *  Kinder des äusseren Rasters mit drei Spuren. */
  containerStyle?: CSSProperties;
  /** Je Zeile ihr Platz im äusseren Raster. Ohne Raster leer – dann trägt der Fluss. */
  rowStyle?: (index: number) => CSSProperties;
  /** **Hier entstandene** Stücke – die eine Herkunft, die nicht im Log steht. */
  origins?: JourneyOrigin[];
  /** Der Ereignis-Log – **am Objekt**, an dem er passiert ist (§5). */
  events?: ProcessEventResponse[];
  eventTotal?: number;
  /** Nur im Entwurf: die geplanten Rückführungen – der Schalter am Anfang ihrer Linie. */
  returns?: ReturnTarget[];
  onToggleReturn?: (parentObjectId: number) => void;
}

/** **Eine geplante Rückführung** – ein Quell-Auftrag und ob es zu ihm zurückgeht. */
interface ReturnTarget {
  objectId: number;
  on: boolean;
}

/**
 * **Eine Spalte des Bildes** – nur Knoten, keine eigenen Linien: so stehen mehrere Spalten
 * in **einem** Rahmen und die Linien kommen aus denselben gemessenen Ankern.
 */
export function FlowColumn({
  graph, steps, prefix = '', mode, activeStepId = null, expandedStepId = null, endStatus,
  head, tail, loop, onDelete,
  renderStep, onExpand, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [], faded = false, onDeviate, deviateBlocked,
  containerStyle, rowStyle, origins = [],
  events = [], eventTotal, returns = [], onToggleReturn,
}: ColumnProps) {
  const running = mode === 'ausfuehrung';
  // **Eingeklappt, ausser das Modul ist dran**: läuft er, das aktive; im Entwurf das zuletzt angelegte.
  const openId = running ? activeStepId : expandedStepId;
  // Dieselben Zeilen wie im Raster daneben (`columnRows`) – sonst sässe alles darunter daneben.
  const rows = columnRows(graph, {
    head: !!head, tail: !!tail, loop: !!loop,
    journeyIn: hasJourney(journeyIn, origins), journeyOut: journeyOut.length > 0,
    returns: returns.length > 0,
  });
  const byId = new Map(steps.map((s) => [s.id, s]));
  const place = (i: number, extra?: CSSProperties): CSSProperties => ({
    ...extra, ...rowStyle?.(i),
  });
  return (
    <div style={{
      // **Derselbe Takt wie im Raster** (`FLOW_GAP`), damit Querlinien lesbar getrennt bleiben.
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: FLOW_GAP,
      opacity: faded ? 0.55 : 1,
      filter: faded ? 'saturate(0.15)' : undefined,
      ...containerStyle,
    }}>
      {rows.map((row, i) => {
        if ('slot' in row) {
          const body = row.slot === 'head' ? head
            : row.slot === 'tail' ? tail
              : row.slot === 'loop' ? loop
              : row.slot === 'return'
                ? <ReturnRow targets={returns} onToggle={onToggleReturn} />
                : <JourneyRow
                  where={row.slot === 'journey-in' ? 'in' : 'out'}
                  stops={(row.slot === 'journey-in' ? journeyIn : journeyOut)
                    .slice(0, JOURNEY_LIMIT)}
                  origins={row.slot === 'journey-in' ? origins : []}
                  rest={Math.max(0, (row.slot === 'journey-in' ? journeyIn : journeyOut).length
                    - JOURNEY_LIMIT)}
                  prefix={prefix} />;
          return (
            <FlowNode key={row.key} id={`${prefix}${row.key}`}
              style={place(i, { width: '100%' })}>{body}</FlowNode>
          );
        }
        // **Eine Kante trägt ihre Stücke** – die Pille sitzt auf der Linie.
        if ('edge' in row) {
          return (
            <FlowNode key={row.key} id={`${prefix}${row.key}`} style={place(i, { width: '100%' })}>
              <StateRow
                units={row.edge.units ?? []}
                edgeId={row.edge.id}
                away={row.edge.kind === 'out'}
                onExpand={onExpand}
                onDeviate={onDeviate}
                deviateBlocked={deviateBlocked}
              />
            </FlowNode>
          );
        }
        const n = row.node;
        const id = `${prefix}${n.id}`;
        if (n.kind === 'start' || n.kind === 'end') {
          return (
            <FlowNode key={row.key} id={id} style={place(i)}>
              <Terminal which={n.kind} endStatus={endStatus}
                history={historyTip(events, n, eventTotal)} />
            </FlowNode>
          );
        }
        if (n.kind === 'fork' || n.kind === 'join') {
          return (
            <FlowNode key={row.key} id={id} style={place(i)}>
              <Point kind={n.kind} />
            </FlowNode>
          );
        }
        const step = n.at !== null && n.at !== undefined ? byId.get(n.at) : undefined;
        if (!step) return null;
        const isActive = running && step.id === activeStepId;
        const index = steps.indexOf(step);
        return (
          <FlowNode key={row.key} id={id} style={place(i, { width: '100%' })}>
            <StepCard
              step={step}
              active={isActive}
              // Gedämpft nur, wo nichts mehr zu tun ist.
              dimmed={running && !isActive && !step.openActions}
              history={historyTip(events, n, eventTotal)}
              defaultOpen={step.id === openId}
              onDelete={mode === 'definition' && onDelete ? () => onDelete(step.id) : undefined}
              drag={onReorder && mode === 'definition' ? {
                index,
                over: dragging !== null && dragging !== index,
                onStart: () => onDragState?.(index),
                onEnd: () => onDragState?.(null),
                onDrop: (from) => { onReorder(from, index); onDragState?.(null); },
              } : undefined}
            >
              {renderStep?.(step, isActive)}
            </StepCard>
          </FlowNode>
        );
      })}
      {(graph.problems ?? []).length > 0 && <Problems list={graph.problems ?? []} />}
    </div>
  );
}

/** **Abzweige- und Rückführpunkt** – ein Punkt auf der Linie, sonst nichts. */
function Point({ kind }: { kind: string }) {
  return (
    <span
      style={{
        display: 'block', width: POINT, height: POINT, borderRadius: 999,
        border: '2px solid var(--fg-2)', background: 'var(--bg-1)',
      }}
      data-tip={kind === 'fork' ? 'Hier ist ein Stück ausgeschert'
        : 'Hierher kehrt ein Stück zurück'}
    />
  );
}

/**
 * **Der Schalter sitzt am ANFANG der Rückführungslinie** – eine Pille unter dem Ende, von
 * der die Linie abgeht (§8.1a″). Er bleibt, wenn sie geht: die Entscheidung ist änderbar.
 * Die Linie ist die Antwort – ist sie da, geht es zurück.
 */
function ReturnRow({ targets, onToggle }: {
  targets: ReturnTarget[]; onToggle?: (objectId: number) => void;
}) {
  return (
    <div className="w-full flex flex-wrap items-center justify-center gap-1.5">
      {targets.map((t) => (
        <button
          key={t.objectId}
          type="button"
          disabled={!onToggle}
          onClick={() => onToggle?.(t.objectId)}
          className="inline-flex items-center gap-1.5 rounded-full text-xs"
          // Kein Strichmuster: es läse sich als dritte Linienart (§8.1a).
          style={{
            minHeight: 36, padding: '7px 12px',
            border: `1px solid var(${t.on ? '--border-2' : '--border-1'})`,
            background: t.on ? 'var(--bg-1)' : 'transparent',
            color: t.on ? 'var(--fg-2)' : 'var(--fg-4)',
            cursor: onToggle ? 'pointer' : 'default',
          }}
          data-tip={t.on
            ? `Nach dem Durchlauf geht jedes Stück an genau die Stelle in Auftrag `
              + `${formatObjectId(t.objectId)} zurück, an der es ausgeschert ist. `
              + `Klicken kappt die Rückführung.`
            : `Die Stücke bleiben hier; Auftrag ${formatObjectId(t.objectId)} läuft mit `
              + `weniger weiter. Klicken führt sie wieder zurück.`}
        >
          {t.on ? <CornerUpLeft size={13} /> : <Scissors size={13} />}
          {t.on ? 'kehrt zurück' : 'bleibt hier'}
          {targets.length > 1 && (
            <span className="ix-tnum" style={{ color: 'var(--fg-4)' }}>
              {formatObjectId(t.objectId)}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/** **Sichtbar kaputt statt still falsch** – verletzt der Graph eine Invariante, steht es hier. */
function Problems({ list }: { list: string[] }) {
  return (
    <div className="w-full rounded-ds-lg text-[12px]"
      style={{ border: '1px solid var(--danger)', background: 'var(--danger-bg)',
               color: 'var(--danger)', padding: '8px 11px' }}>
      <strong>Das Bild ist nicht verlässlich.</strong>
      <ul className="mt-1 list-disc pl-4">
        {list.map((p) => <li key={p}>{p}</li>)}
      </ul>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Linien — berechnet aus gemessenen Ankern, nirgends eingetragen
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Die Achse einer Spalte** – je Kante ein Zug, senkrecht heraus und hinein (§8.1a). Ob sie
 * kräftig ist (`walked`), leitet der Server aus dem Log ab.
 */
export function Axis({ edges, anchors, prefix = '', journeyIn = [], journeyOut = [] }: {
  edges: GraphEdge[]; anchors: Record<string, FlowAnchor>; prefix?: string;
  /** Die Äste des Herkunfts-/Verbleibsbaums – Schlüssel, keine Geometrie. */
  journeyIn?: Array<string | number>;
  journeyOut?: Array<string | number>;
}) {
  // **Wo die Achse endet, hängt der Verbleibs-Baum** – an der Kante ohne nächsten Knoten.
  const exit = edges.find((e) => e.to == null);
  const outTrunk = exit && anchors[`${prefix}on:${exit.id}`] ? `on:${exit.id}`
    : (exit?.frm ?? 'end');
  return (
    <>
      {fanPaths(anchors, prefix, 'in', journeyIn, outTrunk).map((d, i) => (
        // Gegangen: die Journey kennt nur, was im Log steht.
        <Stroke key={`fan-in-${i}`} d={d} walked />
      ))}
      {fanPaths(anchors, prefix, 'out', journeyOut, outTrunk).map((d, i) => (
        <Stroke key={`fan-out-${i}`} d={d} walked />
      ))}
      {edges.map((e) => {
        const A = anchors[`${prefix}${e.frm}`];
        // Ohne nächsten Knoten führt die Kante zur Zeile ihrer Stücke (`on:<Kante>`).
        const B = anchors[`${prefix}${e.to ?? `on:${e.id}`}`];
        if (!A || !B) return null;
        return (
          <Stroke key={e.id}
            d={polyPath([port(A, 'bottom'), port(B, 'top')])} walked={e.walked} />
        );
      })}
    </>
  );
}

/** **Zwei Stärken, sonst nichts** (§8.1a): gegangen kräftig, ausstehend Haarlinie – jede Linie geht hier durch. */
export function Stroke({ d, walked }: { d: string; walked: boolean }) {
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

// ─────────────────────────────────────────────────────────────────────────────
// Knoten
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Die Journey** – über dem Start die Aufträge davor, unter dem Ende die danach;
 * gruppiert («wie viele woher»), nicht je Stück. Ohne Nachbarn entsteht die Zeile nicht.
 */
function JourneyRow({ where, stops, origins, prefix, rest }: {
  where: 'in' | 'out';
  stops: JourneyStop[];
  /** Nur oben: die **hier entstandenen** Stücke – sie haben keinen Vorgänger. */
  origins: JourneyOrigin[];
  prefix: string;
  /** Wie viele Nachbarn nicht gezeigt werden. Gekappt, aber nicht verschwiegen. */
  rest: number;
}) {
  // Der Sprung zum Nachbarn über dieselbe Navigation wie jede Objektnummer.
  const nav = useErpNav();
  // **Der Rest ist kein Ast**: «… N» auf eigener Zeile, weg vom Stamm – sonst verschöbe er die Reihe.
  const note = rest > 0 && (
    <span className="inline-flex items-center gap-1 text-[11px]"
      style={{ color: 'var(--fg-4)', whiteSpace: 'nowrap' }}
      data-tip="Weitere Nachbarn – sie stehen im jeweiligen Auftrag">
      <MoreHorizontal size={12} /> {rest}
    </span>
  );
  return (
    <div className="flex flex-col items-center" style={{ gap: 4 }}>
    {where === 'in' && note}
    <div className="flex items-start justify-center gap-1.5" style={{ flexWrap: 'nowrap' }}>
      {origins.map((o, i) => (
        <FlowNode key={`new-${i}`} id={`${prefix}${journeyId(where, `new:${i}`)}`}>
          <span
            className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)',
                     color: 'var(--fg-3)', whiteSpace: 'nowrap' }}
            data-tip={`${o.count}× ${o.label} entstehen in diesem Auftrag – kein Vorgänger`}
          >
            <Sprout size={11} style={{ color: 'var(--fg-4)' }} />
            <span className="ix-tnum">{o.count}×</span>
            <span className="truncate" style={{ maxWidth: 120 }}>{o.label}</span>
          </span>
        </FlowNode>
      ))}
      {stops.map((j) => (
        <FlowNode key={j.object_id} id={`${prefix}${journeyId(where, j.object_id)}`}>
          <button
            type="button"
            onClick={nav ? () => nav(j.object_id) : undefined}
            disabled={!nav}
            className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)',
                     color: 'var(--fg-3)', whiteSpace: 'nowrap' }}
            data-tip={`${j.name} · ${j.unit_count} Stück – öffnen`}
          >
            <span className="ix-tnum">{formatObjectId(j.object_id)}</span>
            <span style={{ color: 'var(--fg-4)' }}>· {j.unit_count}</span>
          </button>
        </FlowNode>
      ))}
    </div>
    {where === 'out' && note}
    </div>
  );
}

function Terminal({ which, endStatus, history }: {
  which: 'start' | 'end'; endStatus: string;
  /** Was hier passiert ist – dieselbe Blase wie am Modul (§5). */
  history?: string;
}) {
  const Icon = which === 'start' ? Play : Flag;
  const after = which === 'start' ? START_AFTER : endStatus;
  const before = which === 'start' ? START_BEFORE : END_BEFORE;
  const cfg = statusCfg(after);
  const head = `${which === 'start' ? 'Start' : 'Ende'}: ${statusLabel(before)} → ${statusLabel(after)}`;
  return (
    <div
      className="flex items-center justify-center rounded-full"
      // Fokussierbar, damit die Blase auch ohne Hover erscheint (Tipp, Tab).
      tabIndex={history ? 0 : undefined}
      style={{ width: 46, height: 46, border: `2px solid ${cfg.color}`, background: cfg.bg, color: cfg.color }}
      data-tip={history ? `${head}\n${history}` : head}
      data-tip-list={history ? '' : undefined}
    >
      <Icon size={19} />
    </div>
  );
}

/** Was steht hier gerade? **Eine Pille je Zustand, mit Anzahl**; die Nummern erst beim Aufklappen. */
function StateRow({ units, edgeId, away: outward = false, onExpand, onDeviate,
  deviateBlocked }: {
  /** Was auf dieser Kante steht – vom Server gezählt, hier nur gezeigt. */
  units: GraphUnits[];
  /** **Die Position** – Zähler und Aufklappen fragen dieselbe. */
  edgeId: string;
  /** Führt die Kante **hinaus** in einen anderen Auftrag? Nur dann sind es ausgescherte Stücke. */
  away?: boolean;
  onExpand?: (edgeId: string) => Promise<UnitChip[]>;
  onDeviate?: (unitNumber: string) => void;
  deviateBlocked?: string;
}) {
  const [open, setOpen] = useState(false);
  const [numbers, setNumbers] = useState<UnitChip[] | null>(null);
  const [busy, setBusy] = useState(false);
  const groups = outward ? [] : units;
  /**
   * **Die Linie sagt die Vergangenheit, die Pille die Gegenwart** – aus dem Status:
   * `im_prozess` = arbeitet gerade woanders, sonst = dort geblieben.
   */
  const away = outward ? units.filter((u) => u.status === IM_PROZESS) : [];
  const handed = outward ? units.filter((u) => u.status !== IM_PROZESS) : [];
  const total = groups.reduce((n, g) => n + g.count, 0);
  const gone = away.reduce((n, g) => n + g.count, 0);
  const left = handed.reduce((n, g) => n + g.count, 0);
  async function toggle() {
    if (!onExpand) return;
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (numbers === null) {
      setBusy(true);
      try { setNumbers(await onExpand(edgeId)); } finally { setBusy(false); }
    }
  }

  if (!total && !gone && !left) return null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="flex flex-wrap gap-1.5 justify-center">
        {gone > 0 && (
          // Ausgeschert und noch dort – es fehlt nicht und ist nicht fertig.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--warning-bg)', color: 'var(--warning)',
                     border: '1px dashed var(--warning)' }}
            data-tip="In einem Abweichungsauftrag – es steht weiterhin an dieser Stelle"
          >
            <GitBranch size={11} /> In Abweichung · {gone}
          </span>
        )}
        {left > 0 && (
          // Ausgeschert und dort geblieben – die Abzweigung bleibt im Bild.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--bg-3)', color: 'var(--fg-3)',
                     border: '1px dashed var(--border-2)' }}
            data-tip="Hier ausgeschert und dort geblieben – die Rückführung war gekappt"
          >
            <GitBranch size={11} /> Abgegeben · {left}
          </span>
        )}
        {groups.map((g) => {
          const cfg = statusCfg(g.status);
          const active = g.active;
          return (
            <button
              key={`${g.status}-${g.active}`}
              type="button"
              onClick={toggle}
              disabled={!onExpand}
              // Hier stehen sie jetzt: der leise Ring in der Farbe der Pille.
              className={`inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum${active ? ' ix-live' : ''}`}
              style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}22`,
                       ['--ix-live' as string]: `${cfg.color}55` }}
              data-tip={onExpand ? 'Nummern anzeigen' : cfg.label}
            >
              <StatusDot color={cfg.color} />
              {cfg.label} · {g.count}
              {onExpand && (open
                ? <ChevronUp size={11} style={{ opacity: 0.6 }} />
                : <ChevronDown size={11} style={{ opacity: 0.6 }} />)}
            </button>
          );
        })}
      </div>
      {open && (
        <div className="flex flex-wrap gap-1 justify-center max-w-full">
          {busy && <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>Lädt …</span>}
          {numbers?.map((u) => (
            <span key={u.number} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-3)' }}
              // Seit wann läuft dieses Stück hier? Aus dem Log.
              data-tip={u.startedAt ? `Start passiert: ${whenTitle(u.startedAt)}` : undefined}>
              <UnitNumber value={u.number} size={11} />
              {onDeviate && isPickable(u.status) && (
                // **Der Auslöser sitzt am Stück** (§3.1): öffnet einen gewöhnlichen
                // Auftragsentwurf mit diesem Stück; nur, wo es greifbar ist (`isPickable`).
                <button
                  type="button"
                  onClick={() => onDeviate(u.number)}
                  disabled={!!deviateBlocked}
                  className="flex items-center disabled:opacity-40"
                  style={{ color: 'var(--warning)' }}
                  aria-label={`Auftrag auf ${u.number}`}
                  data-tip={deviateBlocked ?? 'Auftrag auf genau dieses Stück'}
                >
                  <TYPE_META.order.icon size={11} />
                </button>
              )}
            </span>
          ))}
          {numbers && numbers.length < total && (
            // Gekappt, aber nicht verschwiegen.
            <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
              … {numbers.length} von {total}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
