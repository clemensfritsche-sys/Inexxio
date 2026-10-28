'use client';

import { useCallback, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { ObjectSelect } from '@/components/erp/object-select';
import { MICRO_LABEL } from '@/components/erp/fields';
import { SearchSelect } from '@/components/erp/search-select';
import type { VoucherEmbed } from '@/types';

/**
 * **Die Bausteine des Belegs** – die Formen, die jeder Abschnitt der Karte teilt
 * (`beleg-work.tsx` setzt sie zusammen). Eine Form je Sache: `Editable` (die
 * Auszeichnung), darauf `DocPick` (Aufzählung), `DocRef` (Datensatz) und `DocFind`
 * (gesuchte Belege); `Section` ist der ruhige Kopf jedes Abschnitts.
 */
export type Filled = Omit<VoucherEmbed,
  'stages' | 'entries' | 'allowed' | 'can' | 'quotes' | 'lines' | 'documents'> & {
  stages: NonNullable<VoucherEmbed['stages']>;
  entries: NonNullable<VoucherEmbed['entries']>;
  allowed: NonNullable<VoucherEmbed['allowed']>;
  can: NonNullable<VoucherEmbed['can']>;
  quotes: NonNullable<VoucherEmbed['quotes']>;
  lines: NonNullable<VoucherEmbed['lines']>;
  documents: NonNullable<VoucherEmbed['documents']>;
};

/** Der Beleg mit den Listen, die der Dienst immer liefert – leer statt fehlend. */
export function filled(v: VoucherEmbed): Filled {
  return {
    ...v,
    stages: v.stages ?? [], entries: v.entries ?? [], allowed: v.allowed ?? [],
    can: v.can ?? [], quotes: v.quotes ?? [], lines: v.lines ?? [],
    documents: v.documents ?? [],
  };
}

export type Action = { action: string } & Record<string, unknown>;
export type Send = (body: Action) => Promise<unknown> | void;

/**
 * **Darf man das hier tun?** – `can` ist Auskunft **und** Tor (`services/voucher`):
 * dieselbe Liste rendert die Knöpfe und weist ab.
 */
export function may(d: Filled, action: string): boolean {
  return d.can.includes(action);
}

/**
 * **Gibt das Modul diesen Wert vor?** (`fixed`) – dann steht er fest, punktiert, mit dem
 * Grund im Hover (`fixed_hint`). Das Modul ist Master.
 */
export function isFixed(d: Filled, field: string): boolean {
  return (d.fixed ?? []).includes(field);
}

/** Die Beschriftung über einem Wert – die eine Form (`fields.MICRO_LABEL`). */
export const LABEL = MICRO_LABEL;

/**
 * **Ein Feld auf dem Beleg sieht aus wie der Beleg**: kein Rahmen, keine Fläche – was es
 * von einer gedruckten Zeile unterscheidet, ist allein `.ix-editable`.
 */
export const DOC_FIELD: CSSProperties = {
  background: 'transparent', border: 0, outline: 'none', padding: 0,
  font: 'inherit', color: 'inherit',
};

/** Wo noch nichts dasteht («—»), muss der Wähler trotzdem zu treffen sein. */
export const MIN_PICK = 44;

/**
 * **Ein Wert, den man ändern kann** – die eine Hülle: `.ix-editable` (getönt, ohne
 * Layoutwirkung, so gross wie das Feld). Ein Pflichtwert ohne Wert trägt sie warnfarben
 * (`missing`); die Regel selbst steht im Dienst (`voucher.ask_problem`).
 */
export function Editable({ as: Tag = 'span', style, title, missing, children }: {
  as?: 'span' | 'div';
  style?: CSSProperties;
  title?: string;
  missing?: boolean;
  children: ReactNode;
}) {
  const box: CSSProperties = Tag === 'span'
    ? { display: 'inline-flex', width: 'fit-content', maxWidth: '100%', ...style }
    : { display: 'flex', ...style };
  return (
    <Tag className={`ix-editable${missing ? ' is-missing' : ''}`}
      style={box}
      {...(missing ? { 'aria-invalid': true as const } : {})}
      {...(title ? { 'data-tip': missing ? `${title} – Pflichtangabe` : title } : {})}>
      {children}
    </Tag>
  );
}

/**
 * **Ein Wert, den das Modul vorgibt** – gedruckt, punktiert unterstrichen, der Grund im
 * Hover. Er sieht nicht änderbar aus, weil er es nicht ist.
 */
export function FixedValue({ hint, face, children }: {
  hint: string; face?: CSSProperties; children: ReactNode;
}) {
  return (
    <span data-tip={hint} style={{
      width: 'fit-content', borderBottom: '1px dotted var(--fg-3)', ...face,
    }}>{children}</span>
  );
}

/**
 * **Der gedruckte Wert IST das Bedienelement**: sichtbar ein `<span>` in der Schrift, die
 * dort ohnehin steht, bedienbar ein unsichtbares `<select>` darüber.
 */
export function DocPick({ on, value, text, options, face, tip, aria, missing, onChange }: {
  on: boolean;
  value: string;
  text: ReactNode;
  options: { value: string; label: string }[];
  face?: CSSProperties;
  tip?: string;
  aria: string;
  missing?: boolean;
  onChange: (value: string) => void;
}) {
  const shown = <span aria-hidden style={{ whiteSpace: 'pre-line', ...face }}>{text}</span>;
  if (!on) return shown;
  return (
    <Editable title={tip} missing={missing}
      style={{ position: 'relative', minWidth: MIN_PICK, maxWidth: '100%' }}>
      {shown}
      <select value={value} aria-label={aria}
        onChange={(e) => onChange(e.target.value)}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                 opacity: 0, cursor: 'pointer' }}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Editable>
  );
}

