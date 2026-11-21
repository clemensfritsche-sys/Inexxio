/**
 * ►►► **Kleine Regeln mit grosser Reichweite – an der Funktion selbst gefahren.** ◄◄◄
 *
 * Früher als Textsuche in `backend/tests/test_source_{ui,beleg,people}.py`:
 *
 * - **Ein Betrag sieht überall gleich aus** (`lib/utils.formatAmount`): der Tausender-Trenner
 *   ist das gerade `'` – das ICU liefert je nach Laufzeit `’` oder `'`, und zwei Texte an
 *   derselben Stelle sind ein Hydrations-Fehler; die Stellen kommen von der Währung (JPY null,
 *   KWD drei), nicht aus einer festen 2.
 * - **Was man tippen kann, ist die Stelligkeit der Währung** (`controls.numericOnly`, #931).
 * - **Eine Firma heisst überall «Name Rechtsform»** – fertig vom Server (`sites.legal_name`,
 *   #910/#984); `organizationName` liest ihn, statt ihn zu bauen.
 * - **Eine Methode des Clients behält ihr `this`** (`search={api.searchPeople}`, #927).
 *
 *     node --test scripts/format.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const { formatAmount } = await load('lib/utils.ts');
const { numericOnly } = await load('components/erp/controls.tsx');
const { organizationName } = await load('lib/record-name.ts');
const { api } = await load('lib/api.ts', { '@/lib/feed': "export const DATA_CHANGED = 'data-changed';" });

test('ein Betrag: gerades Hochkomma, Stellen der Währung, leer ist «—»', () => {
  assert.equal(formatAmount(12345.6), "12'345.60");
  assert.equal(formatAmount('1234567.891', 3), "1'234'567.891");
  assert.equal(formatAmount(1000, 0), "1'000");
  // Eine Laufzeit, deren ICU das typografische Hochkomma schreibt (so im Browser gemessen):
  const icu = Number.prototype.toLocaleString;
  Number.prototype.toLocaleString = function (...a) { return icu.apply(this, a).replace(/'/g, '\u2019'); };
  try {
    assert.equal(formatAmount(9999.5), "9'999.50", 'das Hochkomma hängt an der Laufzeit');
  } finally {
    Number.prototype.toLocaleString = icu;
  }
  assert.equal(formatAmount(null), '—');
  assert.equal(formatAmount(''), '—');
});

test('ein Zahlenfeld nimmt so viele Stellen, wie die Währung hat', () => {
  assert.equal(numericOnly('12,3456', { decimals: 2 }), '12.34');
  assert.equal(numericOnly('12,3456', { decimals: 3 }), '12.345');
  assert.equal(numericOnly('1200.5', { decimals: 0 }), '12005');
  assert.equal(numericOnly('1.2.3'), '1.23', 'höchstens ein Trenner');
  assert.equal(numericOnly('CHF 1\'200.50'), '1200.50');
  assert.equal(numericOnly('-5', { signed: true }), '-5');
  assert.equal(numericOnly('-5'), '5');
});

test('eine Firma heisst, wie der Server sie nennt – der blosse Name ist nur der Rückfall', () => {
  assert.equal(organizationName({ company_name: 'Muster AG', legal_form: 'AG', legal_name: 'Muster AG' }), 'Muster AG');
  assert.equal(organizationName({ company_name: 'Muster', legal_form: 'GmbH', legal_name: 'Muster GmbH' }), 'Muster GmbH');
  assert.equal(organizationName({ company_name: ' Muster ' }), 'Muster');
  assert.equal(organizationName({ company_name: '' }), null);
});

test('eine Methode des Clients, als Wert weitergereicht, behält ihren Client', () => {
  const { forgetMe } = api;
  assert.doesNotThrow(() => forgetMe(), 'this ging verloren – das Feld bliebe leer, der Fehler stünde in der Konsole');
  const proto = Object.getPrototypeOf(api);
  const methods = Object.getOwnPropertyNames(proto).filter((n) => n !== 'constructor'
    && typeof Object.getOwnPropertyDescriptor(proto, n).value === 'function');
  assert.ok(methods.length > 50, 'Die Methoden nicht gefunden – der Wächter wäre blind.');
  const unbound = methods.filter((n) => !Object.hasOwn(api, n));
  assert.deepEqual(unbound, [], 'nicht gebunden');
});
