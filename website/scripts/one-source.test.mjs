// Wächter: was mehr als ein Skript braucht, steht EINMAL – und die Skripte lesen es dort.
//   npm test
//
//  - die Pfade des ERP (site.erpPaths): check-site, merge-hosting und robots.txt
//  - der Modus (siteMode/isLive in src/lib/text.mjs): Astro-Konfiguration und Prüfskripte
//  - der Ort im Fliesstext (site.address über {{address.*}}): kein Literal in den Inhalten
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site, onErpPath } from '../src/config/site.mjs';
import { plain } from '../src/lib/text.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (/** @type {string} */ rel) => readFileSync(join(ROOT, rel), 'utf8');

test('ERP-Pfade: eine Liste – jede Datei darauf ist erkannt, eine ähnlich benannte nicht', () => {
  for (const { path } of site.erpPaths) {
    const name = path.slice(1);
    for (const rel of [name, `${name}.html`, `${name}/index.html`]) assert.ok(onErpPath(rel), rel);
    assert.ok(!onErpPath(`${name}x.html`), `${name}x.html`);
  }
  assert.ok(!onErpPath('kontakt.html') && !onErpPath('index.html'));
  assert.deepEqual(site.privatePaths, ['/erp', '/konto', '/login', '/abmelden', '/api/']);
});

test('ERP-Pfade: die Skripte tragen keine eigene Liste', () => {
  for (const rel of ['scripts/check-site.mjs', 'scripts/merge-hosting.mjs']) {
    const code = read(rel);
    assert.match(code, /onErpPath\(/, `${rel} fragt site.erpPaths nicht`);
    assert.doesNotMatch(code, /['"/(|]konto\b/, `${rel} nennt die Pfade des ERP selbst`);
  }
});

test('Modus: gelesen und geprüft nur in src/lib/text.mjs', () => {
  for (const rel of ['astro.config.mjs', 'scripts/check-site.mjs', 'scripts/check-content.mjs']) {
    assert.doesNotMatch(read(rel), /process\.env\.SITE_MODE/, `${rel} liest SITE_MODE selbst`);
  }
});

test('Ort: die Inhalte setzen ihn aus site.address ein, statt ihn auszuschreiben', () => {
  const dir = join(ROOT, 'src/content');
  const files = [
    ...readdirSync(dir).filter((f) => f.endsWith('.ts')).map((f) => `src/content/${f}`),
    'src/content/legal/impressum.md',
  ];
  const { city, street, zip } = site.address;
  for (const rel of files) {
    for (const literal of [city, street, zip]) assert.ok(!read(rel).includes(literal), `${rel} schreibt «${literal}» aus`);
  }
  assert.equal(plain('{{address.home}}'), 'Tuttwil-Wängi TG');
  assert.equal(plain('{{address.town}}'), 'Tuttwil-Wängi');
});
