'use client';

import { useMemo, useState } from 'react';
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react';
import type { CapturePoint } from '@/types';
import { CAPTURE_ICON, NEEDS_TARGET } from '@/lib/modules';
import { lookup } from '@/lib/vocab';
import { PhotoShot } from '@/components/erp/photo-capture';
import { SignaturePad } from '@/components/erp/signature-pad';
import { inputCls, numericInputProps, numericOnly } from '@/components/erp/controls';
import { Input } from '@/components/form/field';
import { Skeleton } from './skeleton';

/**
 * **Die Datenerfassung zur Laufzeit** — was das Modul festhält, bevor die Stücke vorrücken.
 *
 * ►►► **Der Scan gilt der Instanz, die Erfassung der Einzelinstanz** ◄◄◄ (PROCESS_CORE
 * §4.4/§9.3): ein Scan, je gezogenem Stück ein eigener Wertesatz.
 *
 * **Jeder offene Punkt blockiert – mit Grund**; alles Angelegte ist Pflicht, der Server
 * prüft dasselbe noch einmal.
 */
export function CaptureForm({ points, numbers, action, busy, onConfirm, onDirty }: {
  points: CapturePoint[];
  /** **Das Verb des Moduls** (`ProcessStepResponse.action`) – vom Server. */
  action: string;
  /**
   * Die Nummern der **gezogenen** Einzelinstanzen – je eine ein eigener Wertesatz.
   * `null` heisst «noch am Laden»; leer heisst «dieses Modul erfasst nichts» (dann ist
   * der Scan die Bestätigung).
   */
  numbers: string[] | null;
  busy?: boolean;
  onConfirm: (values: Record<string, Record<string, unknown>>) => void;
  /**
   * ►►► Zur offenen Frage (Abweichungsauftrag §5) ◄◄◄ – meldet, dass hier **begonnen** wurde
   * zu erfassen; nur dieses Fenster kennt das (eine Vorsichtsmassnahme, keine Regel).
   */
  onDirty?: (dirty: boolean) => void;
}) {
  const [byUnit, setByUnit] = useState<Record<string, Record<string, unknown>>>({});

  // Pflicht an **jedem** gezogenen Stück; gezählt werden die offenen Stücke, nicht die Punkte.
  const open = useMemo(
    () => (numbers ?? []).filter(
      (n) => points.some((p) => isMissing(p, byUnit[n]?.[p.key])),
    ),
    [numbers, points, byUnit],
  );
  const ready = numbers != null && open.length === 0;

  if (numbers == null) {
    return <Skeleton lines={2} label="Nummern werden geladen" />;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {numbers.map((n) => (
        <div key={n} className="flex flex-col gap-2">
          {/* Die Nummer nur, wenn es mehr als eine gibt. */}
          {numbers.length > 1 && (
            <span className="ix-tnum text-[11.5px]" style={{ color: 'var(--fg-4)' }}>{n}</span>
          )}
          {points.map((p) => (
            <PointInput key={p.key} point={p} unit={n} value={byUnit[n]?.[p.key]} disabled={busy}
              onChange={(v) => {
                // Die Meldung neben dem Setzen: der Updater kann mehrfach laufen (StrictMode).
                onDirty?.(true);
                setByUnit((s) => ({ ...s, [n]: { ...s[n], [p.key]: v } }));
              }} />
          ))}
        </div>
      ))}

      <button
        type="button"
        className="erp-actbtn erp-actbtn-primary w-full"
        style={{ height: 38 }}
        disabled={busy || !ready}
        data-tip={open.length ? `Noch offen: ${open.length} von ${numbers.length} Stück` : undefined}
        // Fester Name: der CSS-Tooltip zählte sonst in den Accessible Name.
        aria-label={action}
        onClick={() => { onDirty?.(false); onConfirm(byUnit); }}
      >
        <Check size={15} />
        {action}{numbers.length > 1 ? ` (${numbers.length} Stück)` : ''}
      </button>
      {open.length > 0 && (
        <p className="text-xs" style={{ color: 'var(--fg-3)' }}>
          Noch offen: {open.length} von {numbers.length} Stück
        </p>
      )}
    </div>
  );
}

/** Ist dieser Punkt (noch) nicht erfasst? Knapper Spiegel von `CaptureType.missing`. */
function isMissing(point: CapturePoint, value: unknown): boolean {
  if (point.type === 'bool') return value !== true && value !== false;
  if (point.type === NEEDS_TARGET) return value === undefined || value === null || value === '';
  return value === undefined || value === null || value === '';
}

function PointInput({ point, unit, value, disabled, onChange }: {
  point: CapturePoint;
  /** Das Stück, dem der Wert gilt (ein Bild wird ein Dokument an ihm). */
  unit: string;
  value: unknown;
  disabled?: boolean;
  onChange: (v: unknown) => void;
}) {
  const Icon = lookup(CAPTURE_ICON, point.type);
  // Die Einheit steht am **Sollwert**, nicht als eigene Zeile: sie gehört zur Zahl.
  const soll = point.type === NEEDS_TARGET && point.target != null
    ? `Soll ${point.target}${point.tolerance ? ` ± ${point.tolerance}` : ''}`
      + (point.unit ? ` ${point.unit}` : '')
    : null;

  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--fg-2)' }}>
        {Icon && <Icon size={13} style={{ color: 'var(--fg-3)' }} />}
        {point.label}
        {soll && <span className="font-normal" style={{ color: 'var(--fg-3)' }}>{soll}</span>}
      </span>

      {point.type === 'bool' ? (
        // Nicht angetippt ist **nicht** «nein».
        <span className="flex gap-1.5">
          <ThumbChoice label="Gut" active={value === true} tone="var(--success)" disabled={disabled}
            onClick={() => onChange(true)}><ThumbsUp size={15} /></ThumbChoice>
          <ThumbChoice label="Schlecht" active={value === false} tone="var(--danger)" disabled={disabled}
            onClick={() => onChange(false)}><ThumbsDown size={15} /></ThumbChoice>
        </span>
      ) : point.type === 'photo' ? (
        // **Genau eine Aufnahme, über die Kamera** (kein Upload) – ein Dokument am Stück.
        <PhotoShot value={typeof value === 'string' && value ? value : null} unit={unit}
          label={point.label} disabled={disabled} onChange={(url) => onChange(url ?? '')} />
      ) : point.type === 'signature' ? (
        <SignaturePad value={typeof value === 'string' && value ? value : null}
          disabled={disabled} onChange={(url) => onChange(url ?? '')} />
      ) : (
        <span className="flex items-center gap-1.5">
          <Input
            name={point.key}
            className={inputCls}
            disabled={disabled}
            {...(point.type === NEEDS_TARGET ? numericInputProps : {})}
            value={value == null ? '' : String(value)}
            onChange={(v) => onChange(
              point.type === NEEDS_TARGET ? numericOnly(v, { decimals: true }) : v,
            )}
          />
          {/* Die Einheit klebt am Feld. */}
          {point.type === NEEDS_TARGET && point.unit && (
            <span className="text-xs whitespace-nowrap" style={{ color: 'var(--fg-3)' }}>
              {point.unit}
            </span>
          )}
        </span>
      )}
    </label>
  );
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
        background: active ? `${tone}1A` : 'var(--bg-1)',
        color: active ? tone : 'var(--fg-4)',
      }}>
      {children}
    </button>
  );
}
