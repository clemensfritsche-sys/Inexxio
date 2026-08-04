'use client';

/**
 * **Die Prozesslinien – EIN Modul für die ganze Geometrie des Flusses.**
 *
 * Alles, was eine Linie ist, wohnt hier: die festen Spurbreiten, die Achse, die vier
 * Ecken (als je EIN SVG-Pfad – ein Strich, eine Strichstärke, echte Viertelkreise, keine
 * Naht; Notizen #423/#445/#456), die Drei-Spuren-Zeile und das Zurücktreten der
 * Nachbar-Prozesse. Der Fluss selbst (`order-flow.tsx`) setzt daraus nur noch zusammen.
 *
 * **EINE Linie, EINE Regel** (Notizen #422/#429): stark, wo der Prozess gegangen ist;
 * Haarlinie, wo er noch nicht war. Gestrichelte Linien gibt es nicht – ob ein Weg gegangen
 * wurde, sagt die Stärke, nicht die Strichart.
 */

export const MAIN = 460;          // Hauptspur (Modul-Karten)
export const SIDE = MAIN;         // Seitenspur – gleich breit wie die Hauptspur (#491)
export const GAP = 26;            // Luft zwischen Haupt- und Seitenspur
export const ARM = 40;            // Höhe einer Abzweigung
export const BEND = 12;           // Eckenradius der Prozesslinie
export const LANE = SIDE + GAP;   // Breite einer Seitenspur inkl. Luft
export const RUN = MAIN / 2 + GAP + SIDE / 2;   // Achse ↔ Mitte der Seitenspur

export const lineColor = (strong: boolean) => (strong ? 'var(--fg-2)' : 'var(--border-2)');
export const lineW = (strong: boolean) => (strong ? 3 : 2);

/**
 * **Ecken greifen in die Achse hinein.** Zwei getrennt gezeichnete Elemente treffen sich
 * nie pixelgenau – ein halbes Pixel Layout-Rundung genügt, und an der Naht steht ein
 * heller Strich oder ein Versatz. Ein Überlappen von einem Pixel macht die Frage
 * gegenstandslos: es gibt keine Naht mehr, an der etwas fehlen könnte.
 */
const OVERLAP = 1;

/** Ein senkrechtes Stück Achse. */
export function Axis({ h = 22, strong = false, grow = false }: {
  h?: number; strong?: boolean; grow?: boolean;
}) {
  return (
    <div style={{
      width: lineW(strong), flex: grow ? 1 : 'none', background: lineColor(strong),
      height: grow ? undefined : h, minHeight: grow ? h : undefined,
    }} />
  );
}

type Pt = [number, number];

/**
 * **Eine Linie mit runden Ecken – aus EINER Stelle** (statt vier handgeschriebener Pfade).
 *
 * Beschrieben wird die Linie als **Polygonzug**; die Rundung entsteht hier. Vorher stand
 * die Bogen-Mathematik viermal ausgeschrieben da, mit je eigenen Vorzeichen und
 * Sweep-Flags – vier Stellen, an denen ein Radius auseinanderlaufen konnte. Jetzt ist die
 * Aussage jeder Ecke ein Punkt, und wie eine Ecke aussieht, entscheidet genau diese
 * Funktion (Segmente sind achsenparallel, das genügt für einen Fluss).
 */
