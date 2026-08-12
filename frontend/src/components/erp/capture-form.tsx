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
 * ►►► **Der Scan gilt der Instanz, die Erfassung der Einzelinstanz.** ◄◄◄
 *
 * Zwei verschiedene Dinge (PROCESS_CORE §4.4/§9.3), und sie sind hier bewusst getrennt:
 * verifiziert wird **eine** Instanz – das Etikett klebt am physischen Ding –, erfasst
 * wird je **gezogenem Stück** ein eigener Satz. Ein Scan, n Formulare: Charge über zwei
 * → zwei, Stichprobe ¼ von 6000 → 1500.
 *
 * Vorher stand hier **ein** Formular, dessen Werte auf alle gezogenen Stücke kopiert
 * wurden. Das war nicht bloss unbequem – es war eine Behauptung: zwei Messwerte, gemessen
 * einer. Zwei Schrauben aus derselben Charge haben zwei Durchmesser.
 *
 * **Jeder offene Punkt blockiert – mit Grund.** «Bestätigen nicht möglich» ohne zu sagen,
 * was fehlt, wäre eine Sackgasse mit Ausrufezeichen. Alles, was angelegt ist, ist Pflicht;
 * einen Schalter dafür gibt es nicht mehr. Der Server prüft dasselbe noch einmal – ein
 * deaktivierter Knopf ist keine Absicherung.
 */
export function CaptureForm({ points, numbers, action, busy, onConfirm, onDirty }: {
  points: CapturePoint[];
  /** **Das Verb des Moduls** (`ProcessStepResponse.action`) – «Erfassen & bestätigen»,
   *  «Verschrotten», «Sperren». Es kommt vom Server, weil es beim Aussondern an der
   *  Ausprägung hängt; ein fester Text hier wäre eine zweite Aussage darüber. */
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
   * ►►► Zur offenen Frage (Abweichungsauftrag §5) ◄◄◄ – meldet, dass hier **begonnen**
   * wurde zu erfassen. Serverseitig gibt es diesen Zustand nicht: was nicht bestätigt
   * ist, existiert nirgends. Genau deshalb kann ihn nur dieses Fenster kennen – und
   * genau deshalb ist die Sperre hier eine Vorsichtsmassnahme, keine Regel.
   */
  onDirty?: (dirty: boolean) => void;
}) {
  const [byUnit, setByUnit] = useState<Record<string, Record<string, unknown>>>({});

  // **Alles, was angelegt ist, ist Pflicht** – und zwar an **jedem** gezogenen Stück.
  // Gezählt werden die Stücke, nicht die Punkte: «noch 3 Stück offen» ist die Auskunft,
  // die man bei 1500 braucht; welcher Punkt fehlt, steht am Stück selbst.
  const open = useMemo(
    () => (numbers ?? []).filter(
      (n) => points.some((p) => isMissing(p, byUnit[n]?.[p.key])),
    ),
    [numbers, points, byUnit],
  );
  const ready = numbers != null && open.length === 0;

  if (numbers == null) {
    return <p className="text-xs" style={{ color: 'var(--fg-3)' }}>lädt …</p>;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {numbers.map((n) => (
        <div key={n} className="flex flex-col gap-2">
          {/* Die Nummer nur, wenn es mehr als eine gibt: bei einer wäre sie die
              Wiederholung der Zeile darüber. */}
          {numbers.length > 1 && (
            <span className="ix-tnum text-[11.5px]" style={{ color: 'var(--fg-4)' }}>{n}</span>
          )}
          {points.map((p) => (
            <PointInput key={p.key} point={p} value={byUnit[n]?.[p.key]} disabled={busy}
              onChange={(v) => {
                // Die Meldung steht **neben** dem Setzen, nicht darin: der Updater von
                // `setByUnit` kann mehrfach laufen (StrictMode) und darf keine Wirkung
                // nach aussen haben.
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
        // Fester Name: der Tooltip ist CSS-generierter Inhalt und zählt sonst in den
        // Accessible Name – der Knopf hiesse je nach offenem Punkt anders.
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
        <span className="flex items-center gap-1.5">
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
          {/* **Die Einheit klebt am Feld, nicht daneben** – sie ist keine Eingabe,
              sondern sagt, worin die Zahl links gemeint ist. */}
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
