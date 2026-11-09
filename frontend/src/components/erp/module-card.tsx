'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, GripVertical, Lock, Trash2, type LucideIcon } from 'lucide-react';
import { moduleIcon, moduleTone } from '@/lib/modules';
import { MODULE_CARD, MODULE_TITLE } from './module-ui';
import { formatObjectId } from '@/lib/utils';
import { DiagramStep } from '@/lib/process-graph';

/**
 * **Ein Prozessobjekt = eine Komponente.** Der Modultyp ist Konfiguration (Name, Übergang,
 * Farbe aus `lib/modules.moduleTone`) – kein Zweig je Modulart. Module tragen eine eigene
 * Farbfamilie, getrennt von der Ampel (§5.4).
 */

interface DragProps {
  index: number;
  over: boolean;
  onStart: () => void;
  onEnd: () => void;
  onDrop: (from: number) => void;
}

/**
 * **Das Zeichen eines Moduls** – getöntes Quadrat mit Symbol, die einzige Fläche, die ein Modul
 * färbt. Die Historie hängt an der Kopfzeile (`ModuleShell.history`).
 */
function ModuleMark({ icon: Icon, tone, bg = 'var(--bg-1)' }: {
  icon: LucideIcon; tone: string;
  /** Die Fläche unter dem Symbol – die Modulfarbe, denn die Karte selbst ist weiss. */
  bg?: string;
}) {
  return (
    <span
      className="flex items-center justify-center rounded-ds-sm flex-none"
      style={{ width: 34, height: 34, background: bg, color: tone }}
    >
      <Icon size={17} />
    </span>
  );
}

/**
 * **Die Hülle einer Modul-Karte — EIN Bauteil**: weisse Karte (`module-ui.MODULE_CARD`), Kopf mit
 * `ModuleMark`, Haarlinie vor dem Körper; der Rahmen trägt die Modulfarbe, wenn das Modul dran
 * ist. `lead` und `trail` nehmen Eigenes auf (Ziehgriff, Schloss, Chevron, Löschen).
 */
function ModuleShell({ tone, icon, label, active, lead, trail, head, body,
  history, children }: {
  tone: { fg: string; bg: string; border: string };
  icon: LucideIcon;
  label: string;
  /** Ist dieses Modul an der Reihe? Dann trägt der Rahmen die kräftige Farbe. */
  active?: boolean;
  lead?: ReactNode;
  trail?: ReactNode;
  /** Zusätzliche Eigenschaften am Kopf-Element – z. B. Aufklappen. */
  head?: React.HTMLAttributes<HTMLDivElement>;
  /** Zusätzliche Eigenschaften am äusseren Rahmen – z. B. Ziehen. */
  body?: React.HTMLAttributes<HTMLDivElement>;
  /**
   * **Die Historie hängt an der KOPFZEILE** – über die ganze Kartenbreite; nicht am Rahmen und
   * nicht nur an der Beschriftung. Eigene Blasen darin gewinnen (die innere, `hints.TipHost`).
   */
  history?: string;
  children?: ReactNode;
}) {
  return (
    // **Die Karte ist weiss** wie jeder Datensatz (Struktur vor Fläche); die Modulfarbe
    // steht in der Marke und im Rahmen, wenn das Modul dran ist. `data-where-module` nennt
    // das Modul für die Stecknadel (`lib/pin-point`).
    <div className="rounded-ds-lg" data-where-module={label} {...body}
      style={{
        ...MODULE_CARD,
        borderColor: active ? tone.fg : 'var(--border-1)',
        ...(body?.style ?? {}),
      }}>
      <div className="flex items-center gap-3"
        // Fokussierbar, damit die Blase auch ohne Hover erscheint (Tipp, Tab); `head` gewinnt.
        tabIndex={history ? 0 : undefined}
        {...(history ? { 'data-tip': history, 'data-tip-list': '' } : {})}
        {...head}>
        {lead}
        <ModuleMark icon={icon} tone={tone.fg} bg={tone.bg} />
        {/* Der Name trägt die Display-Schrift, nicht die Modulfarbe – eine Tönung läse sich als Zustand. */}
        <span className="flex-1 min-w-0 truncate" style={MODULE_TITLE}>{label}</span>
        {trail}
      </div>
      {children && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border-1)' }}>
          {children}
        </div>
      )}
    </div>
  );
}


