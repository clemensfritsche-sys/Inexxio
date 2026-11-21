/**
 * ►►► **Hausregeln, die für jede Datei gelten** (CLAUDE.md, Leitbild). ◄◄◄
 *
 * Früher als Textsuche in `backend/tests/test_source_{beleg,ui}.py`. Je Regel ein Wächter,
 * je Wächter die Gegenprobe an einem Beispieltext:
 *
 * 1. **Eine Oberfläche fragt eine Eigenschaft, nie den Modultyp** (`step.verifies`,
 *    `step.moves`, `can`): ein Modulschlüssel als Text steht nur in `lib/modules.ts`. Sonst
 *    fehlt beim nächsten Modul derselben Art die Zeile (#945/#950).
 * 2. **`busy` sperrt Handlungen, nie Geometrie** (#1009/#1016): in einer Datei mit Auto-Save
 *    entscheidet `busy` nie, ob etwas gezeichnet wird – sonst springt die Karte bei jedem
 *    Speichern.
 * 3. **Kein Steuerzeichen im Quelltext** (#943): PostgreSQL nimmt in `text` kein NUL auf; über
 *    die Stecknadel landet, was die Seite hergibt, in einer Erfassung.
 * 4. **Ein Firmenname wird nie zusammengesetzt** (#910/#984): «Name Rechtsform» kommt fertig
 *    vom Server (`sites.legal_name`, ohne «Muster AG AG»); ein `company_name + legal_form` im
 *    Browser ist die zweite Fassung einer Regel mit Ausnahme.
 * 5. **Die Hausregeln in ESLint sind scharf** – geprüft wird, dass ESLint die Bug-Form wirklich
 *    abweist (ein toter `useState`-Setter, `toLocaleString`, ein Datum über das ICU, ein
 *    Rollenvergleich, `disabled={busy}` an einem Feld), nicht, wie die Konfiguration aussieht.
 *
 *     node --test scripts/house.test.mjs
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { ESLint } from 'eslint';
import { SRC, calls, files, find, line, parse, read, strings, ts } from './lib/source.mjs';

// ─── 1. Der Modultyp steht an einer Stelle ───────────────────────────────────

/** Die Modulschlüssel – aus dem generierten Vokabular gelesen, nicht abgetippt. */
function moduleKeys() {
  const vocab = parse('lib/vocab.ts');
  const block = vocab.statements.find((s) => s.getText().startsWith('export const MODULE_KEYS'));
  assert.ok(block, 'MODULE_KEYS fehlt in lib/vocab.ts – der Wächter wäre blind.');
  const keys = strings(block).map((s) => s.text);
  assert.ok(keys.includes('beleg'), 'MODULE_KEYS ohne Schlüssel gelesen – der Wächter wäre blind.');
  return new Set(keys);
}

function moduleNames(sf, keys) {
  return strings(sf).filter((s) => keys.has(s.text)).map((s) => `${line(s)}: '${s.text}'`);
}

test('ein Modultyp als Text steht nur in lib/modules.ts', () => {
  const keys = moduleKeys();
  const bad = files().filter((rel) => rel !== 'lib/modules.ts')
    .flatMap((rel) => moduleNames(parse(rel), keys).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Die Oberfläche fragt eine Eigenschaft des Schritts, nicht seinen Typ:\n${bad.join('\n')}`);
});

// ─── 2. busy und die Geometrie ───────────────────────────────────────────────

const isBusy = (e) => (ts.isIdentifier(e) && e.text === 'busy')
  || (ts.isPrefixUnaryExpression(e) && ts.isIdentifier(e.operand) && e.operand.text === 'busy');
const isNull = (e) => e.kind === ts.SyntaxKind.NullKeyword;

const isJsx = (e) => {
  let x = e;
  while (x && ts.isParenthesizedExpression(x)) x = x.expression;
  return !!x && (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x) || ts.isJsxFragment(x));
};

/** `busy && <…>`, `!busy && <…>`, `busy ? null : <…>` – busy entscheidet, ob etwas da ist. */
function busyDraws(sf) {
  return find(sf, (n) => (ts.isBinaryExpression(n)
      && n.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
      && isBusy(n.left) && isJsx(n.right))
    || (ts.isConditionalExpression(n) && isBusy(n.condition)
      && ((isNull(n.whenTrue) && isJsx(n.whenFalse)) || (isNull(n.whenFalse) && isJsx(n.whenTrue)))))
    .map((n) => `${line(n)}: ${n.getText().slice(0, 60)}`);
}

test('in einer Datei mit Auto-Save entscheidet busy nie, ob etwas da ist', () => {
  const saving = files().filter((rel) => calls(parse(rel), (c) => /^useAutosave/.test(c)).length);
  assert.ok(saving.length > 3, 'Keine Datei mit Auto-Save gefunden – der Wächter wäre blind.');
  const bad = saving.flatMap((rel) => busyDraws(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `busy sperrt (disabled), es blendet nichts aus:\n${bad.join('\n')}`);
});

// ─── 3. Steuerzeichen ────────────────────────────────────────────────────────

const CONTROL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/;

test('kein Steuerzeichen im Quelltext', () => {
  const bad = files().filter((rel) => CONTROL.test(read(rel)));
  assert.deepEqual(bad, [], `Diese Dateien tragen ein Steuerzeichen (NUL & Co.):\n${bad.join('\n')}`);
});

// ─── 4. Der Firmenname ───────────────────────────────────────────────────────

const NAME_PARTS = ['company_name', 'legal_form'];

/** Ein `+` oder eine Vorlage, in der Name und Rechtsform zusammenkommen. */
function joinedNames(sf) {
  const names = (n) => new Set(find(n, (m) => (ts.isPropertyAccessExpression(m) && NAME_PARTS.includes(m.name.text))
    || (ts.isIdentifier(m) && NAME_PARTS.includes(m.text))).map((m) => (m.name ?? m).text));
  const joining = find(sf, (n) => ts.isTemplateExpression(n)
    || (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.PlusToken
      && !ts.isBinaryExpression(n.parent)));
  return joining.filter((n) => names(n).size === 2).map((n) => `${line(n)}: ${n.getText().slice(0, 60)}`);
}

test('ein Firmenname wird nicht aus Name und Rechtsform zusammengesetzt', () => {
  const bad = files().flatMap((rel) => joinedNames(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Der Name kommt fertig vom Server (legal_name):\n${bad.join('\n')}`);
});

