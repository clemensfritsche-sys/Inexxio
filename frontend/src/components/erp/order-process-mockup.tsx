'use client';

import { Fragment, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowDown, ArrowUp, Blocks, Flag, Lock, Minus, Play, Plus, X,
} from 'lucide-react';
import { TONE } from '@/lib/status-flow';
import { FlowFrame, FlowNode, polyPath, type FlowAnchor } from './process-flow';

/**
 * **MOCKUP — der Auftrag-Reiter, wie er aussehen soll.**
 *
 * Statische Beispieldaten, keine Datenbank, keine API. Der Zweck ist, die Grundlogik aus
 * `PROCESS_CORE.md` einmal **zu sehen** statt sie zu lesen — und die kritische
 * Darstellungs-Anforderung überprüfbar zu machen: die Linien werden aus gemessenen
 * Ankerpunkten berechnet (`process-flow.tsx`), also trägt dasselbe Bild 3 wie 50 Module.
 * Die Steuerleiste oben ist genau dafür da.
 *
 * Was hier **bewusst** nicht steht:
 *
 * - **Keine echten Modulnamen.** Die Prozessschrittmodule sind noch nicht definiert
 *   (§9.1, erstes wird die Datenerfassung); erfundene Namen wären eine Behauptung.
 * - **Keine Unterauftrags-Logik.** Der Abzweig ist *angedeutet* — gestrichelt, weil der
 *   Mechanismus offen ist (§9.2). Dasselbe links für den übergeordneten Auftrag (§9.3).
 * - **Nichts unterhalb der aktuellen Stelle.** Der Fluss sagt nicht voraus (§4.3, §8):
 *   wo noch kein Material war, steht auch keines. Sichtbar zu machen, indem man mit
 *   «Fortschritt» durchgeht.
 *
 * Wird ersetzt, sobald die Prozesslogik gebaut ist. `process-flow.tsx` bleibt.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Beispiel-Vokabular  (MOCKUP — die verbindliche Liste ist offen, §10 Q1)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Farbe hängt am **Status**, nicht an der Position im Fluss (§7). Genau darum stehen
 * hier Statuswerte und keine Positionsnamen: dieselbe Einzelinstanz sieht an jeder
 * Stelle des Flusses gleich aus, solange ihr Status derselbe ist.
 */
const STATUS = {
  verfuegbar: { label: 'Verfügbar', ...TONE.done },
  im_prozess: { label: 'Im Prozess', ...TONE.pending },
  gesperrt: { label: 'Gesperrt', ...TONE.danger },
  abgeschlossen: { label: 'Abgeschlossen', ...TONE.done },
} as const;

type StatusKey = keyof typeof STATUS;

/**
 * Prozessmodule tragen eine **eigene** Farbfamilie (§7) — sie sind keine Zustände und
 * dürfen nicht wie welche aussehen. Slate ist im Design-System die leise Stimme des
 * ERP und damit sicher keine Ampelfarbe. Die endgültige Familie kommt mit den Modulen.
 */
const MODULE_TONE = {
  bg: 'var(--accent-soft)',
  fg: 'var(--accent-ink)',
  border: '#BFD6E2',
};

/** Übergänge von Start und Ende — im Mockup systemweit fest (§10 Q2). */
const START_STEP = { before: 'verfuegbar' as StatusKey, after: 'im_prozess' as StatusKey };
const END_STEP = { before: 'im_prozess' as StatusKey, after: 'abgeschlossen' as StatusKey };

/** Beispiel-Einzelinstanzen: `<Instanz-Objektnummer>-<Suffix>`, so wie sie entstehen. */
const UNIT_POOL = [
  '100000412-1', '100000412-2', '100000412-3', '100000412-4',
  '100000418-1', '100000418-2', '100000423-1', '100000423-2',
];

interface MockModule {
  id: number;
  /** Platzhalter — die Module sind noch nicht definiert (§9.1). */
  name: string;
  before: StatusKey;
  after: StatusKey;
  /** Deutet einen Unterauftrag an. Nur angedeutet — der Mechanismus ist offen (§9.2). */
  branch?: boolean;
}

