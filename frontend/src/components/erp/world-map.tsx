'use client';

/**
 * **Die Welt, mit Code gemalt** – nur Linien und Ecken, keine Rundungen.
 *
 * Ein grobes Raster statt Umriss-Polygonen: jede Zelle ist ein 5°-Feld an ihrer echten
 * Position, die Form entsteht aus der Menge, und jede Zelle gehört genau einer Region.
 * Maske: 72 Spalten (Länge −180…+175) × 25 Zeilen (Breite 75…−50), ein Buchstabe je Zelle =
 * Region, `.` = Wasser. Grönland und die Antarktis fehlen, weil sie in keiner Region liegen.
 * Russland liegt fachlich in EUR (`services/geography.py`) – die Karte behauptet nichts anderes
 * als die Auflösung.
 */

import { useState } from 'react';

const REGION_BY_LETTER: Record<string, string> = {
  N: 'NAM', L: 'LATAM', E: 'EUR', A: 'ASIA', F: 'AFR', M: 'MEA', O: 'OCE',
};

// prettier-ignore
const MASK: string[] = [
  '...NNNNN..NNNNNNNNNNNNN................EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE', // 75–70
  '...NNNNNNNNNNNNNNNNNNNN........EE.....EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE', // 70–65
  '...NNNNNNNNNNNNNNNNNNNNNN......E.....EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE', // 65–60
  '...NNNNNNNNNNNNNNNNNNNNNN.........EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE', // 60–55
  '..........NNNNNNNNNNNNNNNN........EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE', // 55–50
  '...........NNNNNNNNNNNNN..........EEEEEEEEEEEEEAAAAAAAAAAAAAAAAA........', // 50–45
  '...........NNNNNNNNNNNN...........EEEEEEEEEEMMMAAAAAAAAAAAAAAAAAAA......', // 45–40
  '............NNNNNNNNNN............EEEEEEEEMMMMMMAAAAAAAAAAAAAAAAA.......', // 40–35
  '............NNNNNNNNN.............FFFFFFFFFMMMMMAAAAAAAAAAAAAAAAA.......', // 35–30
  '............NNNNNNNN.............FFFFFFFFFFFMMMMAAAAAAAAAAAAA...........', // 30–25
  '.............LLLL..LLL..........FFFFFFFFFFFFMMMMAAAAAAAAAAAAA...........', // 25–20
  '...............LLLL..LLLL.......FFFFFFFFFFFFFMM...AAAAAAAAA.............', // 20–15
  '.................LLL.LLLL.......FFFFFFFFFFFFFF....AAAAAAAAAAAA..........', // 15–10
  '...................LLLLLL........FFFFFFFFFFFFF.....AAAAAAAAAAA..........', // 10–5
  '....................LLLLLLL.......FFFFFFFFFFFF.........AAAAAAA..........', // 5–0
  '....................LLLLLLLLL........FFFFFFFF...........AAAAAAA.OOO.....', // 0–−5
  '.....................LLLLLLLLL........FFFFFFF............AAA...OOOO.....', // −5–−10
  '....................LLLLLLLLLL........FFFFFFF.................OOOO......', // −10–−15
  '.....................LLLLLLLL.........FFFFFFFFF............OOOOOOO......', // −15–−20
  '......................LLLLLLL.........FFFFFF.F............OOOOOOOOO.....', // −20–−25
  '......................LLLLL............FFFF...............OOOOOOOOO.....', // −25–−30
  '.....................LLLLL.............FFFF................OOOOOOOO.....', // −30–−35
  '.....................LLLL..............FF.......................OO....OO', // −35–−40
  '.....................LLL..............................................OO', // −40–−45
  '.....................LL.................................................', // −45–−50
];

type MapCell = { x: number; y: number; region: string };

/** Die Maske einmal in Zellen je Region übersetzt (Modul-Konstante – keine Laufzeitarbeit). */
const CELLS_BY_REGION: Record<string, MapCell[]> = (() => {
  const out: Record<string, MapCell[]> = {};
  MASK.forEach((row, y) => {
    [...row].forEach((ch, x) => {
      const region = REGION_BY_LETTER[ch];
      if (!region) return;
      (out[region] ??= []).push({ x, y, region });
    });
  });
  return out;
})();

/**
 * **Der Rahmen ist die Landmasse, nicht das Raster**: der Ausschnitt ist die Bounding-Box aller
 * Landzellen, abgeleitet statt nachjustiert.
 */
/**
 * **Eine Region = EIN Pfad** – ein Rechteck je Zelle, minimal überlappend, alle in einem ``d``
 * (der SVG-Filter ist teuer je Knoten).
 */
const PATH_BY_REGION: Record<string, string> = {};

