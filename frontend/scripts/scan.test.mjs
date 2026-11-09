/**
 * ►►► **Was der Scanner annimmt, anbietet und wohin er ablegt** (`src/lib/scan.ts`). ◄◄◄
 *
 * Gefahren gegen die echte Quelle (transpiliert, `lib/source.load`). Die Regeln:
 * - **«Erkannt» heisst «gibt es»** – ein freier Lookup fragt nach; eine fremde, formal
 *   gültige Nummer kommt nicht still durch, und ein Ausfall der Frage ist nicht «nicht im ERP».
 * - **Die Vorschlagsquelle macht nichts gültig** – was ein Schritt annimmt, sagt allein
 *   `validateForStep`; `suggest` wird dort nicht gelesen.
 * - **Ware zuerst, Ziel zuletzt** – der Ziel-Scan ist die Quittung der Ablage, und das Ziel wird
 *   dort gelesen, wo die Sequenz es hinstellt (auch im Sammel-Scan: EIN Ziel am Ende).
 *
 *     node --test scripts/scan.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './lib/source.mjs';

const scan = await load('lib/scan.ts');
const N = 100000787;

test('ein freier Lookup fragt, ob es die Nummer gibt – und trennt «nein» vom Ausfall', async () => {
  const check = (exists) => scan.objectCodes.check(N, { exists });
  assert.equal(await check(async () => true), null);
  assert.match(await check(async () => false), /100000787 ist nicht im ERP/);
  assert.match(await check(async () => { throw new Error('HTTP 503'); }), /nicht geprüft – HTTP 503/);
  assert.equal(await scan.objectCodes.check(N, {}), null, 'ohne Frage gilt jede gültige Nummer');
});

test('eine Verifikation nimmt nur ihr Ziel – Vorschläge ändern daran nichts', async () => {
  const suggest = async () => [{ objectId: 100000001, label: 'X' }];
  const step = { expected: N, suggest };
  assert.equal(scan.validateForStep(N, step), true);
  assert.equal(scan.validateForStep(100000001, step), false, 'ein Vorschlag wird gültig');
  assert.match(await scan.objectCodes.check(100000001, step), /nicht das erwartete Objekt/);
  const restricted = { restrict: true, candidates: [{ objectId: N, label: 'A' }], suggest };
  assert.equal(scan.validateForStep(100000001, restricted), false);
});

test('ein Schritt bietet an, was er annimmt – ohne dass der Aufrufer eine Liste mitgibt', () => {
  assert.deepEqual(scan.offersFor({ expected: N, label: 'Instanz' }), [{ objectId: N, label: 'Instanz' }]);
  assert.deepEqual(scan.offersFor({}), []);
  const given = [{ objectId: 1, label: 'gewählt' }];
  assert.equal(scan.offersFor({ expected: N, candidates: given }), given);
});

test('Ware zuerst, Ziel zuletzt – und das Ziel ist die letzte Nummer', () => {
  const goods = [{ expected: 1 }, { expected: 2 }];
  const target = { label: 'Zielort' };
  assert.deepEqual(scan.deliverySteps(goods, target), [...goods, target]);
  assert.deepEqual(scan.deliverySteps(goods, null), goods);
  assert.equal(scan.deliveredTo([1, 2, 100000900], true), 100000900);
  assert.equal(scan.deliveredTo([1, 2], false), null, 'ohne Ziel gibt es keinen Ort');
});
