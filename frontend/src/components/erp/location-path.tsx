'use client';

/**
 * **Standort** – die einzige Standort-Anzeige der Instanz («wo genau liegt das?»).
 *
 * Ein Standort ist bei Inexxio eine Referenz auf ein anderes Objekt; verschachtelt ergibt
 * das eine Kette, die am geografischen Blatt (Anschrift) endet:
 *
 *     Behälter 100000007 → Halle Nord 100000003 → Musterstrasse 1, 8000 Zürich
 *
 * Die Kette beginnt beim **unmittelbaren Halter** – NICHT bei der Instanz selbst (die ist
 * ja bereits geöffnet). Jede Station trägt ihr Symbol und ist klickbar (ausser der
 * Anschrift, die keine Objektnummer hat). Die Kette kommt fertig aufgelöst vom Backend
 * (``InstanceResponse.location_path``). Diese Karte ersetzt die frühere Standort-Kachel
 * vollständig und zeigt auch den Einzel-Halter bzw. «Nicht festgelegt».
 */

import { MapPin, CornerDownRight } from 'lucide-react';
import type { LocationType } from '@/types';
import { LOCATION_META, locationTypeLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { useErpNav } from '@/components/erp/obj-id';
import { TileShell } from '@/components/erp/fields';

export type LocationHop = {
  location_type: string;
  location_id?: number | null;
  label?: string | null;
};

export function LocationPathCard({ path, distributedCount, style }: {
  path: LocationHop[] | null | undefined;
  /** Ist die Charge auf mehrere Standorte verteilt: deren Anzahl (Aufteilung folgt darunter). */
  distributedCount?: number | null;
  /** Platzierung im Kachel-Raster der Instanz (volle Breite). */
  style?: React.CSSProperties;
}) {
  const nav = useErpNav();
  // Defensiv: nur brauchbare Stationen (mit Typ) rendern – die Kette darf das Detail
  // nie zerlegen (Altdaten/gelöschter Halter kosten höchstens die Kette, nicht die Ansicht).
  const hops = Array.isArray(path)
    ? path.filter((h): h is LocationHop => !!h && typeof h.location_type === 'string')
    : [];
  const distributed = (distributedCount ?? 0) > 1;

  return (
    <TileShell icon={MapPin} label="Standort" style={style}>
      {distributed && (
        <div style={ST.note}>Auf {distributedCount} Standorte verteilt – Aufteilung siehe unten.</div>
      )}

      {hops.length === 0 ? (
        <div style={ST.empty}>Nicht festgelegt</div>
      ) : (
        <ol style={ST.list}>
          {hops.map((hop, i) => {
            const isAddress = hop.location_type === 'address';
            const Icon = isAddress
              ? MapPin
              : (LOCATION_META[hop.location_type as LocationType]?.icon ?? MapPin);
            const clickable = !isAddress && hop.location_id != null;
            return (
              <li
                key={`${hop.location_type}:${hop.location_id ?? i}`}
                style={{ ...ST.row, paddingLeft: i * 16 }}
              >
                {i > 0 && <CornerDownRight size={13} style={ST.arrow} />}
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
      )}
    </TileShell>
  );
}

const ST: Record<string, React.CSSProperties> = {
  note: { font: '500 12.5px var(--font-body)', color: 'var(--fg-3)', marginTop: 6 },
  empty: { font: '500 13.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 6 },
  list: { listStyle: 'none', margin: '4px 0 0', padding: 0, display: 'flex', flexDirection: 'column', gap: 2 },
  row: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' },
  arrow: { color: 'var(--fg-4)', flexShrink: 0 },
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
