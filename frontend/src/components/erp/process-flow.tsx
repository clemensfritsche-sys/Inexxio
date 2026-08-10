'use client';

import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState,
  type CSSProperties, type ReactNode,
} from 'react';

/**
 * **Prozess-Fluss — Rahmen, gemessene Anker, berechnete Linien.**
 *
 * Die eine harte Anforderung an diese Darstellung (PROCESS_CORE.md §8): **Linien nie mit
 * festen Pixelwerten.** Die Zahl der Prozessschritte ist unbekannt und wächst; jede
 * Position, die im Code steht, ist eine Behauptung, die beim vierten Modul falsch wird.
 *
 * Darum die Arbeitsteilung:
 *
 * | | |
 * |---|---|
 * | **Knoten** | bestimmen ihre Position **selbst** — normales Fluss-Layout (Flex/Grid). Kein `absolute`, kein `top:`. |
 * | **Linien** | werden aus **gemessenen** Ankerpunkten berechnet und als SVG darüber gelegt. |
 *
 * Damit trägt dasselbe Bauteil 3 wie 50 Schritte, und es verschiebt sich nichts, wenn
 * ein Knoten breiter wird, ein Text umbricht oder das Fenster schmaler wird: die
 * Messung läuft über einen `ResizeObserver` **und** nach jedem Commit erneut, weil ein
 * Knoten wandern kann, ohne seine Grösse zu ändern.
 *
 * Gezeichnet wird **hinter** den Knoten (`zIndex 0` gegen `zIndex 1`), damit keine Linie
 * über eine Pille läuft, und mit `pointerEvents: none`, damit sie nichts anklickbar
 * verdeckt.
 *
 * Die Kinder werden erst gerendert, **wenn die Breite gemessen ist**. Das kostet keinen
 * sichtbaren Sprung (`useLayoutEffect` läuft vor dem Paint) und erspart die Alternative:
 * einmal mit geratener Breite rendern und dann umbauen.
 */

/**
 * **Die Spurmasse — die eine Stelle, an der eine Breite entsteht.**
 *
 * Sie gehören zum Bild, nicht zu seinen Aufrufern: sonst gäbe es je Ansicht ein eigenes
 * Mass, und dieselben Module sähen verschieden breit aus (Testnotiz #684, #597).
 *
 * Gemessen wird der **Rahmen**, nicht das Fenster — eine Container-Abfrage statt einer
 * Media-Query. Das ist nicht Geschmack: dieselbe Fensterbreite ergibt im Detailfenster
 * einen anderen Rahmen als auf einer freien Seite, und die Linien richten sich ohnehin
 * nach der Messung. Eine Media-Query wäre der zweite Massstab für dieselbe Frage.
 *
 * **Warum das an einem 13,3″-Notebook zählt:** entschieden wird nach **effektiver
 * CSS-Breite**, nicht nach der Panel-Auflösung. Ein MacBook Pro 13,3″ hat 2560 × 1600
 * Pixel und liefert dem Browser trotzdem 1440 × 900 CSS-Pixel (Standard, DPR 2) bzw.
 * 1280 / 1680 in den skalierten Modi. Wer gegen 2560 rechnet, hält jedes Notebook für
 * einen Grossbildschirm.
 */
export const LANE = {
  /** Abstand zwischen zwei Spuren. */
  GAP: 16,
  /** Wie schmal die Mitte werden darf. Darunter drängen sich die Modul-Karten. */
  MID_MIN: 360,
  /** Wie breit die Mitte höchstens wird — sie ist der Fokus, aber kein Fass ohne Boden. */
  MID_MAX: 620,
  /** Was ein Nachbar mindestens braucht, damit seine Modul-Karten lesbar bleiben. */
  SIDE_MIN: 168,
  /** Wie breit ein Nachbar höchstens wird. Schmaler als die Mitte. */
  SIDE_MAX: 380,
} as const;

