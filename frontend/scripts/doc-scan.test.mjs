/**
 * ►►► **Der Dokumentscanner findet ein gewöhnliches Blatt** (Rückmeldung: «er erkennt ein
 * normales Blatt nicht»). ◄◄◄
 *
 * Gegen die **echte** Quelle (`src/lib/doc-scan.ts`, transpiliert) und das echte OpenCV.js –
 * auf nachgebildeten Kamerabildern (480 px breit wie die Suche im Scanner): ein Blatt mit
 * Text auf dunklem, hellem, weissem und Holz-Tisch, mit Daumen am Rand, Gegenstand daneben,
 * Schatten, unscharf, weit weg, fast bildfüllend. Und ohne Blatt: dann nichts – ein
 * Schein-Blatt löste von selbst eine Aufnahme aus. Die frühere Fassung (eine Karte, die
 * grösste Kontur) fand 6 der 10 Fälle.
 *
 *     node --test scripts/doc-scan.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { createRequire } from 'node:module';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, '../src/lib/doc-scan.ts'), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { detect } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

const loaded = createRequire(import.meta.url)('@techstark/opencv-js');
const cv = loaded instanceof Promise ? await loaded : loaded;
await new Promise((ok) => { if (cv.Mat) ok(); else cv.onRuntimeInitialized = ok; });

const W = 480, H = 640;
const Q = (a) => a.map(([x, y]) => ({ x, y }));
const TILT = Q([[90, 110], [400, 90], [430, 560], [60, 540]]);
const BIG = Q([[30, 40], [455, 25], [470, 615], [15, 600]]);
const SMALL = Q([[150, 200], [330, 190], [340, 440], [140, 450]]);
const DESK = {
  dunkel: () => 60,
  hell: (x, y) => 185 + 12 * Math.sin(x / 9 + Math.sin(y / 40) * 3),
  weiss: (x, y) => 212 + 8 * Math.sin(y / 30),
  holz: (x, y) => 150 + 25 * Math.sin(x / 5 + Math.sin(y / 60) * 4),
};

function inside(q, x, y) {
  let c = false;
  for (let i = 0, j = 3; i < 4; j = i++) {
    const a = q[i], b = q[j];
    if ((a.y > y) !== (b.y > y) && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) c = !c;
  }
  return c;
}

/** Ein Kamerabild: Tisch, darauf (vielleicht) ein Blatt mit Textzeilen, dazu Störungen. */
function photo({ quad = null, desk, thumb = false, thing = false, shadow = 0, noise = 6, blur = 0 }) {
  let s = 1;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
  const data = new Uint8ClampedArray(W * H * 4);
  const mid = quad && { x: (quad[2].x + quad[3].x) / 2, y: (quad[2].y + quad[3].y) / 2 };
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const v = desk(x, y);
      let rgb = [v, v * 0.97, v * 0.9];
      if (quad && inside(quad, x, y)) rgb = y % 18 < 3 && x > 140 && x < 380 && y > 160 && y < 480 ? [60, 60, 60] : [240, 240, 238];
      if (shadow) rgb = rgb.map((c) => c * (1 - shadow * (x / W)));
      if (thing && x > W * 0.86 && y > H * 0.3 && y < H * 0.55) rgb = [40, 40, 45];
      if (thumb && mid && ((x - mid.x) / 40) ** 2 + ((y - mid.y) / 34) ** 2 < 1) rgb = [200, 150, 125];
      const n = (rnd() - 0.5) * 2 * noise, i = (y * W + x) * 4;
      data[i] = rgb[0] + n; data[i + 1] = rgb[1] + n; data[i + 2] = rgb[2] + n; data[i + 3] = 255;
    }
  }
  if (!blur) return { data, width: W, height: H };
  const m = cv.matFromImageData({ data, width: W, height: H });
  cv.GaussianBlur(m, m, new cv.Size(blur, blur), 0);
  const out = { data: new Uint8ClampedArray(m.data), width: W, height: H };
  m.delete();
  return out;
}

const SHEETS = {
  'dunkler Tisch': { quad: TILT, desk: DESK.dunkel },
  'heller Tisch': { quad: TILT, desk: DESK.hell },
  'weisser Tisch': { quad: TILT, desk: DESK.weiss },
  'Holztisch': { quad: TILT, desk: DESK.holz },
  'Daumen am Rand': { quad: TILT, desk: DESK.hell, thumb: true },
  'Gegenstand daneben': { quad: TILT, desk: DESK.holz, thing: true },
  'Schatten': { quad: TILT, desk: DESK.hell, shadow: 0.35 },
  'unscharf': { quad: TILT, desk: DESK.weiss, blur: 9 },
  'fast bildfüllend': { quad: BIG, desk: DESK.holz },
  'weit weg': { quad: SMALL, desk: DESK.hell },
  'stark verrauscht': { quad: TILT, desk: DESK.hell, noise: 20 },
};

for (const [name, scene] of Object.entries(SHEETS)) {
  test(`findet das Blatt: ${name}`, () => {
    const q = detect(cv, photo(scene));
    assert.ok(q, 'nichts gefunden');
    const off = Math.max(...q.map((p, i) => Math.hypot(p.x - scene.quad[i].x, p.y - scene.quad[i].y)));
    assert.ok(off < 0.04 * W, `Ecken ${off.toFixed(0)} px daneben`);
  });
}

for (const [name, desk] of Object.entries(DESK)) {
  test(`ohne Blatt kein Blatt: ${name} Tisch`, () => {
    assert.equal(detect(cv, photo({ desk })), null);
    assert.equal(detect(cv, photo({ desk, thing: true, shadow: 0.3 })), null);
  });
}
