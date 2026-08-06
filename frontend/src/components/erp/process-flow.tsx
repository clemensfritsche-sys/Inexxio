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
  /** Die Knoten. Bekommt die **gemessene** Rahmenbreite — davon hängt das Layout ab
   *  (drei Spuren oder eine), nicht von einer Media-Query: sonst gäbe es zwei Massstäbe
   *  für dieselbe Frage, und die Linien richten sich ohnehin nach der Messung. */
  children: (width: number) => ReactNode;
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
        {size && children(size.w)}
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
 * Ein Linienzug mit gerundeten Ecken — die **eine** Stelle, an der eine Ecke entsteht.
 *
 * Vier von Hand geschriebene Bogen-Formeln wären vier Stellen, an denen ein Radius
 * auseinanderlaufen kann; hier ist die Rundung eine Eigenschaft des Linienzugs. Die
 * Richtung fällt aus den Punkten heraus, sie wird nicht angegeben.
 */
export function polyPath(points: Array<[number, number]>, r = 10): string {
  const pts = points.filter((p, i) => i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1]);
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
