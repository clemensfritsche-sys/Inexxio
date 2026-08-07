'use client';

import type { InstanceSummary } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { kindLabel } from '@/lib/record-status';

/**
 * Der Bestand eines Artikels: seine Instanzen mit ihrer **gezählten** Menge.
 *
 * Diese Liste ist eine reine Summierung – eine Filterung über Einzelinstanzen, keine
 * eigene Datenquelle. Was hier als Menge steht, ist die Anzahl der Einzelinstanzen der
 * jeweiligen Instanz; sie liegt an keiner Stelle als Feld herum.
 *
 * **Kein Zustand je Zeile** (Testnotiz #675): eine Instanz ist eine Gruppe, und die hat
 * keinen. Wer die Zustände sehen will, öffnet sie – dort steht einer je Stück.
 */
export function InstanceList({ rows }: { rows: InstanceSummary[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-fg-3">Noch keine Instanzen zu diesem Artikel.</p>;
  }

  const total = rows.reduce((n, r) => n + r.quantity, 0);

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 pb-2 text-xs text-fg-3">
        <span>{rows.length} Instanz{rows.length !== 1 ? 'en' : ''}</span>
        <span>·</span>
        <span>{total} Einzelinstanz{total !== 1 ? 'en' : ''}</span>
      </div>
      {rows.map((r) => (
        <div key={r.id} className="flex items-center gap-3 py-2 border-t border-border-1">
          <ObjId value={r.object_id} />
          <span className="text-sm text-fg-3">{kindLabel(r.kind)}</span>
          <span className="ml-auto text-sm tabular-nums">{r.quantity}</span>
        </div>
      ))}
    </div>
  );
}
