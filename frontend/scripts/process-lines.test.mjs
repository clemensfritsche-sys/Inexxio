/**
 * ►►► **Die Linien des Prozessbildes** (`components/erp/process-flow.tsx`). ◄◄◄
 *
 * Der Graph kommt vom Server (`services/flow.py`, geprüft in `backend/tests/test_flow_graph.py`);
 * die Oberfläche legt ihn aus und zeichnet. Früher prüfte das Backend hier den Text der
 * Komponenten. Jetzt:
 *
 * 1. **Verhalten der reinen Funktionen**: zwei Abzweigungen, deren Spannen sich überschneiden
 *    oder berühren, bekommen verschiedene Kanäle (sonst liegen zwei Wege aufeinander); die Lücke
 *    wächst mit den Kanälen; eine Linie dockt an einem Port; ein Zittern wird begradigt; eine
 *    Ecke ist ein Bogen; der Takt lässt zwischen Abzweigung und Rückführung so viel Luft, wie der
 *    Punkt gross ist (`FLOW_GAP + POINT − 2·BEND = POINT`).
 * 2. **Eine Stelle zeichnet** (Regel über den Quelltext der Bild-Dateien): ein `<path>` (die zwei
 *    Stärken in `Stroke`, keine gestrichelte dritte), ein Linien-Layer (`<svg>`), und keine gemessene Koordinate mit einer
 *    nackten Zahl verschoben (`a.cx + 4` – der Anfang einer zweiten Geometrie, PROCESS_CORE §8).
 *
 *     node --test scripts/process-lines.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { find, jsx, line, load, parse, ts } from './lib/source.mjs';

const flow = await load('components/erp/process-flow.tsx');

/** Das Prozessbild – jede Datei, die eine Linie, eine Spalte oder einen Knoten setzt. */
const DIAGRAM = ['components/erp/process-flow.tsx', 'components/erp/process-columns.tsx',
  'components/erp/flow-column.tsx', 'components/erp/module-card.tsx', 'lib/process-graph.ts'];

// ─── 1. Verhalten ────────────────────────────────────────────────────────────

test('überschneidende oder berührende Spannen bekommen verschiedene Kanäle', () => {
  const { of, used } = flow.channels([
    { key: 'a', from: 1, to: 4 }, { key: 'b', from: 2, to: 3 }, { key: 'c', from: 4, to: 6 },
    { key: 'd', from: 7, to: 9 }]);
  assert.notEqual(of.get('a'), of.get('b'), 'überschneidend – ein Kanal');
  assert.notEqual(of.get('a'), of.get('c'), 'am selben Punkt – ein Kanal (die Spannen sind geschlossen)');
  assert.equal(of.get('d'), 0, 'eine freie Spanne nimmt den ersten Kanal');
  assert.equal(used, 2);
  assert.equal(flow.channels([{ key: 'r', from: 5, to: 2 }]).of.get('r'), 0, 'rückwärts ist dieselbe Spanne');
});

test('die Lücke wächst mit den Kanälen, und die Kanäle liegen mittig in ihr', () => {
  assert.ok(flow.gutterFor(3) > flow.gutterFor(2) && flow.gutterFor(2) > flow.gutterFor(1));
  assert.equal(flow.gutterFor(0), flow.gutterFor(1));
  const xs = [0, 1, 2].map((c) => flow.channelX(100, c, 3));
  assert.equal(xs[1], 100);
  assert.equal(xs[1] - xs[0], xs[2] - xs[1]);
  assert.ok(xs[2] - xs[0] <= flow.gutterFor(3), 'die Kanäle passen in ihre Lücke');
});

test('eine Linie dockt an einem Port am Rand, nie in der Fläche', () => {
  const a = { cx: 50, cy: 20, top: 10, bottom: 30, left: 0, right: 100 };
  assert.deepEqual(flow.port(a, 'top'), [50, 10]);
  assert.deepEqual(flow.port(a, 'bottom'), [50, 30]);
  assert.deepEqual(flow.port(a, 'left'), [0, 20]);
  assert.deepEqual(flow.port(a, 'right'), [100, 20]);
  assert.deepEqual(flow.port(a, 'center'), [50, 20]);
});

