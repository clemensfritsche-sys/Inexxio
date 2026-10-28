/**
 * ►►► **Ein Blatt im Kamerabild finden und gerade ziehen** – die Rechnung des Scanners. ◄◄◄
 *
 * Graustufen → weichzeichnen → drei Karten (hell · Kanten · Kanten fein) → je Kontur die
 * konvexe Hülle → auf vier Ecken vereinfacht → das grösste blattartige Viereck. Gerade
 * gezogen wird mit einer Perspektiv-Transformation auf die Seitenlängen des Blatts.
 *
 * Rein: bekommt `cv` (OpenCV.js) und Pixel, gibt Punkte bzw. Pixel zurück – im Browser und
 * im Test dieselbe Funktion. Findet es nichts, gibt es `null` zurück; dann gelten die Ränder
 * des Bildes (der Mensch zieht die Ecken selbst).
 */

/** Ein Punkt in Pixeln des Bildes, aus dem er stammt. */
export interface Pt { x: number; y: number }
/** Die vier Ecken im Uhrzeigersinn ab oben links. */
export type Quad = [Pt, Pt, Pt, Pt];

/** Pixel wie `ImageData` – im Browser genau das, im Test ein Objekt derselben Form. */
export interface Pixels { data: Uint8ClampedArray; width: number; height: number }

// OpenCV.js bringt keine Typen mit – hier steht genau die Fläche, die der Scanner braucht.
interface Mat { delete(): void; rows: number; data: Uint8Array; data32S: Int32Array }
interface MatVector { size(): number; get(i: number): Mat; delete(): void }
export interface Cv {
  Mat: { new (): Mat; ones(rows: number, cols: number, type: number): Mat };
  MatVector: new () => MatVector;
  Size: new (width: number, height: number) => unknown;
  matFromImageData(px: Pixels): Mat;
  matFromArray(rows: number, cols: number, type: number, values: number[]): Mat;
  cvtColor(src: Mat, dst: Mat, code: number): void;
  GaussianBlur(src: Mat, dst: Mat, size: unknown, sigma: number): void;
  Canny(src: Mat, dst: Mat, low: number, high: number): void;
  threshold(src: Mat, dst: Mat, thresh: number, max: number, type: number): number;
  morphologyEx(src: Mat, dst: Mat, op: number, kernel: Mat): void;
  convexHull(points: Mat, hull: Mat, clockwise: boolean, returnPoints: boolean): void;
  findContours(src: Mat, out: MatVector, hierarchy: Mat, mode: number, method: number): void;
  approxPolyDP(curve: Mat, out: Mat, epsilon: number, closed: boolean): void;
  arcLength(curve: Mat, closed: boolean): number;
  contourArea(curve: Mat): number;
  getPerspectiveTransform(from: Mat, to: Mat): Mat;
  warpPerspective(src: Mat, dst: Mat, m: Mat, size: unknown, flags: number, border: number): void;
  COLOR_RGBA2GRAY: number; CV_8U: number; CV_32FC2: number; RETR_LIST: number;
  THRESH_BINARY: number; THRESH_OTSU: number; MORPH_CLOSE: number;
  CHAIN_APPROX_SIMPLE: number; INTER_LINEAR: number; BORDER_REPLICATE: number;
}

/** Kleiner als dieser Anteil des Bildes ist kein Blatt (sondern ein Etikett, ein Schatten). */
export const MIN_AREA = 0.05;
/** Grösser ist es der Bildrand selbst (alles hell), kein Blatt. */
export const MAX_AREA = 0.97;

/** Die Ecken in feste Reihenfolge: oben links, oben rechts, unten rechts, unten links. */
export function order(points: Pt[]): Quad {
  const bySum = [...points].sort((a, b) => (a.x + a.y) - (b.x + b.y));
  const byDiff = [...points].sort((a, b) => (a.y - a.x) - (b.y - b.x));
  return [bySum[0], byDiff[0], bySum[3], byDiff[3]];
}

/** Die Ränder des Bildes – wenn nichts gefunden wurde. */
export function frame(width: number, height: number): Quad {
  return [{ x: 0, y: 0 }, { x: width, y: 0 }, { x: width, y: height }, { x: 0, y: height }];
}

/** Wie weit sich zwei Viererecke unterscheiden – grösste Eckverschiebung, in Bildbreiten. */
export function moved(a: Quad, b: Quad, width: number): number {
  return Math.max(...a.map((p, i) => Math.hypot(p.x - b[i].x, p.y - b[i].y))) / width;
}

/** Fläche eines Vierecks (Gauss), in Pixeln. */
function areaOf(q: Quad): number {
  let a = 0;
  for (let i = 0; i < 4; i++) { const p = q[i], n = q[(i + 1) % 4]; a += p.x * n.y - n.x * p.y; }
  return Math.abs(a) / 2;
}

