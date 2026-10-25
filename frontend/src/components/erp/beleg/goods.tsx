'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { ObjId } from '@/components/erp/obj-id';
import { numericInputProps, numericOnly } from '@/components/erp/fields';
import { Amount } from '@/components/erp/module-ui';
import { useAutosaveSignature } from '@/lib/use-autosave';
import {
  DOC_FIELD, DocPick, Editable, LABEL, Section, may,
} from './shared';
import type { Filled, Send } from './shared';

type Line = Filled['lines'][number];

/** Unter dieser Breite nennt die Zeile ihre Sache nicht mehr – dann bricht sie um. */
const NAME_MIN = 190;

/**
 * **Die Positionen** – je Position die Stücke (Titel, aus dem Artikel) und die Leistung
 * (Untertitel, bis zur Offerte änderbar), Ware oder Dienstleistung, der Satz (nur aus
 * `vat_choices` – die Anschrift entscheidet), der Einzelpreis und, wo wir den Preis nennen,
 * Vollbetrag ↔ Teilbetrag. Zollangaben nur beim Export. Darunter Netto, MWST je Satz, Total.
 */
export function Goods({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  return (
    <Section title={d.goods_title}>
      <div className="flex flex-col" style={{ gap: 12, minWidth: 0 }}>
        {d.lines.length === 0 && (
          <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
            Vor diesem Modul steht noch nichts – die Positionen sind die Einzelinstanzen
            des Auftrags.
          </span>
        )}
        {d.lines.map((ln) => (
          <LineRow key={ln.id} d={d} line={ln} busy={busy} onAction={onAction} />
        ))}
        <Sums d={d} onAction={onAction} />
      </div>
    </Section>
  );
}

/** Der Entwurf einer Position – was getippt ist, bevor es geschrieben wird. */
type LineDraft = {
  price: string; vat: string; text: string;
  /** `null` = Vollbetrag; ein Text = Teilbetrag (netto, leer = noch keiner getippt). */
  part: string | null;
  hs: string; origin: string; weight: string;
};

function fromLine(line: Line): LineDraft {
  return {
    price: line.price ?? '', vat: line.vat, text: line.text ?? '',
    part: line.part ?? null, hs: line.hs_code ?? '', origin: line.origin_country ?? '',
    weight: line.weight_kg ?? '',
  };
}

/**
 * **Eine Position – gespeichert, nicht abgeschickt**: jede Änderung wird geschrieben
 * (`price`), `ask` schickt sie hinaus. Was der Server sagt, gewinnt, sobald er sich ändert.
 */
function LineRow({ d, line, busy, onAction }: {
  d: Filled; line: Line; busy: boolean; onAction: Send;
}) {
  const remote = useMemo(() => fromLine(line), [line]);
  const [draft, setDraft] = useState<LineDraft>(remote);
  const key = JSON.stringify(remote);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setDraft(remote); }, [key]);

  const on = may(d, 'price');
  const priced = on && d.we_quote;
  const set = (patch: Partial<LineDraft>) => setDraft((x) => ({ ...x, ...patch }));
  const save = useCallback(() => {
    void onAction({ action: 'price', lines: [{
      id: line.id,
      ...(d.we_quote ? { price: draft.price === '' ? null : draft.price, vat: draft.vat,
                         part: draft.part === null || draft.part === '' ? null : draft.part }
        : {}),
      text: draft.text,
      ...(d.export ? { hs_code: draft.hs, origin_country: draft.origin,
                       weight_kg: draft.weight === '' ? null : draft.weight } : {}),
    }] });
  }, [onAction, line.id, d.we_quote, d.export, draft]);
  // Ein gewählter, aber noch leerer Teilbetrag ist noch keine Angabe – er wartet.
  const ready = !(draft.part !== null && draft.part === '' && line.part == null);
  const now = useAutosaveSignature(JSON.stringify(draft),
    on && ready && JSON.stringify(draft) !== key && !busy, save);

  return (
    <div className="flex flex-col" style={{ gap: 6, minWidth: 0 }}>
      <div className="flex flex-wrap items-start" style={{ gap: '6px 12px', minWidth: 0 }}>
        <div className="flex items-baseline" style={{ gap: 8, flex: `1 1 ${NAME_MIN}px`, minWidth: 0 }}>
          <span style={{ fontSize: 15, fontVariantNumeric: 'tabular-nums', flex: 'none' }}>
            {line.quantity}×
          </span>
          <div className="flex flex-col" style={{ gap: 3, minWidth: 0 }}>
            <LineTitle line={line} />
            <Service on={on} value={draft.text}
              onChange={(text) => set({ text })} onDone={now} />
            {d.export && (
              <Customs on={on} draft={draft} set={set} onDone={now} />
            )}
          </div>
        </div>
        {d.we_quote && (
          <div className="flex flex-wrap items-baseline justify-end"
            style={{ gap: '2px 10px', flex: '0 1 auto', minWidth: 0 }}>
            <VatPick d={d} line={line} on={priced} value={draft.vat}
              onChange={(vat) => set({ vat })} />
            <Price d={d} on={priced} value={draft.price} shown={line.price}
              onChange={(price) => set({ price })} onDone={now} />
          </div>
        )}
      </div>
      {d.we_quote && (
        <Part d={d} line={line} on={priced} value={draft.part}
          onChange={(part) => set({ part })} onDone={now} />
      )}
    </div>
  );
}

