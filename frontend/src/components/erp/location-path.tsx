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
 * (``InstanceResponse.location_path``).
 *
 * **Verteilte Charge (Notiz #147):** liegt EINE Objektnummer physisch auf mehreren
 * Standorten (990 @ Eingang · 10 @ Band A), gibt es keinen einen Halter – also auch keine
 * eine Kette. Dann steht die **Aufteilung an der Stelle der Kette**, im selben Container:
 * je Standort eine Zeile mit Menge. Vorher hing sie als zweite Karte «Standort · verteilt»
 * darunter – dieselbe Frage, zweimal beantwortet, und die Kette darüber galt ohnehin nur
 * für die grösste Teilmenge. Das **Verteilen** selbst geschieht ausschliesslich über einen
 * regulären Auftrag + Bewegungsschritt, nie hier.
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

export type LocationSlice = {
  location_type: string;
  location_id: number;
  quantity: number;
  location_label?: string | null;
};

export function LocationPathCard({ path, slices, unit, style }: {
  path: LocationHop[] | null | undefined;
  /** Teilmengen einer verteilten Charge; ab zwei Einträgen ersetzen sie die Kette. */
  slices?: LocationSlice[] | null;
  unit?: string;
  /** Platzierung im Kachel-Raster der Instanz (volle Breite). */
  style?: React.CSSProperties;
}) {
  const nav = useErpNav();
  // Defensiv: nur brauchbare Stationen (mit Typ) rendern – die Kette darf das Detail
  // nie zerlegen (Altdaten/gelöschter Halter kosten höchstens die Kette, nicht die Ansicht).
  const hops = Array.isArray(path)
    ? path.filter((h): h is LocationHop => !!h && typeof h.location_type === 'string')
    : [];
  const parts = (slices ?? []).filter((s) => !!s && s.location_id != null);
  const distributed = parts.length > 1;

  return (
    <TileShell
      icon={MapPin} label="Standort" style={style}
      right={distributed ? <span style={ST.pill}>verteilt · {parts.length} Standorte</span> : undefined}
    >
      {distributed ? (
        <ol style={ST.list}>
          {parts.map((s) => {
            const Icon = LOCATION_META[s.location_type as LocationType]?.icon ?? MapPin;
            return (
              <li key={`${s.location_type}:${s.location_id}`} style={ST.row}>
                <Icon size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                <button type="button" onClick={() => nav?.(s.location_id)}
                  style={{ ...ST.label, cursor: 'pointer' }}
                  title={locationTypeLabel(s.location_type)}>
                  {s.location_label ?? locationTypeLabel(s.location_type)}
                </button>
                <span style={ST.nr}>{fmtObjId(s.location_id)}</span>
                <span style={ST.qty}>{s.quantity}{unit ? <span style={ST.unit}>{unit}</span> : null}</span>
              </li>
            );
          })}
        </ol>
      ) : hops.length === 0 ? (
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
  pill: {
    font: '600 11px var(--font-body)', color: 'var(--accent-ink)', background: 'var(--accent-soft)',
    padding: '2px 9px', borderRadius: 'var(--r-pill)', textTransform: 'none', letterSpacing: 0,
  },
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
  qty: {
    font: '700 13.5px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums',
    flexShrink: 0, minWidth: 46, textAlign: 'right',
  },
  unit: { font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', marginLeft: 3 },
};
