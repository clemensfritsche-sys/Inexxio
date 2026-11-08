'use client';

import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState,
  type CSSProperties, type ReactNode,
} from 'react';

/**
 * **Prozess-Fluss — Rahmen, gemessene Anker, berechnete Linien.**
 *
 * Linien nie mit festen Pixelwerten (PROCESS_CORE.md §8): Knoten bestimmen ihre Position im
 * normalen Fluss-Layout (kein `absolute`), Linien werden aus gemessenen Ankern berechnet und
 * als SVG dahinter gelegt (`pointerEvents: none`). Gemessen wird per `ResizeObserver` und nach
 * jedem Commit (ein Knoten kann wandern, ohne seine Grösse zu ändern). Die Kinder rendern erst,
 * wenn die Breite gemessen ist (`useLayoutEffect`, vor dem Paint).
 */

/**
 * **Die Spurmasse — die eine Stelle, an der eine Breite entsteht.** Sie gehören zum Bild,
 * nicht zu den Aufrufern. Gemessen wird der Rahmen, nicht das Fenster (Container- statt
 * Media-Query), in effektiven CSS-Pixeln.
 */
export const LANE = {
  /** Abstand zwischen zwei Spuren — **die Fahrbahn der Querlinien**. */
  GAP: 16,
  /**
   * Abstand zweier Kanäle in dieser Fahrbahn (§1): jede gleichzeitige Abzweigung bekommt eine
   * eigene senkrechte Spur, die Lücke wächst entsprechend.
   */
  CHANNEL: 12,
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
 * Ab dieser Rahmenbreite stehen drei Spuren nebeneinander: 360 + 2·168 + 2·16 = 728 px
 * (≈ 1108 px Fenster). Untere Schranke für eine Abzweigung; mit mehr Kanälen rechnet
 * `flowMetrics` aus der tatsächlichen Lücke.
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
 * Die Spurbreiten zu einer gemessenen Rahmenbreite — eine Formel, keine Stufenliste: erst
 * bekommt die Mitte, was sie braucht (der Fokus), dann gehen die Reste an die Nachbarn.
 */
function flowMetrics(width: number, gutter: number = LANE.GAP): FlowMetrics {
  const { GAP, MID_MIN, MID_MAX, SIDE_MIN, SIDE_MAX } = LANE;
  const gap = Math.max(GAP, Math.round(gutter));
  const mid = clamp(MID_MIN, width - 2 * SIDE_MIN - 2 * gap, MID_MAX);
  const side = clamp(SIDE_MIN, (width - mid - 2 * gap) / 2, SIDE_MAX);
  return {
    lanes: width >= MID_MIN + 2 * SIDE_MIN + 2 * gap,
    mid, side: Math.floor(side), gap, width,
  };
}

/** Wie breit die Spurlücke sein muss, damit ``n`` Kanäle nebeneinander hineinpassen. */
export function gutterFor(channelCount: number): number {
  return LANE.GAP + Math.max(0, channelCount - 1) * LANE.CHANNEL;
}

/** Die x-Koordinate eines Kanals — mittig um die Lücke gelegt, Kanal für Kanal. */
export function channelX(centre: number, channel: number, used: number): number {
  return Math.round(centre + (channel - (used - 1) / 2) * LANE.CHANNEL);
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

interface FlowSize {
  w: number;
  h: number;
}

type Register = (id: string, el: HTMLElement | null) => void;

const Ctx = createContext<Register | null>(null);

// Auf dem Server gibt es kein Layout zu messen; `useLayoutEffect` würde dort nur warnen.
const useIsoLayout = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export function FlowFrame({ children, lines, gutter }: {
  /** Die Knoten, mit den gemessenen Spurmassen (drei Spuren oder eine). */
  children: (metrics: FlowMetrics) => ReactNode;
  /** Die Linien: Anker aller Knoten, Rahmengrösse und dieselben Spurmasse wie die Knoten. */
  lines: (anchors: Record<string, FlowAnchor>, size: FlowSize, m: FlowMetrics) => ReactNode;
  /** Wie breit die Spurlücke sein muss (`gutterFor`), damit alle Kanäle hineinpassen. */
  gutter?: number;
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
    // Nur bei Änderung neuen State schreiben – sonst Messung → Commit → Messung ohne Ende.
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

  // Ein Knoten kann wandern, ohne seine Grösse zu ändern – das sieht nur der Commit.
  useIsoLayout(() => { measure(); });

  const metrics = size ? flowMetrics(size.w, gutter) : null;

  return (
    <Ctx.Provider value={register}>
      <div ref={frameRef} style={{ position: 'relative', width: '100%' }}>
        {/* Ein einziger, durchgehender Linien-Layer über der ganzen Prozessfläche, von keinem
            Container beschnitten; `overflow: visible`, damit kein Zug still fehlt. */}
        <svg
          width={size?.w ?? 0}
          height={size?.h ?? 0}
          style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0,
                   overflow: 'visible' }}
          aria-hidden
        >
          {size && metrics && lines(anchors, size, metrics)}
        </svg>
        {metrics && children(metrics)}
      </div>
    </Ctx.Provider>
  );
}

/**
 * Ein Knoten im Fluss: meldet sich beim Rahmen an und wird gemessen. Was darin steht, ist Sache
 * des Aufrufers – keine Variante je Modultyp (PROCESS_CORE.md §8).
 */
export function FlowNode({ id, children, style }: {
  id: string;
  children: ReactNode;
  style?: CSSProperties;
}) {
  const register = useContext(Ctx);
  // An- und Abmeldung über denselben Ruf (die Callback-Ref bekommt beim Ausbauen `null`);
  // ein Effekt dafür bräche im StrictMode die Messung.
  const ref = useCallback(
    (el: HTMLDivElement | null) => register?.(id, el),
    [register, id],
  );

  return (
    <div
      ref={ref}
      // Der Knoten nennt sich – «keine Linie überlagert einen Knoten» (§4) ist so nachmessbar.
      data-flow-node={id}
      style={{ position: 'relative', zIndex: 1, ...style }}
    >
      {children}
    </div>
  );
}

/** Der Eckenradius – jede Ecke im Bild ist gleich rund. */
export const BEND = 16;

/** Der Abzweige- bzw. Rückführpunkt – sein Durchmesser bestimmt den Takt. */
export const POINT = 9;

/**
 * **Der senkrechte Takt des Flusses.** Zwischen einem Abzweigepunkt und seinem Rückführpunkt
 * liegen zwei Waagrechte (hinaus bei fork + BEND, herein bei join − BEND). Damit dazwischen so
 * viel Luft bleibt, wie der Punkt gross ist:
 *
 *     FLOW_GAP + POINT − 2 · BEND  =  POINT      ⟹  FLOW_GAP = 2 · BEND
 */
export const FLOW_GAP = 2 * BEND;

/**
 * **Ports — feste Andockpunkte am Container.** Eine Linie beginnt und endet an einem Port, nie
 * auf oder hinter einem Knoten; der Port kommt aus der Messung.
 */
type Port = 'top' | 'bottom' | 'left' | 'right' | 'center';

export function port(a: FlowAnchor, side: Port): [number, number] {
  if (side === 'top') return [a.cx, a.top];
  if (side === 'bottom') return [a.cx, a.bottom];
  // Abzweige- und Rückführpunkt haben keine Ränder: die Linie verlässt den Strang im Punkt.
  if (side === 'center') return [a.cx, a.cy];
  return [side === 'left' ? a.left : a.right, a.cy];
}

/**
 * **Kanäle — je Verbindung eine eigene Spur.** Zwei Segmente, deren Spannen sich überschneiden,
 * bekommen verschiedene Spuren: Intervall-Färbung, gierig nach Anfang sortiert (optimal,
 * deterministisch). Die Spannen sind geschlossen – zwei Nachbarn am selben Punkt teilen nie
 * einen Kanal.
 */
export function channels(
  spans: Array<{ key: string; from: number; to: number }>,
): { of: Map<string, number>; used: number } {
  const of = new Map<string, number>();
  const open: Array<{ end: number; ch: number }> = [];
  let used = 0;
  [...spans]
    .map((s) => (s.from <= s.to ? s : { ...s, from: s.to, to: s.from }))
    .sort((a, b) => a.from - b.from || a.to - b.to || a.key.localeCompare(b.key))
    .forEach((s) => {
      for (let i = open.length - 1; i >= 0; i--) if (open[i].end < s.from) open.splice(i, 1);
      const taken = new Set(open.map((o) => o.ch));
      let ch = 0;
      while (taken.has(ch)) ch++;
      of.set(s.key, ch);
      open.push({ end: s.to, ch });
      used = Math.max(used, ch + 1);
    });
  return { of, used };
}

/**
 * **Ein Zittern ist kein Weg.** Ein Stück, kürzer als ``2 · BEND``, wird begradigt statt
 * gerundet: die spätere Koordinate rastet auf die frühere ein, die Ecke dahinter zieht mit.
 * Nur im Inneren – erstes und letztes Stück sind die Stummel am Objekt (§8.1a).
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
 * **Nur echte Knicke sind Ecken**: Punkte auf einer Geraden und doppelte Punkte fallen weg –
 * wer nichts an der Richtung ändert, ist kein Punkt.
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
 * Ein Linienzug mit gerundeten Ecken — die **eine** Stelle, an der eine Ecke entsteht. Jede
 * Linie des Bildes geht hier durch; die Richtung fällt aus den Punkten heraus.
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
    // Ein Endstück darf ganz im Bogen aufgehen (kein Nachbar, mit dem zu teilen wäre) – der
    // Bogen beginnt bzw. endet am Punkt.
    const k = Math.min(r, inLen / (i === 1 ? 1 : 2), outLen / (i === pts.length - 2 ? 1 : 2));
    const ax = cx + ((px - cx) / inLen) * k;
    const ay = cy + ((py - cy) / inLen) * k;
    const bx = cx + ((nx - cx) / outLen) * k;
    const by = cy + ((ny - cy) / outLen) * k;
    d += ` L ${ax} ${ay} Q ${cx} ${cy} ${bx} ${by}`;
  }
  const last = pts[pts.length - 1];
  return `${d} L ${last[0]} ${last[1]}`;
}
