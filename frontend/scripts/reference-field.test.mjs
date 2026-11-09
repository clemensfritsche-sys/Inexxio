/**
 * ►►► **«Welchen Datensatz meinst du?» hat EINE Bauart – und der Scanner hängt an der Wurzel.** ◄◄◄
 *
 * 1. **Kein Auswahlfeld mit fertiger Liste über Datensätze** (`<select>`, `Select`,
 *    `SelectField`): nicht durchsuchbar, bei tausend Artikeln tausend Knoten je Zeile, und wer
 *    «100000743» tippte, fand je nach Stelle etwas oder nichts (#738). Dafür gibt es
 *    `ObjectSelect` (Nummer ODER Name, Kamera im Feld). Aufzählungen (Währung, Land) bleiben.
 * 2. **`ScanProvider` steht genau einmal, im Wurzel-Layout**: jedes Referenzfeld trägt die
 *    Kamera, also braucht jede Seite den Scanner (das Konto stürzte ab, als er am ERP hing);
 *    ein zweiter darunter hiesse zwei Dialoge.
 *
 *     node --test scripts/reference-field.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { files, jsx, line, parse, stripComments, ts } from './lib/source.mjs';

const LISTS = ['select', 'Select', 'SelectField'];

/** Auswahlfelder mit fertiger Liste, deren Inhalt Objektnummern trägt. */
function recordSelects(sf) {
  return LISTS.flatMap((tag) => jsx(sf, tag))
    .map((n) => (ts.isJsxOpeningElement(n) ? n.parent : n))
    .filter((el) => /\bobject_id\b/.test(stripComments(el.getText())))
    .map((el) => line(el));
}

test('kein natives Auswahlfeld über Datensätze – dafür ObjectSelect', () => {
  const bad = files().flatMap((rel) => recordSelects(parse(rel)).map((l) => `${rel}:${l}`));
  assert.deepEqual(bad, [], `Eine Referenz wählt man mit ObjectSelect:\n${bad.join('\n')}`);
});

function providers(rel) {
  return jsx(parse(rel), 'ScanProvider').length;
}

test('der Scanner steht genau einmal, im Wurzel-Layout', () => {
  const where = files().filter((rel) => providers(rel) > 0);
  assert.deepEqual(where, ['app/layout.tsx']);
  assert.equal(providers('app/layout.tsx'), 1);
});

test('der Wächter erkennt die Bug-Form', () => {
  const s = (t) => recordSelects(parse(t, { text: true }));
  assert.equal(s('const x = <select>{arts.map((a) => <option key={a.object_id}>{a.name}</option>)}</select>;').length, 1);
  assert.equal(s('const x = <SelectField options={arts.map((a) => ({ value: a.object_id, label: a.name }))} />;').length, 1);
  assert.equal(s("const x = <Select value={c} options={CURRENCIES} />;").length, 0);
  assert.equal(s('const x = <ObjectSelect value={id} search={api.searchPlaces} />;').length, 0);
});
