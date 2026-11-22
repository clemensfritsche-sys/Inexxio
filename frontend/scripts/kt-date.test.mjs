/**
 * ►►► **Das Geburtsdatum im Konto, wie man es tippt** (`form/kt-section.maskDate`). ◄◄◄ Bug-Form
 * (Rückmeldung 22.11.2026): «17/12/1997» wurde zu «17.121997» – nach dem ersten Punkt setzte die
 * Maske keinen zweiten mehr.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const { maskDate } = await load('components/form/kt-section.tsx', {
  './field': 'export const Input = () => null;',
  '@/lib/lang': 'export const useT = () => (s) => s;',
});

test('jede Schreibweise wird TT.MM.JJJJ', () => {
  for (const typed of ['17/12/1997', '17.12.1997', '17121997', '17-12-1997', '17 12 1997']) {
    assert.equal(maskDate(typed), '17.12.1997', typed);
  }
  assert.equal(maskDate('1.5.1980'), '1.5.1980');
  assert.equal(maskDate('1/5/1980'), '1.5.1980');
});

test('beim Tippen: der Punkt kommt mit der nächsten Ziffer oder dem Trennzeichen', () => {
  const steps = ['1', '17', '17/', '17/1', '17/12', '17/12/', '17/12/19'];
  assert.deepEqual(steps.map(maskDate), ['1', '17', '17.', '17.1', '17.12', '17.12.', '17.12.19']);
  // Die Maske gibt ihr eigenes Ergebnis wieder unverändert zurück – auch beim Löschen.
  for (const v of ['17.', '17', '17.12.', '17.12', '17.12.1997']) assert.equal(maskDate(v), v);
  assert.equal(maskDate('171'), '17.1');
  assert.equal(maskDate('17.12.19971'), '17.12.1997', 'das Jahr hat vier Ziffern');
});
