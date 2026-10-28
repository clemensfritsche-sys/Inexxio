'use client';

import { useCallback, useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { useAutosaveSignature } from '@/lib/use-autosave';
import { day } from '@/lib/when';
import { numericInputProps, numericOnly } from '@/components/erp/fields';
import {
  DOC_FIELD, DocPick, Editable, FixedValue, Section, Stacked, isFixed, may,
} from './shared';
import type { Filled, Send } from './shared';

const VALUE = { fontSize: 13, color: 'var(--fg-1)' } as const;

/** Die üblichen Gültigkeiten einer Offerte – die freie Zahl steht daneben. */
const VALID_TERMS = [14, 30, 60, 90].map((n) => ({ days: n, label: `${n} Tage` }));

/**
 * **Die Konditionen** – Zahlungsfrist, Lieferfrist, Lieferbedingung (nur bei Ware), Gültigkeit
 * der Offerte (nur wo wir den Preis nennen) und Eigentum. Was das Modul vorgibt, steht fest
 * (punktiert, Grund im Hover); jeder änderbare Wert wird sofort geschrieben. Darunter der
 * Satz zu den AGB.
 */
export function Terms({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const on = may(d, 'terms') && d.we_quote;
  return (
    <Section title={d.terms_title}>
      <div style={{ display: 'grid', gap: '12px 24px',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 118px), 1fr))' }}>
        <SavedTerm d={d} label={d.payment_term_label} field="payment_days" busy={busy}
          on={on} days={d.due_days} terms={d.payment_terms ?? []} onAction={onAction} />
        <SavedTerm d={d} label={d.lead_term_label} field="lead_days" busy={busy}
          on={on} days={d.lead_days} terms={d.lead_terms ?? []} onAction={onAction}
          hint={d.due_date ? `Termin ${day(d.due_date)}` : undefined} />
        {d.incoterm_needed && <Delivery d={d} onAction={onAction} />}
        {d.valid_days != null && (
          <SavedTerm d={d} label={d.valid_label} field="valid_days" busy={busy}
            on={on} days={d.valid_days} terms={VALID_TERMS} onAction={onAction}
            hint={d.valid_until
              ? `Zählt ab «Anbieten» – gültig bis ${day(d.valid_until)}`
              : 'Zählt ab «Anbieten» – das Datum rechnet das System'} />
        )}
        <Ownership d={d} onAction={onAction} />
      </div>
      <Agb />
    </Section>
  );
}

/**
 * **Eine Frist, sofort geschrieben** – Entwurf, `useAutosaveSignature`, ein Verb (`terms`).
 * Gibt das Modul sie vor, steht sie fest.
 */
function SavedTerm({ d, label, field, busy, on, days, terms, hint, onAction }: {
  d: Filled; label: string; field: 'payment_days' | 'lead_days' | 'valid_days';
  busy: boolean; on: boolean; days: number | null | undefined;
  terms: { days: number; label: string }[]; hint?: string; onAction: Send;
}) {
  const remote = days == null ? '' : String(days);
  const [draft, setDraft] = useState(remote);
  useEffect(() => { setDraft(remote); }, [remote]);
  const fixed = isFixed(d, field);
  const save = useCallback(() => {
    // **Die Null ist eine Angabe** («Vorauszahlung» · «Sofort») – geprüft wird auf leer.
    return onAction({ action: 'terms', [field]: draft === '' ? null : Number(draft) });
  }, [onAction, field, draft]);
  useAutosaveSignature(`${field}:${draft}`, on && !fixed && draft !== remote && !busy, save);

  if (fixed) {
    return (
      <Stacked label={label}>
        <FixedValue hint={d.fixed_hint} face={VALUE}>{termWord(remote, terms)}</FixedValue>
      </Stacked>
    );
  }
  return (
    <Term label={label} on={on} value={on ? draft : remote} terms={terms} hint={hint}
      freeMin={d.term_free_min} freeLabel={d.term_free_label} onChange={setDraft} />
  );
}

/** Was eine Frist heisst – das Wort der Liste oder «N Tage». */
function termWord(value: string, terms: { days: number; label: string }[]): string {
  if (value === '') return '—';
  const named = terms.find((t) => String(t.days) === value);
  return named ? named.label : `${value} Tag${value === '1' ? '' : 'e'}`;
}

/** Der Platzhalter der freien Wahl – ein Wort, kein Steuerzeichen. */
const TERM_FREE = 'frei';

/**
 * **Eine Frist ist ein Wert auf dem Beleg, keine Knopfreihe**: der gedruckte Wert ist der
 * Wähler; die freie Eingabe steht an derselben Stelle. Auch an der Angebotszeile eines
 * Lieferanten – dieselbe Form für dieselbe Frage.
 */
export function Term({ label, on, value, terms, hint, freeMin, freeLabel, onChange }: {
  label: string; on: boolean;
  /** Der Wert (leer = noch nichts gewählt). */
  value: string;
  terms: { days: number; label: string }[];
  hint?: string;
  freeMin: number; freeLabel: string;
  onChange: (value: string) => void;
}) {
  const named = terms.find((t) => String(t.days) === value);
  const free = value !== '' && !named;
  const [typing, setTyping] = useState(false);
  return (
    <Stacked label={label}>
      {on && (free || typing) ? (
        <Editable title={label} missing={value === ''}>
          <input {...numericInputProps} autoFocus={typing} value={value} aria-label={label}
            onChange={(e) => onChange(numericOnly(e.target.value, { decimals: false }))}
            onBlur={() => {
              setTyping(false);
              const n = Number(value);
              onChange(String(Number.isFinite(n) && n >= freeMin ? n : freeMin));
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            style={{ ...DOC_FIELD, width: 28, fontSize: 13, fontVariantNumeric: 'tabular-nums' }} />
          <span style={{ fontSize: 13, paddingRight: 4 }}>Tage</span>
        </Editable>
      ) : (
        <DocPick on={on} value={named ? value : ''} text={termWord(value, terms)} aria={label}
          missing={value === ''} face={VALUE} tip={hint}
          options={[
            ...(value === '' ? [{ value: '', label: '—' }] : []),
            ...terms.map((t) => ({ value: String(t.days), label: t.label })),
            { value: TERM_FREE, label: freeLabel },
          ]}
          onChange={(v) => {
            if (v === TERM_FREE) { setTyping(true); onChange(String(freeMin)); return; }
            onChange(v);
          }} />
      )}
    </Stacked>
  );
}

/**
 * **Die Lieferbedingung – gewählt wird nur die Klausel**; der Ort ist kein Feld, er folgt
 * aus den Anschriften (E/F bei uns, C/D am Ziel). Die Erklärung steht sichtbar darunter,
 * solange gewählt wird: hier entscheidet ein Kürzel über Kosten und Risiko.
 */
function Delivery({ d, onAction }: { d: Filled; onAction: Send }) {
  const label = d.incoterm_label;
  const chosen = (d.incoterms ?? []).find((t) => t.key === d.incoterm);
  const place = d.incoterm_place ?? '';
  if (isFixed(d, 'incoterm')) {
    return (
      <Stacked label={label}>
        <FixedValue hint={d.fixed_hint} face={VALUE}>
          {[d.incoterm, place].filter(Boolean).join(' ') || '—'}
        </FixedValue>
      </Stacked>
    );
  }
  if (!may(d, 'incoterm')) {
    return (
      <Stacked label={label}>
        <span style={VALUE} {...(chosen ? { 'data-tip': chosen.hint } : {})}>
          {[d.incoterm, place].filter(Boolean).join(' ') || '—'}
        </span>
      </Stacked>
    );
  }
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <Stacked label={label}>
        <DocPick on value={d.incoterm ?? ''} text={chosen ? chosen.key : '—'} aria={label}
          face={VALUE} missing={!chosen}
          options={[{ value: '', label: '—' },
                    ...(d.incoterms ?? []).map((t) => ({ value: t.key,
                                                         label: `${t.key} · ${t.label}` }))]}
          onChange={(v) => void onAction({ action: 'incoterm', incoterm: v || null })} />
      </Stacked>
      {chosen && place && (
        <span style={VALUE} data-tip={`${d.incoterm_place_label} – aus der Anschrift, kein eigenes Feld`}>
          {place}
        </span>
      )}
      {chosen?.hint && (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 2 }}>{chosen.hint}</span>
      )}
    </div>
  );
}