/**
 * **Ein Datensatz auf dem Beleg** – im Ruhezustand der gedruckte Name mit der
 * Auszeichnung, der Klick macht daraus die Suche (`ObjectSelect`). `open` darf der Aufrufer
 * setzen: «Partner wählen» in der Leiste öffnet genau diese Suche.
 */
export function DocRef<T extends { object_id: number; name: string }>({
  on, text, placeholder, value, selected, find, face, tip, open: opened, onOpen, onChange,
}: {
  on: boolean;
  text: ReactNode;
  placeholder: string;
  value: number | null;
  selected?: T | null;
  find: (query: string) => Promise<T[]>;
  face?: CSSProperties;
  tip?: string;
  open?: boolean;
  onOpen?: (open: boolean) => void;
  onChange: (objectId: number | null, option: T | null) => void;
}) {
  const [own, setOwn] = useState(false);
  const open = opened ?? own;
  const setOpen = onOpen ?? setOwn;
  // **Wer klickt, will tippen** – ohne den Sprung ins Feld kostet die Wahl zwei Klicks.
  const focus = useCallback((node: HTMLDivElement | null) => {
    node?.querySelector('input')?.focus();
  }, []);

  if (!on) return <span style={face}>{text}</span>;
  if (!open) {
    return (
      <Editable title={tip}>
        <button type="button" onClick={() => setOpen(true)}
          style={{ ...DOC_FIELD, ...face, cursor: 'pointer', textAlign: 'left',
                   maxWidth: '100%' }}>
          {text}
        </button>
      </Editable>
    );
  }
  return (
    <div ref={focus} style={{ minWidth: 0 }}>
      <Editable as="div" style={{ minWidth: 190 }}>
        <ObjectSelect<T>
          value={value} selected={selected} placeholder={placeholder} find={find}
          onChange={(n, option) => { setOpen(false); onChange(n, option); }}
        />
      </Editable>
    </div>
  );
}

/**
 * **Eine Liste von Belegen** – gesucht auf dem Server (`SearchSelect.search`), die
 * Vorschläge vorab (`options`). Ohne Kamera: eine Rechnung zieht keine Objektnummer.
 */
