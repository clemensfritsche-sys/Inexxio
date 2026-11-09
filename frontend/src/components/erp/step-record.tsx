'use client';

import { AlertTriangle, Check, Keyboard, Minus, ScanLine } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import type { RecordEntry, RecordValue } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { UnitNumber } from '@/components/erp/unit-number';
import { when, whenTitle } from '@/lib/when';
import { MICRO_LABEL, StatusDot } from '@/components/erp/fields';
import { Skeleton } from './skeleton';
import { errorText } from '@/lib/use-action';
import { useQuery } from '@tanstack/react-query';
import { qk } from '@/lib/queries';

/**
 * ►►► **Ein abgeschlossenes Modul zeigt lückenlos, was in ihm passiert ist** ◄◄◄ – für alle
 * Module eine Ansicht, im Server eine Ableitung aus dem Log (`services/record`). **Ein
 * Eintrag ist ein Vorgang, kein Stück** (Wiederholungen stehen alle da). Erst auf Klick.
 */
export function StepRecord({ orderObjectId, stepId }: {
  orderObjectId: number;
  stepId: number;
}) {
  const query = useQuery({
    queryKey: qk.stepRecord(orderObjectId, stepId),
    queryFn: ({ signal }) => api.stepRecord(orderObjectId, stepId, 200, 0, { signal }),
    meta: { what: 'Protokoll' },
  });
  const rows: RecordEntry[] | null = query.data ? query.data.entries ?? [] : null;
  const total = query.data?.total ?? 0;
  const err = query.error ? errorText(query.error) : null;

  if (err) return <p className="text-xs" style={{ color: 'var(--danger)' }}>{err}</p>;
  if (rows === null) {
    return <Skeleton lines={2} label="Protokoll wird geladen" />;
  }
  if (rows.length === 0) {
    return (
      <p className="text-xs" style={{ color: 'var(--fg-4)' }}>
        Hier ist noch nichts passiert.
      </p>
    );
  }

  return (
    <div className="flex flex-col">
      {/* ►►► **Die Liste sagt, WAS sie ist** ◄◄◄ – der Nachweis des Moduls, mit Gesamtzahl. */}
      <div className="flex items-baseline gap-2" style={{ marginBottom: 4 }}>
        <span style={MICRO_LABEL}>Was hier passiert ist</span>
        <span className="ix-tnum text-[11px]" style={{ color: 'var(--fg-4)' }}
          data-tip="Ein Eintrag ist ein Vorgang, kein Stück – ein Stück kann dasselbe
                    Modul mehrfach passieren.">
          {total} {total === 1 ? 'Vorgang' : 'Vorgänge'}
        </span>
      </div>
      {rows.map((e, i) => <Row key={`${e.number}-${e.at}-${i}`} entry={e} first={i === 0} />)}
      {rows.length < total && (
        <p className="mt-1.5 text-[11.5px]" style={{ color: 'var(--fg-4)' }}>
          {rows.length} von {total} Vorgängen – die neuesten stehen weiter unten.
        </p>
      )}
    </div>
  );
}

/** Ein Vorgang: **wer, wann, womit bestätigt** – und darunter jede erfasste Angabe. */
function Row({ entry, first }: { entry: RecordEntry; first: boolean }) {
  // **Nur eine Änderung ist eine Aussage** – gefragt wird nach den Daten, nicht dem Modultyp.
  const changed = !!entry.status_after && entry.status_after !== entry.status_before;
  const cfg = changed && entry.status_after ? statusCfg(entry.status_after) : null;
  const values = entry.values ?? [];
  return (
    <div className="flex flex-col gap-1 py-1.5"
      style={first ? undefined : { borderTop: '1px solid var(--border-1)' }}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <UnitNumber value={entry.number} />
        {/* **Wie bestätigt wurde** (Kamera oder Tastatur), sagt ein Symbol (§4.4). */}
        {entry.verification === 'scan' && (
          <ScanLine size={12} style={{ color: 'var(--fg-4)' }} data-tip="Gescannt" />
        )}
        {entry.verification === 'manual' && (
          <Keyboard size={12} style={{ color: 'var(--warning)' }}
            data-tip="Von Hand bestätigt – erlaubt, protokolliert, und als das erkennbar" />
        )}
        {entry.result === 'failed' && (
          <span className="flex items-center gap-1 text-[11.5px]" style={{ color: 'var(--danger)' }}>
            <AlertTriangle size={12} /> nicht bestanden
          </span>
        )}
        {entry.result === 'passed' && (
          <Check size={12} style={{ color: 'var(--success)' }} data-tip="Bestanden" />
        )}
        {!entry.sampled && (
          <span className="flex items-center gap-1 text-[11.5px]" style={{ color: 'var(--fg-4)' }}
            data-tip="Ausserhalb der Ziehung – ohne Erfassung durchgelaufen (§9.3)">
            <Minus size={12} /> nicht gezogen
          </span>
        )}
        {entry.into && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
            verbaut in <UnitNumber value={entry.into} />
          </span>
        )}
        {cfg && (
          <span className="ml-auto flex items-center gap-1.5 text-[11.5px]"
            style={{ color: cfg.color }}>
            <StatusDot color={cfg.color} />
            {cfg.label}
          </span>
        )}
      </div>

      {values.length > 0 && (
        <div className="flex flex-col gap-1" style={{
          marginLeft: 10, paddingLeft: 10, borderLeft: '1px solid var(--border-1)',
        }}>
          {values.map((v) => <Value key={v.key} value={v} />)}
        </div>
      )}

      {/* **Die Aussage steht da, die Tatsache im Hover** (`lib/when`). */}
      <span className="text-[11px]" style={{ color: 'var(--fg-4)' }}
        {...(whenTitle(entry.at) ? { 'data-tip': whenTitle(entry.at) } : {})}>
        {[entry.actor, when(entry.at)].filter(Boolean).join(' · ')}
      </span>
    </div>
  );
}

/** Ein erfasster Wert – **mit seiner Frage**; Bild und Unterschrift als Bild. */
function Value({ value }: { value: RecordValue }) {
  const tone = value.ok === false ? 'var(--danger)'
    : value.ok === true ? 'var(--success)' : 'var(--fg-2)';
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <span className="text-[11.5px]" style={{ color: 'var(--fg-4)' }}>{value.label}</span>
      {value.type === 'photo' || value.type === 'signature' ? (
        <Media value={value.value} label={value.label} />
      ) : (
        <span className="text-xs" style={{ color: tone }}>{describe(value)}</span>
      )}
    </div>
  );
}

function Media({ value, label }: { value: unknown; label: string }) {
  const url = typeof value === 'string' && value ? value : null;
  if (!url) return <span className="text-xs" style={{ color: 'var(--fg-4)' }}>—</span>;
  return (
    <a href={attachmentUrl(url)} target="_blank" rel="noopener noreferrer"
      className="rounded-ds-md overflow-hidden inline-block"
      style={{ width: 56, height: 56, border: '1px solid var(--border-1)' }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={attachmentUrl(url)} alt={label}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </a>
  );
}

/** Der Wert als Wort – **ohne Deutung**: gezeigt wird, was erfasst wurde. */
function describe(value: RecordValue): string {
  const raw = value.value;
  if (raw === true) return 'gut';
  if (raw === false) return 'schlecht';
  if (raw === null || raw === undefined || raw === '') return '—';
  return String(raw);
}
