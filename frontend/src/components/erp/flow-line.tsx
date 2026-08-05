'use client';

/**
 * **Die Prozesslinien – EIN Modul für die ganze Geometrie des Flusses.**
 *
 * Alles, was eine Linie ist, wohnt hier: die Spurbreiten, die Achse, die vier Ecken (als je
 * EIN SVG-Pfad – ein Strich, eine Strichstärke, echte Viertelkreise, keine Naht; Notizen
 * #423/#445/#456), die Drei-Spuren-Zeile und das Zurücktreten der Nachbar-Prozesse. Der
 * Fluss selbst (`order-flow.tsx`) setzt daraus nur noch zusammen.
 *
 * **EINE Linie, EINE Regel** (Notizen #422/#429): stark, wo der Prozess gegangen ist;
 * Haarlinie, wo er noch nicht war. Gestrichelte Linien gibt es nicht – ob ein Weg gegangen
 * wurde, sagt die Stärke, nicht die Strichart.
 *
 * ## Die Breiten sind GEMESSEN, nicht gesetzt
 *
 * Bis hierher standen `MAIN`/`SIDE`/`GAP`/`RUN` als feste Zahlen im Modul – drei Spuren à
 * 460 px plus Luft ergaben **1432 px Mindestbreite**, und was nicht hineinpasste, wurde in
 * einen waagrecht scrollenden Kasten gesteckt. Das war auf **jedem** Gerät ein Kompromiss:
 * schon ein 13″-MacBook hat im Detailfenster nur ~1060 px, ein iPhone ~335. Waagrecht
 * scrollen ist aber kein Zustand, den man einem Diagramm zumuten darf – man verliert die
 * Achse aus dem Blick, genau das, worum es hier geht.
 *
 * Die Geometrie ist darum eine **Funktion der verfügbaren Breite**. Sie wird EINMAL gemessen
 * (`FlowFrame`, ResizeObserver) und über einen Context an alles verteilt, was eine Linie
 * zeichnet – Achse, Ecke, Spur, Zeile. Damit gibt es weiterhin genau EINE Quelle für jede
 * Zahl; sie ist nur nicht mehr konstant.
 *
 * Zwei Ausprägungen, dieselben Bausteine:
 *
 *     Spuren   Drei Spuren nebeneinander (Herkunft · Achse · Abzweige) – das gewohnte Bild.
 *              Die Spurbreite schrumpft mit dem Platz (460 → 260), das Bild bleibt gleich.
 *     Gestapelt  Unter ~812 px passen drei lesbare Spuren nicht mehr nebeneinander. Dann
 *              läuft ALLES in einer Spur: ein Abzweig ist ein Unterprozess **auf** der
 *              Achse, die Ecken werden zu geraden Verbindungsstücken. Kein zweites
 *              Vokabular – dieselben Karten, dieselbe Linie, nur ohne Seitwärtsbewegung.
 */

import { createContext, useContext, useLayoutEffect, useMemo, useRef, useState } from 'react';

/** Wunschbreite einer Spur – darüber wird eine Modul-Karte nicht breiter. */
export const MAIN_MAX = 460;
/** Darunter ist eine Modul-Karte (Symbolkasten + Name + Zustand) nicht mehr lesbar. */
export const LANE_MIN = 240;
export const GAP = 26;            // Luft zwischen Haupt- und Seitenspur
export const ARM = 40;            // Höhe einer Abzweigung (drei Spuren)
/** Gestapelt ist die «Abzweigung» ein gerades Stück Achse – es darf kürzer sein. */
export const ARM_STACKED = 22;
export const BEND = 12;           // Eckenradius der Prozesslinie

export type FlowMetrics = {
  /** Breite der Hauptspur (Modul-Karten). */
  main: number;
  /** Breite einer Seitenspur – gleich breit wie die Hauptspur (#491). */
  side: number;
  gap: number;
  /** Achse ↔ Mitte der Seitenspur (Länge einer Abzweigung). */
  run: number;
  /** Höhe einer Abzweigung – gestapelt kürzer, dort ist es nur ein Stück Achse. */
  arm: number;
  /** Breite einer Seitenspur inkl. Luft (0 = keine Seitenspuren). */
  lane: number;
  /** Kein Platz für Seitenspuren – Nachbarn laufen IN der Achse mit. */
  stacked: boolean;
};

/**
 * **Die Geometrie aus der verfügbaren Breite** – die eine Rechnung, sonst nirgends.
 *
 * Ohne Nachbarn braucht es nur die Hauptspur; sie füllt, was da ist, höchstens `MAIN_MAX`.
 * Mit Nachbarn wird geprüft, ob drei **lesbare** Spuren nebeneinander passen: erst dann
 * gibt es das Drei-Spuren-Bild, sonst wird gestapelt.
 */
