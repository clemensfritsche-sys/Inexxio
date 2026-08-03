'use client';

/**
 * **Das Material-Journal – «was ist passiert»** (ADR 007).
 *
 * Jede Zeile ist eine **Buchung**: wann, was, wie viel, Zustand danach – chronologisch von
 * neu nach alt (das Jüngste interessiert zuerst), unveränderlich. Dieselbe Komponente dient
 * beiden Richtungen der einen Geschichte: am **Instanz**-Detail ist der Chip der beteiligte
 * Auftrag (wohin ging es), am **Auftrags**-Detail die betroffene Instanz (welche Menge).
 *
 * Der Zustand trägt die Ampelfarbe aus derselben Projektion wie überall
 * (`instanceStatusConfig`) – ein Wort, eine Farbe, an jeder Stelle gleich.
 */

import { TriangleAlert } from 'lucide-react';
import { instanceStatusConfig } from '@/lib/process';
import { useErpNav } from '@/components/erp/obj-id';
import { formatObjectId, localDateTime } from '@/lib/utils';

export type MoveRow = {
  at: string;
  kind: string;
  quantity: number;
  quality?: string | null;
  disposition?: string | null;
  order_object_id?: number | null;
  order_name?: string | null;
  instance_object_id?: number | null;
  note?: string | null;
};

const MOVE_LABEL: Record<string, string> = {
  created: 'Entstanden', opening: 'Eröffnungsbilanz', taken: 'Übernommen',
  returned: 'Zurückgegeben', released: 'Ans Lager freigegeben', sold: 'Verkauft',
  consumed: 'Verbaut', scrapped: 'Verschrottet', blocked: 'Gesperrt',
  unblocked: 'Entsperrt',
};

export function MoveJournal({ rows, chip = 'order' }: {
  rows: MoveRow[];
  /** Welche Seite der Buchung der Chip nennt: den Auftrag (Instanz-Detail) oder die
   *  Instanz (Auftrags-Detail). */
  chip?: 'order' | 'instance';
}) {
  const nav = useErpNav();
  if (rows.length === 0) return null;
  return (
    <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
      background: '#fff', overflow: 'hidden' }}>
      {[...rows].reverse().map((m, i) => {
        const cfg = instanceStatusConfig(m.quality, m.disposition, false);
        const Icon = cfg.icon;
        const refId = chip === 'order' ? m.order_object_id : m.instance_object_id;
        const refLabel = chip === 'order' ? (m.order_name ?? 'Auftrag') : null;
        return (
          <div key={`${m.at}-${i}`} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px',
            borderBottom: i < rows.length - 1 ? '1px solid var(--border-1)' : 'none',
            font: '500 13px var(--font-body)', color: 'var(--fg-2)', flexWrap: 'wrap',
          }}>
            <span style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)',
              width: 118, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
              {localDateTime(m.at)}
            </span>
            <span style={{ fontWeight: 600, color: 'var(--fg-1)' }}>
              {MOVE_LABEL[m.kind] ?? m.kind}
            </span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{m.quantity}</span>
            <span title={cfg.label} style={{ display: 'inline-flex', alignItems: 'center',
              gap: 4, color: cfg.color, font: '500 12px var(--font-body)' }}>
              {Icon && <Icon size={12} />}{cfg.label}
            </span>
            {refId != null && (
              <button type="button" className="erp-chip"
                onClick={() => nav?.(refId)}
                title={`${refLabel ?? 'Instanz'} ${formatObjectId(refId)} öffnen`}
                style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center',
                  gap: 6, font: '500 12px var(--font-body)', cursor: 'pointer' }}>
                {refLabel && (
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap', maxWidth: 160 }}>{refLabel}</span>
                )}
                <span style={{ font: '500 11px var(--font-mono), monospace',
                  fontVariantNumeric: 'tabular-nums', color: 'var(--fg-4)' }}>
                  {formatObjectId(refId)}
                </span>
              </button>
            )}
            {m.note === '!unbalanced' && (
              <span title="Buchung ohne ausreichenden Quell-Topf – bitte melden"
                style={{ color: 'var(--danger)', display: 'inline-flex' }}>
                <TriangleAlert size={13} />
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
