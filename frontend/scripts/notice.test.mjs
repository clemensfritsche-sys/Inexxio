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
  ['components/scan/use-camera.ts', 'Kamera: Autoplay-Politik, Geräteliste, Lampe – das Bild sagt selbst, was geht'],
  ['components/scan/use-barcode-scanner.ts', 'ein unlesbares Bild – der nächste Takt zählt'],
  ['components/auth/passkey-nudge.tsx', 'localStorage voll oder gesperrt – nur eine Erinnerung'],
  ['components/feedback/feedback-pin.tsx', 'die Rolle ist Beiwerk der Testnotiz'],
  ['components/beleg/beleg-page.tsx', 'Nachfragen nach der Zahlung – der nächste Versuch kommt'],
  ['components/beleg/paper.tsx', 'die Schriften des Papiers – gemessen wird trotzdem'],
  ['app/(auth)/abmelden/page.tsx', 'Abmelden – es geht in jedem Fall zur Startseite'],
  ['lib/api.ts', 'der Client selbst: Token-Abruf und ein Fehlerkörper ohne JSON'],
  ['components/chunk-reload-guard.tsx', 'sessionStorage gesperrt – es wird trotzdem einmal neu geladen'],
]);

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* files(p);
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.d.ts')) yield p;
  }
}

/**
 * **Die Formen des Schweigens** – jede macht aus einem Fehler eine leere Liste, ein «nichts»
 * oder gar nichts. Statt ihrer: `tell('…')` (der alte Stand bleibt) oder ein sichtbarer
 * Zustand, der den Grund nennt.
 */
const COMMENT = String.raw`(?:\/\*[^*]*\*\/\s*)?`;
const EMPTY = String.raw`(?:\[\s*\]|null|undefined|false)`;
const SILENT = [
  // .catch(() => {}) – auch mit einem Kommentar darin
  new RegExp(String.raw`\.catch\(\s*\([^)]*\)\s*=>\s*\{\s*${COMMENT}\}\s*\)`, 'g'),
  // .catch(() => []) · null · undefined · false
  new RegExp(String.raw`\.catch\(\s*\([^)]*\)\s*=>\s*${EMPTY}\s*\)`, 'g'),
  // .catch(() => setX([])) · .catch(() => { if (!dead) setX(null); })
  new RegExp(String.raw`\.catch\(\s*\([^)]*\)\s*=>\s*\{?\s*(?:if\s*\([^)]*\)\s*)?\{?\s*set\w+\(\s*${EMPTY}\s*\)\s*;?\s*\}?\s*\}?\s*\)`, 'g'),
  // try { … } catch {} · catch (e) { /* … */ }
  new RegExp(String.raw`\bcatch\s*(?:\(\s*\w*\s*\))?\s*\{\s*${COMMENT}\}`, 'g'),
];

/** Wo im Quelltext eine der Formen steht – `datei:zeile`. */
export function silentIn(text, rel) {
  const found = [];
  for (const re of SILENT) {
    for (const m of text.matchAll(re)) found.push(`${rel}:${text.slice(0, m.index).split('\n').length}`);
  }
  return found;
}

test('kein stummes catch im Quelltext', () => {
  const found = [];
  for (const f of files(src)) {
    const rel = relative(src, f).replaceAll('\\', '/');
    if (ALLOWED.has(rel) || rel === 'lib/notice.ts') continue;
    found.push(...silentIn(readFileSync(f, 'utf8'), rel));
  }
  assert.deepEqual(found, [], `stumm – stattdessen .catch(tell('…')) aus lib/notice:\n${found.join('\n')}`);
});

test('der Wächter erkennt jede Form (gegengeprüft)', () => {
  const forms = [
    'x.catch(() => {})', 'x.catch(() => { /* egal */ })', 'x.catch(() => [])',
    'x.catch(() => null)', 'x.catch(() => undefined)', 'x.catch(() => false)',
    'x.catch(() => setDocs([]))', 'x.catch(() => { if (!dead) setFull(null); })',
    'x.catch(() => { if (!stale) setRows([]); })', 'try { a(); } catch {}',
    'try { a(); } catch (e) { /* ignorieren */ }',
  ];
  for (const f of forms) assert.equal(silentIn(f, 't').length, 1, f);
  const fine = [
    "x.catch(tell('Aufträge'))", 'x.catch((e) => setError(e.message))',
    'x.catch(() => { if (!gone) setCvFailed(true); })', 'try { a(); } catch (e) { report(e); }',
  ];
  for (const f of fine) assert.equal(silentIn(f, 't').length, 0, f);
});