export function StepCard({ step, active, dimmed, defaultOpen, onDelete, drag, history,
  children }: {
  step: DiagramStep; active: boolean; dimmed: boolean;
  /** Was an diesem Modul passiert ist – der Ereignis-Log, an seinem Ort (§5). */
  history?: string;
  /** Startet dieses Modul aufgeklappt? Sonst zu – und der Kopf klappt es auf. */
  defaultOpen?: boolean;
  onDelete?: () => void;
  drag?: DragProps;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(!!defaultOpen);

  // ►► **Wird ein Modul zum aktiven, klappt es auf.** ◄◄ Der Effekt hängt nur an
  // `defaultOpen`: wer selbst zuklappt, bleibt zugeklappt.
  useEffect(() => { setOpen(!!defaultOpen); }, [defaultOpen]);
  // **Die Sperre gehört hierher, nicht ins Modul**: `fieldset[disabled]` schaltet jede Eingabe
  // und jeden Knopf darin ab, was immer das Modul rendert; der Inhalt bleibt sichtbar.
  const waiting = step.waitingFor ?? [];
  const locked = waiting.length > 0;
  // Der Übergang steht nicht auf der Karte (für jedes Modul derselbe); die Art trägt das Symbol.
  const Icon = moduleIcon(step.moduleType);
  // Die Farbe kommt vom Schritt; `moduleTone` meldet eine unbekannte Familie sichtbar.
  const c = moduleTone(step.tone);
  return (
    // Die Hülle ist `ModuleShell`; Eigenes hängt in `lead`/`trail`.
    <ModuleShell
      tone={c} icon={Icon} label={step.label} active={active}
      body={{
        // Gezogen wird am Griff, nicht an der Karte – sonst liesse sich in den Feldern kein
        // Text markieren.
        onDragEnd: drag ? drag.onEnd : undefined,
        onDragOver: drag
          ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
          : undefined,
        onDrop: drag ? (e) => {
          e.preventDefault();
          const from = Number(e.dataTransfer.getData('text/plain'));
          if (Number.isInteger(from)) drag.onDrop(from);
        } : undefined,
        style: {
          opacity: dimmed ? 0.55 : 1,
          // Die Zielkarte zeigt sich beim Ziehen – ohne das rät man, wo es landet.
          outline: drag?.over ? `2px dashed ${c.fg}` : undefined,
          outlineOffset: 2,
        },
      }}
      // Der Kopf klappt auf – ohne Inhalt ist er kein Knopf.
      head={{
        role: children ? 'button' : undefined,
        tabIndex: children ? 0 : undefined,
        'aria-expanded': children ? open : undefined,
        style: { cursor: children ? 'pointer' : undefined },
        onClick: children ? () => setOpen(!open) : undefined,
        onKeyDown: children ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(!open); }
        } : undefined,
      }}
      lead={drag ? (
        <span className="flex items-center justify-center flex-none"
          style={{ width: 16, color: c.fg, opacity: 0.5, cursor: 'grab' }}
          draggable
          onClick={(e) => e.stopPropagation()}
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
      ) : undefined}
      trail={(
        <>
          {locked && (
            <Lock size={13} className="flex-none" style={{ color: 'var(--warning)' }}
              data-tip={lockReason(waiting)} />
          )}
          {children && (open
            ? <ChevronUp size={14} className="flex-none"
                style={{ color: c.fg, opacity: 0.55 }} />
            : <ChevronDown size={14} className="flex-none"
                style={{ color: c.fg, opacity: 0.55 }} />)}
          {onDelete && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="flex items-center justify-center rounded"
              style={{ width: 26, height: 26, color: 'var(--danger)' }}
              data-tip="Modul entfernen. Ändern geht nicht – eine gesetzte Definition rastet ein."
              aria-label={`${step.label} entfernen`}
            >
              <Trash2 size={14} />
            </button>
          )}
        </>
      )}
      history={history}
    >
      {children && open && (
        // Die Sperre (siehe oben): `fieldset[disabled]` schaltet alles darin ab.
        <fieldset disabled={locked}
          style={{ border: 0, padding: 0, margin: 0, minWidth: 0,
                   opacity: locked ? 0.65 : 1 }}>
          {children}
        </fieldset>
      )}
    </ModuleShell>
  );
}

function lockReason(waiting: number[]): string {
  return `Wartet auf die Rückführung aus ${waiting.length === 1 ? 'Auftrag' : 'den Aufträgen'} `
    + waiting.map(formatObjectId).join(', ');
}