/** Sieht es aus wie ein Blatt? Jeder Winkel zwischen 45° und 135° (auch schräg fotografiert). */
function sheetLike(q: Quad): boolean {
  for (let i = 0; i < 4; i++) {
    const p = q[(i + 3) % 4], c = q[i], n = q[(i + 1) % 4];
    const ax = p.x - c.x, ay = p.y - c.y, bx = n.x - c.x, by = n.y - c.y;
    const cos = (ax * bx + ay * by) / (Math.hypot(ax, ay) * Math.hypot(bx, by) || 1);
    if (Math.abs(cos) > 0.71) return false;
  }
  return true;
}

/** So viel heller (Grauwert) muss das Blatt innen sein als aussen, an einer Stelle seines Rands. */
const EDGE_CONTRAST = 10;
/** An so viel seines Rands muss es das sein (eine Hand, ein Gegenstand darf den Rest decken) –
 *  und an jeder Seite mindestens an einem Drittel. */
const EDGE_SUPPORT = 0.7;
const SIDE_SUPPORT = 0.35;

/**
 * ►► **Das Blatt finden** – vier Ecken oder `null`. ◄◄
 *
 * Drei Karten liefern Kandidaten: **hell** (Otsu – das Blatt ist heller als der Tisch),
 * **Kanten** (Canny) und **Kanten fein** (wenig Kontrast, weisser Tisch). Jede Kontur wird zur
 * konvexen Hülle (eine Hand am Rand, ein Knick, ein Daumen beissen sich nicht hinein) und so
 * weit vereinfacht, bis vier Ecken bleiben. **Ein Blatt ist es erst, wenn sein Rand trägt**:
 * entlang aller vier Seiten innen heller als aussen (`support`) – Maserung, Schatten und
 * Gegenstände ergeben Vierecke, die das nicht sind. Es gewinnt das grösste, das am besten trägt (Fläche × Rand³).
 */
export function detect(cv: Cv, px: Pixels): Quad | null {
  const src = cv.matFromImageData(px);
  const gray = new cv.Mat();
  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.GaussianBlur(gray, gray, new cv.Size(5, 5), 0);
    const maps: ((m: Mat) => void)[] = [
      (m) => { cv.threshold(gray, m, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU); },
      (m) => cv.Canny(gray, m, 50, 150),
      (m) => cv.Canny(gray, m, 12, 36),
    ];
    const total = px.width * px.height;
    const img = { data: gray.data, width: px.width, height: px.height };
    let best: Quad | null = null;
    let bestScore = 0;
    for (const make of maps) {
      for (const q of quads(cv, make, MIN_AREA * total, MAX_AREA * total)) {
        const s = support(img, q);
        const score = s >= EDGE_SUPPORT ? areaOf(q) * s ** 3 : 0;
        if (score > bestScore) { best = q; bestScore = score; }
      }
    }
    return best;
  } finally {
    src.delete(); gray.delete();
  }
}

/** Die blattartigen Vierecke einer Karte, deren Fläche zwischen `min` und `max` liegt. */
function quads(cv: Cv, make: (m: Mat) => void, min: number, max: number): Quad[] {
  const bin = new cv.Mat();
  const contours = new cv.MatVector();
  const hierarchy = new cv.Mat();
  const kernel = cv.Mat.ones(5, 5, cv.CV_8U);
  try {
    make(bin);
    cv.morphologyEx(bin, bin, cv.MORPH_CLOSE, kernel);
    cv.findContours(bin, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE);
    const out: Quad[] = [];
    for (let i = 0; i < contours.size(); i++) {
      const c = contours.get(i);
      const q = cv.contourArea(c) >= min * 0.5 ? quadOf(cv, c) : null;
      c.delete();
      const area = q ? areaOf(q) : 0;
      if (q && area > min && area < max) out.push(q);
    }
    return out;
  } finally {
    bin.delete(); contours.delete(); hierarchy.delete(); kernel.delete();
  }
}

/** Eine Kontur als Viereck: Hülle, dann vereinfachen, bis vier Ecken bleiben. */
function quadOf(cv: Cv, contour: Mat): Quad | null {
  const hull = new cv.Mat();
  try {
    cv.convexHull(contour, hull, false, true);
    const len = cv.arcLength(hull, true);
    for (const eps of [0.02, 0.03, 0.045, 0.06, 0.08, 0.1]) {
      const approx = new cv.Mat();
      cv.approxPolyDP(hull, approx, eps * len, true);
      const n = approx.rows;
      let q: Quad | null = null;
      if (n === 4) {
        const pts: Pt[] = [];
        for (let k = 0; k < 4; k++) pts.push({ x: approx.data32S[k * 2], y: approx.data32S[k * 2 + 1] });
        q = order(pts);
      }
      approx.delete();
      if (n === 4) return q && sheetLike(q) ? q : null;
      if (n < 4) return null;
    }
    return null;
  } finally {
    hull.delete();
  }
}