function roundedPath(points: Pt[], r: number): string {
  const step = (a: Pt, b: Pt, d: number): Pt => {
    const [dx, dy] = [Math.sign(b[0] - a[0]), Math.sign(b[1] - a[1])];
    return [a[0] + dx * d, a[1] + dy * d];
  };
  let d = `M${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [prev, cur, next] = [points[i - 1], points[i], points[i + 1]];
    const inLen = Math.hypot(cur[0] - prev[0], cur[1] - prev[1]);
    const outLen = Math.hypot(next[0] - cur[0], next[1] - cur[1]);
    const rad = Math.min(r, inLen, outLen);
    const a = step(cur, prev, rad);      // Beginn der Rundung
    const b = step(cur, next, rad);      // Ende der Rundung
    // Drehrichtung aus dem Kreuzprodukt der beiden Richtungen – kein Sweep-Flag von Hand.
    const cross = (cur[0] - prev[0]) * (next[1] - cur[1]) - (cur[1] - prev[1]) * (next[0] - cur[0]);
    d += `L${a[0]} ${a[1]}A${rad} ${rad} 0 0 ${cross > 0 ? 1 : 0} ${b[0]} ${b[1]}`;
  }
  const last = points[points.length - 1];
  return `${d}L${last[0]} ${last[1]}`;
}

/** Erste und letzte Station um ``OVERLAP`` verlängern – die Ecke greift in die Achse. */
function overlapped(points: Pt[]): Pt[] {
  const out = points.map((p) => [...p] as Pt);
  const grow = (i: number, j: number) => {
    const [dx, dy] = [Math.sign(out[i][0] - out[j][0]), Math.sign(out[i][1] - out[j][1])];
    out[i] = [out[i][0] + dx * OVERLAP, out[i][1] + dy * OVERLAP];
  };
  grow(0, 1);
  grow(out.length - 1, out.length - 2);
  return out;
}

/**
 * **Der Weg zwischen Achse und Seitenspur – EIN Pfad, echte Viertelkreise.**
 *
 * Vier Richtungen aus denselben Konstanten und demselben Baustein. Fork und Merge sind eine
 * **Gabelung** (#456): die Linie biegt mit demselben Radius aus der Achse ab, mit dem sie in
 * den Unterprozess einläuft. Herkunft und Rückweg treffen die Achse dort, wo sie beginnt bzw.
 * endet – die Linie biegt zweimal ab (#430/#431).
 *
 * **Die Strichstärke einer Ecke ist die ihrer Achse.** Trafen an einer Ecke zwei verschiedene
 * Bits aufeinander (3 px Achse ↔ 2 px Ecke), stand dort ein sichtbarer Versatz – ein halbes
 * Pixel auf jeder Seite. Der Aufrufer reicht darum denselben Zustand durch, den auch das
 * angrenzende Achsenstück trägt.
 */
const ELBOW: Record<string, { pts: Pt[]; left: number; h: number; top?: number; bottom?: number }> = {
  // Achse → Seitenspur (Abzweigung, oben) und zurück (Einmündung, unten).
  'fork-right': { left: -(MAIN / 2 + GAP), top: -BEND, h: ARM + BEND,
    pts: [[0, 0], [0, BEND], [RUN, BEND], [RUN, ARM + BEND]] },
  'merge-right': { left: -(MAIN / 2 + GAP), bottom: 0, h: ARM,
    pts: [[RUN, 0], [RUN, ARM - BEND], [0, ARM - BEND], [0, ARM]] },
  // Nachbar-Spur links → Achse (Herkunft) und Achse → Nachbar (Rückweg).
  'in-from-left': { left: SIDE / 2, bottom: 0, h: ARM,
    pts: [[0, 0], [0, ARM - BEND], [RUN, ARM - BEND], [RUN, ARM]] },
  'out-to-left': { left: SIDE / 2, top: 0, h: ARM,
    pts: [[RUN, 0], [RUN, 2 * BEND], [0, 2 * BEND], [0, ARM]] },
};

export function Elbow({ dir, strong }: {
  dir: 'fork-right' | 'merge-right' | 'in-from-left' | 'out-to-left'; strong?: boolean;
}) {
  const { pts, left, h, top, bottom } = ELBOW[dir];
  return (
    <svg width={RUN} height={h} viewBox={`0 0 ${RUN} ${h}`} aria-hidden
      shapeRendering="geometricPrecision"
      style={{ position: 'absolute', left, top, bottom, overflow: 'visible', pointerEvents: 'none' }}>
      <path d={roundedPath(overlapped(pts), BEND)} fill="none"
        stroke={lineColor(!!strong)} strokeWidth={lineW(!!strong)}
        strokeLinecap="butt" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * **Nachbar-Prozesse treten zurück** (Notizen #453/#460): links der übergeordnete Auftrag,
 * rechts der Abzweig. Beide gehören zum Bild, aber der Fokus liegt auf der Mitte – beim
 * Hovern kommen sie ganz nach vorn (CSS, ``.ix-flow-aside``).
 */
export const aside = (to: 'left' | 'right', style?: React.CSSProperties) => ({
  className: 'ix-flow-aside',
  style: { ...style, ['--ix-fade' as string]: to } as React.CSSProperties,
});

/**
 * Eine Zeile des Flusses: die Achse in der Mitte, links Herkunft, rechts Abzweige.
 * Die Spuren sind fest breit; ohne Nachbarn fällt die Spurbreite auf 0 (`--flow-lane`).
 */
export function Row({ children, left, right }: {
  children?: React.ReactNode; left?: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', width: '100%', justifyContent: 'center', alignItems: 'stretch' }}>
      <div style={{ width: 'var(--flow-lane)', flex: 'none', display: 'flex',
        justifyContent: 'flex-start', alignItems: 'center' }}>
        {left && <div style={{ width: SIDE, minWidth: 0 }}>{left}</div>}
      </div>
      <div style={{ width: MAIN, flex: 'none', display: 'flex', flexDirection: 'column',
        alignItems: 'center', minWidth: 0 }}>
        {children}
      </div>
      <div style={{ width: 'var(--flow-lane)', flex: 'none', display: 'flex',
        justifyContent: 'flex-end', alignItems: 'center' }}>
        {right && <div style={{ width: SIDE, minWidth: 0 }}>{right}</div>}
      </div>
    </div>
  );
}