/** Titel = die Stücke: Name, Ware oder Dienstleistung, Nummer – gekappt wird der Name. */
function LineTitle({ line }: { line: Line }) {
  return (
    <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
      <span className="truncate" style={{ fontSize: 13, color: 'var(--fg-1)' }}>
        {line.article_name || '—'}
      </span>
      <span data-tip={line.is_service
        ? 'Steuersatz nach dem Sitz des Empfängers – keine Lieferbedingung'
        : 'Steuersatz nach der Lieferadresse'}
        style={{ fontSize: 11, color: 'var(--fg-3)', border: '1px solid var(--border-1)',
                 borderRadius: 4, padding: '0 5px', whiteSpace: 'nowrap', flex: 'none' }}>
        {line.kind_label}
      </span>
      {line.article_object_id != null && (
        <span style={{ flex: 'none' }}><ObjId value={line.article_object_id} /></span>
      )}
    </span>
  );
}

/** Untertitel = die Leistung – vorbelegt aus dem Artikel, bis zur Offerte änderbar. */
function Service({ on, value, onChange, onDone }: {
  on: boolean; value: string; onChange: (v: string) => void; onDone: () => void;
}) {
  const face: CSSProperties = { fontSize: 12, color: 'var(--fg-2)' };
  if (!on) return value ? <span style={face}>{value}</span> : null;
  return (
    <Editable title="Die Leistung zu diesen Stücken – vorbelegt aus dem Artikel, bis zur Offerte änderbar">
      <input value={value} aria-label="Leistung" placeholder="Leistung"
        onChange={(e) => onChange(e.target.value)} onBlur={onDone}
        onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
        style={{ ...DOC_FIELD, ...face, width: `${Math.max(12, value.length + 1)}ch`,
                 maxWidth: '100%' }} />
    </Editable>
  );
}

/** **Zoll – nur beim Export**: Tarif, Ursprung, Gewicht je Stück. */
function Customs({ on, draft, set, onDone }: {
  on: boolean; draft: LineDraft; set: (p: Partial<LineDraft>) => void; onDone: () => void;
}) {
  return (
    <span className="flex flex-wrap items-baseline" style={{ gap: '4px 10px', minWidth: 0 }}>
      <CustomsField label="Zolltarif" value={draft.hs} on={on} width={86}
        onChange={(hs) => set({ hs })} onDone={onDone} />
      <CustomsField label="Ursprung" value={draft.origin} on={on} width={40}
        onChange={(origin) => set({ origin: origin.toUpperCase() })} onDone={onDone} />
      <CustomsField label="Gewicht" unit="kg je Stück" value={draft.weight} on={on} width={52}
        numeric onChange={(weight) => set({ weight })} onDone={onDone} />
    </span>
  );
}

/**
 * **Eine Zoll-Angabe** – die Beschriftung steht davor, beim Eingeben wie im fertigen Beleg
 * (nie als Platzhalter, der beim ersten Zeichen verschwindet).
 */
function CustomsField({ label, unit, value, on, width, numeric, onChange, onDone }: {
  label: string; unit?: string; value: string; on: boolean; width: number;
  numeric?: boolean; onChange: (v: string) => void; onDone: () => void;
}) {
  const face: CSSProperties = { fontSize: 11.5, color: 'var(--fg-3)' };
  if (!on) {
    return value ? <span style={face}>{label} {value}{unit ? ` ${unit}` : ''}</span> : null;
  }
  return (
    <span className="inline-flex items-baseline" style={{ gap: 4, minWidth: 0 }}>
      <span style={{ ...face, flex: 'none' }}>{label}</span>
      <Editable title={label} missing={value.trim() === ''}>
        <input value={value} aria-label={label}
          {...(numeric ? numericInputProps : {})}
          onChange={(e) => onChange(numeric
            ? numericOnly(e.target.value, { decimals: 3 }) : e.target.value)}
          onBlur={onDone} onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
          style={{ ...DOC_FIELD, width, fontSize: 11.5, color: 'var(--fg-2)' }} />
      </Editable>
      {unit && <span style={{ ...face, flex: 'none' }}>{unit}</span>}
    </span>
  );
}