/**
 * Ab dieser **Rahmen**breite stehen drei Spuren nebeneinander.
 *
 * 360 + 2·168 + 2·16 = **728 px Rahmen** ≈ 1108 px Fenster (das Detailfenster ist rund
 * 380 px schmaler als das Fenster: Feed + Polsterung). Damit tragen alle üblichen
 * Notebook-Modi drei Spuren — 1280, 1440, 1512, 1680 — und erst darunter wird gestapelt.
 */
export const LANES_FROM = LANE.MID_MIN + 2 * LANE.SIDE_MIN + 2 * LANE.GAP;

export interface FlowMetrics {
  /** Drei Spuren nebeneinander? Sonst untereinander. */
  lanes: boolean;
  /** Breite der Mitte. */
  mid: number;
  /** Breite je Nachbarspur. */
  side: number;
  gap: number;
  /** Die gemessene Rahmenbreite – für alles, was sich sonst noch danach richtet. */
  width: number;
}

/**
 * Die Spurbreiten zu einer gemessenen Rahmenbreite — **eine Formel, keine Stufenliste**.
 *
 * Die Reihenfolge der Zuteilung ist die Aussage: **erst bekommt die Mitte, was sie
 * braucht** (sie ist der Fokus), **dann geht der Rest an die Nachbarn**. Umgekehrt wäre
 * der Fokus die schmalste Spalte, sobald es eng wird — genau der Fehler, den ein
 * `minmax(0,1fr)` in der Mitte schon einmal erzeugt hat.
 */
export function flowMetrics(width: number): FlowMetrics {
  const { GAP, MID_MIN, MID_MAX, SIDE_MIN, SIDE_MAX } = LANE;
  const mid = clamp(MID_MIN, width - 2 * SIDE_MIN - 2 * GAP, MID_MAX);
  const side = clamp(SIDE_MIN, (width - mid - 2 * GAP) / 2, SIDE_MAX);
  return { lanes: width >= LANES_FROM, mid, side: Math.floor(side), gap: GAP, width };
}

function clamp(lo: number, v: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Ein gemessener Knoten — in Koordinaten des Rahmens, nicht des Fensters. */
export interface FlowAnchor {
  top: number;
  bottom: number;
  left: number;
  right: number;
  /** Mitte waagrecht */
  cx: number;
  /** Mitte senkrecht */
  cy: number;
}

export interface FlowSize {
  w: number;
  h: number;
}

type Register = (id: string, el: HTMLElement | null) => void;

const Ctx = createContext<Register | null>(null);

// Auf dem Server gibt es kein Layout zu messen; `useLayoutEffect` würde dort nur warnen.
const useIsoLayout = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export function FlowFrame({ children, lines }: {
  /** Die Knoten. Bekommen die **gemessenen** Spurmasse — davon hängt das Layout ab
   *  (drei Spuren oder eine), nicht von einer Media-Query: sonst gäbe es zwei Massstäbe
   *  für dieselbe Frage, und die Linien richten sich ohnehin nach der Messung. */
  children: (metrics: FlowMetrics) => ReactNode;
  /** Die Linien. Bekommt die Anker aller registrierten Knoten und die Rahmengrösse. */
  lines: (anchors: Record<string, FlowAnchor>, size: FlowSize) => ReactNode;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const els = useRef(new Map<string, HTMLElement>());
  const roRef = useRef<ResizeObserver | null>(null);
  const sig = useRef('');

  const [anchors, setAnchors] = useState<Record<string, FlowAnchor>>({});
  const [size, setSize] = useState<FlowSize | null>(null);

  const measure = useCallback(() => {
    const root = frameRef.current;
    if (!root) return;
    const base = root.getBoundingClientRect();
    const next: Record<string, FlowAnchor> = {};
    els.current.forEach((el, id) => {
      if (!el.isConnected) return;
      const r = el.getBoundingClientRect();
      next[id] = {
        top: Math.round(r.top - base.top),
        bottom: Math.round(r.bottom - base.top),
        left: Math.round(r.left - base.left),
        right: Math.round(r.right - base.left),
        cx: Math.round(r.left - base.left + r.width / 2),
        cy: Math.round(r.top - base.top + r.height / 2),
      };
    });
    const w = Math.round(base.width);
    const h = Math.round(base.height);
    // Ohne diesen Vergleich schriebe jede Messung neuen State, jeder State löste einen
    // Commit aus und jeder Commit eine Messung — eine Schleife ohne Ende.
    const stamp = JSON.stringify([next, w, h]);
    if (stamp === sig.current) return;
    sig.current = stamp;
    setAnchors(next);
    setSize({ w, h });
  }, []);

  const register = useCallback<Register>((id, el) => {
    const prev = els.current.get(id);
    if (prev && prev !== el) roRef.current?.unobserve(prev);
    if (el) {
      els.current.set(id, el);
      roRef.current?.observe(el);
    } else {
      els.current.delete(id);
    }
  }, []);

  useIsoLayout(() => {
    const ro = new ResizeObserver(() => measure());
    roRef.current = ro;
    if (frameRef.current) ro.observe(frameRef.current);
    els.current.forEach((el) => ro.observe(el));
    measure();
    return () => {
      ro.disconnect();
      roRef.current = null;
    };
  }, [measure]);

  // Ein Knoten kann seine Position ändern, ohne seine Grösse zu ändern (ein Knoten
  // darüber fällt weg). Der ResizeObserver sieht das nicht — der Commit schon.
  useIsoLayout(() => { measure(); });

  return (
    <Ctx.Provider value={register}>
      <div ref={frameRef} style={{ position: 'relative', width: '100%' }}>
        <svg
          width={size?.w ?? 0}
          height={size?.h ?? 0}
          style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0 }}
          aria-hidden
        >
          {size && lines(anchors, size)}
        </svg>
        {size && children(flowMetrics(size.w))}
      </div>
    </Ctx.Provider>
  );
}

