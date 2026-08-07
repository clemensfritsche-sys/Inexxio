'use client';

import { useMemo, useState } from 'react';
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react';
import type { CapturePoint } from '@/types';
import { CAPTURE_ICON, NEEDS_TARGET } from '@/lib/modules';
import { PhotoCapture } from '@/components/erp/photo-capture';
import { SignaturePad } from '@/components/erp/signature-pad';
import { inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';

/**
 * **Die Datenerfassung zur Laufzeit** — was das Modul festhält, bevor die Stücke vorrücken.
 *
 * Erfasst wird **einmal für alle**, die gerade vor dem Modul stehen (getroffene Annahme,
 * siehe PROCESS_CORE §13 – die Alternative «je Stück ein eigener Satz» ist die offene
 * Frage an den Nutzer). Gespeichert wird trotzdem **je Einzelinstanz**: die Zeile hängt am
 * Stück, damit sie in dessen Historie steht.
 *
 * **Jeder offene Punkt blockiert – mit Grund.** «Bestätigen nicht möglich» ohne zu sagen,
 * was fehlt, wäre eine Sackgasse mit Ausrufezeichen. Alles, was angelegt ist, ist Pflicht;
 * einen Schalter dafür gibt es nicht mehr. Der Server prüft dasselbe noch einmal – ein
 * deaktivierter Knopf ist keine Absicherung.
 */
export function CaptureForm({ points, count, busy, onConfirm, onDirty }: {
  points: CapturePoint[];
  /** Wie viele Stücke stehen davor – die Erfassung gilt für sie alle. */
  count: number;
  busy?: boolean;
  onConfirm: (values: Record<string, unknown>) => void;
  /**
   * ►►► Zur offenen Frage (Abweichungsauftrag §5) ◄◄◄ – meldet, dass hier **begonnen**
   * wurde zu erfassen. Serverseitig gibt es diesen Zustand nicht: was nicht bestätigt
   * ist, existiert nirgends. Genau deshalb kann ihn nur dieses Fenster kennen – und
   * genau deshalb ist die Sperre hier eine Vorsichtsmassnahme, keine Regel.
   */
  onDirty?: (dirty: boolean) => void;
}) {
  const [values, setValues] = useState<Record<string, unknown>>({});

  // **Alles, was angelegt ist, ist Pflicht** – es gibt keine optionalen Punkte mehr.
  const open = useMemo(
    () => points.filter((p) => isMissing(p, values[p.key])).map((p) => p.label),
    [points, values],
  );

  return (
    <div className="flex flex-col gap-2.5">
      {points.map((p) => (
        <PointInput key={p.key} point={p} value={values[p.key]} disabled={busy}
          onChange={(v) => {
            // Die Meldung steht **neben** dem Setzen, nicht darin: der Updater von
            // `setValues` kann mehrfach laufen (StrictMode) und darf keine Wirkung
            // nach aussen haben.
            onDirty?.(true);
            setValues((s) => ({ ...s, [p.key]: v }));
          }} />
      ))}

      <button
        type="button"
        className="erp-actbtn erp-actbtn-primary w-full"
        style={{ height: 38 }}
        disabled={busy || open.length > 0}
        data-tip={open.length ? `Noch nicht erfasst: ${open.join(', ')}` : undefined}
        // Fester Name: der Tooltip ist CSS-generierter Inhalt und zählt sonst in den
        // Accessible Name – der Knopf hiesse je nach offenem Punkt anders.
        aria-label="Erfassen und bestätigen"
        onClick={() => { onDirty?.(false); onConfirm(values); }}
      >
        <Check size={15} />
        Erfassen &amp; bestätigen{count > 1 ? ` (${count} Stück)` : ''}
      </button>
      {open.length > 0 && (
        <p className="text-xs" style={{ color: 'var(--fg-3)' }}>
          Noch nicht erfasst: {open.join(', ')}
        </p>
      )}
    </div>
  );
}

/**
 * Ist dieser Punkt (noch) nicht erfasst?
 *
 * Spiegel von `CaptureType.missing` im Backend – bewusst knapp gehalten: die Regel wird
 * dort entschieden, hier geht es nur darum, den Knopf nicht anzubieten, wenn er ohnehin
 * abgewiesen würde.
 */
function isMissing(point: CapturePoint, value: unknown): boolean {
  if (point.type === 'bool') return value !== true && value !== false;
  if (point.type === NEEDS_TARGET) return value === undefined || value === null || value === '';
  return value === undefined || value === null || value === '';
}

function PointInput({ point, value, disabled, onChange }: {
  point: CapturePoint;
  value: unknown;
  disabled?: boolean;
  onChange: (v: unknown) => void;
}) {
  const Icon = CAPTURE_ICON[point.type];
  const soll = point.type === NEEDS_TARGET && point.target != null
    ? `Soll ${point.target}${point.tolerance ? ` ± ${point.tolerance}` : ''}`
    : null;

  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--fg-2)' }}>
        {Icon && <Icon size={13} style={{ color: 'var(--fg-3)' }} />}
        {point.label}
        {soll && <span className="font-normal" style={{ color: 'var(--fg-3)' }}>{soll}</span>}
      </span>

      {point.type === 'bool' ? (
        // Daumen hoch / Daumen runter. Nicht angetippt ist **nicht** dasselbe wie «nein» –
        // sonst zählte ein übersehener Pflichtpunkt als bewusstes «schlecht».
        <span className="flex gap-1.5">
          <ThumbChoice label="Gut" active={value === true} tone="var(--success)" disabled={disabled}
            onClick={() => onChange(true)}><ThumbsUp size={15} /></ThumbChoice>
          <ThumbChoice label="Schlecht" active={value === false} tone="var(--danger)" disabled={disabled}
            onClick={() => onChange(false)}><ThumbsDown size={15} /></ThumbChoice>
        </span>
      ) : point.type === 'photo' ? (
        <PhotoCapture value={asList(value)} disabled={disabled} max={4}
          onChange={(urls) => onChange(urls.length ? urls : '')} />
      ) : point.type === 'signature' ? (
        <SignaturePad value={typeof value === 'string' && value ? value : null}
          disabled={disabled} onChange={(url) => onChange(url ?? '')} />
      ) : (
        <input
          className={inputCls}
          disabled={disabled}
          {...(point.type === NEEDS_TARGET ? numericInputProps : {})}
          value={value == null ? '' : String(value)}
          onChange={(e) => onChange(
            point.type === NEEDS_TARGET
              ? numericOnly(e.target.value, { decimals: true })
              : e.target.value,
          )}
        />
      )}
    </label>
  );
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value as string[];
  return typeof value === 'string' && value ? [value] : [];
}

/** Daumen hoch/runter – **ein Symbol trägt seinen Namen** (Hover + Screenreader). */
function ThumbChoice({ label, active, tone, disabled, onClick, children }: {
  label: string; active: boolean; tone: string; disabled?: boolean;
  onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      aria-label={label} data-tip={label}
      className="flex items-center justify-center rounded-ds-md"
      style={{
        width: 44, height: 34,
        border: `1px solid ${active ? tone : 'var(--border-2)'}`,
        background: active ? `${tone}1A` : '#fff',
        color: active ? tone : 'var(--fg-4)',
      }}>
      {children}
    </button>
  );
}