/**
 * **Ein Steuersatz heisst, wie hoch er ist – und wie er heisst** («8.10 % · Normalsatz»).
 * Wählbar ist nur, was die Anschrift zulässt (`vat_choices`); bei genau einer Wahl steht
 * der Satz fest.
 */
export function vatText(label?: string | null, rate?: string | null): string {
  const name = label ?? '';
  if (!rate) return name || '—';
  return name ? `${rate} % · ${name}` : `${rate} %`;
}

function VatPick({ d, line, on, value, onChange }: {
  d: Filled; line: Line; on: boolean; value: string; onChange: (v: string) => void;
}) {
  const rates = (d.vat_rates ?? []).filter((v) => (line.vat_choices ?? []).includes(v.key));
  const current = (d.vat_rates ?? []).find((v) => v.key === value);
  const text = vatText(current?.label ?? line.vat_label, current?.rate ?? line.vat_rate);
  return (
    <DocPick on={on && rates.length > 1} value={value} text={text} aria={d.vat_label}
      tip={line.vat_note || d.vat_label} face={{ fontSize: 12, color: 'var(--fg-3)' }}
      options={rates.map((v) => ({ value: v.key, label: vatText(v.label, v.rate) }))}
      onChange={onChange} />
  );
}

/** **Der Einzelpreis, netto** – mit Währung und der Stellenzahl der Währung. */
function Price({ d, on, value, shown, onChange, onDone }: {
  d: Filled; on: boolean; value: string; shown?: string | null;
  onChange: (v: string) => void; onDone: () => void;
}) {
  if (!on) {
    return <Amount value={shown} currency={d.currency} decimals={d.currency_decimals}
      size={15} weight={400} />;
  }
  return (
    <Editable title="Einzelpreis, netto" missing={value.trim() === ''}>
      <Amount currency={d.currency} size={13}>
        <input {...numericInputProps} value={value} aria-label="Einzelpreis"
          onChange={(e) => onChange(numericOnly(e.target.value, { decimals: d.currency_decimals }))}
          onBlur={onDone} onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
          style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                   fontVariantNumeric: 'tabular-nums' }} />
      </Amount>
    </Editable>
  );
}

const FULL = 'full';
const PART = 'part';

/**
 * **Vollbetrag ↔ Teilbetrag** – je Position ein Umschalter; der Teilbetrag ist ein Betrag
 * (netto), daneben der Anteil. Jedes Zahlungsmodul steht für sich – kein Vorschlag, kein
 * «Rest». Nach der Zusage steht nur noch, was gilt.
 */
function Part({ d, line, on, value, onChange, onDone }: {
  d: Filled; line: Line; on: boolean; value: string | null;
  onChange: (v: string | null) => void; onDone: () => void;
}) {
  const dec = d.currency_decimals;
  const share = value && line.full && Number(line.full) > 0
    ? `${((Number(value) / Number(line.full)) * 100).toFixed(1)} %` : null;
  if (!on) {
    if (line.part == null) return null;
    return (
      <span style={{ fontSize: 11.5, color: 'var(--fg-3)', textAlign: 'right' }}>
        Teilbetrag {line.part} von {line.full ?? '—'}{share ? ` (${share})` : ''}
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-end" style={{ gap: 8, minWidth: 0 }}>
      <PartSwitch value={value === null ? FULL : PART}
        onChange={(v) => { onChange(v === FULL ? null : (line.part ?? '')); }} />
      {value !== null && (
        <span className="inline-flex items-baseline" style={{ gap: 6 }}>
          <Editable title={`Teilbetrag, netto – von ${line.full ?? '—'} ${d.currency}`}
            missing={value.trim() === ''}>
            <input {...numericInputProps} value={value} aria-label="Teilbetrag" autoFocus={!line.part}
              onChange={(e) => onChange(numericOnly(e.target.value, { decimals: dec }))}
              onBlur={onDone} onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
              style={{ ...DOC_FIELD, width: 84, textAlign: 'right', fontSize: 13,
                       fontWeight: 600, fontVariantNumeric: 'tabular-nums' }} />
          </Editable>
          {share && <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>({share})</span>}
        </span>
      )}
    </div>
  );
}

function PartSwitch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const opt = (key: string, label: string) => {
    const active = value === key;
    return (
      <button type="button" aria-pressed={active} onClick={() => onChange(key)}
        style={{
          padding: '3px 9px', fontSize: 12, fontWeight: 600, borderRadius: 6,
          cursor: 'pointer', border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
          background: active ? 'var(--accent-soft)' : 'var(--bg-1)',
          color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
        }}>{label}</button>
    );
  };
  return (
    <span className="inline-flex" style={{ gap: 4 }}>
      {opt(FULL, 'Vollbetrag')}
      {opt(PART, 'Teilbetrag')}
    </span>
  );
}

