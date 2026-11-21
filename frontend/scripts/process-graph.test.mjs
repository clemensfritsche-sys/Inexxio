/**
 * ►►► **Das Prozessbild als reine Funktionen** (`src/lib/process-graph.ts`). ◄◄◄
 *
 * Gefahren gegen die echte Quelle (transpiliert); die drei Hilfen von aussen
 * (`chainProblems`, `statusLabel`, `whenTitle`) sind ersetzt – geprüft wird hier, was das
 * Bild aus einem Graph macht: die Kette eines Entwurfs, die Zeilenfolge einer Spalte, die
 * Historie am Prozessobjekt und die Äste der Herkunft.
 *
 *     node --test scripts/process-graph.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const STUBS = {
  "import { chainProblems } from '@/lib/modules';": 'const chainProblems = () => [];',
  "import { statusLabel } from '@/lib/process-status';": 'const statusLabel = (s) => s ?? "—";',
  "import { whenTitle } from '@/lib/when';": 'const whenTitle = (iso) => `am ${iso}`;',
};
let source = readFileSync(resolve(here, '../src/lib/process-graph.ts'), 'utf8');
for (const [line, stub] of Object.entries(STUBS)) {
  assert.ok(source.includes(line), `Import nicht gefunden: ${line}`);
  source = source.replace(line, stub);
}
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const g = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

const step = (id, terminal = false) => ({ id, moduleType: 'datenerfassung', label: `M${id}`, tone: null, terminal });

test('ein Entwurf ist die Kette Start → Module → Ende', () => {
  const graph = g.definitionGraph([step(1), step(2)]);
  assert.deepEqual(graph.nodes.map((n) => n.id), ['start', 'module:1', 'module:2', 'end']);
  assert.deepEqual(graph.edges.map((e) => `${e.frm}>${e.to}`), ['start>module:1', 'module:1>module:2', 'module:2>end']);
  assert.ok(graph.edges.every((e) => e.kind === 'axis' && !e.walked));
});

test('hinter einem Ausgang gibt es kein Ende', () => {
  const graph = g.definitionGraph([step(1), step(2, true)]);
  assert.deepEqual(graph.nodes.map((n) => n.id), ['start', 'module:1', 'module:2']);
});

test('die Zeilen: Kopf, Herkunft, Knoten, Stücke auf ihrer Kante, Rückführung zuletzt', () => {
  const graph = {
    nodes: [{ id: 'start', kind: 'start' }, { id: 'module:1', kind: 'module', at: 1 }, { id: 'end', kind: 'end' }],
    edges: [
      { id: 'a', frm: 'start', to: 'module:1', kind: 'axis', units: [{ status: 'x', count: 2 }] },
      { id: 'b', frm: 'module:1', to: 'end', kind: 'axis', units: [] },
      { id: 'o', frm: 'module:1', to: 'order:9', kind: 'out', units: [{ status: 'y', count: 1 }] },
    ],
    problems: [],
  };
  const rows = g.columnRows(graph, { head: true, tail: true, journeyIn: true, returns: true });
  assert.deepEqual(rows.map((r) => r.key),
    ['head', 'journey-in', 'start', 'on:a', 'module:1', 'on:o', 'tail', 'end', 'return']);
  assert.equal(g.rowOfNode(rows, 'module:1'), 4);
  assert.equal(g.rowOfNode(rows, 'fehlt'), -1);
  assert.deepEqual(g.axisEdges(graph).map((e) => e.id), ['a', 'b']);
});

test('die Historie steht am Prozessobjekt – Start und Ende eingeschlossen', () => {
  const events = [
    { kind: 'start', step_id: null, unit_number: '1-1', status_before: null, status_after: 'Im Prozess', created_at: 't1', actor: 'A' },
    { kind: 'pass', step_id: 7, unit_number: '1-1', status_before: 'Im Prozess', status_after: 'Im Prozess', created_at: 't2', actor: 'B' },
    { kind: 'end', step_id: null, unit_number: '1-1', status_before: 'Im Prozess', status_after: 'Freigegeben', created_at: 't3', actor: 'C' },
  ];
  assert.equal(g.historyTip(events, { id: 'start', kind: 'start' }), '1-1 · — → Im Prozess · am t1 · A');
  assert.equal(g.historyTip(events, { id: 'module:7', kind: 'module', at: 7 }), '1-1 · Im Prozess → Im Prozess · am t2 · B');
  assert.match(g.historyTip(events, { id: 'end', kind: 'end' }), /Freigegeben/);
  assert.equal(g.historyTip(events, { id: 'module:8', kind: 'module', at: 8 }), undefined);
  assert.match(g.historyTip(events, { id: 'end', kind: 'end' }, 10), /letzten 3 von 10/);
});

test('Herkunft: erst die neu Erzeugten, dann höchstens drei Nachbarn', () => {
  const stops = [1, 2, 3, 4].map((n) => ({ object_id: 100000000 + n }));
  assert.deepEqual(g.journeyKeys(stops, [{ label: 'A', count: 2 }]),
    ['new:0', 100000001, 100000002, 100000003]);
  assert.equal(g.hasJourney([], []), false);
  assert.equal(g.hasJourney([], [{ label: 'A', count: 1 }]), true);
  assert.equal(g.journeyId('in', 5), 'j:in:5');
});
