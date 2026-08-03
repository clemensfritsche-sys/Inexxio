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

/**
 * **Der Weg zwischen Achse und Seitenspur – EIN Pfad, echte Viertelkreise.**
 *
 * Vier Richtungen über denselben Konstanten. Fork und Merge sind eine **Gabelung** (#456):
 * die Linie biegt mit demselben Radius aus der Achse ab, mit dem sie in den Unterprozess
 * einläuft. Herkunft und Rückweg treffen die Achse dort, wo sie beginnt bzw. endet – die
 * Linie biegt zweimal ab (#430/#431). Weil jeder Pfad durchgehend ist, gibt es an keiner
 * Ecke eine Naht.
 */
const ELBOW: Record<string, { d: string; left: number; h: number; top?: number; bottom?: number }> = {
  'fork-right': { left: -(MAIN / 2 + GAP), top: -BEND, h: ARM + BEND,
    d: `M0 0 A${BEND} ${BEND} 0 0 0 ${BEND} ${BEND} H${RUN - BEND} `
      + `A${BEND} ${BEND} 0 0 1 ${RUN} ${2 * BEND} V${ARM + BEND}` },
  'merge-right': { left: -(MAIN / 2 + GAP), bottom: 0, h: ARM,
    d: `M${RUN} 0 V${ARM - 2 * BEND} A${BEND} ${BEND} 0 0 1 ${RUN - BEND} ${ARM - BEND} `
      + `H${BEND} A${BEND} ${BEND} 0 0 0 0 ${ARM}` },
  'in-from-left': { left: SIDE / 2, bottom: 0, h: ARM,
    d: `M0 0 V${ARM - 2 * BEND} A${BEND} ${BEND} 0 0 0 ${BEND} ${ARM - BEND} `
      + `H${RUN - BEND} A${BEND} ${BEND} 0 0 1 ${RUN} ${ARM}` },
  'out-to-left': { left: SIDE / 2, top: 0, h: ARM,
    d: `M${RUN} 0 V${BEND} A${BEND} ${BEND} 0 0 1 ${RUN - BEND} ${2 * BEND} `
      + `H${BEND} A${BEND} ${BEND} 0 0 0 0 ${3 * BEND} V${ARM}` },
};

export function Elbow({ dir, strong }: {
  dir: 'fork-right' | 'merge-right' | 'in-from-left' | 'out-to-left'; strong?: boolean;
}) {
  const { d, left, h, top, bottom } = ELBOW[dir];
  return (
    <svg width={RUN} height={h} viewBox={`0 0 ${RUN} ${h}`} aria-hidden
      shapeRendering="geometricPrecision"
      style={{ position: 'absolute', left, top, bottom, overflow: 'visible', pointerEvents: 'none' }}>
      <path d={d} fill="none" stroke={lineColor(!!strong)} strokeWidth={lineW(!!strong)}
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
