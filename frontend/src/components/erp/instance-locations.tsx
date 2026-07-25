'use client';

import { MapPin } from 'lucide-react';
import type { Instance, LocationType } from '@/types';
import { LOCATION_META } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';

/**
 * **Read-only** Standort-Verteilung einer Charge: liegt eine Charge (EINE Objektnummer)
 * physisch auf mehreren Standorten (300 @ Band A · 700 @ Band B), werden die Teilmengen
 * hier gezeigt. Das **Verteilen** selbst geschieht ausschliesslich über einen regulären
 * Auftrag + Prozessschritt (Bewegen) – NICHT an der Instanz. Bei nur EINEM Standort genügt
 * die «Standort»-Kachel, dann rendert diese Karte nichts.
 */
export function InstanceLocationsCard({ instance }: { instance: Instance }) {
  const slices = instance.locations ?? [];
  if (slices.length <= 1) return null;

  return (
    <div style={ST.card}>
      <div style={ST.head}>
        <MapPin size={16} style={{ color: 'var(--fg-3)' }} />
        <h3 style={ST.title}>Standort · verteilt</h3>
        <span style={ST.pill}>{slices.length} Standorte</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {slices.map((s) => {
          const Icon = LOCATION_META[s.location_type as LocationType]?.icon ?? MapPin;
          return (
            <div key={`${s.location_type}:${s.location_id ?? 'place'}`} style={ST.slice}>
              <Icon size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <span style={ST.sliceLabel}>{s.location_label ?? (s.location_id != null ? fmtObjId(s.location_id) : 'Ort')}</span>
              {/* Ein Ort trägt keine Objektnummer – dann bleibt die Nummern-Spalte leer. */}
              <span style={ST.sliceNr}>{s.location_id != null ? fmtObjId(s.location_id) : ''}</span>
              <span style={ST.sliceQty}>{s.quantity}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const ST: Record<string, React.CSSProperties> = {
  card: { border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 18, background: '#fff', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 30 },
  head: { display: 'flex', alignItems: 'center', gap: 8 },
  title: { font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 },
  pill: { marginLeft: 'auto', font: '600 11px var(--font-body)', color: 'var(--accent-ink)', background: 'var(--accent-soft)', padding: '2px 9px', borderRadius: 'var(--r-pill)' },
  slice: { display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)' },
  sliceLabel: { font: '600 13.5px var(--font-body)', color: 'var(--fg-1)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  sliceNr: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' },
  sliceQty: { font: '700 14px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', minWidth: 44, textAlign: 'right' },
};
