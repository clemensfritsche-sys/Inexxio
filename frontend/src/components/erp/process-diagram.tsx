'use client';

import { useMemo, useState, type ReactNode } from 'react';
import {
  Blocks, ChevronDown, ChevronUp, CornerDownRight, CornerRightDown, Flag, GitBranch,
  GripVertical, Play, Trash2,
} from 'lucide-react';
import { MODULE_ICON, moduleTone } from '@/lib/modules';
import { FlowFrame, FlowNode, polyPath, type FlowAnchor } from './process-flow';
import { UnitNumber } from './unit-number';
import { statusCfg, START_AFTER, START_BEFORE, END_BEFORE, statusLabel } from '@/lib/process-status';
import { formatObjectId } from '@/lib/utils';
import { useErpNav } from './obj-id';
import type { JourneyStop } from '@/types';

/**
 * **Die Prozessdarstellung — EINE Komponente, zwei Modi.**
 *
 * | Modus | Wo | Was |
 * |---|---|---|
 * | `definition` | Auftragsentwurf und Artikel-Spezifikation | Module anlegen, löschen, sortieren |
 * | `ausfuehrung` | freigegebener Auftrag | Zustand je Objekt, aktuelle Stelle, Ausführung |
 *
 * Zweimal zu bauen wäre an dieser Stelle der teuerste Fehler (PROCESS_CORE.md §8.1) —
 * darum ist der Modus ein Schalter und kein zweites Bauteil. Beide Modi werden **schon
 * im Auftrag** gebraucht (Entwurf ↔ freigegeben); der Artikel benutzt nur den ersten
 * und ist damit kein neuer Fall.
 *
 * Die **Definition der Einzelinstanzen** ist bewusst **nicht** Teil dieses Diagramms,
 * sondern ein Slot darüber (`head`): ein Artikel hat keine Einzelinstanzen, und ein
 * Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar.
 *
 * **Ein Prozessobjekt = eine Komponente.** Start, Modul und Ende teilen sich `FlowNode`;
 * der Modultyp ist Konfiguration, nicht ein eigenes Bauteil.
 */

export interface DiagramStep {
  /**
   * **Die Identität des Moduls** (Testnotiz #687). Serverseitig vergeben und
   * unveränderlich; im Entwurf eine lokale Nummer, weil es den Datensatz noch nicht gibt.
   * Der Ereignis-Log zeigt auf sie – nie auf einen Namen, nie auf die Position.
   */
  id: number;
  moduleType: string;
  /** Wie das Modul heisst – **aus seinem Typ abgeleitet**, nicht eingegeben (#682). */
  label: string;
}

export type DiagramMode = 'definition' | 'ausfuehrung';

/**
 * **Die Breite gehört zum Prozessbild, nicht zu seinem Aufrufer** (Testnotiz #684).
 *
 * Es war schon EINE Komponente – aber der Artikel stellte sie in einen 880-px-Container
 * und der Auftrag in einen 620er, und damit sahen dieselben Module verschieden breit
 * aus. Eine visuelle Abweichung ist der Beweis, dass irgendwo zwei Stände sind; hier war
 * es nicht die Komponente, sondern das Mass. Also bringt sie es selbst mit: der Prozess
 * sieht überall gleich aus, weil ihn niemand mehr messen kann.
 */
export const PROCESS_MAXW = 620;

/**
 * Wie viele Stücke stehen an einer Stelle, in welchem Zustand.
 *
 * **Gezählt, nicht aufgelistet.** Die Datenhaltung bleibt pro Einzelinstanz (§4 des
 * Auftrags); dies ist die Darstellungsfrage. Bei Menge 5000 ist der Unterschied nicht
 * Geschmack, sondern der zwischen einer Pille und 5000 DOM-Knoten. Wer die Nummern
 * sehen will, klappt auf – dann holt `onExpand` sie nach.
 */
export interface DiagramGroup {
  /** `null` = am Ende angekommen. Nur im Ausführungsmodus gesetzt. */
  currentStepId: number | null;
  status: string;
  active: boolean;
  count: number;
}

