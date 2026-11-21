/**
 * ►►► **Was ein Modul im Bild und im Editor ist – gefahren, nicht gelesen.** ◄◄◄
 *
 * Die reinen Funktionen aus `src/lib/modules.ts`, `src/lib/process-status.ts` und
 * `src/lib/need.ts` (transpiliert über `lib/source.load`). Früher prüften
 * `backend/tests/test_source_process.py` und `test_source_capture.py` dieselben Regeln als
 * Textstellen (`?? CircleHelp`, `const enough = need.available >= required;` …) – jede
 * Umformulierung brach sie, eine falsche Logik in anderer Schreibweise nicht.
 *
 *     node --test scripts/modules.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { CircleHelp } from 'lucide-react';
import { load } from './lib/source.mjs';

const STUBS = {
  // Der Editor-Baustein bringt React-Bauteile mit; für die Entwurfsform genügt eine leere Zeile.
  '@/components/erp/definition-lines': 'export const emptyLine = () => ({});',
};
const m = await load('lib/modules.ts', STUBS);
const vocab = await load('lib/vocab.ts');
const status = await load('lib/process-status.ts');
const catalog = await load('lib/status-catalog.ts');
const { needOffer } = await load('lib/need.ts');

test('ein unbekanntes Modul sieht unbekannt aus – nie wie ein anderes', () => {
  assert.equal(m.moduleIcon('gibt-es-nicht'), CircleHelp);
  assert.equal(m.moduleIcon(undefined), CircleHelp);
  const known = vocab.MODULE_KEYS.map((k) => m.moduleIcon(k));
  assert.ok(known.every((icon) => icon !== CircleHelp), 'ein bekanntes Modul trägt das Fragezeichen');
  assert.equal(new Set(known).size, known.length, 'zwei Module teilen ein Symbol');

  const unknown = m.moduleTone('gibt-es-nicht');
  assert.match(unknown.fg, /--danger/, 'eine unbekannte Farbfamilie muss kaputt aussehen');
  for (const family of Object.keys(m.MODULE_TONE)) {
    assert.notDeepEqual(unknown, m.MODULE_TONE[family], `Rückfall auf «${family}»`);
    assert.equal(m.moduleTone(family), m.MODULE_TONE[family]);
  }
  assert.equal(m.moduleTone('toString'), unknown, 'ein Prototyp-Name ist keine Familie');
});

test('hinter einem Ausgang meldet der Editor jedes weitere Modul', () => {
  assert.deepEqual(m.chainProblems([{ label: 'A', terminal: false }, { label: 'X', terminal: true }]), []);
  const [problem, ...rest] = m.chainProblems([
    { label: 'A', terminal: false }, { label: 'Aussondern', terminal: true }, { label: 'B', terminal: false }]);
  assert.equal(rest.length, 0);
  assert.match(problem, /«Aussondern»/);
  assert.match(problem, /Schritt 3/);
});

test('die Stichprobe ist eine Zahl – ein halb getippter Anteil geht unverändert hinaus', () => {
  assert.deepEqual(m.samplePayload({ mode: 'all', value: '' }), { percent: 100 });
  assert.deepEqual(m.samplePayload({ mode: 'half', value: '7' }), { percent: 50 });
  assert.deepEqual(m.samplePayload({ mode: 'free', value: '12,' }), { percent: '12,' },
    'die Oberfläche deutet keinen halben Wert zu «alle» um – der Server prüft');
});

test('der Verbrauch fragt nach keinem Ort – den erbt er vom Produkt', () => {
  const consume = { ...m.blankModule(1, 'verbrauch'), target: '100000123' };
  assert.ok(!('target' in m.toModulePayload(consume).config), 'Verbrauch schickt ein Ziel');
  const move = { ...m.blankModule(2, 'bewegen'), target: '100000123' };
  assert.equal(m.toModulePayload(move).config.target, 100000123, 'Bewegen verliert sein Ziel');
});

test('ein Stück in einem Endzustand wird nirgends angeboten – aus dem Katalog, nicht aus einer Liste', () => {
  const ends = catalog.STATUS_CATALOG.filter((s) => s.terminal).map((s) => s.value);
  assert.ok(ends.length > 0, 'der Katalog kennt keinen Endzustand – der Test wäre blind');
  for (const s of catalog.STATUS_CATALOG) {
    assert.equal(status.isPickable(s.value), !s.terminal, s.value);
  }
  assert.equal(status.isPickable('Gesperrt'), true, 'Greifen IST das Aufheben');
  assert.equal(status.isPickable('gibt-es-nicht'), true, 'ein Tippfehler in den Daten mauert nichts ein');
});

// ─── Die Stückliste: was eine Zeile anbietet (#723, #1027) ─────────────────────

// «fehlt» und «am falschen Ort» liefert der Server (`consumption.Need`) – hier wie dort gerechnet.
const need = (o) => {
  const n = { per_unit: 1, required: 3, available: 0, here: 0, place: null, ...o };
  if (!n.place) n.here = n.available;
  return { ...n, missing: Math.max(0, n.required - n.available),
    misplaced: Math.max(0, Math.min(n.required, n.available) - n.here) };
};

test('angeboten wird nur, was gerade Sinn ergibt', () => {
  const at = { object_id: 100000500, label: 'Werkbank' };
  // genug am Arbeitsort → nichts
  assert.deepEqual(pick(needOffer(need({ available: 5, here: 5, place: at }))), [false, 0, false]);
  // genug, liegt nur woanders → holen lassen, genau die Differenz
  assert.deepEqual(pick(needOffer(need({ available: 5, here: 1, place: at }))), [true, 2, false]);
  // reicht nicht, Bestand da → wählen
  assert.deepEqual(pick(needOffer(need({ available: 2 }))), [true, 0, false]);
  // nichts da → nur Nachschub; wählen liesse sich nichts
  assert.deepEqual(pick(needOffer(need({ available: 0 }))), [false, 0, true]);
  // ohne Ortsbedarf zählt alles Verfügbare als «hier»
  assert.deepEqual(pick(needOffer(need({ available: 3 }))), [false, 0, false]);
});

test('gemessen wird am Bedarf des Moduls, nicht am Anteil der Zeile (#1027)', () => {
  // Ein freier Schraubendreher, drei Produkt-Stücke vor dem Modul: nie «genug».
  const offer = needOffer(need({ per_unit: 1, required: 3, available: 1 }));
  assert.equal(offer.enough, false);
  assert.equal(offer.required, 3);
  assert.equal(offer.units, 3);
});

const pick = (o) => [o.choose, o.haul, o.supply];