test('ein Linienzug: Ecken sind Bögen, Geraden haben keine, ein Zittern wird begradigt', () => {
  assert.equal(flow.polyPath([[0, 0], [0, 100]]), 'M 0 0 L 0 100');
  assert.equal(flow.polyPath([[0, 0], [0, 50], [0, 100]]), 'M 0 0 L 0 100', 'ein Punkt auf der Geraden ist keine Ecke');
  const bend = flow.polyPath([[0, 0], [0, 100], [100, 100]]);
  assert.equal((bend.match(/Q/g) ?? []).length, 1, 'eine Ecke, ein Bogen');
  const jitter = flow.polyPath([[0, 0], [0, 100], [3, 100], [3, 200]]);
  assert.ok(!jitter.includes('Q'), `drei Pixel Versatz sind keine zwei Ecken: ${jitter}`);
  assert.equal(flow.polyPath([[5, 5]]), '');
});

test('der Takt: zwischen Abzweigung und Rückführung bleibt so viel Luft, wie der Punkt gross ist', () => {
  assert.equal(flow.FLOW_GAP + flow.POINT - 2 * flow.BEND, flow.POINT);
});

// ─── 2. Eine Stelle zeichnet ─────────────────────────────────────────────────

const MEASURED = new Set(['cx', 'cy', 'top', 'bottom', 'left', 'right']);

/** `a.cx + 4`, `top - 2` … – eine gemessene Koordinate, mit einer nackten Zahl verschoben. */
function nudges(sf) {
  const measured = (e) => ts.isPropertyAccessExpression(e) && MEASURED.has(e.name.text);
  return find(sf, (n) => ts.isBinaryExpression(n)
    && [ts.SyntaxKind.PlusToken, ts.SyntaxKind.MinusToken].includes(n.operatorToken.kind)
    && ((measured(n.left) && ts.isNumericLiteral(n.right)) || (measured(n.right) && ts.isNumericLiteral(n.left))))
    .map((n) => `${line(n)}: ${n.getText()}`);
}

test('ein <path> und ein Linien-Layer für das ganze Bild', () => {
  const trees = DIAGRAM.map((rel) => parse(rel));
  const where = (tag) => trees.flatMap((sf, i) => jsx(sf, tag).map((el) => `${DIAGRAM[i]}:${line(el)}`));
  assert.equal(where('path').length, 1, `Mehr als eine Stelle zeichnet eine Linie: ${where('path')}`);
  assert.equal(where('svg').length, 1, `Mehr als ein Linien-Layer: ${where('svg')}`);
  const dashed = trees.flatMap((sf, i) => find(sf, (n) => ts.isIdentifier(n) && n.text === 'strokeDasharray')
    .map((n) => `${DIAGRAM[i]}:${line(n)}`));
  assert.deepEqual(dashed, [], 'Zwei Stärken, sonst nichts – ob zurückgeführt wird, sagt die Anwesenheit der Linie');
});

test('keine gemessene Koordinate mit einer nackten Zahl verschoben', () => {
  const bad = DIAGRAM.flatMap((rel) => nudges(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Ein benanntes Mass (BEND, LEAD …) statt einer Zahl:\n${bad.join('\n')}`);
});

test('der Wächter erkennt die Bug-Form', () => {
  const sample = (t) => parse(t, { text: true });
  assert.equal(nudges(sample('const y = a.cy + 4;')).length, 1);
  assert.equal(nudges(sample('const y = 2 - b.top;')).length, 1);
  assert.equal(nudges(sample('const y = a.cy + BEND; const n = list.length + 1;')).length, 0);
  assert.equal(jsx(sample('const a = <svg><path d={d} /></svg>;'), 'path').length, 1);
});
