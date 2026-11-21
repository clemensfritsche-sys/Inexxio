/**
 * ►►► **Eine Handlung am Server läuft über `useAction`** (`src/lib/use-action.ts`). ◄◄◄
 *
 * Die Bug-Form: ein eigener Merker `const [busy, setBusy] = useState(false)`, der um einen
 * `api.…`-Aufruf herum auf `true` und wieder auf `false` gesetzt wird – mit eigenem
 * try/catch/finally. Jede Kopie davon vergisst irgendwann etwas (den Fehler leeren, `busy`
 * nach einem Fehler lösen, den Satz des Servers zeigen). Gesucht wird darum genau das: in der
 * Funktion, die einen booleschen Zustand auf `true` setzt, steht ein `api.…`-Aufruf und
 * derselbe Setter mit `false`.
 *
 *     node --test scripts/action.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../src');

/** Datei · Zustand → warum er hier selbst geführt wird. */
const ALLOWED = new Map([
  ['components/erp/document-draft.tsx · setReading',
    'das Lesen des Entwurfs läuft in einem Effekt, der beim Wechsel der Datei verworfen wird (`gone`) – kein Klick'],
  ['lib/assistant.ts · setChoosing', 'das Wissen wird still im Hintergrund neu gewählt – kein Klick, nur eine Anzeige'],
  ['components/erp/beleg-work.tsx · setRefunding',
    'bleibt nach dem Erfolg zu, bis die Zahlung gebucht ist (Webhook) – ein Zustand der Lage, nicht der Anfrage'],
]);

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return files(p);
    return /\.tsx?$/.test(n) && !p.endsWith('types/api.ts') ? [p] : [];
  });
}

const isFn = (n) => ts.isArrowFunction(n) || ts.isFunctionExpression(n) || ts.isFunctionDeclaration(n)
  || ts.isMethodDeclaration(n);

/** Die Setter boolescher Zustände (`useState(false|true)`) und wo sie selbst geführt werden. */
export function offenders(text, name = 'x.tsx') {
  const sf = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const setters = new Set();
  const collect = (n) => {
    if (ts.isVariableDeclaration(n) && ts.isArrayBindingPattern(n.name) && n.initializer
        && ts.isCallExpression(n.initializer) && ts.isIdentifier(n.initializer.expression)
        && n.initializer.expression.text === 'useState') {
      const arg = n.initializer.arguments[0];
      const el = n.name.elements[1];
      if (arg && (arg.kind === ts.SyntaxKind.FalseKeyword || arg.kind === ts.SyntaxKind.TrueKeyword)
          && el && ts.isBindingElement(el) && ts.isIdentifier(el.name)) setters.add(el.name.text);
    }
    ts.forEachChild(n, collect);
  };
  collect(sf);
  const setTo = (n, value) => ts.isCallExpression(n) && ts.isIdentifier(n.expression)
    && setters.has(n.expression.text) && n.arguments[0]?.kind === value;
  const contains = (root, test) => {
    let hit = false;
    const walk = (n) => { if (!hit) { if (test(n)) hit = true; else ts.forEachChild(n, walk); } };
    walk(root);
    return hit;
  };
  const isApi = (n) => ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression)
    && ts.isIdentifier(n.expression.expression) && n.expression.expression.text === 'api';
  const found = new Set();
  const visit = (n) => {
    if (setTo(n, ts.SyntaxKind.TrueKeyword)) {
      let fn = n.parent;
      while (fn && !isFn(fn)) fn = fn.parent;
      const setter = n.expression.text;
      if (fn && contains(fn, isApi)
          && contains(fn, (m) => setTo(m, ts.SyntaxKind.FalseKeyword) && m.expression.text === setter)) {
        found.add(setter);
      }
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return [...found];
}

test('jede Handlung am Server läuft über useAction – ausser mit Grund', () => {
  const seen = new Set();
  const bad = [];
  for (const path of files(src)) {
    const rel = relative(src, path);
    for (const setter of offenders(readFileSync(path, 'utf8'), path)) {
      const key = `${rel} · ${setter}`;
      seen.add(key);
      if (!ALLOWED.has(key)) bad.push(key);
    }
  }
  assert.deepEqual(bad, [], `Ein eigenes busy neben api.… – dafür gibt es useAction:\n${bad.join('\n')}`);
  const stale = [...ALLOWED.keys()].filter((k) => !seen.has(k));
  assert.deepEqual(stale, [], `Ausnahmen ohne Fundstelle – bitte streichen:\n${stale.join('\n')}`);
});

test('der Wächter erkennt die Bug-Form', () => {
  const handRolled = `
    function A() {
      const [busy, setBusy] = useState(false);
      async function save() {
        setBusy(true);
        try { await api.updateCompany(1, {}); } finally { setBusy(false); }
      }
    }`;
  assert.deepEqual(offenders(handRolled), ['setBusy']);
  const promise = `
    function A() {
      const [saving, setSaving] = useState(false);
      const go = () => { setSaving(true); api.timeView(1).finally(() => setSaving(false)); };
    }`;
  assert.deepEqual(offenders(promise), ['setSaving']);
  // Ein Schalter ohne Server (ein Dialog auf, zu) ist keine Handlung.
  assert.deepEqual(offenders(`
    function A() {
      const [open, setOpen] = useState(false);
      const t = () => { setOpen(true); setOpen(false); };
      const run = () => api.timeView(1);
    }`), []);
  assert.deepEqual(offenders(`
    function A() {
      const { busy, run } = useAction();
      const go = () => run(() => api.timeView(1));
    }`), []);
});
