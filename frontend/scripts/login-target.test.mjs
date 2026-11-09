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

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const mod = await load('lib/login-target.ts');
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

test('Was der Browser zu einer fremden Herkunft auflöst, ist fremd', () => {
  for (const bad of ['/\t/evil.com', '/\n/evil.com', '/\r/evil.com', '/\t\\evil.com',
    '//evil.com', '/\\evil.com', '/\\/evil.com', '/./login', '/erp/../login?x', '/?x=1']) {
    assert.equal(isSafeTarget(bad), false, JSON.stringify(bad));
  }
  // Prozentkodiert bleibt es ein Pfad im eigenen Haus – der Browser löst es nicht zur Herkunft auf.
  for (const own of ['/%09/evil.com', '/%2F%2Fevil.com']) {
    assert.equal(isSafeTarget(own), true, own);
    assert.equal(new URL(own, 'https://inexxio.ch').host, 'inexxio.ch', own);
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
