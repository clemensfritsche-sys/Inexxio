'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { Blocks, ChevronDown, ChevronUp, Flag, Play, Trash2 } from 'lucide-react';
import { MODULE_ICON } from '@/lib/modules';
import { FlowFrame, FlowNode, polyPath, type FlowAnchor } from './process-flow';
import { statusCfg, START_AFTER, START_BEFORE, END_BEFORE, statusLabel } from '@/lib/process-status';

/**
 * **Die Prozessdarstellung — EINE Komponente, zwei Modi.**
 *
 * | Modus | Wo | Was |
 * |---|---|---|
 * | `definition` | Auftragsentwurf, später der Artikel-Reiter «Erzeugungsprozess» | Module anlegen, löschen, sortieren |
 * | `ausfuehrung` | freigegebener Auftrag | Zustand je Objekt, aktuelle Stelle, Ausführung |
 *
 * Zweimal zu bauen wäre an dieser Stelle der teuerste Fehler (PROCESS_CORE.md §8.1) —
 * darum ist der Modus ein Schalter und kein zweites Bauteil. Beide Modi werden **schon
 * im Auftrag** gebraucht (Entwurf ↔ freigegeben); der Artikel benutzt später nur den
 * ersten und ist damit kein neuer Fall.
 *
 * Die **Definition der Einzelinstanzen** ist bewusst **nicht** Teil dieses Diagramms,
 * sondern ein Slot darüber (`head`): ein Artikel hat keine Einzelinstanzen, und ein
 * Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar.
 *
 * **Ein Prozessobjekt = eine Komponente.** Start, Modul und Ende teilen sich `FlowNode`;
 * der Modultyp ist Konfiguration, nicht ein eigenes Bauteil.
 */

export interface DiagramStep {
  /** Serverseitige id im Ausführungsmodus; im Entwurf eine lokale Nummer. */
  id: number;
  name: string;
  moduleType: string;
}

export type DiagramMode = 'definition' | 'ausfuehrung';

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

export function ProcessDiagram({
  mode, steps, groups = [], activeStepId = null, endStatus,
  head, onDelete, renderStep, onExpand,
}: {
  mode: DiagramMode;
  steps: DiagramStep[];
  /** Nur im Ausführungsmodus – im Definitionsmodus gibt es nichts unterwegs (§6.1). */
  groups?: DiagramGroup[];
  activeStepId?: number | null;
  endStatus: string;
  /** Slot über dem Start: die Definition (nur beim Auftrag). */
  head?: ReactNode;
  /** Nur im Definitionsmodus: ein Modul entfernen. */
  onDelete?: (id: number) => void;
  /** Nur im Ausführungsmodus: was in der Karte des aktiven Moduls steht. */
  renderStep?: (step: DiagramStep, isActive: boolean) => ReactNode;
  /** Eine Gruppe aufklappen: die einzelnen Nummern nachladen. */
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
}) {
  const running = mode === 'ausfuehrung';

  /**
   * Die Knotenfolge. Die **Zustandsanzeige zwischen zwei Modulen ist abgeleitet**: nach
   * Modul *i* steht per Statusregel genau dessen `Nachher` (§4). Das Bild zeigt damit
   * die Regel, statt sie zu wiederholen.
   *
   * Unterhalb der aktuellen Stelle entsteht **kein** Zustandsknoten — dort war noch kein
   * Material, also gibt es keines anzuzeigen (§7.3). Eine leere Anzeige wäre eine
   * Fallback-Anzeige.
   */
  const nodes = useMemo(() => {
    const out: Array<
      | { id: string; kind: 'head' }
      | { id: string; kind: 'terminal'; which: 'start' | 'end' }
      | { id: string; kind: 'state'; at: number | null }
      | { id: string; kind: 'step'; step: DiagramStep }
    > = [];
    if (head) out.push({ id: 'head', kind: 'head' });
    out.push({ id: 'start', kind: 'terminal', which: 'start' });
    if (running && groupsAt(groups, steps[0]?.id ?? null, true).length) {
      out.push({ id: 'state-start', kind: 'state', at: steps[0]?.id ?? null });
    }
    steps.forEach((s, i) => {
      out.push({ id: `step-${s.id}`, kind: 'step', step: s });
      const next = steps[i + 1]?.id ?? null;
      if (running && next !== null && groupsAt(groups, next, true).length) {
        out.push({ id: `state-${s.id}`, kind: 'state', at: next });
      }
    });
    out.push({ id: 'end', kind: 'terminal', which: 'end' });
    if (running && groups.some((g) => !g.active)) {
      out.push({ id: 'state-end', kind: 'state', at: null });
    }
    return out;
  }, [head, steps, groups, running]);

  /** Bis wohin ist die Linie stark? Bis zu der Stelle, an der der Prozess wirklich steht. */
  const walkedEdges = useMemo(() => {
    if (!running) return 0;
    let last = -1;
    nodes.forEach((n, i) => {
      if (n.kind === 'state') last = i;
    });
    return Math.max(0, last);
  }, [nodes, running]);

  return (
    <FlowFrame lines={(a) => <Lines ids={nodes.map((n) => n.id)} anchors={a} walked={walkedEdges} />}>
      {() => (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
          {nodes.map((n) => {
            if (n.kind === 'head') {
              return <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>{head}</FlowNode>;
            }
            if (n.kind === 'terminal') {
              return (
                <FlowNode key={n.id} id={n.id}>
                  <Terminal which={n.which} endStatus={endStatus} />
                </FlowNode>
              );
            }
            if (n.kind === 'state') {
              const active = n.id !== 'state-end';
              return (
                <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>
                  <StateRow
                    groups={groupsAt(groups, n.at, active)}
                    stepId={n.at}
                    active={active}
                    onExpand={onExpand}
                  />
                </FlowNode>
              );
            }
            const isActive = running && n.step.id === activeStepId;
            return (
              <FlowNode key={n.id} id={n.id} style={{ width: '100%' }}>
                <StepCard
                  step={n.step}
                  active={isActive}
                  dimmed={running && !isActive}
                  onDelete={mode === 'definition' && onDelete ? () => onDelete(n.step.id) : undefined}
                >
                  {renderStep?.(n.step, isActive)}
                </StepCard>
              </FlowNode>
            );
          })}
        </div>
      )}
    </FlowFrame>
  );
}

