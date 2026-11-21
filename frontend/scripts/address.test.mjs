/**
 * ►►► **Die Adress-Eingabe: was Google liefert, und wann entschieden wird** (Testnotiz #1044). ◄◄◄
 *
 * *«Die Adresse wird manchmal mit dem Google-Maps-Suchdesign gerendert und manchmal wechselt sie
 * zu einem einfachen Eingabeformular. Zudem wird in dieser Variante die Region nicht korrekt
 * befüllt.»* Zwei Ursachen, beide hier am Verhalten gefahren (früher Textsuche in
 * `backend/tests/test_source_people.py`):
 *
 * 1. **«Noch nicht bekannt» ist nicht «es gibt keinen»**: der Schlüssel kommt vom Server und ist
 *    beim ersten Zeichnen noch nicht da. `useMapsApiKey` antwortet bis dahin `undefined`,
 *    `useGoogleMaps(undefined)` entscheidet nichts – erst `null` heisst `no-key` (dann das
 *    Formular). Vorher wurde aus dem ersten `no-key` für immer das Formular.
 * 2. **Ein Treffer bringt seine Region mit** (`parsePlace`: Kanton bzw. Bundesstaat, kurz vor
 *    lang) – vorher blieb die Region des vorherigen Ortes stehen.
 *
 *     node --test scripts/address.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const React = (await import('react')).default;
const { createRoot } = (await import('react-dom/client')).default;

/** Der Schlüssel des Servers – eine Antwort, die der Test selbst einlöst. */
let answer;
const keys = await load('lib/use-maps-key.ts', {
  '@/lib/api': 'export const api = { getMapsKey: () => globalThis.__mapsKey };',
  '@/lib/notice': 'export const tell = () => () => {};',
});
const maps = await load('lib/use-google-maps.ts');
const { parsePlace } = await load('components/erp/address-field.tsx', {
  '@/lib/use-google-maps': 'export const useGoogleMaps = () => ({ loaded: false, error: null });',
  '@/lib/use-maps-key': 'export const useMapsApiKey = () => undefined;',
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.window ??= globalThis;
globalThis.document ??= { createElement: () => ({}), addEventListener() {}, activeElement: null };
globalThis.HTMLIFrameElement ??= class {};

/** Den Hook in echtem React fahren und jede Antwort mitschreiben. */
async function run(hook, ...args) {
  const seen = [];
  function Probe(props) { seen.push(hook(...props.args)); return null; }
  const doc = { nodeType: 9, addEventListener() {}, removeEventListener() {} };
  doc.ownerDocument = doc;
  doc.defaultView = globalThis;
  const root = createRoot({ nodeType: 1, nodeName: 'DIV', tagName: 'DIV', ownerDocument: doc,
    addEventListener() {}, removeEventListener() {} });
  const render = (a) => React.act(() => root.render(React.createElement(Probe, { args: a })));
  await render(args);
  return { seen, render, unmount: () => React.act(() => root.unmount()) };
}

test('der Schlüssel: erst «noch nicht bekannt», dann die Antwort des Servers', async () => {
  globalThis.__mapsKey = new Promise((r) => { answer = r; });
  const { seen, unmount } = await run(keys.useMapsApiKey);
  assert.equal(seen.at(-1), undefined, 'vor der Antwort ist nichts entschieden');
  await React.act(async () => { answer(null); await globalThis.__mapsKey; });
  assert.equal(seen.at(-1), null, '«es gibt keinen» ist eine Antwort');
  await unmount();
});

test('ohne Antwort entscheidet die Karte nichts – erst «keiner» heisst no-key', async () => {
  const { seen, render, unmount } = await run(maps.useGoogleMaps, undefined);
  assert.deepEqual(seen.at(-1), { loaded: false, error: null }, 'ein undefined ist kein no-key');
  await render([null]);
  assert.deepEqual(seen.at(-1), { loaded: false, error: 'no-key' });
  await unmount();
});

test('ein Treffer bringt Strasse, Ort, Land – und seine Region', () => {
  const comp = (types, long, short = long) => ({ types, long_name: long, short_name: short });
  const hit = parsePlace({ address_components: [
    comp(['route'], 'Bahnhofstrasse'), comp(['street_number'], '1'), comp(['postal_code'], '8001'),
    comp(['locality'], 'Zürich'), comp(['administrative_area_level_1'], 'Zürich', 'ZH'),
    comp(['country'], 'Schweiz', 'CH')] });
  assert.deepEqual({ ...hit }, { street: 'Bahnhofstrasse 1', zip: '8001', city: 'Zürich',
    region: 'ZH', country: 'CH', lat: undefined, lng: undefined });
  assert.equal(parsePlace({ address_components: [] }).region, '', 'ohne Region: leer, nie die vorige');
});