/** Ein Knoten im Bild. Die Liste entsteht in ``flowNodes`` – **einmal**, für jede Spalte. */
export type FlowSpec =
  | { id: string; kind: 'head' }
  | { id: string; kind: 'tail' }
  | { id: string; kind: 'terminal'; which: 'start' | 'end' }
  | { id: string; kind: 'state'; at: number | null }
  | { id: string; kind: 'step'; step: DiagramStep; index: number }
  | { id: string; kind: 'journey'; where: 'in' | 'out' };

/**
 * Die Knotenfolge — **eine reine Funktion**, damit sie nicht nur die Komponente selbst
 * kennt. Ein Bild aus mehreren Spalten (übergeordneter Auftrag · eigener Ablauf ·
 * Abweichungen) braucht sie je Spalte, und die Linien dazwischen brauchen die Ids.
 *
 * Die **Zustandsanzeige zwischen zwei Modulen ist abgeleitet**: nach Modul *i* steht per
 * Statusregel genau dessen `Nachher` (§4). Das Bild zeigt damit die Regel, statt sie zu
 * wiederholen. Unterhalb der aktuellen Stelle entsteht **kein** Zustandsknoten — dort
 * war noch kein Material (§7.3), und eine leere Anzeige wäre eine Fallback-Anzeige.
 */
export function flowNodes({
  prefix = '', running, steps, groups, hasHead, hasTail, journeyIn = 0, journeyOut = 0,
}: {
  prefix?: string;
  running: boolean;
  steps: DiagramStep[];
  groups: DiagramGroup[];
  hasHead?: boolean;
  hasTail?: boolean;
  journeyIn?: number;
  journeyOut?: number;
}): FlowSpec[] {
  const p = (id: string) => `${prefix}${id}`;
  const out: FlowSpec[] = [];
  if (hasHead) out.push({ id: p('head'), kind: 'head' });
  if (journeyIn) out.push({ id: p('journey-in'), kind: 'journey', where: 'in' });
  out.push({ id: p('start'), kind: 'terminal', which: 'start' });
  if (running && groupsAt(groups, steps[0]?.id ?? null, true).length) {
    out.push({ id: p('state-start'), kind: 'state', at: steps[0]?.id ?? null });
  }
  steps.forEach((s, i) => {
    out.push({ id: p(`step-${s.id}`), kind: 'step', step: s, index: i });
    const next = steps[i + 1]?.id ?? null;
    if (running && next !== null && groupsAt(groups, next, true).length) {
      out.push({ id: p(`state-${s.id}`), kind: 'state', at: next });
    }
  });
  if (hasTail) out.push({ id: p('tail'), kind: 'tail' });
  out.push({ id: p('end'), kind: 'terminal', which: 'end' });
  if (running && groups.some((g) => !g.active && g.currentStepId === null)) {
    out.push({ id: p('state-end'), kind: 'state', at: null });
  }
  if (journeyOut) out.push({ id: p('journey-out'), kind: 'journey', where: 'out' });
  return out;
}

/** Bis wohin ist die Linie stark? Bis zu der Stelle, an der der Prozess wirklich steht. */
export function walkedEdges(nodes: FlowSpec[], running: boolean): number {
  if (!running) return 0;
  let last = -1;
  nodes.forEach((n, i) => { if (n.kind === 'state') last = i; });
  return Math.max(0, last);
}

