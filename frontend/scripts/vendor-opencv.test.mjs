import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Der Scanner lädt OpenCV unter dem Namen, den der Build ablegt – stehen zwei verschiedene da,
// findet der Scanner kein Blatt (er nähme nur noch Fotos auf).
test('Scanner und Build nennen dieselbe OpenCV-Datei', () => {
  const name = (src) => src.match(/OPENCV = '([^']+)'/)?.[1];
  const script = name(readFileSync(new URL('./vendor-opencv.mjs', import.meta.url), 'utf8'));
  const lib = name(readFileSync(new URL('../src/lib/doc-scan.ts', import.meta.url), 'utf8'));
  assert.ok(script && script === lib, `${script} ≠ ${lib}`);
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.ok(script.includes(pkg.dependencies['@techstark/opencv-js']), 'Version im Namen = Version im Paket');
});
