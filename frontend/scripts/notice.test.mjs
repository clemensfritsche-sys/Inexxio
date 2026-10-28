/**
 * ►►► **Ein gescheiterter Abruf ist nie stumm** (`src/lib/notice.ts`). ◄◄◄
 *
 * Anlass: das Lesen der KI scheiterte an der Zeitgrenze des Hostings, und der Entwurf zeigte
 * nichts – `.catch(() => {})`. 34 solche Stellen machten aus jedem Ladefehler eine leere Liste.
 * Geprüft: die Meldung selbst (Wortlaut, einmal je fünf Minuten) und dass im Quelltext kein
 * neues stummes `catch` entsteht.
 *
 *     node --test scripts/notice.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../src');
const js = ts.transpileModule(readFileSync(join(src, 'lib/notice.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const notice = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('die Meldung nennt, was fehlt, und den Grund vom Server', () => {
  const seen = [];
  const off = notice.subscribe((list) => seen.push(list.map((n) => n.text)));
  notice.tell('Aufträge')(new Error('Server nicht erreichbar (HTTP 503)'));
  notice.tell('Postfach', 'Nicht abgeglichen')('kein Error-Objekt');
  off();
  const last = seen.at(-1);
  assert.ok(last.includes('Nicht geladen: Aufträge – Server nicht erreichbar (HTTP 503)'));
  assert.ok(last.includes('Nicht abgeglichen: Postfach – keine Antwort vom Server'));
});

test('dieselbe Meldung kommt nur einmal je fünf Minuten', () => {
  let count = 0;
  const off = notice.subscribe(() => { count += 1; });
  const before = count;
  notice.notify('Nicht geladen: Zu tun – x', 1_000);
  notice.notify('Nicht geladen: Zu tun – x', 2_000);
  notice.notify('Nicht geladen: Zu tun – x', 1_000 + 5 * 60 * 1000 + 1);
  off();
  assert.equal(count - before, 2);
});

/** Stellen, an denen Schweigen richtig ist – mit Grund. */
const ALLOWED = new Map([
  ['components/scan/use-camera.ts', 'video.play() – die Autoplay-Politik, kein Abruf'],
]);

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* files(p);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.d.ts')) yield p;
  }
}

test('kein stummes catch im Quelltext', () => {
  const silent = /\.catch\(\s*\(\s*\)\s*=>\s*\{\s*(\/\*[^*]*\*\/\s*)?\}\s*\)/g;
  const found = [];
  for (const f of files(src)) {
    const rel = relative(src, f).replaceAll('\\', '/');
    if (ALLOWED.has(rel) || rel === 'lib/notice.ts') continue;
    const text = readFileSync(f, 'utf8');
    for (const m of text.matchAll(silent)) {
      found.push(`${rel}:${text.slice(0, m.index).split('\n').length}`);
    }
  }
  assert.deepEqual(found, [], `stumm – stattdessen .catch(tell('…')) aus lib/notice:\n${found.join('\n')}`);
});
