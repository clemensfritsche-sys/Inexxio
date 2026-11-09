/**
 * ►►► **Was das Vokabular regelt, steht an EINER Stelle – auch im Gebrauch.** ◄◄◄
 *
 * Schlüssel und Wörter kommen generiert aus dem Backend (`lib/vocab.ts`, `scripts/dump_vocab`);
 * dass eine Tabelle jeden Schlüssel kennt, erzwingt der Compiler (`Record<ModuleKey, …>`). Zwei
 * Regeln kann kein Typ prüfen – sie stehen hier (früher in `backend/tests/test_frontend_mirrors.py`):
 *
 * 1. **Die Farbe eines Moduls steht in `lib/modules`** (`MODULE_TONE`, gelesen über
 *    `moduleTone`). Ein harter Farbwert im Prozessbild oder im Editor wäre eine zweite Stelle –
 *    der nächste Modultyp eine Änderung an der Komponente.
 * 2. **Die Beleg-Karte vergleicht Stufen über `VOUCHER_STAGE`**, nie gegen ein Wort
 *    (`'agreed'`, `'zusage'`): ein Wort hängt an der Richtung, ein Schlüssel als Text ist ein
 *    zweiter Ort für denselben Schlüssel.
 *
 *     node --test scripts/vocab-use.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { files, line, parse, strings } from './lib/source.mjs';

/** Prozessbild und Editor – wo Module gemalt werden. */
const PAINTERS = ['lib/process-graph.ts', 'components/erp/flow-column.tsx',
  'components/erp/module-card.tsx', 'components/erp/process-designer.tsx'];
/** Die ganze Karte des Belegs – der Einstieg und jeder Abschnitt. */
const BELEG = ['components/erp/beleg-work.tsx', ...files('components/erp/beleg')];

/** Die Stufen als Schlüssel (aus dem generierten Vokabular gelesen, nicht abgetippt) – und ihre Wörter. */
function stageWords() {
  const vocab = parse('lib/vocab.ts');
  const block = vocab.statements.find((s) => s.getText().startsWith('export const VOUCHER_STAGE'));
  assert.ok(block, 'VOUCHER_STAGE fehlt in lib/vocab.ts – der Wächter wäre blind.');
  const keys = strings(block).map((s) => s.text);
  assert.ok(keys.includes('agreed'), 'VOUCHER_STAGE ohne Stufen gelesen – der Wächter wäre blind.');
  return new Set([...keys, 'angebot', 'zusage', 'abgeschlossen', 'storniert']);
}

const HEX = /#[0-9a-f]{3,8}\b/i;

function hexIn(sf) {
  return strings(sf).filter((s) => HEX.test(s.text)).map((s) => `${line(s)}: '${s.text}'`);
}

function stagesIn(sf, words) {
  return strings(sf).filter((s) => words.has(s.text)).map((s) => `${line(s)}: '${s.text}'`);
}

test('kein harter Farbwert in Prozessbild und Editor – Modulfarben stehen in lib/modules', () => {
  const bad = PAINTERS.flatMap((rel) => hexIn(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Farbe über moduleTone (lib/modules.MODULE_TONE):\n${bad.join('\n')}`);
});

test('die Beleg-Karte vergleicht Stufen über VOUCHER_STAGE, nie gegen ein Wort', () => {
  const words = stageWords();
  assert.ok(BELEG.length > 2, 'Die Abschnitte des Belegs nicht gefunden – der Wächter wäre blind.');
  const bad = BELEG.flatMap((rel) => stagesIn(parse(rel), words).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Stufe als Text statt VOUCHER_STAGE.<schlüssel>:\n${bad.join('\n')}`);
});

test('die Wächter erkennen ihre Bug-Form', () => {
  const words = stageWords();
  const sample = (t) => parse(t, { text: true });
  assert.equal(hexIn(sample("const c = { color: '#9A7238' };")).length, 1);
  assert.equal(hexIn(sample('// #9A7238 im Kommentar\nconst c = moduleTone(t);')).length, 0);
  assert.equal(stagesIn(sample("if (d.stage === 'agreed') go();"), words).length, 1);
  assert.equal(stagesIn(sample('if (d.stage === "zusage") go();'), words).length, 1);
  assert.equal(stagesIn(sample('if (d.stage === VOUCHER_STAGE.agreed) go();'), words).length, 0);
});
