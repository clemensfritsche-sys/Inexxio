'use client';

/**
 * **Eine Instanz in einem Prozessschritt – EINE Zeile, überall dieselbe** (Testnotiz #642).
 *
 * Sie stand zweimal fast gleich in den Panels (Bewegung, Aussondern), jedes Mal als eigener
 * Kasten mit Rahmen, in der Alt-Palette und mit dem Wort «Instanz» in jeder Zeile – obwohl
 * unter einer Instanz-Liste ohnehin jede Zeile eine Instanz ist. Drei Angaben tragen die
 * Aussage, in der Leserichtung des ganzen ERP:
 *
 *     Objektnummer · Menge · Zustand        (+ Standort, wo er zählt)
 *
 * Getrennt wird mit einer **Haarlinie** statt mit einem Kasten je Zeile – Struktur vor
 * Fläche, wie überall.
 *
 * **Ohne Zustand** (Testnotiz #659): in einem Modul ist die Frage, WELCHE Instanzen es
 * bearbeitet – und wo sie jetzt liegen. In welchem Zustand das Material ist, sagt der
 * Fluss direkt darüber (die Materialzeile auf der Kante, in ihrer Ampelfarbe). Eine Badge
 * je Zeile wiederholte das nur, und zwar an der Stelle, an der es am wenigsten zählt.
 */

import type { ElementType } from 'react';
import type { OrderInstance } from '@/types';
import { formatQty } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';

export function InstanceRow({ instance, unit, where, whereIcon }: {
  instance: OrderInstance;
  /** Mengeneinheit des Artikels (Stk, kg …). */
  unit?: string | null;
  /** Standort – nur dort zeigen, wo er die Aussage des Schritts ist (Bewegung). */
  where?: string | null;
  whereIcon?: ElementType;
}) {
  const Where = whereIcon;
  return (
    <div style={S.row}>
      <ObjId value={instance.object_id} />
      <span style={S.qty}>
        {formatQty(Number(instance.quantity ?? 0))}{unit ? ` ${unit}` : ''}
      </span>
      <span style={{ flex: 1 }} />
      {where !== undefined && (
        <span style={S.where}>
          {Where && <Where size={12} style={{ flexShrink: 0 }} />}
          {where ?? '—'}
        </span>
      )}
    </div>
  );
}

/** Die Liste dazu: Haarlinien statt Kästen – der Container ist die Modul-Karte. */
export function InstanceRows({ children }: { children: React.ReactNode }) {
  return <div style={S.list}>{children}</div>;
}

const S: Record<string, React.CSSProperties> = {
  list: {
    display: 'flex', flexDirection: 'column', maxHeight: 320, overflowY: 'auto',
    border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', background: '#fff',
  },
  row: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
    borderTop: '1px solid var(--border-1)', minWidth: 0,
  },
  qty: {
    font: '500 12.5px var(--font-body)', color: 'var(--fg-3)',
    fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
  },
  where: {
    display: 'inline-flex', alignItems: 'center', gap: 5, minWidth: 0,
    font: '500 12px var(--font-body)', color: 'var(--fg-3)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
};
