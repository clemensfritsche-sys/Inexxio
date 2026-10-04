// ►►► Der Anzeige-Cache hat zwei Seiten – sie müssen dieselben Wörter sprechen. ◄◄◄
//
// Das Konto-/ERP-Frontend schreibt drei localStorage-Schlüssel (frontend/src/lib/
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

test('beide Seiten kennen dieselben drei Schlüssel', () => {
  const front = keysIn(cache);
  assert.deepEqual(front, ['inexxio_user_contact', 'inexxio_user_fullname', 'inexxio_user_role']);
  assert.deepEqual(keysIn(website), front);
});

test('early.js liest denselben Rollen-Schlüssel und dieselben Personal-Rollen wie isStaff', () => {
  assert.match(early, /localStorage\.getItem\('inexxio_user_role'\)/);
  const body = gate.slice(gate.indexOf('export function isStaff('));
  const staff = (src) => [...src.matchAll(/role === '(\w+)'/g)].map((m) => m[1]).sort();
  const front = staff(body.slice(0, body.indexOf('}')));
  assert.ok(front.length > 0, 'isStaff nennt keine Rolle mehr – der Wächter muss nachgezogen werden');
  assert.deepEqual(staff(early), front);
});

test('Abmelden räumt den ganzen Anzeige-Cache, und zwar vor allem anderen', () => {
  const body = firebase.slice(firebase.indexOf('export async function logout('));
  const fn = body.slice(0, body.indexOf('\n}'));
  assert.ok(fn.includes('clearAccountCache()'), 'logout() räumt den Anzeige-Cache nicht');
  assert.ok(
    fn.indexOf('clearAccountCache()') < fn.indexOf('if (!auth)'),
    'logout() räumt erst nach der Firebase-Prüfung – ohne Firebase bliebe der Name stehen',
  );
});

test('die Website verlinkt das Abmelden auf eine Route, die es im Frontend gibt', async () => {
  const { site } = await import('../src/config/site.mjs');
  assert.equal(site.account.logout.href, '/abmelden');
  read('../frontend/src/app/(auth)/abmelden/page.tsx');
});
