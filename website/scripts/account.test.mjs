// ►►► Der Anzeige-Cache hat zwei Seiten – sie müssen dieselben Wörter sprechen. ◄◄◄
//
// Das Konto-/ERP-Frontend schreibt vier localStorage-Schlüssel (frontend/src/lib/
// account-cache.ts), die Website liest sie (src/scripts/account.ts, early.js). Benennt eine
// Seite einen Schlüssel um, zeigt die Website still «Anmelden» für Angemeldete – kein
// Fehler, keine Meldung. Dasselbe gilt für die Frage «darf ins ERP?»: early.js baut
// `isStaff` nach, weil es vor dem ersten Zeichnen läuft und nichts importieren kann.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => readFileSync(resolve(ROOT, p), 'utf8');

const website = read('src/scripts/account.ts');
const early = read('src/scripts/early.js');
const cache = read('../frontend/src/lib/account-cache.ts');
const gate = read('../frontend/src/lib/record-status.ts');
const firebase = read('../frontend/src/lib/firebase.ts');

const keysIn = (src) => [...src.matchAll(/'(inexxio_user_\w+)'/g)].map((m) => m[1]).sort();

test('beide Seiten kennen dieselben vier Schlüssel', () => {
  const front = keysIn(cache);
  assert.deepEqual(front, ['inexxio_user_contact', 'inexxio_user_fullname', 'inexxio_user_photo', 'inexxio_user_role']);
  assert.deepEqual(keysIn(website), front);
});

test('early.js liest denselben Rollen-Schlüssel und dieselben Personal-Rollen wie isStaff', () => {
  assert.match(early, /localStorage\.getItem\('inexxio_user_role'\)/);
  const body = gate.slice(gate.indexOf('export function isStaff('));
  const staff = (src) => [...src.matchAll(/role === '(\w+)'/g)].map((m) => m[1]).sort();
  const front = staff(body.slice(0, body.indexOf('}')));
  assert.ok(front.length > 0, 'isStaff nennt keine Rolle mehr – der Wächter muss nachgezogen werden');
  assert.deepEqual(staff(early), front);
  // Dieselbe Regel steht in account.ts (syncRole) – für einen Cache, der sich NACH dem Laden
  // ändert (Konto/ERP schreiben ihn nach der Anmeldung).
  const sync = website.slice(website.indexOf('function syncRole('));
  assert.deepEqual(staff(sync.slice(0, sync.indexOf('\n}'))), front);
});

test('Abmelden räumt den ganzen Anzeige-Cache – unbedingt, und erst nach dem Abmelden', () => {
  // Die Regel: ohne Firebase und bei einem Fehler bleibt kein Name stehen (unbedingt), und
  // ein später Profil-Abruf kann den Cache nicht zurückschreiben (erst signOut, dann räumen).
  // Früher hiess sie «vor allem anderen» – genau diese Reihenfolge liess den Rückschreiber
  // durch, und man musste zweimal abmelden.
  const body = firebase.slice(firebase.indexOf('export async function logout('));
  // Nur der Code: die Begründung im Kommentar nennt dieselben Wörter.
  const fn = body.slice(0, body.indexOf('\n}')).replace(/^\s*\/\/.*$/gm, '');
  assert.ok(fn.includes('clearAccountCache()'), 'logout() räumt den Anzeige-Cache nicht');
  assert.ok(!/return/.test(fn.slice(0, fn.indexOf('clearAccountCache()'))),
    'logout() kann vor dem Räumen zurückkehren – ohne Firebase bliebe der Name stehen');
  assert.ok(fn.indexOf('signOut(') < fn.indexOf('finally') && fn.indexOf('finally') < fn.indexOf('clearAccountCache()'),
    'logout() räumt nicht im finally nach signOut – ein später Profil-Abruf schriebe den Cache zurück');
});

test('die Website verlinkt das Abmelden auf eine Route, die es im Frontend gibt', async () => {
  const { site } = await import('../src/config/site.mjs');
  assert.equal(site.account.logout.href, '/abmelden');
  read('../frontend/src/app/(auth)/abmelden/page.tsx');
});
