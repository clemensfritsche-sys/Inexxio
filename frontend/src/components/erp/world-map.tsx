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

/**
 * **Der Rahmen ist die Landmasse, nicht das Raster** (Testnotiz #357).
 *
 * Die Maske ist ein volles 72×25-Gitter, aber links stehen drei reine Wasser-Spalten (und je
 * nach Maske oben/unten Leerzeilen). Als `viewBox` genommen, ergab das einen Streifen
 * Hintergrund am Rand – die Karte «füllte den Container nicht aus». Statt das mit einem
 * Zahlenwert nachzujustieren (der bei jeder Masken-Änderung wieder falsch wäre), wird der
 * Ausschnitt aus den Zellen **abgeleitet**: die Bounding-Box aller Landzellen.
 */
/**
 * **Eine Region = EIN Pfad** (Testnotiz #369).
 *
 * Vorher war jede 5°-Zelle ein eigenes ``<rect>``: rund 700 Knoten, alle unter je einem
 * SVG-Filter. Der Filter ist das Teure – er legt pro Gruppe einen Offscreen-Puffer an,
 * zeichnet weich und schneidet die Alpha-Kante zurück –, und je mehr Knoten darunter
 * liegen, desto länger dauert das Rastern. Beim Scrollen wurde die Karte genau dann
 * gerastert, wenn sie in den Blick kommt: das war das Stocken.
 *
 * Die Form bleibt haargenau dieselbe, sie steht nur in EINEM ``d``-Attribut statt in
 * hundert Elementen – ein Rechteck je Zelle, minimal überlappend (damit der Weichzeichner
 * sie zu einer Fläche zusammenzieht statt Perlen zu bilden), alle im selben Pfad.
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
 * **Wo liegt der Schwerpunkt einer Region?** – in Prozent der Kartenfläche.
 *
 * Damit kann die Gebietsansicht ihre Beschriftung und ihre Zuweisung **dort** anbringen,
 * wo das Gebiet liegt (Testnotiz #342), statt in einer Liste daneben. Der Median statt des
 * Mittels: bei einer langgezogenen Region (Europa bis Ostrussland) zieht ein Ausreisser den
 * Mittelwert ins Meer, der Median bleibt auf der Landmasse.
 */
export function regionAnchor(region: string): { x: number; y: number } {
  const cells = CELLS_BY_REGION[region] ?? [];
  if (!cells.length) return { x: 50, y: 50 };
  const mid = (v: number[]) => v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
  // Prozent **des gezeichneten Ausschnitts** (BOX), nicht des vollen Rasters – sonst
  // liefen Beschriftung und Zuweisungs-Kärtchen gegenüber der Karte aus dem Ruder.
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
  /** Beschriftung IN der Fläche: Gebiet + wer es fakturiert (Testnotiz #342). */
  label?: (region: string) => { title: string; sub: string; ink: string } | null;
}) {
  // Gehören mehrere Regionen derselben Gesellschaft, sind sie gleich eingefärbt – dann ist
  // ohne Hover nicht zu sehen, wo Asien aufhört. Der Hover zeichnet die Region nach; das
  // ist zugleich die Erkundung («welches Gebiet ist das?»), ohne Fläche zu kosten.
  const [hover, setHover] = useState<string | null>(null);

  return (
    <svg viewBox={`${BOX.x} ${BOX.y} ${BOX.w} ${BOX.h}`} width="100%" role="img" aria-label="Weltkarte der Gebietsaufteilung"
      // Eigene Rasterebene: einmal gezeichnet, beim Scrollen nur noch zusammengesetzt
      // statt neu gefiltert (der Filter ist die teure Stelle).
      style={{ display: 'block', background: 'var(--bg-3)', willChange: 'transform', contain: 'paint' }}
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
      {/* **Die Zuordnung steht IN der Fläche**, nicht in einer Liste daneben: welche
          Gesellschaft ein Gebiet fakturiert, liest man dort, wo das Gebiet liegt.
          Ausserhalb der Filter-Gruppe, damit die Weichzeichnung die Schrift nicht anfasst. */}
      {label && Object.keys(CELLS_BY_REGION).map((region) => {
        const l = label(region);
        if (!l) return null;
        const cells = CELLS_BY_REGION[region];
        const mid = (v: number[]) => v.sort((a, b) => a - b)[Math.floor(v.length / 2)];
        const cx = mid(cells.map((c) => c.x)) + 0.5;
        const cy = mid(cells.map((c) => c.y)) + 0.5;
        // **Die Schrift muss den Hover überleben** (Testnotiz #357): unter dem Cursor wird die
        // Fläche mit dem KRÄFTIGEN Ton der Gesellschaft nachgezeichnet – und genau dieser Ton
        // ist auch die Schriftfarbe, die Beschriftung verschwand also im eigenen Gebiet. Auf
        // der kräftigen Fläche schreibt sie darum weiss. Kein zweiter Zustand, nur eine Farbe,
        // die dem Untergrund folgt.
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
