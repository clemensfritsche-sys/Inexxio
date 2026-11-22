'use client';

/**
 * ►►► **Die eine Weltkarte des ERP** – Länder als echte Umrisse (`lib/world-map.ts`, Natural Earth,
 * Equal Earth). ◄◄◄ Dieselbe Karte für die Website-Statistik (Besuche je Land) und die Gebiete
 * (welche Gesellschaft welches Land fakturiert): wer sie nutzt, sagt je Land Farbe, Hover und Klick;
 * Punkte und Beschriftungen gibt er als `children` mit, in Kartenkoordinaten (`WORLD.centers`,
 * `WORLD.anchors`) und mit `unit` = eine Bildschirm-Einheit des Ausschnitts.
 *
 * Ausschnitt «Welt» oder «Europa» (`zoomable`): derselbe Inhalt, nur ein anderer `viewBox`; Linien
 * bleiben gleich dünn (`non-scaling-stroke`).
 */

import { useState } from 'react';
import { WORLD } from '@/lib/world-map';
import { Segmented } from '@/components/erp/controls';

export { WORLD };

export type GeoView = keyof typeof WORLD.views;

export function GeoMap({ fill, opacity, stroke, tip, onSelect, label, zoomable = false, initial = 'world', children }: {
  /** Fläche je Land (ISO-2); ein Land ohne Angabe ist neutral. */
  fill: (code: string) => string;
  opacity?: (code: string) => number;
  /** Kontur je Land – sonst die Fläche dahinter (Haarlinie zwischen den Ländern). */
  stroke?: (code: string) => string | undefined;
  tip?: (code: string) => string;
  onSelect?: (code: string) => void;
  /** Name der Karte für Screenreader. */
  label: string;
  zoomable?: boolean;
  initial?: GeoView;
  /** Was über den Ländern liegt – `unit` = Massstab des Ausschnitts (1 in der Welt). */
  children?: (unit: number, view: GeoView) => React.ReactNode;
}) {
  const [view, setView] = useState<GeoView>(initial);
  const [x, y, w, h] = WORLD.views[view];
  const unit = w / WORLD.w;
  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`${x} ${y} ${w} ${h}`} width="100%" role="img" aria-label={label}
        style={{ display: 'block', background: 'var(--bg-2)' }}>
        {Object.entries(WORLD.paths).map(([code, d]) => (
          <path key={code} d={d} fill={fill(code)} fillOpacity={opacity?.(code) ?? 1}
            stroke={stroke?.(code) ?? 'var(--bg-1)'} strokeWidth={0.7} vectorEffect="non-scaling-stroke"
            data-tip={tip?.(code)} onClick={onSelect ? () => onSelect(code) : undefined}
            style={onSelect ? { cursor: 'pointer' } : undefined} />
        ))}
        {children?.(unit, view)}
      </svg>
      {zoomable && (
        <div style={{ position: 'absolute', top: 8, right: 8 }}>
          <Segmented value={view} onChange={(v) => setView(v as GeoView)}
            options={[{ value: 'world', label: 'Welt' }, { value: 'europe', label: 'Europa' }]} />
        </div>
      )}
    </div>
  );
}