export function ProcessDiagram({
  mode, steps, groups = [], activeStepId = null, endStatus,
  head, tail, onDelete, renderStep, onExpand, tone, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [],
}: {
  mode: DiagramMode;
  steps: DiagramStep[];
  /** Nur im Ausführungsmodus – im Definitionsmodus gibt es nichts unterwegs (§6.1). */
  groups?: DiagramGroup[];
  activeStepId?: number | null;
  endStatus: string;
  /** Slot über dem Start: die Definition (nur beim Auftrag). */
  head?: ReactNode;
  /** **Journey**: woher die Stücke kamen (über dem Start) und wohin sie gingen (unter
   *  dem Ende). Leer heisst «keiner» – dann steht dort nichts. */
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /** Slot **vor dem Ende**: die Modulauswahl – genau dort, wo das nächste Modul hinkäme. */
  tail?: ReactNode;
  /** Nur im Definitionsmodus: ein Modul entfernen. */
  onDelete?: (id: number) => void;
  /** Was in der Karte steht: im Entwurf die Felder des Moduls, zur Laufzeit seine Arbeit. */
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  /** Eine Gruppe aufklappen: die einzelnen Nummern nachladen. */
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
  /** Farbfamilie je Modultyp. Ohne sie der neutrale Grundton – nie eine leere Fläche. */
  tone?: (moduleType: string) => { bg: string; fg: string; border: string };
  /** Nur im Definitionsmodus: Reihenfolge per Drag & Drop. Sie IST der Prozess. */
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
}) {
  const running = mode === 'ausfuehrung';
  const nodes = useMemo(
    () => flowNodes({
      running, steps, groups,
      hasHead: !!head, hasTail: !!tail,
      journeyIn: journeyIn.length, journeyOut: journeyOut.length,
    }),
    [head, tail, steps, groups, running, journeyIn.length, journeyOut.length],
  );
  const walked = useMemo(() => walkedEdges(nodes, running), [nodes, running]);

  return (
    <div className="mx-auto w-full" style={{ maxWidth: PROCESS_MAXW }}>
      <FlowFrame lines={(a) => <Lines ids={nodes.map((n) => n.id)} anchors={a} walked={walked} />}>
        {() => (
          <FlowColumn
            nodes={nodes} mode={mode} groups={groups} activeStepId={activeStepId}
            endStatus={endStatus} head={head} tail={tail} onDelete={onDelete}
            renderStep={renderStep} onExpand={onExpand} tone={tone} onReorder={onReorder}
            dragging={dragging} onDragState={onDragState}
            journeyIn={journeyIn} journeyOut={journeyOut}
          />
        )}
      </FlowFrame>
    </div>
  );
}

/**
 * **Eine Spalte des Bildes.** Sie zeichnet ihre Knoten in den Rahmen, in dem sie steht –
 * eigene Linien hat sie nicht. Genau dadurch lassen sich mehrere Spalten in **einem**
 * Rahmen zeigen (übergeordneter Auftrag · eigener Ablauf · Abweichungen) und die Linien
 * dazwischen aus denselben gemessenen Ankern berechnen.
 */
export function FlowColumn({
  nodes, mode, groups = [], activeStepId = null, endStatus, head, tail, onDelete,
  renderStep, onExpand, tone, onReorder, dragging, onDragState,
  journeyIn = [], journeyOut = [], faded = false, onDeviate, deviateBlocked,
}: {
  nodes: FlowSpec[];
  mode: DiagramMode;
  groups?: DiagramGroup[];
  activeStepId?: number | null;
  endStatus: string;
  head?: ReactNode;
  tail?: ReactNode;
  onDelete?: (id: number) => void;
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
  tone?: (moduleType: string) => { bg: string; fg: string; border: string };
  onReorder?: (from: number, to: number) => void;
  dragging?: number | null;
  onDragState?: (index: number | null) => void;
  journeyIn?: JourneyStop[];
  journeyOut?: JourneyStop[];
  /** Ein **fremder** Auftrag daneben: vollständig sichtbar, aber nicht der Fokus. */
  faded?: boolean;
  /** **Abweichung an genau diesem Stück** (Abweichungsauftrag §3.1): der Auslöser sitzt
   *  dort, wo das Stück gerade im Prozess steht – nicht in einem Menü darüber. */
  onDeviate?: (unitNumber: string) => void;
  /** Warum der Auslöser gerade gesperrt ist. Gesetzt = gesperrt, mit Grund im Hover. */
  deviateBlocked?: string;
}) {
  const running = mode === 'ausfuehrung';
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
      opacity: faded ? 0.5 : 1,
    }}>
      {nodes.map((n) => {
        if (n.kind === 'head') {
          return <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>{head}</FlowNode>;
        }
        if (n.kind === 'tail') {
          return <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>{tail}</FlowNode>;
        }
        if (n.kind === 'journey') {
          return (
            <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>
              <JourneyRow where={n.where} stops={n.where === 'in' ? journeyIn : journeyOut} />
            </FlowNode>
          );
        }
        if (n.kind === 'terminal') {
          return (
            <FlowNode key={n.id} id={n.id}>
              <Terminal which={n.which} endStatus={endStatus} />
            </FlowNode>
          );
        }
        if (n.kind === 'state') {
          const active = n.at !== null;
          return (
            <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>
              <StateRow
                groups={groupsAt(groups, n.at, active)}
                away={n.at !== null ? groupsAway(groups, n.at) : []}
                stepId={n.at}
                active={active}
                onExpand={onExpand}
                onDeviate={active ? onDeviate : undefined}
                deviateBlocked={deviateBlocked}
              />
            </FlowNode>
          );
        }
        const isActive = running && n.step.id === activeStepId;
        const index = n.index;
        return (
          <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>
            <StepCard
              step={n.step}
              active={isActive}
              dimmed={running && !isActive}
              tone={tone?.(n.step.moduleType)}
              onDelete={mode === 'definition' && onDelete ? () => onDelete(n.step.id) : undefined}
              drag={onReorder && mode === 'definition' ? {
                index,
                over: dragging !== null && dragging !== index,
                onStart: () => onDragState?.(index),
                onEnd: () => onDragState?.(null),
                onDrop: (from) => { onReorder(from, index); onDragState?.(null); },
              } : undefined}
            >
              {renderStep?.(n.step, isActive)}
            </StepCard>
          </FlowNode>
        );
      })}
    </div>
  );
}