const even = (n: number) => n - (n % 2);

export function metricsFor(available: number, hasAside: boolean): FlowMetrics {
  const room = Math.max(0, Math.floor(available));
  const main = even(Math.min(MAIN_MAX, room || MAIN_MAX));
  const flat = { main, side: 0, gap: 0, run: 0, lane: 0, arm: ARM_STACKED, stacked: true };
  if (!hasAside) return flat;
  if (room < 3 * LANE_MIN + 2 * GAP) return flat;
  // **Gerade Spurbreite** – aus demselben Grund wie die gerade Strichstärke (#550): die
  // Achse sitzt mittig in ihrer Spur, also muss `(spur − strich) / 2` eine ganze Zahl sein.
  // Bei ungerader Spur begänne ihr Kasten auf einer halben Pixelgrenze, und der SVG-Pfad
  // der Ecke läge daneben.
  const w = even(Math.min(MAIN_MAX, Math.floor((room - 2 * GAP) / 3)));
  // Bei gleich breiten Spuren ist der Weg von der Achse zur Spurmitte genau w + gap
  // (main/2 + gap + side/2) – dieselbe Zahl, nur ohne die überflüssige Halbierung.
  return { main: w, side: w, gap: GAP, run: w + GAP, lane: w + GAP, arm: ARM, stacked: false };
}

const FlowCtx = createContext<FlowMetrics>(metricsFor(MAIN_MAX, false));

/** Die geltende Geometrie – für jeden, der eine Linie oder eine Spur zeichnet. */
export const useFlow = () => useContext(FlowCtx);

/**
 * **Der Rahmen misst und verteilt.**
 *
 * Er hat bewusst KEIN `overflow-x`: was nicht passt, wird nicht weggescrollt, sondern
 * schmaler – waagrecht scrollen ist der Zustand, den es hier nicht geben darf.
 */
