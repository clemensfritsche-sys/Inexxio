'use client';

import { useEffect, useState } from 'react';
import { ClipboardCheck, Check, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Capture, CaptureField } from '@/types';
import { Card, PrimaryButton, inputCls, numericOnly, numericInputProps } from '@/components/erp/fields';
import { localDateTime } from '@/lib/utils';

/**
 * Datenerfassung an **einer Einzelinstanz** – das einzige Modul, das der Basis-Neuaufbau
 * offen lässt.
 *
 * Die Maske kommt vom Artikel, die Werte gehören dem Stück. Was erfasst wurde, hat heute
 * **keine Folgen**: es sperrt nichts, stuft nichts hoch und löst keinen Folgeauftrag aus –
 * das war Prozesslogik und ist entfallen. Der Ausweis dafür ist die Ergebnis-Pille: sie
 * sagt, ob die bewertbaren Felder in Ordnung waren, mehr nicht. Trägt die Maske nichts
 * Bewertbares, steht dort auch nichts – ein erfundenes «bestanden» wäre eine Aussage,
 * die niemand getroffen hat.
 */
export function CapturePanel({ number }: { number: string }) {
  const [fields, setFields] = useState<CaptureField[] | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [history, setHistory] = useState<Capture[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    setError(null);
    Promise.all([api.getCaptureFields(number), api.getCaptures(number)])
      .then(([f, h]) => { if (!dead) { setFields(f.fields ?? []); setHistory(h); } })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [number]);

  async function submit() {
    setBusy(true); setError(null);
    try {
      await api.recordCapture(number, { values: values as never, note: null });
      setValues({});
      setHistory(await api.getCaptures(number));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && fields === null) {
    return <Card icon={ClipboardCheck} title="Datenerfassung"><ErrorLine msg={error} /></Card>;
  }
  if (fields === null) return null;

  if (fields.length === 0) {
    return (
      <Card icon={ClipboardCheck} title="Datenerfassung">
        <p className="text-sm text-fg-3">
          Für diesen Artikel ist keine Erfassungsmaske hinterlegt. Ohne Felder gibt es
          nichts zu erfassen – die Maske wird am Artikel gepflegt.
        </p>
      </Card>
    );
  }

  return (
    <Card icon={ClipboardCheck} title="Datenerfassung">
      <div className="flex flex-col gap-3">
        {fields.map((f) => (
          <FieldInput
            key={f.key}
            field={f}
            value={values[f.key]}
            onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))}
          />
        ))}

        {error && <ErrorLine msg={error} />}

        <PrimaryButton icon={Check} onClick={submit} disabled={busy}>
          Erfassen
        </PrimaryButton>

        {history.length > 0 && (
          <div className="mt-2 flex flex-col">
            {history.map((c) => (
              <div key={c.id} className="flex items-center gap-2 py-1.5 border-t border-border-1 text-sm">
                <Verdict result={c.result} />
                <span className="text-fg-3">{localDateTime(c.created_at)}</span>
                <span className="text-fg-3 truncate">
                  {Object.entries(c.values as Record<string, unknown>)
                    .map(([k, v]) => `${k}: ${String(v)}`).join(' · ')}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

/** `null` heisst «nichts Bewertbares erfasst» – dann steht hier bewusst nichts. */
function Verdict({ result }: { result: string | null | undefined }) {
  if (!result) return <span className="text-fg-3 text-xs">ohne Urteil</span>;
  const ok = result === 'passed';
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-ds-sm text-xs font-medium"
      style={{
        color: ok ? 'var(--success)' : 'var(--danger)',
        background: ok ? 'var(--success-bg)' : 'var(--danger-bg)',
      }}
    >
      {ok ? <Check size={12} /> : <X size={12} />}
      {ok ? 'bestanden' : 'nicht bestanden'}
    </span>
  );
}

function FieldInput({ field, value, onChange }: {
  field: CaptureField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const soll = field.type === 'measure' && field.target != null
    ? `Soll ${field.target}${field.tolerance ? ` ± ${field.tolerance}` : ''}`
    : undefined;

  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-fg-2">
        {field.label}
        {soll && <span className="ml-2 font-normal text-fg-3">{soll}</span>}
      </span>

      {field.type === 'bool' ? (
        <input
          type="checkbox"
          className="w-5 h-5 accent-[var(--inexxio)]"
          checked={value === true}
          onChange={(e) => onChange(e.target.checked)}
        />
      ) : (
        <input
          className={inputCls}
          {...(field.type === 'measure' ? numericInputProps : {})}
          value={value == null ? '' : String(value)}
          onChange={(e) => onChange(
            field.type === 'measure' ? numericOnly(e.target.value, { decimals: true }) : e.target.value,
          )}
        />
      )}
    </label>
  );
}

function ErrorLine({ msg }: { msg: string }) {
  return (
    <p className="text-sm" style={{ color: 'var(--danger)' }}>{msg}</p>
  );
}
