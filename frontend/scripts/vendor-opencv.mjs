// ►►► **OpenCV für den Scanner** – aus dem Paket nach `public/vendor/opencv-<Version>.js` (nicht
// im Repo, ~10 MB; die Version im Namen, weil `*.js` ein Jahr im Cache bleibt). Geladen wird es erst, wenn jemand scannt (`lib/doc-scan.loadCv`). Fehlt das Paket,
// bricht der Build ab: ohne die Datei fände der Scanner kein Blatt (er nähme dann nur Fotos auf).
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const from = join(root, 'node_modules', '@techstark', 'opencv-js', 'dist', 'opencv.js');
// Derselbe Name steht in `src/lib/doc-scan.ts` (OPENCV) – ein Test prüft, dass beide gleich sind.
export const OPENCV = '/vendor/opencv-4.12.0-release.1.js';
const pkg = JSON.parse(readFileSync(join(root, 'node_modules', '@techstark', 'opencv-js', 'package.json'), 'utf8'));
if (!OPENCV.includes(pkg.version)) {
  console.error(`vendor-opencv: Paket ${pkg.version} passt nicht zu ${OPENCV}.`);
  process.exit(1);
}
const to = join(root, 'public', OPENCV);
if (!existsSync(from)) {
  console.error('vendor-opencv: @techstark/opencv-js fehlt – npm ci ausführen.');
  process.exit(1);
}
if (!existsSync(to) || statSync(to).size !== statSync(from).size) {
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
}
console.log(`vendor-opencv: public${OPENCV} bereit.`);