/** Eine Zeile der Aufstellung – ein Satz und seine Steuer. */
type SumLine = { key: string; label: string; tax: string | null };

/**
 * **Welche Sätze die Aufstellung zeigt** – von Anfang an: welche Zeilen es gibt, sagen die
 * Positionen (jede trägt ihren Satz), nicht erst die Preise; sonst wüchse die Aufstellung
 * mit der ersten Serverantwort und schöbe alles darunter weg.
 */
function sumLines(d: Filled, theirs: NonNullable<NonNullable<Filled['invoice']>['vat']>): SumLine[] {
  if (!d.we_quote) {
    return theirs.map((v) => ({
      key: v.vat ?? v.rate, label: `${v.label ?? v.rate} (${v.rate} %)`, tax: v.tax }));
  }
  const out: SumLine[] = (d.vat_split ?? []).map((v) => ({
    key: v.vat ?? v.rate, label: `${v.label ?? v.rate} (${v.rate} %)`, tax: v.tax,
  }));
  for (const ln of d.lines) {
    if (out.some((r) => r.key === ln.vat)) continue;
    out.push({ key: ln.vat, label: `${ln.vat_label} (${ln.vat_rate} %)`, tax: null });
  }
  return out;
}

/**
 * **Netto · Steuer je Satz · Total** – jede Zahl nennt ihre Währung, und der Währungscode
 * am Total IST der Wähler (nur wo `can` ihn führt). Wo wir den Preis nennen, kommt die
 * Aufstellung aus den Positionen; wo die Gegenpartei ihn nennt, aus ihrer Rechnung.
 */
function Sums({ d, onAction }: { d: Filled; onAction: Send }) {
  const dec = d.currency_decimals;
  const theirs = !d.we_quote ? (d.invoice?.vat ?? []) : [];
  const rows = sumLines(d, theirs);
  const net = d.we_quote
    ? d.net
    : (theirs.length ? theirs.reduce((n, v) => n + Number(v.net), 0).toFixed(dec) : null);
  const total = d.we_quote
    ? (d.vat_split?.length ? d.vat_split.reduce((n, v) => n + Number(v.net) + Number(v.tax), 0)
      .toFixed(dec) : null)
    : (d.invoice?.amount ?? d.amount ?? null);
  return (
    <div className="flex flex-col" style={{
      gap: 4, marginTop: 4, paddingTop: 9, borderTop: '1px solid var(--border-1)',
    }}>
      <SumRow label="Netto" value={net} code={d.currency} dec={dec} />
      {rows.map((v) => (
        <SumRow key={v.key} label={`${d.vat_label} ${v.label}`} value={v.tax}
          code={d.currency} dec={dec} />
      ))}
      <div className="flex items-baseline" style={{
        gap: 10, marginTop: 4, paddingTop: 7, borderTop: '1px solid var(--border-1)',
      }}>
        <span style={{ ...LABEL, flex: 1 }}>Total</span>
        <Amount value={total} decimals={dec} size={15} weight={600}
          currency={<Currency d={d} onAction={onAction} />} />
      </div>
    </div>
  );
}

function SumRow({ label, value, code, dec }: {
  label: string; value?: string | null; code: string; dec: number;
}) {
  return (
    <div className="flex items-baseline" style={{ gap: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--fg-3)', flex: 1, minWidth: 0 }}>{label}</span>
      <Amount value={value} currency={code} decimals={dec} size={14} weight={400} />
    </div>
  );
}

/** **Die Währung – der Code selbst ist der Wähler**, wo `can` ihn führt. */
function Currency({ d, onAction }: { d: Filled; onAction: Send }) {
  return (
    <DocPick on={may(d, 'currency')} value={d.currency} text={d.currency}
      face={{ font: 'inherit', color: 'inherit' }} tip={d.currency_label} aria={d.currency_label}
      options={(d.currencies ?? []).map((c) => ({ value: c.code, label: c.label }))}
      onChange={(currency) => void onAction({ action: 'currency', currency })} />
  );
}
