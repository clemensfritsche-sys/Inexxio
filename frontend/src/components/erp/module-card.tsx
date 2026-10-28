'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, GripVertical, Lock, Trash2, type LucideIcon } from 'lucide-react';
import { moduleIcon, moduleTone } from '@/lib/modules';
import { MODULE_CARD, MODULE_TITLE } from './module-ui';
import { formatObjectId } from '@/lib/utils';
import { DiagramStep } from '@/lib/process-graph';

/**
 * **Ein Prozessobjekt = eine Komponente.** Der Modultyp ist Konfiguration (Name,
 * Übergang, Farbe) — es gibt hier bewusst keinen Zweig je Modulart und wird auch keinen
 * geben. Die Farbe kommt aus `lib/modules.moduleTone`, gefüttert vom Backend: ein neuer
 * Modultyp ist ein Eintrag in der Registry, kein Eingriff hier.
 *
 * Prozessmodule tragen eine **eigene Farbfamilie**, getrennt von der Ampel (§5.4): sie
 * sind keine Zustände und dürfen nicht wie welche aussehen.
 */

interface DragProps {
  index: number;
  over: boolean;
  onStart: () => void;
  onEnd: () => void;
  onDrop: (from: number) => void;
}

/**
 * **Das Zeichen eines Moduls** – getöntes Quadrat mit seinem Symbol: die einzige Fläche,
 * die ein Modul färbt. Die Historie hängt nicht hier, sondern an der Kopfzeile der Karte
 * (`ModuleShell.history`, #790).
 */
