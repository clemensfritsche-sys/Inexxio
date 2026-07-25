'use client';

/**
 * **Standort-Kette** – die Antwort auf «wo genau liegt das?».
 *
 * Ein Standort ist bei Inexxio eine Referenz auf ein anderes Objekt; verschachtelt ergibt
 * das eine Kette, die am geografischen Blatt endet:
 *
 *     Schraube 100000042 → Behälter 100000007 → Halle Nord 100000003 → Musterstrasse 1, 8000 Zürich
 *
 * Statt nur den unmittelbaren Halter zu zeigen, rendert diese Karte den ganzen Pfad –
 * jede Station mit ihrem Symbol, klickbar (ausser der Anschrift, die keine Objektnummer
 * trägt). Die Kette kommt fertig aufgelöst vom Backend (``InstanceResponse.location_path``).
 */

import { MapPin, CornerDownRight } from 'lucide-react';
import type { LocationType } from '@/types';
import { LOCATION_META, locationTypeLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { useErpNav } from '@/components/erp/obj-id';

export type LocationHop = {
  location_type: string;
  location_id?: number | null;
  label?: string | null;
};

export function LocationPathCard({ path, self }: {
  path: LocationHop[] | null | undefined;
  /** Objektnummer der Instanz selbst – als Startpunkt der Kette gezeigt. */
  self?: number | null;
}) {
  const nav = useErpNav();
  // Die Kette ist eine abgeleitete Dekoration – sie darf das Instanz-Detail unter keinen
  // Umständen zerlegen. Darum defensiv: nur brauchbare Stationen (mit Typ) rendern und
  // alles andere still verwerfen, statt auf ein Feld zu vertrauen.
  const hops = Array.isArray(path)
    ? path.filter((h): h is LocationHop => !!h && typeof h.location_type === 'string')
    : [];
  // Ohne echte Verschachtelung (nur unmittelbarer Halter) lohnt die Karte nicht – die
  // Standort-Kachel oben sagt dann bereits alles.
  if (hops.length < 2) return null;

  return (
    <div style={ST.card}>
      <div style={ST.head}>
        <MapPin size={16} style={{ color: 'var(--fg-3)' }} />
        <h3 style={ST.title}>Standort · Kette</h3>
        <span style={ST.pill}>{hops.length} Stationen</span>
      </div>

      <ol style={ST.list}>
        {self != null && (
          <li style={{ ...ST.row, paddingLeft: 0 }}>
            <span style={ST.dot} />
            <span style={ST.selfLabel}>Diese Instanz</span>
            <span style={ST.nr}>{fmtObjId(self)}</span>
          </li>
        )}
        {hops.map((hop, i) => {
          const isAddress = hop.location_type === 'address';
          const Icon = isAddress
            ? MapPin
            : (LOCATION_META[hop.location_type as LocationType]?.icon ?? MapPin);
          const clickable = !isAddress && hop.location_id != null;
          return (
            <li
              key={`${hop.location_type}:${hop.location_id ?? i}`}
              style={{ ...ST.row, paddingLeft: (self != null ? i + 1 : i) * 14 }}
            >
              <CornerDownRight size={13} style={ST.arrow} />
              <Icon size={14} style={{ color: isAddress ? 'var(--fg-3)' : 'var(--accent)', flexShrink: 0 }} />
              <button
                type="button"
                onClick={clickable ? () => nav?.(hop.location_id as number) : undefined}
                disabled={!clickable}
                style={{ ...ST.label, cursor: clickable ? 'pointer' : 'default' }}
                title={isAddress ? 'Anschrift – kein Datensatz' : locationTypeLabel(hop.location_type)}
              >
                {hop.label ?? locationTypeLabel(hop.location_type)}
              </button>
              {/* Eine Anschrift trägt keine Objektnummer – dann bleibt die Spalte leer. */}
              <span style={ST.nr}>{hop.location_id != null ? fmtObjId(hop.location_id) : ''}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

const ST: Record<string, React.CSSProperties> = {
  card: {
    border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 18,
    background: '#fff', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 30,
  },
  head: { display: 'flex', alignItems: 'center', gap: 8 },
  title: { font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 },
  pill: {
    marginLeft: 'auto', font: '600 11px var(--font-body)', color: 'var(--accent-ink)',
    background: 'var(--accent-soft)', padding: '2px 9px', borderRadius: 'var(--r-pill)',
  },
  list: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 2 },
  row: { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 0' },
  arrow: { color: 'var(--fg-4)', flexShrink: 0 },
  dot: {
    width: 7, height: 7, borderRadius: 999, background: 'var(--inexxio-red)',
    flexShrink: 0, marginLeft: 3, marginRight: 4,
  },
  selfLabel: { font: '700 13.5px var(--font-body)', color: 'var(--fg-1)', flex: 1, minWidth: 0 },
  label: {
    font: '600 13.5px var(--font-body)', color: 'var(--fg-1)', flex: 1, minWidth: 0,
    textAlign: 'left', background: 'none', border: 'none', padding: 0,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  nr: {
    fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-4)',
    fontVariantNumeric: 'tabular-nums', flexShrink: 0,
  },
};