function groupsAt(groups: DiagramGroup[], stepId: number | null, active: boolean): DiagramGroup[] {
  return groups.filter((g) => g.active === active && g.currentStepId === stepId);
}

/**
 * **Ausgescherte Stücke** – sie stehen an dieser Stelle, sind aber gerade in einem
 * anderen Auftrag. Erkennbar an genau der Kombination, die ``OrderUnit`` beschreibt:
 * Zugehörigkeit geschlossen (``!active``), Position aber noch gesetzt.
 */
function groupsAway(groups: DiagramGroup[], stepId: number): DiagramGroup[] {
  return groups.filter((g) => !g.active && g.currentStepId === stepId);
}

// ─────────────────────────────────────────────────────────────────────────────
// Linien — berechnet aus gemessenen Ankern, nirgends eingetragen
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
        // Stabile Identität je Kante — Voraussetzung dafür, dass hier später eine
        // Animation andocken kann (stroke-dashoffset, getPointAtLength).
        d={polyPath([[A.cx, A.bottom], [B.cx, B.top]])}
        fill="none"
        stroke={i < walked ? 'var(--fg-2)' : 'var(--border-2)'}
        strokeWidth={2}
      />,
    );
  }
  return <>{out}</>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Knoten
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **Die Journey** – woher die Stücke dieses Auftrags kamen, wohin sie gingen.
 *
 * Ein Stück ist immer in genau einem Auftrag aktiv; alles ist ein einziger Prozess, nur
 * in Aufträge aufgeteilt. Diese Zeile setzt die Teilung wieder zusammen: über dem Start
 * der Auftrag davor, unter dem Ende der danach.
 *
 * **Gruppiert, nicht aufgezählt.** Bei 5000 Stück wären 5000 Verweise weder darstellbar
 * noch lesbar – und die Frage lautet «wie viele kamen woher», nicht «welche». Wer die
 * einzelnen Stücke sehen will, öffnet den genannten Auftrag; dort stehen sie.
 *
 * Gibt es keinen Nachbarn, steht hier **nichts**: der Knoten entsteht gar nicht erst.
 * Ein Platzhalter «kein Vorgänger» wäre eine Zeile, die nichts sagt.
 */
function JourneyRow({ where, stops }: { where: 'in' | 'out'; stops: JourneyStop[] }) {
  // Der Sprung zum Nachbarn läuft über die **bestehende** Navigation (`ErpNavContext`) –
  // dieselbe, mit der jede Objektnummer im ERP ihren Datensatz öffnet. Ein eigener
  // Handler wäre ein zweiter Weg zur selben Sache.
  const nav = useErpNav();
  const Icon = where === 'in' ? CornerDownRight : CornerRightDown;
  return (
    <div className="flex flex-wrap items-center justify-center gap-1.5">
      <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: 'var(--fg-4)' }}>
        <Icon size={12} />
        {where === 'in' ? 'aus' : 'weiter nach'}
      </span>
      {stops.map((j) => (
        <button
          key={j.object_id}
          type="button"
          onClick={nav ? () => nav(j.object_id) : undefined}
          disabled={!nav}
          className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
          style={{ background: 'var(--bg-2)', border: '1px solid var(--border-1)', color: 'var(--fg-3)' }}
          data-tip={`${j.name} – ${j.unit_count} Stück`}
        >
          <span className="ix-tnum">{formatObjectId(j.object_id)}</span>
          <span style={{ color: 'var(--fg-4)' }}>· {j.unit_count}</span>
        </button>
      ))}
    </div>
  );
}

