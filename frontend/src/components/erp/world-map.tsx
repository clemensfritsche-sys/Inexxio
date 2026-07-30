'use client';

/**
 * **Die Welt, mit Code gemalt** (Testnotiz #322) – nur Linien und Ecken, keine Rundungen.
 *
 * Die Gebietskarte war eine Reihe rechteckiger Kacheln, grob nach Himmelsrichtung
 * angeordnet. Das war eine *Tabelle, die so tut als wäre sie eine Karte*: man musste die
 * Zuordnung lesen, statt sie zu sehen. Hier ist es umgekehrt.
 *
 * **Warum ein Raster und keine Umriss-Polygone.** Ein Kontinent aus zehn Stützpunkten
 * bleibt ein Fleck – erkennbar wird eine Weltkarte erst über die *Verhältnisse* (wo liegt
 * was zu was). Ein grobes Raster liefert die geschenkt: jede Zelle ist ein 5°-Feld, seine
 * Position ist die echte geografische Position, und die Form entsteht aus der Menge. Das
 * Ergebnis ist strikt angular (nur Zellkanten), ohne dass irgendwo eine Kurve gerundet
 * werden müsste – genau das Gewünschte, und nebenbei ehrlich: eine Zelle gehört genau
 * einer Region, es gibt keine gemalte Grauzone.
 *
 * Die Maske ist Handarbeit: 72 Spalten (Länge −180…+175) × 25 Zeilen (Breite 75…−50).
 * Ein Buchstabe je Zelle = die Region, `.` = Wasser. Grönland und die Antarktis fehlen
 * bewusst – sie liegen in **keiner** Region (sie fielen auf den Betreiber zurück), und
 * eine Fläche einzufärben, die keiner Region gehört, wäre eine gemalte Behauptung.
 *
 * Russland liegt fachlich in EUR (siehe `services/geography.py`) und ist darum bis in den
 * Osten europäisch eingefärbt – das ist zugleich geografisch wahr (Russland ist beides)
 * und modell-wahr. Die Karte darf nicht anders behaupten als die Auflösung entscheidet.
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

export type MapCell = { x: number; y: number; region: string };

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

const COLS = 72;
const ROWS = MASK.length;

/**
 * Die Karte. Farbe und Auswahl kommen von aussen (die Gebietsansicht kennt die
 * Gesellschaften) – diese Datei kennt nur Geografie.
 */
export function WorldMap({ fill, stroke, selected, onSelect, title }: {
  /** Füllfarbe je Regions-Code. */
  fill: (region: string) => string;
  /** Randfarbe je Region – die Kontur der Landmasse. */
  stroke: (region: string) => string | null;
  selected?: string | null;
  onSelect?: (region: string) => void;
  /** Hover-Text je Region (z. B. «Europa · Inexxio AG»). */
  title?: (region: string) => string;
}) {
  // Gehören mehrere Regionen derselben Gesellschaft, sind sie gleich eingefärbt – dann ist
  // ohne Hover nicht zu sehen, wo Asien aufhört. Der Hover zeichnet die Region nach; das
  // ist zugleich die Erkundung («welches Gebiet ist das?»), ohne Fläche zu kosten.
  const [hover, setHover] = useState<string | null>(null);

  return (
    <svg viewBox={`0 0 ${COLS} ${ROWS}`} width="100%" role="img" aria-label="Weltkarte der Gebietsaufteilung"
      style={{ display: 'block', background: 'var(--bg-3)' }}
      onMouseLeave={() => setHover(null)}>
      <defs>
        {/* **Ecken leicht abrunden** (Testnotiz #336) – ohne die Zellen zu Punkten zu
            machen: weichzeichnen, dann die Alpha-Kante hart zurückschneiden. Weil das je
            Region auf die GANZE Gruppe wirkt, verschmelzen ihre Zellen zu EINER Fläche,
            deren Aussenkante gerundet ist; die Innenkanten verschwinden. Nebeneffekt, der
            genau zu #340 passt: zwei benachbarte Regionen runden jede für sich, wodurch
            zwischen ihnen eine sichtbare Naht entsteht – die fehlende «Abgrenzung». */}
        <filter id="ix-map-round" x="-4%" y="-4%" width="108%" height="108%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.26" result="b" />
          <feColorMatrix in="b" type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9" />
        </filter>
      </defs>
      {Object.entries(CELLS_BY_REGION).map(([region, cells]) => {
        const ring = stroke(region);
        const marked = selected === region || hover === region;
        return (
          <g key={region} onClick={onSelect ? () => onSelect(region) : undefined}
            onMouseEnter={() => setHover(region)}
            filter="url(#ix-map-round)"
            style={{ cursor: onSelect ? 'pointer' : 'default' }}>
            {title && <title>{title(region)}</title>}
            {cells.map((c) => (
              // Zellen überlappen minimal, damit der Weichzeichner sie sauber zu einer
              // Fläche zusammenzieht statt Perlen zu bilden.
              <rect key={`${c.x}-${c.y}`} x={c.x - 0.02} y={c.y - 0.02} width={1.04} height={1.04}
                fill={marked && ring ? ring : fill(region)}
                stroke="none" strokeWidth={0} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
