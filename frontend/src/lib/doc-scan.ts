/**
 * ►►► **Ein Blatt im Kamerabild finden und gerade ziehen** – die Rechnung des Scanners. ◄◄◄
 *
 * Dieselbe Methode wie jscanify, ohne dessen Node-Abhängigkeiten: Graustufen → weichzeichnen →
 * Kanten (Canny) → die grösste geschlossene Kontur → auf vier Ecken vereinfacht. Gerade
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
  dilate(src: Mat, dst: Mat, kernel: Mat): void;
  findContours(src: Mat, out: MatVector, hierarchy: Mat, mode: number, method: number): void;
  approxPolyDP(curve: Mat, out: Mat, epsilon: number, closed: boolean): void;
  arcLength(curve: Mat, closed: boolean): number;
  contourArea(curve: Mat): number;
  isContourConvex(curve: Mat): boolean;
  getPerspectiveTransform(from: Mat, to: Mat): Mat;
  warpPerspective(src: Mat, dst: Mat, m: Mat, size: unknown, flags: number, border: number): void;
  COLOR_RGBA2GRAY: number; CV_8U: number; CV_32FC2: number; RETR_EXTERNAL: number;
  CHAIN_APPROX_SIMPLE: number; INTER_LINEAR: number; BORDER_REPLICATE: number;
}

/** Kleiner als dieser Anteil des Bildes ist kein Blatt (sondern ein Etikett, ein Schatten). */
export const MIN_AREA = 0.2;

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

/** ►► **Das Blatt finden** – vier Ecken oder `null`. ◄◄ */
export function detect(cv: Cv, px: Pixels): Quad | null {
  const src = cv.matFromImageData(px);
  const gray = new cv.Mat();
  const edges = new cv.Mat();
  const contours = new cv.MatVector();
  const hierarchy = new cv.Mat();
  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.GaussianBlur(gray, gray, new cv.Size(5, 5), 0);
    cv.Canny(gray, edges, 50, 150);
    const kernel = cv.Mat.ones(3, 3, cv.CV_8U);
    cv.dilate(edges, edges, kernel);
    kernel.delete();
    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);
    let best: Quad | null = null;
    let bestArea = MIN_AREA * px.width * px.height;
    for (let i = 0; i < contours.size(); i++) {
      const c = contours.get(i);
      const approx = new cv.Mat();
      cv.approxPolyDP(c, approx, 0.02 * cv.arcLength(c, true), true);
      const area = Math.abs(cv.contourArea(approx));
      if (approx.rows === 4 && area > bestArea && cv.isContourConvex(approx)) {
        const pts: Pt[] = [];
        for (let k = 0; k < 4; k++) pts.push({ x: approx.data32S[k * 2], y: approx.data32S[k * 2 + 1] });
        best = order(pts);
        bestArea = area;
      }
      approx.delete();
      c.delete();
    }
    return best;
  } finally {
    src.delete(); gray.delete(); edges.delete(); contours.delete(); hierarchy.delete();
  }
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