export function ModuleMark({ icon: Icon, tone, bg = 'var(--bg-1)' }: {
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
 * **Die Hülle einer Modul-Karte — EIN Bauteil.** Weisse Karte (`module-ui.MODULE_CARD`),
 * Kopf mit `ModuleMark` und Beschriftung, Haarlinie vor dem Körper; der Rahmen trägt die
 * Modulfarbe, wenn das Modul dran ist. Die Anatomie, an der man eine Modul-Karte erkennt,
 * steht **einmal**.
 *
 * `lead` und `trail` sind die Stellen, an denen ein Träger Eigenes einhängt (Ziehgriff,
 * Schloss, Chevron, Löschen) – der Rahmen selbst kennt davon nichts.
 */
export function ModuleShell({ tone, icon, label, active, lead, trail, head, body,
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
   * **Die Historie hängt an der KOPFZEILE** (#790): sie läuft über die ganze Kartenbreite
   * und ist zugeklappt die Karte. Nicht am äusseren Rahmen (dort stünde die Blase beim
   * Tippen im Feldsatz) und **nie an der Beschriftung**: die trägt `truncate`
   * (`overflow: hidden`) und schnitte das `::after` weg. Was darin eine eigene Blase
   * trägt, gewinnt (`:has` in `globals.css`).
   */
  history?: string;
  children?: ReactNode;
}) {
  return (
    // **Die Karte ist weiss** wie jeder Datensatz (Struktur vor Fläche); die Modulfarbe
    // steht in der Marke und im Rahmen, wenn das Modul dran ist. `data-fb-module` nennt
    // das Modul für eine Testnotiz (`lib/feedback.originOf`).
    <div className="rounded-ds-lg" data-fb-module={label} {...body}
      style={{
        ...MODULE_CARD,
        borderColor: active ? tone.fg : 'var(--border-1)',
        ...(body?.style ?? {}),
      }}>
      <div className="flex items-center gap-3"
        // Fokussierbar, damit die Blase auch **ohne Hover** erscheint – auf dem
        // Touchgerät per Tipp, an der Tastatur per Tab. Wo der Kopf ohnehin aufklappt,
        // ist er längst fokussierbar; `head` steht darum danach und gewinnt.
        tabIndex={history ? 0 : undefined}
        {...(history ? { 'data-tip': history, 'data-tip-list': '' } : {})}
        {...head}>
        {lead}
        <ModuleMark icon={icon} tone={tone.fg} bg={tone.bg} />
        {/* **Der Name trägt die Display-Schrift des Hauses**, nicht die Modulfarbe: ein
            Titel in einer Tönung liest sich als Zustand, und der steht woanders. */}
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
  /** Startet dieses Modul aufgeklappt? Sonst zu – und der Kopf klappt es auf (#696). */
  defaultOpen?: boolean;
  onDelete?: () => void;
  drag?: DragProps;
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(!!defaultOpen);

  // ►► **Wird ein Modul zum aktiven, klappt es auf** (Testnotiz #727). ◄◄
  //
  // `defaultOpen` war ein reiner **Startwert**: wer den Auftrag öffnete, bevor die Stücke
  // ankamen, bekam `false` – und dabei blieb es. Als das Modul dann an der Reihe war,
  // blieb es zu, ohne blockiert zu sein. Genau so wurde es gemeldet.
  //
  // Der Effekt hängt an `defaultOpen` und **nur** daran: er läuft, wenn das aktive Modul
  // wechselt, nicht bei jedem Rendern. Wer selbst zuklappt, bleibt darum zugeklappt –
  // eine Entscheidung des Menschen wird nicht bei der nächsten Antwort überschrieben.
  useEffect(() => { setOpen(!!defaultOpen); }, [defaultOpen]);
  // **Die Sperre gehört hierher, nicht ins Modul** (Testnotiz #698). Ein Modul fragt
  // nicht, ob es darf – ihm wird gesagt, dass es nicht darf. `fieldset[disabled]` schaltet
  // JEDE Eingabe und JEDEN Knopf darin ab, ganz gleich, was das Modul rendert; ein
  // künftiger Einkauf oder Verkauf erbt das, ohne eine Zeile dafür zu schreiben. Der
  // Inhalt bleibt sichtbar – man will ja sehen, was drinsteht.
  const waiting = step.waitingFor ?? [];
  const locked = waiting.length > 0;
  // **Der Übergang steht nicht mehr auf der Karte.** Er gehört zum Modultyp und ist für
  // jedes Modul derselbe (Durchläufer) – ihn hinzuschreiben wäre eine Zeile, die bei
  // jeder Karte dasselbe sagt. Was die Karten unterscheidet, ist ihre **Art**, und die
  // trägt das Symbol.
  const Icon = moduleIcon(step.moduleType);
  // **Die Farbe kommt vom Schritt, nicht von einem Aufrufer.** Wer sie nicht kennt, malt
  // nicht irgendetwas: `moduleTone` meldet eine unbekannte Familie sichtbar (Warnfarbe),
  // statt sie stillschweigend zur Datenerfassung zu machen.
  const c = moduleTone(step.tone);
  return (
    // **Die Hülle ist ein eigenes Bauteil** (`ModuleShell`). Was hier dazukommt, hängt
    // in `lead`/`trail`: der Ziehgriff, das Schloss, der Chevron, das Löschen. Der
    // Rahmen kennt davon nichts.
    <ModuleShell
      tone={c} icon={Icon} label={step.label} active={active}
      body={{
        // **Gezogen wird am Griff, nicht an der Karte.** Ein `draggable` auf der Karte
        // macht ihren ganzen Inhalt zum Ziehgriff – und damit lässt sich in ihren
        // Eingabefeldern kein Text mehr markieren. Das fällt bei einem Modul kaum auf
        // und bei zwanzig sofort.
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
      // **Der Kopf klappt auf** (#696) – eine Stelle, jedes Modul. Ohne Inhalt gibt es
      // nichts aufzuklappen, dann ist er auch kein Knopf.
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
        // **Die Sperre gehört hierher, nicht ins Modul** (#698). Ein Modul fragt nicht,
        // ob es darf – ihm wird gesagt, dass es nicht darf. `fieldset[disabled]` schaltet
        // JEDE Eingabe und JEDEN Knopf darin ab, ganz gleich, was das Modul rendert.
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