/**
 * **Eigentum** – geht an die Partei · geht an uns. **Bewusst gewählt, ohne Vorbelegung**:
 * ohne Wahl gehen Offerte und Zusage nicht (gelb markiert wie jede Pflichtangabe). Am Ziel
 * des Auftrags wird ein Stück, das so an die Partei ging, «Verkauft».
 */
function Ownership({ d, onAction }: { d: Filled; onAction: Send }) {
  const options = d.ownership_options ?? [];
  const chosen = options.find((o) => o.key === d.ownership);
  const text = chosen?.label ?? '—';
  const tip = 'Wem die Stücke danach gehören – an die Partei: am Ziel des Auftrags werden sie '
    + '«Verkauft»; an uns: sie bleiben unser Bestand. Bewusst wählen, frei bis zur Zusage.';
  if (isFixed(d, 'ownership')) {
    return (
      <Stacked label={d.ownership_label}>
        <FixedValue hint={d.fixed_hint} face={VALUE}>{text}</FixedValue>
      </Stacked>
    );
  }
  return (
    <Stacked label={d.ownership_label}>
      <DocPick on={may(d, 'ownership')} value={d.ownership ?? ''} text={text}
        aria={d.ownership_label} tip={tip} face={VALUE} missing={!chosen}
        options={[...(chosen ? [] : [{ value: '', label: '—' }]),
                  ...options.map((o) => ({ value: o.key, label: o.label }))]}
        onChange={(ownership) => { if (ownership) void onAction({ action: 'ownership', ownership }); }} />
    </Stacked>
  );
}

/** Die AGB einmal je Sitzung – jede Karte nennt dasselbe Datum. */
let agbFrom: Promise<string | null> | null = null;

function agbDate(): Promise<string | null> {
  // Gescheitert gilt nicht als Antwort: gemeldet, und die nächste Karte fragt neu.
  agbFrom ??= api.publicLegal('agb').then((r) => r.valid_from).catch((e: unknown) => {
    tell('Datum der AGB')(e);
    agbFrom = null;
    return null;
  });
  return agbFrom;
}

/**
 * **«Es gelten unsere AGB vom …»** – das Datum der Fassung, die jedes Dokument als letzte
 * Seite trägt; der Link öffnet sie als A4-Dokument.
 */
function Agb() {
  const [from, setFrom] = useState<string | null>(null);
  useEffect(() => {
    let stale = false;
    void agbDate().then((v) => { if (!stale) setFrom(v); });
    return () => { stale = true; };
  }, []);
  if (!from) return null;
  return (
    <div className="flex items-center" style={{ gap: 6, marginTop: 12, fontSize: 12,
                                                color: 'var(--fg-3)' }}>
      <ExternalLink size={12} style={{ flex: 'none' }} />
      <span>
        Es gelten unsere{' '}
        <a href="/agb" target="_blank" rel="noopener noreferrer" style={{
          color: 'var(--accent-ink)', textDecoration: 'none',
          borderBottom: '1px solid var(--accent)',
        }}>AGB vom {day(from)}</a>.
      </span>
    </div>
  );
}