const INITIAL_MODULES: MockModule[] = [
  { id: 1, name: 'Prozessschrittmodul 1', before: 'im_prozess', after: 'im_prozess' },
  { id: 2, name: 'Prozessschrittmodul 2', before: 'im_prozess', after: 'im_prozess', branch: true },
  { id: 3, name: 'Prozessschrittmodul 3', before: 'im_prozess', after: 'im_prozess' },
];

type Lifecycle = 'entwurf' | 'freigegeben';

// ─────────────────────────────────────────────────────────────────────────────
// Der Fluss
// ─────────────────────────────────────────────────────────────────────────────

/** Ein Knoten der mittleren Spur. Start, Modul, Zustand und Ende sind dasselbe Bauteil. */
type Node =
  | { id: string; kind: 'definition' }
  | { id: string; kind: 'terminal'; which: 'start' | 'end' }
  | { id: string; kind: 'state'; status: StatusKey }
  | { id: string; kind: 'module'; mod: MockModule };

export function OrderProcessMockup() {
  const [lifecycle, setLifecycle] = useState<Lifecycle>('freigegeben');
  const [modules, setModules] = useState<MockModule[]>(INITIAL_MODULES);
  const [units, setUnits] = useState<string[]>(UNIT_POOL.slice(0, 3));
  const [selected, setSelected] = useState<number | null>(null);
  /** Wie viele Module sind durchlaufen. Im Entwurf ist nichts unterwegs (§5). */
  const [walked, setWalked] = useState(1);

  const running = lifecycle === 'freigegeben';
  const progress = running ? Math.min(walked, modules.length) : 0;

  /**
   * Die Knotenfolge. Die **Zustandsanzeigen zwischen den Modulen sind abgeleitet**, nicht
   * eingetragen: der Zustand nach Modul *i* ist per Statusregel (§3) genau das `Nachher`
   * von *i*. So zeigt das Bild die Regel, statt sie zu wiederholen.
   *
   * Unterhalb der aktuellen Stelle entsteht **kein** Zustandsknoten — dort war noch kein
   * Material, also gibt es keines anzuzeigen (§8). Eine leere Anzeige wäre eine
   * Fallback-Anzeige, und die ist verboten.
   */
  const nodes = useMemo<Node[]>(() => {
    const out: Node[] = [{ id: 'def', kind: 'definition' }];
    out.push({ id: 'start', kind: 'terminal', which: 'start' });
    if (running) out.push({ id: 'state-0', kind: 'state', status: START_STEP.after });
    modules.forEach((m, i) => {
      out.push({ id: `mod-${m.id}`, kind: 'module', mod: m });
      if (running && i < progress) {
        out.push({ id: `state-${i + 1}`, kind: 'state', status: m.after });
      }
    });
    out.push({ id: 'end', kind: 'terminal', which: 'end' });
    if (running && progress >= modules.length) {
      out.push({ id: 'state-end', kind: 'state', status: END_STEP.after });
    }
    return out;
  }, [modules, running, progress]);

  /**
   * Bis zu welcher Kante ist die Linie stark? Bis zu dem Knoten, den der Prozess wirklich
   * erreicht hat — nicht weiter. Im Entwurf ist niemand unterwegs (§5), dort ist die ganze
   * Achse Haarlinie.
   */
  const walkedEdges = useMemo(() => {
    if (!running) return 0;
    const lastReached = progress >= modules.length ? 'state-end' : `state-${progress}`;
    return Math.max(0, nodes.findIndex((n) => n.id === lastReached));
  }, [nodes, running, progress, modules.length]);

  const branching = running ? modules.filter((m) => m.branch) : [];

  return (
    <div className="flex flex-col gap-3">
      <MockBar
        lifecycle={lifecycle}
        onLifecycle={(l) => { setLifecycle(l); setSelected(null); }}
        moduleCount={modules.length}
        onModules={setModules}
        unitCount={units.length}
        onUnits={setUnits}
        progress={progress}
        onProgress={setWalked}
      />

      <FlowFrame lines={(a) => <Lines nodes={nodes} anchors={a} walkedEdges={walkedEdges} branching={branching} />}>
        {(width) => {
          // Schmal ⇒ nur die mittlere Spur (PROCESS_CORE.md §8). Die Entscheidung fällt an
          // der **gemessenen** Breite, damit Layout und Linien denselben Massstab haben.
          const narrow = width < 860;
          // Jeder Knoten bekommt eine **Zeile**; was seitlich zu ihm gehört, steht in
          // derselben Zeile. Damit setzt das Raster die Nachbarschaft – und die Abzweigung
          // ist eine kurze Waagrechte statt eines Umwegs quer über die Fläche.
          const mid = narrow ? 1 : 2;
          return (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: narrow
                  ? 'minmax(0,1fr)'
                  : 'minmax(0,0.85fr) minmax(0,1.6fr) minmax(0,0.85fr)',
                columnGap: 20,
                rowGap: 14,
                alignItems: 'center',
              }}
            >
              {nodes.map((n, i) => {
                const row = i + 1;
                const side: ReactNode[] = [];

                if (!narrow && n.kind === 'definition') {
                  side.push(
                    <div key="parent" style={{ gridColumn: 1, gridRow: row }}>
                      <SideLane id="parent" icon={ArrowUp} title="Übergeordneter Auftrag" note="Mechanismus offen (§9.3)" />
                    </div>,
                    <div key="sub-empty" style={{ gridColumn: 3, gridRow: row }}>
                      {branching.length === 0 && (
                        <SideLane id="sub-empty" icon={ArrowDown} title="Untergeordnete Aufträge" note="Mechanismus offen (§9.2)" />
                      )}
                    </div>,
                  );
                }
                if (!narrow && n.kind === 'module' && n.mod.branch && running) {
                  side.push(
                    <div key={`sub-${n.mod.id}`} style={{ gridColumn: 3, gridRow: row }}>
                      <FlowNode id={`sub-${n.mod.id}`}><SubOrderCard /></FlowNode>
                    </div>,
                  );
                }

                let body: ReactNode;
                if (n.kind === 'definition') {
                  body = (
                    <FlowNode id={n.id} style={{ width: '100%' }}>
                      <DefinitionCard
                        units={units}
                        frozen={running}
                        onAdd={() => setUnits((u) => [...u, UNIT_POOL[u.length % UNIT_POOL.length]])}
                        onRemove={(k) => setUnits((u) => u.filter((_, j) => j !== k))}
                      />
                    </FlowNode>
                  );
                } else if (n.kind === 'terminal') {
                  body = <FlowNode id={n.id}><Terminal which={n.which} /></FlowNode>;
                } else if (n.kind === 'state') {
                  body = (
                    <FlowNode id={n.id} style={{ width: '100%' }}>
                      <StateRow units={units} status={n.status} />
                    </FlowNode>
                  );
                } else {
                  const idx = modules.findIndex((m) => m.id === n.mod.id);
                  body = (
                    <FlowNode
                      id={n.id}
                      style={{ width: '100%' }}
                      onClick={() => setSelected(selected === n.mod.id ? null : n.mod.id)}
                    >
                      <ModuleCard
                        mod={n.mod}
                        state={!running ? 'defined' : idx < progress ? 'done' : idx === progress ? 'active' : 'ahead'}
                        open={selected === n.mod.id}
                        narrow={narrow}
                      />
                    </FlowNode>
                  );
                }

                return (
                  <Fragment key={n.id}>
                    {side}
                    <div style={{ gridColumn: mid, gridRow: row, display: 'flex', justifyContent: 'center' }}>
                      {body}
                    </div>
                  </Fragment>
                );
              })}
            </div>
          );
        }}
      </FlowFrame>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Die Linien — berechnet, nirgends eingetragen
