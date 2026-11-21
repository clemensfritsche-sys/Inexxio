/**
 * ►►► **«Öffnen» bringt den ganzen Vorschlag in den Entwurf.** ◄◄◄
 *
 * Ein Entwurf ist die Form derselben Route (`POST /erp/orders`, `POST /erp/articles`). Früher kam
 * vom Auftrag nur die erste Zeile (Artikel, Menge) an, vom Artikel nur die einfachen Felder – die
 * Schritte der KI verschwanden still. Gefahren werden die reinen Funktionen aus
 * `src/lib/proposal-draft.ts`: jede Zeile, jeder Schritt mit seinen Einstellungen, die
 * Wiederholung; was nicht passt, steht in `left`.
 *
 *     node --test scripts/proposal-draft.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const STUBS = {
  '@/components/erp/definition-lines': `export const NEU = 'neu'; export const LAGER = 'lager';
    export const emptyLine = (key) => ({ key, articleObjectId: null, quantity: 1, origin: 'lager', units: [], returns: true });`,
};
const { orderFromProposal, articleFromProposal } = await load('lib/proposal-draft.ts', STUBS);
const m = await load('lib/modules.ts', STUBS);

const STEPS = [
  { module_type: 'datenerfassung', config: {
    points: [{ label: 'Durchmesser', type: 'measure', target: 12.5, tolerance: 0.1, unit: 'mm' },
      { label: 'Sauber?', type: 'bool' }],
    sample: { percent: 25 } } },
  { module_type: 'verbrauch', config: { lines: [{ article: 100000101, quantity: 4 }] } },
  { module_type: 'bewegen', config: { target: 100000123 } },
  { module_type: 'beleg', config: { direction: 'in', parties: [{ party: 100000201 }], payment_days: 30,
    prices: [{ article: 100000101, price: '120.00' }] } },
  { module_type: 'aussondern', config: { mode: 'block', reason: 'Riss im Gehäuse' } },
];

/** Was der Entwurf wieder hinausschickt – derselbe Weg wie «Freigeben». */
const sent = (steps) => steps.map(m.toModulePayload);

test('ein Auftrag kommt mit allen Zeilen, allen Schritten und der Wiederholung an', () => {
  const got = orderFromProposal({
    lines: [
      { article_object_id: 100000101, quantity: 3, origin: 'neu' },
      { article_object_id: 100000102, quantity: 2, origin: 'lager',
        units: [{ number: '100000300-1', from_order: 100000400 }, { number: '100000300-2' }], returns: false },
    ],
    steps: STEPS,
    loop: { every: 'week', first: '2026-12-01', count: 4, takes: [null, 'fifo'] },
    date: { kind: 'until', on: '2026-12-20' },
  });
  assert.deepEqual(got.left, []);
  assert.deepEqual(got.date, { kind: 'until', on: '2026-12-20' });
  assert.equal(got.lines.length, 2, 'eine Zeile ging verloren');
  assert.deepEqual(got.lines.map((l) => [l.articleObjectId, l.quantity, l.origin]),
    [[100000101, 3, 'neu'], [100000102, 2, 'lager']]);
  assert.deepEqual(got.lines[1].units, [{ number: '100000300-1', fromOrder: 100000400 },
    { number: '100000300-2', fromOrder: null }]);
  assert.equal(got.lines[1].returns, false);
  assert.deepEqual(got.steps.map((s) => s.moduleType), STEPS.map((s) => s.module_type));
  const out = sent(got.steps);
  assert.equal(out[0].config.points.length, 2);
  assert.deepEqual(out[0].config.points[0],
    { label: 'Durchmesser', type: 'measure', target: 12.5, tolerance: 0.1, unit: 'mm' });
  assert.deepEqual(out[0].config.sample, { percent: 25 });
  assert.deepEqual(out[1].config.lines, [{ article: 100000101, quantity: 4 }]);
  assert.equal(out[2].config.target, 100000123);
  assert.equal(out[3].config.direction, 'in');
  assert.equal(out[3].config.payment_days, '30');
  assert.deepEqual(out[3].config.prices, [{ article: 100000101, price: '120.00' }]);
  assert.deepEqual(out[4].config, { mode: 'block', reason: 'Riss im Gehäuse' });
  assert.equal(got.loop.every, 'week');
  assert.equal(got.loop.end, 'count');
  assert.equal(got.loop.count, '4');
  assert.equal(got.loop.takes[got.lines[1].key], 'fifo');
});

test('ein Datum, das der Entwurf nicht kennt, nennt er oben', () => {
  const got = orderFromProposal({ date: { kind: 'bald', on: '2026-12-20' } });
  assert.equal(got.date, null);
  assert.equal(got.left.length, 1);
});

test('ein Artikel kommt mit seinen Schritten und seinem Vorgänger an', () => {
  const got = articleFromProposal({ name: 'Welle', weight_kg: 2, steps: STEPS, replaces_object_id: 100000099 },
    ['name', 'weight_kg']);
  assert.deepEqual(got.left, []);
  assert.equal(got.replaces, 100000099);
  assert.deepEqual(sent(got.steps).map((s) => s.module_type), STEPS.map((s) => s.module_type));
  assert.deepEqual(sent(got.steps)[4].config, { mode: 'block', reason: 'Riss im Gehäuse' });
});

test('was der Entwurf nicht darstellen kann, verschwindet nicht still', () => {
  const got = orderFromProposal({
    lines: [{ article_object_id: 100000101, quantity: 1, origin: 'irgendwo', colour: 'rot' }],
    steps: [{ module_type: 'teleport', config: {} },
      { module_type: 'bewegen', config: { target: 100000123, speed: 9 } }],
    priority: 'hoch',
  });
  const text = got.left.join(' | ');
  for (const lost of ['priority', 'colour', 'irgendwo', 'teleport', 'speed']) {
    assert.match(text, new RegExp(lost), `«${lost}» verschwand still`);
  }
  assert.equal(got.steps.length, 1, 'ein unbekanntes Modul wird kein leerer Schritt');
  const art = articleFromProposal({ name: 'X', colour: 'rot' }, ['name']);
  assert.match(art.left.join(), /colour/);
});

test('ohne Zeilen bleibt eine leere Zeile zum Ausfüllen', () => {
  const got = orderFromProposal({});
  assert.equal(got.lines.length, 1);
  assert.equal(got.lines[0].articleObjectId, null);
  assert.equal(got.loop, null);
});