/**
 * Ein Knoten im Fluss. Er meldet sich beim Rahmen an und wird gemessen — mehr tut diese
 * Hülle nicht. **Was** darin steht, ist Sache des Aufrufers: Start-Symbol, Modul,
 * Zustandsanzeige und Ende teilen sich dieses eine Bauteil, es gibt keine Variante je
 * Modultyp (PROCESS_CORE.md §8).
 */
export function FlowNode({ id, children, style, onClick, title }: {
  id: string;
  children: ReactNode;
  style?: CSSProperties;
  onClick?: () => void;
  title?: string;
}) {
  const register = useContext(Ctx);
  // An- **und** Abmeldung laufen über denselben Ruf: React gibt der Callback-Ref beim
  // Ausbauen `null`. Die Abmeldung in einen Effekt zu legen wäre ein zweiter Weg – und
  // im StrictMode ein Fehler: dessen doppeltes Ausführen räumt den Knoten wieder aus der
  // Messung, ohne dass die Ref ihn erneut einträgt. Genau daran wurde im Browser keine
  // einzige Linie gezeichnet.
  const ref = useCallback(
    (el: HTMLDivElement | null) => register?.(id, el),
    [register, id],
  );

  return (
    <div
      ref={ref}
      style={{ position: 'relative', zIndex: 1, ...style }}
      onClick={onClick}
      title={title}
    >
      {children}
    </div>
  );
}

/**
 * **Der Eckenradius.** Eine Zahl, ein Ort – jede Ecke im Bild ist gleich rund.
 */
export const BEND = 14;

/**
 * **Ein Zittern ist kein Weg.**
 *
 * Zwei lange Geraden, dazwischen ein Versatz von wenigen Pixeln: geometrisch ein
 * Linienzug mit zwei Ecken, im Bild ein Knick, der nichts bedeutet. Er entsteht ganz
 * von selbst, sobald zwei gemessene Anker fast – aber eben nicht genau – auf einer
 * Höhe liegen, und er fiel bisher unterschiedlich aus, je nachdem wie hoch ein Knoten
 * gerade war: derselbe Weg sah zweimal verschieden aus.
 *
 * Die Rundung macht es sichtbar, statt es zu verdecken: für eine Ecke braucht es
 * ``2 · BEND`` Länge, kürzere Stücke bekommen einen gestauchten Bogen – genau das
 * Wackeln, das man dann sieht. Also wird ein zu kurzes Stück **begradigt** statt
 * gerundet: die spätere Koordinate rastet auf die frühere ein, und die Ecke dahinter
 * zieht mit, damit alles achsenparallel bleibt.
 *
 * **Nur im Inneren.** Das erste und das letzte Stück sind die senkrechten Stummel, mit
 * denen eine Linie in ein Objekt einläuft (§8.1a) – die sind kurz und sollen es sein.
 */
