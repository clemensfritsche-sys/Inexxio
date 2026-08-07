'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { ModuleCatalog } from '@/types';
import {
  CAPTURE_ICON, MODULE_ICON, NEEDS_TARGET,
  type ModuleDraft, type PointDraft,
} from '@/lib/modules';
import { Card, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';

/**
 * **Ein Modul anlegen — dieselbe Komponente am Artikel wie im Auftrag.**
 *
 * Beide Orte definieren denselben Prozess (PROCESS_CORE.md §8): am Artikel als Vorlage,
 * im Auftrag als das, was gleich läuft. Zwei Editoren dafür wären zwei Stände, und sie
 * liefen garantiert auseinander.
 *
 * **Kein Status-Feld.** Der Übergang gehört zum Modultyp und steht im Backend
 * (`domain/modules.py`) — die Datenerfassung ist ein Durchläufer. Zwei Auswahlen hätten
 * dem Anwender eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand.
 *
 * Bewusst ein «Hinzufügen»-Knopf statt Auto-Save: ein halb konfiguriertes Modul ist genau
 * das, was die Pflichtangaben verhindern sollen.
 */
export function AddModule({ onAdd, disabled }: {
  onAdd: (m: Omit<ModuleDraft, 'id'>) => void;
  disabled?: boolean;
}) {
  const [catalog, setCatalog] = useState<ModuleCatalog | null>(null);
  const [type, setType] = useState<string>('');
  const [name, setName] = useState('');
  const [points, setPoints] = useState<PointDraft[]>([]);

  useEffect(() => {
    let dead = false;
    api.getModuleCatalog()
      .then((c) => {
        if (dead) return;
        setCatalog(c);
        setType((t) => t || c.modules?.[0]?.key || '');
      })
      .catch(() => { /* der Katalog ist Auswahlhilfe – ohne ihn bleibt der Knopf aus */ });
    return () => { dead = true; };
  }, []);

  const captureTypes = catalog?.capture_types ?? [];
  const defaultType = captureTypes[0]?.key ?? 'text';

  function addPoint() {
    setPoints((p) => [...p, { label: '', type: defaultType, required: true, target: '', tolerance: '' }]);
  }
  function setPoint(i: number, patch: Partial<PointDraft>) {
    setPoints((p) => p.map((row, n) => (n === i ? { ...row, ...patch } : row)));
  }

  // Warum «Hinzufügen» (noch) nicht geht – im Klartext, nicht als stummes Grau.
  const blocked =
    !type ? 'Erst einen Modultyp wählen.'
      : !name.trim() ? 'Ein Modul braucht einen Namen.'
        : points.length === 0 ? 'Mindestens ein Erfassungspunkt – sonst gibt es nichts zu erfassen.'
          : points.some((p) => !p.label.trim()) ? 'Jeder Erfassungspunkt braucht eine Bezeichnung.'
            : points.some((p) => p.type === NEEDS_TARGET && !String(p.target ?? '').trim())
              ? 'Ein Soll-Ist-Vergleich braucht einen Sollwert.'
              : null;

  const ModIcon = MODULE_ICON[type] ?? Plus;

  return (
    <Card icon={ModIcon} title="Prozessschrittmodul hinzufügen">
      <div className="flex flex-wrap gap-2 items-end">
        <label>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Modul</span>
          <select className={inputCls} style={{ width: 170 }} value={type} disabled={disabled}
            onChange={(e) => setType(e.target.value)}>
            {(catalog?.modules ?? []).map((m) => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </label>
        <label className="flex-1 min-w-[160px]">
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Name</span>
          <input className={inputCls} value={name} maxLength={120} disabled={disabled}
            onChange={(e) => setName(e.target.value)} placeholder="z. B. Endkontrolle" />
        </label>
      </div>

      {/* Was erfasst bzw. kontrolliert wird. */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>Erfassungspunkte</span>
          <button type="button" className="erp-actbtn" style={{ height: 26, padding: '0 10px' }}
            disabled={disabled} onClick={addPoint}>
            <Plus size={13} /> Punkt
          </button>
        </div>
        {points.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--fg-4)' }}>
            Noch kein Punkt. Ein Modul ohne Erfassungspunkt stünde im Prozess und hätte
            nichts zu tun.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {points.map((p, i) => (
              <PointRow
                key={i}
                point={p}
                types={captureTypes}
                disabled={disabled}
                onChange={(patch) => setPoint(i, patch)}
                onRemove={() => setPoints((rows) => rows.filter((_, n) => n !== i))}
              />
            ))}
          </div>
        )}
      </div>

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          className="erp-actbtn erp-actbtn-primary"
          style={{ height: 32, padding: '0 14px' }}
          disabled={disabled || blocked !== null}
          data-tip={blocked ?? undefined}
          // Der Tooltip läuft über CSS-generierten Inhalt (`content: attr(data-tip)`), und
          // den zählt Chromium in den Accessible Name. Ohne festes Label hiesse der Knopf
          // je nach Zustand anders – für Screenreader wie für jede Automatisierung.
          aria-label="Modul hinzufügen"
          onClick={() => {
            onAdd({ moduleType: type, name: name.trim(), points });
            setName(''); setPoints([]);
          }}
        >
          Hinzufügen
        </button>
      </div>
    </Card>
  );
}

/** Ein Erfassungspunkt: Bezeichnung · Typ · Pflicht (+ Soll/Toleranz beim Vergleich). */
function PointRow({ point, types, disabled, onChange, onRemove }: {
  point: PointDraft;
  types: { key: string; label: string }[];
  disabled?: boolean;
  onChange: (patch: Partial<PointDraft>) => void;
  onRemove: () => void;
}) {
  const Icon = CAPTURE_ICON[point.type];
  return (
    <div className="flex flex-wrap gap-1.5 items-center rounded-ds-md"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 8 }}>
      <span className="flex items-center justify-center rounded flex-none"
        style={{ width: 26, height: 26, background: 'var(--bg-2)', color: 'var(--fg-2)' }}>
        {Icon ? <Icon size={14} /> : null}
      </span>
      <input className={inputCls} style={{ flex: 1, minWidth: 130 }} value={point.label}
        maxLength={120} disabled={disabled} placeholder="Bezeichnung, z. B. Gratfrei"
        onChange={(e) => onChange({ label: e.target.value })} />
      <select className={inputCls} style={{ width: 160 }} value={point.type} disabled={disabled}
        onChange={(e) => onChange({ type: e.target.value })}>
        {types.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
      </select>
      {point.type === NEEDS_TARGET && (
        <>
          <input className={inputCls} style={{ width: 84 }} value={point.target ?? ''}
            {...numericInputProps} disabled={disabled} placeholder="Soll"
            onChange={(e) => onChange({ target: numericOnly(e.target.value, { decimals: true }) })} />
          <input className={inputCls} style={{ width: 84 }} value={point.tolerance ?? ''}
            {...numericInputProps} disabled={disabled} placeholder="± Tol."
            onChange={(e) => onChange({ tolerance: numericOnly(e.target.value, { decimals: true }) })} />
        </>
      )}
      <label className="flex items-center gap-1 text-xs" style={{ color: 'var(--fg-3)' }}
        data-tip="Pflicht: ohne diesen Wert lässt sich der Schritt nicht bestätigen.">
        <input type="checkbox" className="w-4 h-4 accent-[var(--inexxio)]" disabled={disabled}
          checked={point.required} onChange={(e) => onChange({ required: e.target.checked })} />
        Pflicht
      </label>
      <button type="button" onClick={onRemove} disabled={disabled}
        className="flex items-center justify-center rounded flex-none"
        style={{ width: 26, height: 26, color: 'var(--danger)' }}
        aria-label="Erfassungspunkt entfernen">
        <Trash2 size={14} />
      </button>
    </div>
  );
}
