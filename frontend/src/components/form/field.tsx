import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { inputClass, inputCls } from '@/components/erp/controls';
import { useField, type FieldNote, type FieldSpec } from './use-field';
import { ProposalMark } from './proposal-mark';

/**
 * ►►► **Der Feld-Baustein des ERP** – jedes bearbeitbare Feld eines Datensatzes steht hier
 * (Projektakte «Die lernende Firma» §4.3, Schritt 2.1). ◄◄◄
 *
 * Die Logik steht EINMAL in `useField` (Wert, Pflicht, Format, Meldung, Enter, Vorschlag).
 * Zwei Formen tragen sie – und beide das Zeichen eines offenen Vorschlags (`proposal-mark`):
 * die Standardform neben der Beschriftung, das freie Aussehen schwebend an der Ecke.
 *
 * - **`Field` · `SelectField`** – die Standardform: Beschriftung, das Feld in `inputClass`,
 *   darunter höchstens eine Meldung. So sieht ein Feld im ERP aus, wenn nichts anderes gilt.
 * - **`Input` · `Select` · `TextArea`** – **Logik zentral, Aussehen frei**: dieselbe Logik
 *   ohne eigenes Aussehen; Klasse und Stil gibt der Aufrufer (der Beleg sieht aus wie
 *   gedrucktes Papier, das Konto wie die Website, der Prozess-Editor ist eng).
 *
 * Ein loses `<input>`/`<select>`/`<textarea>` unter `components/erp/` weist ESLint ab
 * (`eslint.config.mjs`, «RAW_FIELD»); die begründeten Ausnahmen stehen dort.
 */

/** Was am Element frei bleibt – alles, was nicht Logik des Feldes ist. */
type Look<A> = Omit<A, 'name' | 'value' | 'onChange' | 'onKeyDown' | 'readOnly' | 'required' | 'type'>;

/** Die Meldung unter einem Feld der Standardform. */
const NOTE_COLOR: Record<FieldNote['tone'], string> = {
  danger: 'var(--danger)', warning: 'var(--warning)', quiet: 'var(--fg-4)',
};
function Note({ note }: { note: FieldNote | null }) {
  return note && <p style={{ fontSize: 12, color: NOTE_COLOR[note.tone], margin: 0 }}>{note.text}</p>;
}

const COLUMN = { display: 'flex', flexDirection: 'column', gap: 4 } as const;
const LABEL = { fontSize: 13, fontWeight: 500, color: 'var(--fg-2)', display: 'flex', alignItems: 'center',
  gap: 6 } as const;

interface FieldProps extends FieldSpec {
  label: string;
  placeholder?: string;
  /** `id` einer `<datalist>` – Vorschläge beim Tippen, Freitext bleibt möglich. */
  list?: string;
  /** Mehrzeilig mit so vielen Zeilen – Enter ist dann eine neue Zeile. */
  rows?: number;
}

/** **Die Standardform** eines Feldes: Text, Telefon, E-Mail, Zahl, Datum – oder mehrzeilig. */
export function Field({ label, placeholder, list, rows, ...spec }: FieldProps) {
  const f = useField(rows ? { ...spec, onEnter: undefined } : spec);
  const className = inputClass(f.tone);
  return (
    <div style={COLUMN}>
      <label style={LABEL}>
        {label}
        {f.empty && <span style={{ color: 'var(--warning)', marginLeft: -3, fontWeight: 700 }}>*</span>}
        <ProposalMark mark={f.proposal} />
      </label>
      {rows ? (
        <textarea rows={rows} placeholder={placeholder} className={className} {...f.control} />
      ) : (
        <input type={spec.type ?? 'text'} placeholder={placeholder} list={list} className={className} {...f.control} />
      )}
      <Note note={f.note} />
    </div>
  );
}

interface SelectFieldProps extends Omit<FieldSpec, 'type' | 'readOnly' | 'onEnter' | 'hint'> {
  label: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}

/** **Die Standardform einer Auswahl** aus wenigen festen Werten (Rolle, Währung …). */
export function SelectField({ label, options, ...spec }: SelectFieldProps) {
  const f = useField(spec);
  return (
    <div style={COLUMN}>
      <label style={LABEL}>{label}<ProposalMark mark={f.proposal} /></label>
      <select ref={f.control.ref} value={f.control.value} onChange={f.control.onChange}
        className={`${inputCls} cursor-pointer`}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <Note note={f.note} />
    </div>
  );
}

/**
 * **Ein Feld in freiem Aussehen** – die Logik von `useField`, Klasse und Stil vom Aufrufer.
 * `required` bleibt am Element, wie der Aufrufer es setzt.
 */
export function Input({ name, objectId, value, onChange, type, required, readOnly, onEnter, error, hint, ...look }:
  FieldSpec & Look<InputHTMLAttributes<HTMLInputElement>>) {
  const f = useField({ name, objectId, value, onChange, type, required, readOnly, onEnter, error, hint });
  return (
    <>
      <input type={type} required={required} {...look} {...f.control}
        inputMode={look.inputMode ?? f.control.inputMode} />
      <ProposalMark mark={f.proposal} anchor={f.element} />
    </>
  );
}

/** **Eine Auswahl in freiem Aussehen** – die Optionen sind die Kinder. */
export function Select({ name, objectId, value, onChange, required, error, children, ...look }:
  Omit<FieldSpec, 'type' | 'readOnly' | 'onEnter' | 'hint'> & Look<SelectHTMLAttributes<HTMLSelectElement>> & { children: ReactNode }) {
  const f = useField({ name, objectId, value, onChange, required, error });
  return (
    <>
      <select required={required} {...look} ref={f.control.ref} value={f.control.value} onChange={f.control.onChange}>
        {children}
      </select>
      <ProposalMark mark={f.proposal} anchor={f.element} />
    </>
  );
}

/** **Mehrzeilig in freiem Aussehen** – Enter ist eine neue Zeile, kein «fertig». */
export function TextArea({ name, objectId, value, onChange, required, readOnly, error, ...look }:
  Omit<FieldSpec, 'type' | 'onEnter' | 'hint'> & Look<TextareaHTMLAttributes<HTMLTextAreaElement>>) {
  const f = useField({ name, objectId, value, onChange, required, readOnly, error });
  return (
    <>
      <textarea required={required} {...look} {...f.control} />
      <ProposalMark mark={f.proposal} anchor={f.element} />
    </>
  );
}