function straighten(points: Array<[number, number]>, minLen: number): Array<[number, number]> {
  const p = points.map((q) => [...q] as [number, number]);
  for (let i = 1; i + 2 < p.length; i++) {
    for (const axis of [0, 1] as const) {
      const delta = p[i + 1][axis] - p[i][axis];
      if (delta === 0 || Math.abs(delta) >= minLen) continue;
      const was = p[i + 1][axis];
      p[i + 1][axis] = p[i][axis];
      if (i + 2 < p.length && p[i + 2][axis] === was) p[i + 2][axis] = p[i][axis];
    }
  }
  return p;
}

/**
 * **Nur echte Knicke sind Ecken.**
 *
 * Nach dem Begradigen liegen drei Punkte auf einer Geraden – der mittlere ist dann kein
 * Knick mehr, sondern ein Rest. Bliebe er stehen, setzte die Rundung dort einen Bogen
 * an, dessen Kontrollpunkt auf der Geraden liegt: unsichtbar, aber vorhanden, und die
 * Linie sähe je nach Vorgeschichte anders aus, obwohl sie denselben Weg beschreibt.
 *
 * Dasselbe gilt für doppelte Punkte. Beides ist derselbe Fall: **wer nichts an der
 * Richtung ändert, ist kein Punkt.**
 */
function simplify(points: Array<[number, number]>): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (const p of points) {
    const b = out[out.length - 1];
    if (b && b[0] === p[0] && b[1] === p[1]) continue;
    const a = out[out.length - 2];
    if (a && b && ((a[0] === b[0] && b[0] === p[0]) || (a[1] === b[1] && b[1] === p[1]))) {
      out[out.length - 1] = p;
      continue;
    }
    out.push(p);
  }
  return out;
}

/**
 * Ein Linienzug mit gerundeten Ecken — die **eine** Stelle, an der eine Ecke entsteht.
 *
 * Vier von Hand geschriebene Bogen-Formeln wären vier Stellen, an denen ein Radius
 * auseinanderlaufen kann; hier ist die Rundung eine Eigenschaft des Linienzugs. Die
 * Richtung fällt aus den Punkten heraus, sie wird nicht angegeben.
 *
 * **Jede** Linie des Bildes geht hier durch – Achse, Ausscherung, Rückführung. Eine
 * zweite Zeichenstelle wäre eine zweite Bildsprache; ein Korrekturversatz an einer
 * Aufrufstelle wäre der Anfang davon.
 */
export function polyPath(points: Array<[number, number]>, r = BEND): string {
  const pts = simplify(straighten(points, 2 * r));
  if (pts.length < 2) return '';

  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1];
    const [cx, cy] = pts[i];
    const [nx, ny] = pts[i + 1];
    const inLen = Math.hypot(cx - px, cy - py);
    const outLen = Math.hypot(nx - cx, ny - cy);
    if (inLen === 0 || outLen === 0) continue;
    const k = Math.min(r, inLen / 2, outLen / 2);
    const ax = cx + ((px - cx) / inLen) * k;
    const ay = cy + ((py - cy) / inLen) * k;
    const bx = cx + ((nx - cx) / outLen) * k;
    const by = cy + ((ny - cy) / outLen) * k;
    d += ` L ${ax} ${ay} Q ${cx} ${cy} ${bx} ${by}`;
  }
  const last = pts[pts.length - 1];
  return `${d} L ${last[0]} ${last[1]}`;
}
