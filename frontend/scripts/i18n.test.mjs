/**
 * ►►► **Konto und Anmeldung in jeder Sprache der Website – keine bleibt still zurück.** ◄◄◄
 *
 * `lib/lang.ts`: der deutsche Text ist der Schlüssel, `src/i18n/<sprache>.json` übersetzt ihn. Hier
 * wird jeder Aufruf `t('…')` bzw. `tr('…')` aus dem Syntaxbaum gelesen und verlangt:
 *   - der Schlüssel ist eine feste Zeichenkette (sonst lässt er sich nicht prüfen),
 *   - jede Sprache der Website (`website/src/config/languages.mjs`) hat ein Wörterbuch,
 *   - jede übersetzt jeden Schlüssel, nichts Verwaistes, dieselben Werte `{…}`.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { SRC, calls, files, line, parse, ts } from './lib/source.mjs';
import { SOURCE, languages } from '../../website/src/config/languages.mjs';

const isT = (n) => (n === 't' || n === 'tr');

/** Die Schlüssel eines Syntaxbaums – und was keine feste Zeichenkette ist. */
function keysOf(sf) {
  const keys = [];
  const loose = [];
  for (const c of calls(sf, isT)) {
    const a = c.arguments[0];
    if (a && (ts.isStringLiteral(a) || ts.isNoSubstitutionTemplateLiteral(a))) keys.push(a.text);
    else loose.push(line(c));
  }
  return { keys, loose };
}

/** Nur Dateien, die `lib/lang` einbinden – ein anderes `t` (Zähler, Zeit) zählt nicht. */
const users = files().filter((f) => /from '@\/lib\/lang'|from '\.\/lang'/.test(readFileSync(resolve(SRC, f), 'utf8')));
const all = new Map();
for (const f of users) {
  const { keys, loose } = keysOf(parse(f));
  assert.deepEqual(loose, [], `${f}: t() mit einem Ausdruck statt einer festen Zeichenkette (Zeilen ${loose.join(', ')})`);
  for (const k of keys) all.set(k, f);
}
const values = (s) => [...s.matchAll(/\{\w+\}/g)].map((m) => m[0]).sort().join(' ');
const DIR = resolve(SRC, 'i18n');

test('es gibt Texte zu übersetzen', () => {
  assert.ok(all.size > 50, `nur ${all.size} Schlüssel gefunden – liest der Wächter noch?`);
});

test('jede Sprache der Website hat ein Wörterbuch – und keines mehr', () => {
  const want = languages.filter((l) => l.code !== SOURCE && l.status !== 'planned').map((l) => `${l.code}.json`).sort();
  assert.deepEqual(readdirSync(DIR).filter((n) => n.endsWith('.json')).sort(), want);
});

for (const name of readdirSync(DIR).filter((n) => n.endsWith('.json'))) {
  test(`${name}: vollständig, nichts verwaist, dieselben Werte`, () => {
    const dict = JSON.parse(readFileSync(resolve(DIR, name), 'utf8'));
    const missing = [...all.keys()].filter((k) => !dict[k]?.trim());
    assert.deepEqual(missing, [], `${name}: fehlt`);
    const orphans = Object.keys(dict).filter((k) => !all.has(k));
    assert.deepEqual(orphans, [], `${name}: verwaist – den deutschen Text gibt es nicht mehr`);
    const off = Object.entries(dict).filter(([k, v]) => values(k) !== values(v)).map(([k]) => k);
    assert.deepEqual(off, [], `${name}: andere Werte {…} als im Deutsch`);
  });
}

test('Gegenprobe: ein Ausdruck statt einer Zeichenkette fällt auf', () => {
  const sf = parse("const a = t(label); const b = t('Gespeichert'); const c = tr(`x ${y}`);", { text: true });
  const { keys, loose } = keysOf(sf);
  assert.deepEqual(keys, ['Gespeichert']);
  assert.equal(loose.length, 2);
});