const BOX = (() => {
  const all = Object.values(CELLS_BY_REGION).flat();
  const xs = all.map((c) => c.x);
  const ys = all.map((c) => c.y);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) + 1 - x, h: Math.max(...ys) + 1 - y };
})();

for (const [region, cells] of Object.entries(CELLS_BY_REGION)) {
  PATH_BY_REGION[region] = cells
    .map((c) => `M${c.x - 0.02} ${c.y - 0.02}h1.04v1.04h-1.04z`)
    .join('');
}

/**
 * **Wo liegt der Schwerpunkt einer Region?** – in Prozent der Kartenfläche, damit Beschriftung
 * und Zuweisung dort stehen, wo das Gebiet liegt. Median statt Mittel: er bleibt auf der Landmasse.
 */
export function regionAnchor(region: string): { x: number; y: number } {
  const cells = CELLS_BY_REGION[region] ?? [];
  if (!cells.length) return { x: 50, y: 50 };
  const mid = (v: number[]) => v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
  // Prozent des gezeichneten Ausschnitts (BOX), nicht des vollen Rasters.
  return {
    x: ((mid(cells.map((c) => c.x)) + 0.5 - BOX.x) / BOX.w) * 100,
    y: ((mid(cells.map((c) => c.y)) + 0.5 - BOX.y) / BOX.h) * 100,
  };
}

/**
 * Die Karte. Farbe und Auswahl kommen von aussen (die Gebietsansicht kennt die
 * Gesellschaften) – diese Datei kennt nur Geografie.
 */
export function WorldMap({ fill, stroke, selected, onSelect, title, label }: {
  /** Füllfarbe je Regions-Code. */
  fill: (region: string) => string;
  /** Randfarbe je Region – die Kontur der Landmasse. */
  stroke: (region: string) => string | null;
  selected?: string | null;
  onSelect?: (region: string) => void;
  /** Hover-Text je Region (z. B. «Europa · Inexxio AG»). */
  title?: (region: string) => string;
  /** Beschriftung IN der Fläche: Gebiet + wer es fakturiert. */
  label?: (region: string) => { title: string; sub: string; ink: string } | null;
}) {
  // Gleich eingefärbte Regionen derselben Gesellschaft: der Hover zeichnet die Region nach.
  const [hover, setHover] = useState<string | null>(null);

  return (
    <svg viewBox={`${BOX.x} ${BOX.y} ${BOX.w} ${BOX.h}`} width="100%" role="img" aria-label="Weltkarte der Gebietsaufteilung"
      // Eigene Rasterebene: beim Scrollen nur zusammengesetzt statt neu gefiltert.
      style={{ display: 'block', background: 'var(--bg-3)', willChange: 'transform', contain: 'paint' }}
      onMouseLeave={() => setHover(null)}>
      <defs>
        {/* Ecken leicht abrunden: weichzeichnen, dann die Alpha-Kante hart zurückschneiden – je
            Region verschmelzen die Zellen zu einer Fläche; zwischen Regionen bleibt eine Naht. */}
        <filter id="ix-map-round" x="-4%" y="-4%" width="108%" height="108%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.26" result="b" />
          <feColorMatrix in="b" type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9" />
        </filter>
      </defs>
      {Object.entries(PATH_BY_REGION).map(([region, d]) => {
        const ring = stroke(region);
        const marked = selected === region || hover === region;
        return (
          <g key={region} onClick={onSelect ? () => onSelect(region) : undefined}
            onMouseEnter={() => setHover(region)}
            filter="url(#ix-map-round)"
            style={{ cursor: onSelect ? 'pointer' : 'default' }}>
            {title && <title>{title(region)}</title>}
            <path d={d} fill={marked && ring ? ring : fill(region)} stroke="none" />
          </g>
        );
      })}
      {/* Die Zuordnung steht IN der Fläche – ausserhalb der Filter-Gruppe, damit die
          Weichzeichnung die Schrift nicht anfasst. */}
      {label && Object.keys(CELLS_BY_REGION).map((region) => {
        const l = label(region);
        if (!l) return null;
        const cells = CELLS_BY_REGION[region];
        const mid = (v: number[]) => v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
        const cx = mid(cells.map((c) => c.x)) + 0.5;
        const cy = mid(cells.map((c) => c.y)) + 0.5;
        // Unter dem Cursor ist die Fläche im kräftigen Ton der Gesellschaft – dort schreibt die
        // Beschriftung weiss.
        const ink = selected === region || hover === region ? '#fff' : l.ink;
        return (
          <g key={`l-${region}`} pointerEvents="none" textAnchor="middle">
            <text x={cx} y={cy - 0.35} fill={ink} style={{ font: '700 1.5px var(--font-body)' }}>
              {l.title}
            </text>
            <text x={cx} y={cy + 1.5} fill={ink} opacity={0.8} style={{ font: '500 1.35px var(--font-body)' }}>
              {l.sub}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
