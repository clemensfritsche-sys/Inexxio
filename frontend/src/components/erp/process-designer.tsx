'use client';

import { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { ModuleCatalog } from '@/types';
import {
  CAPTURE_ICON, MODULE_ICON, NEEDS_TARGET, moduleTone,
  type ModuleDraft, type PointDraft,
} from '@/lib/modules';
import { ProcessDiagram, type DiagramStep } from '@/components/erp/process-diagram';
import { END_BEFORE } from '@/lib/process-status';
import { inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';

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
export function ProcessDesigner({ modules, onChange, frozen, readOnlySteps, head }: {
  modules: ModuleDraft[];
  onChange: (m: ModuleDraft[]) => void;
  frozen?: boolean;
  /** Eingefrorener Stand (freigegebener Artikel/Auftrag) – dann wird nur gezeigt. */
  readOnlySteps?: DiagramStep[];
  /** Slot über dem Start – beim Auftrag die Definition der Einzelinstanzen. Der Artikel
   *  hat keine, und ein Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar. */
  head?: React.ReactNode;
}) {
  const [catalog, setCatalog] = useState<ModuleCatalog | null>(null);
  const [drag, setDrag] = useState<number | null>(null);

  useEffect(() => {
    if (frozen) return;
    let dead = false;
    api.getModuleCatalog()
      .then((c) => { if (!dead) setCatalog(c); })
      .catch(() => { /* ohne Katalog bleibt die Palette leer – kein erfundener Typ */ });
    return () => { dead = true; };
  }, [frozen]);

  const steps: DiagramStep[] = readOnlySteps
    ?? modules.map((m) => ({ id: m.id, name: m.name, moduleType: m.moduleType }));

  function add(moduleType: string) {
    const id = (modules[modules.length - 1]?.id ?? 0) + 1;
    onChange([...modules, { id, moduleType, name: '', points: [] }]);
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
    <ProcessDiagram
      mode="definition"
      steps={steps}
      endStatus={END_BEFORE}
      head={head}
      tone={(t) => moduleTone(catalog?.modules?.find((m) => m.key === t)?.tone)}
      onDelete={frozen ? undefined : (id) => onChange(modules.filter((m) => m.id !== id))}
      onReorder={frozen ? undefined : move}
      dragging={drag}
      onDragState={setDrag}
      renderStep={frozen ? undefined : (step) => {
        const m = modules.find((x) => x.id === step.id);
        return m ? <ModuleFields module={m} types={catalog?.capture_types ?? []}
          onChange={(next) => patch(m.id, next)} /> : null;
      }}
      tail={frozen ? undefined : (
        <Palette catalog={catalog} onPick={add} />
      )}
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
 * Der Inhalt eines Moduls im Entwurf: Name und Erfassungspunkte.
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
      <input
        className={inputCls}
        value={m.name}
        maxLength={120}
        placeholder="Name des Moduls, z. B. Endkontrolle"
        onChange={(e) => onChange({ name: e.target.value })}
      />

      <div className="flex flex-col gap-1.5">
        {m.points.map((p, i) => (
          <div key={i} className="flex flex-wrap gap-1.5 items-center">
            <input className={inputCls} style={{ flex: 1, minWidth: 120 }} value={p.label}
              maxLength={120} placeholder="Erfassungspunkt, z. B. Gratfrei"
              onChange={(e) => setPoint(i, { label: e.target.value })} />
            <select className={inputCls} style={{ width: 150 }} value={p.type}
              onChange={(e) => setPoint(i, { type: e.target.value })}>
              {types.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
            {p.type === NEEDS_TARGET && (
              <>
                <input className={inputCls} style={{ width: 76 }} value={p.target ?? ''}
                  {...numericInputProps} placeholder="Soll"
                  onChange={(e) => setPoint(i, { target: numericOnly(e.target.value, { decimals: true }) })} />
                <input className={inputCls} style={{ width: 76 }} value={p.tolerance ?? ''}
                  {...numericInputProps} placeholder="± Tol."
                  onChange={(e) => setPoint(i, { tolerance: numericOnly(e.target.value, { decimals: true }) })} />
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
                points: [...m.points, { label: '', type: t.key || defaultType, target: '', tolerance: '' }],
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
