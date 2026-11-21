/**
 * ►►► **Jeder Dialog verhält sich gleich** (Änderungsakte U8, `src/lib/use-dialog.ts`). ◄◄◄
 * Wer `role="dialog"` setzt, holt Fokus, Escape und Tab aus EINER Stelle – sonst hätte jeder
 * Dialog seine eigene Tastatur.
 *
 *     node --test scripts/dialog.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const src = resolve(dirname(fileURLToPath(import.meta.url)), '../src');

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : (p.endsWith('.tsx') ? [p] : []);
  });
}

/** Ein Dialog (das JSX-Attribut, nicht ein Selektor `[role="dialog"]`) ohne das eine Verhalten. */
export function offenders(text) {
  return /\srole="dialog"/.test(text) && !/useDialog\(/.test(text) ? ['ohne useDialog'] : [];
}

test('jeder Dialog nutzt useDialog', () => {
  const bad = files(src).flatMap((p) => offenders(readFileSync(p, 'utf8')).map((w) => `${relative(src, p)}: ${w}`));
  assert.deepEqual(bad, []);
});

test('der Wächter erkennt die Bug-Form', () => {
  assert.deepEqual(offenders('<div role="dialog" onKeyDown={(e) => e.key === \'Escape\' && x()} />'),
    ['ohne useDialog']);
  assert.deepEqual(offenders("t.closest('[role=\"dialog\"]')"), []);
});