export function FlowFrame({ hasAside = false, children }: {
  hasAside?: boolean; children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setWidth(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const metrics = useMemo(() => metricsFor(width, hasAside), [width, hasAside]);
  return (
    <div ref={ref} style={{ width: '100%', minWidth: 0 }}>
      <FlowCtx.Provider value={metrics}>
        <div style={{ width: '100%', minWidth: 0, display: 'flex',
          flexDirection: 'column', alignItems: 'stretch' }}>
          {children}
        </div>
      </FlowCtx.Provider>
    </div>
  );
}

export const lineColor = (strong: boolean) => (strong ? 'var(--fg-2)' : 'var(--border-2)');

/**
 * **Die Strichstärke ist GERADE – sonst passt die Ecke nie zur Geraden** (Testnotiz #550).
 *
 * Die Achse ist ein ``div``, die Ecke ein SVG-Pfad. Ein Browser **rastert** die Fläche eines
 * div auf ganze Gerätepixel, einen Pfad zeichnet er analytisch (mit Kantenglättung). Bei
 * **ungerader** Breite fällt beides auseinander: die Achse liegt mittig in einer Spur gerader
 * Breite, ihr Kasten beginnt damit auf einer halben Pixelgrenze (bei 3 px: 748.5) und wird
 * auf 749 gerundet – der Strich der Ecke bleibt bei 748.5 und ragt eine halbe Pixelbreite
 * nach links heraus. Genau das sah aus, «als ob der Radius über die gerade Linie hinausgeht»,
 * und zwar systematisch an jeder Gabelung und jeder Einmündung.
 *
 * Bei **gerader** Breite ist die Frage gegenstandslos: Kasten und Strich liegen exakt gleich
 * (bei 4 px beide auf 748…752) – und das unabhängig von der Pixeldichte des Bildschirms. Ein
 * Ausrichten auf halbe Pixel wäre die Alternative gewesen, würde aber auf Retina-Geräten
 * genau den Fehler erzeugen, den es auf einfachen behebt.
 */
export const lineW = (strong: boolean) => (strong ? 4 : 2);

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
function roundedPath(points: Pt[], r: number, splitAt?: number): [string, string] {
  const step = (a: Pt, b: Pt, d: number): Pt => {
    const [dx, dy] = [Math.sign(b[0] - a[0]), Math.sign(b[1] - a[1])];
    return [a[0] + dx * d, a[1] + dy * d];
  };
  let d = `M${points[0][0]} ${points[0][1]}`;
  let head = '';
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
    // Am Anschluss-Bogen wird der Pfad geteilt: sein Stück gehört der **Achse**, der Rest
    // dem Weg (siehe ``Elbow``). Ohne Teilung ist ``head`` leer und alles ist «Rest».
    if (i === splitAt) { head = d; d = `M${b[0]} ${b[1]}`; }
  }
  const last = points[points.length - 1];
  return [head, `${d}L${last[0]} ${last[1]}`];
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

export type ElbowDir = 'fork-right' | 'merge-right' | 'in-from-left' | 'out-to-left';

/**
 * **Der Weg zwischen Achse und Seitenspur – EIN Baustein, echte Viertelkreise.**
 *
 * Vier Richtungen aus denselben Zahlen. **Runde Ecken überall – auch am Anschluss an die
 * Achse** (Testnotiz #591): ein T mit scharfer 90°-Ecke wäre die einzige harte Ecke im
 * ganzen Bild. Die Abzweigung biegt mit demselben Radius aus der Achse ab, mit dem sie unten
 * wieder einmündet (#456); Herkunft und Rückweg treffen die Achse dort, wo sie **beginnt bzw.
 * endet** – eine Ecke des Weges, also zwei Bögen (#430/#431).
 *
 * **Warum dieser Bogen früher einen Stummel hinterliess** (#586): er liegt ein Stück
 * ENTLANG der Achse (gemessen ~8 px). Trug er eine andere Strichstärke als das Achsenstück
 * daneben, blieb dort ein schwarzer Rest auf einer Haarlinie stehen. Die Lösung ist keine
 * Formfrage, sondern eine **Zuordnung**: der Anschluss-Bogen gehört der **Achse**, der Rest
 * dem **Weg**. Der Pfad wird darum an genau diesem Bogen geteilt (``roundedPath(…, splitAt)``)
 * und in zwei Stärken gezeichnet – der Bogen so stark wie das Stärkere von beiden, damit er
 * nie eine dickere Linie zerschneidet.
 *
 * **Und Fork und Merge sind echte Spiegelbilder**: beide Waagrechten liegen ``BEND`` innerhalb
 * der Zeile, ihre Mitte ist also die Mitte der Zeile. Damit steht das Material ohne
 * Korrekturglied mittig – auch zwischen zwei aufeinanderfolgenden Teilungen (#586).
 *
 * **Gestapelt** gibt es keine Seitwärtsbewegung: dann ist der Weg ein gerades Stück Achse.
 * Dieselbe Aussage («hier geht es weiter»), nur ohne den Umweg, den es auf 375 px nicht gibt.
 */
function elbowShape(m: FlowMetrics, dir: ElbowDir): {
  pts: Pt[]; left: number; h: number; top?: number; bottom?: number; joint?: number;
} {
  const { main, side, gap, run, arm } = m;
  switch (dir) {
    // Achse → Seitenspur (Abzweigung, oben) und zurück (Einmündung, unten) – Spiegelbilder.
    case 'fork-right':
      return { left: -(main / 2 + gap), top: 0, h: arm, joint: 1,
        pts: [[0, 0], [0, BEND], [run, BEND], [run, arm]] };
    case 'merge-right':
      return { left: -(main / 2 + gap), bottom: 0, h: arm, joint: 2,
        pts: [[run, 0], [run, arm - BEND], [0, arm - BEND], [0, arm]] };
    // Nachbar-Spur links → Achse (Herkunft) und Achse → Nachbar (Rückweg). Sie treffen die
    // Achse an ihrem Anfang bzw. Ende – dort liegt kein Achsenstück daneben, also gibt es
    // auch nichts, was sich beissen könnte.
    case 'in-from-left':
      return { left: side / 2, bottom: 0, h: arm,
        pts: [[0, 0], [0, arm - BEND], [run, arm - BEND], [run, arm]] };
    default:
      return { left: side / 2, top: 0, h: arm,
        pts: [[run, 0], [run, 2 * BEND], [0, 2 * BEND], [0, arm]] };
  }
}

export function Elbow({ dir, strong, axis }: {
  dir: ElbowDir;
  strong?: boolean;
  /** Stärke des Achsenstücks, an dem dieser Weg hängt – für den Anschluss-Bogen. */
  axis?: boolean;
}) {
  const m = useFlow();
  const shape = elbowShape(m, dir);
  const { pts, left, h, top, bottom, joint } = shape;
  // Gestapelt: ein gerades Stück Achse statt eines Umwegs zur Seite.
  if (m.stacked) {
    return (
      <div aria-hidden style={{
        position: 'absolute', left: '50%', transform: 'translateX(-50%)', top, bottom,
        width: lineW(!!strong), height: h, background: lineColor(!!strong),
      }} />
    );
  }
  const [head, tail] = roundedPath(overlapped(pts), BEND, joint);
  // Der Anschluss-Bogen nimmt die **stärkere** der beiden Linien: eine dünne Kurve quer über
  // eine starke Achse wäre ein heller Schnitt mitten in ihr.
  const jointStrong = !!strong || !!axis;
  const parts: [string, boolean][] = joint === undefined
    ? [[tail, !!strong]]
    : joint === 1 ? [[head, jointStrong], [tail, !!strong]]
                  : [[tail, jointStrong], [head, !!strong]];
  return (
    <svg width={m.run} height={h} viewBox={`0 0 ${m.run} ${h}`} aria-hidden
      shapeRendering="geometricPrecision"
      style={{ position: 'absolute', left, top, bottom, overflow: 'visible', pointerEvents: 'none' }}>
      {parts.map(([d, s], i) => (
        <path key={i} d={d} fill="none" stroke={lineColor(s)} strokeWidth={lineW(s)}
          strokeLinecap="butt" strokeLinejoin="round" />
      ))}
    </svg>
  );
}

/**
 * **Nachbar-Prozesse treten zurück** (Notizen #453/#460): links der übergeordnete Auftrag,
 * rechts der Abzweig. Beide gehören zum Bild, aber der Fokus liegt auf der Mitte – beim
 * Hovern kommen sie ganz nach vorn (CSS, ``.ix-flow-aside``).
 *
 * **Gestapelt bleibt das Zurücktreten, das Ausblenden zur Kante entfällt** (`flat`): eine
 * Maske zur Seite sagt «hier geht es seitwärts weiter» – wo nichts seitwärts liegt, wäre
 * das eine falsche Behauptung.
 */
export const aside = (to: 'left' | 'right', style?: React.CSSProperties, flat = false) => ({
  className: 'ix-flow-aside',
  'data-flat': flat ? '1' : undefined,
  style: { ...style, ['--ix-fade' as string]: to } as React.CSSProperties,
});

/**
 * **Die Hauptspur – EINE Breite für jeden Prozess** (Testnotiz #597).
 *
 * Ein Modul war beim Hinzufügen, nach dem Zwischenspeichern und nach der Freigabe
 * verschieden breit, weil die Breite an drei Stellen entstand: im Fluss als feste
 * Spaltenbreite, im Schritt-Editor als `max-width` je Karte (also «so breit wie der Platz,
 * höchstens …»), und der Platz war je nach Fenster ein anderer.
 *
 * Darum gibt es die Spur als **einen** Baustein: der laufende Fluss setzt sie in seine
 * Mitte, der Editor stellt sich hinein. Ihre Breite kommt aus der gemessenen Geometrie –
 * ohne Rahmen (Artikel-Prozess) aus dem Standard, und **nie** breiter als der Platz.
 */
export function Lane({ children }: { children?: React.ReactNode }) {
  const m = useFlow();
  return (
    <div style={{ width: m.main, maxWidth: '100%', flex: 'none', display: 'flex',
      flexDirection: 'column', alignItems: 'center', minWidth: 0 }}>
      {children}
    </div>
  );
}

/**
 * Eine Zeile des Flusses: die Achse in der Mitte, links Herkunft, rechts Abzweige.
 *
 * **Gestapelt** gibt es keine Seiten: der Nachbar läuft dann IN der Achse mit, vor dem
 * Inhalt der Zeile – zuerst, woher es kommt bzw. was abzweigt, dann, was auf der Achse
 * weitergeht. Das ist dieselbe Leserichtung wie im Drei-Spuren-Bild, nur untereinander.
 */
export function Row({ children, left, right }: {
  children?: React.ReactNode; left?: React.ReactNode; right?: React.ReactNode;
}) {
  const m = useFlow();
  if (m.stacked) {
    if (!left && !right) return <Lane>{children}</Lane>;
    return (
      <div style={{ width: '100%', minWidth: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center' }}>
        {left && <Lane>{left}</Lane>}
        {right && <Lane>{right}</Lane>}
        {children != null && <Lane>{children}</Lane>}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', width: '100%', minWidth: 0, justifyContent: 'center',
      alignItems: 'stretch' }}>
      <div style={{ width: m.lane, flex: 'none', display: 'flex',
        justifyContent: 'flex-start', alignItems: 'center' }}>
        {left && <div style={{ width: m.side, minWidth: 0 }}>{left}</div>}
      </div>
      <Lane>{children}</Lane>
      <div style={{ width: m.lane, flex: 'none', display: 'flex',
        justifyContent: 'flex-end', alignItems: 'center' }}>
        {right && <div style={{ width: m.side, minWidth: 0 }}>{right}</div>}
      </div>
    </div>
  );
}