/**
 * **Trägt der Rand?** Anteil der Stellen entlang der vier Seiten, an denen es innen um
 * `EDGE_CONTRAST` heller ist als aussen (je 6 px senkrecht zur Seite); 0, wenn eine Seite
 * weniger als `SIDE_SUPPORT` trägt. Wo «aussen» nicht mehr im Bild liegt, wird nicht gezählt;
 * liegt eine ganze Seite auf dem Bildrand, ist es 0 – dort ist kein Rand zu sehen, und ein
 * Blatt, das hinausragt, hätte ohnehin nicht seine Ecken.
 */
export function support(img: { data: Uint8Array; width: number; height: number }, q: Quad): number {
  const cx = (q[0].x + q[1].x + q[2].x + q[3].x) / 4;
  const cy = (q[0].y + q[1].y + q[2].y + q[3].y) / 4;
  const at = (x: number, y: number) => {
    const ix = Math.round(x), iy = Math.round(y);
    return ix < 0 || iy < 0 || ix >= img.width || iy >= img.height ? null : img.data[iy * img.width + ix];
  };
  let good = 0, all = 0;
  for (let i = 0; i < 4; i++) {
    let sideGood = 0, sideAll = 0;
    const a = q[i], b = q[(i + 1) % 4];
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    let nx = -(b.y - a.y) / len, ny = (b.x - a.x) / len;
    if (nx * (cx - a.x) + ny * (cy - a.y) < 0) { nx = -nx; ny = -ny; }   // zeigt nach innen
    for (let t = 0.1; t <= 0.9; t += 0.04) {
      const x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t;
      const inner = at(x + nx * 6, y + ny * 6), outer = at(x - nx * 6, y - ny * 6);
      if (outer === null || inner === null) continue;
      sideAll++;
      if (inner - outer >= EDGE_CONTRAST) sideGood++;
    }
    if (sideAll < 5 || sideGood < SIDE_SUPPORT * sideAll) return 0;
    good += sideGood; all += sideAll;
  }
  return all >= 20 ? good / all : 0;
}

/** Die Grösse des gerade gezogenen Blatts – aus seinen Seitenlängen, höchstens `max` px. */
export function sizeOf(q: Quad, max = 2000): { width: number; height: number } {
  const d = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y);
  const w = Math.max(d(q[0], q[1]), d(q[3], q[2]));
  const h = Math.max(d(q[0], q[3]), d(q[1], q[2]));
  const k = Math.min(1, max / Math.max(w, h, 1));
  return { width: Math.max(1, Math.round(w * k)), height: Math.max(1, Math.round(h * k)) };
}

/** ►► **Gerade ziehen** – das Blatt aus dem Bild, als eigene Pixel. ◄◄ */
export function warp(cv: Cv, px: Pixels, q: Quad, max = 2000): Pixels {
  const { width, height } = sizeOf(q, max);
  const src = cv.matFromImageData(px);
  const dst = new cv.Mat();
  const from = cv.matFromArray(4, 1, cv.CV_32FC2, q.flatMap((p) => [p.x, p.y]));
  const to = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, width, 0, width, height, 0, height]);
  const m = cv.getPerspectiveTransform(from, to);
  try {
    cv.warpPerspective(src, dst, m, new cv.Size(width, height), cv.INTER_LINEAR, cv.BORDER_REPLICATE);
    return { data: new Uint8ClampedArray(dst.data), width, height };
  } finally {
    src.delete(); dst.delete(); from.delete(); to.delete(); m.delete();
  }
}

/**
 * **OpenCV laden** – einmal, erst wenn gescannt wird (~10 MB, `scripts/vendor-opencv.mjs`).
 *
 * Das Modul von OpenCV.js ist selbst «thenable»: wer es als Wert einer Promise auflöst, löst
 * es endlos weiter auf (die Seite hängt). Darum kommt es verpackt (`{ cv }`) zurück, und
 * bereit ist es, sobald `cv.Mat` da ist – nachgesehen, nicht auf ein Ereignis gewartet.
 */
/** Wo OpenCV liegt – die Version im Namen (Cache); derselbe Name in `scripts/vendor-opencv.mjs`. */
export const OPENCV = '/vendor/opencv-4.12.0-release.1.js';

let loading: Promise<{ cv: Cv }> | null = null;
export function loadCv(src = OPENCV, waitMs = 30000): Promise<{ cv: Cv }> {
  if (loading) return loading;
  loading = new Promise<{ cv: Cv }>((resolve, reject) => {
    const w = window as unknown as { cv?: Cv };
    const started = Date.now();
    const poll = () => {
      if (w.cv?.Mat) { resolve({ cv: w.cv }); return; }
      if (Date.now() - started > waitMs) { loading = null; reject(new Error('OpenCV startet nicht')); return; }
      setTimeout(poll, 50);
    };
    if (w.cv) { poll(); return; }
    const s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.onload = poll;
    s.onerror = () => { loading = null; reject(new Error('OpenCV lässt sich nicht laden')); };
    document.head.appendChild(s);
  });
  return loading;
}
