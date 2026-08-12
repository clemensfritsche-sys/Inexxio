'use client';

import { useEffect, useState } from 'react';
import { Columns2, Grid2x2, Layers, Lock, Percent, Trash2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { ModuleCatalog } from '@/types';
import {
  CAPTURE_ICON, DISPOSAL_MODES, MODULE_ICON, NEEDS_TARGET, SAMPLE_PRESETS, blankModule,
  moduleTone,
  type DisposalMode, type ModuleDraft, type PointDraft, type SampleDraft, type SampleMode,
} from '@/lib/modules';

/** Symbol je Kurzweg. Die Wörter stehen daneben – ein Anteil hat kein Bild (#636). */
const SAMPLE_ICON: Record<SampleMode, LucideIcon> = {
  all: Layers, half: Columns2, quarter: Grid2x2, free: Percent,
};
import {
  DRAFT_OBJECT_ID, definitionGraph, type DiagramStep,
} from '@/components/erp/process-diagram';
import { ProcessColumns } from '@/components/erp/process-columns';
import { END_BEFORE } from '@/lib/process-status';
import type { RelatedOrder } from '@/types';
import { IconSwitch, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';

/**
 * **Den Prozess definieren — dieselbe Komponente am Artikel wie im Auftrag.**
 *
 * Beide Orte definieren denselben Prozess (PROCESS_CORE.md §8): am Artikel als Vorlage,
 * im Auftrag als das, was gleich läuft. Zwei Editoren dafür wären zwei Stände, und sie
 * liefen garantiert auseinander.
 *
 * **Kein «Hinzufügen»-Knopf und kein Bearbeiten-Modus.** Ein Klick auf die Palette legt
 * das Modul an; es steht ab dem ersten Moment im Fluss und füllt sich, während man tippt
 * (Autosave). Vollständig ist es, wenn seine Pflichtangaben stehen – bis dahin sagt die
 * Karte, was fehlt, und die Freigabe verweigert. Ändern heisst löschen und neu anlegen;
 * dafür gibt es den Mülleimer, keinen zweiten Weg.
 *
 * **Nach der Freigabe ist die Struktur eingefroren** (`frozen`): keine Palette, kein
 * Mülleimer, kein Ziehen. Das ist keine bewachte Regel, sondern ein fehlendes Bedienelement –
 * einen Endpunkt, der eine freigegebene Definition ändert, gibt es ohnehin nicht.
 */
export function ProcessDesigner({ modules, onChange, frozen, readOnlySteps, head,
  parents, onToggleReturn }: {
  modules: ModuleDraft[];
  onChange: (m: ModuleDraft[]) => void;
  frozen?: boolean;
  /** Eingefrorener Stand (freigegebener Artikel/Auftrag) – dann wird nur gezeigt. */
  readOnlySteps?: DiagramStep[];
  /** Slot über dem Start – beim Auftrag die Definition der Einzelinstanzen. Der Artikel
   *  hat keine, und ein Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar. */
  head?: React.ReactNode;
  /**
   * **Die Quell-Aufträge des Entwurfs** (Auftrag §2) – vom Server vorausberechnet, mit
   * der Abzweigung, die entstehen würde. Ein Artikel hat keine; dann steht hier nur der
   * Prozess, wie bisher.
   */
  parents?: RelatedOrder[];
  /** Ein Klick auf den Quell-Auftrag schaltet seine Rückführung an und aus (§5). */
  onToggleReturn?: (parentObjectId: number) => void;
}) {
  const [catalog, setCatalog] = useState<ModuleCatalog | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  // **Das zuletzt angelegte Modul startet aufgeklappt** (#696): es ist das, woran gerade
  // gearbeitet wird – die Entsprechung zum «aktiven» Modul im laufenden Auftrag. Alle
  // übrigen sind zu; ihr Kopf klappt sie auf.
  const [justAdded, setJustAdded] = useState<number | null>(null);

  useEffect(() => {
    if (frozen) return;
    let dead = false;
    api.getModuleCatalog()
      .then((c) => { if (!dead) setCatalog(c); })
      .catch(() => { /* ohne Katalog bleibt die Palette leer – kein erfundener Typ */ });
    return () => { dead = true; };
  }, [frozen]);

  // **Was ein Modul ist, sagt sein Typ** – im Entwurf über den Katalog, gespeichert über
  // die Antwort des Servers. Beides dieselbe Registry, nur zwei Wege dorthin; **beide**
  // bringen Beschriftung, Farbfamilie und «Ausgang?» mit, damit keine Ansicht sie
  // nachschlagen muss und keine sie vergessen kann.
  const steps: DiagramStep[] = readOnlySteps
    ?? modules.map((m) => {
      const type = catalog?.modules?.find((x) => x.key === m.moduleType);
      return {
        id: m.id,
        moduleType: m.moduleType,
        label: type?.label ?? m.moduleType,
        tone: type?.tone ?? null,
        terminal: !!type?.terminal,
      };
    });

  function add(moduleType: string) {
    const id = (modules[modules.length - 1]?.id ?? 0) + 1;
    setJustAdded(id);
    onChange([...modules, blankModule(id, moduleType)]);
  }
  function patch(id: number, next: Partial<ModuleDraft>) {
    onChange(modules.map((m) => (m.id === id ? { ...m, ...next } : m)));
  }

  /** Ein Modul an eine andere Stelle ziehen. Die Reihenfolge IST der Prozess. */
  function move(from: number, to: number) {
    if (from === to) return;
    const next = [...modules];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    onChange(next);
  }

  return (
    <ProcessColumns
      mid={{
        objectId: DRAFT_OBJECT_ID,
        // **Der Graph eines Entwurfs ist seine Definition** – hier steht keine
        // Prozesslogik, sondern die Liste, die daneben bearbeitet wird.
        graph: definitionGraph(steps),
        steps,
        mode: 'definition',
        expandedStepId: justAdded,
        endStatus: END_BEFORE,
        head,
        onDelete: frozen ? undefined : (id) => onChange(modules.filter((m) => m.id !== id)),
        onReorder: frozen ? undefined : move,
        dragging: drag,
        onDragState: setDrag,
        renderStep: frozen ? undefined : (step) => {
          const m = modules.find((x) => x.id === step.id);
          if (!m) return null;
          // **Welche Felder ein Modul hat, sagt sein Typ** – die Zuordnung steht hier,
          // nicht als Bedingung im Rumpf. Ein neuer Typ ist ein Eintrag, kein Eingriff.
          const Fields = MODULE_FIELDS[m.moduleType];
          return Fields ? <Fields module={m} types={catalog?.capture_types ?? []}
            onChange={(next) => patch(m.id, next)} /> : (
            <p className="text-xs" style={{ color: 'var(--danger)' }}>
              Modultyp «{m.moduleType}» ist dieser Oberfläche unbekannt.
            </p>
          );
        },
        // ►► **Hinter einem Ausgang gibt es nichts mehr anzubieten.** ◄◄
        //
        // Dieselbe Eigenschaft (`Module.terminal`), aus der die Freigabe ihren Fehler
        // zieht und das Bild sein Ende: was an einem terminalen Modul ankommt, verlässt
        // den Auftrag – ein Modul dahinter bekäme nie eine Einzelinstanz. Es hier gar
        // nicht erst anzubieten ist die freundlichere Hälfte derselben Regel; die
        // Prüfung bei der Freigabe bleibt das Netz (eine fehlende Schaltfläche ist keine
        // Absicherung, sondern eine Bitte).
        tail: frozen || steps.some((s) => s.terminal)
          ? undefined
          : <Palette catalog={catalog} onPick={add} />,
      }}
      parents={parents}
      onToggleReturn={onToggleReturn}
    />
  );
}

/**
 * **Die Modulauswahl — dort, wo das nächste Modul hinkäme.**
 *
 * Ein Symbol je Modultyp, in seiner Farbe; der Name klappt beim Hovern daneben auf.
 * Dieselbe Interaktion wie die Mengeneinheit am Artikel (`IconSwitch labelActiveOnly`):
 * man sieht die Auswahl auf einen Blick, ohne dass Wörter um Aufmerksamkeit ringen –
 * nur ist dies keine Wahl zwischen Werten, sondern ein Griff in den Baukasten.
 */
function Palette({ catalog, onPick }: {
  catalog: ModuleCatalog | null; onPick: (key: string) => void;
}) {
  const mods = catalog?.modules ?? [];
  if (!mods.length) return null;
  return (
    <div className="flex flex-wrap justify-center gap-1.5">
      {mods.map((m) => {
        const Icon = MODULE_ICON[m.key] ?? CAPTURE_ICON.text;
        const tone = moduleTone(m.tone);
        return (
          <button
            key={m.key}
            type="button"
            className="ix-palette"
            style={{ background: tone.bg, color: tone.fg, borderColor: tone.border }}
            aria-label={`${m.label} hinzufügen`}
            onClick={() => onPick(m.key)}
          >
            <Icon size={17} />
            <span className="ix-palette-name">{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * **Aussondern — eine Entscheidung, sonst nichts.**
 *
 * Verschrotten und Sperren tun dasselbe: das Stück verlässt den Auftrag. Der einzige
 * Unterschied ist, **ob es einen Weg zurück gibt** – und genau das steht hier. Es ist
 * kein Status-Dropdown: der Anwender wählt, was passieren soll, den Zustand leitet das
 * Modul ab (`Aussondern.status_after_for`).
 *
 * Keine Erfassungspunkte, keine Stichprobe: was ankommt, wird ausgesondert.
 *
 * **Der Grund gehört hierher, nicht ans Band.** Warum an dieser Stelle ausgesondert wird,
 * ist eine Eigenschaft des Ablaufs und lautet bei jedem Stück gleich – am Band wäre es
 * ein Feld, das immer dasselbe aufnimmt. Ohne ihn lässt sich das Modul nicht anlegen
 * (`Aussondern.clean_config`); die Meldung hier ist die Bedienung, die Regel steht dort.
 */
function DisposalFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <IconSwitch
        value={m.mode}
        onChange={(mode: DisposalMode) => onChange({ mode })}
        options={DISPOSAL_MODES.map((o) => ({
          value: o.value, icon: o.value === 'scrap' ? Trash2 : Lock,
          label: o.label, hint: o.hint,
        }))}
      />
      <input className={inputCls} value={m.reason} maxLength={200}
        placeholder="Grund, z. B. Ausschuss aus der Sichtprüfung"
        aria-label="Grund der Aussonderung"
        onChange={(e) => onChange({ reason: e.target.value })} />
    </div>
  );
}

/** Welcher Feldsatz gehört zu welchem Modultyp. Eine Zuordnung, keine Bedingung. */
const MODULE_FIELDS: Record<string, React.ComponentType<{
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}>> = {
  datenerfassung: ModuleFields,
  aussondern: DisposalFields,
};

/**
 * **Die Stichprobe — eine Zeile, keine Maske.**
 *
 * Drei Formen und **eine** Zahl: alle (Vorgabe) · Anzahl · Prozent. Mehr braucht die
 * Frage nicht, und ein Formular mit fünf Feldern wäre die falsche Antwort auf etwas,
 * das sich in einem Satz stellen lässt.
 *
 * **Die Wörter stehen ausgeschrieben da.** Ein Anteil hat kein Bild, das man ohne
 * Vorwissen liest – ein Symbol, das man raten muss, ist keines (Testnotizen #618/#636).
 *
 * **«je Instanz» ist keine Beschriftungs-Kosmetik, sondern die Regel**: eine Stichprobe
 * wird aus einem Los gezogen (ISO 2859-1), und das Los ist die Instanz. «10 %» heisst
 * 10 % **aus jeder** Charge, nicht 10 % aus dem Haufen; sonst bliebe eine ganze Charge
 * womöglich ungeprüft.
 */
function SampleRow({ value, onChange }: {
  value: SampleDraft; onChange: (next: SampleDraft) => void;
}) {
  return (
    // **Die Beschriftung steht ÜBER den Knöpfen**, nicht neben ihnen: daneben stand sie
    // auf gleicher Höhe wie die Auswahl und las sich wie deren erste Option.
    <div className="flex flex-col gap-1">
      <span style={{
        font: '700 11px var(--font-body)', textTransform: 'uppercase',
        letterSpacing: '.07em', color: 'var(--fg-4)',
      }}>Stichprobe</span>
      <div className="flex flex-wrap items-center gap-2">
        <IconSwitch
          value={value.mode}
          onChange={(mode: SampleMode) => onChange({ mode, value: mode === 'free' ? value.value : '' })}
          options={SAMPLE_PRESETS.map((p) => ({
            value: p.value,
            icon: SAMPLE_ICON[p.value],
            label: p.label,
            hint: p.percent
              ? `${p.percent} % aller wartenden Einzelinstanzen`
              : 'Ein frei gewählter Anteil, aufgerundet',
          }))}
        />
        {value.mode === 'free' && (
          <>
            <input className={inputCls} style={{ width: 80 }} value={value.value}
              {...numericInputProps} placeholder="z. B. 10"
              onChange={(e) => onChange({ ...value, value: numericOnly(e.target.value) })} />
            <span className="text-xs" style={{ color: 'var(--fg-4)' }}>%</span>
          </>
        )}
      </div>
    </div>
  );
}

/** Die Art eines Erfassungspunktes – Symbol mit dem Namen im Hover. */
function PointIcon({ type, types }: { type: string; types: { key: string; label: string }[] }) {
  const Icon = CAPTURE_ICON[type] ?? CAPTURE_ICON.text;
  return (
    <span className="flex items-center justify-center flex-none rounded"
      style={{ width: 26, height: 26, color: 'var(--fg-3)' }}
      data-tip={types.find((t) => t.key === type)?.label ?? type}>
      <Icon size={14} />
    </span>
  );
}

/**
 * Der Inhalt eines Moduls im Entwurf: seine Erfassungspunkte.
 *
 * Es gibt **kein** «Pflicht ja/nein» mehr: alles, was angelegt ist, ist Pflicht. Ein
 * Schalter dafür wäre die Frage, warum man einen Erfassungspunkt anlegt, den niemand
 * ausfüllen muss – und jeder ausgeschaltete Punkt eine Lücke, die erst später auffällt.
 */
function ModuleFields({ module: m, types, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const defaultType = types[0]?.key ?? 'text';
  function setPoint(i: number, p: Partial<PointDraft>) {
    onChange({ points: m.points.map((row, n) => (n === i ? { ...row, ...p } : row)) });
  }

  return (
    <div className="flex flex-col gap-2">
      <SampleRow value={m.sample} onChange={(sample) => onChange({ sample })} />

      <div className="flex flex-col gap-1.5">
        {m.points.map((p, i) => (
          <div key={i} className="flex flex-wrap gap-1.5 items-center">
            {/* **Die Art ist das Symbol der Zeile, kein Feld** (Testnotiz #683). Gewählt
                wird sie unten mit der Palette – ein Auswahlfeld daneben wäre der zweite
                Weg zur selben Entscheidung. Umentscheiden heisst löschen und neu
                anlegen, wie beim Modul selbst. */}
            <PointIcon type={p.type} types={types} />
            <input className={inputCls} style={{ flex: 1, minWidth: 120 }} value={p.label}
              maxLength={120} placeholder="Erfassungspunkt, z. B. Gratfrei"
              onChange={(e) => setPoint(i, { label: e.target.value })} />
            {p.type === NEEDS_TARGET && (
              <>
                <input className={inputCls} style={{ width: 76 }} value={p.target ?? ''}
                  {...numericInputProps} placeholder="Soll"
                  onChange={(e) => setPoint(i, { target: numericOnly(e.target.value, { decimals: true }) })} />
                <input className={inputCls} style={{ width: 76 }} value={p.tolerance ?? ''}
                  {...numericInputProps} placeholder="± Tol."
                  onChange={(e) => setPoint(i, { tolerance: numericOnly(e.target.value, { decimals: true }) })} />
                {/* **Worin gemessen wird** – ein freies, kurzes Wort (Testnotiz #707).
                    Bewusst keine Liste: die Mengeneinheiten des Artikels beantworten
                    eine andere Frage («worin wird die Menge geführt») und kennen weder
                    °C noch bar; eine zweite Liste wäre endlos, und das System rechnet
                    nie mit der Einheit – es zeigt sie an. */}
                <input className={inputCls} style={{ width: 62 }} value={p.unit ?? ''}
                  maxLength={8} placeholder="Einheit" data-tip="mm · kg · °C …"
                  onChange={(e) => setPoint(i, { unit: e.target.value })} />
              </>
            )}
            <button type="button" aria-label="Erfassungspunkt entfernen"
              className="flex items-center justify-center rounded flex-none"
              style={{ width: 26, height: 26, color: 'var(--danger)' }}
              onClick={() => onChange({ points: m.points.filter((_, n) => n !== i) })}>
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {/* Ein Symbol je Erfassungstyp – dieselbe Geste wie die Modulauswahl, eine Ebene
          tiefer. Klick legt den Punkt an; ausgefüllt wird er dort, wo er steht. */}
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => {
          const Icon = CAPTURE_ICON[t.key] ?? CAPTURE_ICON.text;
          return (
            <button key={t.key} type="button" className="ix-palette ix-palette-sm"
              aria-label={`${t.label} hinzufügen`}
              onClick={() => onChange({
                points: [...m.points, { label: '', type: t.key || defaultType, target: '',
                                        tolerance: '', unit: '' }],
              })}>
              <Icon size={14} />
              <span className="ix-palette-name">{t.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
