'use client';

import { Input } from '@/components/form/field';
import { inputClass } from './controls';
import { ORDER_DATE_KINDS, type OrderDateKind } from '@/lib/vocab';

/**
 * **Das eine Datum am Auftrag** (Projektakte `docs/konzept/aufgaben.md` §5): «ab» am Start,
 * «bis» am Ende – nie beide. Wer das eine füllt, ersetzt das andere; leer = so schnell wie
 * möglich. Im Entwurf ein Wert des Entwurfs, am laufenden Auftrag ein Befehl (`setOrderDate`).
 */
export interface OrderDate {
  kind: OrderDateKind;
  /** «JJJJ-MM-TT» – so, wie das Datumsfeld es gibt. */
  on: string;
}

const TIP: Record<OrderDateKind, string> = {
  from: 'Ab: nicht vor diesem Tag – vorher gibt es keine Aufgabe. Ersetzt «bis».',
  until: 'Bis: fertig bis zu diesem Tag (Liefertermin) – die Aufgaben reihen sich nach ihm ein. Ersetzt «ab».',
};

export function OrderDateField({ which, value, onChange, readOnly = false }: {
  which: 'start' | 'end';
  value: OrderDate | null;
  onChange: (next: OrderDate | null) => void;
  readOnly?: boolean;
}) {
  const kind: OrderDateKind = which === 'start' ? 'from' : 'until';
  const mine = value?.kind === kind ? value.on : '';
  // Steht das Datum am anderen Ende, bleibt dieses Feld leer – und still, solange nur gelesen wird.
  if (readOnly && !mine) return null;
  return (
    <div className="flex items-center gap-2" data-tip={TIP[kind]}
      style={{ opacity: mine ? 1 : 0.6 }}>
      <span className="text-[13px]" style={{ color: 'var(--fg-2)' }}>{ORDER_DATE_KINDS[kind]}</span>
      <div style={{ width: 150 }}>
        <Input name={`date.${kind}`} type="date" value={mine} readOnly={readOnly}
          className={inputClass(readOnly ? 'read' : 'normal')}
          onChange={(v) => onChange(v ? { kind, on: v } : value?.kind === kind ? null : value)} />
      </div>
    </div>
  );
}
