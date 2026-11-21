/**
 * ►►► **Auto-Save: nichts geht verloren, nichts kommt in falscher Reihenfolge an.** ◄◄◄
 *
 * Gefahren gegen die echten Quellen (`src/lib/saver.ts`, `src/lib/use-autosave.ts`,
 * transpiliert) – die Hooks in echtem React (ein Wurzelknoten ohne DOM: die Testbauteile
 * zeichnen nichts). Die Bug-Formen: ein Stand, der beim Verlassen oder beim Wechsel des
 * Datensatzes im Zeitgeber liegen bleibt (verloren), und zwei PATCH, von denen der ältere
 * den neueren überholt.
 *
 *     node --test scripts/autosave.test.mjs
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
// In node_modules, damit `react` sich von dort auflöst wie im Bauteil.
const out = resolve(here, '../node_modules/.cache/autosave-test');
mkdirSync(out, { recursive: true });
for (const name of ['saver', 'notice', 'use-autosave']) {
  const js = ts.transpileModule(readFileSync(resolve(here, `../src/lib/${name}.ts`), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText.replace(/from '\.\/([\w-]+)'/g, "from './$1.mjs'");
  writeFileSync(resolve(out, `${name}.mjs`), js);
}
const { createSaver } = await import(pathToFileURL(resolve(out, 'saver.mjs')).href);
const { useAutosaveValue, useAutosaveSignature, AUTOSAVE_DELAY } =
  await import(pathToFileURL(resolve(out, 'use-autosave.mjs')).href);
const notice = await import(pathToFileURL(resolve(out, 'notice.mjs')).href);
const React = (await import('react')).default;
const { createRoot } = (await import('react-dom/client')).default;

const tick = () => new Promise((r) => setImmediate(r));
/** Ein Versprechen, das der Test selbst einlöst – so steht ein Speichern «unterwegs». */
function deferred() {
  let resolve; const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

test('zwei Speichervorgänge laufen hintereinander, der zweite mit dem neuesten Wert', async () => {
  const log = [];
  const first = deferred();
  const save = (v) => { log.push(`start ${v}`); return (v === 'a' ? first.promise : Promise.resolve()).then(() => log.push(`ende ${v}`)); };
  const s = createSaver({ delay: 10_000 });
  s.change('a', save);
  const a = s.flush();
  await tick();
  s.change('b', save);
  s.change('c', save);
  const c = s.flush();
  await tick();
  assert.deepEqual(log, ['start a'], 'der zweite darf nicht starten, solange der erste läuft');
  first.resolve();
  await Promise.all([a, c]);
  assert.deepEqual(log, ['start a', 'ende a', 'start c', 'ende c']);
});

test('ein Fehler meldet sich und wird mit flush erneut versucht', async () => {
  const errors = [];
  let calls = 0;
  const s = createSaver({ delay: 10_000, onError: (e) => errors.push(e.message) });
  s.change('x', () => { calls += 1; return calls === 1 ? Promise.reject(new Error('HTTP 503')) : undefined; });
  await s.flush();
  assert.deepEqual(errors, ['HTTP 503']);
  await s.flush();
  assert.equal(calls, 2);
  await s.flush();
  assert.equal(calls, 2, 'gespeichert ist gespeichert – kein drittes Mal');
});

// ─── Die Hooks in echtem React ──────────────────────────────────────────────

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
/** Der kleinste Wurzelknoten, den react-dom annimmt, solange nichts gezeichnet wird. */
function container() {
  const doc = { nodeType: 9, addEventListener() {}, removeEventListener() {} };
  doc.ownerDocument = doc;
  doc.defaultView = globalThis;
  return { nodeType: 1, nodeName: 'DIV', tagName: 'DIV', ownerDocument: doc, addEventListener() {}, removeEventListener() {} };
}
globalThis.window ??= globalThis;
globalThis.document ??= { createElement: () => ({}), addEventListener() {}, activeElement: null };
globalThis.HTMLIFrameElement ??= class {};

function mount(Component, props) {
  const root = createRoot(container());
  const render = (p) => React.act(() => root.render(React.createElement(Component, p)));
  return { render, unmount: () => React.act(() => root.unmount()), ready: render(props) };
}

function Value({ value, record, saves }) {
  useAutosaveValue(value, async (v) => { saves.push(`${record}:${v}`); }, record);
  return null;
}

test('useAutosaveValue: beim Verlassen geht der offene Stand sofort hinaus', async () => {
  const saves = [];
  const view = mount(Value, { value: 'Muster', record: 'A', saves });
  await view.ready;
  await view.render({ value: 'Muster AG', record: 'A', saves });
  assert.deepEqual(saves, [], 'erst nach der Wartezeit oder beim Verlassen');
  await view.unmount();
  await tick();
  assert.deepEqual(saves, ['A:Muster AG']);
});

test('useAutosaveValue: beim Wechsel des Datensatzes geht der Stand an den alten', async () => {
  const saves = [];
  const view = mount(Value, { value: 'alt', record: 'A', saves });
  await view.ready;
  await view.render({ value: 'getippt', record: 'A', saves });
  await view.render({ value: 'geladen B', record: 'B', saves });
  await tick();
  assert.deepEqual(saves, ['A:getippt'], 'der geladene Wert von B ist nicht getippt');
  await view.render({ value: 'getippt B', record: 'B', saves });
  await view.unmount();
  await tick();
  assert.deepEqual(saves, ['A:getippt', 'B:getippt B']);
});

function Signature({ sig, saves }) {
  useAutosaveSignature(sig, true, () => { saves.push(sig); });
  return null;
}

test('useAutosaveSignature: beim Verlassen geht die offene Signatur hinaus', async () => {
  const saves = [];
  const view = mount(Signature, { sig: 'x', saves });
  await view.ready;
  await view.render({ sig: 'y', saves });
  await view.unmount();
  await tick();
  assert.deepEqual(saves, ['y'], 'der neueste Stand, einmal');
});

test('ein gescheitertes Auto-Save steht unten rechts', async () => {
  const seen = [];
  const off = notice.subscribe((list) => seen.push(...list.map((n) => n.text)));
  function Failing({ value }) {
    useAutosaveValue(value, async () => { throw new Error('HTTP 409'); });
    return null;
  }
  const view = mount(Failing, { value: 1 });
  await view.ready;
  await view.render({ value: 2 });
  await view.unmount();
  await tick(); await tick();
  off();
  assert.ok(seen.includes('Nicht gespeichert: Änderung – HTTP 409'), seen.join(' | '));
  assert.ok(AUTOSAVE_DELAY >= 1000);
});