// ─────────────────────────────────────────────────────────────────────────────

function Lines({ nodes, anchors, walkedEdges, branching }: {
  nodes: Node[];
  anchors: Record<string, FlowAnchor>;
  walkedEdges: number;
  branching: MockModule[];
}) {
  const out: ReactNode[] = [];

  // Die Achse: je ein Stück zwischen zwei aufeinanderfolgenden Knoten. Stark bis zu der
  // Stelle, an der der Prozess steht — darunter Haarlinie, weil dort noch nichts war.
  for (let i = 0; i < nodes.length - 1; i++) {
    const A = anchors[nodes[i].id];
    const B = anchors[nodes[i + 1].id];
    if (!A || !B) continue;
    const strong = i < walkedEdges;
    out.push(
      <path
        key={`axis-${nodes[i].id}`}
        d={polyPath([[A.cx, A.bottom], [B.cx, B.top]])}
        fill="none"
        stroke={strong ? 'var(--fg-2)' : 'var(--border-2)'}
        strokeWidth={2}
      />,
    );
  }

  // Der Abzweig: raus aus der Achse, in den Unterauftrag, unterhalb zurück. Gestrichelt,
  // weil er angedeutet und nicht definiert ist (§9.2) — die Achse selbst ist es nie.
  for (const m of branching) {
    const M = anchors[`mod-${m.id}`];
    const S = anchors[`sub-${m.id}`];
    if (!M || !S) continue;
    const at = nodes.findIndex((n) => n.id === `mod-${m.id}`);
    const nxt = at >= 0 && at < nodes.length - 1 ? anchors[nodes[at + 1].id] : undefined;
    const backY = nxt ? Math.round((M.bottom + nxt.top) / 2) : M.bottom + 24;
    // Der Unterauftrag steht in derselben Rasterzeile, also ist der Hinweg eine kurze
    // Waagrechte — bei gleicher Höhe fällt der Knick von selbst weg (`polyPath` faltet
    // doppelte Punkte zusammen).
    out.push(
      <path
        key={`out-${m.id}`}
        d={polyPath([[M.right, M.cy], [Math.round((M.right + S.left) / 2), M.cy],
          [Math.round((M.right + S.left) / 2), S.cy], [S.left, S.cy]])}
        fill="none"
        stroke="var(--border-2)"
        strokeWidth={2}
        strokeDasharray="5 5"
      />,
      <path
        key={`back-${m.id}`}
        d={polyPath([[S.cx, S.bottom], [S.cx, backY], [M.cx, backY]])}
        fill="none"
        stroke="var(--border-2)"
        strokeWidth={2}
        strokeDasharray="5 5"
      />,
    );
  }

  // Der übergeordnete Auftrag mündet in die Definition — dieselbe Geste, andere Richtung.
  const P = anchors.parent;
  const D = anchors.def;
  if (P && D) {
    const x = Math.round((P.right + D.left) / 2);
    out.push(
      <path
        key="parent"
        d={polyPath([[P.right, P.cy], [x, P.cy], [x, D.cy], [D.left, D.cy]])}
        fill="none"
        stroke="var(--border-2)"
        strokeWidth={2}
        strokeDasharray="5 5"
      />,
    );
  }

  return <>{out}</>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Knoten
// ─────────────────────────────────────────────────────────────────────────────

function DefinitionCard({ units, frozen, onAdd, onRemove }: {
  units: string[];
  frozen: boolean;
  onAdd: () => void;
  onRemove: (i: number) => void;
}) {
  return (
    <div
      className="rounded-ds-lg"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 14 }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
          Definition
        </span>
        {frozen && (
          <span
            className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded"
            style={{ background: 'var(--bg-3)', color: 'var(--fg-3)' }}
            title="Freigegeben: die Definition ist eingefroren. Kein Nachschieben, kein Ersetzen (§2.1)."
          >
            <Lock size={11} /> eingefroren
          </span>
        )}
      </div>
      <p className="text-xs mb-3" style={{ color: 'var(--fg-3)' }}>
        Mit welchen Einzelinstanzen arbeitet dieser Auftrag? Ohne Definition kein Start.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {units.map((u, i) => (
          <UnitPill
            key={`${u}-${i}`}
            unit={u}
            status="verfuegbar"
            onRemove={frozen ? undefined : () => onRemove(i)}
          />
        ))}
        {!frozen && (
          <button
            type="button"
            onClick={onAdd}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
            style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}
          >
            <Plus size={12} /> Einzelinstanz
          </button>
        )}
      </div>
    </div>
  );
}

