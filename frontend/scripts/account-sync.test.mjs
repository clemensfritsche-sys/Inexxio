/**
 * ►►► **Ein später Profil-Abruf macht kein Abmelden rückgängig.** ◄◄◄
 *
 * Auf `/abmelden` läuft auch `AccountSync`: sein Abruf (`api.getMe`) kam nach dem Räumen des
 * Anzeige-Caches an und schrieb Name und Rolle zurück – die Website zeigte weiter einen
 * Angemeldeten, man musste zweimal abmelden. Wer **nach** einem `await` schreibt, fragt nach, ob
 * die Sitzung noch besteht (`currentUid()`). Dass `logout` erst abmeldet und dann unbedingt
 * räumt, prüft `website/scripts/account.test.mjs`. Früher Textsuche in
 * `backend/tests/test_source_people.py`; hier in echtem React gefahren.
 *
 *     node --test scripts/account-sync.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const React = (await import('react')).default;
const { createRoot } = (await import('react-dom/client')).default;

/** Was der Test steuert: wer angemeldet ist, die Antwort des Servers, was geschrieben wird. */
const world = globalThis.__sync = { uid: null, onAuth: null, me: null, written: [] };
const { AccountSync } = await load('components/layout/account-sync.tsx', {
  '@/lib/firebase': `export const currentUid = () => globalThis.__sync.uid;
    export const onAuthChange = (cb) => { globalThis.__sync.onAuth = cb; return () => {}; };`,
  '@/lib/api': 'export const api = { getMe: () => globalThis.__sync.me };',
  '@/lib/account-cache': ['clearAccountCache', 'rememberContact', 'rememberName', 'rememberPhoto', 'rememberRole']
    .map((n) => `export const ${n} = (v) => globalThis.__sync.written.push(['${n}', v]);`).join('\n'),
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window ??= globalThis;
globalThis.window.addEventListener ??= () => {};
globalThis.window.removeEventListener ??= () => {};
globalThis.document ??= { createElement: () => ({}), addEventListener() {}, activeElement: null };
globalThis.HTMLIFrameElement ??= class {};

async function mount() {
  const doc = { nodeType: 9, addEventListener() {}, removeEventListener() {} };
  doc.ownerDocument = doc;
  doc.defaultView = globalThis;
  const root = createRoot({ nodeType: 1, nodeName: 'DIV', tagName: 'DIV', ownerDocument: doc,
    addEventListener() {}, removeEventListener() {} });
  await React.act(() => root.render(React.createElement(AccountSync)));
  return () => React.act(() => root.unmount());
}

const PROFILE = { role: 'employee', first_name: 'Lea', last_name: 'Muster', email: 'l@x.ch', phone: null };

test('wer zwischen Abruf und Antwort abgemeldet wurde, bekommt keinen Namen zurück', async () => {
  const unmount = await mount();
  let reply;
  world.me = new Promise((r) => { reply = r; });
  world.uid = 'u1';
  const running = world.onAuth({ uid: 'u1', photoURL: null });
  world.uid = null;                                  // abgemeldet, während der Abruf läuft
  reply(PROFILE);
  await running;
  assert.deepEqual(world.written.filter(([n]) => n === 'rememberRole' || n === 'rememberName'), [],
    'der späte Abruf schreibt einen Abgemeldeten zurück in den Kopf');
  await unmount();
});

test('wer angemeldet bleibt, bekommt Rolle und Namen', async () => {
  world.written = [];
  const unmount = await mount();
  world.me = Promise.resolve(PROFILE);
  world.uid = 'u2';
  await world.onAuth({ uid: 'u2', photoURL: null });
  assert.deepEqual(world.written.filter(([n]) => n === 'rememberRole'), [['rememberRole', 'employee']]);
  assert.deepEqual(world.written.filter(([n]) => n === 'rememberName'), [['rememberName', 'Lea Muster']]);
  await unmount();
});
