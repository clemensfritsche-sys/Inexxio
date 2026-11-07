/**
 * ►►► **«Übernehmen» versteckt einen Vorschlag nur für eine Weile** (`src/lib/settled.ts`). ◄◄◄
 *
 * Anlass: ein Dauer-Merker blendete einen übernommenen Vorschlag für immer aus – auch wenn das
 * Speichern danach scheiterte und der Server ihn weiter als offen meldete. Geprüft: sofort weg,
 * nach `SETTLE_MS` wieder da (dann zählt der Server).
 *
 *     node --test scripts/settled.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../src');
const js = ts.transpileModule(readFileSync(join(src, 'lib/settled.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const settled = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('lokal entschieden: sofort weg, nach SETTLE_MS wieder vom Server', () => {
  const t0 = 1_000_000;
  assert.equal(settled.isSettled(7, t0), false);
  settled.markSettled(7, t0);
  assert.equal(settled.isSettled(7, t0 + 1), true);
  assert.equal(settled.isSettled(7, t0 + settled.SETTLE_MS - 1), true);
  assert.equal(settled.isSettled(7, t0 + settled.SETTLE_MS), false);
  assert.equal(settled.isSettled(7, t0 + 1), false, 'abgelaufen ist abgelaufen – kein Dauer-Merker');
  assert.equal(settled.isSettled(8, t0 + 1), false);
});

test('lib/proposals blendet nur über lib/settled aus – kein eigener Dauer-Merker', () => {
  const code = readFileSync(join(src, 'lib/proposals.ts'), 'utf8');
  assert.match(code, /isSettled\(/);
  assert.doesNotMatch(code, /new Set<number>\(\)/);
});