function groupsAt(groups: DiagramGroup[], stepId: number | null, active: boolean): DiagramGroup[] {
  return groups.filter((g) => g.active === active && g.currentStepId === stepId);
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
function StateRow({ groups, stepId, active, onExpand }: {
  groups: DiagramGroup[];
  stepId: number | null;
  active: boolean;
  onExpand?: (stepId: number | null, active: boolean) => Promise<string[]>;
}) {
  const [open, setOpen] = useState(false);
  const [numbers, setNumbers] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const total = groups.reduce((n, g) => n + g.count, 0);

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
            <span key={n} className="text-[11px] ix-tnum px-1.5 py-0.5 rounded"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-3)' }}>{n}</span>
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
 * Übergang) — es gibt hier bewusst keinen Zweig je Modulart und wird auch keinen geben.
 *
 * Prozessmodule tragen eine **eigene Farbfamilie**, getrennt von der Ampel (§5.3): sie
 * sind keine Zustände und dürfen nicht wie welche aussehen.
 */
export const MODULE_TONE = { bg: 'var(--accent-soft)', fg: 'var(--accent-ink)', border: '#BFD6E2' };

function StepCard({ step, active, dimmed, onDelete, children }: {
  step: DiagramStep; active: boolean; dimmed: boolean;
  onDelete?: () => void; children?: ReactNode;
}) {
  // **Der Übergang steht nicht mehr auf der Karte.** Er gehört zum Modultyp und ist für
  // jedes Modul derselbe (Durchläufer) – ihn hinzuschreiben wäre eine Zeile, die bei
  // jeder Karte dasselbe sagt. Was die Karten unterscheidet, ist ihre **Art**, und die
  // trägt das Symbol.
  const Icon = MODULE_ICON[step.moduleType] ?? Blocks;
  return (
    <div
      className="rounded-ds-lg"
      style={{
        border: `1px solid ${active ? MODULE_TONE.fg : MODULE_TONE.border}`,
        background: MODULE_TONE.bg,
        opacity: dimmed ? 0.55 : 1,
        padding: '11px 14px',
      }}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="flex items-center justify-center rounded-md flex-none"
          style={{ width: 32, height: 32, background: 'var(--bg-1)', color: MODULE_TONE.fg }}
        >
          <Icon size={17} />
        </span>
        <span className="text-sm font-semibold flex-1 min-w-0 truncate" style={{ color: MODULE_TONE.fg }}>
          {step.name}
        </span>
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="flex items-center justify-center rounded"
            style={{ width: 26, height: 26, color: 'var(--danger)' }}
            data-tip="Modul entfernen. Ändern geht nicht – eine gesetzte Definition rastet ein."
            aria-label={`${step.name} entfernen`}
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