function Terminal({ which }: { which: 'start' | 'end' }) {
  const Icon = which === 'start' ? Play : Flag;
  const step = which === 'start' ? START_STEP : END_STEP;
  return (
    <div
      className="flex items-center justify-center rounded-full"
      style={{
        width: 46,
        height: 46,
        border: `2px solid ${STATUS[step.after].color}`,
        background: STATUS[step.after].bg,
        color: STATUS[step.after].color,
      }}
      title={`${which === 'start' ? 'Start' : 'Ende'}: ${STATUS[step.before].label} → ${STATUS[step.after].label}`}
    >
      <Icon size={19} />
    </div>
  );
}

function StateRow({ units, status }: { units: string[]; status: StatusKey }) {
  return (
    <div className="flex flex-wrap gap-1.5 justify-center">
      {units.map((u, i) => (
        <UnitPill key={`${u}-${i}`} unit={u} status={status} />
      ))}
    </div>
  );
}

function UnitPill({ unit, status, onRemove }: {
  unit: string;
  status: StatusKey;
  onRemove?: () => void;
}) {
  const s = STATUS[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}22` }}
      title={s.label}
    >
      <span style={{ width: 6, height: 6, borderRadius: 999, background: s.color }} />
      {unit}
      {onRemove && (
        <button type="button" onClick={onRemove} style={{ color: 'inherit', opacity: 0.6 }} aria-label="entfernen">
          <X size={11} />
        </button>
      )}
    </span>
  );
}

/**
 * **Ein Prozessobjekt = eine Komponente** (§8). Der Modultyp ist Konfiguration — Name,
 * Symbol, Übergang. Es gibt hier bewusst keinen Zweig je Modulart und wird auch später
 * keinen geben.
 */
function ModuleCard({ mod, state, open, narrow }: {
  mod: MockModule;
  state: 'defined' | 'done' | 'active' | 'ahead';
  open: boolean;
  narrow: boolean;
}) {
  const muted = state === 'done' || state === 'ahead';
  return (
    <div
      className="rounded-ds-lg cursor-pointer transition-opacity"
      style={{
        border: `1px solid ${state === 'active' ? MODULE_TONE.fg : MODULE_TONE.border}`,
        background: MODULE_TONE.bg,
        opacity: muted ? 0.55 : 1,
        padding: '11px 14px',
      }}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="flex items-center justify-center rounded-md flex-none"
          style={{ width: 32, height: 32, background: 'var(--bg-1)', color: MODULE_TONE.fg }}
        >
          <Blocks size={17} />
        </span>
        <span className="text-sm font-semibold flex-1 min-w-0 truncate" style={{ color: MODULE_TONE.fg }}>
          {mod.name}
        </span>
        {mod.branch && narrow && (
          <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>→ Unterauftrag</span>
        )}
      </div>
      {open && (
        <div
          className="mt-2.5 pt-2.5 text-xs flex flex-wrap items-center gap-1.5"
          style={{ borderTop: '1px solid var(--border-1)', color: 'var(--fg-3)' }}
        >
          <span>Vorher</span>
          <b style={{ color: STATUS[mod.before].color }}>{STATUS[mod.before].label}</b>
          <span>→ Nachher</span>
          <b style={{ color: STATUS[mod.after].color }}>{STATUS[mod.after].label}</b>
          <span style={{ color: 'var(--fg-4)' }}>· Pflichtbestandteil jeder Moduldefinition (§3)</span>
        </div>
      )}
    </div>
  );
}

function SubOrderCard() {
  return (
    <div
      className="rounded-ds-lg p-3 text-center"
      style={{ border: '1px dashed var(--border-2)' }}
    >
      <ArrowDown size={16} style={{ color: 'var(--fg-4)', margin: '0 auto 4px' }} />
      <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
        Unterauftrag
      </div>
      <div className="text-[11px]" style={{ color: 'var(--fg-4)' }}>
        Mechanismus offen (§9.2)
      </div>
    </div>
  );
}

function SideLane({ id, icon: Icon, title, note }: {
  id: string;
  icon: React.ElementType;
  title: string;
  note: string;
}) {
  return (
    <FlowNode id={id}>
      <div
        className="rounded-ds-lg p-3 text-center"
        style={{ border: '1px dashed var(--border-2)' }}
      >
        <Icon size={16} style={{ color: 'var(--fg-4)', margin: '0 auto 4px' }} />
        <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
          {title}
        </div>
        <div className="text-[11px]" style={{ color: 'var(--fg-4)' }}>{note}</div>
      </div>
    </FlowNode>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Steuerleiste — sichtbar Gerüst, nicht Produkt
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Bewusst in der Warnfarbe und bewusst anders gesetzt als die übrige Oberfläche: das ist
 * kein Bedienelement des Auftrags, sondern das Werkzeug, mit dem sich die Zusagen aus
 * `PROCESS_CORE.md` nachprüfen lassen — vor allem die, dass 50 Module dasselbe Bild
 * ergeben wie 3.
 */
function MockBar({
  lifecycle, onLifecycle, moduleCount, onModules, unitCount, onUnits, progress, onProgress,
}: {
  lifecycle: Lifecycle;
  onLifecycle: (l: Lifecycle) => void;
  moduleCount: number;
  onModules: (fn: (m: MockModule[]) => MockModule[]) => void;
  unitCount: number;
  onUnits: (fn: (u: string[]) => string[]) => void;
  progress: number;
  onProgress: (fn: (n: number) => number) => void;
}) {
  const running = lifecycle === 'freigegeben';
  const grow = (n: number) =>
    onModules((m) => {
      const next = [...m];
      while (next.length < n) {
        const id = (next[next.length - 1]?.id ?? 0) + 1;
        next.push({ id, name: `Prozessschrittmodul ${next.length + 1}`, before: 'im_prozess', after: 'im_prozess' });
      }
      return next.slice(0, n);
    });

  return (
    <div
      className="rounded-ds-lg flex flex-wrap items-center gap-x-4 gap-y-2"
      style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning)', padding: '9px 12px' }}
    >
      <span
        className="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
        style={{ background: 'var(--warning)', color: '#fff' }}
      >
        Mockup
      </span>
      <span className="text-xs" style={{ color: 'var(--fg-2)' }}>
        Beispieldaten, keine Datenbank. Grundlogik: <code>PROCESS_CORE.md</code>.
      </span>

      <span className="flex-1" />

      <Group label="Lebenszyklus">
        {(['entwurf', 'freigegeben'] as const).map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => onLifecycle(l)}
            className="text-xs px-2 py-0.5 rounded"
            style={{
              background: lifecycle === l ? 'var(--fg-1)' : 'transparent',
              color: lifecycle === l ? '#fff' : 'var(--fg-2)',
              border: '1px solid var(--border-2)',
            }}
          >
            {l === 'entwurf' ? 'Entwurf' : 'Freigegeben'}
          </button>
        ))}
      </Group>

      {!running ? (
        <>
          <Group label="Module">
            <Step onClick={() => grow(Math.max(1, moduleCount - 1))} icon={Minus} />
            <Count value={moduleCount} />
            <Step onClick={() => grow(moduleCount + 1)} icon={Plus} />
            <button
              type="button"
              onClick={() => grow(50)}
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ border: '1px solid var(--border-2)', color: 'var(--fg-2)' }}
              title="Die Zusage aus §8: 50 Schritte müssen dasselbe Bild ergeben wie 3."
            >
              50
            </button>
          </Group>
          <Group label="Einzelinstanzen">
            <Step onClick={() => onUnits((u) => u.slice(0, Math.max(1, u.length - 1)))} icon={Minus} />
            <Count value={unitCount} />
            <Step onClick={() => onUnits((u) => [...u, UNIT_POOL[u.length % UNIT_POOL.length]])} icon={Plus} />
          </Group>
        </>
      ) : (
        <Group label="Fortschritt">
          <Step onClick={() => onProgress((n) => Math.max(0, n - 1))} icon={Minus} />
          <Count value={progress} />
          <Step onClick={() => onProgress((n) => Math.min(moduleCount, n + 1))} icon={Plus} />
        </Group>
      )}
    </div>
  );
}

function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>{label}</span>
      {children}
    </span>
  );
}

function Step({ onClick, icon: Icon }: { onClick: () => void; icon: React.ElementType }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center rounded"
      style={{ width: 20, height: 20, border: '1px solid var(--border-2)', color: 'var(--fg-2)' }}
    >
      <Icon size={12} />
    </button>
  );
}

function Count({ value }: { value: number }) {
  return (
    <span className="text-xs ix-tnum" style={{ minWidth: 18, textAlign: 'center', color: 'var(--fg-1)' }}>
      {value}
    </span>
  );
}
