/**
 * ►►► **Tippen sucht – und eine ältere Antwort überholt nie eine neuere** (`src/lib/use-search.ts`). ◄◄◄
 *
 * Die eine Suche beim Tippen (Referenzfeld, Scanner-Vorschläge, Empfänger): hier in echtem
 * React gefahren (ein Wurzelknoten ohne DOM, wie `autosave.test.mjs`). Bug-Form: wer «ab» tippt,
 * während die Antwort zu «a» noch unterwegs ist, sah danach die Treffer zu «a».
 *
 *     node --test scripts/use-search.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const { useSearch } = await load('lib/use-search.ts');
const React = (await import('react')).default;
const { createRoot } = (await import('react-dom/client')).default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window ??= globalThis;
globalThis.document ??= { createElement: () => ({}), addEventListener() {}, activeElement: null };
globalThis.HTMLIFrameElement ??= class {};

function container() {
  const doc = { nodeType: 9, addEventListener() {}, removeEventListener() {} };
  doc.ownerDocument = doc;
  doc.defaultView = globalThis;
  return { nodeType: 1, nodeName: 'DIV', tagName: 'DIV', ownerDocument: doc, addEventListener() {}, removeEventListener() {} };
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

test('eine ältere Antwort überholt nie eine neuere', async () => {
  const pending = {};
  const search = (q) => new Promise((resolve) => { pending[q] = resolve; });
  let seen = null;
  function Probe({ query }) {
    seen = useSearch(query, search, { delay: 0 });
    return null;
  }
  const root = createRoot(container());
  await React.act(async () => root.render(React.createElement(Probe, { query: 'a' })));
  await React.act(() => wait(5));
  await React.act(async () => root.render(React.createElement(Probe, { query: 'ab' })));
  await React.act(() => wait(5));
  assert.deepEqual(Object.keys(pending).sort(), ['a', 'ab'], 'beide Eingaben haben gefragt');
  await React.act(async () => { pending.ab(['neu']); });
  await React.act(async () => { pending.a(['alt']); });
  assert.deepEqual(seen.hits, ['neu']);
  assert.equal(seen.pending, false);
  await React.act(async () => root.unmount());
});

test('ohne Suche oder ohne Eingabe gibt es keine Treffer und keine Anfrage', async () => {
  let asked = 0;
  const search = async () => { asked += 1; return ['x']; };
  let seen = null;
  function Probe({ query, on }) {
    seen = useSearch(query, on ? search : null, { delay: 0 });
    return null;
  }
  const root = createRoot(container());
  await React.act(async () => root.render(React.createElement(Probe, { query: 'abc', on: false })));
  await React.act(async () => root.render(React.createElement(Probe, { query: '  ', on: true })));
  await React.act(() => wait(5));
  assert.equal(asked, 0);
  assert.deepEqual(seen.hits, []);
  await React.act(async () => root.unmount());
});