function Terminal({ which, endStatus }: { which: 'start' | 'end'; endStatus: string }) {
  const Icon = which === 'start' ? Play : Flag;
  const after = which === 'start' ? START_AFTER : endStatus;
  const before = which === 'start' ? START_BEFORE : END_BEFORE;
  const cfg = statusCfg(after);
  return (
    <div
      className="flex items-center justify-center rounded-full"
      style={{ width: 46, height: 46, border: `2px solid ${cfg.color}`, background: cfg.bg, color: cfg.color }}
      data-tip={`${which === 'start' ? 'Start' : 'Ende'}: ${statusLabel(before)} → ${statusLabel(after)}`}
    >
      <Icon size={19} />
    </div>
  );
}

/**
 * Was steht hier gerade? **Eine Pille je Zustand, mit Anzahl** – nicht eine je Stück.
 *
 * Bei Menge 5000 wären 5000 Pillen weder darstellbar noch lesbar; und die Frage, die
 * man an dieser Stelle hat, ist «wie viele stehen wo», nicht «welche». Wer die Nummern
 * braucht, klappt auf: dann und nur dann werden sie geholt.
 */
function StateRow({ groups, away = [], stepId, active, onExpand, onDeviate, deviateBlocked }: {
  groups: DiagramGroup[];
  /** Stücke, die hier stehen, aber gerade in einer Abweichung sind. */
  away?: DiagramGroup[];
  stepId: number | null;
  active: boolean;
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
  onDeviate?: (unitNumber: string) => void;
  deviateBlocked?: string;
}) {
  const [open, setOpen] = useState(false);
  const [numbers, setNumbers] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const total = groups.reduce((n, g) => n + g.count, 0);
  const gone = away.reduce((n, g) => n + g.count, 0);

  async function toggle() {
    if (!onExpand) return;
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (numbers === null) {
      setBusy(true);
      try { setNumbers(await onExpand(stepId, active)); } finally { setBusy(false); }
    }
  }

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="flex flex-wrap gap-1.5 justify-center">
        {gone > 0 && (
          // **Ausgeschert.** Das Stück steht hier – es arbeitet nur gerade woanders.
          // Es fehlt nicht, und es ist nicht fertig; beides zu behaupten wäre falsch.
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--warning-bg)', color: 'var(--warning)',
                     border: '1px dashed var(--warning)' }}
            data-tip="In einer Abweichung – kehrt an diese Stelle zurück"
          >
            <GitBranch size={11} /> In Abweichung · {gone}
          </span>
        )}
        {groups.map((g) => {
          const cfg = statusCfg(g.status);
          return (
            <button
              key={`${g.status}-${g.active}`}
              type="button"
              onClick={toggle}
              disabled={!onExpand}
              className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
              style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}22` }}
              data-tip={onExpand ? 'Nummern anzeigen' : cfg.label}
            >
              <span style={{ width: 6, height: 6, borderRadius: 999, background: cfg.color }} />
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
          {numbers?.map((n) => (
            <span key={n} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-3)' }}>
              <UnitNumber value={n} size={11} />
              {onDeviate && (
                // **Der Auslöser sitzt am Stück, an seiner Stelle im Prozess** (§3.1).
                // Er legt nichts an – er öffnet einen gewöhnlichen Auftragsentwurf, in
                // dem dieses Stück schon steht.
                <button
                  type="button"
                  onClick={() => onDeviate(n)}
                  disabled={!!deviateBlocked}
                  className="flex items-center disabled:opacity-40"
                  style={{ color: 'var(--warning)' }}
                  aria-label={`Abweichung für ${n}`}
                  data-tip={deviateBlocked ?? 'Abweichung: Auftrag auf genau dieses Stück'}
                >
                  <GitBranch size={11} />
                </button>
              )}
            </span>
          ))}
          {numbers && numbers.length < total && (
            // Ein stumm gekappte Liste sähe aus wie die ganze Wahrheit.
            <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
              … {numbers.length} von {total}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * **Ein Prozessobjekt = eine Komponente.** Der Modultyp ist Konfiguration (Name,
 * Übergang, Farbe) — es gibt hier bewusst keinen Zweig je Modulart und wird auch keinen
 * geben. Die Farbe kommt aus `lib/modules.moduleTone`, gefüttert vom Backend: ein neuer
 * Modultyp ist ein Eintrag in der Registry, kein Eingriff hier.
 *
 * Prozessmodule tragen eine **eigene Farbfamilie**, getrennt von der Ampel (§5.3): sie
 * sind keine Zustände und dürfen nicht wie welche aussehen.
 */

interface DragProps {
  index: number;
  over: boolean;
  onStart: () => void;
  onEnd: () => void;
  onDrop: (from: number) => void;
}

function StepCard({ step, active, dimmed, onDelete, tone, drag, children }: {
  step: DiagramStep; active: boolean; dimmed: boolean;
  onDelete?: () => void;
  tone?: { bg: string; fg: string; border: string };
  drag?: DragProps;
  children?: ReactNode;
}) {
  // **Der Übergang steht nicht mehr auf der Karte.** Er gehört zum Modultyp und ist für
  // jedes Modul derselbe (Durchläufer) – ihn hinzuschreiben wäre eine Zeile, die bei
  // jeder Karte dasselbe sagt. Was die Karten unterscheidet, ist ihre **Art**, und die
  // trägt das Symbol.
  const Icon = MODULE_ICON[step.moduleType] ?? Blocks;
  const c = tone ?? moduleTone(undefined);
  return (
    <div
      className="rounded-ds-lg"
      // **Gezogen wird am Griff, nicht an der Karte.** Ein `draggable` auf der Karte
      // macht ihren ganzen Inhalt zum Ziehgriff – und damit lässt sich in ihren
      // Eingabefeldern kein Text mehr markieren. Das fällt bei einem Modul kaum auf und
      // bei zwanzig sofort.
      onDragEnd={drag ? drag.onEnd : undefined}
      onDragOver={drag ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } : undefined}
      onDrop={drag ? (e) => {
        e.preventDefault();
        const from = Number(e.dataTransfer.getData('text/plain'));
        if (Number.isInteger(from)) drag.onDrop(from);
      } : undefined}
      style={{
        border: `1px solid ${active ? c.fg : c.border}`,
        background: c.bg,
        opacity: dimmed ? 0.55 : 1,
        padding: '11px 14px',
        // Die Zielkarte zeigt sich beim Ziehen – ohne das rät man, wo es landet.
        outline: drag?.over ? `2px dashed ${c.fg}` : undefined,
        outlineOffset: 2,
      }}
    >
      <div className="flex items-center gap-2.5">
        {drag && (
          <span className="flex items-center justify-center flex-none"
            style={{ width: 16, color: c.fg, opacity: 0.5, cursor: 'grab' }}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = 'move';
              e.dataTransfer.setData('text/plain', String(drag.index));
              drag.onStart();
            }}
            onDragEnd={drag.onEnd}
            role="button"
            aria-label={`${step.label} verschieben`}
            data-tip="Ziehen, um die Reihenfolge zu ändern">
            <GripVertical size={15} />
          </span>
        )}
        <span
          className="flex items-center justify-center rounded-md flex-none"
          style={{ width: 32, height: 32, background: 'var(--bg-1)', color: c.fg }}
        >
          <Icon size={17} />
        </span>
        <span className="text-sm font-semibold flex-1 min-w-0 truncate" style={{ color: c.fg }}>
          {step.label}
        </span>
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="flex items-center justify-center rounded"
            style={{ width: 26, height: 26, color: 'var(--danger)' }}
            data-tip="Modul entfernen. Ändern geht nicht – eine gesetzte Definition rastet ein."
            aria-label={`${step.label} entfernen`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
      {children && (
        <div className="mt-2.5 pt-2.5" style={{ borderTop: '1px solid var(--border-1)' }}>
          {children}
        </div>
      )}
    </div>
  );
}
