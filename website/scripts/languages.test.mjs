// Die Regeln von t() (src/i18n/t.mjs, WEBSITE_PLAN Entscheid 136): was übersetzt wird und was bleibt.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mapTexts, isText } from '../src/i18n/t.mjs';

const upper = (v, keep = []) => mapTexts(v, keep, (s) => s.toUpperCase());

test('Text wird ersetzt, Daten bleiben', () => {
  const v = { title: 'So läuft es ab.', icon: 'phone', href: '/krantechnik', photo: 'heukran', items: [{ text: 'Wir prüfen.', illo: 'menu/x' }] };
  assert.deepEqual(upper(v), { title: 'SO LÄUFT ES AB.', icon: 'phone', href: '/krantechnik', photo: 'heukran', items: [{ text: 'WIR PRÜFEN.', illo: 'menu/x' }] });
});

test('Nur Werte, Zahlen oder Zeichen sind kein Text', () => {
  assert.equal(isText('{{history.founded}}'), false);
  assert.equal(isText('2026 · 12'), false);
  assert.equal(isText('Seit {{history.founded}}'), true);
});

test('keep lässt Pfade aus – auch mit * für einen Index', () => {
  const v = { brand: { name: 'INEXXIO', claim: 'Ihr Problem.' }, seasons: [{ from: '11-01', label: 'Termin planen', note: 'Winter' }] };
  assert.deepEqual(upper(v, ['brand.name', 'seasons.*.note']), {
    brand: { name: 'INEXXIO', claim: 'IHR PROBLEM.' }, seasons: [{ from: '11-01', label: 'TERMIN PLANEN', note: 'Winter' }],
  });
});

test('Getter bleiben Getter (site.privatePaths)', () => {
  const v = { list: [{ path: '/erp' }], get first() { return this.list[0].path; } };
  const out = upper(v);
  assert.equal(Object.getOwnPropertyDescriptor(out, 'first')?.get !== undefined, true);
  assert.equal(out.first, '/erp');
});