export function DocFind({ on, text, value, options, placeholder, emptyOption, face, tip,
                          search, onChange }: {
  on: boolean;
  text: ReactNode;
  value: string;
  options: { value: string; label: string }[];
  placeholder: string;
  emptyOption: string;
  face?: CSSProperties;
  tip?: string;
  search: (query: string) => Promise<{ value: string; label: string }[]>;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const focus = useCallback((node: HTMLDivElement | null) => {
    node?.querySelector('input')?.focus();
  }, []);

  if (!on) return <span style={face}>{text}</span>;
  if (!open) {
    return (
      <Editable title={tip} style={{ minWidth: MIN_PICK }}>
        <button type="button" onClick={() => setOpen(true)}
          style={{ ...DOC_FIELD, ...face, cursor: 'pointer', textAlign: 'left',
                   maxWidth: '100%' }}>
          {text}
        </button>
      </Editable>
    );
  }
  return (
    <div ref={focus} style={{ minWidth: 0 }}>
      <Editable as="div" style={{ minWidth: 220 }}>
        <SearchSelect value={value} options={options} placeholder={placeholder}
          emptyOption={emptyOption} search={search}
          onChange={(v) => { setOpen(false); onChange(v); }} />
      </Editable>
    </div>
  );
}

/** **Der Abstand zwischen zwei Abschnitten** – er gehört der Gattung, nicht der Aufrufstelle. */
const SECTION_GAP = 30;

/**
 * **Ein Abschnitt des Belegs** – ein ruhiger Kopf (Titel links, eine leise Auskunft
 * rechts), keine Leiste, kein Punkt: wie weit der Beleg ist, sagen die Stationen oben.
 * Eingefrorene Abschnitte bleiben offen sichtbar – es wird nichts zusammengeklappt.
 */
export function Section({ title, aside, first, children }: {
  title: string;
  aside?: ReactNode;
  first?: boolean;
  children: ReactNode;
}) {
  return (
    <section data-fb-section={title} style={{ marginTop: first ? 0 : SECTION_GAP, minWidth: 0 }}>
      <header className="flex items-baseline justify-between" style={{
        gap: 12, margin: '0 0 14px', font: '600 14px var(--font-display)',
        letterSpacing: '-.01em', color: 'var(--fg-1)',
      }}>
        <span>{title}</span>
        {aside && (
          <small style={{ font: '400 12.5px var(--font-body)', color: 'var(--fg-3)',
                          textAlign: 'right' }}>{aside}</small>
        )}
      </header>
      {children}
    </section>
  );
}

/** **Beschriftung über dem Wert** – die Anatomie jeder benannten Angabe dieses Belegs. */
export function Stacked({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={LABEL}>{label}</span>
      {children}
    </div>
  );
}

/** Eine Pflichtangabe, die fehlt – klein, rot, an ihrer Stelle. Erfunden wird nichts. */
export function Missing({ what }: { what: string }) {
  return <span style={{ ...LABEL, color: 'var(--danger)' }}>{what} fehlt</span>;
}

/**
 * **Eine leise Auskunft** – die Blase steht darüber; `width: fit-content` hält das Element
 * so breit wie seinen Text.
 */
export function Note({ tip, color, children }: {
  tip?: string | null; color?: string; children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center"
      style={{ gap: 6, fontSize: 11.5, color: color ?? 'var(--fg-3)', width: 'fit-content',
               flex: 'none', minWidth: 0 }}
      {...(tip ? { 'data-tip': tip } : {})}>
      {children}
    </span>
  );
}

/**
 * **Ein Kasten, in dem etwas erfasst wird** – grau getönt, ohne Rahmen: die Offerte des
 * Lieferanten, die Lieferantenrechnung, der Ausfuhrnachweis, eine Zahlung.
 */
export function FieldBox({ children, tone }: {
  children: ReactNode;
  /** Ein Hinweis, der eine Entscheidung verlangt (Abweichung, Nachweis fehlt). */
  tone?: 'warning';
}) {
  return (
    <div className="flex flex-col" style={{
      gap: 10, padding: '10px 12px', borderRadius: 'var(--r-md)', minWidth: 0,
      background: tone ? 'var(--warning-bg)' : 'var(--bg-2)',
      border: tone ? '1px solid var(--warning)' : '1px solid var(--border-1)',
    }}>{children}</div>
  );
}

/** Ein Satz ohne Zahl-Vorzeichen – für «0.42» aus «-0.42». */
export function unsigned(amount: string): string {
  return amount.trim().replace(/^[-+]/, '');
}