// ─── 5. ESLint weist die Bug-Formen ab ───────────────────────────────────────

const eslint = new ESLint({ cwd: resolve(SRC, '..') });

async function rules(code, file = 'src/components/erp/probe.tsx') {
  const [r] = await eslint.lintText(code, { filePath: file });
  return r.messages.filter((m) => m.severity === 2).map((m) => m.ruleId);
}

test('ESLint weist jede Hausregel als Fehler ab – und lässt das Richtige durch', async () => {
  const head = "import { useState } from 'react';\n";
  const cases = [
    ['ein toter Setter (der tote Scan-Knopf)', 'export function A() { const [x, setX] = useState(0); return x; }',
      '@typescript-eslint/no-unused-vars'],
    ['eine Zahl über das ICU', 'export const s = (n: number) => n.toLocaleString();', 'no-restricted-syntax'],
    ['ein Datum über das ICU', 'export const s = (d: Date) => d.toLocaleDateString();', 'no-restricted-syntax'],
    ['ein Datum über Intl', "export const f = new Intl.DateTimeFormat('de-CH');", 'no-restricted-syntax'],
    ['ein Rollenvergleich', "export const s = (r: string) => r === 'employee';", 'no-restricted-syntax'],
    ['busy sperrt ein Feld', 'export function A({ busy }: { busy: boolean }) { return <input disabled={busy} />; }',
      'no-restricted-syntax'],
  ];
  for (const [what, code, rule] of cases) {
    assert.ok((await rules(head + code)).includes(rule), `ESLint lässt durch: ${what}`);
  }
  const fine = 'export function A({ go }: { go: () => void }) { const [x, _setX] = useState(0); return <b onClick={go}>{x}</b>; }';
  assert.deepEqual(await rules(head + fine), [], 'ESLint weist richtigen Code ab');
});

test('npm run lint ist ESLint selbst – und neben der Flat Config liegt keine alte', () => {
  const pkg = JSON.parse(readFileSync(resolve(SRC, '../package.json'), 'utf8'));
  assert.match(pkg.scripts.lint, /^eslint\b/);
  assert.throws(() => readFileSync(resolve(SRC, '../.eslintrc.json')), 'eine .eslintrc.json liest ESLint 9 nicht');
});

test('die Wächter erkennen ihre Bug-Form', () => {
  const sample = (t) => parse(t, { text: true });
  const keys = moduleKeys();
  assert.equal(moduleNames(sample("if (step.module_type === 'beleg') go();"), keys).length, 1);
  assert.equal(moduleNames(sample('// beleg im Kommentar\nif (step.verifies) go();'), keys).length, 0);
  assert.equal(busyDraws(sample('const a = <div>{!busy && <Knopf />}</div>;')).length, 1);
  assert.equal(busyDraws(sample('const a = <div>{busy ? null : <Knopf />}</div>;')).length, 1);
  assert.equal(busyDraws(sample('function A() { return busy ? null : (<Knopf />); }')).length, 1);
  assert.equal(busyDraws(sample('const a = <div>{busy ? <Spin /> : <Check />}<Knopf disabled={busy} /></div>;')).length, 0);
  assert.equal(joinedNames(sample('const n = `${c.company_name} ${c.legal_form}`;')).length, 1);
  assert.equal(joinedNames(sample("const n = c.company_name + ' ' + c.legal_form;")).length, 1);
  assert.equal(joinedNames(sample('const f = { company_name: c.company_name, legal_form: c.legal_form };')).length, 0);
  assert.ok(CONTROL.test('const p = "a\u0000b";'));
  assert.ok(!CONTROL.test('const p = "a\tb\nc";'));
});
