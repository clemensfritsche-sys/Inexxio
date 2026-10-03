/**
 * ►►► **Nach der Anmeldung geht es nie auf «/»** (Oktober 2026). ◄◄◄
 *
 * Seit die öffentliche Website «/» besitzt, landete ein frisch angemeldeter Mensch dort –
 * ohne Konto, ohne ERP-Link, ohne jedes Zeichen, dass er angemeldet ist. Diese Prüfungen
 * halten die eine Antwort fest, die Dialog, Route und Magic Link teilen
 * (`src/lib/login-target.ts`): genanntes Ziel → gemerktes Ziel → Vorgabe → Startplatz der
 * Rolle; und nie eine fremde Adresse.
 *
 * Gefahren gegen die **echte** Quelle (transpiliert, nicht nachgebaut). `isStaff` kommt
 * ebenfalls aus seiner echten Datei – eine zweite Fassung hier wäre die Stelle, an der der
 * Wächter grün bleibt, während die Rollenfrage anders lautet.
 *
 *     node --test scripts/login-target.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(resolve(here, '../src/lib', p), 'utf8');

const staff = read('record-status.ts').match(/export function isStaff[\s\S]*?\n}\n/);
assert.ok(staff, 'isStaff in record-status.ts nicht gefunden');
const source = read('login-target.ts').replace(/^import \{ isStaff \} from '\.\/record-status';$/m, staff[0]);
assert.ok(!source.includes("from './record-status'"), 'Import nicht ersetzt');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const mod = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const { startPage, isSafeTarget, loginTarget, REDIRECT_KEY } = mod;

/** Ein Browser in zwei Angaben: die Adresszeile und der Speicher. */
function browser(search = '', stored = {}) {
  const store = new Map(Object.entries(stored));
  globalThis.window = { location: { search } };
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  return store;
}

test('Startplatz: ins ERP, wer dort arbeitet – sonst ins Konto', () => {
  assert.equal(startPage('admin'), '/erp');
  assert.equal(startPage('employee'), '/erp');
  assert.equal(startPage('user'), '/konto');
  assert.equal(startPage(null), '/konto');
});

test('Nie «/», nie zurück zur Anmeldung, nie eine fremde Adresse', () => {
  for (const bad of ['/', '//evil.example', '/\\evil.example', 'https://evil.example',
    '/login', '/login/verify', '/login?from=/erp', '', null, undefined]) {
    assert.equal(isSafeTarget(bad), false, String(bad));
  }
  for (const ok of ['/erp', '/konto', '/agb', '/erp?select=100000001', '/loginhilfe']) {
    assert.equal(isSafeTarget(ok), true, ok);
  }
});

test('Ohne Ziel: der Startplatz der Rolle (der gemeldete Fehler: vorher «/»)', () => {
  browser();
  assert.equal(loginTarget('employee'), '/erp');
  browser();
  assert.equal(loginTarget('user'), '/konto');
});

test('Reihenfolge: ?from= vor gemerktem Ziel vor Vorgabe', () => {
  browser('?from=/erp', { [REDIRECT_KEY]: '/konto' });
  assert.equal(loginTarget('user', '/agb'), '/erp');
  browser('', { [REDIRECT_KEY]: '/konto' });
  assert.equal(loginTarget('employee', '/agb'), '/konto');
  browser('');
  assert.equal(loginTarget('employee', '/agb'), '/agb');
});

test('Ein gemerktes Ziel gilt einmal', () => {
  const store = browser('', { [REDIRECT_KEY]: '/konto' });
  loginTarget('employee');
  assert.equal(store.has(REDIRECT_KEY), false);
});

test('Eine fremde Adresse im ?from= wird übergangen, nicht befolgt', () => {
  browser('?from=//evil.example');
  assert.equal(loginTarget('employee'), '/erp');
  browser('?from=/');
  assert.equal(loginTarget('user'), '/konto');
});
